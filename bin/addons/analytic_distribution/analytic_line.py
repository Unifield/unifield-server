# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

class analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    def _get_fake_is_fp_compat_with(self, cr, uid, ids, field_name, args, context=None):
        """
        Fake method for 'is_fp_compat_with' field
        """
        res = {}
        for i in ids:
            res[i] = ''
        return res

    def _search_is_fp_compat_with(self, cr, uid, obj, name, args, context=None):
        """
        Return domain that permit to give all analytic line compatible with a given FP.
        """
        if not args:
            return []
        res = []
        # We just support '=' operator
        for arg in args:
            if not arg[1]:
                raise osv.except_osv(_('Warning'), _('Some search args are missing!'))
            if arg[1] not in ['=',]:
                raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
            if not arg[2]:
                raise osv.except_osv(_('Warning'), _('Some search args are missing!'))
            analytic_account = self.pool.get('account.analytic.account').browse(cr, uid, arg[2])
            tuple_list = [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in analytic_account.tuple_destination_account_ids if not x.disabled]
            cost_center_ids = [x and x.id for x in analytic_account.cost_center_ids]
            for cc in cost_center_ids:
                for t in tuple_list:
                    if res:
                        res = ['|'] + res
                    res.append('&')
                    res.append('&')
                    res.append(('cost_center_id', '=', cc))
                    res.append(('general_account_id', '=', t[0]))
                    res.append(('destination_id', '=', t[1]))
        return res

    def _journal_type_get(self, cr, uid, context=None):
        """
        Get journal types
        """
        return self.pool.get('account.analytic.journal').get_journal_type(cr, uid, context)

    def _get_entry_sequence(self, cr, uid, ids, field_names, args, context=None):
        """
        Give right entry sequence. Either move_id.move_id.name,
        or commitment_line_id.commit_id.name, or
        if the line was imported, the stored name
        """
        if not context:
            context = {}
        res = {}
        for l in self.browse(cr, uid, ids, context):
            if l.entry_sequence:
                res[l.id] = l.entry_sequence
            else:
                res[l.id] = ''
                if l.move_id:
                    res[l.id] = l.move_id.move_id.name
                elif l.commitment_line_id:
                    res[l.id] = l.commitment_line_id.commit_id.name
                elif l.imported_commitment:
                    res[l.id] = l.imported_entry_sequence
                elif not l.move_id:
                    # UF-2217
                    # on create the value is inserted by a sql query, so we can retreive it after the insertion
                    # the field has store=True so we don't create a loop
                    # on write the value is not updated by the query, the method always returns the value set at creation
                    res[l.id] = l.entry_sequence
        return res

    def _get_period_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Fetch period_id from:
        - move_id
        - commitment_line_id
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        period_obj = self.pool.get('account.period')
        for al in self.browse(cr, uid, ids, context):
            res[al.id] = False
            # US-945: Consider IN PRIORITY the new physical real period field
            # (else keep default behaviour)
            if al.real_period_id:
                res[al.id] = al.real_period_id.id
            else:
                # UTP-943: Since this ticket, we search period regarding analytic line posting date.
                period_ids = period_obj.get_period_from_date(cr, uid, date=al.date)
                if period_ids:
                    res[al.id] = period_ids[0]
        return res

    def _search_period_id(self, cr, uid, obj, name, args, context=None):
        """
        Search period regarding date.
        First fetch period date_start and date_stop.
        Then check that analytic line have a posting date bewteen these two date.
        Finally do this check as "OR" for each given period.
        Examples:
        - Just january:
        ['&', ('date', '>=', '2013-01-01'), ('date', '<=', '2013-01-31')]
        - January + February:
        ['|', '&', ('date', '>=', '2013-01-01'), ('date', '<=', '2013-01-31'), '&', ('date', '>=', '2013-02-01'), ('date', '<=', '2013-02-28')]
        - January + February + March
        ['|', '|', '&', ('date', '>=', '2013-01-01'), ('date', '<=', '2013-01-31'), '&', ('date', '>=', '2013-02-01'), ('date', '<=', '2013-02-28'), '&', ('date', '>=', '2013-03-01'), ('date', '<=', '2013-03-31')]

        (US-650) Management of "NOT IN". For example to exclude Jan 2016 and Oct 2015:
        ['&', '|', ('date', '<', '2016-01-01'), ('date', '>', '2016-01-31'), '|', ('date', '<', '2015-10-01'), ('date', '>', '2015-10-31')]

        AFTER US-945:
        We use the real_period_id.
        For the old entries this field doesn't exist: we keep using the posting dates.
        For example to include a Period 13:
        ['|', ('real_period_id', '=', 13), '&', '&', ('real_period_id', '=', False), ('date', '>=', '2016-12-01'), ('date', '<=', '2016-12-31')]
        """
        # Checks
        if context is None:
            context = {}
        if not args:
            return []
        new_args = []
        period_obj = self.pool.get('account.period')
        for arg in args:
            if len(arg) == 3 and arg[1] in ['=', 'in', 'not in']:
                periods = arg[2]
                if isinstance(periods, (int, long)):
                    periods = [periods]
                if len(periods) > 1:
                    for null in range(len(periods) - 1):
                        if arg[1] == 'not in':
                            new_args.append('&')
                        else:
                            new_args.append('|')
                for p_id in periods:
                    period = period_obj.browse(cr, uid, [p_id])[0]
                    if arg[1] == 'not in':
                        new_args.append('|')
                        new_args.append('|')
                        new_args.append(('date', '<', period.date_start))
                        new_args.append(('date', '>', period.date_stop))
                        new_args.append('&')
                        new_args.append(('real_period_id', '!=', False))
                        new_args.append(('real_period_id', '!=', p_id))
                    else:
                        new_args.append('|')
                        new_args.append(('real_period_id', '=', p_id))
                        # or no real period and in period range
                        # for previous US-945 entries
                        new_args.append('&')
                        new_args.append('&')
                        new_args.append(('real_period_id', '=', False))
                        new_args.append(('date', '>=', period.date_start))
                        new_args.append(('date', '<=', period.date_stop))
        return new_args

    def _get_from_commitment_line(self, cr, uid, ids, field_name, args, context=None):
        """
        Check if line comes from a 'engagement' journal type. If yes, True. Otherwise False.
        """
        if context is None:
            context = {}
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.journal_id.type == 'engagement':
                res[al.id] = True
        return res

    def _get_is_unposted(self, cr, uid, ids, field_name, args, context=None):
        """
        Check journal entry state. If unposted: True, otherwise False.
        A line that comes from a commitment cannot be posted. So it's always to False.
        """
        if context is None:
            context = {}
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.move_state != 'posted' and al.journal_id.type != 'engagement':
                res[al.id] = True
        return res

    _columns = {
        'commitment_line_id': fields.many2one('account.commitment.line', string='Commitment Voucher Line', ondelete='cascade'),
        'is_fp_compat_with': fields.function(_get_fake_is_fp_compat_with, fnct_search=_search_is_fp_compat_with, method=True, type="char", size=254, string="Is compatible with some FP?"),
        'move_state': fields.related('move_id', 'move_id', 'state', type='selection', size=64, relation="account.move.line", selection=[('draft', 'Unposted'), ('posted', 'Posted')], string='Journal Entry state', readonly=True, help="Indicates that this line come from an Unposted Journal Entry."),
        'journal_type': fields.related('journal_id', 'type', type='selection', selection=_journal_type_get, string="Journal Type", readonly=True, \
                                       help="Indicates the Journal Type of the Analytic journal item"),
        'entry_sequence': fields.function(_get_entry_sequence, method=True, type='text', string="Entry Sequence", readonly=True, store=True),
        'period_id': fields.function(_get_period_id, fnct_search=_search_period_id, method=True, string="Period", readonly=True, type="many2one", relation="account.period", store=False),
        'fiscalyear_id': fields.related('period_id', 'fiscalyear_id', type='many2one', relation='account.fiscalyear', string='Fiscal Year', store=False),
        'from_commitment_line': fields.function(_get_from_commitment_line, method=True, type='boolean', string="Commitment?"),
        'is_unposted': fields.function(_get_is_unposted, method=True, type='boolean', string="Unposted?"),
        'imported_commitment': fields.boolean(string="From imported commitment?"),
        'imported_entry_sequence': fields.text("Imported Entry Sequence"),
        # US-945: real physical period wrapper for the period_id calculated field
        'real_period_id': fields.many2one('account.period', 'Real period', select=1),
    }

    _defaults = {
        'imported_commitment': lambda *a: False,
    }

    def create(self, cr, uid, vals, context=None):
        """
        Check date for given date and given account_id
        """
        # Some verifications
        if not context:
            context = {}
        # Default behaviour
        res = super(analytic_line, self).create(cr, uid, vals, context=context)
        # Check soft/hard closed contract
        sql = """SELECT fcc.id
        FROM financing_contract_funding_pool_line fcfpl, account_analytic_account a, financing_contract_format fcf, financing_contract_contract fcc
        WHERE fcfpl.funding_pool_id = a.id
        AND fcfpl.contract_id = fcf.id
        AND fcc.format_id = fcf.id
        AND a.id = %s
        AND fcc.state in ('soft_closed', 'hard_closed');"""
        cr.execute(sql, tuple([vals.get('account_id')]))
        sql_res = cr.fetchall()
        if sql_res:
            account = self.pool.get('account.analytic.account').browse(cr, uid, vals.get('account_id'))
            contract = self.pool.get('financing.contract.contract').browse(cr, uid, sql_res[0][0])
            raise osv.except_osv(_('Warning'), _('Selected Funding Pool analytic account (%s) is blocked by a soft/hard closed contract: %s') % (account and account.code or '', contract and contract.name or ''))
        return res

    def update_account(self, cr, uid, ids, account_id, date=False, context=None):
        """
        Update account on given analytic lines with account_id on given date
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not account_id:
            return False
        if not date:
            date = strftime('%Y-%m-%d')

        # Prepare some value
        account = self.pool.get('account.analytic.account').browse(cr, uid, [account_id], context)[0]
        context.update({'from': 'mass_reallocation'}) # this permits reallocation to be accepted when rewrite analaytic lines
        move_prefix = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.move_prefix

        aaj_obj = self.pool.get('account.analytic.journal')
        correction_journal_ids = aaj_obj.search(cr, uid, [('type', '=', 'correction'), ('is_current_instance', '=', True)])
        correction_journal_id = correction_journal_ids and correction_journal_ids[0] or False
        if not correction_journal_id:
            raise osv.except_osv(_('Error'), _('No analytic journal found for corrections!'))

        # sequence info from GL journal
        aj_obj = self.pool.get('account.journal')
        gl_correction_journal_ids = aj_obj.search(cr, uid, [('type', '=', 'correction'), ('is_current_instance', '=', True)])
        gl_correction_journal_id = gl_correction_journal_ids and gl_correction_journal_ids[0] or False
        if not gl_correction_journal_id:
            raise osv.except_osv(_('Error'), _('No GL journal found for corrections!'))
        gl_correction_journal_rec = aj_obj.browse(cr, uid, gl_correction_journal_id, context=context)

        # Process lines
        for aline in self.browse(cr, uid, ids, context=context):
            if account.category in ['OC', 'DEST']:
                # Period verification
                period = aline.period_id
                # Prepare some values
                fieldname = 'cost_center_id'
                if account.category == 'DEST':
                    fieldname = 'destination_id'

                # update or reverse ?
                update = period and period.state not in ['done', 'mission-closed']
                if aline.journal_id.type == 'hq':
                    # US-773/2: if HQ entry always like period closed fashion
                    update = False

                if update:
                    # not mission close: override line
                    # Update account # Date: UTP-943 speak about original date for non closed periods
                    vals = {
                        fieldname: account_id,
                        'date': aline.date,
                        'source_date': aline.source_date or aline.date,
                    }
                    self.write(cr, uid, [aline.id], vals, context=context)
                # else reverse line before recreating them with right values
                else:
                    # mission close or + or HQ entry: reverse

                    # compute entry sequence
                    seq_num_ctx = period and {'fiscalyear_id': period.fiscalyear_id.id} or None
                    seqnum = self.pool.get('ir.sequence').get_id(cr, uid, gl_correction_journal_rec.sequence_id.id, context=seq_num_ctx)
                    entry_seq = "%s-%s-%s" % (move_prefix, gl_correction_journal_rec.code, seqnum)

                    # First reverse line
                    rev_ids = self.pool.get('account.analytic.line').reverse(cr, uid, [aline.id], posting_date=date)
                    # UTP-943: Shoud have a correction journal on these lines
                    self.pool.get('account.analytic.line').write(cr, uid, rev_ids, {'journal_id': correction_journal_id, 'is_reversal': True, 'reversal_origin': aline.id, 'last_corrected_id': False})
                    # UTP-943: Check that period is open
                    correction_period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, date, context=context)
                    if not correction_period_ids:
                        raise osv.except_osv(_('Error'), _('No period found for this date: %s') % (date,))
                    for p in self.pool.get('account.period').browse(cr, uid, correction_period_ids, context=context):
                        if p.state != 'draft':
                            raise osv.except_osv(_('Error'), _('Period (%s) is not open.') % (p.name,))
                    # then create new lines
                    cor_name = self.pool.get('account.analytic.line').join_without_redundancy(aline.name, 'COR')
                    cor_ids = self.pool.get('account.analytic.line').copy(cr, uid, aline.id, {fieldname: account_id, 'date': date,
                                                                                              'source_date': aline.source_date or aline.date, 'journal_id': correction_journal_id,
                                                                                              'name': cor_name, 'ref': aline.entry_sequence, 'real_period_id': correction_period_ids[0]}, context=context)
                    self.pool.get('account.analytic.line').write(cr, uid, cor_ids, {'last_corrected_id': aline.id})
                    # finally flag analytic line as reallocated
                    self.pool.get('account.analytic.line').write(cr, uid, [aline.id], {'is_reallocated': True})

                    if isinstance(rev_ids, (int, long, )):
                        rev_ids = [rev_ids]
                    if isinstance(cor_ids, (int, long, )):
                        cor_ids = [cor_ids]
                    for rev_cor_id in rev_ids + cor_ids:
                        cr.execute('update account_analytic_line set entry_sequence = %s where id = %s', (entry_seq, rev_cor_id))
            else:
                # Update account
                self.write(cr, uid, [aline.id], {'account_id': account_id}, context=context)
            # Set line as corrected upstream if we are in COORDO/HQ instance
            if aline.move_id:
                self.pool.get('account.move.line').corrected_upstream_marker(cr, uid, [aline.move_id.id], context=context)
        return True

    def check_analytic_account(self, cr, uid, ids, account_id, wiz_date, context=None):
        """
        Analytic distribution validity verification with given account for given ids.
        Return all valid ids.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        account = self.pool.get('account.analytic.account').read(cr, uid, account_id, ['category', 'date_start', 'date'], context=context)
        account_type = account and account.get('category', False) or False
        res = []
        if not account_type:
            return res
        try:
            msf_private_fund = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                                   'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_private_fund = 0
        expired_date_ids = []
        date_start = account and account.get('date_start', False) or False
        date_stop = account and account.get('date', False) or False
        # Date verification for all lines and fetch all necessary elements sorted by analytic distribution
        for aline in self.browse(cr, uid, ids):
            # UTP-800: Change date comparison regarding FP. If FP, use document date. Otherwise use date.
            aline_cmp_date = aline.date
            if account_type == 'FUNDING':
                aline_cmp_date = aline.document_date
            # Add line to expired_date if date is not in date_start - date_stop
            # since US-711 date_stop is to be excluded itself as a frontier
            # => >= date_stop vs > date_stop
            # => http://jira.unifield.org/browse/US-711?focusedCommentId=45744&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-45744
            if account_type in ['OC', 'DEST']:
                if aline.journal_id.type == 'hq' or aline.period_id and aline.period_id.state in ['done', 'mission-closed']:
                    aline_cmp_date = wiz_date
                    # these lines will be reverted, check if the reverted line is active
                    oc_dest_date_start = max(aline.cost_center_id.date_start, aline.destination_id.date_start)
                    oc_dest_date_stop = min(aline.cost_center_id.date or '9999-01-01', aline.destination_id.date or '9999-01-01')
                    if (oc_dest_date_start and wiz_date < oc_dest_date_start) or (oc_dest_date_stop and wiz_date >= oc_dest_date_stop):
                        expired_date_ids.append(aline.id)
            if (date_start and aline_cmp_date < date_start) or (date_stop and aline_cmp_date >= date_stop):
                expired_date_ids.append(aline.id)
        # Process regarding account_type
        if account_type == 'OC':
            for aline in self.browse(cr, uid, ids):
                # Verify that:
                # - the line doesn't have any draft/open contract
                check_accounts = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [aline.account_id.id])
                if check_accounts and aline.account_id.id in check_accounts:
                    continue

                if aline.account_id and aline.account_id.id == msf_private_fund:
                    res.append(aline.id)
                elif aline.account_id and aline.cost_center_id and aline.account_id.cost_center_ids:
                    if account_id in [x and x.id for x in aline.account_id.cost_center_ids] or aline.account_id.id == msf_private_fund:
                        res.append(aline.id)
        elif account_type == 'FUNDING':
            fp = self.pool.get('account.analytic.account').read(cr, uid, account_id, ['cost_center_ids', 'tuple_destination_account_ids'], context=context)
            cc_ids = fp and fp.get('cost_center_ids', []) or []
            tuple_destination_account_ids = fp and fp.get('tuple_destination_account_ids', []) or []
            tuple_list = [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in self.pool.get('account.destination.link').browse(cr, uid, tuple_destination_account_ids) if not x.disabled]
            # Browse all analytic line to verify them
            for aline in self.browse(cr, uid, ids):
                # Verify that:
                # - the line doesn't have any draft/open contract
                check_accounts = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [aline.account_id.id])
                if check_accounts and aline.account_id.id in check_accounts:
                    continue
                # No verification if account is MSF Private Fund because of its compatibility with all elements.
                if account_id == msf_private_fund:
                    res.append(aline.id)
                    continue
                # Verify that:
                # - the line have a cost_center_id field (we expect it's a line with a funding pool account)
                # - the cost_center is in compatible cost center from the new funding pool
                # - the general account is in compatible account/destination tuple
                # - the destination is in compatible account/destination tuple
                if aline.cost_center_id and aline.cost_center_id.id in cc_ids and aline.general_account_id and aline.destination_id and (aline.general_account_id.id, aline.destination_id.id) in tuple_list:
                    res.append(aline.id)
        elif account_type == "DEST":
            for aline in self.browse(cr, uid, ids, context=context):
                if aline.general_account_id and account_id in [x.id for x in aline.general_account_id.destination_ids]:
                    res.append(aline.id)
        else:
            # Case of FREE1 and FREE2 lines
            for i in ids:
                res.append(i)
        # Delete elements that are in expired_date_ids
        for e in expired_date_ids:
            if e in res:
                res.remove(e)
        return res

    def check_dest_cc_fp_compatibility(self, cr, uid, ids,
                                       dest_id=False, cc_id=False, fp_id=False,
                                       from_import=False, from_import_general_account_id=False,
                                       from_import_posting_date=False,
                                       context=None):
        """
        check compatibility of new dest/cc/fp to reallocate
        :return list of not compatible entries tuples
        :rtype: list of tuples [(id, entry_sequence, reason), ]
        """
        def check_date(aaa_br, posting_date):
            if aaa_br.date_start and aaa_br.date:
                return aaa_br.date > posting_date >= aaa_br.date_start or False
            elif aaa_br.date_start:
                return posting_date >= aaa_br.date_start or False
            return False

        def check_entry(id, entry_sequence,
                        general_account_br, posting_date,
                        new_dest_id, new_dest_br,
                        new_cc_id, new_cc_br,
                        new_fp_id, new_fp_br):
            if not general_account_br.is_analytic_addicted:
                res.append((id, entry_sequence, ''))
                return False

            # check cost center with general account
            dest_ids = [d.id for d in general_account_br.destination_ids]
            if not new_dest_id in dest_ids:
                # not compatible with general account
                res.append((id, entry_sequence, 'DEST'))
                return False

            # check funding pool (expect for MSF Private Fund)
            if not new_fp_id == msf_pf_id:  # all OK for MSF Private Fund
                # - cost center and funding pool compatibility
                cc_ids = [cc.id for cc in new_fp_br.cost_center_ids]
                if not new_cc_id in cc_ids:
                    # not compatible with CC
                    res.append((id, entry_sequence, 'CC'))
                    return False

                # - destination / account
                acc_dest = (general_account_br.id, new_dest_id)
                if acc_dest not in [x.account_id and x.destination_id and \
                                    (x.account_id.id, x.destination_id.id) \
                                    for x in new_fp_br.tuple_destination_account_ids if not x.disabled]:
                    # not compatible with dest/account
                    res.append((id, entry_sequence, 'account/dest'))
                    return False

            # check active date
            if not check_date(new_dest_br, posting_date):
                res.append((id, entry_sequence, 'DEST date'))
                return False
            if not check_date(new_cc_br, posting_date):
                res.append((id, entry_sequence, 'CC date'))
                return False
            if new_fp_id != msf_pf_id and not \
                    check_date(new_fp_br, posting_date):
                res.append((id, entry_sequence, 'FP date'))
                return False

            return True

        res = []
        if from_import:
            if not dest_id or not cc_id or not fp_id or \
                    not from_import_general_account_id or \
                    not from_import_posting_date:
                return [(False, '', '')]  # tripplet required at import
        elif not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not dest_id and not cc_id and not fp_id:
            return [(id, '', '') for id in ids]  # all uncompatible
        if context is None:
            context = {}

        aaa_obj = self.pool.get('account.analytic.account')
        if dest_id:
            dest_br = aaa_obj.browse(cr, uid, dest_id, context=context)
        else:
            dest_br = False
        if cc_id:
            cc_br = aaa_obj.browse(cr, uid, cc_id, context=context)
        else:
            cc_br = False
        if fp_id:
            fp_br = aaa_obj.browse(cr, uid, fp_id, context=context)
        else:
            fp_br = False

        # MSF Private Fund
        msf_pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
                                                                        'analytic_distribution', 'analytic_account_msf_private_funds')[1]

        if from_import:
            account_br = self.pool.get('account.account').browse(cr, uid,
                                                                 from_import_general_account_id, context=context)
            check_entry(False, '', account_br, from_import_posting_date,
                        dest_id, dest_br, cc_id, cc_br, fp_id, fp_br)
        else:
            for self_br in self.browse(cr, uid, ids, context=context):
                new_dest_id = dest_id or self_br.destination_id.id
                new_dest_br = dest_br or self_br.destination_id
                new_cc_id = cc_id or self_br.cost_center_id.id
                new_cc_br = cc_br or self_br.cost_center_id
                new_fp_id = fp_id or self_br.account_id.id
                new_fp_br = fp_br or self_br.account_id

                check_entry(self_br.id, self_br.entry_sequence,
                            self_br.general_account_id, self_br.date,
                            new_dest_id, new_dest_br,
                            new_cc_id, new_cc_br,
                            new_fp_id, new_fp_br)

        return res

analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
