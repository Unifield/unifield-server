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
from datetime import datetime
import decimal_precision as dp
import time
import netsvc

class wizard_account_invoice(osv.osv):
    _name = 'wizard.account.invoice'
    _inherit = 'account.invoice'
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
        'register_posting_date': fields.date(string="Register posting date", required=True),
    }
    _defaults = {
        'currency_id': lambda cr, uid, ids, c: c.get('currency'),
        'register_posting_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def invoice_create_wizard(self, cr, uid, ids, context={}):
        """
        Take information from wizard in order to create an invoice, invoice lines and to post a register line that permit to reconcile the invoice.
        """
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
        if inv['invoice_line']:
            amount = 0
            for line in self.pool.get('wizard.account.invoice.line').read(cr, uid, inv['invoice_line'], 
                ['product_id','account_id', 'account_analytic_id', 'quantity', 'price_unit','price_subtotal','name', 'uos_id']):
                print line['account_id']
                vals['invoice_line'].append( (0, 0,
                    {
                        'product_id': line['product_id'] and line['product_id'][0] or False,
                        'account_id': line['account_id'] and line['account_id'][0] or False,
                        'account_analytic_id': line['account_analytic_id'] and line['account_analytic_id'][0] or False,
                        'quantity': line['quantity'] ,
                        'price_unit': line['price_unit'] ,
                        'price_subtotal': line['price_subtotal'],
                        'name': line['name'],
                        'uos_id': line['uos_id'] and line['uos_id'][0] or False,
                    }
                ))
                amount += line['price_subtotal']
        # Give the total of invoice in the "check_total" field. This permit not to encount problems when validating invoice.
        vals.update({'check_total': amount})
        
        # Prepare some value
        inv_obj = self.pool.get('account.invoice')
        absl_obj = self.pool.get('account.bank.statement.line')
        
        # Create invoice
        inv_id = inv_obj.create(cr, uid, vals, context=context)
        
        # Approve invoice
        netsvc.LocalService("workflow").trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)
       
        # Make an invoice number
        inv_number = inv_obj.read(cr, uid, inv_id, ['number'])['number']
        
        # Create the attached register line and link the invoice to the register
        reg_id = absl_obj.create(cr, uid, {
            'account_id': vals['account_id'],
            'currency_id': vals['currency_id'],
            'date': time.strftime('%Y-%m-%d'),
            'direct_invoice': True,
            'amount_out': amount,
            'invoice_id': inv_id,
            'partner_type': 'res.partner,%d'%(vals['partner_id'], ),
            'statement_id': inv['register_id'][0],
            'name': inv_number,
        })
        
        # Hard post the line
        absl_obj.button_hard_posting(cr, uid, [reg_id], context=context)
        
        # Link invoice and register_line
        res_inv = inv_obj.write(cr, uid, [inv_id], {'register_line_ids': [(4, reg_id)]}, context=context)
        
        # Do reconciliation
        inv_obj.action_reconcile_direct_invoice(cr, uid, [inv_id], context=context)

        # Delete the wizard
        # TODO: correct this to work
        self.unlink(cr, uid, ids, context=context)

        # TODO: to be factorized
        st_type = self.pool.get('account.bank.statement').browse(cr, uid, inv['register_id'][0]).journal_id.type
        module = 'account'
        mod_action = 'action_view_bank_statement_tree'
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        if st_type:
            if st_type == 'cash':
                mod_action = 'action_view_bank_statement_tree'
            elif st_type == 'bank':
                mod_action = 'action_bank_statement_tree'
            elif st_type == 'cheque':
                mod_action = 'action_cheque_register_tree'
                module = 'register_accounting'
        result = mod_obj._get_id(cr, uid, module, mod_action)
        id = mod_obj.read(cr, uid, [result], ['res_id'], context=context)[0]['res_id']
        result = act_obj.read(cr, uid, [id], context=context)[0]
        result['res_id'] = inv['register_id'][0]
        result['view_mode'] = 'form,tree,graph'
        views_id = {}
        for (num, typeview) in result['views']:
            views_id[typeview] = num
        result['views'] = []
        for typeview in ['form','tree','graph']:
            if views_id.get(typeview):
                result['views'].append((views_id[typeview], typeview))
        result['target'] = 'crush'
        return result

wizard_account_invoice()

class wizard_account_invoice_line(osv.osv):
    _name = 'wizard.account.invoice.line'
    _table = 'wizard_account_invoice_line'
    _inherit = 'account.invoice.line'
    _columns  = {
        'invoice_id': fields.many2one('wizard.account.invoice', 'Invoice Reference', select=True),
    }

wizard_account_invoice_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
