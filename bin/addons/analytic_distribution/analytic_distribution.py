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

import time
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
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        ret = True   # by default if either dest or cc is missing
        if destination_id and cost_center_id:
            if analytic_acc_obj.search_exist(cr, uid, [('id', '=', destination_id), ('allow_all_cc', '=', True)], context=context):
                ret = True
            elif dest_cc_link_obj.search_exist(cr, uid, [('dest_id', '=', destination_id), ('cc_id', '=', cost_center_id)], context=context):
                ret = True
            else:
                ret = False
        return ret

    def check_fp_cc_compatibility(self, cr, uid, fp_id, cost_center_id, context=None):
        """
        Checks the compatibility between the FP and the Cost Center (cf. CC tab in the FP form).
        Returns False if they aren't compatible.

        If "Allow all Cost Centers" is ticked: only CC linked to the prop. instance of the FP are allowed.
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        ir_model_data_obj = self.pool.get('ir.model.data')
        res = True
        if fp_id and cost_center_id:
            # The Funding Pool PF is compatible with every CC
            try:
                pf_id = ir_model_data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                pf_id = 0
            if fp_id != pf_id:
                fp = analytic_acc_obj.browse(cr, uid, fp_id,
                                             fields_to_fetch=['category', 'allow_all_cc_with_fp', 'instance_id', 'cost_center_ids'],
                                             context=context)
                cc = analytic_acc_obj.browse(cr, uid, cost_center_id, fields_to_fetch=['category', 'type', 'cc_instance_ids'], context=context)
                if fp and cc and fp.category == 'FUNDING' and cc.category == 'OC':
                    if fp.allow_all_cc_with_fp and cc.type != 'view' and fp.instance_id and \
                            fp.instance_id.id in [inst.id for inst in cc.cc_instance_ids]:
                        res = True
                    elif cc.id in [c.id for c in fp.cost_center_ids]:
                        res = True
                    else:
                        res = False
        return res

    def onchange_ad_cost_center(self, cr, uid, ids, cost_center_id=False, funding_pool_id=False, fp_field_name='funding_pool_id'):
        """
        Resets the FP in case the CC selected isn't compatible with it.
        """
        res = {}
        if cost_center_id and funding_pool_id and not self.check_fp_cc_compatibility(cr, uid, funding_pool_id, cost_center_id):
            res = {'value': {fp_field_name: False}}
        return res

    def check_fp_acc_dest_compatibility(self, cr, uid, fp_id, account_id, dest_id, context=None):
        """
        Checks the compatibility between the FP and the "G/L Account/Destination" combination.
        Returns False if they aren't compatible.
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        account_obj = self.pool.get('account.account')
        ir_model_data_obj = self.pool.get('ir.model.data')
        res = True
        if fp_id and account_id and dest_id:
            # The Funding Pool PF is compatible with every combination
            try:
                pf_id = ir_model_data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                pf_id = 0
            if fp_id != pf_id:
                fp = analytic_acc_obj.browse(cr, uid, fp_id,
                                             fields_to_fetch=['category', 'select_accounts_only', 'fp_account_ids',
                                                              'tuple_destination_account_ids'],
                                             context=context)
                if fp and fp.category == 'FUNDING':
                    # continue only if the account and destination selected are compatible with one another
                    account_selected = account_obj.browse(cr, uid, account_id, fields_to_fetch=['destination_ids'], context=context)
                    if dest_id not in [d.id for d in account_selected.destination_ids]:
                        res = False
                    else:
                        # when the link is made to G/L accounts only: all Destinations compatible with the acc. are allowed
                        if fp.select_accounts_only and account_id in [a.id for a in fp.fp_account_ids]:
                            res = True
                        # otherwise the combination "account + dest" must be checked
                        elif not fp.select_accounts_only and (account_id, dest_id) in \
                                [(t.account_id.id, t.destination_id.id) for t in fp.tuple_destination_account_ids if not t.disabled]:
                            res = True
                        else:
                            res = False
        return res

    def onchange_ad_destination(self, cr, uid, ids, destination_id=False, funding_pool_id=False, account_id=False,
                                fp_field_name='funding_pool_id'):
        """
        Resets the FP in case the Dest/Acc combination selected isn't compatible with it.
        """
        res = {}
        if destination_id and funding_pool_id and account_id and \
                not self.check_fp_acc_dest_compatibility(cr, uid, funding_pool_id, account_id, destination_id):
            res = {'value': {fp_field_name: False}}
        return res

    def _get_distribution_state(self, cr, uid, distrib_id, parent_id, account_id, context=None,
                                doc_date=False, posting_date=False, manual=False, amount=False):
        """
        Return distribution state

        Check that there is only one AD line for amounts <= 1 ONLY IF an amount is passed in param.
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        # Have an analytic distribution on another account than analytic-a-holic account make no sense. So their analytic distribution is valid
        if account_id:
            account =  self.pool.get('account.account').read(cr, uid, account_id, ['is_analytic_addicted'])
            if account and not account.get('is_analytic_addicted', False):
                return 'valid'
        if not distrib_id:
            if parent_id:
                return self._get_distribution_state(cr, uid, parent_id, False, account_id, context=context,
                                                    doc_date=doc_date, posting_date=posting_date, manual=manual, amount=amount)
            return 'none'
        distrib = self.browse(cr, uid, distrib_id)
        if not distrib.funding_pool_lines:
            return 'none'
        # set AD as invalid when several distrib. lines are applied to booking amount <= 1
        if amount is not None and amount is not False and abs(amount) <= 1:
            if not all(len(d) <= 1 for d in [distrib.funding_pool_lines, distrib.free_1_lines, distrib.free_2_lines]):
                return 'invalid_small_amount'
        account = self.pool.get('account.account').read(cr, uid, account_id, ['destination_ids'])
        # Check Cost Center lines regarding destination/account and destination/CC links
        for cc_line in distrib.cost_center_lines:
            if account and cc_line.destination_id.id not in account.get('destination_ids', []):
                return 'invalid'
            if not self.check_dest_cc_compatibility(cr, uid, cc_line.destination_id.id,
                                                    cc_line.analytic_id and cc_line.analytic_id.id or False, context=context):
                return 'invalid'
        # Check Funding pool lines regarding:
        # - date validity for manual entries only
        # - destination / account
        # - destination / cost center
        # - If analytic account is MSF Private funds
        # - Cost center and funding pool compatibility
        for fp_line in distrib.funding_pool_lines:
            if manual:
                if posting_date:
                    if not analytic_acc_obj.is_account_active(fp_line.destination_id, posting_date):
                        return 'invalid'
                    if not analytic_acc_obj.is_account_active(fp_line.cost_center_id, posting_date):
                        return 'invalid'
                    if dest_cc_link_obj.is_inactive_dcl(cr, uid, fp_line.destination_id.id, fp_line.cost_center_id.id,
                                                        posting_date, context=context):
                        return 'invalid'
                if doc_date and fp_line.analytic_id and not analytic_acc_obj.is_account_active(fp_line.analytic_id, doc_date):
                    return 'invalid'
            if account and fp_line.destination_id.id not in account.get('destination_ids', []):
                return 'invalid'
            if not self.check_dest_cc_compatibility(cr, uid, fp_line.destination_id.id, fp_line.cost_center_id.id, context=context):
                return 'invalid'
            if not fp_line.analytic_id:
                return 'invalid'
            if not self.check_fp_acc_dest_compatibility(cr, uid, fp_line.analytic_id.id, account_id,
                                                        fp_line.destination_id.id, context=context):
                return 'invalid'
            if not self.check_fp_cc_compatibility(cr, uid, fp_line.analytic_id.id, fp_line.cost_center_id.id, context=context):
                return 'invalid'
        # Check the date validity of the free accounts used in manual entries
        if manual and doc_date:
            for free1_line in distrib.free_1_lines:
                if free1_line.analytic_id and not analytic_acc_obj.is_account_active(free1_line.analytic_id, doc_date):
                    return 'invalid'
            for free2_line in distrib.free_2_lines:
                if free2_line.analytic_id and not analytic_acc_obj.is_account_active(free2_line.analytic_id, doc_date):
                    return 'invalid'
        return 'valid'

    def analytic_state_from_info(self, cr, uid, account_id, destination_id, cost_center_id, analytic_id, posting_date=False, document_date=False, check_analytic_active=False, context=None):
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
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        account = self.pool.get('account.account').browse(cr, uid, account_id, context=context)
        analytic_acc_obj = self.pool.get('account.analytic.account')
        # DISTRIBUTION VERIFICATION
        # Check that destination is compatible with account
        if check_analytic_active:
            for aa in analytic_acc_obj.browse(cr, uid, [destination_id, cost_center_id, analytic_id], context=context):
                if aa.category == 'FUNDING':
                    date_check = document_date or time.strftime('%Y-%m-%d')
                else:
                    date_check = posting_date or time.strftime('%Y-%m-%d')

                if not analytic_acc_obj.is_account_active(aa, date_check):
                    return 'invalid', _('Account %s is inactive on %s') % (aa.code, date_check)

        if destination_id not in [x.id for x in account.destination_ids]:
            return 'invalid', _('Destination not compatible with account')
        # Check that Destination and Cost Center are compatible
        if not self.check_dest_cc_compatibility(cr, uid, destination_id, cost_center_id, context=context):
            return 'invalid', _('Cost Center not compatible with destination')
        # Check that their combination is active
        if posting_date and dest_cc_link_obj.is_inactive_dcl(cr, uid, destination_id, cost_center_id, posting_date, context=context):
            return 'invalid', _('Inactive DEST/CC combination')
        # Check that cost center is compatible with FP
        if not self.check_fp_cc_compatibility(cr, uid, analytic_id, cost_center_id, context=context):
            return 'invalid', _('Cost Center not compatible with FP')
        # Check that tuple account/destination is compatible with FP
        if not self.check_fp_acc_dest_compatibility(cr, uid, analytic_id, account_id, destination_id, context=context):
            return 'invalid', _('account/destination tuple not compatible with given FP analytic account')
        return res, info

    def check_cc_distrib_active(self, cr, uid, distrib_br, posting_date=False, prefix='', from_supply=False):
        """
        Checks the Cost Center Distribution Lines of the distribution in param.:
        raises an error if the CC, the Dest., or their combination is not active at the posting date selected (or today's date)
        If needed a "prefix" can be added to the error message.
        """
        cc_distrib_line_obj = self.pool.get('cost.center.distribution.line')
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        if distrib_br:
            if not posting_date:
                posting_date = time.strftime('%Y-%m-%d')
            # note: the browse is used to specify the date and the from_supply tag in context
            for cline in cc_distrib_line_obj.browse(cr, uid, [ccl.id for ccl in distrib_br.cost_center_lines],
                                                    fields_to_fetch=['analytic_id', 'destination_id'],
                                                    context={'date': posting_date, 'from_supply_wkf': from_supply}):
                if cline.analytic_id and not cline.analytic_id.filter_active:
                    raise osv.except_osv(_('Error'), _('%sCost center account %s is not active at this date: %s') %
                                         (prefix, cline.analytic_id.code or '', posting_date))
                if not cline.destination_id.filter_active:
                    if from_supply:
                        raise osv.except_osv(_('Error'), _('%sDestination %s is not active at this date: %s') %
                                             (prefix, cline.destination_id.code or '', posting_date))
                    else:
                        raise osv.except_osv(_('Error'), _('%sDestination %s is either inactive at the date %s, or it allows no Cost Center.') %
                                             (prefix, cline.destination_id.code or '', posting_date))
                if cline.destination_id and cline.analytic_id and \
                        dest_cc_link_obj.is_inactive_dcl(cr, uid, cline.destination_id.id, cline.analytic_id.id, posting_date):
                    raise osv.except_osv(_('Error'), _("%sThe combination \"%s - %s\" is not active at this date: %s") %
                                         (prefix, cline.destination_id.code or '', cline.analytic_id.code or '', posting_date))



analytic_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
