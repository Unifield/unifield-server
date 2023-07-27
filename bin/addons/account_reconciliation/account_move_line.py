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
        'reconcile_date': fields.date('Reconcile date', help="Date of reconciliation", select=1),
        'unreconcile_date': fields.date('Unreconcile date', help="Date of unreconciliation", select=1),
        'unreconcile_txt': fields.text(string='Unreconcile number', required=False, readonly=True, select=1,
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

    def check_multi_curr_rec(self, cr, uid, ids, context=None):
        """
        Raises an error in case a reconciliation includes several currencies whereas the account is set as prevent_multi_curr_rec
        (Note that we don't directly use the rec. field "different_currencies" as it could be False in case of a transfer with change)
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        amls = self.browse(cr, uid, ids, fields_to_fetch=['account_id', 'currency_id'], context=context)
        rec_account = amls and amls[0].account_id or False
        if rec_account and rec_account.prevent_multi_curr_rec:
            currencies = set()
            for aml in amls:
                if aml.currency_id:
                    currencies.add(aml.currency_id.id)
            if len(currencies) > 1:
                raise osv.except_osv(_('Warning'), _('The account "%s - %s" is set as "Prevent Reconciliation with different currencies".') %
                                     (rec_account.code, rec_account.name))

    def reconcile_partial(self, cr, uid, ids, type='auto', context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        self.check_imported_invoice(cr, uid, ids, context)
        self.check_multi_curr_rec(cr, uid, ids, context=context)
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
                merges_rec.append(line.reconcile_partial_id)
            else:
                unmerge.append(line.id)
                total += (line.debit_currency or 0.0) - (line.credit_currency or 0.0)

        if self.pool.get('res.currency').is_zero(cr, uid, company_currency_id, total):
            res = self.reconcile(cr, uid, merges+unmerge, type=type, context=context)
            return res

        # delete old partial rec
        if merges_rec:
            self.pool.get('account.move.reconcile')._generate_unreconcile(cr, uid, merges_rec, context=context)

        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_partial_ids': map(lambda x: (4,x,False), merges+unmerge),
            'is_multi_instance': different_level,
            'nb_partial_legs': len(set(merges+unmerge)),
        })

        if merges_rec:
            self.pool.get('account.move.reconcile').unlink(cr, uid, [x.id for x in merges_rec], context=context)

        # do not delete / recreate AJIs
        cr.execute("""
            update account_move_line set
            reconcile_date=%s, unreconcile_date=NULL, unreconcile_txt=''
            where id in %s
            """, (time.strftime('%Y-%m-%d'), tuple(merges+unmerge), )
        )

        move_rec_obj.reconcile_partial_check(cr, uid, [r_id] + [x.id for x in merges_rec], context=context)
        return True

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        self.check_imported_invoice(cr, uid, ids, context)
        self.check_multi_curr_rec(cr, uid, ids, context=context)
        account_obj = self.pool.get('account.account')
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        currency = 0.0
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
        partial_reconcile_ids = set()
        func_balance = 0
        book_balance = 0
        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('Error'),
                                     _('Entry "%s" is not valid !') % line.name)
            book_balance += line['debit_currency'] - line['credit_currency']
            func_balance += line['debit'] - line['credit']
            currency += line['amount_currency'] or 0.0
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
            if line.reconcile_partial_id:
                partial_reconcile_ids.add(line.reconcile_partial_id)

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
        if not context.get('fy_closing', False) and not context.get('fy_hq_closing', False) and not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconciled !'))
        if r[0][1] != None:
            raise osv.except_osv(_('Error'), _('Some entries are already reconciled !'))

        if context.get('fy_hq_closing', False):
            if abs(func_balance) > 10**-3 or abs(book_balance) > 10**-3:
                # yearly move to zero entries should be balanced in functional and booking currency
                raise osv.except_osv(_('Error'),
                                     _("The entries included in the yearly move to zero can't be reconciled together "
                                       "because they are unbalanced."))
        elif abs(func_balance) > 10**-3:  # FIX UF-1903 problem
            partner_line_id = self.create_addendum_line(cr, uid, [x.id for x in unrec_lines], func_balance)
            if partner_line_id:
                # Add partner_line to do total reconciliation
                ids.append(partner_line_id)

        if partial_reconcile_ids:
            # delete old partial rec
            self.pool.get('account.move.reconcile')._generate_unreconcile(cr, uid, list(partial_reconcile_ids), context=context)

        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_id': map(lambda x: (4, x, False), ids),
            'line_partial_ids': map(lambda x: (3, x, False), ids),
            'is_multi_instance': different_level,
            'multi_instance_level_creation': multi_instance_level_creation,
        })
        if partial_reconcile_ids:
            # delete old partial rec
            self.pool.get('account.move.reconcile').unlink(cr, uid, [x.id for x in partial_reconcile_ids], context=context)

        # US-533: date of JI reconciliation for total reconciliation linked
        # with above (4, 0)
        # bypass orm methods: for specific lines:
        #  - US-1766 FXA AJI should not be recomputed
        #  - US-1682 yealry REV JI have a dedicated rate
        cr.execute("UPDATE account_move_line SET reconcile_date=%s, unreconcile_date=NULL, unreconcile_txt='' WHERE id IN %s",
                   (time.strftime('%Y-%m-%d'), tuple(ids))
                   )

        wf_service = netsvc.LocalService("workflow")
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and context and context.get('stop_reconcile', False):
                partner_obj.write(cr, uid, [partner_id], {'last_reconciliation_date': time.strftime('%Y-%m-%d %H:%M:%S')})

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
        - if the period isn't Open, the posting date is the first date of the next open period. Periods 0 and 16 are excluded.
        - note that the Document date is always the same as the Posting Date (to avoid FY differences)
        '''
        period_obj = self.pool.get('account.period')
        fxa_period = fxa_move.period_id
        if fxa_period.state == 'draft':  # Open
            date_and_period = (fxa_move.date, fxa_move.period_id.id)
        else:
            period_ids = period_obj.search(
                cr, uid,
                [('date_start', '>=', fxa_period.date_start),
                 ('state', '=', 'draft'),
                 ('number', 'not in', [0, 16])],
                order='date_start, number', limit=1, context=context)
            if not period_ids:
                raise osv.except_osv(_('Warning !'),
                                     _('There is no open period to book the reversal FX entry.'))
            period = period_obj.browse(cr, uid, period_ids[0], fields_to_fetch=['date_start'], context=context)
            date_and_period = (period.date_start, period.id)
        return date_and_period

    def reverse_fxa(self, cr, uid, fxa_line_ids, context):
        """
        Creates a reversal FX entry that offsets the FXA amount, and reconciles it with the original FXA entry.
        The reversal FXA Prop. Instance is the current one, in which the Entry Sequence is created.
        """
        am_obj = self.pool.get('account.move')
        journal_obj = self.pool.get('account.journal')
        for fxa_line in self.browse(cr, uid, fxa_line_ids, context=context,
                                    fields_to_fetch=['move_id', 'debit', 'credit', 'debit_currency', 'credit_currency']):
            am = fxa_line.move_id
            counterpart_id = self.search(cr, uid, [('move_id', '=', am.id), ('id', '!=', fxa_line.id)],
                                         order='NO_ORDER', limit=1, context=context)
            counterpart_line = self.browse(cr, uid, counterpart_id[0], context=context,
                                           fields_to_fetch=['debit', 'credit', 'debit_currency', 'credit_currency'])
            # create the JE
            date_and_period = self._get_reversal_fxa_date_and_period(cr, uid, am, context)
            # get the FXA journal of the current instance
            journal_ids = journal_obj.search(cr, uid, [('type', '=', 'cur_adj'), ('is_current_instance', '=', True)],
                                             order='NO_ORDER', limit=1, context=context)
            if not journal_ids:
                raise osv.except_osv(_('Warning !'),
                                     _('No journal found to book the reversal FX entry.'))
            reversal_am_id = am_obj.create(cr, uid,
                                           {'journal_id': journal_ids[0],  # it also determines the instance_id (= the current instance)
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
                                 _("Entries with an FX adjustment entry can only be unreconciled in the same instance "
                                   "where they have been reconciled in."))

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
        reconcile_ids = set(x['reconcile_id'][0] for x in self.read(cr, uid, move_ids, ['reconcile_id'], context=context) if x['reconcile_id'])
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
            fxa_line_ids = []
            for rec_line in rec_lines:
                debit += rec_line.debit
                credit += rec_line.credit
                debit_currency += rec_line.debit_currency
                credit_currency += rec_line.credit_currency
                if rec_line.is_addendum_line:
                    fxa_line_ids.append(rec_line.id)
            balanced_in_booking = abs(debit_currency - credit_currency) < 10**-3
            balanced_in_fctal = abs(debit - credit) < 10**-3
            if balanced_in_booking and not balanced_in_fctal:
                raise osv.except_osv(_('Warning !'),
                                     _("You can't unreconcile these lines because the FX entry is still missing."))
            # The loop is on full reconciliations => if the amounts are partial all legs aren't in the current instance:
            # prevent from unreconciling
            if not balanced_in_booking and not balanced_in_fctal:
                raise osv.except_osv(_('Warning !'),
                                     _("You can't unreconcile these entries in this instance "
                                       "because all legs are not present."))
            if fxa_line_ids:
                # if there is a FXA the unreconciliation must be done in the same instance as the reconciliation
                self._check_instance(cr, uid, reconcile_id, context)
                fxa_set.update(fxa_line_ids)
        # first we delete the reconciliation for all lines including FXA
        context.update({'from_remove_move_reconcile': True})
        res = super(account_move_line, self)._remove_move_reconcile(cr, uid, move_ids, context=context)
        if fxa_set:
            # then for each FXA we create a reversal entry and reconcile them together
            self.reverse_fxa(cr, uid, list(fxa_set), context)
        return res

    def log_reconcile(self, cr, uid, reconcile_obj, aml_id=None, previous=None, delete=False, rec_name=False, context=None):
        """
        create a track change line for a reconcile obj (partial or full)
        this line must be logged on account.move

        Args:
            reconcile_obj: browse record of account.move.reconcile
            aml_id: account_move_line id, if set account.move.line linked to the reconcile will not be processed
            previous: dict indexed by account.move.line.id, contains the value of the previous reconcile
            delete: True when called from reconcile_obj unlink, no new value, old value extracted from reconcile_obj
            rec_name: reconciliation ref, used for partial rec when name contains the diff amount, otherwise reconcile_obj.name is used
        """
        if previous is None:
            previous = {}
        if context is None:
            context = {}

        # build list of account.move.line to compute
        if aml_id:
            aml_obj = self.browse(cr, uid, aml_id, context=context)
            if aml_obj.reconcile_id:
                rec_type = 'Reconcile'
            else:
                rec_type = 'Partial Reconcile'
            to_compute = [(rec_type, [aml_obj])]
        else:
            to_compute = [('Reconcile', reconcile_obj.line_id), ('Partial Reconcile', reconcile_obj.line_partial_ids)]

        model_id_tolog = self.pool.get('ir.model').search(cr, uid, [('model', '=', 'account.move')])[0]
        fct_id_tolog = self.pool.get('ir.model').search(cr, uid, [('model', '=', 'account.move.line')])[0]
        rule_obj = self.pool.get('audittrail.rule')

        if delete:
            old_value = rec_name or reconcile_obj.name
            new_value = ''
        else:
            new_value = rec_name or reconcile_obj.name

        user_id =  hasattr(uid, 'realUid') and uid.realUid or uid
        for desc, amls in to_compute:
            for aml in amls:
                if not delete:
                    old_value = previous.get(aml.id, '')

                self.pool.get('audittrail.log.line').create(cr, uid, {
                    'name': desc,
                    'field_description': desc,
                    'method': 'write',
                    'object_id': model_id_tolog,
                    'fct_object_id': fct_id_tolog,
                    'user_id': user_id,
                    'res_id': aml.move_id.id,
                    'fct_res_id': aml.id,
                    'log': rule_obj.get_sequence(cr, uid, 'account.move', aml.move_id.id, context=context),
                    'old_value': old_value,
                    'old_value_text': old_value,
                    'new_value': new_value,
                    'new_value_text': new_value,
                    'other_column': aml.sequence_move,
                    'sub_obj_name': aml.name,
                }, context=context)

        return True

account_move_line()

class account_move_reconcile(osv.osv):
    _name = 'account.move.reconcile'
    _inherit = 'account.move.reconcile'

    _columns = {
        'is_multi_instance': fields.boolean(string="Reconcile at least 2 lines that comes from different instance levels."),
        'multi_instance_level_creation': fields.selection([('section', 'Section'), ('coordo', 'Coordo'), ('project', 'Project')],
                                                          string='Where the adjustement line should be created'
                                                          ),
        'nb_partial_legs': fields.integer('Nb legs in partial reconcile'),
        'action_date': fields.date('Date of (un)reconciliation'),
    }

    _defaults = {
        'is_multi_instance': lambda *a: False,
        'multi_instance_level_creation': False,
        'nb_partial_legs': 0,
        'action_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def common_create_write(self, cr, uid, ids, action_date, prev=None, context=None):
        if context is None:
            context = {}
        for r in self.browse(cr, uid, ids):
            t = [x.id for x in r.line_id]
            p = [x.id for x in r.line_partial_ids]
            d = self.name_get(cr, uid, [r.id])
            name = ''
            if d and d[0] and d[0][1]:
                name = d[0][1]
            if p or t:
                sql_params = [name, tuple(p+t)]
                new_field = ""
                if prev is not None:
                    self.pool.get('account.move.line').log_reconcile(cr, uid, r, previous=prev, rec_name=name, context=context)
                if context.get('sync_update_execution') and t:
                    if action_date:
                        new_field = "unreconcile_date=NULL, unreconcile_txt='', reconcile_date=%s,"
                        sql_params.insert(0, action_date)

                    # during sync exec, check if invoices must be set as paid / closed
                    invoice_ids = [line.invoice.id for line in r.line_id if
                                   line.invoice and line.invoice.state not in ('paid','inv_close')]
                    if invoice_ids and self.pool.get('account.invoice').test_paid(cr, uid, invoice_ids):
                        self.pool.get('account.invoice').confirm_paid(cr, uid, invoice_ids)


                sql = "UPDATE " + self.pool.get('account.move.line')._table + " SET " + new_field + " reconcile_txt = %s WHERE id in %s"  # not_a_user_entry
                cr.execute(sql, sql_params)
        return True

    def _set_accruals_to_done(self, cr, rec_id):
        """
        Accruals in Running state are set to Done if they are fully reconciled.

        Note that only One Time Accruals can be in Running state, and that only the header line on the accrual account is reconcilable.
        """
        if rec_id:
            accrual_sql = """
                UPDATE msf_accrual_line
                SET state = 'done'
                WHERE state = 'running'
                AND id IN (SELECT accrual_line_id FROM account_move_line WHERE reconcile_id = %s)
            """
            cr.execute(accrual_sql, (rec_id,))
        return True

    def _set_accruals_to_running(self, cr, rec_ids):
        """
        One Time Accruals in Done state are set back to Running if their header line is unreconciled.
        """
        if rec_ids:
            if isinstance(rec_ids, (int, long)):
                rec_ids = [rec_ids]
            accrual_sql = """
                UPDATE msf_accrual_line
                SET state = 'running'
                WHERE accrual_type = 'one_time_accrual' AND state = 'done'
                AND id IN (SELECT accrual_line_id FROM account_move_line WHERE reconcile_id IN %s)
            """
            cr.execute(accrual_sql, (tuple(rec_ids),))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Write reconcile_txt on linked account_move_lines if any changes on this reconciliation.
        """
        if not context:
            context = {}

        # track changes: we need the old value, the previous reconcile if any
        prev = {}
        aml_ids = []

        new_vals = {}
        # use one2many codification (x,values) to get account.move.line tied to this new rec
        # x=5 to delete existing links is ignored as we are in create mode
        for rec_type in ['line_id', 'line_partial_ids']:
            if vals.get(rec_type):
                for x in vals.get(rec_type):
                    if x[0] in (1, 2, 3, 4):
                        aml_ids.append(x[1])
                        if context.get('sync_update_execution'):
                            new_vals.setdefault(rec_type, []).append(x)
                    elif x[0] == 6:
                        aml_ids += x[2]
                        if context.get('sync_update_execution') and x[2]:
                            new_vals.setdefault(rec_type, []).append((7, x[2]))

        if new_vals:
            vals.update(new_vals)

        # get previous reconcile from _txt
        already_reconciled = []
        if aml_ids:
            cr.execute('select l.id, l.reconcile_txt, l.reconcile_id, l.reconcile_partial_id, l.name, m.name from account_move_line l left join account_move m on m.id = l.move_id where l.id in %s', (tuple(aml_ids),))
            for x in cr.fetchall():
                prev[x[0]] = x[1]

                if context.get('sync_update_execution') and x[2]:
                    already_reconciled.append('%s %s already reconciled on the instance, id:%s, rec_txt:%s' % (x[4], x[5], x[0], x[1]))

        if already_reconciled:
            raise osv.except_osv(_('Warning'), "\n".join(already_reconciled))

        res = super(account_move_reconcile, self).create(cr, uid, vals, context)
        if res:
            tmp_res = res
            if isinstance(res, (int, long)):
                tmp_res = [tmp_res]
            self.common_create_write(cr, uid, tmp_res, vals.get('action_date'), prev=prev, context=context)

        if context.get('sync_update_execution'):
            self.pool.get('account.move.line').reconciliation_update(cr, uid, [res], context=context)
        self._set_accruals_to_done(cr, res)
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
        self.common_create_write(cr, uid,  ids, vals.get('action_date'), context=context)
        return res

    def _generate_unreconcile(self, cr, uid, rec_obj, context=None):
        if context is None:
            context = {}

        if not context.get('sync_update_execution'):
            move_obj = self.pool.get('account.move.line')
            for rec in rec_obj:
                if rec.line_id or rec.line_partial_ids:
                    # full reconcile deleted
                    lines = rec.line_id or rec.line_partial_ids
                    sdrefs = move_obj.get_sd_ref(cr, uid, [x.id for x in lines], context=context)
                    self.pool.get('account.move.unreconcile').create(cr, 1, {'delete_reconcile_txt': rec.name, 'move_sdref_txt': ','.join(sdrefs.values())}, context=context)
                    # do not trigger sync
                    cr.execute('''update account_move_line set
                            has_a_counterpart_transfer='f', counterpart_transfer_st_line_id=NULL
                        where
                            id in %s
                            and (counterpart_transfer_st_line_id is not null or has_a_counterpart_transfer='t')
                    ''', (tuple([x.id for x in lines]), ))
        return True

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        move_obj = self.pool.get('account.move.line')
        for rec in self.browse(cr, uid, list(set(ids)), fields_to_fetch=['name', 'line_id', 'line_partial_ids'], context=context):
            move_obj.log_reconcile(cr, uid, rec, delete=True, context=context)
            self._generate_unreconcile(cr, uid, [rec], context)

        self._set_accruals_to_running(cr, ids)

        return super(account_move_reconcile, self).unlink(cr, uid, ids, context=context)


account_move_reconcile()

class account_move_unreconcile(osv.osv):

    """ Object used to track JI legs on unreconcile, used by sync to set unreconcile_date on JI """

    _name = 'account.move.unreconcile'
    _rec_name = 'unreconcile_date'

    _columns = {
        'unreconcile_date': fields.date("Unreconcile date"),
        'delete_reconcile_txt': fields.char('Old reconcile ref', size=126),
        'move_sdref_txt': fields.text('List of JI sdref'),
        'reconcile_sdref': fields.char('Rec sdref', size=128, internal=True, help='used to fix US-6930'),
    }

    _defaults = {
        'unreconcile_date': lambda *a: time.strftime('%Y-%m-%d'),
        'reconcile_sdref': False,
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals.get('move_sdref_txt'):
            move_line_obj = self.pool.get('account.move.line')
            invoice_reopen = []
            move_ids = move_line_obj.find_sd_ref(cr, uid, vals['move_sdref_txt'].split(","), context=context)
            if move_ids:
                move_lines = []
                for move_line in move_line_obj.browse(cr, uid, move_ids.values(), fields_to_fetch=['invoice', 'reconcile_id', 'reconcile_partial_id'], context=context):
                    if not move_line.reconcile_id and not move_line.reconcile_partial_id or \
                            move_line.reconcile_id and move_line.reconcile_id.name == vals.get('delete_reconcile_txt') or \
                            move_line.reconcile_partial_id and move_line.reconcile_partial_id.name == vals.get('delete_reconcile_txt'):
                        move_lines.append(move_line)
                if move_lines:
                    invoice_reopen = [line.invoice.id for line in move_lines if line.reconcile_id and line.invoice and line.invoice.state in ['paid','inv_close']]
                    cr.execute("UPDATE account_move_line SET unreconcile_txt=%s, unreconcile_date=%s, reconcile_txt='', reconcile_date=NULL, has_a_counterpart_transfer='f' WHERE id in %s", (vals.get('delete_reconcile_txt'), vals.get('unreconcile_date'), tuple([x.id for x in move_lines])))

            if vals.get('delete_reconcile_txt'):
                # do not sync reconcile delete, to prevent any error in case of account_move_unreconcile update is NR
                delete_rec = self.pool.get('account.move.reconcile').search(cr, uid, [('name', '=', vals.get('delete_reconcile_txt'))], context=context)
                if delete_rec:
                    self.pool.get('account.move.reconcile').unlink(cr, uid, delete_rec, context=context)
            if invoice_reopen:
                # invoices unreconciled on upper level to reopen
                netsvc.LocalService("workflow").trg_validate(uid, 'account.invoice', invoice_reopen, 'open_test', cr)
        elif context.get('sync_update_execution') and vals.get('reconcile_sdref'):
            rec_id = self.pool.get('account.move.reconcile').find_sd_ref(cr, uid, vals.get('reconcile_sdref'), context=context)
            if rec_id:
                if self.pool.get('account.move.reconcile').exists(cr, uid, rec_id, context=context):
                    self.pool.get('account.move.reconcile').unlink(cr, uid, rec_id, context=context)
            else:
                update_ids = self.pool.get('sync.client.update_received').search(cr, uid, [('run', '=', False), ('sdref', '=', vals.get('reconcile_sdref'))], context=context)
                if update_ids:
                    self.pool.get('sync.client.update_received').write(cr, uid, update_ids, {'run': 't', 'log': 'Set as run by patch US-6930'}, context=context)
        return super(account_move_unreconcile, self).create(cr, uid, vals, context)

account_move_unreconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
