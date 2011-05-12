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
        'partner_id': fields.many2one('res.partner', 'Partner', change_default=True, readonly=True, required=False, states={'draft':[('readonly',False)]}),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False, states={'draft':[('readonly',False)]}),
        'account_id': fields.many2one('account.account', 'Account', required=False, readonly=True, states={'draft':[('readonly',False)]}, help="The partner account used for this invoice."),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True),
        'register_id': fields.many2one('account.bank.statement', 'Register', readonly=True),
        'reconciled' : fields.boolean('Reconciled'),
        'residual': fields.float('Residual', digits_compute=dp.get_precision('Account')),
    }
    _defaults = {
        'currency_id': lambda cr, uid, ids, c: c.get('currency')
    }

    def invoice_create_wizard(self, cr, uid, ids, context={}):
        # TODO: check amount total
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
            for line in self.pool.get('wizard.account.invoice.line').read(cr, uid, inv['invoice_line'],['product_id','account_id', 'account_analytic_id', 'quantity', 'price_unit','price_subtotal','name', 'uos_id']):
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
        inv_obj = self.pool.get('account.invoice')
        inv_id = inv_obj.create(cr, uid, vals)
        netsvc.LocalService("workflow").trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)
       
        inv_number = inv_obj.read(cr, uid, inv_id, ['number'])['number']
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {
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
        # TODO: delete wizard.account.invoice or use osv_memory
        # TODO: validate invoice ? hard post statement line ?

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

class wizard_closing_cashbox(osv.osv_memory):
    
    _name = 'wizard.closing.cashbox'
    _columns = {
        'be_sure': fields.boolean( string="Are you sure ?", required=False ),
    }
    
    def button_close_cashbox(self, cr, uid, ids, context={}):
        # retrieve context active id (verification)
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv(_('Warning'), _("You don't select any item!"))
        else:
            # retrieve user's choice
            res = self.browse(cr,uid,ids)[0].be_sure
            if res:
                st_obj = self.pool.get('account.bank.statement')
                # retrieve Calculated balance
                balcal = st_obj.read(cr, uid, id, ['balance_end']).get('balance_end')
                # retrieve CashBox Balance
                bal = st_obj.read(cr, uid, id, ['balance_end_cash']).get('balance_end_cash')
                
                # compare the selected balances
                equivalent = balcal == bal
                if not equivalent:
                    res_id = st_obj.write(cr, uid, [id], {'state' : 'partial_close'})
                    return { 'type' : 'ir.actions.act_window_close', 'active_id' : res_id }
                else:
                    # @@@override@account.account_bank_statement.button_confirm_bank()
                    obj_seq = self.pool.get('ir.sequence')
                    if context is None:
                        context = {}

                    for st in st_obj.browse(cr, uid, [id], context=context):
                        j_type = st.journal_id.type
                        company_currency_id = st.journal_id.company_id.currency_id.id
                        if not st_obj.check_status_condition(cr, uid, st.state, journal_type=j_type):
                            continue

                        st_obj.balance_check(cr, uid, st.id, journal_type=j_type, context=context)
                        if (not st.journal_id.default_credit_account_id) \
                                or (not st.journal_id.default_debit_account_id):
                            raise osv.except_osv(_('Configuration Error !'),
                                    _('Please verify that an account is defined in the journal.'))

                        if not st.name == '/':
                            st_number = st.name
                        else:
                            if st.journal_id.sequence_id:
                                c = {'fiscalyear_id': st.period_id.fiscalyear_id.id}
                                st_number = obj_seq.get_id(cr, uid, st.journal_id.sequence_id.id, context=c)
                            else:
                                st_number = obj_seq.get(cr, uid, 'account.bank.statement')

                        for line in st.move_line_ids:
                            if line.state <> 'valid':
                                raise osv.except_osv(_('Error !'),
                                        _('The account entries lines are not in valid state.'))
                        for st_line in st.line_ids:
                            if st_line.analytic_account_id:
                                if not st.journal_id.analytic_journal_id:
                                    raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") \
                                        % (st.journal_id.name,))
                    # @@@end
                            if not st_line.amount:
                                 continue
                        res_id = st_obj.write(cr, uid, [st.id], {'name': st_number, 'state':'confirm', 'closing_date': datetime.today()}, context=context)
                return { 'type' : 'ir.actions.act_window_close', 'active_id' : res_id }
            else:
                raise osv.except_osv(_('Warning'), _("You don't have really confirm by ticking!"))
        return { 'type' : 'ir.actions.act_window_close', 'active_id' : id }

wizard_closing_cashbox()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
