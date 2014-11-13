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
import time
import netsvc
from tools.translate import _
from tools.misc import flatten

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _name = 'account.move.line'

    def check_imported_invoice(self, cr, uid, ids, context=None):
        """
        Check that for these IDS, no one is used in imported invoice.
        For imported invoice, the trick comes from the fact that do_import_invoices_reconciliation hard post the moves before reconciling them.
        """
        # Some verifications
        if not context:
            context = {}
        from_pending_payment = False
        if context.get('pending_payment', False) and context.get('pending_payment') is True:
            from_pending_payment = True
        # Create a SQL request that permit to fetch quickly statement lines that have an imported invoice
        sql = """SELECT st_line_id
        FROM imported_invoice
        WHERE move_line_id in %s
        AND st_line_id IN (SELECT st.id 
            FROM account_bank_statement_line st 
            LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id 
            LEFT JOIN account_move m ON m.id = rel.statement_id 
            WHERE m.state = 'draft')
        GROUP BY st_line_id;
        """
        cr.execute(sql, (tuple(ids),))
        sql_res = cr.fetchall()
        if sql_res and not from_pending_payment:
            res = [x and x[0] for x in sql_res]
            # Search register lines
            msg = []
            for absl in self.pool.get('account.bank.statement.line').browse(cr, uid, res):
                msg += [_("%s (in %s)") % (absl.name, absl.statement_id and absl.statement_id.name or '',)]
            raise osv.except_osv(_('Warning'), _('Reconciliation of lines that come from a "Pending payment" wizard should be done via registers. Lines: %s') % (' - '.join(msg),))
        return True

    def reconcile_partial(self, cr, uid, ids, type='auto', context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        self.check_imported_invoice(cr, uid, ids, context)
        # @@@override@account.account_move_line.py
        move_rec_obj = self.pool.get('account.move.reconcile')
        merges = []
        unmerge = []
        total = 0.0
        merges_rec = []
        company_list = []
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)

        # UTP-752: Add an attribute to reconciliation element if different instance levels
        previous_level = False
        different_level = False
        for line in self.browse(cr, uid, ids, context=context):
            # Do level check only if we don't know if more than 1 different level exists between lines
            if not different_level:
                if not previous_level:
                    previous_level = line.instance_id.id
                if previous_level != line.instance_id.id:
                    different_level = True
            company_currency_id = line.company_id.currency_id
            if line.reconcile_id:
                raise osv.except_osv(_('Warning'), _('Already Reconciled!'))
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    if not line2.reconcile_id:
                        if line2.id not in merges:
                            merges.append(line2.id)
                        # Next line have been modified from debit/credit to debit_currency/credit_currency
                        total += (line2.debit_currency or 0.0) - (line2.credit_currency or 0.0)
                merges_rec.append(line.reconcile_partial_id.id)
            else:
                unmerge.append(line.id)
                total += (line.debit_currency or 0.0) - (line.credit_currency or 0.0)

        if self.pool.get('res.currency').is_zero(cr, uid, company_currency_id, total):
            res = self.reconcile(cr, uid, merges+unmerge, context=context)
            return res
        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_partial_ids': map(lambda x: (4,x,False), merges+unmerge),
            'is_multi_instance': different_level,
        })
        
        # UF-2011: synchronize move lines (not "marked" after reconcile creation)
        if self.pool.get('sync.client.orm_extended'):
            self.pool.get('account.move.line').synchronize(cr, uid, merges+unmerge, context=context)
        
        move_rec_obj.reconcile_partial_check(cr, uid, [r_id] + merges_rec, context=context)
        # @@@end
        return True

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        self.check_imported_invoice(cr, uid, ids, context)
        # @@@override@account.account_move_line.py
        account_obj = self.pool.get('account.account')
        move_obj = self.pool.get('account.move')
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        currency_obj = self.pool.get('res.currency')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = func_debit = func_credit = currency = 0.0
        account_id = partner_id = employee_id = functional_currency_id = False
        current_company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        currency_id = current_company.currency_id.id
        current_instance_level = current_company.instance_id.level
        if context is None:
            context = {}
        company_list = []
        # Check company's field
        # UTP-752: Check if lines comes from the same instance level
        previous_level = False
        different_level = False
        multi_instance_level_creation = False
        has_project_line = False
        has_section_line = False
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)
            # instance level
            if not different_level:
                if not previous_level:
                    previous_level = line.instance_id.id
                if previous_level != line.instance_id.id:
                    different_level = True
            if current_instance_level == 'section':
                if line.instance_id.level == 'section':
                    has_section_line = True
                elif line.instance_id.level == 'project':
                    has_project_line = True
        if different_level and has_project_line and not has_section_line:
            different_level = False
            multi_instance_level_creation = 'coordo'
        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('Error'),
                        _('Entry "%s" is not valid !') % line.name)
            credit += line['credit_currency']
            debit += line['debit_currency']
            func_debit += line['debit']
            func_credit += line['credit']
            currency += line['amount_currency'] or 0.0
#            currency_id = line['currency_id']['id']
            functional_currency_id = line['currency_id']['id']
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
            employee_id = (line['employee_id'] and line['employee_id']['id']) or False
        func_balance = func_debit - func_credit

        # Ifdate_p in context => take this date
        if context.has_key('date_p') and context['date_p']:
            date=context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        cr.execute('SELECT account_id, reconcile_id '\
                   'FROM account_move_line '\
                   'WHERE id IN %s '\
                   'GROUP BY account_id,reconcile_id',
                   (tuple(ids), ))
        r = cr.fetchall()
        #TODO: move this check to a constraint in the account_move_reconcile object
        if (len(r) != 1) and not context.get('fy_closing', False):
            raise osv.except_osv(_('Error'), _('Entries are not of the same account or already reconciled ! '))
        if not unrec_lines:
            raise osv.except_osv(_('Error'), _('Entry is already reconciled'))
        account = account_obj.browse(cr, uid, account_id, context=context)
        if not context.get('fy_closing', False) and not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconciled !'))
        if r[0][1] != None:
            raise osv.except_osv(_('Error'), _('Some entries are already reconciled !'))
        
        if abs(func_balance) > 10**-3: # FIX UF-1903 problem
            partner_line_id = self.create_addendum_line(cr, uid, [x.id for x in unrec_lines], func_balance)
            if partner_line_id:
                # Add partner_line to do total reconciliation
                ids.append(partner_line_id)

        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_id': map(lambda x: (4, x, False), ids),
            'line_partial_ids': map(lambda x: (3, x, False), ids),
            'is_multi_instance': different_level,
            'multi_instance_level_creation': multi_instance_level_creation,
        })
        
        # UF-2011: synchronize move lines (not "marked" after reconcile creation)
        if self.pool.get('sync.client.orm_extended'):
            self.pool.get('account.move.line').synchronize(cr, uid, ids, context=context)
        
        wf_service = netsvc.LocalService("workflow")
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and context and context.get('stop_reconcile', False):
                partner_obj.write(cr, uid, [partner_id], {'last_reconciliation_date': time.strftime('%Y-%m-%d %H:%M:%S')})
        # @@@end
        return r_id

    def _hook_check_period_state(self, cr, uid, result=False, context=None, *args, **kargs):
        """
        Check period state only if "from" is in context and equal to "reverse_addendum"
        """
        if not result or not context:
            return super(account_move_line, self)._hook_check_period_state(cr, uid, result, context, *args, **kargs)
        if context and 'from' in context and context.get('from') == 'reverse_addendum':
            return True
        return super(account_move_line, self)._hook_check_period_state(cr, uid, result, context, *args, **kargs)

    def _remove_move_reconcile(self, cr, uid, move_ids=None, context=None):
        """
        Delete reconciliation object from given move lines ids (move_ids) and reverse gain/loss lines.
        """
        # Some verifications
        if move_ids is None:
            move_ids = []
        if not context:
            context = {}
        if isinstance(move_ids, (int, long)):
            move_ids = [move_ids]
        # Prepare some values
        to_reverse = []
        # Retrieve all addendum lines
        # First search all reconciliation ids to find ALL move lines (some could be not selected but unreconciled after
        reconcile_ids = [(x.reconcile_id and x.reconcile_id.id) or (x.reconcile_partial_id and x.reconcile_partial_id.id) or None for x in self.browse(cr, uid, move_ids, context=context)]
        if reconcile_ids:
            # Search all account move line for this reconcile_ids
            operator = 'in'
            if len(reconcile_ids) == 1:
                operator = '='
            ml_ids = self.search(cr, uid, [('reconcile_id', operator, reconcile_ids)])
            # Search addendum line to delete
            for line in self.browse(cr, uid, ml_ids, context=context):
                if line.is_addendum_line:
                    lines = [x.id for x in line.move_id.line_id]
                    to_reverse.append(lines)
        # Retrieve default behaviour
        res = super(account_move_line, self)._remove_move_reconcile(cr, uid, move_ids, context=context)
        # If success, verify that no addendum line exists
        if res and to_reverse:
            # Delete doublons
            to_reverse = flatten(to_reverse)
            # Reverse move
            context.update({'from': 'reverse_addendum'})
            success_ids, move_ids = self.reverse_move(cr, uid, to_reverse, context=context)
            # Search all move lines attached to given move_ids
            moves = self.pool.get('account.move').browse(cr, uid, move_ids, context=context)
            lines = []
            for move in moves:
                lines += [x.id for x in move.line_id]
            lines = flatten(lines)
            # Set booking debit/credit to 0 for these lines
            sql = """
                UPDATE account_move_line
                SET debit_currency=%s, credit_currency=%s, amount_currency=%s
                WHERE id IN %s
            """
            cr.execute(sql, [0.0, 0.0, 0.0, tuple(lines)])
            # Reconcile lines
            all_lines = flatten([to_reverse, lines])
            to_reconcile = self.pool.get('account.move.line').search(cr, uid, [('id', 'in', all_lines), ('account_id.reconcile', '=', True)])
            if to_reconcile:
                self.pool.get('account.move.line').reconcile(cr, uid, to_reconcile)
        return res

account_move_line()

class account_move_reconcile(osv.osv):
    _name = 'account.move.reconcile'
    _inherit = 'account.move.reconcile'

    _columns = {
        'is_multi_instance': fields.boolean(string="Reconcile at least 2 lines that comes from different instance levels."),
        'multi_instance_level_creation': fields.selection([('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')],
            string='Where the adjustement line should be created'
        )
    }

    _defaults = {
        'is_multi_instance': lambda *a: False,
        'multi_instance_level_creation': False,
    }

    def create(self, cr, uid, vals, context=None):
        """
        Write reconcile_txt on linked account_move_lines if any changes on this reconciliation.
        """
        if not context:
            context = {}
        res = super(account_move_reconcile, self).create(cr, uid, vals, context)
        if res:
            tmp_res = res
            if isinstance(res, (int, long)):
                tmp_res = [tmp_res]
            for r in self.browse(cr, uid, tmp_res):
                t = [x.id for x in r.line_id]
                p = [x.id for x in r.line_partial_ids]
                d = self.name_get(cr, uid, [r.id])
                name = ''
                if d and d[0] and d[0][1]:
                    name = d[0][1]
                if p or t:
                    sql = "UPDATE " + self.pool.get('account.move.line')._table + " SET reconcile_txt = %s WHERE id in %s"
                    cr.execute(sql, (name, tuple(p+t)))
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write reconcile_txt on linked account_move_lines if any changes on this reconciliation.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_move_reconcile, self).write(cr, uid, ids, vals, context)
        if res:
            for r in self.browse(cr, uid, ids):
                t = [x.id for x in r.line_id]
                p = [x.id for x in r.line_partial_ids]
                d = self.name_get(cr, uid, [r.id])
                name = ''
                if d and d[0] and d[0][1]:
                    name = d[0][1]
                if p or t:
                    sql = "UPDATE " + self.pool.get('account.move.line')._table + " SET reconcile_txt = %s WHERE id in %s"
                    cr.execute(sql, (name, tuple(p+t)))
        return res

account_move_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
