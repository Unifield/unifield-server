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
                        res.append('|')
                    res.append('&')
                    res.append('&')
                    res.append(('cost_center_id', '=', cc))
                    res.append(('general_account_id', '=', t[0]))
                    res.append(('destination_id', '=', t[1]))
        return res

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center'),
        'commitment_line_id': fields.many2one('account.commitment.line', string='Commitment Voucher Line', ondelete='cascade'),
        'from_write_off': fields.boolean(string='From write-off account line?', readonly=True, help="Indicates that this line come from a write-off account line."),
        'destination_id': fields.many2one('account.analytic.account', string="Destination"),
        'is_fp_compat_with': fields.function(_get_fake_is_fp_compat_with, fnct_search=_search_is_fp_compat_with, method=True, type="char", size=254, string="Is compatible with some FP?"),
        'distrib_line_id': fields.reference('Distribution Line ID', selection=[('funding.pool.distribution.line', 'FP'),('free.1.distribution.line', 'free1'), ('free.2.distribution.line', 'free2')], size=512),
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
        if view_type=='tree' and is_funding_pool_view:
            tree = etree.fromstring(view['arch'])
            # Change OC field
            fields = tree.xpath('/tree/field[@name="account_id"]')
            for field in fields:
                field.set('string', _("Funding Pool"))
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
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            if vals['date'] < account.date_start \
            or (account.date != False and \
                vals['date'] >= account.date):
                if 'from' not in context or context.get('from') != 'mass_reallocation':
                    raise osv.except_osv(_('Error !'), _("The analytic account selected '%s' is not active.") % account.name)

    def create(self, cr, uid, vals, context=None):
        """
        Check date for given date and given account_id
        """
        self._check_date(cr, uid, vals, context=context)
        return super(analytic_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify date for all given ids with account
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            vals2 = vals.copy()
            if not 'account_id' in vals:
                line = self.browse(cr, uid, [id], context=context)
                account_id = line and line[0] and line[0].account_id.id or False
                vals2.update({'account_id': account_id})
            self._check_date(cr, uid, vals2, context=context)
        return super(analytic_line, self).write(cr, uid, ids, vals, context=context)

    def update_account(self, cr, uid, ids, account_id, context=None):
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
            if account.category in ['OC', 'DEST']:
                # Period verification
                period = aline.move_id and aline.move_id.period_id or False
                # Prepare some values
                fieldname = 'cost_center_id'
                if account.category == 'DEST':
                    fieldname = 'destination_id'
                # if period is not closed, so override line.
                if period and period.state != 'done':
                    # Update account
                    self.write(cr, uid, [aline.id], {fieldname: account_id, 'date': strftime('%Y-%m-%d'), 
                        'source_date': aline.source_date or aline.date}, context=context)
                # else reverse line before recreating them with right values
                else:
                    # First reverse line
                    self.pool.get('account.analytic.line').reverse(cr, uid, [aline.id])
                    # then create new lines
                    self.pool.get('account.analytic.line').copy(cr, uid, aline.id, {fieldname: account_id, 'date': strftime('%Y-%m-%d'),
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
            # Add line to expired_date if date is not in date_start - date_stop
            if (date_start and aline.date < date_start) or (date_stop and aline.date > date_stop):
                expired_date_ids.append(aline.id)
        # Process regarding account_type
        if account_type == 'OC':
            for aline in self.browse(cr, uid, ids):
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
