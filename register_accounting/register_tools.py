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
from tools.translate import _

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

def _get_date_in_period(self, cr, uid, date=None, period_id=None, context={}):
    """
    Permit to return a date included in period :
     - if given date is included in period, return the given date
     - else return the date_stop of given period
    """
    if not context:
        context={}
    if not date or not period_id:
        return False
    period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
    if date < period.date_start or date > period.date_stop:
        return period.date_stop
    return date

def previous_register_id(self, cr, uid, period_id, currency_id, register_type, context={}):
    """
    Give the previous register id regarding some criteria:
     - period_id: the period of current register
     - currency_id: currency of the current register
     - register_type: type of register
     - fiscalyear_id: current fiscalyear
    """
    # TIP - Use this postgresql query to verify current registers:
    # select s.id, s.state, s.journal_id, j.type, s.period_id, s.name, c.name 
    # from account_bank_statement as s, account_journal as j, res_currency as c 
    # where s.journal_id = j.id and j.currency = c.id;

    # Prepare some values
    p_obj = self.pool.get('account.period')
    j_obj = self.pool.get('account.journal')
    st_obj = self.pool.get('account.bank.statement')
    # Search period and previous one
    period = p_obj.browse(cr, uid, [period_id], context=context)[0]
    first_period_id = p_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id)], order='date_start', limit=1, context=context)[0]
    previous_period_ids = p_obj.search(cr, uid, [('date_start', '<', period.date_start), ('fiscalyear_id', '=', period.fiscalyear_id.id)], 
        order='date_start desc', limit=1, context=context)
    if period_id == first_period_id: 
        # if the current period is the first period of fiscalyear we have to search the last period of previous fiscalyear
        previous_fiscalyear = self.pool.get('account.fiscalyear').search(cr, uid, [('date_start', '<', period.fiscalyear_id.date_start)], 
            limit=1, order="date_start desc", context=context)
        if not previous_fiscalyear:
            raise osv.except_osv(_('Error'), 
                _('No previous fiscalyear found. Is your period the first one of a fiscalyear that have no previous fiscalyear ?'))
        previous_period_ids = p_obj.search(cr, uid, [('fiscalyear_id', '=', previous_fiscalyear[0])], 
            limit=1, order='date_stop desc, name desc') # this work only for msf because of the last period name which is "Period 13", "Period 14" 
            # and "Period 15"
    # Search journal_ids that have the type we search
    journal_ids = j_obj.search(cr, uid, [('currency', '=', currency_id), ('type', '=', register_type)], context=context)
    previous_reg_ids = st_obj.search(cr, uid, [('journal_id', 'in', journal_ids), ('period_id', '=', previous_period_ids[0])], context=context)
    if len(previous_reg_ids) != 1:
        return False
    return previous_reg_ids[0]

def previous_register_is_closed(self, cr, uid, ids, context={}):
    """
    Return true if previous register is closed. Otherwise return an exception
    """
    if not context:
        context={}
    if isinstance(ids, (int, long)):
        ids = [ids]
    # Verify that the previous register is closed
    for reg in self.pool.get('account.bank.statement').browse(cr, uid, ids, context=context):
        # if no previous register (case where register is the first register) we don't need to close unexistent register
        if reg.prev_reg_id:
            if reg.prev_reg_id.state not in ['partial_close', 'confirm']:
                raise osv.except_osv(_('Error'), 
                    _('The previous register "%s" for period "%s" has not been closed properly.') % 
                        (reg.prev_reg_id.name, reg.prev_reg_id.period_id.name))
    return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
