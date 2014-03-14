# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 MSF, TeMPO Consulting.
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
from lxml import etree

class analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    def _get_is_free(self, cr, uid, ids, field_names, args, context=None):
        """
        Check if the line comes from a Free 1 or Free 2 analytic account category.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.account_id and al.account_id.category and al.account_id.category in ['FREE1', 'FREE2']:
                res[al.id] = True
        return res

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center', domain="[('category', '=', 'OC'), ('type', '<>', 'view')]"),
        'from_write_off': fields.boolean(string='Write-off?', readonly=True, help="Indicates that this line come from a write-off account line."),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '<>', 'view')]"),
        'distrib_line_id': fields.reference('Distribution Line ID', selection=[('funding.pool.distribution.line', 'FP'),('free.1.distribution.line', 'free1'), ('free.2.distribution.line', 'free2')], size=512),
        'free_account': fields.function(_get_is_free, method=True, type='boolean', string='Free account?', help="Is that line comes from a Free 1 or Free 2 account?"),
    }

    _defaults = {
        'from_write_off': lambda *a: False,
    }

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
            if vals.get('cost_center_id', False):
                cc = account_obj.browse(cr, uid, vals['cost_center_id'], context=context)
                if date < cc.date_start or (cc.date != False and date >= cc.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (cc.name or '',))
            if vals.get('destination_id', False):
                dest = account_obj.browse(cr, uid, vals['destination_id'], context=context)
                if date < dest.date_start or (dest.date != False and date >= dest.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (dest.name or '',))
        return True

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

analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: