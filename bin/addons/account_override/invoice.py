#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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


from osv import osv
from osv import fields
from time import strftime
from tools.translate import _
from lxml import etree
import re
import netsvc


import decimal_precision as dp

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_invoice_report_name(self, cr, uid, ids, context=None):
        '''
        Returns the name of the invoice according to its type
        '''
        if isinstance(ids, list):
            ids = ids[0]

        inv = self.browse(cr, uid, ids, context=context)
        inv_name = inv.number or inv.name or 'No_description'
        prefix = 'STV_'

        if inv.type == 'out_refund': # Customer refund
            prefix = 'CR_'
        elif inv.type == 'in_refund': # Supplier refund
            prefix = 'SR_'
        elif inv.type == 'out_invoice':
            # Stock transfer voucher
            prefix = 'STV_'
            # Debit note
            if inv.is_debit_note and not inv.is_inkind_donation and not inv.is_intermission:
                prefix = 'DN_'
            # Intermission voucher OUT
            elif not inv.is_debit_note and not inv.is_inkind_donation and inv.is_intermission:
                prefix = 'IMO_'
        elif inv.type == 'in_invoice':
            # Supplier invoice
            prefix = 'SI_'
            # Intermission voucher IN
            if not inv.is_debit_note and not inv.is_inkind_donation and inv.is_intermission:
                prefix = 'IMI_'
            # Direct invoice
            elif inv.is_direct_invoice:
                prefix = 'DI_'
            # In-kind donation
            elif not inv.is_debit_note and inv.is_inkind_donation:
                prefix = 'DON_'
        return '%s%s' % (prefix, inv_name)

    def _get_journal(self, cr, uid, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        # @@@override@account.invoice.py
        if context is None:
            context = {}
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if context.get('is_inkind_donation'):
            args = [('type', 'in', ['inkind', 'extra'])]
        else:
            type_inv = context.get('type', 'out_invoice')
            company_id = context.get('company_id', user.company_id.id)
            type2journal = {'out_invoice': 'sale', 'in_invoice': 'purchase', 'out_refund': 'sale_refund', 'in_refund': 'purchase_refund'}
            refund_journal = {'out_invoice': False, 'in_invoice': False, 'out_refund': True, 'in_refund': True}
            args = [('type', '=', type2journal.get(type_inv, 'sale')),
                    ('company_id', '=', company_id),
                    ('refund_journal', '=', refund_journal.get(type_inv, False))]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, args, order='id', limit=1, context=context)
        return res and res[0] or False

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Fake method for 'ready_for_import_in_debit_note' field
        """
        res = {}
        for i in ids:
            res[i] = False
        return res

    def _search_ready_for_import_in_debit_note(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        account_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account and \
            self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account.id or False
        if not account_id:
            raise osv.except_osv(_('Error'), _('No default account for import invoice on Debit Note!'))
        dom1 = [
            ('account_id','=',account_id),
            ('reconciled','=',False),
            ('state', '=', 'open'),
            ('type', '=', 'out_invoice'),
            ('journal_id.type', 'not in', ['migration']),
        ]
        return dom1+[('is_debit_note', '=', False)]

    def _get_int_journal_for_current_instance(self, cr, uid, context=None):
        """
        Returns the id of the Intermission journal of the current instance if it exists, else returns False.
        """
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        int_journal_domain = [('type', '=', 'intermission'), ('is_current_instance', '=', True)]
        int_journal_id = journal_obj.search(cr, uid, int_journal_domain, order='id', limit=1, context=context)
        return int_journal_id and int_journal_id[0] or False

    def _get_fake_m2o_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get many2one field content
        """
        res = {}
        name = field_name.replace("fake_", '')
        for i in self.browse(cr, uid, ids):
            if context and context.get('is_intermission', False):
                res[i.id] = False
                if name == 'account_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.intermission_default_counterpart:
                        res[i.id] = user[0].company_id.intermission_default_counterpart.id
                elif name == 'journal_id':
                    int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                    if int_journal_id:
                        res[i.id] = int_journal_id
                elif name == 'currency_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.currency_id:
                        res[i.id] = user[0].company_id.currency_id.id
            else:
                res[i.id] = getattr(i, name, False) and getattr(getattr(i, name, False), 'id', False) or False
        return res

    def _get_have_donation_certificate(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        If this invoice have a stock picking in which there is a Certificate of Donation, return True. Otherwise return False.
        """
        res = {}
        for i in self.browse(cr, uid, ids):
            res[i.id] = False
            if i.picking_id:
                a_ids = self.pool.get('ir.attachment').search(cr, uid, [('res_model', '=', 'stock.picking'), ('res_id', '=', i.picking_id.id), ('description', '=', 'Certificate of Donation')])
                if a_ids:
                    res[i.id] = True
        return res

    def _get_virtual_fields(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get fields in order to transform them into 'virtual fields" (kind of field duplicity):
         - currency_id
         - account_id
         - supplier
        """
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = {'virtual_currency_id': inv.currency_id.id or False, 'virtual_account_id': inv.account_id.id or False,
                           'virtual_partner_id': inv.partner_id.id or False}
        return res

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _get_can_merge_lines(self, cr, uid, ids, field_name, args,
                             context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long, )):
            ids = [ids]

        for inv_br in self.browse(cr, uid, ids, context=context):
            # US-357: allow merge of line only for draft SI
            res[inv_br.id] = inv_br.state and inv_br.state == 'draft' \
                and inv_br.invoice_line \
                and inv_br.type == 'in_invoice' \
                and not inv_br.is_direct_invoice \
                and not inv_br.is_inkind_donation \
                and not inv_br.is_debit_note \
                and not inv_br.is_intermission \
                or False

        return res

    _columns = {
        'sequence_id': fields.many2one('ir.sequence', string='Lines Sequence', ondelete='cascade',
                                       help="This field contains the information related to the numbering of the lines of this order."),
        'date_invoice': fields.date('Posting Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                            'close':[('readonly',True)]}, select=True),
        'document_date': fields.date('Document Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                              'close':[('readonly',True)]}, select=True),
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'is_inkind_donation': fields.boolean(string="Is an In-kind Donation?"),
        'is_intermission': fields.boolean(string="Is an Intermission Voucher?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean",
                                                          method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
        'partner_move_line': fields.one2many('account.move.line', 'invoice_partner_link', string="Partner move line", readonly=True),
        'fake_journal_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.journal", string="Journal", hide_default_menu=True, readonly="True"),
        'fake_currency_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="res.currency", string="Currency", readonly="True"),
        'have_donation_certificate': fields.function(_get_have_donation_certificate, method=True, type='boolean', string="Have a Certificate of donation?"),
        'purchase_list': fields.boolean(string='Purchase List ?', help='Check this box if the invoice comes from a purchase list', readonly=True, states={'draft':[('readonly',False)]}),
        'virtual_currency_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Currency",
                                               type='many2one', relation="res.currency", readonly=True),
        'virtual_account_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Account",
                                              type='many2one', relation="account.account", readonly=True),
        'virtual_partner_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Supplier",
                                              type='many2one', relation="res.partner", readonly=True),
        'register_line_ids': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register Lines"),
        'is_direct_invoice': fields.boolean("Is direct invoice?", readonly=True),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False,
                                              states={'draft':[('readonly',False)]}),
        'register_posting_date': fields.date(string="Register posting date for Direct Invoice", required=False),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'st_lines': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register lines", readonly=True, help="Register lines that have a link to this invoice."),
        'can_merge_lines': fields.function(_get_can_merge_lines, method=True, type='boolean', string='Can merge lines ?'),
        'is_merged_by_account': fields.boolean("Is merged by account"),
    }

    _defaults = {
        'journal_id': _get_journal,
        'date_invoice': lambda *a: strftime('%Y-%m-%d'),
        'is_debit_note': lambda obj, cr, uid, c: c.get('is_debit_note', False),
        'is_inkind_donation': lambda obj, cr, uid, c: c.get('is_inkind_donation', False),
        'is_intermission': lambda obj, cr, uid, c: c.get('is_intermission', False),
        'is_direct_invoice': lambda *a: False,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'can_merge_lines': lambda *a: False,
        'is_merged_by_account': lambda *a: False,
    }

    def onchange_company_id(self, cr, uid, ids, company_id, part_id, ctype, invoice_line, currency_id):
        """
        This is a method to redefine the journal_id domain with the current_instance taken into account
        """
        res = super(account_invoice, self).onchange_company_id(cr, uid, ids, company_id, part_id, ctype, invoice_line, currency_id)
        if company_id and ctype:
            res.setdefault('domain', {})
            res.setdefault('value', {})
            ass = {
                'out_invoice': 'sale',
                'in_invoice': 'purchase',
                'out_refund': 'sale_refund',
                'in_refund': 'purchase_refund',
            }
            journal_ids = self.pool.get('account.journal').search(cr, uid, [
                ('company_id','=',company_id), ('type', '=', ass.get(ctype, 'purchase')), ('is_current_instance', '=', True)
            ], order='id')
            if not journal_ids:
                raise osv.except_osv(_('Configuration Error !'), _('Can\'t find any account journal of %s type for this company.\n\nYou can create one in the menu: \nConfiguration\Financial Accounting\Accounts\Journals.') % (ass.get(type, 'purchase'), ))
            res['value']['journal_id'] = journal_ids[0]
            # TODO: it's very bad to set a domain by onchange method, no time to rewrite UniField !
            res['domain']['journal_id'] = [('id', 'in', journal_ids)]
        return res

    def onchange_partner_id(self, cr, uid, ids, ctype, partner_id, date_invoice=False, payment_term=False, partner_bank_id=False,
                            company_id=False, is_inkind_donation=False, is_intermission=False, is_debit_note=False, is_direct_invoice=False,
                            account_id=False):
        """
        Get default donation account for Donation invoices.
        Get default intermission account for Intermission Voucher IN/OUT invoices.
        Get default currency from partner if this one is linked to a pricelist.
        Ticket utp917 - added code to avoid currency cd change if a direct invoice
        """
        res = super(account_invoice, self).onchange_partner_id(cr, uid, ids, ctype, partner_id, date_invoice, payment_term, partner_bank_id, company_id)
        if is_inkind_donation and partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            account_id = partner and partner.donation_payable_account and partner.donation_payable_account.id or False
            res['value']['account_id'] = account_id
        if is_intermission and partner_id:
            if account_id:
                # if the account_id field is filled in: keep its value
                res['value']['account_id'] = account_id
            else:
                # else: use its default value
                intermission_default_account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
                account_id = intermission_default_account and intermission_default_account.id or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
                res['value']['account_id'] = account_id
        if partner_id and ctype:
            p = self.pool.get('res.partner').browse(cr, uid, partner_id)
            ai_direct_invoice = False
            if ids: #utp917
                ai = self.browse(cr, uid, ids)[0]
                ai_direct_invoice = ai.is_direct_invoice
            if p:
                c_id = False
                if ctype in ['in_invoice', 'out_refund'] and p.property_product_pricelist_purchase:
                    c_id = p.property_product_pricelist_purchase.currency_id.id
                elif ctype in ['out_invoice', 'in_refund'] and p.property_product_pricelist:
                    c_id = p.property_product_pricelist.currency_id.id
                # UFTP-121: regarding UTP-917, we have to change currency when changing partner, but not for direct invoices
                if c_id and (not is_direct_invoice and not ai_direct_invoice):
                    if not res.get('value', False):
                        res['value'] = {'currency_id': c_id}
                    else:
                        res['value'].update({'currency_id': c_id})
        # UFTP-168: If debit note, set account to False value
        if is_debit_note:
            res['value'].update({'account_id': False})
        return res

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for i in self.browse(cr, uid, ids):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               i.document_date, i.date_invoice)
        return True

    def _check_invoice_merged_lines(self, cr, uid, ids, context=None):
        """
        US-357:
            merge of lines by account break lines descriptions (required field)
            => before next workflow stage from draft (validate, split)
               check that user has entered description on each line
               (force user to enter a custom description)
        """
        for self_br in self.browse(cr, uid, ids, context=context):
            if self_br.is_merged_by_account:
                if not all([ l.name for l in self_br.invoice_line ]):
                    raise osv.except_osv(
                        _('Error'),
                        _('Please enter a description in each merged line' \
                            ' before invoice validation')
                    )

    def _refund_cleanup_lines(self, cr, uid, lines, is_account_inv_line=False, context=None):
        """
        Remove useless fields
        """
        for line in lines:
            if line.get('move_lines',False):
                del line['move_lines']
            if line.get('import_invoice_id',False):
                del line['import_invoice_id']
        res = super(account_invoice, self)._refund_cleanup_lines(cr, uid, lines, is_account_inv_line=is_account_inv_line, context=context)
        return res

    def check_po_link(self, cr, uid, ids, context=None):
        """
        Check that invoice (only supplier invoices) has no link with a PO. This is because of commitments presence.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for inv in self.read(cr, uid, ids, ['purchase_ids', 'type', 'is_inkind_donation', 'is_debit_note', 'is_intermission', 'state']):
            if inv.get('type', '') == 'in_invoice' and not inv.get('is_inkind_donation', False) and not inv.get('is_debit_note', False):
                if inv.get('purchase_ids', False):
                    if inv.get('is_intermission'):
                        if inv.get('state', '') != 'draft':  # only draft IVIs can be deleted
                            raise osv.except_osv(_('Warning'),
                                                 _('Intermission Vouchers linked to a PO can be deleted only in Draft state.'))
                    else:
                        # US-1702 Do not allow at all the deletion of SI coming from PO
                        raise osv.except_osv(_('Warning'), _('You cannot cancel or delete a supplier invoice linked to a PO.'))
        return True

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
        res = self.pool.get('account.period').search(cr, uid, [('date_start','<=',inv.date_invoice or strftime('%Y-%m-%d')),
                                                               ('date_stop','>=',inv.date_invoice or strftime('%Y-%m-%d')), ('state', 'not in', ['created', 'done']),
                                                               ('company_id', '=', inv.company_id.id), ('special', '=', False)], context=context, order="date_start ASC, name ASC")
        return res

    def __hook_lines_before_pay_and_reconcile(self, cr, uid, lines):
        """
        Add document date to account_move_line before pay and reconcile
        """
        for line in lines:
            if line[2] and 'date' in line[2] and not line[2].get('document_date', False):
                line[2].update({'document_date': line[2].get('date')})
        return lines

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        """
        Rename Supplier/Customer to "Donor" if view_type == tree
        """
        if not context:
            context = {}
        res = super(account_invoice, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree' and (context.get('journal_type', False) == 'inkind' or context.get('journal_type', False) == 'intermission'):
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='partner_id']")
            name = _('Donor')
            if context.get('journal_type') == 'intermission':
                name = _('Partner')
            for node in nodes:
                node.set('string', name)
            res['arch'] = etree.tostring(doc)
        elif view_type in ('tree', 'search') and context.get('type') in ['out_invoice', 'out_refund']:
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='supplier_reference']")
            for node in nodes:
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc)
        elif view_type == 'form' and context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'sale' \
                and not context.get('is_debit_note', False) and not context.get('is_intermission', False):
            # Restriction on allowed partners for STV: Inter-section or External type, customers only
            doc = etree.XML(res['arch'])
            partner_nodes = doc.xpath("//field[@name='partner_id']")
            partner_domain_stv = "[('partner_type', 'in', ('section', 'external')), ('customer', '=', True)]"
            for node in partner_nodes:
                node.set('domain', partner_domain_stv)
            res['arch'] = etree.tostring(doc)
        return res

    def default_get(self, cr, uid, fields, context=None):
        """
        Fill in fake currency for intermission invoice (in context).
        """
        defaults = super(account_invoice, self).default_get(cr, uid, fields, context=context)
        if context and context.get('is_intermission', False):
            intermission_type = context.get('intermission_type', False)
            if intermission_type in ('in', 'out'):
                # UF-2270: manual intermission (in or out)
                if defaults is None:
                    defaults = {}
                user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                if user and user[0] and user[0].company_id:
                    # get company default currency
                    if user[0].company_id.currency_id:
                        defaults['fake_currency_id'] = user[0].company_id.currency_id.id
                        defaults['currency_id'] = defaults['fake_currency_id']
                    # get 'intermission counter part' account
                    if user[0].company_id.intermission_default_counterpart:
                        defaults['account_id'] = user[0].company_id.intermission_default_counterpart.id
                    else:
                        raise osv.except_osv("Error","Company Intermission Counterpart Account must be set")
                # 'INT' intermission journal
                int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                if int_journal_id:
                    defaults['fake_journal_id'] = int_journal_id
                    defaults['journal_id'] = defaults['fake_journal_id']
        return defaults

    def copy(self, cr, uid, inv_id, default=None, context=None):
        """
        Delete period_id from invoice.
        Check context for splitting invoice.
        Reset register_line_ids.
        """
        # Some checks
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'period_id': False,
            'purchase_ids': False,  # UFTP-24 do not copy linked POs
            'purchase_list': False,  # UFTP-24 do not copy linked: reset of potential purchase list flag (from a PO direct purchase)
            'partner_move_line': False,
            'imported_invoices': False
        })
        # Manual duplication should generate a "manual document not created through the supply workflow"
        # so we don't keep the link to: FOs, Picking List
        if context.get('from_button', False):
            default.update({
                'order_ids': False,
                'picking_id': False,
            })
        # Reset register_line_ids if not given in default
        if 'register_line_ids' not in default:
            default['register_line_ids'] = []
        # US-267: Reset st_lines if not given in default, otherwise a new line in Reg will be added
        if 'st_lines' not in default:
            default['st_lines'] = []
        # Default behaviour
        new_id = super(account_invoice, self).copy(cr, uid, inv_id, default, context)
        # Case where you split an invoice
        if 'split_it' in context:
            purchase_obj = self.pool.get('purchase.order')
            sale_obj = self.pool.get('sale.order')
            if purchase_obj:
                # attach new invoice to PO
                purchase_ids = purchase_obj.search(cr, uid, [('invoice_ids', 'in', [inv_id])], context=context)
                if purchase_ids:
                    purchase_obj.write(cr, uid, purchase_ids, {'invoice_ids': [(4, new_id)]}, context=context)
            if sale_obj:
                # attach new invoice to SO
                sale_ids = sale_obj.search(cr, uid, [('invoice_ids', 'in', [inv_id])], context=context)
                if sale_ids:
                    sale_obj.write(cr, uid, sale_ids, {'invoice_ids': [(4, new_id)]}, context=context)
        return new_id


    def is_set_ref_from_partner(self, cr, uid, vals, context=None):
        '''read some properties to determine if the invoice is a supplier
        invoice or supplier refund to be able to set the reference from partner.
        '''
        if context is None:
            context = {}

        is_supplier_invoice = vals.get('type') == 'in_invoice'\
            and not vals.get('is_direct_invoice')\
            and not vals.get('is_inkind_donation')\
            and not vals.get('is_debit_note')\
            and not vals.get('is_intermission')

        is_supplier_refund = vals.get('type') == 'in_refund'

        if is_supplier_invoice or is_supplier_refund:
            return True
        return False

    def create(self, cr, uid, vals, context=None):
        """
        """
        if not context:
            context = {}
        if 'document_date' in vals and 'date_invoice' in vals:
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               vals['document_date'], vals['date_invoice'], context=context)

        # Create a sequence for this new invoice
        res_seq = self.create_sequence(cr, uid, vals, context)
        vals.update({'sequence_id': res_seq,})

        # UTP-317 # Check that no inactive partner have been used to create this invoice
        if 'partner_id' in vals:
            partner_id = vals.get('partner_id')
            if isinstance(partner_id, (str)):
                partner_id = int(partner_id)
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.read(cr, uid, partner_id,
                                       ['active', 'name', 'ref'])
            if partner and not partner['active']:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner and partner['name'] or '',))

            #US-1686: set supplier reference from partner
            if 'supplier_reference' not in vals\
                    and self.is_set_ref_from_partner(cr, uid, vals=vals,
                                                     context=context):
                vals['supplier_reference'] = partner['ref']

        return super(account_invoice, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # US_286: Forbit possibility to add include price tax
        # in bottom left corner
        if 'tax_line' in vals:
            tax_obj = self.pool.get('account.tax')
            for tax_line in vals['tax_line']:
                if tax_line[2]:
                    if 'account_tax_id' in tax_line[2]:
                        args = [('price_include', '=', '1'),
                                ('id', '=', tax_line[2]['account_tax_id'])]
                        tax_ids = tax_obj.search(cr, uid, args, limit=1,
                                                 order='NO_ORDER', context=context)
                        if tax_ids:
                            raise osv.except_osv(_('Error'),
                                                 _('Tax included in price can not be tied to the whole invoice.'))

        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete register line if this invoice is a Direct Invoice.
        Don't delete an invoice that is linked to a PO. This is only for supplier invoices.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Check register lines
        for inv in self.browse(cr, uid, ids):
            if inv.is_direct_invoice and inv.register_line_ids:
                if not context.get('from_register', False):
                    self.pool.get('account.bank.statement.line').unlink(cr, uid, [x.id for x in inv.register_line_ids], {'from_direct_invoice': True})
        # Check PO
        self.check_po_link(cr, uid, ids)
        return super(account_invoice, self).unlink(cr, uid, ids, context)

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new invoice
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Invoice L' # For Invoice Lines
        code = 'account.invoice'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def log(self, cr, uid, inv_id, message, secondary=False, context=None):
        """
        Change first "Invoice" word from message into "Debit Note" if this invoice is a debit note.
        Change it to "In-kind donation" if this invoice is an In-kind donation.
        """
        if not context:
            context = {}
        local_ctx = context.copy()
        # Prepare some values
        # Search donation view and return it
        try:
            # try / except for runbot
            debit_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_debit_note_form')
            inkind_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_inkind_donation_form')
            intermission_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_intermission_form')
            supplier_invoice_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_supplier_form')
            customer_invoice_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_form')
            supplier_direct_invoice_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', 'direct_supplier_invoice_form')
        except ValueError:
            return super(account_invoice, self).log(cr, uid, inv_id, message, secondary, context)
        debit_view_id = debit_res and debit_res[1] or False
        debit_note_ctx = {'view_id': debit_view_id, 'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True}
        # Search donation view and return it
        inkind_view_id = inkind_res and inkind_res[1] or False
        inkind_ctx = {'view_id': inkind_view_id, 'type':'in_invoice', 'journal_type': 'inkind', 'is_inkind_donation': True}
        # Search intermission view
        intermission_view_id = intermission_res and intermission_res[1] or False
        intermission_ctx = {'view_id': intermission_view_id, 'journal_type': 'intermission', 'is_intermission': True}
        customer_view_id = customer_invoice_res[1] or False
        customer_ctx = {'view_id': customer_view_id, 'type': 'out_invoice', 'journal_type': 'sale'}
        message_changed = False
        pattern = re.compile('^(Invoice)')
        for el in [('is_debit_note', 'Debit Note', debit_note_ctx), ('is_inkind_donation', 'In-kind Donation', inkind_ctx), ('is_intermission', 'Intermission Voucher', intermission_ctx)]:
            if self.read(cr, uid, inv_id, [el[0]]).get(el[0], False) is True:
                m = re.match(pattern, message)
                if m and m.groups():
                    message = re.sub(pattern, el[1], message, 1)
                    message_changed = True
                local_ctx.update(el[2])
        # UF-1112: Give all customer invoices a name as "Stock Transfer Voucher".
        if not message_changed and self.read(cr, uid, inv_id, ['type']).get('type', False) == 'out_invoice':
            message = re.sub(pattern, 'Stock Transfer Voucher', message, 1)

            local_ctx.update(customer_ctx)
        # UF-1307: for supplier invoice log (from the incoming shipment), the context was not
        # filled with all the information; this leaded to having a "Sale" journal in the supplier
        # invoice if it was saved after coming from this link. Here's the fix.
        if local_ctx.get('type', False) == 'in_invoice':
            if not local_ctx.get('journal_type', False):
                supplier_view_id = supplier_invoice_res and supplier_invoice_res[1] or False
                local_ctx.update({'journal_type': 'purchase',
                                  'view_id': supplier_view_id})
            elif local_ctx.get('direct_invoice_view', False): # UFTP-166: The wrong context saved in log
                supplier_view_id = supplier_direct_invoice_res and supplier_direct_invoice_res[1] or False
                local_ctx = {'journal_type': 'purchase',
                             'view_id': supplier_view_id}
        return super(account_invoice, self).log(cr, uid, inv_id, message, secondary, local_ctx)

    def invoice_open(self, cr, uid, ids, context=None):
        """
        No longer fills the date automatically, but requires it to be set
        """
        # Some verifications
        if context is None:
            context = {}
        self._check_invoice_merged_lines(cr, uid, ids, context=context)
        self.check_accounts_for_partner(cr, uid, ids, context=context)

        # Prepare workflow object
        wf_service = netsvc.LocalService("workflow")
        for inv in self.browse(cr, uid, ids):
            values = {}
            curr_date = strftime('%Y-%m-%d')
            if inv.is_debit_note:
                for inv_line in inv.invoice_line:
                    if inv_line.partner_id != inv.partner_id:
                        raise osv.except_osv(_('Warning'),
                                             _('All the imported lines must have the same partner as the Debit Note.'))
            # the journal used for Intermission Vouchers must be the INT journal of the current instance
            is_iv = context and context.get('type') in ['in_invoice', 'out_invoice'] and not context.get('is_debit_note') \
                and not context.get('is_inkind_donation') and context.get('is_intermission')
            if is_iv:
                int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                # update the IV if the INT journal exists but isn't used in the IV (= journal created after the IV creation)
                if int_journal_id:
                    if not inv.journal_id or inv.journal_id.id != int_journal_id:
                        self.write(cr, uid, inv.id, {'journal_id': int_journal_id}, context=context)
                else:
                    raise osv.except_osv(_('Warning'), _('No Intermission journal found for the current instance.'))
            if not inv.date_invoice and not inv.document_date:
                values.update({'date': curr_date, 'document_date': curr_date, 'state': 'date'})
            elif not inv.date_invoice:
                values.update({'date': curr_date, 'document_date': inv.document_date, 'state': 'date'})
            elif not inv.document_date:
                values.update({'date': inv.date_invoice, 'document_date': curr_date, 'state': 'date'})
            if inv.type in ('in_invoice', 'in_refund') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding/2.0):
                state = values and 'both' or 'amount'
                values.update({'check_total': inv.check_total , 'amount_total': inv.amount_total, 'state': state})
            if values:
                values['invoice_id'] = inv.id
                wiz_id = self.pool.get('wizard.invoice.date').create(cr, uid, values, context)
                return {
                    'name': "Missing Information",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.invoice.date',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': wiz_id,
                }

            wf_service.trg_validate(uid, 'account.invoice', inv.id, 'invoice_open', cr)

        return True

    def action_reconcile_imported_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile each imported invoice with its attached invoice line
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # browse all given invoices
        for inv in self.browse(cr, uid, ids):
            for invl in inv.invoice_line:
                if not invl.import_invoice_id:
                    continue
                imported_invoice = invl.import_invoice_id
                # reconcile partner line from import invoice with this invoice line attached move line
                import_invoice_partner_move_lines = self.pool.get('account.move.line').search(cr, uid, [('invoice_partner_link', '=', imported_invoice.id)])
                invl_move_lines = [x.id or None for x in invl.move_lines]
                rec = self.pool.get('account.move.line').reconcile_partial(cr, uid, [import_invoice_partner_move_lines[0], invl_move_lines[0]], 'auto', context=context)
                if not rec:
                    return False
        return True

    def action_reconcile_direct_invoice(self, cr, uid, inv, context=None):
        """
        Reconcile move line if invoice is a Direct Invoice
        NB: In order to define that an invoice is a Direct Invoice, we need to have register_line_ids not null
        """
        # Verify that this invoice is linked to a register line and have a move
        if not inv:
            return False
        if inv.move_id and inv.register_line_ids:
            ml_obj = self.pool.get('account.move.line')
            # First search move line that becomes from invoice
            res_ml_ids = ml_obj.search(cr, uid, [
                ('move_id', '=', inv.move_id.id),
                ('account_id', '=', inv.account_id.id),
                ('invoice_line_id', '=', False),  # US-254: do not seek invoice line's JIs (if same account as header)
            ])
            if len(res_ml_ids) > 1:
                raise osv.except_osv(_('Error'), _('More than one journal items found for this invoice.'))
            invoice_move_line_id = res_ml_ids[0]
            # Then search move line that corresponds to the register line
            reg_line = inv.register_line_ids[0]
            reg_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', reg_line.move_ids[0].id), ('account_id', '=', reg_line.account_id.id)])
            if len(reg_ml_ids) > 1:
                raise osv.except_osv(_('Error'), _('More than one journal items found for this register line.'))
            register_move_line_id = reg_ml_ids[0]
            # Finally do reconciliation
            ml_obj.reconcile_partial(cr, uid, [invoice_move_line_id, register_move_line_id])
        return True

    def action_cancel(self, cr, uid, ids, *args):
        """
        Reverse move if this object is a In-kind Donation. Otherwise do normal job: cancellation.
        Don't delete an invoice that is linked to a PO. This is only for supplier invoices.
        """
        to_cancel = []
        for i in self.browse(cr, uid, ids):
            if i.is_inkind_donation:
                move_id = i.move_id.id
                tmp_res = self.pool.get('account.move').reverse(cr, uid, [move_id], strftime('%Y-%m-%d'))
                # If success change invoice to cancel and detach move_id
                if tmp_res:
                    # Change invoice state
                    self.write(cr, uid, [i.id], {'state': 'cancel', 'move_id':False})
                continue
            to_cancel.append(i.id)
        # Check PO link
        self.check_po_link(cr, uid, ids)
        return super(account_invoice, self).action_cancel(cr, uid, to_cancel, args)

    def action_date_assign(self, cr, uid, ids, *args):
        """
        Check Document date.
        """
        # Prepare some values
        period_obj = self.pool.get('account.period')
        # Default behaviour to add date
        res = super(account_invoice, self).action_date_assign(cr, uid, ids, args)
        # Process invoices
        for i in self.browse(cr, uid, ids):
            if not i.date_invoice:
                self.write(cr, uid, i.id, {'date_invoice': strftime('%Y-%m-%d')})
                i = self.browse(cr, uid, i.id) # This permit to refresh the browse of this element
            if not i.document_date:
                raise osv.except_osv(_('Warning'), _('Document Date is a mandatory field for validation!'))
            # UFTP-105: Search period and raise an exeception if this one is not open
            period_ids = period_obj.get_period_from_date(cr, uid, i.date_invoice)
            if not period_ids:
                raise osv.except_osv(_('Error'), _('No period found for this posting date: %s') % (i.date_invoice))
            for period in period_obj.browse(cr, uid, period_ids):
                if period.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('You cannot validate this document in the given period: %s because it\'s not open. Change the date of the document or open the period.') % (period.name))
        # Posting date should not be done BEFORE document date
        self._check_document_date(cr, uid, ids)
        return res

    def get_account_invoice_type(self, cr, uid, inv_id, context=None):
        """
        Returns the type of the account.invoice document as a string
        It can be: 'si', 'sr', 'di', 'ivi', 'ivo', 'stv', 'dn', 'cr', 'donation'
        Raises an error if the type is not recognized.
        """
        if context is None:
            context = {}
        inv_type = False
        fields = ['type', 'is_debit_note', 'is_inkind_donation', 'is_intermission', 'is_direct_invoice', 'internal_number']
        inv = self.browse(cr, uid, inv_id, fields_to_fetch=fields, context=context)
        if inv.is_debit_note:
            if inv.type == 'out_invoice':
                inv_type = 'dn'  # Debit Note
        elif inv.is_inkind_donation:
            if inv.type == 'in_invoice':
                inv_type = 'donation'
        elif inv.is_intermission:
            if inv.type == 'in_invoice':
                inv_type = 'ivi'  # Intermission Voucher In
            elif inv.type == 'out_invoice':
                inv_type = 'ivo'  # Intermission Voucher Out
        elif inv.type == 'in_invoice':
            if inv.is_direct_invoice:
                inv_type = 'di'  # Direct Invoice
            else:
                inv_type = 'si'  # Supplier Invoice
        elif inv.type == 'in_refund':
            inv_type = 'sr'  # Supplier Refund
        elif inv.type == 'out_invoice':
            inv_type = 'stv'  # Stock Transfer Voucher'
        elif inv.type == 'out_refund':
            inv_type = 'cr'  # Customer Refund'
        if not inv_type:
            raise osv.except_osv(_('Error'), _('The type of the document %s is unknown.') % inv.internal_number or '')
        return inv_type

    def _check_journal(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the journal used are not compatible
        """
        if context is None:
            context = {}
        journal = self.browse(cr, uid, inv_id, fields_to_fetch=['journal_id'], context=context).journal_id
        j_type = journal.type
        if inv_type is None:
            inv_type = self.get_account_invoice_type(cr, uid, inv_id, context=context)
        if inv_type in ('si', 'di') and j_type != 'purchase' or inv_type == 'sr' and j_type != 'purchase_refund' or \
            inv_type in ('ivi', 'ivo') and j_type != 'intermission' or inv_type in ('stv', 'dn') and j_type != 'sale' or \
                inv_type == 'cr' and j_type != 'sale_refund' or inv_type == 'donation' and j_type not in ('inkind', 'extra'):
            raise osv.except_osv(_('Error'), _("The journal %s is not allowed for this document.") % journal.name)

    def _check_partner(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the partner used are not compatible
        """
        if context is None:
            context = {}
        partner = self.browse(cr, uid, inv_id, fields_to_fetch=['partner_id'], context=context).partner_id
        p_type = partner.partner_type
        if inv_type is None:
            inv_type = self.get_account_invoice_type(cr, uid, inv_id, context=context)
        # if a supplier/customer is expected for the doc: check that the partner used has the right flag
        supplier_ko = inv_type in ('si', 'di', 'sr', 'ivi', 'donation') and not partner.supplier
        customer_ko = inv_type in ('ivo', 'stv', 'dn', 'cr') and not partner.customer
        if supplier_ko or customer_ko or inv_type in ('ivi', 'ivo') and p_type != 'intermission' or \
            inv_type == 'stv' and p_type not in ('section', 'external') or \
                inv_type == 'donation' and p_type not in ('esc', 'external', 'section'):
            raise osv.except_osv(_('Error'), _("The partner %s is not allowed for this document.") % partner.name)

    def _check_header_account(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the account used are not compatible
        """
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        account = self.browse(cr, uid, inv_id, fields_to_fetch=['account_id'], context=context).account_id
        if inv_type is None:
            inv_type = self.get_account_invoice_type(cr, uid, inv_id, context=context)
        account_domain = []
        if inv_type in ('si', 'di', 'sr'):
            account_domain.append(('restricted_area', '=', 'in_invoice'))
        elif inv_type in ('stv', 'cr'):
            account_domain.append(('restricted_area', '=', 'out_invoice'))
        elif inv_type == 'dn':
            account_domain.append(('restricted_area', '=', 'out_invoice'))
            account_domain.append(('is_intersection_counterpart', '=', False))
        elif inv_type == 'donation':
            account_domain.append(('restricted_area', '=', 'donation_header'))
        elif inv_type == 'ivi':
            context.update(({'check_header_ivi': True, }))
            account_domain.append(('restricted_area', '=', 'intermission_header'))
        elif inv_type == 'ivo':
            context.update(({'check_header_ivo': True, }))
            account_domain.append(('restricted_area', '=', 'intermission_header'))
        account_domain.append(('id', '=', account.id))  # the account used in the account_invoice
        if not account_obj.search_exist(cr, uid, account_domain, context=context):
            raise osv.except_osv(_('Error'), _("The account %s - %s is not allowed for this document.") % (account.code, account.name))

    def _check_line_accounts(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the accounts used at line level are not compatible
        No check is done for Debit Notes where the creation of lines is only possible by importing existing finance docs
        """
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        inv_line_obj = self.pool.get('account.invoice.line')
        lines = inv_line_obj.search(cr, uid, [('invoice_id', '=', inv_id)], context=context, order='NO_ORDER')
        if inv_type is None:
            inv_type = self.get_account_invoice_type(cr, uid, inv_id, context=context)
        account_domain = []
        if inv_type in ('si', 'di', 'sr', 'cr'):
            account_domain.append(('restricted_area', '=', 'invoice_lines'))
        elif inv_type == 'stv':
            context.update(({'check_line_stv': True, }))
            account_domain.append(('restricted_area', '=', 'invoice_lines'))
        elif inv_type == 'donation':
            account_domain.append(('restricted_area', '=', 'donation_lines'))
        elif inv_type in ('ivi', 'ivo'):
            account_domain.append(('restricted_area', '=', 'intermission_lines'))
        for line in inv_line_obj.browse(cr, uid, lines, fields_to_fetch=['account_id'], context=context):
            acc = line.account_id
            if not account_obj.search_exist(cr, uid, account_domain + [('id', '=', acc.id)], context=context):
                raise osv.except_osv(_('Error'), _("The account %s - %s used at line level is not allowed.") % (acc.code, acc.name))

    def check_domain_restrictions(self, cr, uid, ids, context=None):
        """
        Check that the journal, partner and accounts used are compatible with the type of the document
        """
        if context is None:
            context = {}
        for inv_id in ids:
            inv_type = self.get_account_invoice_type(cr, uid, inv_id, context=context)
            self._check_journal(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_partner(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_header_account(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_line_accounts(cr, uid, inv_id, inv_type=inv_type, context=context)

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Give function to use when changing invoice to open state
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
        if not self.action_reconcile_imported_invoice(cr, uid, ids, context):
            return False
        self.check_domain_restrictions(cr, uid, ids, context)  # raises an error if one unauthorized element is used
        return True

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        """
        Add these field into invoice line:
        - invoice_line_id
        """
        if not context:
            context = {}
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context)
        res.update({'invoice_line_id': x.get('invoice_line_id', False)})
        return res

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
        return super(account_invoice, self).finalize_invoice_move_lines(cr, uid, inv, new_line)

    def button_debit_note_import_invoice(self, cr, uid, ids, context=None):
        """
        Launch wizard that permits to import invoice on a debit note
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all given invoices
        for inv in self.browse(cr, uid, ids):
            if inv.type != 'out_invoice' or inv.is_debit_note == False:
                raise osv.except_osv(_('Error'), _('You can only do import invoice on a Debit Note!'))
            w_id = self.pool.get('debit.note.import.invoice').create(cr, uid, {'invoice_id': inv.id, 'currency_id': inv.currency_id.id,
                                                                               'partner_id': inv.partner_id.id}, context=context)
            context.update({
                'active_id': inv.id,
                'active_ids': ids,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'debit.note.import.invoice',
                'name': 'Import invoice',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': w_id,
                'context': context,
                'target': 'new',
            }

    def button_split_invoice(self, cr, uid, ids, context=None):
        """
        Launch the split invoice wizard to split an invoice in two elements.
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_invoice_merged_lines(cr, uid, ids, context=context)

        # Prepare some value
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        inv_lines_obj = self.pool.get('account.invoice.line')
        # Creating wizard
        wizard_id = self.pool.get('wizard.split.invoice').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        # Add invoices_lines into the wizard
        invoice_line_ids = self.pool.get('account.invoice.line').search(cr, uid, [('invoice_id', '=', ids[0])], context=context)
        # Some other verifications
        if not len(invoice_line_ids):
            raise osv.except_osv(_('Error'), _('No invoice line in this invoice or not enough elements'))
        for invl in inv_lines_obj.browse(cr, uid, invoice_line_ids, context=context):
            wiz_lines_obj.create(cr, uid, {'invoice_line_id': invl.id, 'product_id': invl.product_id.id, 'quantity': invl.quantity,
                                           'price_unit': invl.price_unit, 'description': invl.name, 'wizard_id': wizard_id}, context=context)
        # Return wizard
        if wizard_id:
            return {
                'name': "Split Invoice",
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.split.invoice',
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [wizard_id],
                'context':
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_id': wizard_id,
                }
            }
        return False

    def button_donation_certificate(self, cr, uid, ids, context=None):
        """
        Open a view containing a list of all donation certificates linked to the given invoice.
        """
        for inv in self.browse(cr, uid, ids):
            pick_id = inv.picking_id and inv.picking_id.id or ''
            domain = "[('res_model', '=', 'stock.picking'), ('res_id', '=', " + str(pick_id) + "), ('description', '=', 'Certificate of Donation')]"
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_attachment_tree_2')
            view_id = view_id and view_id[1] or False
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_attachment_search_2')
            search_view_id = search_view_id and search_view_id[1] or False
            return {
                'name': "Certificate of Donation",
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'search_view_id': search_view_id,
                'domain': domain,
                'context': context,
                'target': 'current',
            }
        return False

    def button_dummy_compute_total(self, cr, uid, ids, context=None):
        return True

    def button_merge_lines(self, cr, uid, ids, context=None):
        # US-357 merge lines (by account) button for draft SIs
        def check(inv_br):
            if not inv_br.can_merge_lines:
                raise osv.except_osv(_('Error'),
                                     _("Invoice not eligible for lines merging"))

            account_iterations = {}
            for l in inv_br.invoice_line:
                account_iterations[l.account_id.id] = \
                    account_iterations.setdefault(l.account_id.id, 0) + 1

            any_to_merge = False
            if account_iterations:
                for a in account_iterations:
                    if account_iterations[a] > 1:
                        any_to_merge = True
                        break

            if not any_to_merge:
                raise osv.except_osv(_('Error'),
                                     _("Invoice has no line to merge by account"))

        def is_tax_included(inv_br):
            '''
            Returns True if ALL the invoice lines have an "included tax", else returns False
            Note: a "tax included" and a "tax excluded" within the same line wouldn't make sense
            '''
            tax_included = True
            for inv_line in inv_br.invoice_line:
                if not inv_line.invoice_line_tax_id or not inv_line.invoice_line_tax_id[0].price_include:
                    tax_included = False
                    break
            return tax_included

        def check_tax_lines(inv_br, vals):
            '''
            Returns vals.
            vals['invoice_line_tax_id'] will contain the tax lines to use for the whole invoice,
            if all lines to merge have the same taxes.
            Otherwise vals['invoice_line_tax_id'] will contain False
            '''
            for l in inv_br.invoice_line:
                # get rid of the product tax line if <> between merged lines
                if vals['invoice_line_tax_id'] is None:
                    # first tax line browsed for the account
                    if l.invoice_line_tax_id:
                        vals['invoice_line_tax_id'] = [ t.id for t in l.invoice_line_tax_id ]
                    else:
                        vals['invoice_line_tax_id'] = False
                elif vals['invoice_line_tax_id'] and l.invoice_line_tax_id:
                    # track <> tax lines, if it's the case abort tax(es) in merge
                    tax_ids = [ t.id for t in l.invoice_line_tax_id ]
                    if cmp(vals['invoice_line_tax_id'], tax_ids) != 0:
                        vals['invoice_line_tax_id'] = False
                else:
                    # no tax(es) for this line, abort tax(es) in merge
                    vals['invoice_line_tax_id'] = False
                if not vals['invoice_line_tax_id']:
                    break
            return vals

        def compute_merge(inv_br):
            """
            :result:
                - A: lines vals by line number
                - B: and list of inv id to keep (1 line by account (not merged))
            :rtype : [dict, list]

            NOTES:
            - no impact on 'import_invoice_id', 'is_corrected' as the 
              invoice is draft so not imported, and no accounting entries
            - for order_line_id and sale_order_line_id these m2o are used
              for AD at line level but when merging we keep only AD from header
            """
            index = 1
            vals_template = {
                '_index_': index,  # internal merged line index

                'account_id': False,
                'company_id': inv_br.company_id.id,
                'discount': 0.,
                'invoice_id': inv_br.id,
                'invoice_line_tax_id': None,  # m2m (None to distinguished False)
                'name': '',
                'partner_id': inv_br.partner_id.id,
                'price_unit': 0.,
                'quantity': 1.,
            }

            by_account_vals = {}  # key: account_id
            for l in inv_br.invoice_line:
                # get current merge vals for account or create new
                if l.account_id.id in by_account_vals:
                    vals = by_account_vals[l.account_id.id]
                else:
                    # new account to merge
                    vals = vals_template.copy()
                    vals.update({
                        '_index_': index,
                        'account_id': l.account_id.id,
                    })
                    index += 1

                '''
                There is only one case where the "base" used for computation must be "tax included":
                when taxes are the same for ALL lines and that taxes are included in the price.
                In all other cases, the untaxed amount should be used:
                - if taxes are identical for each line and are excluded, the tax computation is based on the untaxed amount
                - if taxes are different, only the untaxed amount is kept (the user has to review the tax amount and change it manually)
                '''
                if vals['invoice_line_tax_id'] is None:
                    vals = check_tax_lines(inv_br, vals)
                if vals['invoice_line_tax_id'] and is_tax_included(inv_br):
                    vals['price_unit'] += (l.price_unit * (1-(l.discount or 0.0)/100.0)) * l.quantity
                    if l.invoice_id.currency_id.rounding:
                        rounding = l.invoice_id.currency_id.rounding
                        vals['price_unit'] = round(vals['price_unit'] / rounding) * rounding
                else:
                    vals['price_unit'] += l.price_subtotal  # qty 1 and price

                # update merge line
                by_account_vals[l.account_id.id] = vals

                # internal merged lines ids
                if not '_ids_' in by_account_vals[l.account_id.id]:
                    by_account_vals[l.account_id.id]['_ids_'] = []
                by_account_vals[l.account_id.id]['_ids_'].append(l.id)

            # result by index
            res = [{}, []]
            for a in by_account_vals:
                if len(by_account_vals[a]['_ids_']) > 1:
                    # more than 1 inv line by account
                    index = by_account_vals[a]['_index_']
                    del by_account_vals[a]['_index_']
                    del by_account_vals[a]['_ids_']
                    res[0][index] = by_account_vals[a]
                else:
                    res[1].append(by_account_vals[a]['_ids_'][0])
            return res

        def delete_lines(inv_br, skip_ids):
            # get ids to delete
            ad_to_del_ids = []
            line_to_del_ids = []

            for l in inv_br.invoice_line:
                if l.id in skip_ids:
                    continue  # line not to del (1 by account)
                # delete AD
                if l.analytic_distribution_id \
                        and not l.analytic_distribution_id.id in ad_to_del_ids:
                    ad_to_del_ids.append(l.analytic_distribution_id.id)
                line_to_del_ids.append(l.id)

            # delete ADs
            if ad_to_del_ids:
                ad_obj.unlink(cr, uid, ad_to_del_ids, context=context)

            # delete lines
            if line_to_del_ids:
                ail_obj.unlink(cr, uid, line_to_del_ids, context=context)

        def do_merge(inv_br, lines_vals, not_merged_ids):
            """
            :param lines_vals: lines vals in order
            :type lines_vals: dict
            """
            # the invoice is reviewed with merge lines
            # => reset the line number sequence from 1
            if inv_br.sequence_id:
                inv_br.sequence_id.write({'number_next': 1}, context=context)

            # create merge lines
            for ln in sorted(lines_vals.keys()):
                vals = lines_vals[ln]

                # post encode tax m2m
                vals['invoice_line_tax_id'] = vals['invoice_line_tax_id'] \
                    and [(6, 0, vals['invoice_line_tax_id'])] or False

                # create merge line
                if not self.pool.get('account.invoice.line').create(cr, uid,
                                                                    vals, context=context):
                    break

            # recompute seq number for not merged lines
            ail_obj = self.pool.get('account.invoice.line')
            if not_merged_ids:
                for lid in not_merged_ids:
                    ln = inv_br.sequence_id.get_id(code_or_id='id')
                    ail_obj.write(cr, uid, [lid], {
                        'line_number': ln,
                    })

        def merge_invoice(inv_br):
            check(inv_br)
            merge_res = compute_merge(inv_br)
            delete_lines(inv_br, merge_res[1])
            do_merge(inv_br, merge_res[0], merge_res[1])

            # set merged flag
            inv_br.write({'is_merged_by_account': True}, context=context)

            # recompute taxes (reset not manual ones)
            self.button_reset_taxes(cr, uid, [inv_br.id], context=context)

        def post_merge(inv_br):
            inv_br.write({
                # update check total for accurate check amount at validation
                'check_total':
                    inv_br.amount_total or inv_br.check_amount or 0.,
            }, context=context)

        res = {}
        if not ids:
            return False
        if isinstance(ids, (int, long, )):
            ids = [ids]

        ail_obj = self.pool.get('account.invoice.line')
        ad_obj = self.pool.get('analytic.distribution')

        # merging
        for inv_br in self.browse(cr, uid, ids, context=context):
            merge_invoice(inv_br)

        # post processing (reload invoices)
        for inv_br in self.browse(cr, uid, ids, context=context):
            post_merge(inv_br)

        return res

    def check_accounts_for_partner(self, cr, uid, ids, context=None,
                                   header_obj=False, lines_field='invoice_line',
                                   line_level_partner_type=False):
        """
        :param header_obj: target model for header or self
        :param lines_field: lines o2m field
        :param line_level_partner_type: partner to check lines account with
            if true use partner_type for lines else use header partner
        :return:
        """
        header_obj = header_obj or self
        account_obj = self.pool.get('account.account')
        header_errors = []
        lines_errors = []

        for r in header_obj.browse(cr, uid, ids, context=context):
            partner_id = hasattr(r, 'partner_id') and r.partner_id \
                and r.partner_id.id or False

            # header check
            if hasattr(r, 'account_id') and r.account_id:
                if not account_obj.is_allowed_for_thirdparty(cr, uid,
                                                             [r.account_id.id], partner_id=partner_id,
                                                             context=context)[r.account_id.id]:
                    header_errors.append(
                        _('invoice header account and partner not compatible.'))

            # lines check
            if lines_field and hasattr(r, lines_field):
                if line_level_partner_type:
                    partner_id = False
                else:
                    partner_type = False
                line_index = 1
                for l in getattr(r, lines_field):
                    if l.account_id:
                        if line_level_partner_type:
                            # partner at line level
                            partner_type = l.partner_type
                        if not account_obj.is_allowed_for_thirdparty(cr,
                                                                     uid, [l.account_id.id],
                                                                     partner_type=partner_type or False,
                                                                     partner_id=partner_id or False,
                                                                     context=context)[l.account_id.id]:
                            num = hasattr(l, 'line_number') and l.line_number \
                                or line_index
                            if not lines_errors:
                                header_errors.append(
                                    _('following # lines with account/partner' \
                                        ' are not compatible:'))
                            lines_errors.append(_('#%d account %s - %s') % (num,
                                                                            l.account_id.code, l.account_id.name, ))
                    line_index += 1

        if header_errors or lines_errors:
            raise osv.except_osv(_('Error'),
                                 "\n".join(header_errors + lines_errors))

    def has_one_line_reconciled(self, cr, uid, account_inv_ids, context=None):
        """
        Returns True if one of the account.invoice docs whose ids are in parameter has a line which is fully reconciled
        (header, lines, taxes at header or line level)
        """
        if context is None:
            context = {}
        if isinstance(account_inv_ids, (int, long, )):
            account_inv_ids = [account_inv_ids]
        aml_obj = self.pool.get('account.move.line')
        aml_ids = aml_obj.search(cr, uid, [('invoice', 'in', account_inv_ids)], order='NO_ORDER', context=context)
        if aml_obj.search_exist(cr, uid, [('id', 'in', aml_ids), ('reconcile_id', '!=', False)]):
            return True
        return False


account_invoice()


class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.product_id.id, obj.uos_id.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))
        return True

    _constraints = [(_uom_constraint, 'Constraint error on Uom', [])]

    def _have_been_corrected(self, cr, uid, ids, name, args, context=None):
        """
        Return True if ALL elements are OK:
         - a journal items is linked to this invoice line
         - the journal items is linked to an analytic line that have been reallocated
        """
        if context is None:
            context = {}
        res = {}

        def has_ana_reallocated(move):
            for ml in move.move_lines or []:
                for al in ml.analytic_lines or []:
                    if al.is_reallocated:
                        return True
            return False

        for il in self.browse(cr, uid, ids, context=context):
            res[il.id] = has_ana_reallocated(il)
        return res

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Give product code for each invoice line
        """
        res = {}
        for inv_line in self.browse(cr, uid, ids, context=context):
            res[inv_line.id] = ''
            if inv_line.product_id:
                res[inv_line.id] = inv_line.product_id.default_code

        return res
    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    _columns = {
        'line_number': fields.integer(string='Line Number'),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Account Computation')),
        'import_invoice_id': fields.many2one('account.invoice', string="From an import invoice", readonly=True),
        'move_lines':fields.one2many('account.move.line', 'invoice_line_id', string="Journal Item", readonly=True),
        'is_corrected': fields.function(_have_been_corrected, method=True, string="Have been corrected?", type='boolean',
                                        readonly=True, help="This informs system if this item have been corrected in analytic lines. Criteria: the invoice line is linked to a journal items that have analytic item which is reallocated.",
                                        store=False),
        'product_code': fields.function(_get_product_code, method=True, store=False, string="Product Code", type='char'),
        'reference': fields.char(string="Reference", size=64),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'reversed_invoice_line_id': fields.many2one('account.invoice.line', string='Reversed Invoice Line',
                                                    help='Invoice line that has been reversed by this one through a '
                                                         '"refund cancel" or "refund modify"'),
    }

    _defaults = {
        'price_unit': lambda *a: 0.00,
        'is_corrected': lambda *a: False,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
    }

    _order = 'line_number'

    def create(self, cr, uid, vals, context=None):
        """
        Give a line_number to invoice line.
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        # Create new number with invoice sequence
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            invoice = self.pool.get('account.invoice').browse(cr, uid, vals['invoice_id'])
            if invoice and invoice.sequence_id:
                sequence = invoice.sequence_id
                line = sequence.get_id(code_or_id='id', context=context)
                vals.update({'line_number': line})
        return super(account_invoice_line, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Give a line_number in invoice_id in vals
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """

        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            for il in self.browse(cr, uid, ids):
                if not il.line_number and il.invoice_id.sequence_id:
                    sequence = il.invoice_id.sequence_id
                    il_number = sequence.get_id(code_or_id='id', context=context)
                    vals.update({'line_number': il_number})
        res = super(account_invoice_line, self).write(cr, uid, ids, vals, context)
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.is_direct_invoice and invl.invoice_id.state == 'draft':
                amount = 0.0
                for l in invl.invoice_id.invoice_line:
                    amount += l.price_subtotal
                self.pool.get('account.invoice').write(cr, uid, [invl.invoice_id.id], {'check_total': amount}, context)
                self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in invl.invoice_id.register_line_ids], {'amount': -1 * amount}, context)
        return res

    def copy(self, cr, uid, inv_id, default=None, context=None):
        """
        Check context to see if we come from a split. If yes, we create the link between invoice and PO/FO.
        """
        if not context:
            context = {}
        if not default:
            default = {}

        new_id = super(account_invoice_line, self).copy(cr, uid, inv_id, default, context)

        if 'split_it' in context:
            purchase_lines_obj = self.pool.get('purchase.order.line')
            sale_lines_obj = self.pool.get('sale.order.line')

            if purchase_lines_obj:
                purchase_line_ids = purchase_lines_obj.search(cr, uid,
                                                              [('invoice_lines', 'in', [inv_id])], order='NO_ORDER')
                if purchase_line_ids:
                    purchase_lines_obj.write(cr, uid, purchase_line_ids, {'invoice_lines': [(4, new_id)]})

            if sale_lines_obj:
                sale_lines_ids =  sale_lines_obj.search(cr, uid,
                                                        [('invoice_lines', 'in', [inv_id])], order='NO_ORDER')
                if sale_lines_ids:
                    sale_lines_obj.write(cr, uid,  sale_lines_ids, {'invoice_lines': [(4, new_id)]})

        return new_id

    def copy_data(self, cr, uid, inv_id, default=None, context=None):
        """
        Copy an invoice line without its move lines,
        without the link to a reversed invoice line,
        and without link to PO/FO lines when the duplication is manual
        """
        if default is None:
            default = {}
        default.update({'move_lines': False,
                        'reversed_invoice_line_id': False,
                        })
        # Manual duplication should generate a "manual document not created through the supply workflow"
        # so we don't keep the link to PO/FO at line level
        if context.get('from_button', False):
            default.update({
                'order_line_id': False,
                'sale_order_line_id': False,
                'sale_order_lines': False,
            })
        return super(account_invoice_line, self).copy_data(cr, uid, inv_id, default, context)

    def unlink(self, cr, uid, ids, context=None):
        """
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Fetch all invoice_id to check
        direct_invoice_ids = []
        abst_obj = self.pool.get('account.bank.statement.line')
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.is_direct_invoice and invl.invoice_id.state == 'draft':
                direct_invoice_ids.append(invl.invoice_id.id)
                # find account_bank_statement_lines and used this to delete the account_moves and associated records
                absl_ids = abst_obj.search(cr, uid,
                                           [('invoice_id','=',invl.invoice_id.id)],
                                           order='NO_ORDER')
                if absl_ids:
                    abst_obj.unlink_moves(cr, uid, absl_ids, context)
        # Normal behaviour
        res = super(account_invoice_line, self).unlink(cr, uid, ids, context)
        # See all direct invoice
        for inv in self.pool.get('account.invoice').browse(cr, uid, direct_invoice_ids):
            amount = 0.0
            for l in inv.invoice_line:
                amount += l.price_subtotal
            self.pool.get('account.invoice').write(cr, uid, [inv.id], {'check_total': amount}, context)
            self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in inv.register_line_ids], {'amount': -1 * amount}, context)
        return res

    def move_line_get_item(self, cr, uid, line, context=None):
        """
        Add a link between move line and its invoice line
        """
        # some verification
        if not context:
            context = {}
        # update default dict with invoice line ID
        res = super(account_invoice_line, self).move_line_get_item(cr, uid, line, context=context)
        res.update({'invoice_line_id': line.id})
        return res

    def button_open_analytic_lines(self, cr, uid, ids, context=None):
        """
        Return analytic lines linked to this invoice line.
        First we takes all journal items that are linked to this invoice line.
        Then for all journal items, we take all analytic journal items.
        Finally we display the result for "button_open_analytic_corrections" of analytic lines
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        al_ids = []
        # Browse give invoice lines
        for il in self.browse(cr, uid, ids, context=context):
            if il.move_lines:
                for ml in il.move_lines:
                    if ml.analytic_lines:
                        al_ids += [x.id for x in ml.analytic_lines]
        return self.pool.get('account.analytic.line').button_open_analytic_corrections(cr, uid, al_ids, context=context)

    def onchange_donation_product(self, cr, uid, ids, product_id, qty, currency_id, context=None):
        res = {'value': {}}
        if product_id:
            p_info = self.pool.get('product.product').read(cr, uid, product_id, ['donation_expense_account', 'partner_ref', 'standard_price', 'categ_id'], context=context)
            if p_info['donation_expense_account']:
                res['value']['account_id'] = p_info['donation_expense_account'][0]
            elif p_info['categ_id']:
                categ = self.pool.get('product.category').read(cr, uid, p_info['categ_id'][0], ['donation_expense_account'])
                if categ['donation_expense_account']:
                    res['value']['account_id'] = categ['donation_expense_account'][0]
            if p_info['partner_ref']:
                res['value']['name'] = p_info['partner_ref']
            if p_info['standard_price']:
                std_price = p_info['standard_price']
                company_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
                if company_curr_id and company_curr_id != currency_id:
                    std_price = self.pool.get('res.currency').compute(cr, uid, company_curr_id, currency_id, std_price, context=context)
                res['value']['price_unit'] = std_price
                res['value']['price_subtotal'] = (qty or 0) * std_price
        return res

    def onchange_donation_qty_price(self, cr, uid, ids, qty, price_unit, context=None):
        return {'value': {'price_subtotal': (qty or 0) * (price_unit or 0)}}


account_invoice_line()


class res_partner(osv.osv):
    _description='Partner'
    _inherit = "res.partner"

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _get_search_by_invoice_type(self, cr, uid, obj, name, args,
                                    context=None):
        res = []
        if not len(args):
            return res
        if context is None:
            context = {}
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        if not args[0][2]:
            return res

        invoice_type = context.get('type', False)
        if invoice_type:
            if invoice_type in ('in_invoice', 'in_refund', ):
                # in invoices: only supplier partner
                res = [('supplier', '=', True)]
            elif invoice_type in ('out_invoice', 'out_refund', ):
                # out invoices: only customer partner
                res = [('customer', '=', True)]

        return res

    _columns = {
        'by_invoice_type': fields.function(_get_fake, type='boolean',
                                           fnct_search=_get_search_by_invoice_type, method=True),
    }

    def name_search(self, cr, uid, name='', args=None, operator='ilike',
                    context=None, limit=100):
        # BKLG-50: IN/OUT invoice/refund partner autocompletion filter
        # regarding supplier/customer
        if context is None:
            context = {}
        if args is None:
            args = []

        alternate_domain = False
        invoice_type = context.get('type', False)
        if invoice_type:
            if invoice_type in ('in_invoice', 'in_refund', ):
                alternate_domain = [('supplier', '=', True)]
            elif invoice_type in ('out_invoice', 'out_refund', ):
                alternate_domain = [('customer', '=', True)]
        if alternate_domain:
            args += alternate_domain

        return super(res_partner, self).name_search(cr, uid, name=name,
                                                    args=args, operator=operator, context=context, limit=limit)

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
