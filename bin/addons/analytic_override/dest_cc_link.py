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

    def _get_current_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns a dict with key = value = current DB id.

        current_id is an internal field used to make the CC read-only except for new lines (= without DB id).
        The goal is to prevent the edition of a Dest CC Link with a CC linked to a different coordo than the previous CC.
        """
        res = {}
        for i in ids:
            res[i] = i
        return res

    def _get_cc_code(self, cr, uid, ids, name, args, context=None):
        """
        Returns a dict with key = Dest CC Link id, and value = related Cost Center code.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for dcl in self.browse(cr, uid, ids, fields_to_fetch=['cc_id'], context=context):
            res[dcl.id] = dcl.cc_id.code or ''
        return res

    def _get_dest_cc_link_to_update(self, cr, uid, analytic_acc_ids, context=None):
        """
        Returns the list of Dest CC Links for which the CC code should be updated.
        """
        if context is None:
            context = {}
        if isinstance(analytic_acc_ids, int):
            analytic_acc_ids = [analytic_acc_ids]
        return self.pool.get('dest.cc.link').search(cr, uid, [('cc_id', 'in', analytic_acc_ids)], order='NO_ORDER', context=context)

    _columns = {
        'dest_id': fields.many2one('account.analytic.account', string="Destination", required=True,
                                   domain="[('category', '=', 'DEST'), ('type', '!=', 'view')]", ondelete='cascade', select=1),
        'cc_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, sort_column='cc_code',
                                 domain="[('category', '=', 'OC'), ('type', '!=', 'view')]", ondelete='cascade', select=1),
        'cc_code': fields.function(_get_cc_code, method=True, string="Cost Center Code", type='char', size=24,
                                   readonly=True,
                                   store={
                                       'account.analytic.account': (_get_dest_cc_link_to_update, ['code'], 10),
                                       'dest.cc.link': (lambda self, cr, uid, ids, c=None: ids, ['cc_id'], 20),
                                   }),
        'cc_name': fields.related('cc_id', 'name', type="char", string="Cost Center Name", readonly=True, write_relate=False, store=False),
        'active_from': fields.date('Activation Combination Dest / CC from', required=False),
        'inactive_from': fields.date('Inactivation Combination Dest / CC from', required=False),
        'current_id': fields.function(_get_current_id, method=1, type='integer', internal=1, string="DB Id (used by the UI)"),
    }

    _order = 'dest_id, cc_code, id'

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
            if isinstance(ids, int):
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
                        self.log(cr, uid, dcl.id, _('At least one Analytic Journal Item using the combination \"%s - %s\" '
                                                    'has a Posting Date outside the activation dates selected.') %
                                 (dcl.dest_id.code or '', dcl.cc_id.code or ''))

    def create(self, cr, uid, vals, context=None):
        """
        Creates the Dest CC Combination, and:
        - displays an informative message on the top of the page if existing AJIs are using the combination outside its activation interval.
        - unticks the box "Allow all Cost Centers" from the related Dest.
          (UC: edit a Dest. having the box ticked, untick the box, add a CC and click on Cancel.
           CC isn't removed by the Cancel button as it is a o2m, so the box should remain unticked.)
        """
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        res = super(dest_cc_link, self).create(cr, uid, vals, context=context)
        self._check_analytic_lines(cr, uid, res, context=context)
        dest_id = self.read(cr, uid, res, ['dest_id'], context=context)['dest_id'][0]
        if analytic_acc_obj.search_exist(cr, uid, [('id', '=', dest_id), ('allow_all_cc', '=', True)], context=context):
            analytic_acc_obj.write(cr, uid, dest_id, {'allow_all_cc': False}, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        See _check_analytic_lines
        """
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
        if dest_id and cc_id and posting_date:
            dcl_ids = self.search(cr, uid, [('dest_id', '=', dest_id), ('cc_id', '=', cc_id)], limit=1, context=context)
            if dcl_ids:
                dcl = self.browse(cr, uid, dcl_ids[0], fields_to_fetch=['active_from', 'inactive_from'], context=context)
                inactive_dcl = (dcl.active_from and posting_date < dcl.active_from) or (dcl.inactive_from and posting_date >= dcl.inactive_from)
        return inactive_dcl

    def on_change_cc_id(self, cr, uid, ids, cc_id):
        """
        Fills in the CC Name as soon as a CC is selected
        """
        res = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        if cc_id:
            name = analytic_acc_obj.read(cr, uid, cc_id, ['name'])['name']
        else:
            name = False
        res['value'] = {'cc_name': name, }
        return res


dest_cc_link()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
