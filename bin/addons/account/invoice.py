# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
from lxml import etree
import decimal_precision as dp

import netsvc
from osv import fields, osv, orm
from tools.translate import _
from msf_partner import PARTNER_TYPE
from base import currency_date
from tools.safe_eval import safe_eval


class account_invoice(osv.osv):
    _name = "account.invoice"
    _description = 'Invoice'
    _order = 'is_draft desc, internal_number desc, id desc'
#    _inherit = 'signature.object'

    def _auto_init(self, cr, context=None):
        d = super(account_invoice, self)._auto_init(cr, context=context)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'account_invoice_sort_idx'")
        if not cr.fetchone():
            cr.execute('create index account_invoice_sort_idx on account_invoice (is_draft desc, internal_number desc, id desc)')
            cr.commit()
        return d

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            res[invoice.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0
            }
            for line in invoice.invoice_line:
                res[invoice.id]['amount_untaxed'] += line.price_subtotal
            for line in invoice.tax_line:
                res[invoice.id]['amount_tax'] += line.amount
            res[invoice.id]['amount_total'] = res[invoice.id]['amount_tax'] + res[invoice.id]['amount_untaxed']
        return res

    def _get_type(self, cr, uid, context=None):
        if context is None:
            context = {}
        res = context.get('type', 'out_invoice')
        if context.get('search_default_supplier', False) and context.get('default_supplier', False):
            res = 'in_invoice'
        return res

    def _reconciled(self, cr, uid, ids, name, args, context=None):
        res = {}
        for id in ids:
            res[id] = self.test_paid(cr, uid, [id])
        return res

    def _get_reference_type(self, cr, uid, context=None):
        return [('none', _('Free Reference'))]

    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        """
        Residual amount is 0 when invoice counterpart line is totally recconciled.
        If not, residual amount is the total invoice minus all payments. Payments are line that comes from the reconciliation linked to the counterpart line.
        """
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            # UNIFIELD REFACTORING: UF-1536 have change this method
            # Not needed to do process if invoice is draft or paid
            if invoice.state in ['draft', 'paid', 'inv_close']:
                result[invoice.id] = 0.0
                continue
            result[invoice.id] = invoice.amount_total
            # Browse payments to add/delete their amount regarding the invoice type
            for payment in invoice.payment_ids:
                if invoice.type in ['in_invoice', 'out_refund']:
                    result[invoice.id] -= payment.amount_currency
                else:
                    result[invoice.id] += payment.amount_currency
            # Avoid some problems about negative residual amounts or superior amounts: You have to always have a residual amount between 0 and invoice total amount
            if result[invoice.id] < 0:
                result[invoice.id] = 0.0
            if result[invoice.id] > invoice.amount_total:
                result[invoice.id] = invoice.amount_total
        return result

    # Give Journal Items related to the payment reconciled to this invoice
    # Return ids of partial and total payments related to the selected invoices
    def _get_lines(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            id = invoice.id
            res[id] = []
            if not invoice.move_id:
                continue
            data_lines = [x for x in invoice.move_id.line_id if x.account_id.id == invoice.account_id.id]
            partial_ids = []
            for line in data_lines:
                ids_line = []
                if line.reconcile_id:
                    ids_line = line.reconcile_id.line_id
                elif line.reconcile_partial_id:
                    ids_line = line.reconcile_partial_id.line_partial_ids
                l = [x.id for x in ids_line]
                partial_ids.append(line.id)
                res[id] =[x for x in l if x != line.id and x not in partial_ids]
        return res

    def _get_invoice_line(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context):
            result[line.invoice_id.id] = True
        return list(result.keys())

    def _get_invoice_tax(self, cr, uid, ids, context=None):
        result = {}
        for tax in self.pool.get('account.invoice.tax').browse(cr, uid, ids, context=context):
            result[tax.invoice_id.id] = True
        return list(result.keys())

    def _compute_lines_generic(self, cr, uid, ids, name, args, context=None, temp_post_included=False):
        """
        Returns a dict with key = id of the account.invoice, and value = list of the JIs corresponding to Payments of the doc
        If temp_post_included is False:
            - only the reconciled amounts are taken into account
            - (amount of the doc) - (amount of the payment lines) matches with the residual amount on the doc
        If temp_post_included is True, we get all the payment lines to display to the user:
            - the register lines in temp-posted state are taken into account, too
            - these temp-posted lines don't impact the residual amount
            - for these lines we return ALL the lines related to the import made
        """
        if context is None:
            context = {}
        result = {}
        reg_line_obj = self.pool.get('account.bank.statement.line')
        aml_obj = self.pool.get('account.move.line')
        for invoice in self.browse(cr, uid, ids,
                                   fields_to_fetch=['move_id', 'amount_total', 'account_id'], context=context):
            src = []
            lines = []
            if invoice.move_id:
                # US-1882 The payments should only concern the "header line" of the SI on the counterpart account.
                # For example the import of a tax line shouldn't be considered as a payment (out or in).
                invoice_amls = [ml for ml in invoice.move_id.line_id if ml.account_id == invoice.account_id and ml.is_counterpart]
                for m in invoice_amls:
                    temp_lines = set()
                    if m.reconcile_id:
                        temp_lines = set([x.id for x in m.reconcile_id.line_id])
                    else:
                        if m.reconcile_partial_id:
                            temp_lines = set([x.id for x in m.reconcile_partial_id.line_partial_ids])
                        if temp_post_included:  # don't use 'elif' otherwise only hard-posted lines would be returned for a single doc
                            reg_line_ids = reg_line_obj.search(cr, uid,
                                                               [('imported_invoice_line_ids', '=', m.id)],
                                                               order='NO_ORDER', context=context) or []
                            for reg_line in reg_line_obj.browse(cr, uid, reg_line_ids,
                                                                fields_to_fetch=['first_move_line_id', 'imported_invoice_line_ids'],
                                                                context=context):
                                # get the "Imported Invoice(s)" JI
                                first_leg = reg_line.first_move_line_id
                                other_leg_ids = first_leg and aml_obj.search(cr, uid,
                                                                             [('move_id', '=', first_leg.move_id.id),
                                                                              ('id', '!=', first_leg.id),
                                                                              ('reconcile_id', '=', False)],
                                                                             order='NO_ORDER', context=context) or []
                                # if the doc was imported with other account.invoices, get the JIs of these other docs
                                other_doc_ids = []
                                for reg_aml in reg_line.imported_invoice_line_ids:
                                    if reg_aml.id != m.id and not reg_aml.reconcile_id:
                                        other_doc_ids.append(reg_aml.id)
                                    if reg_aml.reconcile_partial_id:
                                        # covers this use case: SI 75 / SI 25 / group import 10 / group import 80 / hardpost 10
                                        for part_aml in reg_aml.reconcile_partial_id.line_partial_ids:
                                            if part_aml.id != reg_aml.id:
                                                other_doc_ids.append(part_aml.id)
                                temp_lines.update(other_leg_ids)
                                temp_lines.update(other_doc_ids)
                    lines += [x for x in temp_lines if x not in lines]
                    src.append(m.id)

            lines = [x for x in lines if x not in src]
            result[invoice.id] = lines
        return result

    def _compute_lines(self, cr, uid, ids, name, args, context=None):
        """
        Get the reconciled payment lines (hard-posted register lines)
        """
        if context is None:
            context = {}
        return self._compute_lines_generic(cr, uid, ids, name, args, context, temp_post_included=False)

    def _compute_lines_to_display(self, cr, uid, ids, name, args, context=None):
        """
        Get all the payment lines (hard-posted and temp-posted register lines)
        """
        if context is None:
            context = {}
        return self._compute_lines_generic(cr, uid, ids, name, args, context, temp_post_included=True)

    def _get_invoice_from_line(self, cr, uid, ids, context=None):
        move = {}
        for line in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    move[line2.move_id.id] = True
            if line.reconcile_id:
                for line2 in line.reconcile_id.line_id:
                    move[line2.move_id.id] = True
        invoice_ids = []
        if move:
            invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('move_id','in',list(move.keys()))], context=context)
        return invoice_ids

    def _get_invoice_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True

        invoice_ids = []
        if move:
            invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('move_id','in',list(move.keys()))], context=context)
        return invoice_ids

    def _get_journal_type(self, cr, uid, context=None):
        return self.pool.get('account.journal').get_journal_type(cr, uid, context)

    def _get_is_asset_activated(self, cr, uid, ids, field_name=None, arg=None, context=None):
        if not ids:
            return {}
        res = {}
        asset = self.pool.get('unifield.setup.configuration').get_config(cr, uid, key='fixed_asset_ok')
        for _id in ids:
            res[_id] = asset
        return res

    def _get_state_for_po(self, cr, uid, ids, field_name=None, arg=None, context=None):
        if not ids:
            return {}
        if not context:
            context = {}
        res = {}
        res_open = self._get_imported_state(cr, uid, ids, context=context)
        for inv in self.browse(cr, uid, ids, context):
            state_for_po = inv.state
            if state_for_po == 'open':
                if res_open[inv.id] == 'imported':
                    state_for_po = 'open_imported'
                elif res_open[inv.id] == 'not':
                    state_for_po = 'open_not_imported'
                elif res_open[inv.id] == 'partial':
                    state_for_po = 'open_partial_imported'
            res[inv.id] = state_for_po
        return res

    _columns = {
        'name': fields.char('Description', size=256, select=True, readonly=True, states={'draft': [('readonly', False)]}),
        'origin': fields.char('Source Document', size=512, help="Reference of the document that produced this invoice.", readonly=True, states={'draft':[('readonly',False)]}),
        'type': fields.selection([
            ('out_invoice','Customer Invoice'),
            ('in_invoice','Supplier Invoice'),
            ('out_refund','Customer Refund'),
            ('in_refund','Supplier Refund'),
        ],'Type', readonly=True, select=True, change_default=True),

        'number': fields.related('move_id','name', type='char', readonly=True, size=64, relation='account.move', store=True, string='Number', select=1),
        'internal_number': fields.char('Invoice Number', size=32, readonly=True, help="Unique number of the invoice, computed automatically when the invoice is created."),
        'reference': fields.char('Invoice Reference', size=64, help="The partner reference of this invoice."),
        'reference_type': fields.selection(_get_reference_type, 'Reference Type',
                                           readonly=True, states={'draft':[('readonly',False)]}),
        'comment': fields.text('Additional Information'),

        'state': fields.selection([
            ('draft','Draft'),
            ('proforma','Pro-forma'),
            ('proforma2','Pro-forma'),
            ('open','Open'),
            ('paid','Paid'),
            ('done', 'Done'),
            ('inv_close','Closed'),
            ('cancel','Cancelled')
        ],'State', select=True, readonly=True,
            help=' * The \'Draft\' state is used when a user is encoding a new and unconfirmed Invoice. \
            \n* The \'Pro-forma\' when invoice is in Pro-forma state,invoice does not have an invoice number. \
            \n* The \'Open\' state is used when user create invoice,a invoice number is generated.Its in open state till user does not pay invoice. \
            \n* The \'Paid\' state is set automatically when invoice is paid.\
            \n* The \'Done\' state (only for donation invoices) is set automatically when donation invoice is validated and was not cancelled.\
            \n* The \'Cancelled\' state is used when user cancel invoice.'),
        'date_invoice': fields.date('Invoice Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                            'inv_close':[('readonly',True)], 'done':[('readonly',True)]},
                                    select=True, help="Keep empty to use the current date"),
        'date_due': fields.date('Due Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                    'inv_close':[('readonly',True)], 'done':[('readonly',True)]}, select=True,
                                help="If you use payment terms, the due date will be computed automatically at the generation "\
                                "of accounting entries. If you keep the payment term and the due date empty, it means direct payment. The payment term may compute several due dates, for example 50% now, 50% in one month."),
        'partner_id': fields.many2one('res.partner', 'Partner', change_default=True, readonly=True, required=True, states={'draft':[('readonly',False)]}),
        'address_contact_id': fields.many2one('res.partner.address', 'Contact Address', readonly=True, states={'draft':[('readonly',False)]}),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=True, states={'draft':[('readonly',False)]}),
        'payment_term': fields.many2one('account.payment.term', 'Payment Term',readonly=True, states={'draft':[('readonly',False)]},
                                        help="If you use payment terms, the due date will be computed automatically at the generation "\
                                        "of accounting entries. If you keep the payment term and the due date empty, it means direct payment. "\
                                        "The payment term may compute several due dates, for example 50% now, 50% in one month."),
        'period_id': fields.many2one('account.period', 'Force Period', domain=[('state','<>','done')], help="Keep empty to use the period of the validation(invoice) date.", readonly=True, states={'draft':[('readonly',False)]}),

        'account_id': fields.many2one('account.account', 'Account', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="The partner account used for this invoice."),
        'invoice_line': fields.one2many('account.invoice.line', 'invoice_id', 'Invoice Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'tax_line': fields.one2many('account.invoice.tax', 'invoice_id', 'Tax Lines'),
        'move_id': fields.many2one('account.move', 'Journal Entry', readonly=True, select=1, ondelete='restrict', help="Link to the automatically generated Journal Items."),
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Untaxed',
                                          store={
            'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line'], 20),
            'account.invoice.tax': (_get_invoice_tax, None, 20),
            'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
        },
            multi='all'),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Tax',
                                      store={
            'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line'], 20),
            'account.invoice.tax': (_get_invoice_tax, None, 20),
            'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
        },
            multi='all'),
        'amount_total': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Account'), string='Total',
                                        store={
            'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line'], 20),
            'account.invoice.tax': (_get_invoice_tax, None, 20),
            'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
        },
            multi='all'),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft':[('readonly',False)]}, context={'hide_active_buttons': True}),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, hide_default_menu=True, readonly=True, states={'draft':[('readonly',False)]}),
        'journal_type': fields.related('journal_id', 'type', type='selection', string='Journal Type',
                                       selection=_get_journal_type, store=False, write_relate=False),
        'company_id': fields.many2one('res.company', 'Company', required=True, change_default=True, readonly=True, states={'draft':[('readonly',False)]}),
        'check_total': fields.float('Total', digits_compute=dp.get_precision('Account'), states={'open':[('readonly',True)],'inv_close':[('readonly',True)],
                                                                                                 'paid':[('readonly',True)], 'done':[('readonly',True)]}),
        'reconciled': fields.function(_reconciled, method=True, string='Paid/Reconciled', type='boolean',
                                      store={
                                          'account.invoice': (lambda self, cr, uid, ids, c={}: ids, None, 50), # Check if we can remove ?
                                          'account.move.line': (_get_invoice_from_line, None, 50),
                                          'account.move.reconcile': (_get_invoice_from_reconcile, None, 50),
                                      }, help="The Journal Entry of the invoice have been totally reconciled with one or several Journal Entries of payment."),
        'partner_bank_id': fields.many2one('res.partner.bank', 'Bank Account',
                                           help='Bank Account Number, Company bank account if Invoice is customer or supplier refund, otherwise Partner bank account number.', readonly=True, states={'draft':[('readonly',False)]}),
        'move_lines':fields.function(_get_lines, method=True, type='many2many', relation='account.move.line', string='Entry Lines'),
        'residual': fields.function(_amount_residual, method=True, digits_compute=dp.get_precision('Account'), string='Residual',
                                    store={
            'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','move_id', 'state'], 50),
            'account.invoice.tax': (_get_invoice_tax, None, 50),
            'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 50),
            'account.move.line': (_get_invoice_from_line, None, 50),
            'account.move.reconcile': (_get_invoice_from_reconcile, None, 50),
        },
            help="Remaining amount due."),
        'payment_ids': fields.function(_compute_lines, method=True, relation='account.move.line', type="many2many", string='Payments'),
        'payment_to_display_ids': fields.function(_compute_lines_to_display, method=True, relation='account.move.line',
                                                  type='many2many', string='Payments', store=False),
        'move_name': fields.char('Journal Entry', size=64, readonly=True, states={'draft':[('readonly',False)]}),
        'user_id': fields.many2one('res.users', 'Salesman', readonly=True, states={'draft':[('readonly',False)]}),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position', readonly=True, states={'draft':[('readonly',False)]}),
        'is_draft': fields.boolean('Is draft', help='used to sort invoices (draft on top)', readonly=1),
        'is_asset_activated': fields.function(_get_is_asset_activated, method=True, type='boolean', string='Asset Active'),
        'state_for_po': fields.function(_get_state_for_po, method=True, type='selection', string='State',
                                        selection=[('draft','Draft'),
                                                   ('proforma','Pro-forma'),
                                                   ('proforma2','Pro-forma'),
                                                   ('open_not_imported', 'Open Invoice not imported'),
                                                   ('open_imported', 'Open Invoice imported'),
                                                   ('open_partial_imported', 'Open Invoice partially imported'),
                                                   ('paid','Paid'),
                                                   ('done', 'Done'),
                                                   ('inv_close','Closed'),
                                                   ('cancel','Cancelled')]),

    }
    _defaults = {
        'type': _get_type,
        'state': 'draft',
        'is_draft': True,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.invoice', context=c),
        'reference_type': 'none',
        'check_total': 0.0,
        'internal_number': '',
        'user_id': lambda s, cr, u, c: u,
    }

    def _set_invoice_name(self, cr, uid, doc, context=None):
        """
        Sets the correct invoice name to be displayed depending on the doc_type
        """
        if context is None:
            context = {}
        if context.get('doc_type'):
            for doc_type in self._get_invoice_type_list(cr, uid, context=context):
                if context['doc_type'] in doc_type:
                    doc.attrib['string'] = doc_type[1]
                    break
        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if view_id and isinstance(view_id, (list, tuple)):
            view_id = view_id[0]
        res = super(account_invoice,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            if context.get('type', 'out_invoice') == 'in_refund' or context.get('doc_type', '') == 'isr':
                nodes = doc.xpath("//field[@name='amount_to_pay']")
                for node in nodes:
                    node.set('string', _('Amount to be refunded'))
            # adapt the form name depending on the doc_type (used e.g. when clicking on a res.log)
            self._set_invoice_name(cr, uid, doc, context=context)
            """
            Restriction on allowed partners:
            - for STV/STR: Intersection or External customers only
            - for ISI/ISR: Intersection suppliers only
            - for SI/SR/DI: non-Intersection suppliers only
            """
            partner_domain = ""
            if context.get('doc_type', '') in ('stv', 'str') or (
                context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'sale' and
                not context.get('is_debit_note', False) and not context.get('is_intermission', False)
            ):
                partner_domain = "[('partner_type', 'in', ('section', 'external')), ('customer', '=', True)]"
            elif context.get('doc_type', '') in ('isi', 'isr'):
                partner_domain = "[('partner_type', '=', 'section'), ('supplier', '=', True)]"
            elif (context.get('doc_type', '') in ('si', 'sr', 'di')) or \
                (context.get('type') == 'in_invoice' and context.get('journal_type') == 'purchase') or \
                    (context.get('type') == 'in_refund' and context.get('journal_type') == 'purchase_refund'):
                partner_domain = "[('partner_type', '!=', 'section'), ('supplier', '=', True)]"
            if partner_domain:
                partner_nodes = doc.xpath("//field[@name='partner_id']")
                for node in partner_nodes:
                    node.set('domain', partner_domain)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        elif view_type == 'tree':
            doc = etree.XML(res['arch'])
            # (US-777) Remove the possibility to create new invoices through the "Advance Return" Wizard
            if context.get('from_wizard') and context.get('from_wizard')['model'] == 'wizard.cash.return':
                doc.set('hide_new_button', 'True')
            # adapt the name of the Partner field depending on the view
            nodes = doc.xpath("//field[@name='partner_id']")
            if context.get('generic_invoice') or context.get('journal_type') == 'intermission':
                # for tree views combining Customer and Supplier Invoices, or for IVI/IVO
                partner_string = _('Partner')
            elif context.get('journal_type', False) == 'inkind':
                partner_string = _('Donor')
            elif context.get('type', 'out_invoice') in ('in_invoice', 'in_refund') or context.get('doc_type', '') in ('isi', 'isr'):
                partner_string = _('Supplier')
            else:
                partner_string = _('Customer')
            for node in nodes:
                node.set('string', partner_string)
            # ensure that the doc name remains consistent even after clicking on a filter in the Search View
            self._set_invoice_name(cr, uid, doc, context=context)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        elif view_type == 'search':
            # remove the Cancel filter in all invoices but IVO and STV (in Donations the filter is named differently)
            context_ivo = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'intermission' and \
                context.get('is_intermission', False) and context.get('intermission_type', False) == 'out'
            context_stv = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'sale' and \
                not context.get('is_debit_note', False)
            if not context_ivo and not context_stv:
                doc = etree.XML(res['arch'])
                filter_node = doc.xpath("/search/group[1]/filter[@name='cancel_state']")
                if filter_node:
                    filter_node[0].getparent().remove(filter_node[0])
                res['arch'] = etree.tostring(doc, encoding='unicode')
        if view_type in ('tree', 'search') and (context.get('type') in ['out_invoice', 'out_refund'] or context.get('doc_type') == 'str'):
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='supplier_reference']")
            for node in nodes:
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        vals['is_draft'] = vals.get('state', 'draft') == 'draft'
        try:
            res = super(account_invoice, self).create(cr, uid, vals, context)
            for inv_id, name in self.name_get(cr, uid, [res], context=context):
                ctx = context.copy()
                if 'is_intermission' in vals:
                    ctx.update({'is_intermission': vals['is_intermission']})
                if 'type' in vals:
                    ctx.update({'type': vals['type']})
                if '_terp_view_name' in ctx:
                    del ctx['_terp_view_name']
                # if we click on the res.log...
                ctx.update({'from_inv_form': True,  # ...we are sent to the invoice form...
                            'from_split': False,  # ...and won't be in a split process.
                            })
                message = _("Invoice '%s' is waiting for validation.") % name
                self.log(cr, uid, inv_id, message, context=ctx)
            return res
        except Exception as e:
            if '"journal_id" viol' in e.args[0]:
                raise orm.except_orm(_('Configuration Error!'),
                                     _('There is no Accounting Journal of type Sale/Purchase defined!'))
            else:
                raise orm.except_orm(_('Unknown Error'), str(e))

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date
        """
        if not ids:
            return True
        if context is None:
            context = {}

        if 'state' in vals:
            vals['is_draft'] = vals['state'] == 'draft'

        return super(account_invoice, self).write(cr, uid, ids, vals, context=context)

    def confirm_paid(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        # if reconciled with at least 1 liquidity journal then paid else cancel aka Closed
        cr.execute("""
            SELECT i.id, min(j.id), i.number
            FROM account_invoice i
            LEFT JOIN account_move_line l ON i.move_id=l.move_id
            LEFT JOIN account_move_line rec_line ON rec_line.reconcile_id = l.reconcile_id
            LEFT JOIN account_journal j ON j.id = rec_line.journal_id AND j.type in ('cash', 'bank', 'cheque')
            WHERE i.id IN %s
            AND l.reconcile_id is not null
            AND l.account_id=i.account_id
            AND l.is_counterpart
            GROUP BY i.id, i.number""", (tuple(ids), )
                   )

        for x in cr.fetchall():
            if x[1]:
                state = 'paid'
                display_state = _('paid')
            else:
                state = 'inv_close'
                display_state = _('closed')

            self.write(cr, uid, x[0], {'state': state}, context=context)
            self.log(cr, uid, x[0], _("Invoice '%s' is %s.") % (x[2], display_state))

        return True

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoices = self.read(cr, uid, ids, ['state', 'synced', 'from_supply'], context=context)
        unlink_ids = []
        for t in invoices:
            if t['state'] not in ('draft', 'cancel'):
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete invoice(s) that are already opened or paid !'))
            elif t['from_supply']:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete invoice(s) generated by a Supply workflow!'))
            elif t['synced']:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete invoice(s) set as "Synchronized"!'))
            else:
                unlink_ids.append(t['id'])
        osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
        return True

    def onchange_partner_id(self, cr, uid, ids, type, partner_id,\
                            date_invoice=False, payment_term=False, partner_bank_id=False, company_id=False):
        invoice_addr_id = False
        contact_addr_id = False
        partner_payment_term = False
        acc_id = False
        bank_id = False
        fiscal_position = False
        partner_type = False

        opt = [('uid', str(uid))]
        if partner_id:

            opt.insert(0, ('id', partner_id))
            res = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['contact', 'invoice'])
            contact_addr_id = res['contact']
            invoice_addr_id = res['invoice']
            p = self.pool.get('res.partner').browse(cr, uid, partner_id)
            partner_type = p.partner_type  # update the partner type immediately as it is used in a domain in attrs


            if type in ('out_invoice', 'out_refund'):
                acc_id = p.property_account_receivable.id
            else:
                acc_id = p.property_account_payable.id
            fiscal_position = p.property_account_position and p.property_account_position.id or False
            partner_payment_term = p.property_payment_term and p.property_payment_term.id or False
            if p.bank_ids:
                bank_id = p.bank_ids[0].id

        result = {'value': {
            'address_contact_id': contact_addr_id,
            'address_invoice_id': invoice_addr_id,
            'account_id': acc_id,
            'payment_term': partner_payment_term,
            'fiscal_position': fiscal_position,
            'partner_type': partner_type,
        }
        }

        if type in ('in_invoice', 'in_refund'):
            result['value']['partner_bank_id'] = bank_id
            if partner_id and p.ref:
                result['value']['supplier_reference'] = p.ref

        if payment_term != partner_payment_term:
            if partner_payment_term:
                to_update = self.onchange_payment_term_date_invoice(
                    cr, uid, ids, partner_payment_term, date_invoice)
                result['value'].update(to_update['value'])
            else:
                result['value']['date_due'] = False

        if partner_bank_id != bank_id:
            to_update = self.onchange_partner_bank(cr, uid, ids, bank_id)
            result['value'].update(to_update['value'])
        return result

    def get_due_date(self, cr, uid, payment_term_id, date_invoice, context=None):
        """
        If a payment_term_id is given, returns the due date based on the payment term and the invoice date,
        else returns False
        """
        if context is None:
            context = {}
        due_date = False
        if payment_term_id:
            pt_obj = self.pool.get('account.payment.term')
            if not date_invoice:
                date_invoice = time.strftime('%Y-%m-%d')
            pterm_list = pt_obj.compute(cr, uid, payment_term_id, value=1, date_ref=date_invoice, context=context)
            if pterm_list:
                pterm_list = [line[0] for line in pterm_list]
                pterm_list.sort()
                due_date = pterm_list[-1]
            else:
                raise osv.except_osv(_('Data Insufficient !'), _('The Payment Term of Supplier does not have Payment Term Lines(Computation) defined !'))
        return due_date

    def onchange_payment_term_date_invoice(self, cr, uid, ids, payment_term_id, date_invoice):
        res = {}
        due_date = self.get_due_date(cr, uid, payment_term_id, date_invoice)
        if due_date:
            res = {'value': {'date_due': due_date}}
        return res

    def onchange_invoice_line(self, cr, uid, ids, lines):
        return {}

    def onchange_partner_bank(self, cursor, user, ids, partner_bank_id=False):
        return {'value': {}}

    def onchange_company_id(self, cr, uid, ids, company_id, part_id, type, invoice_line, currency_id, context=None):
        val = {}
        account_obj = self.pool.get('account.account')
        inv_line_obj = self.pool.get('account.invoice.line')
        if company_id and part_id and type:
            if ids:
                if company_id:
                    inv_obj = self.browse(cr,uid,ids)
                    for line in inv_obj[0].invoice_line:
                        if line.account_id:
                            if line.account_id.company_id.id != company_id:
                                result_id = account_obj.search(cr, uid, [('name','=',line.account_id.name),('company_id','=',company_id)])
                                if not result_id:
                                    raise osv.except_osv(_('Configuration Error !'),
                                                         _('Can not find account chart for this company in invoice line account, Please Create account.'))
                                inv_line_obj.write(cr, uid, [line.id], {'account_id': result_id[0]})
            else:
                if invoice_line:
                    for inv_line in invoice_line:
                        obj_l = account_obj.browse(cr, uid, inv_line[2]['account_id'])
                        if obj_l.company_id.id != company_id:
                            raise osv.except_osv(_('Configuration Error !'),
                                                 _('Invoice line account company does not match with invoice company.'))
                        else:
                            continue
        if currency_id and company_id:
            currency = self.pool.get('res.currency').browse(cr, uid, currency_id)
            if currency.company_id and currency.company_id.id != company_id:
                val['currency_id'] = False
            else:
                val['currency_id'] = currency.id
        return {'value': val}

    def onchange_synced(self, cr, uid, ids, synced, partner_id):
        """
        Resets "synced" field and informs the user in case the box is ticked whereas the partner is neither Intermission nor Intersection
        """
        res = {}
        partner_obj = self.pool.get('res.partner')
        if synced and partner_id:
            if partner_obj.browse(cr, uid, partner_id, fields_to_fetch=['partner_type']).partner_type not in ('intermission', 'section'):
                warning = {
                    'title': _('Warning!'),
                    'message': _('Synchronization is allowed only with Intermission and Intersection partners.')
                }
                res['warning'] = warning
                res['value'] = {'synced': False, }
        return res

    # go from canceled state to draft state
    def action_cancel_draft(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        for inv_id in ids:
            wf_service.trg_delete(uid, 'account.invoice', inv_id, cr)
            wf_service.trg_create(uid, 'account.invoice', inv_id, cr)
        return True

    # Workflow stuff
    #################

    def move_line_id_payment_get(self, cr, uid, ids, *args):
        '''
            return the ids of the SI header move line
        '''
        if not ids:
            return []
        result = self.move_line_id_payment_gets(cr, uid, ids, *args)
        return result.get(ids[0], [])

    def move_line_id_payment_gets(self, cr, uid, ids, *args):
        if not ids:
            return {}

        res = {}
        cr.execute("""
            SELECT i.id, l.id
            FROM account_move_line l
            LEFT JOIN account_invoice i ON (i.move_id=l.move_id)
            WHERE i.id IN %s
            AND l.account_id=i.account_id
            AND l.is_counterpart""", (tuple(ids), )
                   )
        for r in cr.fetchall():
            res.setdefault(r[0], [])
            res[r[0]].append(r[1])
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context = {}

        if default is None:
            default = {}

        default.update({
            'state':'draft',
            'number': False,
            'move_id':False,
            'move_name':False,
            'internal_number': '',
            'main_purchase_id': False,
            'counterpart_inv_number': False,
            'counterpart_inv_status': False,
            'refunded_invoice_id': False,
        })

        inv = self.browse(cr, uid, [id], fields_to_fetch=['analytic_distribution_id', 'doc_type'], context=context)[0]
        if not context.get('from_split'):  # some values are kept in case of inv. generated via the "Split" feature
            default.update({
                'from_supply': False,
            })
            # Reset the sync tag, except in case of manual duplication of IVO/STV.
            if not context.get('from_copy_web') or inv.doc_type not in ('ivo', 'stv'):
                default.update({
                    'synced': False,
                })
        if 'date_invoice' not in default:
            default.update({
                'date_invoice':False
            })
        if 'date_due' not in default:
            default.update({
                'date_due':False
            })
        if inv.analytic_distribution_id:
            default.update({'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, inv.analytic_distribution_id.id, {}, context=context)})

        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def test_paid(self, cr, uid, ids, *args):
        res = self.move_line_id_payment_get(cr, uid, ids)
        if not res:
            return False
        ok = True
        for id in res:
            cr.execute('select reconcile_id from account_move_line where id=%s', (id,))
            ok = ok and  bool(cr.fetchone()[0])
        return ok

    def button_reset_taxes(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ait_obj = self.pool.get('account.invoice.tax')
        for id in ids:
            cr.execute("DELETE FROM account_invoice_tax WHERE invoice_id=%s AND manual is False", (id,))
            partner = self.browse(cr, uid, id, context=ctx).partner_id
            if partner.lang:
                ctx.update({'lang': partner.lang})
            for taxe in list(ait_obj.compute(cr, uid, id, context=ctx).values()):
                ait_obj.create(cr, uid, taxe)
        # Update the stored value (fields.function), so we write to trigger recompute
        self.pool.get('account.invoice').write(cr, uid, ids, {'invoice_line':[]}, context=ctx)
        return True

    def button_compute(self, cr, uid, ids, context=None, set_total=False):
        self.button_reset_taxes(cr, uid, ids, context)
        for inv in self.browse(cr, uid, ids, context=context):
            if set_total:
                self.pool.get('account.invoice').write(cr, uid, [inv.id], {'check_total': inv.amount_total})
        return True

    def _convert_ref(self, cr, uid, ref):
        return (ref or '').replace('/','')

    def _get_analytic_lines(self, cr, uid, id):
        return self.pool.get('account.invoice.line').move_line_get(cr, uid, id)

    def action_date_assign(self, cr, uid, ids, *args):
        for inv in self.browse(cr, uid, ids):
            res = self.onchange_payment_term_date_invoice(cr, uid, inv.id, inv.payment_term.id, inv.date_invoice)
            if res and res['value']:
                self.write(cr, uid, [inv.id], res['value'])
        return True

    def finalize_invoice_move_lines(self, cr, uid, inv, line):
        """
        Hook that changes move line data before write them.
        Add a link between partner move line and invoice.
        Add invoice document date to data.
        """
        def is_partner_line(dico):
            if isinstance(dico, dict):
                if dico:
                    # In case where no amount_currency filled in, then take debit - credit for amount comparison
                    amount = dico.get('amount_currency', False) or (dico.get('debit', 0.0) - dico.get('credit', 0.0))
                    if amount == inv.amount_total and dico.get('partner_id', False) == inv.partner_id.id:
                        return True
            return False
        new_line = []
        for el in line:
            if el[2]:
                el[2].update({'document_date': inv.document_date})
            if el[2] and is_partner_line(el[2]):
                el[2].update({'invoice_partner_link': inv.id})
                new_line.append((el[0], el[1], el[2]))
            else:
                new_line.append(el)
        return new_line

    def check_tax_lines(self, cr, uid, inv, compute_taxes, ait_obj):
        if not inv.tax_line:
            for tax in list(compute_taxes.values()):
                ait_obj.create(cr, uid, tax)
        else:
            tax_key = []
            for tax in inv.tax_line:
                if tax.manual:
                    continue
                key = tax.account_tax_id.id  # taxes are grouped by id
                tax_key.append(key)
                if not key in compute_taxes:
                    raise osv.except_osv(_('Warning !'),
                                         _('Global taxes defined, click on compute to update tax base !'))
                base = compute_taxes[key]['base']
                if abs(base - tax.base) > inv.company_id.currency_id.rounding:
                    raise osv.except_osv(_('Warning !'), _('Tax base different !\nClick on compute to update tax base'))
            for key in compute_taxes:
                if not key in tax_key:
                    raise osv.except_osv(_('Warning !'), _('Taxes missing !'))

    def compute_invoice_totals(self, cr, uid, inv, company_currency, ref, invoice_move_lines):
        total = 0
        for i in invoice_move_lines:
            i['currency_id'] = inv.currency_id.id
            i['amount_currency'] = i['price']
            i['ref'] = ref
            # the direction of the amounts depends on the invoice type
            if inv.doc_type in ('stv', 'ivo', 'dn', 'sr', 'isr'):
                i['price'] = -i['price']
                i['amount_currency'] = - i['amount_currency']
                i['change_sign'] = True
            else:  # 'str', 'ivi', 'si', 'di', 'isi', 'cr', 'donation'
                i['change_sign'] = False
            total -= i['amount_currency']
        return total, invoice_move_lines

    def inv_line_characteristic_hashcode(self, invoice, invoice_line):
        """Overridable hashcode generation for invoice lines. Lines having the same hashcode
        will be grouped together if the journal has the 'group line' option. Of course a module
        can add fields to invoice lines that would need to be tested too before merging lines
        or not."""
        return "%s-%s-%s-%s-%s"%(
            invoice_line['account_id'],
            invoice_line.get('tax_code_id',"False"),
            invoice_line.get('product_id',"False"),
            invoice_line.get('analytic_account_id',"False"),
            invoice_line.get('date_maturity',"False"))

    def group_lines(self, cr, uid, iml, line, inv):
        """Merge account move lines (and hence analytic lines) if invoice line hashcodes are equals"""
        if inv.journal_id.group_invoice_lines:
            line2 = {}
            for x, y, l in line:
                tmp = self.inv_line_characteristic_hashcode(inv, l)

                if tmp in line2:
                    am = line2[tmp]['debit'] - line2[tmp]['credit'] + (l['debit'] - l['credit'])
                    line2[tmp]['debit'] = (am > 0) and am or 0.0
                    line2[tmp]['credit'] = (am < 0) and -am or 0.0
                    line2[tmp]['tax_amount'] += l['tax_amount']
                    line2[tmp]['analytic_lines'] += l['analytic_lines']
                else:
                    line2[tmp] = l
            line = []
            for key, val in list(line2.items()):
                line.append((0,0,val))
        return line

    def _hook_period_id(self, cr, uid, inv, context=None):
        """
        Give matches period that are not draft and not HQ-closed from given date.
        Do not use special periods as period 13, 14 and 15.
        """
        # Some verifications
        if not context:
            context = {}
        if not inv:
            return False
        # NB: there is some period state. So we define that we choose only open period (so not draft and not done)
        res = self.pool.get('account.period').search(cr, uid, [('date_start','<=',inv.date_invoice or time.strftime('%Y-%m-%d')),
                                                               ('date_stop','>=',inv.date_invoice or time.strftime('%Y-%m-%d')), ('state', 'not in', ['created', 'done']),
                                                               ('company_id', '=', inv.company_id.id), ('special', '=', False)], context=context, order="date_start ASC, name ASC")
        return res

    def action_move_create(self, cr, uid, ids, *args):
        """Creates invoice related analytics and financial move lines"""
        ait_obj = self.pool.get('account.invoice.tax')
        context = {}
        for inv in self.browse(cr, uid, ids):
            if not inv.journal_id.sequence_id:
                raise osv.except_osv(_('Error !'), _('Please define sequence on invoice journal'))
            if not inv.invoice_line:
                raise osv.except_osv(_('No Invoice Lines !'), _('Please create some invoice lines.'))
            if inv.move_id:
                continue

            if not inv.date_invoice:
                self.write(cr, uid, [inv.id], {'date_invoice':time.strftime('%Y-%m-%d')})
            company_currency = inv.company_id.currency_id.id
            # create the analytical lines
            # one move line per invoice line
            iml = self._get_analytic_lines(cr, uid, inv.id)
            # check if taxes are all computed
            ctx = context.copy()
            ctx.update({'lang': inv.partner_id.lang})
            compute_taxes = ait_obj.compute(cr, uid, inv.id, context=ctx)
            self.check_tax_lines(cr, uid, inv, compute_taxes, ait_obj)

            if inv.doc_type in ('si', 'sr', 'donation') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding/2.0):
                raise osv.except_osv(_('Bad total !'), _('Please verify the price of the invoice !\nThe real total does not match the computed total.'))

            if inv.payment_term:
                total_fixed = total_percent = 0
                for line in inv.payment_term.line_ids:
                    if line.value == 'fixed':
                        total_fixed += line.value_amount
                    if line.value == 'procent':
                        total_percent += line.value_amount
                total_fixed = (total_fixed * 100) / (inv.amount_total or 1.0)
                if (total_fixed + total_percent) > 100:
                    raise osv.except_osv(_('Error !'), _("Cannot create the invoice !\nThe payment term defined gives a computed amount greater than the total invoiced amount."))

            # one move line per tax line
            iml += ait_obj.move_line_get(cr, uid, inv.id)
            # UFTP-380: If the name is empty or a space character, by default it is set to '/', otherwise it will cause problem for the sync on destination instance
            for il in iml:
                if not il['name']:
                    il['name'] = '/'

            # UTP-594: Check the Name according to new requests of this ticket
            name = inv['name'] or '/'
            entry_type = ''
            if inv.type in ('in_invoice', 'in_refund'):
                # UTP-594: Get ref and name
                if inv.type == 'in_invoice':
                    is_ivi = inv.is_intermission and not inv.is_debit_note and not inv.is_inkind_donation
                    # SI or ISI
                    is_si = not inv.is_direct_invoice and not inv.is_inkind_donation and not inv.is_debit_note and not inv.is_intermission
                    intersection = inv.partner_id.partner_type == 'section'
                    external = inv.partner_id.partner_type == 'external'
                    if is_ivi or (is_si and intersection) or (is_si and external):
                        # For an IVI, or an SI with an intersection or external supplier, use the doc description
                        name = inv.name or '/'
                    else:
                        name = inv.origin and inv.origin or '/'
                    ref = inv.origin and inv.origin or inv.reference and inv.reference
                else:
                    name = inv.name and inv.name or '/'
                    ref = inv.origin and inv.origin

                entry_type = 'journal_pur_voucher'
                if inv.type == 'in_refund':
                    entry_type = 'cont_voucher'
            else:
                ref = self._convert_ref(cr, uid, inv.number)
                entry_type = 'journal_sale_vou'
                if inv.type == 'out_refund':
                    entry_type = 'cont_voucher'

            # create one move line for the total and possibly adjust the other lines amount
            total = 0
            total, iml = self.compute_invoice_totals(cr, uid, inv, company_currency, ref, iml)
            acc_id = inv.account_id.id

            totlines = False
            if inv.payment_term:
                totlines = self.pool.get('account.payment.term').compute(cr,
                                                                         uid, inv.payment_term.id, total, inv.date_invoice or False)
            if totlines:
                res_amount_currency = total
                i = 0
                for t in totlines:
                    amount_currency = t[1]

                    # last line add the diff
                    res_amount_currency -= amount_currency or 0
                    i += 1
                    if i == len(totlines):
                        amount_currency += res_amount_currency

                    # UNIFIELD REFACTORING: is_counterpart field added (UF-1536)
                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': acc_id,
                        'date_maturity': t[0],
                        'amount_currency': t[1],
                        'currency_id': inv.currency_id.id,
                        'ref': ref,
                        'is_counterpart': True,
                    })
            else:
                # UNIFIELD REFACTORING: is_counterpart field added (UF-1536)
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': acc_id,
                    'date_maturity': inv.date_due or False,
                    'amount_currency': total,
                    'currency_id': inv.currency_id.id,
                    'ref': ref,
                    'reference': ref, # UTP-594: Use both ref and reference
                    'is_counterpart': True,
                })

            date = inv.date_invoice or time.strftime('%Y-%m-%d')
            part = inv.partner_id.id

            line = [(0,0,self.line_get_convert(cr, uid, x, part, date, context={})) for x in iml]

            line = self.group_lines(cr, uid, iml, line, inv)

            journal_id = inv.journal_id.id
            journal = self.pool.get('account.journal').browse(cr, uid, journal_id)
            if journal.centralisation:
                raise osv.except_osv(_('UserError'),
                                     _('Cannot create invoice move on centralised journal'))

            line = self.finalize_invoice_move_lines(cr, uid, inv, line)

            # UTP-594: Get the ref from Inv
            move_ref = inv.reference and inv.reference or inv.name
            if inv.type in ('in_invoice'):
                move_ref = inv.origin and inv.origin or inv.reference and inv.reference or inv.number
            if inv.type in ('in_refund'):
                move_ref = inv.name and inv.name

            move = {
                'ref': move_ref,
                'line_id': line,
                'journal_id': journal_id,
                'date': date,
                'type': entry_type,
                'narration':inv.comment
            }
            period_id = inv.period_id and inv.period_id.id or False
            if not period_id:
                period_ids = self._hook_period_id(cr, uid, inv, context=context)
                if period_ids:
                    period_id = period_ids[0]
            if period_id:
                move['period_id'] = period_id
                for i in line:
                    i[2]['period_id'] = period_id

            #  ticket utp917 - need seqnums variable in the context if ir is in *args
            for argdict in args:
                if 'seqnums' in argdict:
                    context['seqnums'] = argdict['seqnums']

            context.update({'from_invoice_move_creation': True})
            move_id = self.pool.get('account.move').create(cr, uid, move, context=context)
            new_move_name = self.pool.get('account.move').browse(cr, uid, move_id).name
            # make the invoice point to that move
            self.write(cr, uid, [inv.id], {'move_id': move_id,'period_id':period_id, 'move_name':new_move_name})
            if inv.doc_type in ('si', 'isi', 'ivi'):
                self._create_asset_form(cr, uid, inv.id, context)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            self.pool.get('account.move').post(cr, uid, [move_id], context={'invoice':inv})
        self._log_event(cr, uid, ids)
        return True


    def _create_asset_form(self, cr, uid, inv_id, context=None):
        if not self.pool.get('unifield.setup.configuration').get_config(cr, uid, key='fixed_asset_ok'):
            return True
        inv_line_obj = self.pool.get('account.invoice.line')
        asset_obj = self.pool.get('product.asset')
        line_ids = inv_line_obj.search(cr, uid, [('invoice_id', '=', inv_id), ('is_asset', '=', True)], context=context)
        for line in inv_line_obj.browse(cr, uid,  line_ids, context=None):
            for idx in range(0, int(line.quantity)):
                asset_id = asset_obj.create(cr, uid, {
                    'product_id': line.product_id.id or False,
                    'description': line.name,
                    'invoice_id': inv_id,
                    'invo_num': line.invoice_id.number,
                    'quantity_divisor': line.quantity,
                    'invoice_line_id': line.id,
                    'invo_date': line.invoice_id.date_invoice,
                    'invo_value': line.price_unit,
                    'invo_currency': line.invoice_id.currency_id.id,
                    'invo_supplier_id': line.invoice_id.partner_id.id,
                    'from_invoice': True,
                    'move_line_id': line.move_lines[0].id,
                    'start_date': line.invoice_id.date_invoice,
                }, context=context)
                asset_obj.log(cr, uid, asset_id, _('Asset created from %s') % (line.invoice_id.number), context=context)
        return True

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        return {
            'date_maturity': x.get('date_maturity', False),
            'partner_id': x.get('partner_id') or part,
            'name': x['name'][:64],
            'date': date,
            'debit_currency': x['price']>0 and x['price'],
            'credit_currency': x['price']<0 and -x['price'],
            'account_id': x['account_id'],
            'analytic_lines': x.get('analytic_lines', []),
            'amount_currency': x.get('change_sign', False) and -x.get('amount_currency', False) or x.get('amount_currency', False),
            'currency_id': x.get('currency_id', False),
            'tax_code_id': x.get('tax_code_id', False),
            'tax_amount': x.get('tax_amount', False),
            'ref': x.get('ref', False),
            'reference': x.get('reference', False),
            'quantity': x.get('quantity',1.00),
            'product_id': x.get('product_id', False),
            'product_uom_id': x.get('uos_id', False),
            'analytic_account_id': x.get('account_analytic_id', False),
            # UNIFIELD REFACTORISATION: (UF-1536) add new attribute to search which line is the counterpart
            'is_counterpart': x.get('is_counterpart', False),
            'invoice_line_id': x.get('invoice_line_id', False),
            'analytic_distribution_id': x.get('analytic_distribution_id', False),
        }

    def action_number(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        #TODO: not correct fix but required a frech values before reading it.
        self.write(cr, uid, ids, {})

        for obj_inv in self.browse(cr, uid, ids, context=context):
            id = obj_inv.id
            invtype = obj_inv.type
            number = obj_inv.number
            move_id = obj_inv.move_id and obj_inv.move_id.id or False
            reference = obj_inv.reference or ''
            is_ivo = invtype == 'out_invoice' and not obj_inv.is_debit_note and not obj_inv.is_inkind_donation and obj_inv.is_intermission or False
            is_stv = invtype == 'out_invoice' and not obj_inv.is_debit_note and not obj_inv.is_inkind_donation and not obj_inv.is_intermission or False

            self.write(cr, uid, ids, {'internal_number':number})

            if invtype in ('in_invoice') and reference:
                ref = reference
            else:
                # US-1669 For the JI/AJI ref: use the source doc if it exists, else use the Entry Sequence
                ref = obj_inv.origin or self._convert_ref(cr, uid, number)
            ref = ref[:64]

            # UTP-594: for invoice, the ref on move, move lines and analytic lines must be checked and updated
            if invtype in ('in_invoice'):
                if not obj_inv.move_id.ref:
                    cr.execute('UPDATE account_move SET ref=%s WHERE id=%s ', (ref, move_id))

                for line in obj_inv.move_id.line_id:
                    if not line.ref:
                        cr.execute('UPDATE account_move_line SET ref=%s, reference=%s WHERE id=%s ', (ref,ref, line.id))
                    else:
                        cr.execute('UPDATE account_move_line SET reference=%s WHERE id=%s ', (line.ref, line.id))

                    # now update account analytic line with the new ref, only when the ref is null
                    analytic_line_obj = self.pool.get('account.analytic.line')
                    analytic_lines = analytic_line_obj.search(cr, uid, [('move_id','=',line.id)])
                    for an in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                        if not an.ref:
                            cr.execute('UPDATE account_analytic_line SET ref=%s where id =%s ', (ref, an.id))
            elif invtype in ('in_refund'):
                # UTP-594: same for refund, the ref on move, move lines and analytic lines must be checked and updated
                for line in obj_inv.move_id.line_id:
                    cr.execute('UPDATE account_move_line SET ref=%s, reference=%s WHERE id=%s ', (ref,ref, line.id))
                    # now update account analytic line with the new ref, only when the ref is null
                    analytic_line_obj = self.pool.get('account.analytic.line')
                    analytic_lines = analytic_line_obj.search(cr, uid, [('move_id','=',line.id)])
                    for an in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                        cr.execute('UPDATE account_analytic_line SET ref=%s where id =%s ', (ref, an.id))
            elif is_ivo or is_stv:
                # US-1669 Ref for lines coming from IVO or STV: always use Source Doc if possible, else Entry Sequence
                cr.execute('UPDATE account_move SET ref=%s WHERE id=%s', (ref, move_id))
                cr.execute('UPDATE account_move_line SET ref=%s, reference=%s WHERE move_id=%s', (ref, ref, move_id))
                cr.execute('UPDATE account_analytic_line SET ref=%s FROM account_move_line ' \
                           'WHERE account_move_line.move_id = %s AND account_analytic_line.move_id = account_move_line.id',
                           (ref, move_id))
            else:
                cr.execute('UPDATE account_move SET ref=%s ' \
                           'WHERE id=%s AND (ref is null OR ref = \'\')',
                           (ref, move_id))
                cr.execute('UPDATE account_move_line SET ref=%s ' \
                           'WHERE move_id=%s AND (ref is null OR ref = \'\')',
                           (ref, move_id))
                cr.execute('UPDATE account_analytic_line SET ref=%s ' \
                           'FROM account_move_line ' \
                           'WHERE account_move_line.move_id = %s ' \
                           'AND account_analytic_line.move_id = account_move_line.id',
                           (ref, move_id))

            for inv_id, name in self.name_get(cr, uid, [id]):
                ctx = context.copy()
                ctx['type'] = obj_inv.type
                message = _('Invoice ') + " '" + name + "' "+ _("is validated.")
                self.log(cr, uid, inv_id, message, context=ctx)
        return True

    def cancel_invoice_from_workflow(self, cr, uid, ids, *args):
        """
        Sets the invoice to Cancelled and not Synchronized
        """
        if isinstance(ids, int):
            ids = [ids]

        draft_invoice_ids = self.search(cr, uid, [('state', '=', 'draft'), ('id', 'in', ids)])
        if draft_invoice_ids:
            self.update_commitments(cr, uid, draft_invoice_ids)

        self.write(cr, uid, ids, {'state': 'cancel', 'synced': False})
        return True



    def _log_event(self, cr, uid, ids, factor=1.0, name='Open Invoice'):
        #TODO: implement messages system
        return True

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        doc_types = {
            'stv': _('STV: '),
            'str': _('STR: '),
            'cr': _('CR: '),
            'dn': _('DN: '),
            'ivo': _('IVO: '),
            'si': _('SI: '),
            'di': _('DI: '),
            'sr': _('SR: '),
            'isi': _('ISI: '),
            'isr': _('ISR: '),
            'donation': _('DON: '),
            'ivi': _('IVI: '),
        }
        return [(r['id'], (r['number']) or doc_types[r['doc_type']] + (r['name'] or '')) for r in
                self.read(cr, uid, ids, ['doc_type', 'number', 'name'], context, load='_classic_write')]

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('number','=',name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)] + args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def _refund_cleanup_lines(self, cr, uid, lines, is_account_inv_line=False, context=None):
        """
            Warning: lines can be account.invoice.line or account.invoice.tax
        """

        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        for line in lines:
            # in case of a refund cancel/modify, mark each SR line as reversal of the corresponding SI line IF it's an
            # account.invoice.line with an account having the type Income or Expense (EXCLUDE Extra-accounting expenses)
            if is_account_inv_line and context.get('refund_mode', '') in ['cancel', 'modify'] and line['account_id']:
                account_id = type(line['account_id']) == tuple and line['account_id'][0] or line['account_id']
                account = account_obj.browse(cr, uid, account_id,
                                             fields_to_fetch=['user_type_code', 'user_type_report_type'], context=context)
                if account.user_type_code == 'income' or \
                        (account.user_type_code == 'expense' and account.user_type_report_type != 'none'):
                    line['reversed_invoice_line_id'] = line['id']  # store a link to the original invoice line
            del line['id']
            del line['invoice_id']
            if 'is_asset' in line:
                del line['is_asset']
            if line.get('move_lines',False):
                del line['move_lines']
            if line.get('import_invoice_id',False):
                del line['import_invoice_id']

            if 'analytic_line_ids' in line:
                line['analytic_line_ids'] = False

            if 'allow_no_account' in line:
                line['allow_no_account'] = False

            for field in (
                    'company_id', 'partner_id', 'account_id', 'product_id',
                    'uos_id', 'account_analytic_id', 'tax_code_id', 'base_code_id','account_tax_id',
                    'order_line_id', 'sale_order_line_id'
            ):
                line[field] = line.get(field, False) and line[field][0] or False

            if 'invoice_line_tax_id' in line:
                line['invoice_line_tax_id'] = [(6,0, line.get('invoice_line_tax_id', [])) ]

            if 'purchase_order_line_ids' in line:
                line['purchase_order_line_ids'] = [(6, 0, line.get('purchase_order_line_ids', []))]

            if 'analytic_distribution_id' in line:
                if line.get('analytic_distribution_id', False) and line.get('analytic_distribution_id')[0]:
                    distrib_id = line.get('analytic_distribution_id')[0]
                    line['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, distrib_id, {}) or False
                else:
                    line['analytic_distribution_id'] = False

        return [(0,0,x) for x in lines]


    def _hook_fields_for_refund(self, cr, uid, *args):
        """
        Permits to change fields list to be use for creating invoice refund from an invoice.
        """
        res = [
            'name', 'type', 'number', 'reference', 'comment', 'date_due', 'partner_id', 'address_contact_id', 'address_invoice_id',
            'partner_contact', 'partner_insite', 'partner_ref', 'payment_term', 'account_id', 'currency_id', 'invoice_line', 'tax_line',
            'journal_id', 'analytic_distribution_id', 'document_date', 'doc_type',
        ]
        return res

    def _hook_fields_m2o_for_refund(self, cr, uid, *args):
        """
        Permits to change field that would be use for invoice refund.
        NB: This fields should be many2one fields.
        """
        res = [
            'address_contact_id', 'address_invoice_id', 'partner_id',
            'account_id', 'currency_id', 'payment_term', 'journal_id',
            'analytic_distribution_id',
        ]
        return res

    def _hook_refund_data(self, cr, uid, data, *args):
        """
        Copy analytic distribution for refund invoice
        """
        if not data:
            return False
        if 'analytic_distribution_id' in data:
            if data.get('analytic_distribution_id', False):
                data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, data.get('analytic_distribution_id'), {}) or False
            else:
                data['analytic_distribution_id'] = False
        return data

    def refund(self, cr, uid, ids, date=None, period_id=None, description=None, journal_id=None, document_date=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if date or document_date:
            for inv in self.browse(cr, uid, ids, fields_to_fetch=['date_invoice', 'document_date']):
                if date and date < inv.date_invoice:
                    raise osv.except_osv(_('Error'), _("Posting date for the refund is before the invoice's posting date!"))
                if document_date and document_date < inv.document_date:
                    raise osv.except_osv(_('Error'), _("Document date for the refund is before the invoice's document date!"))

        invoices = self.read(cr, uid, ids, self._hook_fields_for_refund(cr, uid))
        obj_invoice_line = self.pool.get('account.invoice.line')
        obj_invoice_tax = self.pool.get('account.invoice.tax')
        obj_journal = self.pool.get('account.journal')
        new_ids = []
        for invoice in invoices:
            invoice.update({'refunded_invoice_id': invoice['id']})
            del invoice['id']

            if context.get('is_intermission', False):
                type_dict = {
                    'out_invoice': 'in_invoice',  # IVO
                    'in_invoice': 'out_invoice',  # IVI
                }
            else:
                type_dict = {
                    'out_invoice': 'out_refund', # Customer Invoice
                    'in_invoice': 'in_refund',   # Supplier Invoice
                    'out_refund': 'out_invoice', # Customer Refund
                    'in_refund': 'in_invoice',   # Supplier Refund
                }

            invoice_lines = obj_invoice_line.read(cr, uid, invoice['invoice_line'])
            invoice_lines = self._refund_cleanup_lines(cr, uid, invoice_lines, is_account_inv_line=True, context=context)

            tax_lines = obj_invoice_tax.read(cr, uid, invoice['tax_line'])
            tax_lines = self._refund_cleanup_lines(cr, uid, tax_lines, context=context)
            if journal_id:
                refund_journal_ids = [journal_id]
            elif invoice['type'] == 'in_invoice':
                refund_journal_ids = obj_journal.search(cr, uid, [('type','=','purchase_refund')])
            else:
                refund_journal_ids = obj_journal.search(cr, uid, [('type','=','sale_refund')])

            if invoice.get('doc_type') == 'stv':
                doc_type = 'str'
            elif invoice.get('doc_type') == 'isi':
                doc_type = 'isr'
            elif invoice.get('doc_type') in ('si', 'di'):
                doc_type = 'sr'
            elif invoice.get('doc_type') == 'ivo':
                doc_type = 'ivi'
            elif invoice.get('doc_type') == 'ivi':
                doc_type = 'ivo'
            else:
                doc_type = ''

            if not date:
                date = time.strftime('%Y-%m-%d')
            invoice.update({
                'type': type_dict[invoice['type']],
                'real_doc_type': doc_type,
                'date_invoice': date,
                'state': 'draft',
                'number': False,
                'invoice_line': invoice_lines,
                'tax_line': tax_lines,
                'journal_id': refund_journal_ids,
                'origin': invoice['number']
            })
            if context.get('is_intermission', False):
                invoice.update({
                    'is_intermission': True,
                })
            if period_id:
                invoice.update({
                    'period_id': period_id,
                })
            if document_date:
                invoice.update({
                    'document_date': document_date,
                })
            if description:
                invoice.update({
                    'name': description,
                })
            # take the id part of the tuple returned for many2one fields
            for field in self._hook_fields_m2o_for_refund(cr, uid):
                invoice[field] = invoice[field] and invoice[field][0]
            invoice = self._hook_refund_data(cr, uid, invoice) or invoice
            # create the new invoice
            new_ids.append(self.create(cr, uid, invoice, context=context))

        return new_ids

    def action_gen_sync_msg(self, cr, uid, ids, context=None):
        for inv_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'account.invoice', inv_id, {},
                                                                                  'account.invoice.update_counterpart_inv', self._logger, check_identifier=False, context=context)
        return True

    def invoice_open_form_view(self, cr, uid, ids, context=None):
        if not ids:
            return True
        view_data = self._get_invoice_act_window(cr, uid, ids[0], views_order=['form', 'tree'], context=context)
        view_data['res_id'] = ids[0]
        view_data['target'] = 'current'
        view_data['keep_open'] = True
        if context.get('search_default_partner_id'):
            dom = []
            if view_data['domain']:
                dom = safe_eval(view_data['domain'])
            dom.append(('partner_id', '=', context.get('search_default_partner_id')))
            view_data['domain'] = dom
        return view_data

account_invoice()

class account_invoice_line(osv.osv):
    def _amount_line(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            price = line.price_unit * (1-(line.discount or 0.0)/100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, product=line.product_id, address_id=line.invoice_id.address_invoice_id, partner=line.invoice_id.partner_id)
            res[line.id] = taxes['total']
            if line.invoice_id:
                cur = line.invoice_id.currency_id
                res[line.id] = cur_obj.round(cr, uid, cur.rounding, res[line.id])
        return res

    _name = "account.invoice.line"
    _description = "Invoice Line"
    _columns = {
        'name': fields.char('Description', size=256, required=True),
        'origin': fields.char('Origin', size=512, help="Reference of the document that produced this invoice."),
        'invoice_id': fields.many2one('account.invoice', 'Invoice Reference', ondelete='cascade', select=True),
        'partner_type': fields.related('invoice_id', 'partner_type', string='Partner Type', type='selection',
                                       selection=PARTNER_TYPE, readonly=True, store=False),
        'uos_id': fields.many2one('product.uom', 'Unit of Measure', ondelete='set null'),
        'product_id': fields.many2one('product.product', 'Product', ondelete='set null'),
        'account_id': fields.many2one('account.account', 'Account', domain=[('type', '<>', 'view'), ('type', '<>', 'closed')],
                                      help="The income or expense account related to the selected product."),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Account')),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', type="float",
                                          digits_compute= dp.get_precision('Account'), store=True),
        'quantity': fields.float('Quantity', required=True),
        'discount': fields.float('Discount (%)', digits_compute= dp.get_precision('Account')),
        'invoice_line_tax_id': fields.many2many('account.tax', 'account_invoice_line_tax', 'invoice_line_id', 'tax_id', 'Taxes', domain=[('parent_id','=',False)]),
        'note': fields.text('Notes'),
        'account_analytic_id':  fields.many2one('account.analytic.account', 'Analytic Account'),
        'company_id': fields.related('invoice_id','company_id',type='many2one',relation='res.company',string='Company', store=True, readonly=True),
        'partner_id': fields.related('invoice_id','partner_id',type='many2one',relation='res.partner',string='Partner',store=True, write_relate=False),
        'is_asset': fields.boolean('Asset'),
    }
    _defaults = {
        'quantity': 1,
        'discount': 0.0,
    }

    def change_is_asset(self, cr, uid, ids, is_asset, product_id, context=None):
        if not product_id:
            return {
                'warning': {'message': _('Product is mandatory, please fill the product before ticking Asset.')},
                'value': {'is_asset': False}
            }


        prod = self.pool.get('product.product').browse(cr, uid, product_id, fields_to_fetch=['categ_id', 'default_code', 'property_account_expense'], context=context)

        if not is_asset:
            account_id = prod.property_account_expense and prod.property_account_expense.id or \
                prod.categ_id and prod.categ_id.property_account_expense_categ and prod.categ_id.property_account_expense_categ.id or \
                False
            return {'value': {'account_id': account_id}}

        if not prod.categ_id:
            return {'warning': {'message': _('Product %s has no category') % (prod.default_code, )}, 'value': {'is_asset': False}}
        if not prod.categ_id.asset_bs_account_id:
            return {'warning': {'message': _('Product Category %s has no Asset Balance Sheet Account') % (prod.categ_id.name, )}, 'value': {'is_asset': False}}
        return {
            'value': {
                'account_id': prod.categ_id.asset_bs_account_id.id
            }
        }



    def product_id_change(self, cr, uid, ids, product, uom, qty=0, name='', type='out_invoice', partner_id=False, fposition_id=False, price_unit=False, address_invoice_id=False, currency_id=False, is_asset=False, context=None):
        if context is None:
            context = {}
        company_id = context.get('company_id',False)
        if not partner_id:
            raise osv.except_osv(_('No Partner Defined !'),_("You must first select a partner !") )
        if not product:
            return {'value': {'price_unit': 0.0, 'categ_id': False}, 'domain':{'product_uom':[]}}
        part = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        fpos_obj = self.pool.get('account.fiscal.position')
        fpos = fposition_id and fpos_obj.browse(cr, uid, fposition_id, context=context) or False

        if part.lang:
            context.update({'lang': part.lang})
        result = {}
        res = self.pool.get('product.product').browse(cr, uid, product, context=context)
        if company_id:
            property_obj = self.pool.get('ir.property')
            account_obj = self.pool.get('account.account')
            in_pro_id = property_obj.search(cr, uid, [('name','=','property_account_income'),('res_id','=','product.template,'+str(res.product_tmpl_id.id)+''),('company_id','=',company_id)])
            if not in_pro_id:
                in_pro_id = property_obj.search(cr, uid, [('name','=','property_account_income_categ'),('res_id','=','product.template,'+str(res.categ_id.id)+''),('company_id','=',company_id)])
            exp_pro_id = property_obj.search(cr, uid, [('name','=','property_account_expense'),('res_id','=','product.template,'+str(res.product_tmpl_id.id)+''),('company_id','=',company_id)])
            if not exp_pro_id:
                exp_pro_id = property_obj.search(cr, uid, [('name','=','property_account_expense_categ'),('res_id','=','product.template,'+str(res.categ_id.id)+''),('company_id','=',company_id)])

            if not in_pro_id:
                in_acc = res.product_tmpl_id.property_account_income
                in_acc_cate = res.categ_id.property_account_income_categ
                if in_acc:
                    app_acc_in = in_acc
                else:
                    app_acc_in = in_acc_cate
            else:
                # Get the fields from the ir.property record
                my_value = property_obj.read(cr,uid,in_pro_id,['name','value_reference','res_id'])
                # Parse the value_reference field to get the ID of the account.account record
                account_id = int (my_value[0]["value_reference"].split(",")[1])
                # Use the ID of the account.account record in the browse for the account.account record
                app_acc_in = account_obj.browse(cr, uid, account_id, context=context)
            if not exp_pro_id:
                ex_acc = res.product_tmpl_id.property_account_expense
                ex_acc_cate = res.categ_id.property_account_expense_categ
                if ex_acc:
                    app_acc_exp = ex_acc
                else:
                    app_acc_exp = ex_acc_cate
            else:
                app_acc_exp = account_obj.browse(cr, uid, exp_pro_id, context=context)[0]
            if not in_pro_id and not exp_pro_id:
                in_acc = res.product_tmpl_id.property_account_income
                in_acc_cate = res.categ_id.property_account_income_categ
                ex_acc = res.product_tmpl_id.property_account_expense
                ex_acc_cate = res.categ_id.property_account_expense_categ
                if in_acc or ex_acc:
                    app_acc_in = in_acc
                    app_acc_exp = ex_acc
                else:
                    app_acc_in = in_acc_cate
                    app_acc_exp = ex_acc_cate
            if app_acc_in and app_acc_in.company_id.id != company_id and app_acc_exp and app_acc_exp.company_id.id != company_id:
                in_res_id = account_obj.search(cr, uid, [('name','=',app_acc_in.name),('company_id','=',company_id)])
                exp_res_id = account_obj.search(cr, uid, [('name','=',app_acc_exp.name),('company_id','=',company_id)])
                if not in_res_id and not exp_res_id:
                    raise osv.except_osv(_('Configuration Error !'),
                                         _('Can not find account chart for this company, Please Create account.'))
                in_obj_acc = account_obj.browse(cr, uid, in_res_id, context=context)
                exp_obj_acc = account_obj.browse(cr, uid, exp_res_id, context=context)
                if in_acc or ex_acc:
                    res.product_tmpl_id.property_account_income = in_obj_acc[0]
                    res.product_tmpl_id.property_account_expense = exp_obj_acc[0]
                else:
                    res.categ_id.property_account_income_categ = in_obj_acc[0]
                    res.categ_id.property_account_expense_categ = exp_obj_acc[0]

        if type in ('out_invoice','out_refund'):
            a = res.product_tmpl_id.property_account_income.id
            if not a:
                a = res.categ_id.property_account_income_categ.id
        else:
            if is_asset:
                if res.categ_id and res.categ_id.asset_bs_account_id:
                    a = res.categ_id.asset_bs_account_id.id
                else:
                    a = False
                    result['account_id'] = False
            else:
                a = res.product_tmpl_id.property_account_expense.id
                if not a:
                    a = res.categ_id.property_account_expense_categ.id
        a = fpos_obj.map_account(cr, uid, fpos, a)
        if a:
            result['account_id'] = a

        if type in ('out_invoice', 'out_refund'):
            taxes = res.taxes_id and res.taxes_id or (a and self.pool.get('account.account').browse(cr, uid, a, context=context).tax_ids or False)
        else:
            taxes = res.supplier_taxes_id and res.supplier_taxes_id or (a and self.pool.get('account.account').browse(cr, uid, a, context=context).tax_ids or False)
        tax_id = fpos_obj.map_tax(cr, uid, fpos, taxes)

        if type in ('in_invoice', 'in_refund'):
            result.update( {'price_unit': price_unit or res.standard_price,'invoice_line_tax_id': tax_id} )
        else:
            result.update({'price_unit': res.list_price, 'invoice_line_tax_id': tax_id})
        result['name'] = res.partner_ref

        domain = {}
        result['uos_id'] = res.uom_id.id or uom or False
        result['note'] = res.description
        if result['uos_id']:
            res2 = res.uom_id.category_id.id
            if res2:
                domain = {'uos_id':[('category_id','=',res2 )]}

        result['categ_id'] = res.categ_id.id
        res_final = {'value':result, 'domain':domain}

        if not company_id or not currency_id:
            return res_final

        company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
        currency = self.pool.get('res.currency').browse(cr, uid, currency_id, context=context)

        if company.currency_id.id != currency.id:
            new_price = res_final['value']['price_unit'] * currency.rate
            res_final['value']['price_unit'] = new_price

        if uom:
            uom = self.pool.get('product.uom').browse(cr, uid, uom, context=context)
            if res.uom_id.category_id.id == uom.category_id.id:
                new_price = res_final['value']['price_unit'] * uom.factor_inv
                res_final['value']['price_unit'] = new_price
        return res_final

    def uos_id_change(self, cr, uid, ids, product, uom, qty=0, name='', type='out_invoice', partner_id=False, fposition_id=False, price_unit=False, address_invoice_id=False, currency_id=False, context=None):
        warning = {}
        res = self.product_id_change(cr, uid, ids, product, uom, qty, name, type, partner_id, fposition_id, price_unit, address_invoice_id, currency_id, context=context)
        if 'uos_id' in res['value']:
            del res['value']['uos_id']
        if not uom:
            res['value']['price_unit'] = 0.0
        if product and uom:
            prod = self.pool.get('product.product').browse(cr, uid, product, context=context)
            prod_uom = self.pool.get('product.uom').browse(cr, uid, uom, context=context)
            if prod.uom_id.category_id.id != prod_uom.category_id.id:
                warning = {
                    'title': _('Warning!'),
                    'message': _('You selected an Unit of Measure which is not compatible with the product.')
                }
            return {'value': res['value'], 'warning': warning}
        return res

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)

        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found= False
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                                           (line.price_unit * (1.0 - (line['discount'] or 0.0) / 100.0)),
                                           line.quantity, inv.address_invoice_id.id, line.product_id,
                                           inv.partner_id)['taxes']:

                if inv.type in ('out_invoice', 'in_invoice'):
                    tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = tax_amount
        return res

    def _get_line_name(self, line):
        '''
        Returns the String to use for the "name" field in JI and AJI lines:
        - if the line is linked to a product: add 'xQty' at the end of the description
        - if necessary trim the string to get 64 characters max.
        '''
        if not line:
            return False
        elif not line.product_id:
            return line.name[:64]
        else:
            qty = line.quantity
            # remove '.0' if it's an integer value, and convert to string
            qty_str = '%s' % (int(qty) == qty and int(qty) or qty)
            qty_len = len(qty_str)
            trimmed_name = line.name[:64 - qty_len - 2]
            return ''.join((trimmed_name, ' x', qty_str))

    def move_line_get_item(self, cr, uid, line, context=None):
        if context is None:
            context = {}

        line_name = self._get_line_name(line)
        res = {
            'type':'src',
            'name': line_name,
            'price_unit':line.price_unit,
            'quantity':line.quantity,
            'price':line.price_subtotal,
            'account_id':line.account_id.id,
            'product_id':line.product_id.id,
            'uos_id':line.uos_id.id,
            'account_analytic_id':line.account_analytic_id.id,
            'taxes':line.invoice_line_tax_id,
            'invoice_line_id': line.id,
        }

        ana_obj = self.pool.get('analytic.distribution')
        if line.analytic_distribution_id:
            new_distrib_id = ana_obj.copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                res['analytic_distribution_id'] = new_distrib_id
        # If no distribution on invoice line, take those from invoice and copy it!
        elif line.invoice_id and line.invoice_id.analytic_distribution_id:
            new_distrib_id = ana_obj.copy(cr, uid, line.invoice_id.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                res['analytic_distribution_id'] = new_distrib_id

        return res

account_invoice_line()

class account_invoice_tax(osv.osv):
    _name = "account.invoice.tax"
    _description = "Invoice Tax"


    def _check_untaxed_amount(self, cr, uid, vals, context=None):
        if 'account_tax_id' in vals and vals['account_tax_id'] and 'base_amount' in vals and vals['base_amount'] == 0:
            raise osv.except_osv(_('Warning !'), _('The Untaxed Amount is zero. Please press the Save & Edit button before saving the %s tax.') % (vals['name']))
        return True

    def _update_tax_partner(self, cr, uid, vals, context=None):
        """
        Updates vals with the partner of the related tax

        Note that in case a partner_id is already in vals, it is used (e.g. in case of a SI refund the SR tax lines must be exactly
        the same as the SI ones, even if the partner linked to the related account.tax has changed in the meantime)
        """
        if context is None:
            context = {}
        tax_obj = self.pool.get('account.tax')
        if 'partner_id' not in vals and 'account_tax_id' in vals:
            tax_partner_id = False
            if vals['account_tax_id']:  # note that at doc level it's possible not to have any link to a tax from the system
                tax = tax_obj.browse(cr, uid, vals['account_tax_id'], fields_to_fetch=['partner_id'], context=context)
                tax_partner_id = tax.partner_id and tax.partner_id.id or False
            vals.update({'partner_id': tax_partner_id})

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        self._check_untaxed_amount(cr, uid, vals, context)
        self._update_tax_partner(cr, uid, vals, context=context)
        return super(account_invoice_tax, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        self._update_tax_partner(cr, uid, vals, context=context)
        return super(account_invoice_tax, self).write(cr, uid, ids, vals, context=context)

    def _count_factor(self, cr, uid, ids, name, args, context=None):
        res = {}
        for invoice_tax in self.browse(cr, uid, ids, context=context):
            res[invoice_tax.id] = {
                'factor_base': 1.0,
                'factor_tax': 1.0,
            }
            if invoice_tax.amount != 0.0:
                factor_tax = invoice_tax.tax_amount / invoice_tax.amount
                res[invoice_tax.id]['factor_tax'] = factor_tax

            if invoice_tax.base != 0.0:
                factor_base = invoice_tax.base_amount / invoice_tax.base
                res[invoice_tax.id]['factor_base'] = factor_base

        return res

    _columns = {
        'invoice_id': fields.many2one('account.invoice', 'Invoice Line', ondelete='cascade', select=True),
        'purchase_id': fields.many2one('purchase.order', 'PO', ondelete='cascade', select=True),
        'name': fields.char('Tax Description', size=64, required=True),
        'account_id': fields.many2one('account.account', 'Tax Account', required=True, domain=[('type','<>','view'),('type','<>','income'), ('type', '<>', 'closed')]),
        'base': fields.float('Base', digits_compute=dp.get_precision('Account')),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account')),
        'manual': fields.boolean('Manual'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of invoice tax."),
        'base_code_id': fields.many2one('account.tax.code', 'Base Code', help="The account basis of the tax declaration."),
        'base_amount': fields.float('Base Code Amount', digits_compute=dp.get_precision('Account')),
        'tax_code_id': fields.many2one('account.tax.code', 'Tax Code', help="The tax basis of the tax declaration."),
        'tax_amount': fields.float('Tax Code Amount', digits_compute=dp.get_precision('Account')),
        'company_id': fields.related('account_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'factor_base': fields.function(_count_factor, method=True, string='Multipication factor for Base code', type='float', multi="all"),
        'factor_tax': fields.function(_count_factor, method=True, string='Multipication factor Tax code', type='float', multi="all"),
        'account_tax_id': fields.many2one('account.tax', 'Tax', domain=[('price_include', '=', False)]),
        'partner_id': fields.many2one('res.partner', 'Partner', ondelete='restrict'),
    }

    def tax_code_change(self, cr, uid, ids, account_tax_id, amount_untaxed, inv_partner_id, context=None):
        if context is None:
            context = {}
        ret = {}
        if account_tax_id:
            atx_obj = self.pool.get('account.tax')
            partner_obj = self.pool.get('res.partner')
            inv_partner = inv_partner_id and partner_obj.browse(cr, uid, inv_partner_id,
                                                                fields_to_fetch=['name', 'lang'], context=context) or None
            inv_partner_name = inv_partner and inv_partner.name or ''
            # use the language of the partner for the tax name (to be consistent with what's done when clicking on Compute Taxes)
            inv_partner_lang = inv_partner and inv_partner.lang or ''
            new_context = context.copy()
            if inv_partner_lang:
                new_context.update({'lang': inv_partner_lang})
            tax = atx_obj.browse(cr, uid, account_tax_id, fields_to_fetch=['name', 'account_collected_id'], context=new_context)
            description = "%s%s%s" % (tax.name, inv_partner_name and ' - ' or '', inv_partner_name or '')
            ret = {'value': {'account_id': tax.account_collected_id and tax.account_collected_id.id or False,
                             'name': description,
                             'base_amount': amount_untaxed,
                             'amount': self._calculate_tax(cr, uid, account_tax_id, amount_untaxed)}}
        return ret

    def _calculate_tax(self, cr, uid, account_tax_id, amount_untaxed):
        atx_obj = self.pool.get('account.tax')
        atx = atx_obj.browse(cr, uid, account_tax_id)
        tax_amount = 0.0
        if atx.type == 'fixed':
            tax_amount = atx.amount
        if atx.type == 'percent':
            tax_amount = round(atx.amount * amount_untaxed, 2)
        return tax_amount

    def base_change(self, cr, uid, ids, base, currency_id=False, company_id=False, document_date=False, date_invoice=False):
        cur_obj = self.pool.get('res.currency')
        company_obj = self.pool.get('res.company')
        company_currency = False
        factor = 1
        if ids:
            factor = self.read(cr, uid, ids[0], ['factor_base'])['factor_base']
        if company_id:
            company_currency = company_obj.read(cr, uid, [company_id], ['currency_id'])[0]['currency_id'][0]
        if currency_id and company_currency:
            curr_date = currency_date.get_date(self, cr, document_date, date_invoice)
            base = cur_obj.compute(cr, uid, currency_id, company_currency, base*factor,
                                   context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
        return {'value': {'base_amount':base}}

    def amount_change(self, cr, uid, ids, amount, currency_id=False, company_id=False, document_date=False, date_invoice=False):
        cur_obj = self.pool.get('res.currency')
        company_obj = self.pool.get('res.company')
        company_currency = False
        factor = 1
        if ids:
            factor = self.read(cr, uid, ids[0], ['factor_tax'])['factor_tax']
        if company_id:
            company_currency = company_obj.read(cr, uid, [company_id], ['currency_id'])[0]['currency_id'][0]
        if currency_id and company_currency:
            curr_date = currency_date.get_date(self, cr, document_date, date_invoice)
            amount = cur_obj.compute(cr, uid, currency_id, company_currency, amount*factor,
                                     context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
        return {'value': {'tax_amount': amount}}

    _order = 'sequence'
    _defaults = {
        'manual': 1,
        'base_amount': 0.0,
        'tax_amount': 0.0,
        'sequence': 0,
    }
    def compute(self, cr, uid, invoice_id, context=None):
        if context is None:
            context = {}
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, (line.price_unit* (1-(line.discount or 0.0)/100.0)), line.quantity, inv.address_invoice_id.id, line.product_id, inv.partner_id)['taxes']:
                val={}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']
                val['account_tax_id'] = tax['id']

                if inv.type in ('out_invoice','in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    curr_date = currency_date.get_date(self, cr, inv.document_date, inv.date_invoice)
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'],
                                                         context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'],
                                                        context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    curr_date = currency_date.get_date(self, cr, inv.document_date, inv.date_invoice)
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'],
                                                         context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'],
                                                        context={'currency_date': curr_date or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_paid_id'] or line.account_id.id

                key = tax['id']  # taxes are grouped by id
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in list(tax_grouped.values()):
            t['base'] = cur_obj.round(cr, uid, cur.rounding, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur.rounding, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur.rounding, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur.rounding, t['tax_amount'])

        ai = self.pool.get('account.invoice').browse(cr, uid, invoice_id)
        ait_ids = self.pool.get('account.invoice.tax').search(cr, uid, [('invoice_id','=',invoice_id)])
        aits = self.pool.get('account.invoice.tax').browse(cr, uid, ait_ids)
        for ait in aits:
            if ait.account_tax_id and not ait.amount:
                self.pool.get('account.invoice.tax').write(cr, uid, ait.id, {'amount': self._calculate_tax(cr, uid, ait.account_tax_id.id,ai.amount_untaxed)})

        return tax_grouped

    def move_line_get(self, cr, uid, invoice_id):
        res = []
        cr.execute('SELECT * FROM account_invoice_tax WHERE invoice_id=%s', (invoice_id,))
        for t in cr.dictfetchall():
            if not t['amount'] \
                    and not t['tax_code_id'] \
                    and not t['tax_amount']:
                continue
            res.append({
                'type':'tax',
                'name':t['name'],
                'price_unit': t['amount'],
                'quantity': 1,
                'price': t['amount'] or 0.0,
                'account_id': t['account_id'],
                'tax_code_id': t['tax_code_id'],
                'tax_amount': t['tax_amount'],
                'partner_id': t['partner_id'],
            })
        return res

account_invoice_tax()


class res_partner(osv.osv):
    """ Inherits partner and adds invoice information in the partner form """
    _inherit = 'res.partner'
    _columns = {
        'invoice_ids': fields.one2many('account.invoice.line', 'partner_id', 'Invoices', readonly=True),
    }

    def copy(self, cr, uid, ids, default=None, context=None):
        if default is None:
            default = {}
        if 'invoice_ids' not in default:
            default['invoice_ids'] = []
        return super(res_partner, self).copy(cr, uid, ids, default, context=context)
res_partner()


class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True, view_id=False):
        """
        Hides the reports:
        - "Invoice Excel Export" in the menu of other invoices than IVO/IVI/STV
        - "FO Follow-up Finance" in the menu of other invoices than IVO/STV
        - "STV/IVO lines follow-up" in the menu of other invoices than IVO/STV (+ renames it depending on the inv. type)
        """
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req, view_id=view_id)
        model_names = [x[0] for x in models]
        if key == 'action' and key2 == 'client_print_multi' and 'account.invoice' in model_names:
            new_act = []
            context_ivo = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'intermission' and \
                context.get('is_intermission', False) and context.get('intermission_type', False) == 'out'
            context_stv = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'sale' and \
                not context.get('is_debit_note', False)
            for v in values:
                # renaming
                if len(v) > 2 and v[1] == 'invoice_lines_follow_up' and v[2].get('name'):
                    if context_ivo:
                        v[2]['name'] = _('IVO lines follow-up')
                    elif context_stv:
                        v[2]['name'] = _('STV lines follow-up')
                # display
                if not context.get('is_intermission') and not context_stv and len(v) > 2 and \
                        v[2].get('report_name', '') == 'invoice.excel.export':
                    continue
                elif not context_ivo and not context_stv and len(v) > 1 and v[1] in ('fo_follow_up_finance', 'invoice_lines_follow_up'):
                    continue
                else:
                    new_act.append(v)
            values = new_act
        return values


ir_values()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
