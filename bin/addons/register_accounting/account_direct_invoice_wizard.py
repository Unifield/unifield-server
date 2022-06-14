#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
#    Developer: Fabien MORIN
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
from osv import osv
from osv import fields
from tools.translate import _
import decimal_precision as dp
from register_tools import _get_date_in_period
from register_tools import open_register_view
from datetime import datetime
from dateutil.relativedelta import relativedelta


class account_direct_invoice_wizard(osv.osv_memory):
    _name = 'account.direct.invoice.wizard'
    _description = 'Account Invoice Temp Object'

    def _get_type(self, cr, uid, context=None):
        if context is None:
            context = {}
        res = context.get('type', 'out_invoice')
        if context.get('search_default_supplier', False) and context.get('default_supplier', False):
            res = 'in_invoice'
        return res

    _columns = {
        'account_id': fields.many2one('account.account', 'Account',
                                      required=True,
                                      states={'draft':[('readonly', False)]},
                                      help="The partner account used for this invoice."),
        'address_contact_id': fields.many2one('res.partner.address',
                                              'Contact Address',
                                              states={'draft':[('readonly',False)]}),
        'address_invoice_id': fields.many2one('res.partner.address',
                                              'Invoice Address', required=False),
        'amount_total': fields.float('Total',
                                     digits_compute=dp.get_precision('Account'), readonly=True),
        'analytic_distribution_id':
            fields.many2one('analytic.distribution', 'Analytic Distribution',
                            select="1"),
            'check_total': fields.float('Total',
                                        digits_compute=dp.get_precision('Account'),
                                        states={'open':[('readonly', True)],
                                                'close':[('readonly', True)],
                                                'paid':[('readonly', True)]}),
            'comment': fields.text('Additional Information'),
            'company_id': fields.many2one('res.company', 'Company',
                                          required=True, change_default=True,
                                          states={'draft':[('readonly',False)]}),
            'create_date': fields.datetime('Created', readonly=True),
            'currency_id': fields.many2one('res.currency', string="Currency"),
            'date_invoice': fields.date('Posting Date', select=True),
            'document_date': fields.date('Document date'),
            'invoice_wizard_line': fields.one2many('account.direct.invoice.wizard.line',
                                                   'invoice_wizard_id', 'Invoice Wizard Lines',
                                                   states={'draft':[('readonly',False)]}),
            'is_direct_invoice': fields.boolean("Is direct invoice?",
                                                readonly=True, default=True),
            'journal_id': fields.many2one('account.journal', 'Journal',
                                          required=True, readonly=True),
            'name': fields.char('Description', size=64, select=True,
                                readonly=True, states={'draft':[('readonly',False)]}),
            'number': fields.related('move_id','name', type='char',
                                     readonly=True, size=64, relation='account.move', store=True,
                                     string='Number', write_relate=False),
            'origin': fields.char('Source Document', size=512,
                                  help="Referencie of the document that produced this invoice.",
                                  readonly=True, states={'draft':[('readonly',False)]}),
            'original_invoice_id': fields.many2one('account.invoice', 'Original Invoice'),
            'partner_id': fields.many2one('res.partner', 'Partner',
                                          change_default=True, required=True),
            'partner_bank_id': fields.many2one('res.partner.bank',
                                               'Bank Account',
                                               help='Bank Account Number, Company bank account if '
                                               'Invoice is customer or supplier refund, otherwise '
                                               'Partner bank account number.', readonly=True,
                                               states={'draft':[('readonly',False)]}),
            'payment_term': fields.many2one('account.payment.term',
                                            'Payment Term', states={'draft':[('readonly',False)]},
                                            help="If you use payment terms, the due date will be computed "
                                            "automatically at the generation of accounting entries. If you"
                                            " keep the payment term and the due date empty, it means "
                                            "direct payment. The payment term may compute several due "
                                            "dates, for example 50% now, 50% in one month."),
            'reference': fields.char('Invoice Reference', size=64,
                                     help="The partner reference of this invoice."),
            'register_posting_date': fields.date(string=\
                                                 "Register posting date for Direct Invoice", required=False),
            'register_id': fields.many2one('account.bank.statement', 'Register', readonly=True),
            'register_line_id': fields.many2one('account.bank.statement.line',
                                                'Register Line', readonly=True),
            'user_id': fields.many2one('res.users', 'Salesman'),
            'state': fields.selection([
                ('draft','Draft'),
                ('proforma','Pro-forma'),
                ('proforma2','Pro-forma'),
                ('open','Open'),
                ('paid','Paid'),
                ('cancel','Cancelled')
            ],'State', select=True, readonly=True,),
        'type': fields.selection([
            ('out_invoice','Customer Invoice'),
            ('in_invoice','Supplier Invoice'),
            ('out_refund','Customer Refund'),
            ('in_refund','Supplier Refund'),
        ],'Type', readonly=True, select=True, change_default=True),
    }

    _defaults = {
        'register_id': False,
        'payment_term': False,
        'type': _get_type,
        'state': 'draft',
        'check_total': 0.0,
        'user_id': lambda s, cr, u, c: u,
    }

    def vacuum(self, cr, uid):
        one_hour = (datetime.now() + relativedelta(hours=-1)).strftime("%Y-%m-%d %H:%M:%S")
        unlink_ids = self.search(cr, uid, [('create_date', '<', one_hour)])
        if unlink_ids:
            return self.unlink(cr, uid, unlink_ids)
        return True

    def unlink(self, cr, uid, ids, context=None):
        """ delete the associated analytic_distribution
        """
        analytic_distribution = self.pool.get('analytic.distribution')
        for obj in self.browse(cr, uid, ids, context):
            # delete analytic_distribution linked to this wizard
            if obj.analytic_distribution_id:
                analytic_distribution.unlink(cr, uid,
                                             obj.analytic_distribution_id.id)
        return super(account_direct_invoice_wizard, self).unlink(cr, uid, ids)

    def compute_wizard(self, cr, uid, ids, context=None):
        """
        Check invoice lines and compute the total invoice amount
        """
        for wiz_inv in self.browse(cr, uid, ids):
            amount = 0
            for line in wiz_inv.invoice_wizard_line:
                amount += line.price_subtotal
            self.write(cr, uid, [wiz_inv.id], {'amount_total': amount})
        return True

    def check_analytic_distribution(self, cr, uid, ids):
        """
        Check that all line have a valid analytic distribution state
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for w in self.browse(cr, uid, ids):
            for l in w.invoice_wizard_line:
                if l.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Warning'),
                                         _('Analytic distribution is not valid for this line: %s') % (l.name or '',))
        return True

    def invoice_create_wizard(self, cr, uid, ids, context=None):
        """
        Take information from wizard in order to create an invoice, invoice lines and to post a register line that permit to reconcile the invoice.
        """
        if context is None:
            context = {}

        self.check_analytic_distribution(cr, uid, ids)

        # Prepare some value
        absl_obj = self.pool.get('account.bank.statement.line')
        inv_obj = self.pool.get('account.invoice')
        invl_obj = self.pool.get('account.invoice.line')
        wiz_obj = self
        wiz_line_obj = self.pool.get('account.direct.invoice.wizard.line')
        analytic_distribution = self.pool.get('analytic.distribution')

        # Get the original invoice
        inv_id = wiz_obj.browse(cr, uid, ids, context)[0].original_invoice_id.id
        invoice = inv_obj.browse(cr, uid, inv_id)

        if invoice and invoice.state != 'draft':
            raise osv.except_osv(_('Error'), _('The invoice cannot be modified'
                                               ' as it is in %s state (should be draft).') % (invoice.state))

        vals = {}
        inv = self.read(cr, uid, ids[0], [])
        for val in inv:
            if val in ('id', 'wiz_invoice_line', 'register_id'):
                continue
            if isinstance(inv[val], tuple):
                vals[val] = inv[val][0]
            elif isinstance(inv[val], list):
                continue
            elif inv[val]:
                vals[val] = inv[val]
        vals['invoice_line'] = []
        amount = 0
        if inv['invoice_wizard_line']:
            for line in wiz_line_obj.browse(cr, uid,
                                            inv['invoice_wizard_line']):
                # line level reference overrides header level reference
                line_reference = False
                if line.reference:
                    line_reference = line.reference
                elif inv['reference']:
                    line_reference = inv['reference']
                vals['invoice_line'].append((line.original_invoice_line_id.id,
                                             {
                                                 'product_id': line.product_id.id,
                                                 'account_id': line.account_id.id,
                                                 'account_analytic_id': line.account_analytic_id.id,
                                                 'analytic_distribution_id': line.analytic_distribution_id.id,
                                                 'quantity': line.quantity,
                                                 'invoice_id': vals['original_invoice_id'],
                                                 'price_unit': line.price_unit,
                                                 'name': line.name,
                                                 'uos_id': line.uos_id.id,
                                                 'reference': line_reference,
                                             })
                                            )
                amount += line.price_subtotal

        # Retrieve period
        register = self.pool.get('account.bank.statement').browse(cr, uid, [inv['register_id']], context=context)[0]
        period = register and register.period_id and register.period_id.id or False
        # Check the dates
        if vals['date_invoice'] and vals['register_posting_date']:
            if vals['date_invoice'] < register.period_id.date_start or \
               vals['date_invoice'] > register.period_id.date_stop:
                raise osv.except_osv(_('Warning'), _('Direct Invoice posting date is outside of the register period!'))
            elif vals['register_posting_date'] < register.period_id.date_start or \
                    vals['register_posting_date'] > register.period_id.date_stop:
                raise osv.except_osv(_('Warning'), _('Register Line posting date is outside of the register period!'))
            elif vals['date_invoice'] > vals['register_posting_date']:
                raise osv.except_osv(_('Warning'), _('Direct Invoice posting date must be sooner or equal to the register line posting date!'))
        vals.update({'date_invoice': vals['date_invoice']})
        vals.update({'register_posting_date': vals['register_posting_date']})

        # delete original analytic_distribution because a copy has been done
        # and linked to the original invoice
        if invoice.analytic_distribution_id:
            analytic_distribution.unlink(cr, uid, invoice.analytic_distribution_id.id)

        # update the invoice
        vals_copy = vals.copy()
        # invoice lines are processed just after
        vals_copy.pop('invoice_line')
        context.update({'skip_ad_date_check': True})
        inv_obj.write(cr, uid, [inv_id], vals_copy, context)
        del context['skip_ad_date_check']

        # get line id list
        invl_id_list = [x.id for x in wiz_obj.browse(cr, uid, ids,
                                                     context)[0].original_invoice_id.invoice_line]

        # update the invoice lines
        not_deleted_id_list = []
        for original_line_id, vals_dict in vals['invoice_line']:
            # get the original invoice line
            if original_line_id: # if there is a corresponding original invoice line
                # delete original analytic_distribution because a copy has been done
                # and will be linked to the original invoice_line
                orig_line = invl_obj.browse(cr, uid, original_line_id, context)
                if orig_line.analytic_distribution_id:
                    analytic_distribution.unlink(cr, uid,
                                                 orig_line.analytic_distribution_id.id)
                not_deleted_id_list.append(original_line_id)
                invl_obj.write(cr, uid, [original_line_id], vals_dict, context)
            else:
                # this is a new line, create is called
                invl_obj.create(cr, uid, vals_dict, context)

        # if lines exist in the invoice but not in the wizard, that means that
        # they have been deleted in the wizard. So we need to delete them in the
        # invoice
        for original_line_id in tuple(set(invl_id_list) - set(not_deleted_id_list)):
            invl_obj.unlink(cr, uid, original_line_id, context=context)

        # update the invoice check_total with all line and
        # link invoice and register_line
        amount = 0.0
        for l in invoice.invoice_line:
            amount += l.price_subtotal
        inv_obj.write(cr, uid, [inv_id],
                      {'check_total': amount,
                       'is_direct_invoice': True,
                       'register_line_ids': [(4, vals['register_line_id'])]},
                      context)
        absl_obj.write(cr, uid, [x.id for x in invoice.register_line_ids], {'amount': -1 * amount}, context)

        # Update the attached register line and link the invoice to the register
        reg_line_id = vals['register_line_id']
        values = {
            'account_id': vals['account_id'],
            'currency_id': vals['currency_id'],
            'date': _get_date_in_period(self, cr, uid,
                                        vals['register_posting_date'] or\
                                        time.strftime('%Y-%m-%d'), period, context=context),
            'document_date': vals['document_date'],
            'direct_invoice': True,
            'amount_out': amount,
            'invoice_id': inv_id,
            'partner_type': 'res.partner,%d'%(vals['partner_id'], ),
            'statement_id': inv['register_id'],
            'name': 'Direct Invoice',
            'ref': inv['reference'],     # register line always takes header reference
        }
        absl_obj.write(cr, uid, [reg_line_id], values)

        # set analytic_ditribution to None on the wizard line not to
        # delete it when the wizard will be deleted
        wiz_line_obj.write(cr, uid, inv['invoice_wizard_line'],
                           {'analytic_distribution_id': None})
        # Delete the wizard lines:
        wiz_line_obj.unlink(cr, uid, inv['invoice_wizard_line'], context=context)

        # set analytic_ditribution to None on the wizard not to
        # delete it when the wizard will be deleted
        wiz_obj.write(cr, uid, ids, {'analytic_distribution_id': None})

        # Delete the wizard
        self.unlink(cr, uid, ids, context=context)

        # update invoice
        inv_obj._direct_invoice_updated(cr, uid, [inv_id], context)

        view = open_register_view(self, cr, uid, inv['register_id'])
        # UF-2308: When closing the Direct Invoice, just refresh only the register lines, and no the whole view
        # to avoid having everything reset to default state.
        view['o2m_refresh'] = 'line_ids'
        view['type'] = 'ir.actions.act_window_close'
        return view

    def invoice_reset_wizard(self, cr, uid, ids, context=None):
        """
        Reset the invoice by reseting some fields
        """
        self.write(cr, uid, ids,{
            'invoice_wizard_line': [(5,)],
            'register_posting_date': time.strftime('%Y-%m-%d'),
            'date_invoice': time.strftime('%Y-%m-%d'),
            'partner_id': False,
            'address_invoice_id': False,
            'account_id': False,
            'state': 'draft',
            'analytic_distribution_id': False,
            'document_date': time.strftime('%Y-%m-%d'),
        })
        return True

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invoice = self.browse(cr, uid, ids[0], context=context)
        amount = 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = invoice.currency_id and invoice.currency_id.id or company_currency
        for line in invoice.invoice_wizard_line:
            amount += line.price_subtotal
        # Get analytic_distribution_id
        distrib_id = invoice.analytic_distribution_id and invoice.analytic_distribution_id.id
        account_id = invoice.account_id and invoice.account_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'direct_invoice_id': invoice.id,
            'account_direct_invoice_wizard_id': invoice.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': account_id or False,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all account direct invoice wizard lines.
        To do this, just delete the analytic_distribution id link on each invoice line.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invl_obj = self.pool.get(self._name + '.line')
        # Search invoice lines
        to_reset = invl_obj.search(cr, uid, [('invoice_wizard_id', 'in', ids)])
        invl_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

    def onchange_partner_id(self, cr, uid, ids, ctype, partner_id,\
                            date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False,
                            is_inkind_donation=False, is_intermission=False,
                            is_debit_note=False, is_direct_invoice=False):
        # just call the original method from account.invoice
        return self.pool.get('account.invoice').onchange_partner_id(cr, uid, [],
                                                                    ctype, partner_id, date_invoice, payment_term, partner_bank_id,
                                                                    company_id, is_inkind_donation, is_intermission, is_debit_note,
                                                                    True)

account_direct_invoice_wizard()


class account_direct_invoice_wizard_line(osv.osv_memory):
    _name = 'account.direct.invoice.wizard.line'
    _description = 'Account Invoice Line Temp Object'

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the invoice line, then "valid"
         - if no distribution, take a tour of invoice distribution, if compatible, then "valid"
         - if no distribution on invoice line and invoice, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            # UF-2115: test for elements
            line_distribution_id = False
            invoice_distribution_id = False
            line_account_id = False
            if line.analytic_distribution_id:
                line_distribution_id = line.analytic_distribution_id.id
            if line.invoice_wizard_id and line.invoice_wizard_id.analytic_distribution_id:
                invoice_distribution_id = line.invoice_wizard_id.analytic_distribution_id.id
            if line.account_id:
                line_account_id = line.account_id.id
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line_distribution_id,
                                                                                          invoice_distribution_id, line_account_id,
                                                                                          amount=line.price_subtotal or 0.0)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = ''
            if not invl.is_allocatable:
                continue
            from_header = ''
            if invl.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            res[invl.id] = '%s%s' % (self.pool.get('ir.model.fields').get_browse_selection(cr, uid, invl, 'analytic_distribution_state', context), from_header)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If invoice have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = True
            if inv.analytic_distribution_id:
                res[inv.id] = False
        return res

    def _get_is_allocatable(self, cr, uid, ids, name, arg, context=None):
        """
        If analytic-a-holic account, then this account is allocatable.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = True
            if invl.account_id and not invl.account_id.is_analytic_addicted:
                res[invl.id] = False
        return res

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.invoice_wizard_id and line.invoice_wizard_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }
        return res

    def _amount_line(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            price = line.price_unit * (1-(line.discount or 0.0)/100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                                        price, line.quantity, product=line.product_id,
                                        address_id=line.invoice_wizard_id.address_invoice_id,
                                        partner=line.invoice_wizard_id.partner_id)
            res[line.id] = taxes['total']
            if line.invoice_wizard_id:
                cur = line.invoice_wizard_id.currency_id
                res[line.id] = cur_obj.round(cr, uid, cur.rounding, res[line.id])
        return res

    _columns = {
        'move_id': fields.many2one('account.move', 'Journal Entry',
                                   readonly=True, select=1, ondelete='restrict',
                                   help="Link to the automatically generated Journal Items."),
        'analytic_distribution_id': fields.many2one('analytic.distribution',
                                                    'Analytic Distribution', select="1"),
        'analytic_distribution_state': fields.function(_get_distribution_state,
                                                       method=True, type='selection',
                                                       selection=[('none', 'None'),
                                                                  ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'),
                                                                  ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state",
                                                       help="Informs from distribution state among 'none',"
                                                       " 'valid', 'invalid."),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap,
                                                             method=True, type='char', size=30,
                                                             string="Distribution",
                                                             help="Informs you about analaytic distribution state among 'none',"
                                                             " 'valid', 'invalid', from header or not, or no analytic distribution"),
        'create_date': fields.datetime('Created', readonly=True),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header,
                                                                  method=True, type='boolean', string='Header Distrib.?'),
        'inactive_product': fields.function(_get_inactive_product, method=True,
                                            type='boolean', string='Product is inactive', store=False,
                                            multi='inactive'),
        'invoice_wizard_id': fields.many2one('account.direct.invoice.wizard',
                                             'Invoice Wizard',
                                             ondelete='cascade', select=True),
        'is_allocatable': fields.function(_get_is_allocatable, method=True,
                                          type='boolean', string="Is allocatable?", readonly=True, store=False),
        'reference': fields.char(string="Reference", size=64),
        'name': fields.char('Description', size=256, required=True),
        'origin': fields.char('Origin', size=512,
                              help="Reference of the document that produced this invoice."),
        'uos_id': fields.many2one('product.uom', 'Unit of Measure',
                                  ondelete='set null'),
        'original_invoice_line_id': fields.many2one('account.invoice.line',
                                                    'Original Invoice Line'),
        'product_id': fields.many2one('product.product', 'Product',
                                      ondelete='set null'),
        'account_id': fields.many2one('account.account', 'Account',
                                      required=True, domain=[('type','<>','view'), ('type', '<>',
                                                                                    'closed')],
                                      help="The income or expense account related to the selected product."),
        'price_unit': fields.float('Unit Price', required=True,
                                   digits_compute=dp.get_precision('Account')),
        'price_subtotal': fields.function(_amount_line, method=True,
                                          string='Subtotal', type="float",
                                          digits_compute=dp.get_precision('Account'), store=False),
        'quantity': fields.float('Quantity', required=True),
        'discount': fields.float('Discount (%)',
                                 digits_compute=dp.get_precision('Account')),
        'invoice_line_tax_id': fields.many2many('account.tax',
                                                'account_invoice_line_tax', 'invoice_line_id', 'tax_id', 'Taxes',
                                                domain=[('parent_id','=',False)]),
        'note': fields.text('Notes'),
        'account_analytic_id':  fields.many2one('account.analytic.account',
                                                'Analytic Account'),
        'company_id': fields.related('invoice_wizard_id','company_id',type='many2one',
                                     relation='res.company', string='Company', store=True, readonly=True),
        'partner_id': fields.related('invoice_wizard_id','partner_id',type='many2one',
                                     relation='res.partner', string='Partner',store=True),
        'inactive_error': fields.function(_get_inactive_product, method=True,
                                          type='char', string='Comment', store=False, multi='inactive'),
        'newline': fields.boolean('New line'),
    }

    _defaults = {
        'quantity': lambda *x: 1,
        'price_unit': lambda *x: 0,
        'newline': lambda *a: True,
        'have_analytic_distribution_from_header': lambda *a: True,
        'is_allocatable': lambda *a: True,
        'analytic_distribution_state': lambda *a: '',
        'analytic_distribution_state_recap': lambda *a: '',
        'inactive_product': False,
        'inactive_error': lambda *a: '',
        'original_invoice_line_id': False,
    }

    def unlink(self, cr, uid, ids, context=None):
        """ delete the associated analytic_distribution
        """
        analytic_distribution = self.pool.get('analytic.distribution')
        for obj in self.browse(cr, uid, ids, context):
            # delete analytic_distribution linked to this wizard
            if obj.analytic_distribution_id:
                analytic_distribution.unlink(cr, uid,
                                             obj.analytic_distribution_id.id)
        return super(account_direct_invoice_wizard_line, self).unlink(cr, uid, ids)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No invoice line given. '
                                               'Please save your invoice line before.'))
        # Prepare some values
        invoice_line = self.browse(cr, uid, ids[0], context=context)
        negative_inv = False
        amount = invoice_line.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid,
                                                             context=context).company_id.currency_id.id
        currency = invoice_line.invoice_wizard_id.currency_id and \
            invoice_line.invoice_wizard_id.currency_id.id or company_currency
        # Change amount sign if necessary
        if invoice_line.invoice_wizard_id.type in ['out_invoice', 'in_refund']:
            negative_inv = True
        if negative_inv:
            amount = -1 * amount
        # Get analytic distribution id from this line
        distrib_id = invoice_line and invoice_line.analytic_distribution_id and\
            invoice_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'account_direct_invoice_wizard_line_id': invoice_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': invoice_line.account_id and invoice_line.account_id.id or False,
            'posting_date': invoice_line.invoice_wizard_id.date_invoice,
            'document_date': invoice_line.invoice_wizard_id.document_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def product_id_change(self, cr, uid, ids, product, uom, qty=0, name='', type='out_invoice', partner_id=False, fposition_id=False, price_unit=False, address_invoice_id=False, currency_id=False, context=None):
        # just call the original method from account.invoice.line
        return self.pool.get('account.invoice.line').product_id_change(cr, uid, ids,
                                                                       product, uom, qty=qty, name=name, type=type, partner_id=partner_id,
                                                                       fposition_id=fposition_id, price_unit=price_unit,
                                                                       address_invoice_id=address_invoice_id, currency_id=currency_id,
                                                                       context=context)

account_direct_invoice_wizard_line()
