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
from osv import fields
from tools.translate import _
from time import strftime
from tools.misc import flatten
from base import currency_date


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def _is_corrigible(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The entry state is posted
         - The account is not payables, receivables or tax
         - Item have not been corrected
         - Item have not been reversed
         - Item come from a reconciliation that have set 'is_addendum_line' to True
         - The account is not the default credit/debit account of the attached statement (register)
         - The line isn't partially or totally reconciled
         - The line doesn't come from a write-off
         - The line is "corrected_upstream" that implies the line have been already corrected from a coordo or a hq to a level that is superior or equal to these instance.
         - The line isn't linked to a SI refund cancel

         Note: JIs on inactive journals are still correctable (US-7563).
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        # Search all accounts that are used in bank, cheque and cash registers
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', 'in', ['bank', 'cheque', 'cash'])])
        account_ids = []
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        level = company and company.instance_id and company.instance_id.level or ''
        for j in self.pool.get('account.journal').read(cr, uid, journal_ids, ['default_debit_account_id', 'default_credit_account_id']):
            if j.get('default_debit_account_id', False) and j.get('default_debit_account_id')[0] not in account_ids:
                account_ids.append(j.get('default_debit_account_id')[0])
            if j.get('default_credit_account_id', False) and j.get('default_credit_account_id')[0] not in account_ids:
                account_ids.append(j.get('default_credit_account_id')[0])

        acc_corr = {}

        allow_extra = self.pool.get('res.company').extra_period_config(cr) == 'other'
        # Skip to next element if the line is set to False
        for ml in self.browse(cr, 1, ids, context=context):
            res[ml.id] = True
            acc_corr.setdefault(ml.account_id.id, ml.account_id.user_type.not_correctible)
            # False if special (or implicitly system period)
            if not allow_extra and ml.period_id.special or ml.period_id.number in (0, 16):
                res[ml.id] = False
                continue
            # False if account type is transfer
            if ml.account_id.type_for_register in ['transfer', 'transfer_same']:
                res[ml.id] = False
                continue
            # False if move is not posted
            if ml.move_id.state != 'posted':
                res[ml.id] = False
                continue
            # False if account type code (User type) is set as non correctible
            if acc_corr.get(ml.account_id.id):
                res[ml.id] = False
                continue
            # False if line have been corrected
            if ml.corrected:
                res[ml.id] = False
                continue
            # False if line is a reversal
            if ml.reversal:
                res[ml.id] = False
                continue
            # False if this line is an addendum line
            if ml.is_addendum_line:
                res[ml.id] = False
                continue
            # False if line account and statement default debit/credit account are similar
            if ml.statement_id:
                accounts = []
                accounts.append(ml.statement_id.journal_id.default_debit_account_id and ml.statement_id.journal_id.default_debit_account_id.id)
                accounts.append(ml.statement_id.journal_id.default_credit_account_id and ml.statement_id.journal_id.default_credit_account_id.id)
                if ml.account_id.id in accounts:
                    res[ml.id] = False
                    continue
            # False if this line come from a write-off
            if ml.is_write_off:
                res[ml.id] = False
                continue
            # False if this line come from an accrual
            if ml.accrual:
                res[ml.id] = False
                continue
            # False if the account is used in a cash/bank/cheque journal
            if ml.account_id.id in account_ids:
                res[ml.id] = False
                continue
            # False if "corrected_upstream" is True and that we come from project level
            if ml.corrected_upstream and level == 'project':
                res[ml.id] = False
                continue
            # False if this line is a revaluation or a system entry
            if ml.journal_id.type in ('revaluation', 'system', ):
                res[ml.id] = False
                continue
            # False if the line is linked to a SI refund cancel (SI line or SR line)
            if ml.is_si_refund:
                res[ml.id] = False
                continue
            # False if the move line is partially or totally reconciled
            if ml.reconcile_id or ml.reconcile_partial_id:
                res[ml.id] = False
                continue
        return res

    _columns = {
        'corrected': fields.boolean(string="Corrected?", readonly=True,
                                    help="If true, this line has been corrected by an accounting correction wizard"),
        'corrected_line_id': fields.many2one('account.move.line', string="Corrected Line", readonly=True,
                                             help="Line that have been corrected by this one.", select=1),
        'reversal': fields.boolean(string="Reversal?", readonly=True,
                                   help="If true, this line is a reversal of another (This was done via a correction wizard)."),
        'reversal_line_id': fields.many2one('account.move.line', string="Reversal Line", readonly=True,
                                            help="Line that have been reversed by this one.", select=1),
        'have_an_historic': fields.boolean(string="Display historic?", readonly=True,
                                           help="If true, this implies that this line have historical correction(s)."),
        'is_corrigible': fields.function(_is_corrigible, method=True, string="Is corrigible?", type='boolean',
                                         readonly=True, help="This informs system if this item is corrigible. Criteria: the entry state should be posted, account should not be payable or \
receivable, item have not been corrected, item have not been reversed and account is not the default one of the linked register (statement).",
                                         store=False),
        'corrected_st_line_id': fields.many2one('account.bank.statement.line', string="Corrected register line", readonly=True,
                                                help="This register line is those which have been corrected last."),
        'last_cor_was_only_analytic': fields.boolean(string="AD Corrected?",
                                                     invisible=True,
                                                     help="If true, this line has been corrected by an accounting correction wizard but with only an AD correction (no G/L correction)"),
        'is_manually_corrected': fields.boolean('Is Manually Corrected'),
    }

    _defaults = {
        'corrected': lambda *a: False,
        'reversal': lambda *a: False,
        'have_an_historic': lambda *a: False,
        'is_corrigible': lambda *a: True,
        'last_cor_was_only_analytic': lambda *a: False,
        'is_manually_corrected': lambda *a: False,
    }

    def copy(self, cr, uid, aml_id, default=None, context=None):
        """
        Copy a move line with draft state. Do not create a new analytic_distribution from line if we come from a correction.
        """
        if default is None:
            default = {}
        if 'omit_analytic_distribution' in context and context.get('omit_analytic_distribution') is True:
            default.update({
                'analytic_distribution_id': False,
            })
        default.update({
            'state': 'draft',
            'have_an_historic': False,
            'corrected': False,
            'corrected_upstream': False,
            'reversal': False,
            'last_cor_was_only_analytic': False,
            'is_manually_corrected': False,
        })
        if 'exported' not in default:
            default['exported'] = False

        # Add default date if no one given
        if not 'date' in default:
            default.update({'date': strftime('%Y-%m-%d')})
        return super(account_move_line, self).copy(cr, uid, aml_id, default, context=context)

    def get_corrections_history(self, cr, uid, ids, context=None):
        """
        Give for each line their history by using "corrected_line_id" field to browse lines
        Return something like that:
            {id1: [line_id, another_line_id], id2: [a_line_id, other_line_id]}
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for ml in self.browse(cr, uid, ids, context=context):
            upstream_line_ids = []
            downstream_line_ids = []
            # Get upstream move lines
            line = ml
            while line != None:
                if line:
                    # Add line to result
                    upstream_line_ids.append(line.id)
                    # Add reversal line to result
                    reversal_ids = self.search(cr, uid, [('move_id', '=', line.move_id.id), ('reversal', '=', True)], context=context)
                    if reversal_ids:
                        upstream_line_ids.append(reversal_ids)
                if line.corrected_line_id:
                    line = line.corrected_line_id
                else:
                    line = None
            # Get downstream move lines
            sline_ids = [ml.id]
            while sline_ids != None:
                operator = 'in'
                if len(sline_ids) == 1:
                    operator = '='
                search_ids = self.search(cr, uid, [('corrected_line_id', operator, sline_ids)], context=context)
                if search_ids:
                    # Add line to result
                    downstream_line_ids.append(search_ids)
                    # Add reversal line to result
                    for dl in self.browse(cr, uid, search_ids, context=context):
                        reversal_ids = self.search(cr, uid, [('move_id', '=', dl.move_id.id), ('reversal', '=', True)], context=context)
                        downstream_line_ids.append(reversal_ids)
                    sline_ids = search_ids
                else:
                    # use case of a refund cancel/modify: no COR line exists but the "reversal" line should appear in the wizard
                    search_reversal_ids = \
                        self.search(cr, uid,
                                    [('reversal_line_id', operator, sline_ids)],  # invoice_line_id not used as won't exist in upper inst.
                                    order='NO_ORDER', context=context)
                    if search_reversal_ids:
                        # Add line to result
                        downstream_line_ids.append(search_reversal_ids)
                        sline_ids = search_reversal_ids
                    else:
                        sline_ids = None
            # Add search result to res
            res[str(ml.id)] = list(set(flatten(upstream_line_ids) + flatten(downstream_line_ids))) # downstream_line_ids needs to be simplify with flatten
        return res

    def get_first_corrected_line(self, cr, uid, ids, context=None):
        """
        For each move line, give the first line from which all corrections have been done.
        Example:
         - line 1 exists.
         - line 1 was corrected by line 3.
         - line 5 correct line 3.
         - line 8 correct line 5.
         - get_first_corrected_line of line 8 should give line 1.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            # Get upstream move lines
            line = ml
            corrected_line_id = ml.corrected_line_id and ml.corrected_line_id
            while corrected_line_id != False:
                line = line.corrected_line_id or False
                if not line:
                    corrected_line_id = False
                    continue
                corrected_line_id = line.corrected_line_id and line.corrected_line_id.id or False
            res[str(ml.id)] = False
            if line:
                res[str(ml.id)] = line.id
        return res

    def button_do_accounting_corrections(self, cr, uid, ids, context=None):
        """
        Launch accounting correction wizard to do reverse or correction on selected move line.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, int):
            ids = [ids]
        # Retrieve some values
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        ml = self.browse(cr, uid, ids[0])
        # Create wizard
        wizard = wiz_obj.create(cr, uid, {'move_line_id': ids[0], 'from_ji': True}, context=context)
        # Change wizard state in order to change date requirement on wizard
        wiz_obj.write(cr, uid, [wizard], {'state': 'open'}, context=context)
        # Update context
        # UFTP-354: Delete "from_web_menu" to avoid conflict with UFTP-262
        if 'from_web_menu' in context:
            del(context['from_web_menu'])
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Change context if account special type is "donation"
        if ml.account_id and ml.account_id.type_for_register and ml.account_id.type_for_register == 'donation':
            wiz_obj.write(cr, uid, [wizard], {'from_donation': True}, context=context)
        # Update context to inform wizard we come from a correction wizard
        context.update({'from_correction': True,})
        return {
            'name': _("Accounting Corrections Wizard (from Journal Items)"),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.journal.items.corrections',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wizard],
            'context': context,
        }

    def button_open_corrections(self, cr, uid, ids, context=None):
        """
        Open all corrections linked to the given one
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, int):
            ids = [ids]
        # if JI was marked as corrected manually: display the Reverse Manual Corr. wizard instead of the History wizard
        # except if it's a project line that was marked as Corrected in a upper level
        reverse_corr_wiz_obj = self.pool.get('reverse.manual.correction.wizard')
        user_obj = self.pool.get('res.users')
        display_reverse_corr_wiz = False
        if len(ids) == 1:
            ml = self.read(cr, uid, ids[0], ['is_manually_corrected', 'corrected_upstream'], context=context)
            if ml['is_manually_corrected']:
                company = user_obj.browse(cr, uid, uid, context=context).company_id
                level = company.instance_id and company.instance_id.level or ''
                if not ml['corrected_upstream'] or level != 'project':
                    display_reverse_corr_wiz = True
        if display_reverse_corr_wiz:
            context.update({
                'active_id': ids[0],
                'active_ids': ids,
            })
            reverse_corr_wizard = reverse_corr_wiz_obj.create(cr, uid, {}, context=context)
            return {
                'name': _("History Move Line"),  # same title as the History Wizard
                'type': 'ir.actions.act_window',
                'res_model': 'reverse.manual.correction.wizard',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [reverse_corr_wizard],
                'context': context,
                'target': 'new',
            }
        # Prepare some values
        domain_ids = []
        # Search ids to be open
        res_ids = self.get_corrections_history(cr, uid, ids, context=context)
        # For each ids, add elements to the domain
        for el in res_ids:
            domain_ids.append(res_ids[el])
        # If no result, just display selected ids
        if not domain_ids:
            domain_ids = ids
        # Create domain
        domain = [('id', 'in', flatten(domain_ids))]#, ('reversal', '=', False)]
        # Update context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # disable the default filters
        new_context = context.copy()
        for c in context:
            if c.startswith('search_default_'):
                del new_context[c]
        # Display the result
        return {
            'name': "History Move Line",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'target': 'new',
            'view_type': 'form',
            'view_mode': 'tree',
            'context': new_context,
            'domain': domain,
        }
        return True

    def _get_third_party_fields(self, third_party):
        """
        Returns the partner_id, employee_id, transfer_journal_id corresponding to the third_party in parameter
        """
        partner_id = False
        employee_id = False
        transfer_journal_id = False
        if third_party:
            if third_party._table_name == 'res.partner':
                partner_id = third_party.id
            elif third_party._table_name == 'hr.employee':
                employee_id = third_party.id
            elif third_party._table_name == 'account.journal':
                transfer_journal_id = third_party.id
        return partner_id, employee_id, transfer_journal_id

    def update_st_line(self, cr, uid, ids, context=None):
        """
        Updates the "corrected_st_line_id" on the JI
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Update lines
        for ml in self.browse(cr, uid, ids, context=context):
            # in order to update hard posted line (that's forbidden!), we use a tip: add from_correction in context
            context.update({'from_correction': True})
            # Search lines that are correction of this one (in order to add some fields)
            corrected_line_ids = self.search(cr, uid, [('corrected_line_id', '=', ml.id)], context=context)
            # Case where this move line have a link to some statement lines
            if ml.statement_id and ml.move_id.statement_line_ids:
                for st_line in ml.move_id.statement_line_ids:
                    if st_line.cash_return_move_line_id:
                        if st_line.cash_return_move_line_id.id == ml.id:
                            # we informs new move line that it have correct a statement line
                            self.write(cr, uid, corrected_line_ids, {'corrected_st_line_id': st_line.id}, context=context)
                            break
                    elif not st_line.from_cash_return:
                        #US-303: If not the case, then we inform the new move line that it has corrected a statement line
                        self.write(cr, uid, corrected_line_ids, {'corrected_st_line_id': st_line.id}, context=context)
        return True

    def correct_aml(self, cr, uid, ids, date=None, new_account_id=None, distrib_id=False, new_third_party=None, context=None):
        r"""
        Corrects the G/L account and/or the Third Party of the JIs having their ids in param.
        Generates the related REV/COR lines.

        /!\ WARNING /!\
        new_third_party is a partner_type, i.e. it can be a res.partner, hr.employee... If it is None (= no 3d party
        passed as a parameter): no change regarding 3d Party should be made, whereas if it is False/empty/browse_null,
        the COR line must have an empty Third Party.
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not date:
            date = strftime('%Y-%m-%d')
        if not new_account_id:
            raise osv.except_osv(_('Error'), _('No new account_id given!'))

        # Prepare some values
        move_obj = self.pool.get('account.move')
        j_obj = self.pool.get('account.journal')
        al_obj = self.pool.get('account.analytic.line')
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        success_move_line_ids = []

        # New account
        # Check the compatibility between the new account selected for the COR lines and the posting date
        self._check_date(cr, uid, {'date': date, 'account_id': new_account_id}, context=context)
        new_account = self.pool.get('account.account').browse(cr, uid,
                                                              new_account_id, context=context)

        # Search correction journal
        j_corr_id = j_obj.get_correction_journal(cr, uid, context=context)

        # Search extra-accounting journal
        j_extra_id = j_obj.get_correction_journal(cr, uid, corr_type='extra', context=context)

        # Search for the "Correction HQ" journal
        hq_corr_journal_id = j_obj.get_correction_journal(cr, uid, corr_type='hq', context=context)

        # Search attached period
        period_obj = self.pool.get('account.period')
        period_ids = period_obj.search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)],
                                       context=context, limit=1, order='date_start, name')
        period_number = period_ids and period_obj.browse(cr, uid, period_ids, context)[0].number or False

        # Browse all given move line for correct them
        for ml in self.browse(cr, uid, ids, context=context):
            # Abort process if this move line was corrected before
            if ml.corrected:
                continue

            self.pool.get('finance.tools').check_correction_date_fy(ml.date, date, context=context)

            # UTP-1187 check corrected line has an AD if need one
            # + BKLG-19/3: search only for fp ones as 'free' are not synced to
            # HQ and initial_al_ids[0] is used to set reversal_origin
            initial_al_ids = al_obj.search(cr, uid,
                                           [('move_id', '=', ml.id), ('account_id.category', '=', 'FUNDING')],
                                           context=context)
            # Note: this search result will be used near end of this function
            # (see # Change analytic lines that come from)
            if not distrib_id and \
                not initial_al_ids and new_account and \
                    new_account.is_analytic_addicted:
                # we check only if no distrib_id arg passed to function
                msg = _("The line '%s' with the new account '%s - %s' needs an" \
                        " analytic distribution (you may have changed the account from" \
                        " one with no AD required to a new one with AD required).")
                raise osv.except_osv(_('Error'), msg % (ml.move_id.name,
                                                        new_account.code, new_account.name, ))

            # If this line was already been corrected, check the first analytic line ID (but not the first first analytic line)
            first_analytic_line_id = False
            first_ana_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', '=', ml.id)])
            if first_ana_ids:
                first_ana = self.pool.get('account.analytic.line').browse(cr, uid, first_ana_ids)[0]
                if first_ana.last_corrected_id:
                    first_analytic_line_id = first_ana.last_corrected_id.id
            # Retrieve right journal
            journal_id = j_corr_id

            # Abort process if the move line is a donation account (type for specific treatment) and that new account is not a donation account
            if ml.account_id.type_for_register == 'donation':
                journal_id = j_extra_id
                if not journal_id:
                    raise osv.except_osv(_('Error'), _('No OD-Extra Accounting Journal found!'))
                if new_account.type_for_register != 'donation':
                    raise osv.except_osv(_('Error'), _('You come from a donation account. And new one is not a Donation account. You should give a Donation account!'))

            # Correction: of an HQ entry, or of a correction of an HQ entry
            if ml.journal_id.type in ('hq', 'correction_hq'):
                journal_id = hq_corr_journal_id
                if not journal_id:
                    raise osv.except_osv(_('Error'), _('No "correction HQ" journal found!'))

            if not journal_id:
                raise osv.except_osv(_('Error'), _('No correction journal found!'))

            # Abort process if the move line have some analytic line that have one line with a FP used in a soft/hard closed contract
            aal_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', '=', ml.id)])
            for aal in self.pool.get('account.analytic.line').browse(cr, uid, aal_ids):
                check_accounts = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [aal.account_id.id])
                if check_accounts and aal.account_id.id in check_accounts:
                    raise osv.except_osv(_('Warning'), _('You cannot change this entry since one of its accounts is '
                                                         'used in a closed financing contract.'))
            # (US-815) use the right period for December HQ Entries
            period_id_dec_hq_entry = False
            if period_number == 12 and context.get('period_id_for_dec_hq_entries', False):
                period_id_dec_hq_entry = context['period_id_for_dec_hq_entries']
            # Create a new move
            move_id = move_obj.create(cr, uid,{'journal_id': journal_id, 'period_id': period_id_dec_hq_entry or period_ids[0], 'date': date, 'document_date': ml.document_date}, context=context)
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': date,
                'document_date': ml.document_date,
                'journal_id': journal_id,
                'period_id': period_id_dec_hq_entry or period_ids[0],
            }
            # Copy the line
            context.update({'omit_analytic_distribution': False})
            rev_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            correction_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            # Do the reverse
            name = self.join_without_redundancy(ml.name, 'REV')
            amt = -1 * ml.amount_currency
            curr_date = currency_date.get_date(self, cr, ml.document_date, ml.date, source_date=ml.source_date)
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': journal_id,
                'name': name,
                'reversal_line_id': ml.id,
                'account_id': ml.account_id.id,
                'source_date': curr_date,
                'reversal': True,
                'document_date': ml.document_date,
                'reference': ml.move_id and ml.move_id.name or '',
                'ref': ml.move_id and ml.move_id.name or '',
            })
            self.write(cr, uid, [rev_line_id], vals, context=context, check=False, update_check=False)
            # Do the correction line
            name = self.join_without_redundancy(ml.name, 'COR')
            cor_vals = {
                'name': name,
                'journal_id': journal_id,
                'corrected_line_id': ml.id,
                'account_id': new_account_id,
                'source_date': curr_date,
                'have_an_historic': True,
                'document_date': ml.document_date,
                'reference': ml.move_id and ml.move_id.name or '',
                'ref': ml.move_id and ml.move_id.name or '',
            }
            if distrib_id:
                cor_vals['analytic_distribution_id'] = distrib_id
            elif ml.analytic_distribution_id:
                cor_vals['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, ml.analytic_distribution_id.id, {}, context=context)
            if new_third_party is not None:  # if None: no correction on Third Party should be made
                new_partner_id, new_employee_id, new_transfer_journal_id = self._get_third_party_fields(new_third_party)
                cor_vals.update({
                    'partner_id': new_partner_id,
                    'employee_id': new_employee_id,
                    'transfer_journal_id': new_transfer_journal_id,
                })
                # if no Third Party: reset partner_txt (this field is automatically updated only when there is one)
                if not new_partner_id and not new_employee_id and not new_transfer_journal_id:
                    cor_vals['partner_txt'] = ''
            # set the partner_type_mandatory tag
            third_required = False
            if new_account.type_for_register in ['advance', 'down_payment', 'payroll', 'transfer', 'transfer_same']:
                third_required = True
            cor_vals['partner_type_mandatory'] = third_required
            self.write(cr, uid, [correction_line_id], cor_vals, context=context, check=False, update_check=False)
            # check the account compatibility with the Third Party on the COR line created
            correction_line = self.browse(cr, uid, correction_line_id, context=context)
            wiz_obj._check_account_partner_compatibility(cr, uid, new_account, correction_line, context)
            if ml.statement_id:
                self.update_st_line(cr, uid, [ml.id], context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [ml.id], {'corrected': True, 'have_an_historic': True,}, context=context, check=False, update_check=False)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
            # Change analytic lines that come from:
            #- initial move line: is_reallocated is True
            #- reversal move line: is_reversal is True + initial analytic line
            #- correction line: change is_reallocated and is_reversal to False
            #- old reversal line: reset is_reversal to True (lost previously in validate())
            if initial_al_ids:  # as initial AD
                search_datas = [(ml.id, {'is_reallocated': True}),
                                (rev_line_id, {'is_reversal': True, 'reversal_origin': initial_al_ids[0]}),
                                (correction_line_id, {'is_reallocated': False, 'is_reversal': False, 'last_corrected_id': initial_al_ids[0]})]
                # If line is already a correction, take the previous reversal move line id
                # (UF_1234: otherwise, the reversal is not set correctly)
                if ml.corrected_line_id:
                    old_reverse_ids = self.search(cr, uid, [('reversal_line_id', '=', ml.corrected_line_id.id)])
                    if len(old_reverse_ids) > 0:
                        search_datas += [(old_reverse_ids[0], {'is_reversal': True, 'reversal_origin': first_analytic_line_id})]
                for search_data in search_datas:
                    # keep initial analytic line as corrected line if it the 2nd or more correction on this line
                    if ml.corrected_line_id and search_data[0] == ml.id and first_analytic_line_id:
                        search_data[1].update({'last_corrected_id': first_analytic_line_id, 'have_an_historic': True,})
                    search_ids = al_obj.search(cr, uid, [('move_id', '=', search_data[0]), ('reversal_origin', '=', False), ('last_corrected_id', '=', False)])
                    if search_ids:
                        al_obj.write(cr, uid, search_ids, search_data[1])
            # Add this line to succeded lines
            success_move_line_ids.append(ml.id)
            # Mark it as "corrected_upstream" if needed
            self.corrected_upstream_marker(cr, uid, [ml.id], context=context)
        return success_move_line_ids

    def correct_account(self, cr, uid, aml_ids, date=None, new_account_id=None, distrib_id=False, context=None):
        """
        Corrects the G/L account (only) of the amls
        """
        return self.correct_aml(cr, uid, aml_ids, date=date, new_account_id=new_account_id, distrib_id=distrib_id, context=context)

    def corrected_upstream_marker(self, cr, uid, ids, context=None):
        """
        Check if we are in a COORDO / HQ instance. If yes, set move line(s) as corrected upstream.
        """
        # Some check
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        # Check if we come from COORDO/HQ instance
        if company and company.instance_id and company.instance_id.level in ['section', 'coordo']:
            # UF-1746: Set also all other move lines as corrected upstream to disallow projet user to correct any move line of this move.
            move_ids = [x and x.get('move_id', False) and x.get('move_id')[0] for x in self.read(cr, uid, ids, ['move_id'], context=context)]
            ml_ids = self.search(cr, uid, [('move_id', 'in', move_ids), ('corrected_upstream', '!=', True)])
            self.write(cr, uid, ml_ids, {'corrected_upstream': True}, check=False, update_check=False, context=context)
        return True

    def set_as_corrected(self, cr, uid, ji_ids, manual=True, context=None):
        """
        Sets the JIs and their related AJIs as Corrected according to the following rules:
        - if one of the JIs or AJIs has already been corrected or if the account can't be corrected it raises an error
        - if manual = True, the Correction will be set as Manual (= the user will be able to reverse it manually)
        """
        if context is None:
            context = {}
        if isinstance(ji_ids, int):
            ji_ids = [ji_ids]
        aal_obj = self.pool.get('account.analytic.line')
        for ji in self.browse(cr, uid, ji_ids, fields_to_fetch=['corrected', 'move_id', 'account_id'], context=context):
            # check that the account can be corrected
            if ji.account_id.is_not_hq_correctible:
                raise osv.except_osv(_('Error'), _('The account "%s - %s" is set as "Prevent correction on '
                                                   'account codes".') % (ji.account_id.code, ji.account_id.name))
            # check that the JI isn't already corrected
            if ji.corrected:
                raise osv.except_osv(_('Error'), _('The entry %s has already been corrected.') % ji.move_id.name)
            # check that none of the AJIs linked to the JIs has already been reallocated
            aji_ids = aal_obj.search(cr, uid, [('move_id', '=', ji.id)], order='NO_ORDER', context=context)
            for aji in aal_obj.read(cr, uid, aji_ids, ['is_reallocated'], context=context):
                if aji['is_reallocated']:
                    raise osv.except_osv(_('Error'), _('One AJI related to the entry %s has already been corrected.') % ji.move_id.name)
            # set the JI as corrected
            manual_corr_vals = {'is_manually_corrected': manual,
                                'corrected': True,  # is_corrigible will be seen as "False"
                                'have_an_historic': True}
            # write on JI without recreating AJIs
            self.write(cr, uid, ji.id, manual_corr_vals, context=context, check=False, update_check=False)
            # Set the "corrected_upstream" flag on the JI if necessary
            # (so that project lines marked as corrected in a upper level can't be "uncorrected" in project)
            self.corrected_upstream_marker(cr, uid, [ji.id], context=context)
            # set the AJIs as corrected
            aal_obj.write(cr, uid, aji_ids, {'is_reallocated': True}, context=context)


account_move_line()


class reverse_manual_correction_wizard(osv.osv_memory):
    _name = 'reverse.manual.correction.wizard'
    _description = 'Manual Correction Reversal Wizard'

    _columns = {
    }

    _defaults = {
    }

    def reverse_manual_correction(self, cr, uid, ids, context=None):
        """
        Cancels the "Manual Correction" on the JI and its AJIs so that they can be re-corrected
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        aal_obj = self.pool.get('account.analytic.line')
        ji_id = context.get('active_id', False)
        if ji_id:
            # set the JI as non-corrected
            is_cor_line = False
            if aml_obj.read(cr, uid, ji_id, ['corrected_line_id'], context=context)['corrected_line_id']:
                # if a COR line was corrected manually: the History Wizard must still appear if manual corr. is removed
                is_cor_line = True
            reverse_corr_vals = {'is_manually_corrected': False,
                                 'corrected': False,  # is_corrigible will be seen as "True"
                                 'have_an_historic': is_cor_line,
                                 'corrected_upstream': False}
            # add a tag in context to allow the write on a system JI (ex: to cancel a manual corr. done on a SI line)
            context.update({'from_manual_corr_reversal': True})
            aml_obj.write(cr, uid, ji_id, reverse_corr_vals, context=context, check=False, update_check=False)
            # set the AJIs as non-corrected
            aji_ids = aal_obj.search(cr, uid, [('move_id', '=', ji_id)], order='NO_ORDER', context=context)
            aal_obj.write(cr, uid, aji_ids, {'is_reallocated': False}, context=context)
        return {'type': 'ir.actions.act_window_close'}


reverse_manual_correction_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
