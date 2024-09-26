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

def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context=None):
    """
    Get "Third Parties" following other fields
    """
    res = {}
    for st_line in self.browse(cr, uid, ids, context=context):
        if st_line.employee_id:
            res[st_line.id] = {'third_parties': 'hr.employee,%s' % st_line.employee_id.id}
            res[st_line.id]['partner_type'] = {'options': [('hr.employee', 'Employee')], 'selection': 'hr.employee,%s' % st_line.employee_id.id}
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
                third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
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

def _set_third_parties(self, cr, uid, obj_id, name=None, value=None, fnct_inv_arg=None, context=None):
    """
    Set some fields in function of "Third Parties" field
    """
    if name:
        element = False
        if value:
            fields = value.split(",")
            element = fields[0]
        sql = "UPDATE %s SET " % self._table  # not_a_user_entry
        emp_val = 'Null'
        par_val = 'Null'
        tra_val = 'Null'
        if element == 'hr.employee':
            emp_val = fields[1] or 'Null'
        elif element == 'res.partner':
            par_val = fields[1] or 'Null'
        elif element == 'account.journal':
            tra_val = fields[1] or 'Null'
        sql += "employee_id = %s, partner_id = %s, transfer_journal_id = %s " % (emp_val, par_val, tra_val)
        sql += "WHERE id = %s" % obj_id
        cr.execute(sql)
    # Delete values for Third Parties if no value given
    elif name == 'partner_type' and not value:
        cr.execute("UPDATE %s SET employee_id = Null, partner_id = Null, transfer_journal_id = Null WHERE id = %%s" % self._table, (obj_id,))  # not_a_user_entry
    return True


def _populate_third_party_name(self, cr, uid, obj_id, field_name, name=None, context=None):
    """
    Populate changes to move line and analytic line when the employee or partner name got changed
    field_name must be 'employee_id' or partner_id (field of account_bank_statement_line)
    """
    absl_obj = self.pool.get('account.bank.statement.line')
    aml_obj = self.pool.get('account.move.line')
    aal_obj = self.pool.get('account.analytic.line')

    # search all register lines that linked to this employee/partner
    domain = [
        (field_name, '=', obj_id),
        # FIX of BKLG-80: only temp posted
        # http://jira.unifield.org/browse/BKLG-80?focusedCommentId=39205&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-39205
        ('state', '=', 'temp'),
    ]

    absl_ids = absl_obj.search(cr, uid, domain, context=context)
    for absl in absl_ids:
        # search for the account.move.line that linked to the given
        je_ids = absl_obj._get_move_ids(cr, uid, [absl], context=context)
        domain = [
            ('move_id', 'in', je_ids),
            # just in case of posted JIs returned by _get_move_ids
            ('move_id.state', '=', 'draft'),
            # only records with previous name
            ('partner_txt', '!=', name),
        ]
        aml_ids = aml_obj.search(cr, uid, domain, context=context)

        if aml_ids:
            # register_line to update the partner_txt field
            # (using write to send sync messages)
            aml_obj.write(cr, uid, aml_ids, {'partner_txt': name},
                          context=context)

            # get reg line AJIs
            domain = [
                ('account_id.category', 'in', ('FUNDING', 'FREE1', 'FREE2')),
                ('move_id', 'in', aml_ids),
            ]
            aal_ids = aal_obj.search(cr, uid, domain, context=context)

            if aal_ids:
                """
                perform changes to regline JIs AJIs,
                a bit tricky, it must be done with sql,
                otherwise it will use always the "previous" value
                NOTE: pay attention that the write of move line deleted the
                current analytic line then recreates new analytic lines!
                """
                sql = "UPDATE account_analytic_line SET partner_txt = %s" \
                    " WHERE id in %s"
                cr.execute(sql, (name, tuple(aal_ids), ))
    return True

def _get_third_parties_name(self, cr, uid, vals, context=None):
    """
    Get third parties name from vals that could contain:
     - partner_type: displayed as "object,id"
     - partner_id: the id of res.partner
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
            if a[0] == "account.journal":
                res = b and b[0] and b[0].code or ''
            return res
    if 'partner_id' in vals and vals.get('partner_id', False):
        partner = self.pool.get('res.partner').browse(cr, uid, [vals.get('partner_id')], context=context)
        res = partner and partner[0] and partner[0].name or ''
    if 'employee_id' in vals and vals.get('employee_id', False):
        employee = self.pool.get('hr.employee').browse(cr, uid, [vals.get('employee_id')], context=context)
        empl_name = []
        if employee and employee[0]:
            if employee[0].section_code:
                empl_name.append(employee[0].section_code)
            empl_name.append(employee[0].name or '')
        res = ' '.join(empl_name)
    if 'transfer_journal_id' in vals and vals.get('transfer_journal_id', False):
        journal = self.pool.get('account.journal').browse(cr, uid, [vals['transfer_journal_id']], context=context)
        res = journal and journal[0] and journal[0].code or ''
    return res

def open_register_view(self, cr, uid, register_id, context=None):
    """
    Return the necessary object in order to return on the register we come from
    """
    st_type = self.pool.get('account.bank.statement').browse(cr, uid, register_id).journal_id.type
    # Get act_window info
    result = self.pool.get('account.bank.statement').get_statement(cr, uid, [register_id], st_type=st_type, context=context)
    # Adapt it to our case
    result['res_id'] = register_id
    result['target'] = 'crush'
    result['view_mode'] = 'form,tree,graph'
    # Sort views by first letter (form, then tree). this permit to show form instead tree view
    result['views'] = sorted(result['views'], key=lambda x: x[1][0:1])
    # Take right ID to display form view
    for view in result['views']:
        if view[1] and view[1] == 'form':
            result['view_id'] = [view[0]]
    return result

def _get_date_in_period(self, cr, uid, date=None, period_id=None, context=None):
    """
    Permit to return a date included in period :
     - if given date is included in period, return the given date
     - else return the date_stop of given period
    """
    if not context:
        context = {}
    if not date or not period_id:
        return False
    period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
    if date < period.date_start or date > period.date_stop:
        return period.date_stop
    return date


def previous_period_id(self, cr, uid, period_id, context=None, raise_error=True):
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
    first_period_id = p_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id), ('number', '!=', 0)], order='date_start', limit=1, context=context)[0]
    previous_period_ids = p_obj.search(cr, uid, [('date_start', '<=', period.date_start), ('fiscalyear_id', '=', period.fiscalyear_id.id),
                                                 ('id', '!=', period_id), ('number', '<=', 12.0)], order='number desc', context=context)
    if period_id == first_period_id:
        # if the current period is the first period of fiscalyear we have to search the last period of previous fiscalyear
        previous_fiscalyear = self.pool.get('account.fiscalyear').search(cr, uid, [('date_start', '<', period.fiscalyear_id.date_start)],
                                                                         order="date_start desc", context=context)
        if not previous_fiscalyear:
            if raise_error:
                raise osv.except_osv(_('Error'),
                                     _('No previous fiscal year found. Is your period the first one of a fiscal year '
                                       'that has no previous fiscal year?'))
            else:
                return False
        previous_period_ids = p_obj.search(cr, uid, [('fiscalyear_id', '=', previous_fiscalyear[0]), ('id', '!=', period_id), ('number', '<=', 12.0)],
                                           order='number desc') # this work only for msf because of the last period name which is "Period 13", "Period 14"
        # and "Period 15"
    if previous_period_ids:
        return previous_period_ids[0]
    return False

def previous_register_id(self, cr, uid, period_id, journal_id, context=None, raise_error=True):
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
    # Search journal_ids that have the type we search
    prev_period_id = previous_period_id(self, cr, uid, period_id, context=context, raise_error=raise_error)
    if not prev_period_id:
        return False
    previous_reg_ids = st_obj.search(cr, uid, [('journal_id', '=', journal_id), ('period_id', '=', prev_period_id)], context=context)
    if len(previous_reg_ids) != 1:
        return False
    return previous_reg_ids[0]


def previous_register_instance_id(self, cr, uid, period_id, journal_id, context=None):
    """
    get instance_id for the previous register 
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
    # Search journal_ids that have the type we search
    prev_period_id = previous_period_id(self, cr, uid, period_id, context=context)
    previous_reg_ids = st_obj.search(cr, uid, [('journal_id', '=', journal_id), ('period_id', '=', prev_period_id)], context=context)
    prev_reg_browse = st_obj.browse(cr, uid, previous_reg_ids, context=context)

    if len(previous_reg_ids) != 1:
        return False
    instance_id = prev_reg_browse[0].instance_id.id
    return instance_id


def previous_register_is_closed(self, cr, uid, ids, context=None):
    """
    Return true if previous register is closed. Otherwise return an exception
    """
    if not context:
        context = {}
    if isinstance(ids, int):
        ids = [ids]
    # Verify that the previous register is closed
    for reg in self.pool.get('account.bank.statement').browse(cr, uid, ids, context=context):
        # if no previous register (case where register is the first register) we don't need to close non-existent registers
        if reg.prev_reg_id:
            if reg.prev_reg_id.state != 'confirm':
                raise osv.except_osv(_('Error'),
                                     _('The previous register "%s" for period "%s" has not been closed properly.') %
                                     (reg.prev_reg_id.name, reg.prev_reg_id.period_id.name))
    return True

def totally_or_partial_reconciled(self, cr, uid, ids, context=None):
    """
    Verify that all given statement lines are totally or partially reconciled.
    To conclue first a statement line is reconciled these lines should be hard-posted.
    Then move_lines that come from this statement lines should have all reconciled account with a reconciled_id or a reconcile_partial_id.
    If ONE account_move_line is not reconciled totally or partially, the function return False
    """
    # Verifications
    if not context:
        context = {}
    if isinstance(ids, int):
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

def create_cashbox_lines(self, cr, uid, register_ids, ending=False, context=None):
    """
    Create account_cashbox_lines from the current registers (register_ids) to the next register (to be defined)
    """
    if isinstance(register_ids, int):
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
                    # note: if ending is True, closing lines are created, but the check on duplicates is skipped as the reg. is in Draft state
                    cashbox_line_obj.create(cr, uid, starting_vals, context=context)
            # update new register balance_start
            balance = st_obj._get_starting_balance(cr, uid, [next_reg_id], context=context)[next_reg_id].get('balance_start', False)
            if balance:
                st_obj.write(cr, uid, [next_reg_id], {'balance_start': balance}, context=context)
    return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
