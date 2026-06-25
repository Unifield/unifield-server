# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import  osv
from osv import fields
from tools.translate import _


class merge_ito_wizard(osv.osv_memory):
    _name = 'merge.ito.wizard'
    _description = 'Inbound Transport Order Merge'

    _columns = {
        'ito_template_id': fields.many2one('transport.order.in', string='Template ITO', help='All information of the ITO template will be written in the new ITO'),
        'cant_merge_msg': fields.text(string='The ITOs can not be merged', readonly=1),
    }

    _defaults = {
        'cant_merge_msg': '',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context={}
        res = super(merge_ito_wizard, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        if context.get('active_model', '') == 'transport.order.in' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'), _('Please select multiple Inbound Transport Orders to merge in the list view.'))
        return res

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        res = super(merge_ito_wizard, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if context.get('active_model', '') == 'transport.order.in' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'), _('Please select multiple Inbound Transport Orders to merge in the list view.'))

        res['ito_template_id'] = context['active_ids'][-1]

        cant_merge_msg = ''
        ito_errors = {}
        states, suppliers, ship_flows, cargo_refs = set(), set(), set(), set()
        ftf = ['name', 'state', 'zone_type', 'shipment_type', 'supplier_partner_id', 'shipment_flow', 'original_cargo_ref']
        for ito in self.pool.get('transport.order.in').read(cr, uid, context['active_ids'], ftf, context=context):
            # Data to check
            ito_errors[ito['name']] = []
            if ito['state'] not in ('draft', 'planned', 'prearrival', 'transit', 'entry'):
                ito_errors[ito['name']].append(_('the State must be Draft, Planned, Pre-Arrival, In Transit or At Customs Entry Point'))
            if ito['zone_type'] != 'int':
                ito_errors[ito['name']].append(_('the Zone Type must be International'))
            # Data that must be the same
            states.add(ito['state'])
            suppliers.add(ito['supplier_partner_id'])
            ship_flows.add(ito['shipment_flow'])
            cargo_refs.add(ito['original_cargo_ref'])

        for ito in ito_errors:
            if ito_errors.get(ito):
                cant_merge_msg += _('%s: %s. ') % (ito, ', '.join(ito_errors[ito]))

        if len(states) > 1:
            cant_merge_msg += _('The State of the second ITO is not consistent with the state of the template ITO. ')
        if len(suppliers) > 1:
            cant_merge_msg += _('The Supplier Partner of the second ITO is not consistent with the state of the template ITO. ')
        if len(ship_flows) > 1:
            cant_merge_msg += _('The Shipment Flow of the second ITO is not consistent with the state of the template ITO. ')
        if len(cargo_refs) > 1:
            cant_merge_msg += _('The Original Cargo ref of the second ITO is not consistent with the state of the template ITO. ')

        res['cant_merge_msg'] = cant_merge_msg

        return res


merge_ito_wizard()
