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

from osv import osv
from osv import fields
from osv import orm
from tools.translate import _

import sync_client.rpc
import uuid
import tools
import time
import sys
import traceback
import netsvc
from datetime import datetime

import sync_client

class test(osv.osv_memory):
    _inherit = "sync.client.test"
    
    def create_data_ucf1_u(self, cr, uid, context=None):
        res_id = self.pool.get('account.account').create(cr, uid, {'code' : "M21", 
                                                          "name" : "MSF Cash Account 1 UCF1", 
                                                          "type" : "liquidity",
                                                          'currency_id' : 38,
                                                          'user_type' : 11 }, context=None)
        self.pool.get('account.account').create(cr, uid, {'code' : "M22", 
                                                          "name" : "MSF Cash Account 2 UCF1", 
                                                          "type" : "liquidity",
                                                          'currency_id' : 38,
                                                          'user_type' : 11 }, context=None)
        
        j_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M2', 
                                                          'currency' : 38,
                                                          'type' : 'cash',
                                                          'default_credit_account_id' : res_id,
                                                          'default_debit_account_id' : res_id,
                                                          'name' : 'MSF Cash Journal UCF1',
                                                          'view_id' : 1}, context=None)
        st_id = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'REG1M2')], context=None)
        if not st_id:
            return False
        
        self.pool.get('account.bank.statement').button_open(cr, uid, st_id, context=context)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : datetime.now().strftime('%Y-%m-%d'),
                                                                      "statement_id" : st_id[0],
                                                                      "name" : "Move 1",
                                                                      "type" : "general",
                                                                      "account_id": res_id,
                                                                      "amount" : 40.0 }, context=context)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : datetime.now().strftime('%Y-%m-%d'),
                                                                      "statement_id" : st_id[0],
                                                                      "name" : "Move 2",
                                                                      "type" : "general",
                                                                      "account_id": res_id,
                                                                      "amount" : 30.0 }, context=context)
        return True

    def modify_data_ucf1_u(self, cr, uid, context=None):
        account_ids = self.pool.get('account.account').search(cr, uid, [('name', '=', 'MSF Cash Account 2 UCF1')], context=context)
        st_ids = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'REG1M2')], context=context)
        line_ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('name', '=', 'Move 2')], context=context)
        j_ids = self.pool.get('account.journal').search(cr, uid, [('name', '=', 'MSF Cash Journal UCF1')], context=context)
        if not account_ids or not st_ids or not line_ids or not j_ids:
            return False
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : datetime.now().strftime('%Y-%m-%d'),
                                                                      "statement_id" : st_ids[0],
                                                                      "name" : "Move 3",
                                                                      "type" : "general",
                                                                      "account_id": account_ids[0],
                                                                      "amount" : 25.0 }, context=context)
        self.pool.get('account.bank.statement.line').write(cr, uid, line_ids, {'account_id' : account_ids[0]}, context=context)
        return True
    
    def check_final_data_ucf1_u(self, cr, uid, context=None):
        if not context:
            context = {}
        ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('account_id', '=', 'MSF Cash Account 2 UCF1')], context=None)
        return len(ids) == 2
    
    
    def create_data_ucf2_u(self, cr, uid, context=None):
        if not context:
            context = {}
        a1_id = self.pool.get('account.account').create(cr, uid, {'code' : "M23", 
                                                          "name" : "MSF Bank Account 1 UCF2", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'user_type' : 7 }, context=None)
        a2_id = self.pool.get('account.account').create(cr, uid, {'code' : "M24", 
                                                          "name" : "MSF Transfert Account 1 UCF2", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'reconcile' : True,
                                                          'user_type' : 7 }, context=None)
        
        a3_id = self.pool.get('account.account').create(cr, uid, {'code' : "M25", 
                                                          "name" : "MSF Cash Account 3 UCF2", 
                                                          "type" : "liquidity",
                                                          'currency_id' : 2,
                                                          'user_type' : 6 }, context=None)
        
        j1_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M21', 
                                                          'currency' : 2,
                                                          'type' : 'bank',
                                                          'default_credit_account_id' : a1_id,
                                                          'default_debit_account_id' : a1_id,
                                                          'name' : 'MSF Bank journal UCF2',
                                                          'view_id' : 1}, context=None)

        
        
        
        st_id = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'REG1M21')], context=None)
        if not st_id:
            return False
        
        p_id = self.pool.get('account.bank.statement').browse(cr, uid, st_id[0]).period_id.id
        self.pool.get('account.period').action_set_state(cr, uid, [p_id], {'state': 'draft'})
        
        self.pool.get('account.bank.statement').button_open(cr, uid, st_id, context=context)
        
        l_id = self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : datetime.now().strftime('%Y-%m-%d'),
                                                                      "statement_id" : st_id[0],
                                                                      "name" : "Move 21",
                                                                      "type" : "general",
                                                                      "account_id": a2_id,
                                                                      "amount" : -2000.0 }, context=context)
        
        self.pool.get('account.bank.statement.line').button_hard_posting(cr, uid, [l_id], context=context)
       
        return True
    
    def open_period(self, cr, uid, context=None):
        if not context:
            context =  {}
        p_ids = self.pool.get('account.period').search(cr, uid, [], context=context)
        self.pool.get('account.period').action_set_state(cr, uid, p_ids, {'state': 'draft'})
    
    def create_cash_statement_ufc2_u(self, cr, uid, context=None):
        if not context:
            context = {}
        
        account_ids = self.pool.get('account.account').search(cr, uid, [('name', '=', 'MSF Transfert Account 1 UCF2')], context=context)
        account3_ids = self.pool.get('account.account').search(cr, uid, [('name', '=', "MSF Cash Account 3 UCF2")], context=context)
        
        print account_ids
        if not account_ids or not account3_ids:
            return False
        
        a3_id = account3_ids[0]
        j_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M23', 
                                                          'currency' : 2,
                                                          'type' : 'cash',
                                                          'default_credit_account_id' : a3_id,
                                                          'default_debit_account_id' : a3_id,
                                                          'name' : 'MSF Cash Journal UCF2',
                                                          'view_id' : 1}, context=None)
        
        st_id = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'REG1M23')], context=None)
        if not st_id:
            return False
        #open the period        
        self.pool.get('account.bank.statement').button_open(cr, uid, st_id, context=context)
        
        l_id = self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : datetime.now().strftime('%Y-%m-%d'),
                                                                      "statement_id" : st_id[0],
                                                                      "name" : "Move 22",
                                                                      "type" : "general",
                                                                      "account_id": account_ids[0],
                                                                      "amount" : 2000.0 }, context=context)
        
        self.pool.get('account.bank.statement.line').button_hard_posting(cr, uid, [l_id], context=context)
        return True
        
    def reconcile_ucf2_u(self, cr, uid, context=None):
        if not context:
            context = {}
        ids = self.pool.get('account.move.line').search(cr, uid, [('name', 'ilike', 'Move'), ('account_id', '=', 'M24 MSF Transfert Account 1 UCF2')], context=context)
        if not ids:
            return False
        
        if not context:
            context = {}
        context['active_ids'] = ids
        wiz_id = self.pool.get('account.move.line.reconcile').create(cr, uid, {}, context=context)
        self.pool.get('account.move.line.reconcile').trans_rec_reconcile_full(cr, uid, [wiz_id], context=context)
        return True
    
    
    def init_data_ucf3_u(self, cr, uid, context=None):
        if not context:
            context = {}
        supplier_S2_id = self.pool.get('res.partner').create(cr, uid, {
            'name': 'msf_supplier_UCF3',
            'supplier': True,
        })
        purchase_account_id = self.pool.get('account.account').create(cr, uid, {
            'code': "M2PC", 
            "name": "Creditors", 
            "type": "other",
            'currency_id': 2,
            'reconcile': True,
            'user_type': 7,
        })
        
        purchase_account_id2 = self.pool.get('account.account').create(cr, uid, {
            'code': "M2PP", 
            "name": "MSF Suppliers", 
            "type": "payable",
            'currency_id': 2,
            'reconcile': True,
            'user_type': 7,
        })
        purchase_journal_id = self.pool.get('account.journal').create(cr, uid, {
            'code': 'M2J1', 
            'currency': 2,
            'type': 'bank',
            'default_credit_account_id': purchase_account_id,
            'default_debit_account_id': purchase_account_id,
            'name': 'MSF Bank journal UCF3',
            'view_id': 1,
        })
        invoice_id = self.pool.get('account.invoice').create(cr, uid, {
            'type': 'in_invoice',
            'journal_id': purchase_journal_id,
            'partner_id': supplier_S2_id,
            'address_invoice_id': 1, # TODO get supplier res.partner.address
            'account_id': purchase_account_id2, # TODO get supplier account.account
            'check_total': 2000.0, # shortcut
        })
        invoice_line_id = self.pool.get('account.invoice.line').create(cr, uid, {
            'name': 'test_invoice_line_S2',
            'invoice_id': invoice_id,
            'account_id': purchase_account_id2, # TODO get appropriate account
            'price_unit': 1000.0,
            'quantity': 2,
        })
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)
        return True

    def register_invoice_payment_ucf3_u(self, cr, uid, context=None):
        if not context:
            context = {}
        creditors_account_id = self.pool.get('account.account').create(cr, uid, {
            'code': "M2CR", 
            "name": "Creditors", 
            "type": "other",
            'currency_id': 2,
            'reconcile': True,
            'user_type': 7,
        })
        bank_account_id = self.pool.get('account.account').create(cr, uid, {
            'code': "M2BK", 
            "name": "MSF Bank Account 1 UCF3", 
            "type": "other",
            'currency_id': 2,
            'user_type': 7,
        })
        journal_id = self.pool.get('account.journal').create(cr, uid, {
            'code': 'M2JN', 
            'currency': 2,
            'type': 'bank',
            'default_credit_account_id': bank_account_id,
            'default_debit_account_id': bank_account_id,
            'name': 'MSF Bank Journal UCF3',
            'view_id': 1,
        })
        
        st_id = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'REG1M2JN')], context=None)
        if not st_id:
            return False
        self.pool.get('account.bank.statement').button_open(cr, uid, st_id, context=context)
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "statement_id": st_id[0],
            "name":  "Move 29",
            "type": "general",
            "account_id": creditors_account_id,
            "amount": 2000.0,
        })
        return True

    def check_final_data_ucf3_u(self, cr, uid, context=None):
        if not context:
            context = {}
        supplier_S2_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', 'msf_supplier_UCF3')])
        if supplier_S2_ids:
            supplier_S2_id = supplier_S2_ids[0]
            invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('partner_id', '=', supplier_S2_id), ('check_total', '=', 2000)])
            return len(invoice_ids)
        return False
test()

