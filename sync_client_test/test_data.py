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

import netsvc

class test(osv.osv_memory):
    _name = "sync.client.test"
    
    
    def set_connection(self, cr, uid, name, server_db, host, port, password, max_size, context=None):
        """
            Set the connection to the server
        """
        con_obj = self.pool.get('sync.client.sync_server_connection')
        con = con_obj._get_connection_manager(cr, uid, context=None)
        con_obj.write(cr, uid, con.id, {'login' : name,
                                    'host' : host,
                                    'database' : server_db,
                                    'port' : port,
                                    'login' : name,
                                    'password' : password,
                                    'max_size' : max_size})
        con_obj.connect(cr, uid, [con.id], None)
        con = con_obj._get_connection_manager(cr, uid, context=None)
        return con.uid
    
    def activate(self, cr, uid, name, context=None):
        activate_obj = self.pool.get('sync.client.activate_entity')
        res_id = activate_obj.create(cr, uid, {'name' : name}, context=context)
        activate_obj.activate(cr, uid, [res_id], context=context)
        return self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).parent
    
    def register(self, cr, uid, name, parent_name, email, group_name_list, context=None):
        re_obj = self.pool.get('sync.client.register_entity')
        group_ids = []
        for gname in group_name_list:
            id_res = self.pool.get('sync.client.entity_group').create(cr, uid,  {'name' : gname}, context=context)
            group_ids.append(id_res)
        parent_id = self.pool.get('sync_client.instance.temp').create(cr, uid, {'name' : parent_name}, context=context) 
        res_id = re_obj.create(cr, uid, {'name' : name, 
                                         'email' : email,
                                         'parent_id' : parent_id,
                                         'group_ids' : [(6, 0, group_ids)]}, context=context)
        re_obj.validate(cr, uid, [res_id], context=context)
        return True
    
    def activate_by_parent(self, cr, uid, child_name, context=None):
        #create wizard
        em_obj = self.pool.get("sync.client.entity_manager")
        res_id = em_obj.create(cr, uid, {'state' : 'data_needed'}, context=context)
        #retrieve info 
        em_obj.retrieve(cr, uid, [res_id], context=context)
        #check for child exist and validate
        wiz = em_obj.browse(cr, uid, res_id, context=context)
        for entity in wiz.entity_ids:
            if entity.name == child_name:
                return self.pool.get("sync.client.child_entity").validation(cr, uid, [entity.id], context=context)
        return False
       
    def synchronize(self, cr, uid, context=None): 
        self.pool.get('sync.client.entity').sync(cr, uid, context=context)
        return True
    
    def check_model_info(self, cr, uid, model, data, context=None):
        if not context:
            context = {}
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data.get('name'))], context=context)
        if not ids:
            return False
        
        for partner in self.pool.get(model).browse(cr, uid, ids, context=context):
            for key, value in data.items():
                if not getattr(partner, key) == value:
                    return False
        return True
    
    def check_model_info_like(self, cr, uid, model, data, context=None):
        """
            check for all object with name like, if one of the data is the same in one object
        """
        if not context:
            context = {}
        ids = self.pool.get(model).search(cr, uid, [('name', 'like', data.get('name'))], context=context)
        if not ids:
            return False
        for partner in self.pool.get(model).browse(cr, uid, ids, context=context):
            res = True
            for key, value in data.items():
                if key != 'name' and not getattr(partner, key) == value:
                    res = False
            if res:
                return True
        return False
    
    
    def create_record(self, cr, uid, model, data, context=None):
        if not context:
            context = {}
        res_id = self.pool.get(model).create(cr, uid, data, context=context)
        return res_id
    
    def write_record(self, cr, uid, model, data, context=None):
        if not context:
            context = {}
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data.get('name'))], context=context)
        if not ids:
            return False
        self.pool.get(model).write(cr, uid, ids, data)
        return True
    
    def get_record_id(self, cr, uid, model, data, context=None):
        if not context:
            context = {}
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data)], context=context)
        return ids and ids[0] or False

    def delete_record(self, cr, uid, model, name, context=None):
        if not context:
            context = {}
        ids = self.pool.get(model).search(cr, uid, [('name', '=', name)], context=context)
        if not ids:
            return False
        self.pool.get(model).unlink(cr, uid, ids, context=context)
        return True
        
    def get_record_data(self, cr, uid, model, id, fields, context=None):
        if not context:
            context = {}
        return self.pool.get(model).read(cr, uid, id, fields, context=context)
    
    def confirm_so(self, cr, uid, ref, context=None):
        ids = self.pool.get('sale.order').search(cr, uid, [('client_order_ref', '=', ref)])
        if not ids:
            return False
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, "sale.order", ids[0], 'order_confirm', cr)
        return True
    
    def _confirm_ship(self, cr, uid, ship_ids, context=None):
        self.pool.get('stock.picking').force_assign(cr, uid, ship_ids)
        res = self.pool.get('stock.picking').action_process(cr, uid, ship_ids, context=context)
        partial_id = res['res_id']
        model = res['res_model']
        context = res['context']
        self.pool.get(model).do_partial(cr, uid, [partial_id], context=context)
    
    def confirm_shippements(self, cr, uid, ref, context=None):
        ids = self.pool.get('sale.order').search(cr, uid, [('client_order_ref', '=', ref)])
        if not ids:
            print 'No sale order'
            return False
        for so in self.pool.get('sale.order').browse(cr, uid, ids):
            ship_ids = [ship.id for ship in so.picking_ids]
            self._confirm_ship(cr, uid, ship_ids, context)
        return True
    
    def confirm_incoming_shippements(self, cr, uid, name, context=None):
        ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', '=', name)])
        if not ids:
            return False
        self._confirm_ship(cr, uid, ids, context)
        return True
        
    def exec_wkf(self, cr, uid, model, transition_name, id=0, name=None):
        if not id and not name:
            return False
        if not id:
            ids = self.pool.get(model).search(cr, uid, [('name', '=', name)])
            if ids:
                id = ids[0]
            else: 
                return False
        
        
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, model, id, transition_name, cr)
        
    def create_data_ucf1(self, cr, uid, context=None):
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
        st_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2_UCF1_CASH_REGISTER",
                                                                         'journal_id' : j_id, 
                                                                         'date' : "2011-08-29",
                                                                         }, context=None)
        self.pool.get('account.bank.statement').button_open(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 1",
                                                                      "type" : "general",
                                                                      "account_id": res_id,
                                                                      "amount" : 40.0 }, context=context)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 2",
                                                                      "type" : "general",
                                                                      "account_id": res_id,
                                                                      "amount" : 30.0 }, context=context)
        return True
        
    def modify_data_ucf1(self, cr, uid, context=None):
        account_ids = self.pool.get('account.account').search(cr, uid, [('name', '=', 'MSF Cash Account 2 UCF1')], context=context)
        st_ids = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', 'M2_UCF1_CASH_REGISTER')], context=context)
        line_ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('name', '=', 'Move 2')], context=context)
        j_ids = self.pool.get('account.journal').search(cr, uid, [('name', '=', 'MSF Cash Journal UCF1')], context=context)
        if not account_ids or not st_ids or not line_ids or not j_ids:
            return False
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-30",
                                                                      "statement_id" : st_ids[0],
                                                                      "name" : "Move 3",
                                                                      "type" : "general",
                                                                      "account_id": account_ids[0],
                                                                      "amount" : 25.0 }, context=context)
        self.pool.get('account.bank.statement.line').write(cr, uid, line_ids, {'account_id' : account_ids[0]}, context=context)
        return True
    
    def check_final_data_ucf1(self, cr, uid, context=None):
        if not context:
            context = {}
        ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('account_id', '=', 'MSF Cash Account 2 UCF1')], context=None)
        return len(ids) == 2
    
    def create_data_ucf2(self, cr, uid, context=None):
        if not context:
            context = {}
        a1_id = self.pool.get('account.account').create(cr, uid, {'code' : "M23", 
                                                          "name" : "MSF Bank Account 1 UCF2", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'user_type' : 15 }, context=None)
        a2_id = self.pool.get('account.account').create(cr, uid, {'code' : "M24", 
                                                          "name" : "MSF Transfert Account 1 UCF2", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'reconcile' : True,
                                                          'user_type' : 15 }, context=None)
        
        a3_id = self.pool.get('account.account').create(cr, uid, {'code' : "M25", 
                                                          "name" : "MSF Cash Account 3 UCF2", 
                                                          "type" : "liquidity",
                                                          'currency_id' : 2,
                                                          'user_type' : 11 }, context=None)
        
        j1_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M21', 
                                                          'currency' : 2,
                                                          'type' : 'bank',
                                                          'default_credit_account_id' : a1_id,
                                                          'default_debit_account_id' : a1_id,
                                                          'name' : 'MSF Bank journal UCF2',
                                                          'view_id' : 1}, context=None)

        j3_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M23', 
                                                          'currency' : 2,
                                                          'type' : 'cash',
                                                          'default_credit_account_id' : a3_id,
                                                          'default_debit_account_id' : a3_id,
                                                          'name' : 'MSF Cash Journal UCF2',
                                                          'view_id' : 1}, context=None)
        st_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2 Bank statement UCF2",
                                                                         'journal_id' : j1_id, 
                                                                         'date' : "2011-08-29",
                                                                         'balance_end_real' : -2000.0,
                                                                         }, context=None)
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 21",
                                                                      "type" : "general",
                                                                      "account_id": a2_id,
                                                                      "amount" : -2000.0 }, context=context)
        
        self.pool.get('account.bank.statement').button_dummy(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement').button_confirm_bank(cr, uid, [st_id], context=context)
       
        return True
    
    def create_cash_statement_ufc2(self, cr, uid, context=None):
        if not context:
            context = {}
        j_ids = self.pool.get('account.journal').search(cr, uid, [('name', '=', 'MSF Cash Journal UCF2')], context=context)
        account_ids = self.pool.get('account.account').search(cr, uid, [('name', '=', 'MSF Transfert Account 1 UCF2')], context=context)
        print j_ids, account_ids
        if not j_ids or not account_ids:
            return False
        st_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2 Bank statement UCF2",
                                                                         'journal_id' : j_ids[0], 
                                                                         'date' : "2011-08-29",
                                                                         }, context=None)
        self.pool.get('account.bank.statement').button_open(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 22",
                                                                      "type" : "general",
                                                                      "account_id": account_ids[0],
                                                                      "amount" : 2000.0 }, context=context)
        res_id = self.pool.get('account.cashbox.line').create(cr, uid, {"pieces" : 100.0,
                                                                      "number" : 20,
                                                                      "ending_id" : st_id}, context=context)
        self.pool.get('account.bank.statement').button_dummy(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement').button_confirm_cash(cr, uid, [st_id], context=context)
        return True
        
    def reconcile_ucf2(self, cr, uid, context=None):
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

    def init_data_ucf3(self, cr, uid, context=None):
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
            'user_type': 15,
        })
        
        purchase_account_id2 = self.pool.get('account.account').create(cr, uid, {
            'code': "M2PP", 
            "name": "MSF Suppliers", 
            "type": "payable",
            'currency_id': 2,
            'reconcile': True,
            'user_type': 15,
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

    def register_invoice_payment_ucf3(self, cr, uid, context=None):
        if not context:
            context = {}
        creditors_account_id = self.pool.get('account.account').create(cr, uid, {
            'code': "M2CR", 
            "name": "Creditors", 
            "type": "other",
            'currency_id': 2,
            'reconcile': True,
            'user_type': 15,
        })
        bank_account_id = self.pool.get('account.account').create(cr, uid, {
            'code': "M2BK", 
            "name": "MSF Bank Account 1 UCF3", 
            "type": "other",
            'currency_id': 2,
            'user_type': 15,
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
        statement_id = self.pool.get('account.bank.statement').create(cr, uid, {
            'name': "Invoice S2 Bank statement UCF3",
            'journal_id': journal_id, 
            'date': "2011-08-29",
            'balance_end_real': 2000.0,
        })
        self.pool.get('account.bank.statement.line').create(cr, uid, {
            "date": "2011-08-29",
            "statement_id": statement_id,
            "name":  "Move 21",
            "type": "general",
            "account_id": creditors_account_id,
            "amount": 2000.0,
        })
        return True

    def check_final_data_ucf3(self, cr, uid, context=None):
        if not context:
            context = {}
        supplier_S2_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', 'msf_supplier_UCF3')])
        if supplier_S2_ids:
            supplier_S2_id = supplier_S2_ids[0]
            invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('partner_id', '=', supplier_S2_id), ('check_total', '=', 2000)])
            return len(invoice_ids)
        return False

    def create_data_ucf4(self, cr, uid, context=None):
        if not context:
            context = {}
    
        a1_id = self.pool.get('account.analytic.account').create(cr, uid, {"name" : 'Analytic Account MSF 1',
                                                                   "code" :  'M2A1',
                                                                   "currency_id" : 2}, context=context)
        a2_id = self.pool.get('account.analytic.account').create(cr, uid, {"name" : 'Analytic Account MSF 2',
                                                                   "code" :  'M2A2',
                                                                   "currency_id" : 2}, context=context)
        j1_id = self.pool.get('account.analytic.journal').create(cr, uid, {"code" : 'M2J1', 
                                                                           'name' : 'MSF Analytic Journal 1',
                                                                           'type' : 'general'}, context=context)
        """
        j2_id = self.pool.get('account.analytic.journal').create(cr, uid, {"code" : 'M2J2', 
                                                                           'name' : 'MSF Analytic Journal 2',
                                                                           'type' : 'general'}, context=context)
        """
        
        p1_id = self.pool.get('account.analytic.plan').create(cr, uid, {"name" : "M2 Analytic Plan"}, context=context)
        
        i1_id = self.pool.get('account.analytic.plan.instance').create(cr, uid, {"name" : "M2 Analytic Distribution 50 - 50", 
                                                                                 "code" : "M2D1",
                                                                                 "plan_id" : p1_id}, context=context)
        il1_id = self.pool.get('account.analytic.plan.instance.line').create(cr, uid, {'plan_id' : i1_id,
                                                                                      'rate' : 50.00,
                                                                                      'analytic_account_id' : a1_id}, context=context)
        
        il2_id = self.pool.get('account.analytic.plan.instance.line').create(cr, uid, {'plan_id' : i1_id,
                                                                                      'rate' : 50.00,
                                                                                      'analytic_account_id' : a2_id}, context=context)
        
        fa1_id = self.pool.get('account.account').create(cr, uid, {'code' : "M214", 
                                                          "name" : "MSF Bank Account 10 UCF4", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'user_type' : 15 }, context=None)
        
        fa2_id = self.pool.get('account.account').create(cr, uid, {'code' : "M215", 
                                                          "name" : "MSF Bank Account 11 UCF4", 
                                                          "type" : "other",
                                                          'currency_id' : 2,
                                                          'user_type' : 15 }, context=None)
        fj1_id = self.pool.get('account.journal').create(cr, uid, {'code' : 'M214', 
                                                          'currency' : 2,
                                                          'type' : 'bank',
                                                          'default_credit_account_id' : fa1_id,
                                                          'default_debit_account_id' : fa1_id,
                                                          'name' : 'MSF Bank journal UCF4',
                                                          'view_id' : 1,
                                                          'analytic_journal_id' : j1_id}, context=None)
        
        st_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2 Bank statement UCF4",
                                                                         'journal_id' : fj1_id, 
                                                                         'date' : "2011-08-29",
                                                                         'balance_end_real' : 2000.0,
                                                                         }, context=None)
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 41",
                                                                      "type" : "general",
                                                                      "account_id": fa2_id,
                                                                      'analytics_id' : i1_id,
                                                                      "amount" : 2000.0 }, context=context)
        self.pool.get('account.bank.statement').button_dummy(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement').button_confirm_bank(cr, uid, [st_id], context=context)
        
        return True
    
    def change_distribution_ucf4(self, cr, uid, context=None):
        if not context:
            context = {}
        a_ids = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'M2A1')], context=context)
        fj_ids = self.pool.get('account.journal').search(cr, uid, [('name', '=', 'MSF Bank journal UCF4')], context=context)
        i_ids = self.pool.get('account.analytic.plan.instance').search(cr, uid, [("name", '=', "M2 Analytic Distribution 50 - 50")], context=context)
        fa_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', "M215")], context=None)
        if not fj_ids or not i_ids or not fa_ids or not a_ids:
            return False
        
        a1_id = a_ids[0]
        fj1_id = fj_ids[0]
        i1_id = i_ids[0]
        fa2_id = fa_ids[0]
        st_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2 Bank statement UCF4 revert",
                                                                         'journal_id' : fj1_id, 
                                                                         'date' : "2011-08-29",
                                                                         'balance_end_real' : -2000.0,
                                                                         }, context=None)
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st_id,
                                                                      "name" : "Move 41",
                                                                      "type" : "general",
                                                                      "account_id": fa2_id,
                                                                      'analytics_id' : i1_id,
                                                                      "amount" : -2000.0 }, context=context)
        self.pool.get('account.bank.statement').button_dummy(cr, uid, [st_id], context=context)
        self.pool.get('account.bank.statement').button_confirm_bank(cr, uid, [st_id], context=context)
        
        p1_id = self.pool.get('account.analytic.plan').create(cr, uid, {"name" : "M2 Analytic Plan 2"}, context=context)
        
        i2_id = self.pool.get('account.analytic.plan.instance').create(cr, uid, {"name" : "M2 Analytic Distribution 100", 
                                                                                 "code" : "M2D2",
                                                                                 "plan_id" : p1_id}, context=context)
        self.pool.get('account.analytic.plan.instance.line').create(cr, uid, {'plan_id' : i2_id,
                                                                                      'rate' : 100.00,
                                                                                      'analytic_account_id' : a1_id}, context=context)
        st2_id = self.pool.get('account.bank.statement').create(cr, uid, {'name' : "M2 Bank statement UCF4 Correction",
                                                                         'journal_id' : fj1_id, 
                                                                         'date' : "2011-08-29",
                                                                         'balance_end_real' : 2000.0,
                                                                         }, context=None)
        
        self.pool.get('account.bank.statement.line').create(cr, uid, {"date" : "2011-08-29",
                                                                      "statement_id" : st2_id,
                                                                      "name" : "Move 41",
                                                                      "type" : "general",
                                                                      "account_id": fa2_id,
                                                                      'analytics_id' : i2_id,
                                                                      "amount" : 2000.0 }, context=context)
        
        self.pool.get('account.bank.statement').button_dummy(cr, uid, [st2_id], context=context)
        self.pool.get('account.bank.statement').button_confirm_bank(cr, uid, [st2_id], context=context)
        return True
    
    #check que a1 a 2000 de balance et a2 a 1000
        
test()

