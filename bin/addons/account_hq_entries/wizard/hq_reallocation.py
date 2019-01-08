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
from lxml import etree
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

    def default_get(self, cr, uid, fields, context=None):
        # BKLG-77: check transation before showing wizard
        line_ids = context and context.get('active_ids', []) or []
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        self.pool.get('hq.entries').check_hq_entry_transaction(cr, uid,
            line_ids, self._name, context=context)
        return super(hq_analytic_reallocation, self).default_get(cr, uid, fields,
            context=context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change funding pool domain in order to include MSF Private fund
        """
        if not context:
            context = {}
        view = super(hq_analytic_reallocation, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'form':
            form = etree.fromstring(view['arch'])
            data_obj = self.pool.get('ir.model.data')
            try:
                oc_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
            except ValueError:
                oc_id = 0
            # Change OC field
            fields = form.xpath('//field[@name="cost_center_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
            # Change FP field
            try:
                fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            fp_fields = form.xpath('//field[@name="analytic_id"]')
            # Do not use line with account_id, because of NO ACCOUNT_ID PRESENCE!
            for field in fp_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', ('cost_center_ids', '=', cost_center_id), ('id', '=', %s)]" % fp_id)
            # NO NEED TO CHANGE DESTINATION_ID FIELD because NO ACCOUNT_ID PRESENCE!
            view['arch'] = etree.tostring(form)
        return view

    def onchange_cost_center(self, cr, uid, ids, cost_center_id=False, analytic_id=False):
        """
        Check given cost_center with funding pool
        """
        # Prepare some values
        res = {}
        if cost_center_id and analytic_id:
            fp_line = self.pool.get('account.analytic.account').browse(cr, uid, analytic_id)
            # Search MSF Private Fund element, because it's valid with all accounts
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            if cost_center_id not in [x.id for x in fp_line.cost_center_ids] and analytic_id != fp_id:
                res = {'value': {'analytic_id': False}}
        elif not cost_center_id:
            res = {}
        else:
            res = {'value': {'analytic_id': False}}
        return res

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

    def default_get(self, cr, uid, fields, context=None):
        # BKLG-77: check transation before showing wizard
        line_ids = context and context.get('active_ids', []) or []
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        self.pool.get('hq.entries').check_hq_entry_transaction(cr, uid,
            line_ids, self._name, context=context)
        return super(hq_reallocation, self).default_get(cr, uid, fields,
            context=context)

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
