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

def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context={}):
    """
    Get "Third Parties" following other fields
    """
    res = {}
    for st_line in self.browse(cr, uid, ids, context=context):
        if st_line.employee_id:
            res[st_line.id] = {'third_parties': 'hr.employee,%s' % st_line.employee_id.id}
            res[st_line.id]['partner_type'] = {'options': [('hr.employee', 'Employee')], 'selection': 'hr.employee,%s' % st_line.employee_id.id}
        elif st_line.register_id:
            res[st_line.id] = {'third_parties': 'account.bank.statement,%s' % st_line.register_id.id}
            res[st_line.id]['partner_type'] = {'options': [('account.bank.statement', 'Register')], 
                'selection': 'account.bank.statement,%s' % st_line.register_id.id}
        elif st_line.partner_id:
            res[st_line.id] = {'third_parties': 'res.partner,%s' % st_line.partner_id.id}
            res[st_line.id]['partner_type'] = {'options': [('res.partner', 'Partner')], 'selection': 'res.partner,%s' % st_line.partner_id.id}
        else:
            res[st_line.id] = {'third_parties': False}
            if st_line.account_id:
                # Prepare some values
                acc_obj = self.pool.get('account.account')
                third_type = [('res.partner', 'Partner')]
                third_selection = 'res.partner,'
                acc_type = st_line.account_id.type_for_register
                if acc_type == 'transfer':
                    third_type = [('account.bank.statement', 'Register')]
                    third_selection = 'account.bank.statement,'
                elif acc_type == 'advance':
                    third_type = [('hr.employee', 'Employee')]
                    third_selection = 'hr.employee,'
                res[st_line.id]['partner_type'] = {'options': third_type, 'selection': third_selection}
    return res

def _set_third_parties(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context={}):
    """
    Set some fields in function of "Third Parties" field
    """
    if name and value:
        fields = value.split(",")
        element = fields[0]
        sql = "UPDATE %s SET " % self._table
        if element == 'hr.employee':
            obj = 'employee_id'
        elif element == 'account.bank.statement':
            obj = 'register_id'
        elif element == 'res.partner':
            obj = 'partner_id'
        if obj:
            sql += "%s = %s " % (obj, fields[1])
            sql += "WHERE id = %s" % id
            cr.execute(sql)
    return True

def open_register_view(self, cr, uid, register_id, context={}): 
    """
    Return the necessary object in order to return on the register we come from
    """
    st_type = self.pool.get('account.bank.statement').browse(cr, uid, register_id).journal_id.type
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
    result['res_id'] = register_id
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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
