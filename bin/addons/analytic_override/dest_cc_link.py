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
from tools.translate import _


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

    def _check_analytic_lines(self, cr, uid, ids, context=None):
        """
        Displays a non-blocking message on the top of the page in case some AJI using the Dest/CC link have been booked
        outside its activation dates.
        """
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            aal_obj = self.pool.get('account.analytic.line')
            if isinstance(ids, (int, long)):
                ids = [ids]
            for dcl in self.browse(cr, uid, ids, context=context):
                if dcl.active_from or dcl.inactive_from:
                    dcl_dom = [('cost_center_id', '=', dcl.cc_id.id), ('destination_id', '=', dcl.dest_id.id)]
                    if dcl.active_from and dcl.inactive_from:
                        dcl_dom.append('|')
                    if dcl.active_from:
                        dcl_dom.append(('date', '<', dcl.active_from))
                    if dcl.inactive_from:
                        dcl_dom.append(('date', '>=', dcl.inactive_from))
                    if aal_obj.search_exist(cr, uid, dcl_dom, context=context):
                        # TODO JN: fix the display of this message (With log called on the analytic acc. obj? With action_xmlid?)
                        # [+ translate the message once it's OK]
                        self.log(cr, uid, dcl.id, _('At least one Analytic Journal Item using the combination \"%s - %s\" '
                                                    'has a Posting Date outside the activation dates selected.') %
                                 (dcl.dest_id.code or '', dcl.cc_id.code or ''))

    def _bypass(self, vals, context=None):
        """
        Returns True if at sync time the CC to be added to the Dest CC Link isn't found. It means that the CC doesn't
        exist in the current instance, so:
        - in case of a creation: the related Dest CC Link should be ignored.
        - in case of an edition: the related Dest CC Link should be DELETED (UC: in HQ create a Dest CC Link with a CC
            linked to a coordo, sync to this coordo, then edit the link with a CC not linked to this coordo).
        """
        if context is None:
            context = {}
        return context.get('sync_update_execution') and 'cc_id' in vals and not vals['cc_id']

    def create(self, cr, uid, vals, context=None):
        """
        See _bypass and _check_analytic_lines
        """
        res = False
        if not self._bypass(vals, context=context):
            res = super(dest_cc_link, self).create(cr, uid, vals, context=context)
            self._check_analytic_lines(cr, uid, res, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        See _bypass and _check_analytic_lines
        """
        if self._bypass(vals, context=context):
            res = self.unlink(cr, uid, ids, context=context)
        else:
            res = super(dest_cc_link, self).write(cr, uid, ids, vals, context=context)
            self._check_analytic_lines(cr, uid, ids, context=context)
        return res

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
