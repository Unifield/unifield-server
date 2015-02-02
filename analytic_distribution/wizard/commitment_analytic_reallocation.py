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

class int_commitment_realloc_wizard(osv.osv_memory):
    _name = 'int.commitment.realloc.wizard'
    _description = 'Intl Commitments Analytic Reallocation'

    _columns = {
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change funding pool domain in order to include MSF Private fund
        """
        if context is None:
            context = {}
        view = super(int_commitment_realloc_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
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
            fp_fields = form.xpath('//field[@name="funding_pool_id"]')
            # Do not use line with account_id, because of NO ACCOUNT_ID PRESENCE!
            for field in fp_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', ('cost_center_ids', '=', cost_center_id), ('id', '=', %s)]" % fp_id)
            # NO NEED TO CHANGE DESTINATION_ID FIELD because NO ACCOUNT_ID PRESENCE!
            # Apply changes
            view['arch'] = etree.tostring(form)
        return view

    def onchange_cost_center(self, cr, uid, ids, cost_center_id=False, funding_pool_id=False):
        """
        Check given cost_center with funding pool
        """
        # Prepare some values
        res = {}
        if cost_center_id and funding_pool_id:
            fp_line = self.pool.get('account.analytic.account').browse(cr, uid, funding_pool_id)
            # Search MSF Private Fund element, because it's valid with all accounts
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            if cost_center_id not in [x.id for x in fp_line.cost_center_ids] and funding_pool_id != fp_id:
                res = {'value': {'funding_pool_id': False}}
        elif not cost_center_id:
            res = {}
        else:
            res = {'value': {'funding_pool_id': False}}
        return res

    def button_validate(self, cr, uid ,ids, context=None):
        """
        Give all lines the given analytic distribution
        """
        if not context:
            raise osv.except_osv(_('Error'), _('Unknown error'))
        
        aal = self.pool.get('account.analytic.line')
        aaj = self.pool.get('account.analytic.journal')
        
        # get intl commitments lines in active_ids
        domain = [
            ('type', '=', 'engagement'),
            ('code', '=', 'ENGI'),
        ]
        engi_journal_ids = aaj.search(cr, uid, domain, context=context)
        if not engi_journal_ids:
            return { 'type': 'ir.actions.act_window_close', 'context': context}
        active_line_ids = context.get('active_ids', [])
        domain = [
            ('id', 'in', active_line_ids),
            ('journal_id', 'in', engi_journal_ids),
            ('imported_commitment', '=', True),
        ]
        line_ids = aal.search(cr, uid, domain, context=context)
        if not line_ids:
            return { 'type': 'ir.actions.act_window_close', 'context': context}
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        
        # wizard data
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0])
        dest_id = wiz.destination_id and wiz.destination_id.id or False
        cc_id = wiz.cost_center_id and wiz.cost_center_id.id or False
        fp_id = wiz.funding_pool_id and wiz.funding_pool_id.id or False
        if not dest_id and not cc_id and not fp_id:
            raise osv.except_osv(_('Error'), _('Nothing to reallocate'))
        
        # check AD consistency
        no_compat = aal.check_dest_cc_fp_compatibility(cr, uid, line_ids,
            dest_id=dest_id, cc_id=cc_id, fp_id=fp_id, context=context)
        if no_compat:
            # no comptatible entries found
            msg = _("No compatible entries found: %s") % (
                ",".join([nc[1] or '' for nc in no_compat]), )
            raise osv.except_osv(_('Error'), msg)
        
        # set vals and update
        vals={}
        if dest_id:
            vals['destination_id'] = dest_id
        if cc_id:
            vals['cost_center_id'] = cc_id
        if fp_id:
            vals['account_id'] = fp_id
        aal.write(cr, uid, line_ids, vals)
        
        return { 'type': 'ir.actions.act_window_close', 'context': context}

int_commitment_realloc_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
