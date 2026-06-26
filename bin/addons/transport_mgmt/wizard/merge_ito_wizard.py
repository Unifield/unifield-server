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

    def merge_ito(self, cr, uid, ids, context=None):
        """
        Method to merge ITOs
        """
        if context is None:
            context = {}

        ito_obj = self.pool.get('transport.order.in')
        data_obj =self.pool.get('ir.model.data')

        search_view_id = data_obj._get_id(cr, uid, 'transport_mgmt', 'transport_order_in_search')
        search_view = data_obj.read(cr, uid, search_view_id, ['res_id'])

        context['merge_ito'] = True
        tmpl_ito = self.browse(cr, uid, ids[0], fields_to_fetch=['ito_template_id'], context=context).ito_template_id
        merged_ito_data = {
            'merged_order': True,
            'state': tmpl_ito.state,
            'line_ids': [],
            'macroprocess_id': tmpl_ito.macroprocess_id.id,
            'transport_step_ids': [],
            'customs_regime': tmpl_ito.customs_regime,
            'transport_customs_fees_ids': [],
            'transport_transport_fees_ids': [],
        }
        # Copy lines
        for line in tmpl_ito.line_ids:
            merged_ito_data['line_ids'].append((0, 0, {
                'incoming_id': line.incoming_id and line.incoming_id.id or False,
                'description': line.description,
                'parcels_nb': line.parcels_nb,
                'volume': line.volume,
                'weight': line.weight,
                'amount': line.amount,
                'currency_id': line.currency_id and line.currency_id.id or False,
                'cargo_category': tmpl_ito.cargo_category,
                'comment': line.comment,
                'kc': line.kc,
                'dg': line.dg,
                'cs': line.cs,
            }))
        # Copy steps
        for step in tmpl_ito.transport_step_ids:
            merged_ito_data['transport_step_ids'].append((0, 0, {
                'step_id': step.step_id.id,
                'sub_step_id': step.sub_step_id and step.sub_step_id.id or False,
                'name': step.name,
                'target_end_date': step.target_end_date,
                'end_date': step.end_date,
                'comment': step.comment,
            }))
        # Copy Customs Fees
        for cfee in tmpl_ito.transport_customs_fees_ids:
            merged_ito_data['transport_customs_fees_ids'].append((0, 0, {
                'name': cfee.name.id,
                'purchase_id': cfee.purchase_id and cfee.purchase_id.id or False,
                'value': cfee.value,
                'currency_id': cfee.currency_id.id,
                'details': cfee.details,
                'validated': cfee.validated,
            }))
        # Copy Transport Fees
        for tfee in tmpl_ito.transport_transport_fees_ids:
            merged_ito_data['transport_transport_fees_ids'].append((0, 0, {
                'name': tfee.name.id,
                'purchase_id': tfee.purchase_id and tfee.purchase_id.id or False,
                'value': tfee.value,
                'currency_id': tfee.currency_id.id,
                'details': tfee.details,
                'validated': tfee.validated,
            }))

        merged_cargo_category = tmpl_ito.cargo_category
        merged_sync_refs = tmpl_ito.sync_ref and tmpl_ito.sync_ref.split(';') or []
        for ito in [ito for ito in ito_obj.browse(cr, uid, context.get('active_ids', []), context=context) if ito.id != tmpl_ito.id]:
            if merged_cargo_category != 'mixed' and merged_cargo_category != ito.cargo_category:
                merged_cargo_category = 'mixed'
            if ito.sync_ref:
                for oto_ref in ito.sync_ref.split(';'):
                    if oto_ref not in merged_sync_refs:
                        merged_sync_refs.append(oto_ref)

            for line in ito.line_ids:
                merged_ito_data['line_ids'].append((0, 0, {
                    'incoming_id': line.incoming_id and line.incoming_id.id or False,
                    'description': line.description,
                    'parcels_nb': line.parcels_nb,
                    'volume': line.volume,
                    'weight': line.weight,
                    'amount': line.amount,
                    'currency_id': line.currency_id and line.currency_id.id or False,
                    'cargo_category': ito.cargo_category,
                    'comment': line.comment,
                    'kc': line.kc,
                    'dg': line.dg,
                    'cs': line.cs,
                }))

        # Update the merged ITO data then create it
        merged_ito_data.update({'cargo_category': merged_cargo_category, 'from_sync': merged_sync_refs and True or False,
                                'sync_ref': ';'.join(merged_sync_refs)})
        merged_ito_id = ito_obj.copy(cr, uid, tmpl_ito.id, merged_ito_data, context=context)

        # Cancel all ITOs used in the merge
        ito_obj.write(cr, uid, context.get('active_ids', []), {'state': 'cancel'}, context=context)

        if context.get('merge_ito'):
            context.pop('merge_ito')

        return {
            'domain': "[('id', '=', %s)]" % (merged_ito_id,),
            'name': 'Inbound Transport Object',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'transport.order.in',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'search_view_id': search_view['res_id'],
            'context': {},
        }


merge_ito_wizard()
