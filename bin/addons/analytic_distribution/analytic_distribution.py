# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) MSF, TeMPO Consulting.
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

class analytic_distribution(osv.osv):
    _name = 'analytic.distribution'
    _inherit = 'analytic.distribution'

    def check_dest_cc_compatibility(self, cr, uid, destination_id, cost_center_id, context=None):
        """
        Checks the compatibility between the Destination and the Cost Center (cf. CC tab in the Destination form).
        Returns False if they aren't compatible.
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        if destination_id and cost_center_id:
            dest = analytic_acc_obj.browse(cr, uid, destination_id, fields_to_fetch=['category', 'allow_all_cc', 'dest_cc_ids'], context=context)
            cc = analytic_acc_obj.browse(cr, uid, cost_center_id, fields_to_fetch=['category'], context=context)
            if dest and cc and dest.category == 'DEST' and cc.category == 'OC' and not dest.allow_all_cc and \
                    cc.id not in [c.id for c in dest.dest_cc_ids]:
                return False
        return True

    def _get_distribution_state(self, cr, uid, distrib_id, parent_id, account_id, context=None):
        """
        Return distribution state
        """
        if context is None:
            context = {}
        # Have an analytic distribution on another account than analytic-a-holic account make no sense. So their analytic distribution is valid
        if account_id:
            account =  self.pool.get('account.account').read(cr, uid, account_id, ['is_analytic_addicted'])
            if account and not account.get('is_analytic_addicted', False):
                return 'valid'
        if not distrib_id:
            if parent_id:
                return self._get_distribution_state(cr, uid, parent_id, False, account_id, context)
            return 'none'
        distrib = self.browse(cr, uid, distrib_id)
        if not distrib.funding_pool_lines:
            return 'none'
        # Search MSF Private Fund element, because it's valid with all accounts
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                        'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        account = self.pool.get('account.account').read(cr, uid, account_id, ['destination_ids'])
        # Check Cost Center lines regarding destination/account and destination/CC links
        for cc_line in distrib.cost_center_lines:
            if cc_line.destination_id.id not in account.get('destination_ids', []):
                return 'invalid'
            if not self.check_dest_cc_compatibility(cr, uid, cc_line.destination_id.id,
                                                    cc_line.analytic_id and cc_line.analytic_id.id or False, context=context):
                return 'invalid'
        # Check Funding pool lines regarding:
        # - destination / account
        # - destination / cost center
        # - If analytic account is MSF Private funds
        # - Cost center and funding pool compatibility
        for fp_line in distrib.funding_pool_lines:
            if fp_line.destination_id.id not in account.get('destination_ids', []):
                return 'invalid'
            if not self.check_dest_cc_compatibility(cr, uid, fp_line.destination_id.id, fp_line.cost_center_id.id, context=context):
                return 'invalid'
            # If fp_line is MSF Private Fund, all is ok
            if fp_line.analytic_id.id == fp_id:
                continue
            if (account_id, fp_line.destination_id.id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in fp_line.analytic_id.tuple_destination_account_ids if not x.disabled]:
                return 'invalid'
            if fp_line.cost_center_id.id not in [x.id for x in fp_line.analytic_id.cost_center_ids]:
                return 'invalid'
        return 'valid'

    def analytic_state_from_info(self, cr, uid, account_id, destination_id, cost_center_id, analytic_id, context=None):
        """
        Give analytic state from the given information.
        Return result and some info if needed.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = 'valid'
        info = ''
        ana_obj = self.pool.get('account.analytic.account')
        account = self.pool.get('account.account').browse(cr, uid, account_id, context=context)
        fp = ana_obj.browse(cr, uid, analytic_id, context=context)
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        is_private_fund = False
        if analytic_id == fp_id:
            is_private_fund = True
        # DISTRIBUTION VERIFICATION
        # Check that destination is compatible with account
        if destination_id not in [x.id for x in account.destination_ids]:
            return 'invalid', _('Destination not compatible with account')
        # Check that Destination and Cost Center are compatible
        if not self.check_dest_cc_compatibility(cr, uid, destination_id, cost_center_id, context=context):
            return 'invalid', _('Cost Center not compatible with destination')
        if not is_private_fund:
            # Check that cost center is compatible with FP (except if FP is MSF Private Fund)
            if cost_center_id not in [x.id for x in fp.cost_center_ids]:
                return 'invalid', _('Cost Center not compatible with FP')
            # Check that tuple account/destination is compatible with FP (except if FP is MSF Private Fund):
            if (account_id, destination_id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in fp.tuple_destination_account_ids if not x.disabled]:
                return 'invalid', _('account/destination tuple not compatible with given FP analytic account')
        return res, info

analytic_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
