#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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


class hq_analytic_reallocation(osv.osv_memory):
    _name = 'hq.analytic.reallocation'
    _description = 'Analytic HQ reallocation wizard'

    _columns = {
        'destination_id': fields.many2one('account.analytic.account', string="Destination",required=True,  domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'analytic_id': fields.many2one('account.analytic.account', string="Funding Pool", required=True, domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        # BKLG-77: check transation before showing wizard
        line_ids = context and context.get('active_ids', []) or []
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        self.pool.get('hq.entries').check_hq_entry_transaction(cr, uid,
                                                               line_ids, self._name, context=context)
        return super(hq_analytic_reallocation, self).default_get(cr, uid, fields,
                                                                 context=context, from_web=from_web)

    def onchange_cost_center(self, cr, uid, ids, cost_center_id=False, analytic_id=False):
        return self.pool.get('analytic.distribution').\
            onchange_ad_cost_center(cr, uid, ids, cost_center_id=cost_center_id, funding_pool_id=analytic_id, fp_field_name='analytic_id')

    def button_validate(self, cr, uid ,ids, context=None):
        """
        Give all lines the given analytic distribution
        """
        if not context:
            raise osv.except_osv(_('Error'), _('Unknown error'))
        model = context.get('active_model')
        if not model:
            raise osv.except_osv(_('Error'), _('Unknown error. Please contact an administrator to resolve this problem. This is probably due to Web server error.'))
        line_ids = context.get('active_ids', [])
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0])
        vals = {
            'destination_id': False,
            'cost_center_id': False,
            'analytic_id': False,
            'free_1_id': False,
            'free_2_id': False,
        }
        for el in ['destination_id', 'cost_center_id', 'analytic_id', 'free_1_id', 'free_2_id']:
            obj = getattr(wiz, el, None)
            if obj:
                vals.update({el: getattr(obj, 'id', None)})
        self.pool.get(model).write(cr, uid, line_ids, vals)
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hq_analytic_reallocation()

class hq_reallocation(osv.osv_memory):
    _name = 'hq.reallocation'
    _description = 'HQ reallocation wizard'

    _columns = {
        'account_id': fields.many2one('account.account', string="Account", required=True,
                                      domain="[('restricted_area', '=', 'hq_lines_correction')]"),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        # BKLG-77: check transation before showing wizard
        line_ids = context and context.get('active_ids', []) or []
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        self.pool.get('hq.entries').check_hq_entry_transaction(cr, uid,
                                                               line_ids, self._name, context=context)
        return super(hq_reallocation, self).default_get(cr, uid, fields,
                                                        context=context, from_web=from_web)

    def button_validate(self, cr, uid ,ids, context=None):
        """
        Give all lines the given account
        """
        if not context:
            raise osv.except_osv(_('Error'), _('Unknown error'))
        model = context.get('active_model')
        if not model:
            raise osv.except_osv(_('Error'), _('Unknown error. Please contact an administrator to resolve this problem. This is probably due to Web server error.'))
        line_ids = context.get('active_ids', [])
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0])
        self.pool.get(model).write(cr, uid, line_ids, {'account_id': wiz.account_id and wiz.account_id.id or False,})
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hq_reallocation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
