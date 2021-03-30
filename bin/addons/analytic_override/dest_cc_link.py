# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2021 MSF, TeMPO Consulting.
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


class dest_cc_link(osv.osv):
    _name = "dest.cc.link"
    _description = "Destination / Cost Center Combination"
    _rec_name = "cc_id"
    _trace = True

    _columns = {
        'dest_id': fields.many2one('account.analytic.account', string="Destination", required=True,
                                   domain="[('category', '=', 'DEST'), ('type', '!=', 'view')]", ondelete='cascade'),
        'cc_id': fields.many2one('account.analytic.account', "Cost Center", required=True,
                                 domain="[('category', '=', 'OC'), ('type', '!=', 'view')]", ondelete='cascade'),
        'cc_name': fields.related('cc_id', 'name', type="char", string="Cost Center Name", readonly=True, store=False),
        'active_from': fields.date('Activation Combination Dest / CC from', required=False),
        'inactive_from': fields.date('Inactivation Combination Dest / CC from', required=False),
    }

    _order = 'dest_id, cc_id'

    _sql_constraints = [
        ('dest_cc_uniq', 'UNIQUE(dest_id, cc_id)', 'Each Cost Center can only be added once to the same Destination.'),
        ('dest_cc_date_check', 'CHECK(active_from < inactive_from)', 'The Activation date of the "Combination Dest / CC" '
                                                                     'must be before the Inactivation date.')
    ]

    def _bypass(self, vals, context=None):
        """
        Returns True if at sync time the CC to be added to the Dest CC Link isn't found. It means that the CC doesn't
        exist in the current instance so the creation/edition of the related Dest CC Link should be ignored.
        """
        if context is None:
            context = {}
        return context.get('sync_update_execution') and 'cc_id' in vals and not vals['cc_id']

    def create(self, cr, uid, vals, context=None):
        if not self._bypass(vals, context=context):
            return super(dest_cc_link, self).create(cr, uid, vals, context=context)
        return False

    def write(self, cr, uid, ids, vals, context=None):
        if not self._bypass(vals, context=context):
            return super(dest_cc_link, self).write(cr, uid, ids, vals, context=context)
        return False

    def is_inactive_dcl(self, cr, uid, dest_id, cc_id, posting_date, context=None):
        """
        Returns True if the Dest CC Link with the dest_id and cc_id exists and that the posting_date
        is outside its validity date range.
        """
        if context is None:
            context = {}
        inactive_dcl = False
        dcl_ids = self.search(cr, uid, [('dest_id', '=', dest_id), ('cc_id', '=', cc_id)], limit=1, context=context)
        if dcl_ids:
            dcl = self.browse(cr, uid, dcl_ids[0], fields_to_fetch=['active_from', 'inactive_from'])
            inactive_dcl = (dcl.active_from and posting_date < dcl.active_from) or (dcl.inactive_from and posting_date >= dcl.inactive_from)
        return inactive_dcl


dest_cc_link()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
