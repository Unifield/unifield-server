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

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _name = 'account.move.line'

    _columns = {
        'reconcile_date': fields.date('Reconcile date',
                                      help="Date of reconciliation"),
        'unreconcile_date': fields.date('Unreconcile date',
                                        help="Date of unreconciliation"),
        'unreconcile_txt': fields.text(string='Unreconcile number', required=False, readonly=True,
                                       help="Store the old reconcile number when the entry has been unreconciled"),
    }

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
               context=None, count=False):
        if context is None:
            context = {}

        # US-533: to answer http://jira.unifield.org/browse/US-533?focusedCommentId=50218&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-50218
        # always consider:
        # 1) reconcile empty to cancel the reconcile date criteria
        # 2) reconcile 'No' filter: become reconciled since (day+1)
        #    or not reconciled (cases 6/9 of Jira comment matrix)
        if context.get('from_web_menu', True):
            ft_obj = self.pool.get('fields.tools')
            if ft_obj.domain_get_field_index(args, 'reconcile_date') >= 0:
                is_reconciled_index = ft_obj.domain_get_field_index(args,
                                                                    'is_reconciled')
                if is_reconciled_index < 0:
                    # 1)
                    args = ft_obj.domain_remove_field(args, 'reconcile_date')
                else:
                    reconciled_date_index = ft_obj.domain_get_field_index(args,
                                                                          'reconcile_date')
                    if  reconciled_date_index >= 0 \
                            and args[is_reconciled_index][1] == '=' \
                            and not args[is_reconciled_index][2]:
                        # 2)
                        reconcile_date = args[reconciled_date_index][2]
                        args = ft_obj.domain_remove_field(args, [
                            'is_reconciled',
                            'reconcile_id',
                            'reconcile_date',
                        ])
                        domain = [
                            '|',
                            ('reconcile_date', '>', reconcile_date),
                            ('reconcile_id', '=', False),
                            ('account_id.reconcile', '=', True),
                        ]
                        args = domain + args

        return super(account_move_line, self).search(cr, uid, args,
                                                     offset=offset, limit=limit, order=order, context=context,
                                                     count=count)

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
        reconcile_partial_browsed = False
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
                if not reconcile_partial_browsed:
                    # (US-1757) We browse the list of the already partially reconciled lines only once to get their total amount
                    reconcile_partial_browsed = True
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
        # US-533: date of JI reconciliation for line_partial_ids linked with
        # above (4, 0)
        self.pool.get('account.move.line').write(cr, uid, merges+unmerge, {
            'reconcile_date': time.strftime('%Y-%m-%d'),
            'unreconcile_date': False,
            'unreconcile_txt': '',
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
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = func_debit = func_credit = currency = 0.0
        account_id = partner_id = False
        current_company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
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
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
        func_balance = func_debit - func_credit

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

        # US-533: date of JI reconciliation for total reconciliation linked
        # with above (4, 0)
        # bypass orm methods: for specific lines:
        #  - US-1766 FXA AJI should not be recomputed
        #  - US-1682 yealry REV JI have a dedicated rate
        cr.execute("UPDATE account_move_line SET reconcile_date=%s, unreconcile_date=NULL, unreconcile_txt='' WHERE id IN %s",
                   (time.strftime('%Y-%m-%d'), tuple(ids))
                   )

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

    def _get_reversal_fxa_date_and_period(self, cr, uid, fxa_move, context):
        '''
        Returns a tuple with the date and the period to use for the reversal FX entry.
        Rules:
        - if the period of the original FXA is Open, the reversal FXA uses its posting date and Period
        - if the period isn't Open, the posting date is the first date of the next open period. Period 13-16 are excluded.
        - note that the Document date is always the same as the Posting Date (to avoid FY differences)
        '''
        period_obj = self.pool.get('account.period')
        fxa_period = fxa_move.period_id
        if fxa_period.state == 'draft':  # Open
            date_and_period = (fxa_move.date, fxa_move.period_id.id)
        else:
            period_ids = period_obj.search(
                cr, uid,
                [('date_start', '>', fxa_period.date_start),
                 ('state', '=', 'draft'),
                 ('number', '>', 0), ('number', '<', 13)],
                order='date_start', limit=1, context=context)
            if not period_ids:
                raise osv.except_osv(_('Warning !'),
                                     _('There is no open period to book the reversal FX entry.'))
            period = period_obj.browse(cr, uid, period_ids[0], fields_to_fetch=['date_start'], context=context)
            date_and_period = (period.date_start, period.id)
        return date_and_period

    def reverse_fxa(self, cr, uid, fxa_line_ids, context):
        """
        Creates a reversal FX entry that offsets the FXA amount, and reconciles it with the original FXA entry
        """
        am_obj = self.pool.get('account.move')
        for fxa_line in self.browse(cr, uid, fxa_line_ids, context=context,
                                    fields_to_fetch=['move_id', 'debit', 'credit', 'debit_currency', 'credit_currency']):
            am_id = fxa_line.move_id.id
            am = am_obj.browse(cr, uid, am_id, context=context,
                               fields_to_fetch=['journal_id', 'period_id', 'date'])
            counterpart_id = self.search(cr, uid, [('move_id', '=', am_id), ('id', '!=', fxa_line.id)],
                                         order='NO_ORDER', limit=1, context=context)
            counterpart_line = counterpart_id and self.browse(cr, uid, counterpart_id[0], context=context,
                                                              fields_to_fetch=['debit', 'credit', 'debit_currency', 'credit_currency'])
            # create the JE
            date_and_period = self._get_reversal_fxa_date_and_period(cr, uid, am, context)
            reversal_am_id = am_obj.create(cr, uid,
                                           {'journal_id': am.journal_id.id,
                                            'period_id': date_and_period[1],
                                            'document_date': date_and_period[0],
                                            'date': date_and_period[0],
                                            'manual_name': 'Realised loss/gain',
                                            'state': 'posted',
                                            },
                                           context=context)
            # create the first JI = copy and reverse the FXA line
            rev_fxa_vals = {
                'move_id': reversal_am_id,
                'period_id': date_and_period[1],
                'document_date': date_and_period[0],
                'date': date_and_period[0],
                'debit': fxa_line.credit,
                'credit': fxa_line.debit,
                'debit_currency': fxa_line.credit_currency,
                'credit_currency': fxa_line.debit_currency,
            }
            rev_fxa_id = self.copy(cr, uid, fxa_line.id, rev_fxa_vals, context=context)
            # create the second JI = copy and reverse the counterpart line
            rev_counterpart_vals = {
                'move_id': reversal_am_id,
                'period_id': date_and_period[1],
                'document_date': date_and_period[0],
                'date': date_and_period[0],
                'debit': counterpart_line.credit,
                'credit': counterpart_line.debit,
                'debit_currency': counterpart_line.credit_currency,
                'credit_currency': counterpart_line.debit_currency,
            }
            self.copy(cr, uid, counterpart_line.id, rev_counterpart_vals, context=context)
            # Set the JE status to "system"
            am_obj.write(cr, uid, [reversal_am_id], {'status': 'sys'}, context=context)
            # reconcile the original FXA line with its reversal
            self.reconcile(cr, uid, [fxa_line.id, rev_fxa_id], context=context)

    def _check_instance(self, cr, uid, reconcile_id, context):
        """
        Checks that the unreconciliation is done at the same instance level as the reconciliation
        (otherwise raises a warning)
        """
        user_obj = self.pool.get('res.users')
        reconcile_obj = self.pool.get('account.move.reconcile')
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        reconciliation = reconcile_obj.browse(cr, uid, reconcile_id, fields_to_fetch=['instance_id'], context=context)
        if reconciliation.instance_id and reconciliation.instance_id.id != company.instance_id.id:
            raise osv.except_osv(_('Warning !'),
                                 _("You can only unreconcile entries in the same instance where they have been reconciled in."))

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
        reconcile_ids = [x['reconcile_id'][0] for x in self.read(cr, uid, move_ids, ['reconcile_id'], context=context) if x['reconcile_id']]
        fxa_set = set()
        for reconcile_id in reconcile_ids:
            # US-1784 Prevent unreconciliation if it is balanced in booking but unbalanced in functional
            # (= full reconciliation but FX entry not yet received via sync)
            rec_line_ids = self.search(cr, uid, [('reconcile_id', '=', reconcile_id)], order='NO_ORDER', context=context)
            rec_lines = self.browse(cr, uid, rec_line_ids, context=context,
                                    fields_to_fetch=['debit', 'credit', 'debit_currency', 'credit_currency', 'is_addendum_line'])
            debit = 0.0
            credit = 0.0
            debit_currency = 0.0
            credit_currency = 0.0
            for rec_line in rec_lines:
                debit += rec_line.debit
                credit += rec_line.credit
                debit_currency += rec_line.debit_currency
                credit_currency += rec_line.credit_currency
            balanced_in_booking = abs(debit_currency - credit_currency) < 10**-3
            balanced_in_fctal = abs(debit - credit) < 10**-3
            if balanced_in_booking and not balanced_in_fctal:
                raise osv.except_osv(_('Warning !'),
                                     _("You can't unreconcile these lines because the FX entry is missing."))
            fxa_line_ids = [rl.id for rl in rec_lines if rl.is_addendum_line]
            if fxa_line_ids:
                # if there is a FXA the unreconciliation must be done in the same instance as the reconciliation
                self._check_instance(cr, uid, reconcile_id, context)
                fxa_set.update(fxa_line_ids)
        # first we delete the reconciliation for all lines including FXA
        res = super(account_move_line, self)._remove_move_reconcile(cr, uid, move_ids, context=context)
        if fxa_set:
            # then for each FXA we create a reversal entry and reconcile them together
            self.reverse_fxa(cr, uid, list(fxa_set), context)
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
        if not ids:
            return True
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

    def reset_addendum_line(self, cr, uid, fxa_line_ids, context):
        '''
        For each addendum line in parameter, put the amount back to 0.0 for:
        - the addendum line and its counterpart (JIs)
        - the related AJI
        '''
        aml_obj = self.pool.get('account.move.line')
        for fxa_line in aml_obj.browse(cr, uid, fxa_line_ids, context=context, fields_to_fetch=['move_id']):
            account_move_id = fxa_line.move_id.id
            counterpart_id = aml_obj.search(cr, uid, [('move_id', '=', account_move_id), ('id', '!=', fxa_line.id)],
                                            order='NO_ORDER', limit=1, context=context)
            counterpart_id = counterpart_id and counterpart_id[0]
            aji = counterpart_id and aml_obj.browse(cr, uid, counterpart_id, context=context,
                                                    fields_to_fetch=['analytic_lines']).analytic_lines
            aji_id = aji and aji[0].id
            # reset the JIs
            # We use an UPDATE in SQL instead of a "write" otherwise we'll end up with a value in functional
            sql_ji = """
                UPDATE account_move_line
                SET debit_currency=0.0, credit_currency=0.0, amount_currency=0.0, debit=0.0, credit=0.0,
                unreconcile_txt=reconcile_txt, unreconcile_date=reconcile_date,
                reconcile_id=NULL, reconcile_txt='', reconcile_date=NULL
                WHERE id IN %s;
            """
            cr.execute(sql_ji, (tuple([fxa_line.id, counterpart_id]),))
            # reset the AJI
            if aji_id:
                sql_aji = """
                UPDATE account_analytic_line
                SET amount=0.0, amount_currency=0.0
                WHERE id = %s;
                """
                cr.execute(sql_aji, (aji_id,))

    def unlink(self, cr, uid, ids, context=None):
        aml_obj = self.pool.get('account.move.line')
        if context is None:
            context = {}
        if context.get('sync_update_execution'):
            # US-1997 While synchronizing if there is an FXA line linked to the reconciliation about to be deleted,
            # update the FXA line with the amount "0.0" (don't delete it to avoid gaps in FX entry sequences).
            # (Cover the use case where balanced entries from an instance are reconciled in an upper instance,
            # sync is done in the upper instance, entries are unreconciled in the upper instance, sync is done in the
            # upper instance and only then sync is done in the lower instance
            # ==> it wrongly creates an FXA line in the lower instance with the amount of one of the legs)
            fxa_line_ids = aml_obj.search(cr, uid, [('reconcile_id', '=', ids), ('is_addendum_line', '=', True)],
                                          context=context, order='NO_ORDER')
            if fxa_line_ids:
                self.reset_addendum_line(cr, uid, fxa_line_ids, context)
        return super(account_move_reconcile, self).unlink(cr, uid, ids, context=context)

account_move_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
