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
        elif st_line.transfer_journal_id:
            res[st_line.id] = {'third_parties': 'account.journal,%s' % st_line.transfer_journal_id.id}
            res[st_line.id]['partner_type'] = {'options': [('account.journal', 'Journal')], 
                'selection': 'account.journal,%s' % st_line.transfer_journal_id.id}
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
                if acc_type in ['transfer', 'transfer_same']:
                    third_type = [('account.journal', 'Journal')]
                    third_selection = 'account.journal,'
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
        obj = False
        if element == 'hr.employee':
            obj = 'employee_id'
        elif element == 'account.bank.statement':
            obj = 'register_id'
        elif element == 'res.partner':
            obj = 'partner_id'
        elif element == 'account.journal':
            obj = 'transfer_journal_id'
        if obj:
            sql += "%s = %s " % (obj, fields[1])
            sql += "WHERE id = %s" % id
            if self._table == 'wizard_journal_items_corrections_lines':
                self.pool.get('wizard.journal.items.corrections.lines').write(cr, uid, [id], {obj: int(fields[1])}, context=context)
                return True
            cr.execute(sql)
    return True

def _get_third_parties_name(self, cr, uid, vals, context={}):
    """
    Get third parties name from vals that could contain:
     - partner_type: displayed as "object,id"
     - partner_id: the id of res.partner
     - register_id: the id of account.bank.statement
     - employee_id: the id of hr.employee
    """
    # Prepare some values
    res = ''
    # Some verifications
    if not context:
        context = {}
    if not vals:
        return res
    if 'partner_type' in vals and vals.get('partner_type', False):
        a = vals.get('partner_type').split(',')
        if len(a) and len(a) > 1:
            b = self.pool.get(a[0]).browse(cr, uid, [int(a[1])], context=context)
            res = b and b[0] and b[0].name or ''
            return res
    if 'partner_id' in vals and vals.get('partner_id', False):
        partner = self.pool.get('res.partner').browse(cr, uid, [vals.get('partner_id')], context=context)
        res = partner and partner[0] and partner[0].name or ''
    if 'employee_id' in vals and vals.get('employee_id', False):
        employee = self.pool.get('hr.employee').browse(cr, uid, [vals.get('employee_id')], context=context)
        res = employee and employee[0] and employee[0].name or ''
    if 'register_id' in vals and vals.get('register_id', False):
        register = self.pool.get('account.bank.statement').browse(cr, uid, [vals.get('register_id')], context=context)
        res = register and register[0] and register[0].name or ''
    if 'journal_id' in vals and vals.get('journal_id', False):
        journal = self.pool.get('account.journal').browse(cr, uid, [vals['journal_id']], context=context)
        res = journal and journal[0] and journal[0].code or ''
    return res

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

def previous_period_id(self, cr, uid, period_id, context={}):
    """
    Give previous period of those given
    """
    # Some verifications
    if not context:
        context = {}
    if not period_id:
        raise osv.except_osv(_('Error'), _('No period given.'))
    # Prepare some values
    p_obj = self.pool.get('account.period')
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
    if previous_period_ids:
        return previous_period_ids[0]
    return False

def previous_register_id(self, cr, uid, period_id, journal_id, context={}):
    """
    Give the previous register id regarding some criteria:
     - period_id: the period of current register
     - journal_id: this include same currency and same type
     - fiscalyear_id: current fiscalyear
    """
    # TIP - Use this postgresql query to verify current registers:
    # select s.id, s.state, s.journal_id, j.type, s.period_id, s.name, c.name 
    # from account_bank_statement as s, account_journal as j, res_currency as c 
    # where s.journal_id = j.id and j.currency = c.id;

    # Prepare some values
    st_obj = self.pool.get('account.bank.statement')
    prev_period_id = False
    # Search journal_ids that have the type we search
    prev_period_id = previous_period_id(self, cr, uid, period_id, context=context)
    previous_reg_ids = st_obj.search(cr, uid, [('journal_id', '=', journal_id), ('period_id', '=', prev_period_id)], context=context)
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

def totally_or_partial_reconciled(self, cr, uid, ids, context={}):
    """
    Verify that all given statement lines are totally or partially reconciled.
    To conclue first a statement line is reconciled these lines should be hard-posted.
    Then move_lines that come from this statement lines should have all reconciled account with a reconciled_id or a reconcile_partial_id.
    If ONE account_move_line is not reconciled totally or partially, the function return False
    """
    # Verifications
    if not context:
        context={}
    if isinstance(ids, (int, long)):
        ids = [ids]
    # Prepare some variables
    absl_obj = self.pool.get('account.bank.statement.line')
    aml_obj = self.pool.get('account.move.line')
    # Process lines
    for absl in absl_obj.browse(cr, uid, ids, context=context):
        for move in absl.move_ids:
            aml_ids = aml_obj.search(cr, uid, [('move_id', '=', move.id)])
            for aml in aml_obj.browse(cr, uid, aml_ids, context=context):
                if aml.account_id.reconcile and not (aml.reconcile_id or aml.reconcile_partial_id):
                    return False
    return True

def create_cashbox_lines(self, cr, uid, register_ids, ending=False, context={}):
    """
    Create account_cashbox_lines from the current registers (register_ids) to the next register (to be defined)
    """
    if isinstance(register_ids, (int, long)):
        register_ids = [register_ids]
    st_obj = self.pool.get('account.bank.statement')
    for st in st_obj.browse(cr, uid, register_ids, context=context):
        # Some verification
        # Verify that the register is a cash register
        if not st.journal_id.type == 'cash':
            continue
        # Verify that another Cash Register exists
        next_reg_ids = st_obj.search(cr, uid, [('prev_reg_id', '=', st.id)], context=context)
        if not next_reg_ids:
            return False
        next_reg_id = next_reg_ids[0]
        # if yes, put in the closing balance in opening balance
        if next_reg_id:
            cashbox_line_obj = self.pool.get('account.cashbox.line')
            # Search lines from current register ending balance
            cashbox_lines_ids = cashbox_line_obj.search(cr, uid, [('ending_id', '=', st.id)], context=context)
            # Unlink all previously cashbox lines for the next register
            elements = ['starting_id']
            # Add ending_id if demand
            if ending:
                elements.append('ending_id')
            for el in elements:
                old_cashbox_lines_ids = cashbox_line_obj.search(cr, uid, [(el, '=', next_reg_id)], context=context)
                cashbox_line_obj.unlink(cr, uid, old_cashbox_lines_ids, context=context)
                for line in cashbox_line_obj.browse(cr, uid, cashbox_lines_ids, context=context):
                    starting_vals = {
                        el: next_reg_id,
                        'pieces': line.pieces,
                        'number': line.number,
                    }
                    if el == 'ending_id':
                        starting_vals.update({'number': 0.0,})
                    cashbox_line_obj.create(cr, uid, starting_vals, context=context)
            # update new register balance_end
            balance = st_obj._get_starting_balance(cr, uid, [next_reg_id], context=context)[next_reg_id].get('balance_start', False)
            if balance:
                st_obj.write(cr, uid, [next_reg_id], {'balance_start': balance}, context=context)
    return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
