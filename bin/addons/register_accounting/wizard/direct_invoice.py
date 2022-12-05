#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from tools.translate import _
import decimal_precision as dp
import time
from ..register_tools import open_register_view
from ..register_tools import _get_date_in_period

WIZARD_INVOICE_EXCEPTION = ['register_line_ids', 'invoice_line']
WIZARD_INVOICE_LINE_EXCEPTION = []

class wizard_account_invoice(osv.osv):
    _name = 'wizard.account.invoice'
    _inherit = 'account.invoice'
    _description = 'Direct Invoice'

    _columns  = {
        'invoice_line': fields.one2many('wizard.account.invoice.line', 'invoice_id', 'Invoice Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'partner_id': fields.many2one('res.partner', 'Partner', change_default=True, readonly=True, required=False,
                                      states={'draft':[('readonly',False)]}, domain=[('supplier','=',True)]),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False, states={'draft':[('readonly',False)]}),
        'account_id': fields.many2one('account.account', 'Account', required=False, readonly=True, states={'draft':[('readonly',False)]},
                                      help="The partner account used for this invoice."),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True),
        'register_id': fields.many2one('account.bank.statement', 'Register', readonly=True),
        'reconciled' : fields.boolean('Reconciled'),
        'residual': fields.float('Residual', digits_compute=dp.get_precision('Account')),
        'amount_total': fields.float('Total', digits_compute=dp.get_precision('Account'), readonly=True),
        'register_posting_date': fields.date(string="Register posting date", required=True),
        'reference': fields.char(string="Reference", size=64),
    }
    _defaults = {
        'currency_id': lambda cr, uid, ids, c: c.get('currency'),
        'register_posting_date': lambda *a: time.strftime('%Y-%m-%d'),
        'date_invoice': lambda *a: time.strftime('%Y-%m-%d'),
        'document_date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
    }

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        """
        Avoid problem of many2many and one2many that comes from the object from which we inherit.
        BUG (found in REF-70): The ORM give the same value for m2m and o2m from the inherit object that have the same ID.
        For an example:
          - wizard.account.invoice inherits from account.invoice
          - account.invoice have a purchase_ids field
          - we got an account.invoice with ID 2 that is linked to a PO (with purchase_ids field)
          - when you read wizard.account.invoice that have the same ID, it will return the same value of the purchase_ids field than account.invoice 2!
        """
        # Default behaviour
        res = super(wizard_account_invoice, self).read(cr, uid, ids, fields, context, load)
        # Fetch all many2many and all one2many fields
        field_to_change = []
        if self._name == 'wizard.account.invoice':
            for field in self._columns:
                if self._columns[field]._type in ['many2many', 'one2many'] and field not in WIZARD_INVOICE_EXCEPTION:
                    field_to_change.append(field)
            # Set all fetched field to False
            if not isinstance(ids, list):
                res = [res]

            for obj in res:
                for ftc in field_to_change:
                    obj.update({ftc: []})
        if not isinstance(ids, list):
            return res[0]
        return res

    def check_analytic_distribution(self, cr, uid, ids):
        """
        Check that all line have a valid analytic distribution state
        """
        if isinstance(ids, int):
            ids = [ids]
        for w in self.browse(cr, uid, ids):
            for l in w.invoice_line:
                if l.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Warning'), _('Analytic distribution is not valid for this line: %s') % (l.name or '',))
        return True

    def compute_wizard(self, cr, uid, ids, context=None):
        """
        Check invoice lines and compute the total invoice amount
        """
        for wiz_inv in self.browse(cr, uid, ids):
            amount = 0
            for line in wiz_inv.invoice_line:
                amount += line.price_subtotal
            self.write(cr, uid, [wiz_inv.id], {'amount_total': amount})
        return True

    def invoice_reset_wizard(self, cr, uid, ids, context=None):
        """
        Reset the invoice by reseting some fields
        """
        self.write(cr, uid, ids, {'invoice_line': [(5,)], 'register_posting_date': time.strftime('%Y-%m-%d'), 'date_invoice': time.strftime('%Y-%m-%d'),
                                  'partner_id': False, 'address_invoice_id': False, 'account_id': False, 'state': 'draft', 'analytic_distribution_id': False,
                                  'document_date': time.strftime('%Y-%m-%d'),})
        return True

    def invoice_cancel_wizard(self, cr, uid, ids, context=None):
        """
        Delete the wizard from database
        """
        self.unlink(cr, uid, ids)
        return {}

    def invoice_create_wizard(self, cr, uid, ids, context=None):
        """
        Take information from wizard in order to create an invoice, invoice lines and to post a register line that permit to reconcile the invoice.
        """
        self.check_analytic_distribution(cr, uid, ids)
        self.pool.get('account.invoice').check_accounts_for_partner(cr, uid,
                                                                    ids, context=context, header_obj=self)

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
        if inv['invoice_line']:
            for line in self.pool.get('wizard.account.invoice.line').read(cr, uid, inv['invoice_line'],
                                                                          ['product_id','account_id', 'account_analytic_id', 'quantity', 'price_unit','price_subtotal','name', 'uos_id','analytic_distribution_id','reference']):
                # line level reference overrides header level reference
                line_reference = False
                if line['reference']:
                    line_reference = line['reference']
                elif inv['reference']:
                    line_reference = inv['reference']
                vals['invoice_line'].append( (0, 0,
                                              {
                                                  'product_id': line['product_id'] and line['product_id'][0] or False,
                                                  'account_id': line['account_id'] and line['account_id'][0] or False,
                                                  'account_analytic_id': line['account_analytic_id'] and line['account_analytic_id'][0] or False,
                                                  'analytic_distribution_id': line['analytic_distribution_id'] and line['analytic_distribution_id'][0] or False,
                                                  'quantity': line['quantity'] ,
                                                  'price_unit': line['price_unit'] ,
                                                  'price_subtotal': line['price_subtotal'],
                                                  'name': line['name'],
                                                  'uos_id': line['uos_id'] and line['uos_id'][0] or False,
                                                  'reference': line_reference,
                                              }
                                              ))
                amount += line['price_subtotal']
        # Give the total of invoice in the "check_total" field. This permit not to encount problems when validating invoice.
        vals.update({'check_total': amount})

        # Prepare some value
        inv_obj = self.pool.get('account.invoice')
        absl_obj = self.pool.get('account.bank.statement.line')
        # Retrieve period
        register = self.pool.get('account.bank.statement').browse(cr, uid, [inv['register_id'][0]], context=context)[0]
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

        # Create invoice
        inv_id = inv_obj.create(cr, uid, vals, context=context)
        # Set this invoice as direct invoice (since UTP-551, is_direct_invoice is a boolean and not a function)
        self.pool.get('account.invoice').write(cr, uid, [inv_id], {'is_direct_invoice': True})

        # Create the attached register line and link the invoice to the register
        reg_line_id = absl_obj.create(cr, uid, {
            'account_id': vals['account_id'],
            'currency_id': vals['currency_id'],
            'date': _get_date_in_period(self, cr, uid, vals['register_posting_date'] or time.strftime('%Y-%m-%d'), period, context=context),
            'document_date': vals['document_date'],
            'direct_invoice': True,
            'amount_out': amount,
            'invoice_id': inv_id,
            'partner_type': 'res.partner,%d'%(vals['partner_id'], ),
            'statement_id': inv['register_id'][0],
            'name': 'Direct Invoice',
            'ref': inv['reference'] and inv['reference'] or False,     # register line always takes header reference
        })

        # Temp post the line
        absl_obj.button_temp_posting(cr, uid, [reg_line_id], context=context)

        # Link invoice and register_line
        inv_obj.write(cr, uid, [inv_id], {'register_line_ids': [(4, reg_line_id)]}, context=context)

        # Do reconciliation
        # Moved since UF-1471. This is now down when you hard post the linked register line.

        # fix the reference UFTP-167
        inv_obj.fix_aal_aml_reference(cr, uid, inv_id, context=context)

        # UTP-1041 : additional reference field functionality
        if inv['reference'] is False:
            inv_number = inv_obj.browse(cr, uid, inv_id, context=context).number

            # US-364/1: display the sequence number in the register line
            # reference field if no reference set in DI header
            absl_obj.write(cr, uid, [reg_line_id], {
                'ref': inv_number,
            }, context=context)

            absl = absl_obj.browse(cr, uid, reg_line_id, context=context)
            am = absl.move_ids[0]
            aml_obj = self.pool.get('account.move.line')
            aml_ids = aml_obj.search(cr, uid,[('move_id','=',am.id)], context=context)
            aml_obj.write(cr, uid, aml_ids, {'reference': inv_number}, context=context, check=False, update_check=False)

        # Delete the wizard
        self.unlink(cr, uid, ids, context=context)
        # TODO: unlink the wizard_account_invoice_line rows also

        view = open_register_view(self, cr, uid, inv['register_id'][0])
        # UF-2308: When closing the Direct Invoice, just refresh only the register lines, and no the whole view
        # to avoid having everything reset to default state.
        view['o2m_refresh'] = 'line_ids'
        view['type'] = 'ir.actions.act_window_close'
        return view


    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch header analytic distribution wizard on a direct invoice
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        invoice = self.browse(cr, uid, ids[0], context=context)
        amount = 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = invoice.currency_id and invoice.currency_id.id or company_currency
        for line in invoice.invoice_line:
            amount += line.price_subtotal
        # Get analytic_distribution_id
        distrib_id = invoice.analytic_distribution_id and invoice.analytic_distribution_id.id
        # Get posting date
        posting_date = invoice.date_invoice
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'direct_invoice_id': invoice.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'posting_date': posting_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
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

wizard_account_invoice()

class wizard_account_invoice_line(osv.osv):
    _name = 'wizard.account.invoice.line'
    _table = 'wizard_account_invoice_line'
    _inherit = 'account.invoice.line'

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Give product code for each invoice line
        """
        res = {}
        for inv_line in self.browse(cr, uid, ids, context=context):
            res[inv_line.id] = False
            if inv_line.product_id:
                res[inv_line.id] = inv_line.product_id.default_code
        return res

    _columns  = {
        'invoice_id': fields.many2one('wizard.account.invoice', 'Invoice Reference', select=True),
        'product_code': fields.function(_get_product_code, method=True, store=False, string="Product Code", type='char'),
    }

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        """
        Avoid problem of many2many and one2many that comes from the object from which we inherit.
        BUG (found in REF-70): The ORM give the same value for m2m and o2m from the inherit object that have the same ID.
        For an example:
          - wizard.account.invoice inherits from account.invoice
          - account.invoice have a purchase_ids field
          - we got an account.invoice with ID 2 that is linked to a PO (with purchase_ids field)
          - when you read wizard.account.invoice that have the same ID, it will return the same value of the purchase_ids field than account.invoice 2!
        """
        # Default behaviour
        res = super(wizard_account_invoice_line, self).read(cr, uid, ids, fields, context, load)
        # Fetch all many2many and all one2many fields
        field_to_change = []
        if self._name == 'wizard.account.invoice.line':
            for field in self._columns:
                if self._columns[field]._type in ['many2many', 'one2many'] and field not in WIZARD_INVOICE_LINE_EXCEPTION:
                    field_to_change.append(field)
            # Set all fetched field to False
            if not isinstance(ids, list):
                res = [res]

            for obj in res:
                for ftc in field_to_change:
                    obj.update({ftc: []})
        if not isinstance(ids, list):
            return res[0]
        return res

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a direct invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No direct invoice line given. Please save your direct invoice line before.'))
        # Prepare some values
        invoice_line = self.browse(cr, uid, ids[0], context=context)

        fields_to_write = ['journal_id', 'partner_id', 'address_invoice_id', 'date_invoice', 'register_posting_date',
                           'account_id', 'partner_bank_id', 'payment_term', 'name', 'document_date',
                           'origin', 'address_contact_id', 'user_id', 'comment', 'reference']
        to_write = {}
        for f in fields_to_write:
            if 'd_%s'%(f,) in context:
                to_write[f] = context['d_%s'%(f,)]
        if to_write:
            self.pool.get('wizard.account.invoice').write(cr, uid, [invoice_line.invoice_id.id], to_write)

        negative_inv = False
        amount = invoice_line.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = invoice_line.invoice_id.currency_id and invoice_line.invoice_id.currency_id.id or company_currency
        # Change amount sign if necessary
        if invoice_line.invoice_id.type in ['out_invoice', 'in_refund']:
            negative_inv = True
        if negative_inv:
            amount = -1 * amount
        # Get analytic distribution id from this line
        distrib_id = invoice_line and invoice_line.analytic_distribution_id and invoice_line.analytic_distribution_id.id or False
        # Get posting date
        posting_date = invoice_line.invoice_id.date_invoice
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'direct_invoice_line_id': invoice_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': invoice_line.account_id and invoice_line.account_id.id or False,
            'posting_date': posting_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
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

wizard_account_invoice_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
