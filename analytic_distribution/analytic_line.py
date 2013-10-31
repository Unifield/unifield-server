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
from tools.misc import flatten
from collections import defaultdict
from time import strftime
from lxml import etree

class analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    def _get_fake_is_fp_compat_with(self, cr, uid, ids, field_name, args, context=None):
        """
        Fake method for 'is_fp_compat_with' field
        """
        res = {}
        for id in ids:
            res[id] = ''
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
            tuple_list = [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in analytic_account.tuple_destination_account_ids]
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
        Give right entry sequence. Either move_id.move_id.name or commitment_line_id.commit_id.name
        """
        if not context:
            context = {}
        res = {}
        for l in self.browse(cr, uid, ids, context):
            res[l.id] = ''
            if l.move_id:
                res[l.id] = l.move_id.move_id.name
            elif l.commitment_line_id:
                res[l.id] = l.commitment_line_id.commit_id.name
        return res

    def _get_period_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Fetch period_id from:
        - move_id
        - commitment_line_id
        """
        # Checks
        if not context:
            context = {}
        # Prepare some values
        res = {}
        for al in self.browse(cr, uid, ids, context):
            res[al.id] = False
            if al.commitment_line_id and al.commitment_line_id.commit_id and al.commitment_line_id.commit_id.period_id:
                res[al.id] = al.commitment_line_id.commit_id.period_id.id
            elif al.move_id and al.move_id.period_id:
                res[al.id] = al.move_id.period_id.id
        return res

    def _search_period_id(self, cr, uid, obj, name, args, context=None):
        """
        Search period
        """
        # Checks
        if not context:
            context = {}
        if not args:
            return []
        new_args = []
        for arg in args:
            if len(arg) == 3 and arg[1] in ['=', 'in']:
                new_args.append('|')
                new_args.append(('move_id.period_id', arg[1], arg[2]))
                new_args.append(('commitment_line_id.commit_id.period_id', arg[1], arg[2]))
        return new_args

    def _get_from_commitment_line(self, cr, uid, ids, field_name, args, context=None):
        """
        Check if commitment_line_id is filled in. If yes, True. Otherwise False.
        """
        if not context:
            context = {}
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.commitment_line_id:
                res[al.id] = True
        return res

    def _get_is_unposted(self, cr, uid, ids, field_name, args, context=None):
        """
        Check journal entry state. If unposted: True, otherwise False.
        """
        if not context:
            context = {}
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.move_state != 'posted':
                res[al.id] = True
        return res

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center', domain="[('category', '=', 'OC'), ('type', '<>', 'view')]"),
        'commitment_line_id': fields.many2one('account.commitment.line', string='Commitment Voucher Line', ondelete='cascade'),
        'from_write_off': fields.boolean(string='Write-off?', readonly=True, help="Indicates that this line come from a write-off account line."),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '<>', 'view')]"),
        'is_fp_compat_with': fields.function(_get_fake_is_fp_compat_with, fnct_search=_search_is_fp_compat_with, method=True, type="char", size=254, string="Is compatible with some FP?"),
        'distrib_line_id': fields.reference('Distribution Line ID', selection=[('funding.pool.distribution.line', 'FP'),('free.1.distribution.line', 'free1'), ('free.2.distribution.line', 'free2')], size=512),
        'move_state': fields.related('move_id', 'move_id', 'state', type='selection', size=64, relation="account.move.line", selection=[('draft', 'Unposted'), ('posted', 'Posted')], string='Journal Entry state', readonly=True, help="Indicates that this line come from an Unposted Journal Entry."),
        'journal_type': fields.related('journal_id', 'type', type='selection', selection=_journal_type_get, string="Journal Type", readonly=True, \
            help="Indicates the Journal Type of the Analytic journal item"),
        'entry_sequence': fields.function(_get_entry_sequence, method=True, type='text', string="Entry Sequence", readonly=True, store=True),
        'period_id': fields.function(_get_period_id, fnct_search=_search_period_id, method=True, string="Period", readonly=True, type="many2one", relation="account.period", store=False),
        'from_commitment_line': fields.function(_get_from_commitment_line, method=True, type='boolean', string="Commitment?"),
        'is_unposted': fields.function(_get_is_unposted, method=True, type='boolean', string="Unposted?"),
    }

    _defaults = {
        'from_write_off': lambda *a: False,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change account_id field name to "Funding Pool if we come from a funding pool
        """
        # Some verifications
        if not context:
            context = {}
        is_funding_pool_view = False
        if context.get('display_fp', False) and context.get('display_fp') is True:
            is_funding_pool_view = True
        view = super(analytic_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type in ('tree', 'search') and is_funding_pool_view:
            tree = etree.fromstring(view['arch'])
            # Change OC field
            fields = tree.xpath('/' + view_type + '//field[@name="account_id"]')
            for field in fields:
                field.set('string', _("Funding Pool"))
                field.set('domain', "[('category', '=', 'FUNDING'), ('type', '<>', 'view')]")
            view['arch'] = etree.tostring(tree)
        return view

    def _check_date(self, cr, uid, vals, context=None):
        """
        Check if given account_id is active for given date. Except for mass reallocation ('from' = 'mass_reallocation' in context)
        """
        if not context:
            context = {}
        if not 'account_id' in vals:
            raise osv.except_osv(_('Error'), _('No account_id found in given values!'))
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.analytic.account')
            date = vals['date']
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            # FIXME: refactoring of next code
            if date < account.date_start or (account.date != False and date >= account.date):
                if 'from' not in context or context.get('from') != 'mass_reallocation':
                    raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (account.name or '',))
            if 'cost_center_id' in vals:
                cc = account_obj.browse(cr, uid, vals['cost_center_id'], context=context)
                if date < cc.date_start or (cc.date != False and date >= cc.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (cc.name or '',))
            if 'destination_id' in vals:
                dest = account_obj.browse(cr, uid, vals['destination_id'], context=context)
                if date < dest.date_start or (dest.date != False and date >= dest.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (dest.name or '',))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Check date for given date and given account_id
        """
        # Some verifications
        if not context:
            context = {}
        # Default behaviour
        res = super(analytic_line, self).create(cr, uid, vals, context=context)
        # Check date
        self._check_date(cr, uid, vals, context=context)
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

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify date for all given ids with account
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for l in self.browse(cr, uid, ids):
            vals2 = vals.copy()
            for el in ['account_id', 'cost_center_id', 'destination_id']:
                if not el in vals:
                    vals2.update({el: l[el] and l[el]['id'] or False})
            self._check_date(cr, uid, vals2, context=context)
        return super(analytic_line, self).write(cr, uid, ids, vals, context=context)

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
        # Process lines
        for aline in self.browse(cr, uid, ids, context=context):
            if account.category in ['OC', 'DEST']:
                # Period verification
                period = aline.move_id and aline.move_id.period_id or False
                # Prepare some values
                fieldname = 'cost_center_id'
                if account.category == 'DEST':
                    fieldname = 'destination_id'
                # if period is not closed, so override line.
                if period and period.state not in ['done', 'mission-closed']:
                    # Update account
                    self.write(cr, uid, [aline.id], {fieldname: account_id, 'date': date, 
                        'source_date': aline.source_date or aline.date}, context=context)
                # else reverse line before recreating them with right values
                else:
                    # First reverse line
                    self.pool.get('account.analytic.line').reverse(cr, uid, [aline.id])
                    # then create new lines
                    self.pool.get('account.analytic.line').copy(cr, uid, aline.id, {fieldname: account_id, 'date': date,
                        'source_date': aline.source_date or aline.date}, context=context)
                    # finally flag analytic line as reallocated
                    self.pool.get('account.analytic.line').write(cr, uid, [aline.id], {'is_reallocated': True})
            else:
                # Update account
                self.write(cr, uid, [aline.id], {'account_id': account_id}, context=context)
        return True

    def check_analytic_account(self, cr, uid, ids, account_id, context=None):
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
            if (date_start and aline_cmp_date < date_start) or (date_stop and aline_cmp_date > date_stop):
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
            tuple_list = [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in self.pool.get('account.destination.link').browse(cr, uid, tuple_destination_account_ids)]
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
        else:
            # Case of FREE1 and FREE2 lines
            for id in ids:
                res.append(id)
        # Delete elements that are in expired_date_ids
        for id in expired_date_ids:
            if id in res:
                res.remove(id)
        return res

analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
