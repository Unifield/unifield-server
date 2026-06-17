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
        analytic_acc_obj = self.pool.get('account.analytic.account')
        # We just support '=' operator
        for arg in args:
            if not arg[1]:
                raise osv.except_osv(_('Warning'), _('Some search args are missing!'))
            if arg[1] not in ['=',]:
                raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))
            if not arg[2]:
                raise osv.except_osv(_('Warning'), _('Some search args are missing!'))
            fp_id = arg[2]
            tuple_list = analytic_acc_obj.get_acc_dest_linked_to_fp(cr, uid, fp_id, context=context)
            cost_center_ids = [c.id for c in analytic_acc_obj.get_cc_linked_to_fp(cr, uid, fp_id, context=context)]
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
                if isinstance(periods, int):
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
        'entry_sequence': fields.function(_get_entry_sequence, method=True, type='text', string="Entry Sequence", readonly=True, store=True, select=True),
        'period_id': fields.function(_get_period_id, fnct_search=_search_period_id, method=True, string="Period", readonly=True, type="many2one", relation="account.period", store=False),
        'fiscalyear_id': fields.related('period_id', 'fiscalyear_id', type='many2one', relation='account.fiscalyear', string='Fiscal Year', store=False, write_relate=False),
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

    def check_analytic_account(self, cr, uid, ids, account_id, wiz_date, context=None):
        """
        Analytic distribution validity verification with given account for given ids.
        Return all valid ids.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some value
        ad_obj = self.pool.get('analytic.distribution')
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        account = self.pool.get('account.analytic.account').read(cr, uid, account_id, ['category', 'date_start', 'date'], context=context)
        account_type = account and account.get('category', False) or False
        res = []
        if not account_type:
            return res
        expired_date_ids = []
        date_start = account and account.get('date_start', False) or False
        date_stop = account and account.get('date', False) or False
        # Date verification for all lines and fetch all necessary elements sorted by analytic distribution
        cmp_dates = {}
        wiz_period_open = self.pool.get('account.period').get_open_period_from_date(cr, uid, wiz_date, check_extra_config=True, context=context)

        try:
            pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                        'analytic_account_msf_private_funds')[1]
        except ValueError:
            pf_id = 0
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
                    if not wiz_period_open:
                        expired_date_ids.append(aline.id)
                    elif not self.pool.get('finance.tools').check_correction_date_fy(aline.date, wiz_date, raise_error=False, context=context):
                        expired_date_ids.append(aline.id)
                    else:
                        oc_dest_date_start = max(aline.cost_center_id.date_start, aline.destination_id.date_start)
                        oc_dest_date_stop = min(aline.cost_center_id.date or '9999-01-01', aline.destination_id.date or '9999-01-01')
                        if (oc_dest_date_start and wiz_date < oc_dest_date_start) or (oc_dest_date_stop and wiz_date >= oc_dest_date_stop):
                            expired_date_ids.append(aline.id)
                        else:
                            # check the Dest/CC link validity with the original Dest and CC which will be used in the REV
                            destination_id = aline.destination_id and aline.destination_id.id or False
                            cost_center_id = aline.cost_center_id and aline.cost_center_id.id or False
                            if destination_id and cost_center_id and \
                                    dest_cc_link_obj.is_inactive_dcl(cr, uid, destination_id, cost_center_id, wiz_date, context=context):
                                expired_date_ids.append(aline.id)
            if (date_start and aline_cmp_date < date_start) or (date_stop and aline_cmp_date >= date_stop):
                expired_date_ids.append(aline.id)
            cmp_dates[aline.id] = aline_cmp_date
        # Process regarding account_type
        ids = [i for i in ids if i not in expired_date_ids]  # exclude the AJI in expired_date_ids
        if account_type == 'OC':
            for aline in self.browse(cr, uid, ids):
                # Verify that:
                # - the line doesn't have any draft/open contract
                check_accounts = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [aline.account_id.id])
                if check_accounts and aline.account_id.id in check_accounts:
                    continue
                dest_id = aline.destination_id and aline.destination_id.id or False
                if ad_obj.check_dest_cc_compatibility(cr, uid, dest_id, account_id, context=context) and \
                    ad_obj.check_fp_cc_compatibility(cr, uid, aline.account_id.id, account_id, context=context) and \
                        not dest_cc_link_obj.is_inactive_dcl(cr, uid, dest_id, account_id, cmp_dates[aline.id], context=context):
                    res.append(aline.id)
        elif account_type == 'FUNDING':
            # Browse all analytic line to verify them
            for aline in self.browse(cr, uid, ids):
                # Verify that:
                # - the line doesn't have any draft/open contract
                check_accounts = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [aline.account_id.id])
                if check_accounts and aline.account_id.id in check_accounts:
                    continue
                # Verify that:
                # - the line have a cost_center_id field (we expect it's a line with a funding pool account)
                # - the cost_center is in compatible cost center from the new funding pool
                # - the general account is in compatible account/destination tuple
                # - the destination is in compatible account/destination tuple
                if aline.cost_center_id and aline.destination_id and \
                    ad_obj.check_fp_cc_compatibility(cr, uid, account_id, aline.cost_center_id.id, context=context) and \
                    ad_obj.check_fp_acc_dest_compatibility(cr, uid, account_id, aline.general_account_id.id,
                                                           aline.destination_id.id, context=context):
                    res.append(aline.id)
        elif account_type == "DEST":
            for aline in self.browse(cr, uid, ids, context=context):
                if aline.account_id.id == pf_id:
                    # UC1: the Funding Pool is PF ==> only check Acc/Dest compatibility
                    fp_acc_dest_ok = ad_obj.check_gl_account_destination_compatibility(cr, uid, aline.general_account_id.id, account_id)
                else:
                    # UC2: the Funding Pool is NOT PF ==> check the FP compatibility with the Acc/Dest (Acc/Dest compat. check is included)
                    fp_acc_dest_ok = ad_obj.check_fp_acc_dest_compatibility(cr, uid, aline.account_id.id, aline.general_account_id.id,
                                                                            account_id, context=context)
                cc_id = aline.cost_center_id and aline.cost_center_id.id or False
                if fp_acc_dest_ok and ad_obj.check_dest_cc_compatibility(cr, uid, account_id, cc_id, context=context) and \
                        not dest_cc_link_obj.is_inactive_dcl(cr, uid, account_id, cc_id, cmp_dates[aline.id], context=context):
                    res.append(aline.id)
        else:
            # Case of FREE1 and FREE2 lines
            for i in ids:
                res.append(i)
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
            ad_obj = self.pool.get('analytic.distribution')
            dest_cc_link_obj = self.pool.get('dest.cc.link')
            if not general_account_br.is_analytic_addicted:
                res.append((id, entry_sequence, ''))
                return False

            # check cost center with general account

            if not ad_obj.check_gl_account_destination_compatibility(cr, uid, general_account_br.id, new_dest_id):
                # not compatible with general account
                res.append((id, entry_sequence, _('DEST')))
                return False

            # check cost center with destination
            if new_dest_id and new_cc_id:
                if not ad_obj.check_dest_cc_compatibility(cr, uid, new_dest_id, new_cc_id, context=context):
                    res.append((id, entry_sequence, _('CC/DEST')))
                    return False

            # - cost center and funding pool compatibility
            if not ad_obj.check_fp_cc_compatibility(cr, uid, new_fp_id, new_cc_id, context=context):
                # not compatible with CC
                res.append((id, entry_sequence, _('CC ')))
                return False

            # - destination / account
            if not ad_obj.check_fp_acc_dest_compatibility(cr, uid, new_fp_id, general_account_br.id, new_dest_id, context=context):
                # not compatible with account/dest
                res.append((id, entry_sequence, _('account/dest')))
                return False

            # check active date
            if not check_date(new_dest_br, posting_date):
                res.append((id, entry_sequence, _('DEST date')))
                return False
            if not check_date(new_cc_br, posting_date):
                res.append((id, entry_sequence, _('CC date')))
                return False
            if new_dest_id and new_cc_id and dest_cc_link_obj.is_inactive_dcl(cr, uid, new_dest_id, new_cc_id, posting_date, context=context):
                res.append((id, entry_sequence, _('DEST/CC combination date')))
                return False
            if new_fp_id != msf_pf_id and not \
                    check_date(new_fp_br, posting_date):
                res.append((id, entry_sequence, _('FP date')))
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
        if isinstance(ids, int):
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
