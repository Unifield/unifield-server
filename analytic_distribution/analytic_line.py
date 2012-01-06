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

class analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center'),
        'commitment_line_id': fields.many2one('account.commitment.line', string='Commitment Voucher Line', ondelete='cascade'),
    }

    def _check_date(self, cr, uid, vals, context={}):
        """
        Check if given account_id is active for given date. Except for mass reallocation ('from' = 'mass_reallocation' in context)
        """
        if not context:
            context={}
        if not 'account_id' in vals:
            raise osv.except_osv(_('Error'), _('No account_id found in given values!'))
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.analytic.account')
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            if vals['date'] < account.date_start \
            or (account.date != False and \
                vals['date'] >= account.date):
                if 'from' not in context or context.get('from') != 'mass_reallocation':
                    raise osv.except_osv(_('Error !'), _("The analytic account selected '%s' is not active.") % account.name)

    def create(self, cr, uid, vals, context={}):
        """
        Check date for given date and given account_id
        """
        self._check_date(cr, uid, vals, context=context)
        return super(analytic_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        """
        Verify date for all given ids with account
        """
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            if not 'account_id' in vals:
                line = self.browse(cr, uid, [id], context=context)
                account_id = line and line[0] and line[0].account_id.id or False
                vals.update({'account_id': account_id})
            self._check_date(cr, uid, vals, context=context)
        return super(analytic_line, self).write(cr, uid, ids, vals, context=context)

    def update_account(self, cr, uid, ids, account_id, context={}):
        """
        Update account on given analytic lines with account_id
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not account_id:
            return False
        # Prepare some value
        account = self.pool.get('account.analytic.account').browse(cr, uid, [account_id], context)[0]
        context.update({'from': 'mass_reallocation'}) # this permits reallocation to be accepted when rewrite analaytic lines
        # Process lines
        for aline in self.browse(cr, uid, ids, context=context):
            if account.category == 'OC':
                old_account_id = aline.account_id and aline.account_id.id or False
                fp_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('cost_center_id', '=', old_account_id), 
                    ('distribution_id', '=', aline.distribution_id.id)], context=context)
                if isinstance(fp_line_ids, (int, long)):
                    fp_line_ids = [fp_line_ids]
                # Period verification
                period = aline.move_id and aline.move_id.period_id or False
                # if period not 'Draft' (created) or 'Open' (draft), so reverse line before recreating them with right values
                if period and period.state not in ['created', 'draft', 'field-closed']:
                    # First reverse lines
                    self.pool.get('account.analytic.line').reverse(cr, uid, fp_line_ids, context=context) # for Funding Pool Lines
                    self.pool.get('account.analytic.line').reverse(cr, uid, [aline.id], context=context) # for given Cost Center Line
                    # Then Create new lines
                    for fp in self.pool.get('account.analytic.line').browse(cr, uid, fp_line_ids, context=context):
                        self.pool.get('account.analytic.line').copy(cr, uid, fp.id, {'cost_center_id': account_id, 'date': strftime('%Y-%m-%d'),
                            'source_date': fp.source_date or fp.date}, context=context)
                        # Update FP line to inform that it have been reallocated
                        self.pool.get('account.analytic.line').write(cr, uid, fp.id, {'is_reallocated': True}, context=context)
                    self.pool.get('account.analytic.line').copy(cr, uid, aline.id, {'account_id': account_id, 'date': strftime('%Y-%m-%d'),
                        'source_date': aline.source_date or aline.date}, context=context)
                    # Update cost center line to inform that it have been reallocated
                    self.pool.get('account.analytic.line').write(cr, uid, aline.id, {'is_reallocated': True}, context=context)
                else:
                    # Update attached funding pool lines
                    for fp in self.pool.get('account.analytic.line').browse(cr, uid, fp_line_ids, context=context):
                        self.pool.get('account.analytic.line').write(cr, uid, [fp.id], {'cost_center_id': account_id, 'date': strftime('%Y-%m-%d'),
                            'source_date': fp.source_date or fp.date}, context=context)
                    # Update account
                    self.write(cr, uid, [aline.id], {'account_id': account_id, 'date': strftime('%Y-%m-%d'), 
                        'source_date': aline.source_date or aline.date}, context=context)
            else:
                # Update account
                self.write(cr, uid, [aline.id], {'account_id': account_id}, context=context)
        return True

    def check_analytic_account(self, cr, uid, ids, account_id, context={}):
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
        elements = defaultdict(list)
        # Date verification for all lines and fetch all necessary elements sorted by analytic distribution
        for aline in self.browse(cr, uid, ids, context=context):
            # Add line to expired_date if date is not in date_start - date_stop
            if (date_start and aline.date < date_start) or (date_stop and aline.date > date_stop):
                expired_date_ids.append(aline.id)
            # add line to elements, sorted by distribution
            elements[aline.distribution_id.id].append(aline)
        # Retrieve distribution_ids
        distrib_ids = [x for x in elements]
        # Process regarding account_type
        if account_type == 'OC':
            # Search all FP lines for given distribution
            fp_line_ids = self.pool.get('funding.pool.distribution.line').search(cr, uid, [('distribution_id', 'in', distrib_ids)])
            # Browse FP and select those that are compatible with selected account_id
            fp_compatible_ids = defaultdict(list)
            non_compatible_distribution_ids = []
            for distrib_line in self.pool.get('funding.pool.distribution.line').browse(cr, uid, fp_line_ids, context=context):
                # If account_id is msf_private_fund OR account_id is in cost_center_ids, then add distrib line in fp_compatible_ids
                if distrib_line.analytic_id.id == msf_private_fund or account_id in [x.id for x in distrib_line.analytic_id.cost_center_ids]:
                    fp_compatible_ids[distrib_line.distribution_id.id].append(distrib_line.id)
            # Browse each distribution
            for distrib_id in fp_compatible_ids:
                # Test FP for each analytic line
                for aline in elements[distrib_id]:
                    if aline.distribution_id and fp_compatible_ids[distrib_id]:
                        # Test that analytic line distribution have some funding pool lines that matches all compatible funding pool for 
                        #+ the current distrib
                        valid = 0
                        aline_fp_lines = self.pool.get('funding.pool.distribution.line').search(cr, uid, [('distribution_id', '=', aline.distribution_id.id), 
                            ('cost_center_id', '=', aline.account_id.id)], context=context) or []
                        for el in aline_fp_lines:
                            if el in fp_compatible_ids[distrib_id]:
                                valid += 1
                        if len(aline_fp_lines) == valid:
                            # All matches
                            res.append(aline.id)
        elif account_type == 'FUNDING':
            fp = self.pool.get('account.analytic.account').read(cr, uid, account_id, ['cost_center_ids', 'account_ids'], context=context)
            cc_ids = fp and fp.get('cost_center_ids', []) or []
            account_ids = fp and fp.get('account_ids', []) or []
            # Browse all analytic line to verify them
            for aline in self.browse(cr, uid, ids, context=context):
                # Verify that:
                # - the line doesn't have any draft/open contract
                contract_ids = self.pool.get('financing.contract.contract').search(cr, uid, [('funding_pool_ids', '=', aline.account_id.id)], context=context)
                valid = True
                for contract in self.pool.get('financing.contract.contract').browse(cr, uid, contract_ids, context=context):
                    if contract.state in ['soft_closed', 'hard_closed']:
                        valid = False
                if not valid:
                    continue
                # No verification if account is MSF Private Fund because of its compatibility with all elements.
                if account_id == msf_private_fund:
                    res.append(aline.id)
                    continue
                # Verify that:
                # - the line have a cost_center_id field (we expect it's a line with a funding pool account)
                # - the cost_center is in compatible cost center from the new funding pool
                # - the general account is in compatible accounts
                if aline.cost_center_id and aline.cost_center_id.id in cc_ids and aline.general_account_id and aline.general_account_id.id in account_ids:
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
