# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from osv import osv, fields
from tools.translate import _

import base64
import time
from datetime import datetime
import re
import json
import math
import threading
import pooler
import tools
from tools.rpc_decorators import jsonrpc_orm_exposed

from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from msf_order_date import TRANSPORT_TYPE
from stock.physical_inventory import PHYSICAL_INVENTORIES_STATES

LIST_ORDER_PRIORITY = {key: _(value) for key, value in ORDER_PRIORITY}
LIST_ORDER_CATEGORY = {key: _(value) for key, value in ORDER_CATEGORY}
LIST_TRANSPORT_TYPE = {key: _(value) for key, value in TRANSPORT_TYPE}
PICKING_STATE = {
    'draft': _('Draft'),
    'auto': _('Waiting'),
    'confirmed': _('Not Available'),
    'assigned': _('Available'),
    'shipped': _('Available Shipped'),
    'done': _('Closed'),
    'dispatched': _('Dispatched'),
    'cancel': _('Cancelled'),
    'import': _('Import in progress'),
    'delivered': _('Delivered'),
    'received': _('Received'),
}
PICKING_LINE_STATE = {
    'confirmed': _('Not Available'),
    'assigned': _('Available'),
    'empty': _('Empty'),
    'processed': _('Processed'),
    'mixed': _('Partially available'),
}
MOVE_STATE = {
    'draft': _('Draft'),
    'waiting': _('Waiting'),
    'confirmed': _('Not Available'),
    'assigned': _('Available'),
    'done': _('Done'),
    'cancel': _('Cancelled'),
}
PI_STATES = {key: _(value) for key, value in PHYSICAL_INVENTORIES_STATES}


class sde_import(osv.osv_memory):
    _name = 'sde.import'
    _description = 'SDE Tools'

    _columns = {
        'json_text': fields.text(string='JSON data', help='Please put the data on a single line, with no line return. Used by IN imports and Picking actions'),
        'file': fields.binary(string='File', filters='*.xml, *.xls'),
        'filename': fields.char(string='Imported filename', size=256),
        'message': fields.text(string='Message'),
        'po_ref_for_in': fields.char(string='PO reference to find the IN', size=128),
        'pack_ref_for_in': fields.char(string='Ship/OUT reference to find the IN', size=128),
        'partner_fo_ref_for_in': fields.char(string='Supplier FO reference to find the IN', size=128),
    }

    # =============================================================================================================== #
    #                                                INCOMING SHIPMENT                                                #
    # =============================================================================================================== #
    def wizard_sde_import_in_updated(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC script to import data in an Available Updated IN
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_import_in(cr, uid, ids, context=context, in_updated=True)

    def wizard_sde_import_in(self, cr, uid, ids, context=None, in_updated=False):
        '''
        Method to use instead of the JSONRPC script to import data in an Available/Available Shipped IN
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No JSON data to use'))
        result = self.sde_in_import(cr, uid, sde_imp['json_text'], in_updated, context=context)

        return self.write(cr, uid, ids, {'message': result.get('message', '')}, context=context)

    def wizard_sde_file_to_in(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC script
        '''
        if context is None:
            context = {}

        sde_imp = self.read(cr, uid, ids[0], ['file', 'filename', 'po_ref_for_in', 'pack_ref_for_in', 'partner_fo_ref_for_in'], context=context)
        if not sde_imp['file']:
            raise osv.except_osv(_('Warning'), _('No file to import'))
        file = base64.b64decode(sde_imp['file'])

        if not sde_imp['po_ref_for_in'] and not sde_imp['partner_fo_ref_for_in']:
            raise osv.except_osv(_('Warning'), _('Please add at least the PO reference or the Supplier FO reference to find the IN'))
        msg = self.sde_file_to_in(cr, uid, sde_imp['filename'], file, sde_imp['po_ref_for_in'],
                                  sde_imp['pack_ref_for_in'], sde_imp['partner_fo_ref_for_in'], context=context)

        return self.write(cr, uid, ids, {'message': msg}, context=context)

    def generate_sde_dispatched_packing_list_report(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC script
        '''
        if context is None:
            context = {}
        return self.pool.get('shipment').generate_dispatched_packing_list_report(cr, uid, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_in_import')
    def sde_in_import(self, cr, uid, json_text, in_updated=False, context=None):
        '''
        Method used by the SDE script to import JSON data.
        A pagination system has been added to the import to allow users to import several JSONs for the same document
        before trying to process the data. The keys sde_pagination_id, sde_import_page and sde_import_type are necessary
        to allow the pagination.
        '''
        if context is None:
            context = {}

        pagi_obj = self.pool.get('sde.import.pagination')
        pick_obj = self.pool.get('stock.picking')
        in_proc_obj = self.pool.get('stock.incoming.processor')
        in_simu_obj = self.pool.get('wizard.import.in.simulation.screen')

        context['sde_flow'] = True
        result = {'error': False, 'message': 'Done'}
        pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False
        pagi_json_text = ''
        pagi_json_data = []
        try:
            json_data = json.loads(json_text)

            sde_pagi_error = False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_type' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_type are mandatory to use the pagination in the SDE IN import')
                else:
                    sde_pagi_end_msg = json_data['sde_pagination_type'] == 'end' and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, 1, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, 1, sde_pagi_id, context=context)
                        if sde_pagi['state'] == 'done':
                            sde_pagi_error = _('This SDE import ID is already finished, please use a new SDE import ID')
                        elif sde_pagi_page - sde_pagi['page'] != 1:
                            sde_pagi_error = _('The page number must be in sequential order without gaps: last page imported %s, imported page %s') \
                                % (sde_pagi['page'], json_data['sde_pagination_page'])
                        else:
                            # Update the existing JSON with the new data in the key packing_data
                            # Use from_pack, to_pack and parcel_ids to see is the pack already exist
                            pagi_json_text = sde_pagi['pagination_json_text']
                            pagi_json_data = json.loads(pagi_json_text)
                            parcel_keys = sde_pagi['pagination_keys'].split(',')
                            for pack_data in json_data.get('packing_data', []):
                                parcels = []
                                for parcel in pack_data.get('parcel_ids', []):
                                    if parcel.get('parcel_id'):
                                        parcel_id = str(parcel['parcel_id']).strip()
                                        if ',' in parcel_id:
                                            raise osv.except_osv(_('Warning'), _('parcel_id "%s": Commas (,) are not allowed in Parcel ID')
                                                                 % (parcel_id,))
                                        parcels.append(parcel_id)
                                parcel_key = 'f%st%spl%spar%s' % (pack_data.get('parcel_from', 0), pack_data.get('parcel_to', 0),
                                                                  pack_data.get('packing_list', ''), ''.join(parcels))
                                if parcel_key in parcel_keys:
                                    # Find the correct existing packing_data to update in
                                    for pagi_pack_data in pagi_json_data.get('packing_data', []):
                                        pagi_parcels = []
                                        for pagi_parcel in pagi_pack_data.get('parcel_ids', []):
                                            if pagi_parcel.get('parcel_id'):
                                                pagi_parcels.append(str(pagi_parcel['parcel_id']).strip())
                                        pagi_parcel_key = 'f%st%spl%spar%s' % (pagi_pack_data.get('parcel_from', 0), pagi_pack_data.get('parcel_to', 0),
                                                                               pagi_pack_data.get('packing_list', ''), ''.join(pagi_parcels))
                                        if pagi_parcel_key == parcel_key:
                                            pagi_json_data['packing_data'][pagi_json_data['packing_data'].index(pagi_pack_data)]['move_lines'].extend(pack_data['move_lines'])
                                            break
                                else:
                                    pagi_json_data['packing_data'].append(pack_data)
                                    parcel_keys.append(parcel_key)

                            pagi_json_text = json.dumps(pagi_json_data)
                            pagi_vals = {
                                'pagination_json_text': pagi_json_text,
                                'pagination_keys': ','.join(parcel_keys),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, 1, sde_pagi_ids[0], pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s updated%s with page %s') \
                                % (json_data['sde_pagination_id'], sde_pagi_end_msg, sde_pagi_page)
                    else:
                        if sde_pagi_page != 1:
                            sde_pagi_error = _('The first page of a paginated SDE import must be 1')
                        else:
                            parcel_keys = []
                            for pack_data in json_data.get('packing_data', []):
                                parcels = []
                                for parcel in pack_data.get('parcel_ids', []):
                                    if parcel.get('parcel_id'):
                                        parcel_id = str(parcel['parcel_id']).strip()
                                        if ',' in parcel_id:
                                            raise osv.except_osv(_('Warning'), _('parcel_id "%s": Commas (,) are not allowed in Parcel ID')
                                                                 % (parcel_id,))
                                        parcels.append(parcel_id)
                                parcel_keys.append('f%st%spl%spar%s' % (pack_data.get('parcel_from', 0), pack_data.get('parcel_to', 0),
                                                                        pack_data.get('packing_list', ''), ''.join(parcels)))
                            sde_pagi_vals = {
                                'state': json_data['sde_pagination_type'] == 'end' and 'done' or 'progress',
                                'pagination_json_id': json_data['sde_pagination_id'],
                                'pagination_json_text': json_text,
                                'pagination_keys': ','.join(parcel_keys),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, 1, sde_pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s created%s') % (json_data['sde_pagination_id'], sde_pagi_end_msg)

            if sde_pagi_error:
                raise osv.except_osv(_('Error'), _('An error occurred during the management of the paginated SDE import "%s": %s')
                                     % (json_data.get('sde_pagination_id'), sde_pagi_error))
            elif not json_data.get('sde_pagination_id') or (sde_pagi_end_msg and sde_pagi_id):
                # Get the correct JSON data if the pagination has been used
                if sde_pagi_id and pagi_json_text and pagi_json_data:
                    json_text = pagi_json_text
                    json_data = pagi_json_data

                # get the IN with the Ship Ref or the Origin
                in_id = self.get_incoming_id_from_json(cr, uid, json_data, in_updated, context=context)

                # If the IN is Available Shipped/Updated reset as much data as possible, compared to the PO
                if self.pool.get('stock.picking').read(cr, uid, in_id, ['state'], context=context)['state'] in ['shipped', 'updated']:
                    self.reset_in_available_shipped_updated(cr, uid, [in_id], context=context)

                in_proc_ids = in_proc_obj.search(cr, uid, [('picking_id', '=', in_id), ('draft', '=', True)], context=context)
                if in_proc_ids:
                    in_processor = in_proc_ids[0]
                    if not in_proc_obj.read(cr, uid, in_processor, ['sde_updated'], context=context)['sde_updated']:
                        in_proc_obj.write(cr, uid, in_processor, {'sde_updated': True}, context=context)
                else:
                    # create stock.incoming.processor and its stock.move.in.processor
                    in_processor = in_proc_obj.create(cr, uid, {'picking_id': in_id, 'sde_updated': True}, context=context)
                    # import all lines and set qty to zero
                    in_proc_obj.create_lines(cr, uid, in_processor, context=context)

                in_proc_obj.launch_simulation(cr, uid, in_processor, context=context)

                simu_id = context.get('simu_id')

                # create simulation screen to get the simulation report:
                in_simu_obj.write(cr, uid, [simu_id], {'json_text': json_text, 'with_pack': True}, context=context)

                in_simu_obj.launch_simulate(cr, 1, [simu_id], context=context)
                file_res = pick_obj.generate_simulation_screen_report(cr, uid, simu_id, context=context)

                simu_data = in_simu_obj.read(cr, uid, simu_id, ['import_error_ok', 'message'], context=context)
                if simu_data['message'] or pagi_msg:
                    result.update({'error': simu_data['import_error_ok'], 'message': simu_data['message'] or pagi_msg})
                # Only import when all the data is correct
                if not simu_data['import_error_ok']:
                    in_simu_obj.launch_import(cr, uid, [simu_id], context=context)
                    # Log the update
                    in_name = pick_obj.read(cr, uid, in_id, ['name'], context=context)['name']
                    self.pool.get('sde.update.log').create(cr, 1, {'date': datetime.now(), 'doc_type': 'in', 'doc_ref': in_name}, context=context)

                # attach the simulation report to the IN
                self.pool.get('ir.attachment').create(cr, uid, {
                    'name': 'SDE_simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                    'datas_fname': 'SDE_simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                    'description': 'IN simulation screen',
                    'res_model': 'stock.picking',
                    'res_id': in_id,
                    'datas': file_res.get('result'),
                })
            elif pagi_msg:
                result['message'] = pagi_msg
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_file_to_in')
    def sde_file_to_in(self, cr, uid, file_path, file, po_ref, pack_ref, partner_fo_ref, context=None):
        '''
        Method used by the SDE script to attach a file to an IN
        '''
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')

        msg = False
        try:
            if isinstance(file, bytes):
                file_data = file
            elif isinstance(file, str):
                file_data = file.encode('utf-8')
            else:  # Binary expected
                file_data = file.data

            # Get the IN with the references given
            in_id = self.get_incoming_id_from_refs(cr, uid, po_ref, pack_ref, partner_fo_ref, False, context=context)
            in_name = pick_obj.read(cr, uid, in_id, ['name'], context=context)['name']

            # attach the simulation file to the IN
            filename = 'SDE_incoming_shipment_simulation_file_%s.%s' % (time.strftime('%Y_%m_%d_%H_%M'), file_path.split('.')[-1])
            self.pool.get('ir.attachment').create(cr, uid, {
                'name': filename,
                'datas_fname': filename,
                'description': 'SDE file for IN',
                'res_model': 'stock.picking',
                'res_id': in_id,
                'datas': base64.b64encode(file_data).decode('utf8'),
            })
            msg = _('%s has been attached to %s') % (filename, in_name)
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                msg = e.value
            else:
                msg = e.args and '. '.join(e.args) or e

        return msg

    def get_incoming_id_from_json(self, cr, uid, json_data, in_updated, context=None):
        '''
        The Origin field is required in the file, but not the Ship Reference. If the Ship Reference is filled, only
        Available Shipped INs will be searched, Available otherwise
        '''
        if context is None:
            context = {}

        # Search the file
        if 'origin' not in json_data:
            raise osv.except_osv(_('Error'), _('Main key "origin" not found in the given JSON'))
        if not json_data.get('origin') and not json_data.get('partner_fo_ref'):
            raise osv.except_osv(_('Error'), _('Either the main key "origin" or the main key "partner_fo_ref" shouldn\'t be empty'))

        po_name = json_data.get('origin') and json_data['origin'].strip().upper() or False
        partner_fo_ref = json_data.get('partner_fo_ref') and json_data['partner_fo_ref'].strip().upper() or False
        ship_ref = json_data.get('freight_number') and json_data['freight_number'].strip().upper() or False

        # Search the IN
        return self.get_incoming_id_from_refs(cr, uid, po_name, ship_ref, partner_fo_ref, in_updated, context=context)

    def get_incoming_id_from_refs(self, cr, uid, po_name, ship_ref, partner_fo_ref, in_updated, context=None):
        if context is None:
            context = {}

        if not po_name and not partner_fo_ref:
            raise osv.except_osv(_('Error'), _('Both the PO Reference and the Supplier FO Reference must not be empty'))

        po_obj = self.pool.get('purchase.order')
        pick_obj = self.pool.get('stock.picking')

        po_id = False
        if po_name:
            if po_name.find(':') != -1:
                for part in po_name.split(':'):
                    re_res = re.findall(r'PO[0-9]+$', part, re.I)
                    if re_res:
                        po_name = part
                        break
            po_id = po_obj.search(cr, uid, [('name', '=ilike', po_name)], context=context)
            if not po_id:
                raise osv.except_osv(_('Error'), _('PO with name %s not found') % po_name)
        if not po_id and partner_fo_ref:
            po_id = po_obj.search(cr, uid, [('partner_ref', 'ilike', partner_fo_ref)], context=context)
            if not po_id:
                raise osv.except_osv(_('Error'), _('PO with Supplier FO reference %s not found') % partner_fo_ref)

        # Search the IN
        if not po_id:
            raise osv.except_osv(_('Error'), _('PO was not found with the given references'))
        in_domain = [('purchase_id', '=', po_id[0]), ('type', '=', 'in'), ('claim', '=', False)]
        error_msg = _('No available IN found for the given PO %s') % po_name

        in_id = False
        # Look for Available Updated IN first
        if in_updated:
            in_upd_domain = in_domain + [('state', '=', 'updated')]
            if ship_ref:
                in_upd_domain.append(('shipment_ref', '=ilike', ship_ref))
            in_id = pick_obj.search(cr, uid, in_upd_domain, context=context)

        if not in_id:
            if ship_ref:
                in_domain.extend([('shipment_ref', '=ilike', ship_ref), ('state', '=', 'shipped')])
                error_msg = _('No available shipped IN found for the given PO %s and the given Ship Reference %s') % (po_name, ship_ref)
                in_id = pick_obj.search(cr, uid, in_domain, context=context)
            else:
                in_id = pick_obj.search(cr, uid, in_domain + [('state', '=', 'assigned')], context=context)
                if not in_id:
                    in_id = pick_obj.search(cr, uid, in_domain + [('state', 'in', ['assigned', 'shipped'])], context=context)
        if not in_id:
            raise osv.except_osv(_('Error'), error_msg)
        elif len(in_id) > 1:
            raise osv.except_osv(_('Error'), _('Unifield was unable to identify the correct IN since multiple documents match the PO reference %s received from SDE. Please check the data sent and add more references') % (po_name,))

        return in_id[0]

    def reset_in_available_shipped_updated(self, cr, uid, ids, context=None):
        '''
        For each move of the Available Shipped/Updated IN, reset as much data as possible:
            - Merge the quantities of split lines and delete the splits
            - Remove any BN/ED info
            - Restore the product, quantity and unit price of the linked PO line
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        move_obj = self.pool.get('stock.move')

        cr.execute("""
            SELECT m.id, m.picking_id, m.line_number, m.purchase_line_id, m.product_qty,
                COALESCE(pl.product_id, m.product_id), COALESCE(pl.price_unit, m.price_unit)
            FROM stock_move m LEFT JOIN purchase_order_line pl ON m.purchase_line_id = pl.id
            WHERE m.state = 'assigned' AND m.picking_id IN %s AND m.product_qty != 0
            """, (tuple(ids),))
        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2], x[3])
            if key not in data:
                data[key] = {'product_id': x[5], 'product_qty': 0, 'price_unit': x[6], 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['product_qty'] += x[4]
        for key in data:
            move_vals = {'product_id': data[key]['product_id'], 'product_qty': data[key]['product_qty'],
                         'product_uos_qty': data[key]['product_qty'], 'price_unit': data[key]['price_unit'],
                         'prodlot_id': False, 'expired_date': False}
            move_obj.write(cr, uid, data[key]['master'], move_vals, context=context)
        move_obj.unlink(cr, uid, to_del, force=True, context=context)

        return True

    # =============================================================================================================== #
    #                                                 PICKING TICKET                                                  #
    # =============================================================================================================== #
    def wizard_sde_picking_ticket_import(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to import on a Picking Tickets
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_picking_ticket_actions(cr, uid, ids, 'picking_import', context=context)

    def wizard_sde_picking_ticket_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to set a banner message on Picking Tickets
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_picking_ticket_actions(cr, uid, ids, 'banner_msg', context=context)

    def wizard_sde_picking_ticket_remove_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to remove a banner message on Picking Tickets
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_picking_ticket_actions(cr, uid, ids, 'remove_banner_msg', context=context)

    def wizard_sde_picking_ticket_export(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export Picking
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_picking_ticket_actions(cr, uid, ids, 'picking_export', context=context)

    def wizard_sde_picking_ticket_export_lines(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export Picking Tickets with lines
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_picking_ticket_actions(cr, uid, ids, 'picking_export_lines', context=context)

    def wizard_sde_picking_ticket_actions(self, cr, uid, ids, action, context=None):
        '''
        Method to use instead of the JSONRPC
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No JSON data to use'))

        result = []
        if action == 'picking_import':
            result = self.sde_picking_ticket_import(cr, uid, sde_imp['json_text'], context=context)
        elif action == 'banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'pick', False, context=context)
        elif action == 'remove_banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'pick', True, context=context)
        elif action == 'picking_export':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'picking', with_lines=False, context=context)
        elif action == 'picking_export_lines':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'picking', with_lines=True, context=context)

        return self.write(cr, uid, ids, {'message': json.dumps(result)}, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_picking_ticket_import')
    def sde_picking_ticket_import(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to import JSON data.
        A pagination system has been added to the import to allow users to import several JSONs for the same document
        before trying to process the data. The keys sde_pagination_id, sde_pagination_page and sde_pagination_end are
        necessary to allow the pagination.
        '''
        if context is None:
            context = {}

        pagi_obj = self.pool.get('sde.import.pagination')
        pick_obj = self.pool.get('stock.picking')
        wiz_imp_obj = self.pool.get('wizard.pick.import')

        context['sde_flow'] = True
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        result = {'database': instance_name, 'error': False, 'message': _('Done')}
        pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False
        pagi_json_text = ''
        pagi_json_data, pick_ids = [], []
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)') % (json_data['database'], instance_name))

            sde_pagi_error = False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_end' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_end are mandatory to use the pagination in the SDE Picking Ticket import')
                else:
                    sde_pagi_end_msg = json_data.get('sde_pagination_end') and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, 1, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, 1, sde_pagi_id, context=context)
                        if sde_pagi['state'] == 'done':
                            sde_pagi_error = _('This SDE import ID is already finished, please use a new SDE import ID')
                        elif sde_pagi_page - sde_pagi['page'] != 1:
                            sde_pagi_error = _('The page number must be in sequential order without gaps: last page imported %s, imported page %s') \
                                % (sde_pagi['page'], json_data['sde_pagination_page'])
                        else:
                            # Update the existing JSON with the new data in the key move_lines
                            pagi_json_text = sde_pagi['pagination_json_text']
                            pagi_json_data = json.loads(pagi_json_text)

                            pagi_json_data['move_lines'].extend(json_data['move_lines'])
                            pagi_json_text = json.dumps(pagi_json_data)

                            pagi_vals = {
                                'pagination_json_text': pagi_json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, 1, sde_pagi_ids[0], pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s updated%s with page %s') % (json_data['sde_pagination_id'], sde_pagi_end_msg, sde_pagi_page)
                    else:
                        if sde_pagi_page != 1:
                            sde_pagi_error = _('The first page of a paginated SDE import must be 1')
                        else:
                            sde_pagi_vals = {
                                'state': json_data.get('sde_pagination_end') and 'done' or 'progress',
                                'pagination_json_id': json_data['sde_pagination_id'],
                                'pagination_json_text': json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, 1, sde_pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s created%s') % (json_data['sde_pagination_id'], sde_pagi_end_msg)

            if sde_pagi_error:
                raise osv.except_osv(_('Error'), _('An error occurred during the management of the paginated SDE import "%s": %s')
                                     % (json_data.get('sde_pagination_id'), sde_pagi_error))
            elif not json_data.get('sde_pagination_id') or (sde_pagi_end_msg and sde_pagi_id):
                # Get the correct JSON data if the pagination has been used
                if sde_pagi_id and pagi_json_text and pagi_json_data:
                    json_text = pagi_json_text
                    json_data = pagi_json_data

                # Get the Picking Ticket from the name
                if not json_data.get('name'):
                    raise osv.except_osv(_('Error'), _('The main key "name" is mandatory and should not be empty'))
                pick_ids = self.get_stock_picking_from_refs(cr, uid, [json_data['name']], ['assigned'], 'out', 'picking', context=context)
                pick_id = pick_ids[0]
                pick = pick_obj.read(cr, uid, pick_id, ['name', 'sde_updated'], context=context)
                if pick['sde_updated']:
                    raise osv.except_osv(_('Error'), _('The Picking Ticket %s has already been updated by SDE. Please process the imported data in UniField or reset the SDE update there') % (pick['name'],))

                # Reset the data of the imported lines
                if not json_data.get('move_lines'):
                    raise osv.except_osv(_('Error'), _('The main key "move_lines" is mandatory and should not be empty'))
                lines_to_reset = []
                for move_data in json_data['move_lines']:
                    if isinstance(move_data.get('line_number', False), int) and move_data['line_number'] not in lines_to_reset:
                        lines_to_reset.append(move_data['line_number'])
                if lines_to_reset:
                    self.reset_pick_lines(cr, uid, [pick_id], lines_to_reset, context=context)

                # Import the data
                wiz_id = wiz_imp_obj.create(cr, uid, {'picking_id': pick_id, 'json_text': json_text}, context=context)
                imp_res = wiz_imp_obj.import_pick_xls(cr, uid, [wiz_id], context=context)

                final_msg = pagi_msg or _('Done')
                if imp_res:
                    final_msg = final_msg + _('. The lines number %s were ignored during the import') % (', '.join(imp_res),)
                result['message'] = final_msg

                # Set the PICK as sde_updated and remove the banner message
                pick_obj.write(cr, uid, pick_id, {'sde_updated': True, 'sde_update_msg': False}, context=context)

                # Log the update
                self.pool.get('sde.update.log').create(cr, 1, {'date': datetime.now(), 'doc_type': 'pick', 'doc_ref': pick['name']}, context=context)
            elif pagi_msg:
                result['message'] = pagi_msg
        except Exception as e:
            cr.rollback()
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_picking_ticket_msg')
    def sde_picking_ticket_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of Picking Tickets
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'pick', False, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_picking_ticket_remove_msg')
    def sde_picking_ticket_remove_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to remove a 'SDE is updating' message on a list of Picking Tickets
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'pick', True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_picking_ticket_export_lines')
    def sde_picking_ticket_export_lines(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on Picking Tickets with lines
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'picking', with_lines=True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_picking_ticket_export')
    def sde_picking_ticket_export(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on Picking Tickets
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'picking', with_lines=False, context=context)

    def get_picking_ticket_export_data(self, cr, uid, ids, offset, limit, with_lines=False, context=None):
        """
        Get info from PICKs, its latest Track Change and info from their moves when needed
        """
        if context is None:
            context = {}

        sql_lines_col, sql_lines_join, sql_lines_group, sql_lines_order = '', '', '', ''
        if with_lines:  # Additional data for the lines
            sql_lines_col = """,
                m.id, -- 22
                m.line_number, -- 23
                pp.default_code, -- 24
                pt.name, -- 25
                pis.name, -- 26
                pno.name, -- 27
                CASE WHEN m.sale_line_id IS NOT NULL AND sl.product_id != m.product_id 
                    THEN CONCAT(pp.default_code, ' [', pt.name, ']') ELSE '' END, -- 28
                m.comment, -- 29
                l.name, -- 30
                m.product_qty, -- 31
                lot.name, -- 32
                m.expired_date, -- 33
                pcc.cold_chain, -- 34 kc_check
                pp.dangerous_goods, -- 35 dg_check
                pp.controlled_substance, -- 36 np_check
                m.state, -- 37
                pp.id, -- 38
                l.id, -- 39
                lot.id -- 40
            """
            sql_lines_join = """
                LEFT JOIN product_product pp ON m.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_cold_chain pcc ON pp.cold_chain = pcc.id
                LEFT JOIN product_international_status pis ON pp.international_status = pis.id
                LEFT JOIN product_nomenclature pno ON pt.nomen_manda_0 = pno.id
                LEFT JOIN sale_order_line sl ON m.sale_line_id = sl.id
                LEFT JOIN stock_location l ON m.location_id = l.id
                LEFT JOIN stock_production_lot lot ON m.prodlot_id = lot.id
            """
            sql_lines_group = """, m.id,  m.line_number, pp.default_code, pt.name, sl.product_id, pis.name, pno.name,
                m.comment, l.name, m.product_qty, lot.name, m.expired_date, pcc.cold_chain, pp.dangerous_goods,
                pp.controlled_substance, m.state, pp.id, l.id, lot.id"""
            sql_lines_order = ', m.line_number, m.id'
        cr.execute("""
            SELECT
                p.name, -- 0
                p.date, -- 1
                p.origin, -- 2
                s.client_order_ref, -- 3
                inc.name, -- 4
                p.order_category, -- 5
                s.delivery_requested_date, -- 6
                COALESCE(s.details, p.details), -- 7
                s.transport_type, -- 8
                s.priority, -- 9
                s.ready_to_ship_date, -- 10
                par.name, -- 11
                addr.street, -- 12
                addr.street2, -- 13
                co.name, -- 14
                addr.phone, -- 15
                COUNT(DISTINCT(m.line_number)), -- 16
                p.sde_updated, -- 17
                p.state, -- 18
                p.line_state, -- 19
                MAX(a.log), -- 20
                MAX(a.timestamp) -- 21
                """ + sql_lines_col + """
            FROM stock_move m
                LEFT JOIN stock_picking p ON m.picking_id = p.id
                LEFT JOIN audittrail_log_line a ON p.id = a.res_id AND object_id = (SELECT id FROM ir_model WHERE model = 'stock.picking' LIMIT 1)
                LEFT JOIN stock_picking inc ON p.incoming_id = inc.id
                LEFT JOIN sale_order s ON p.sale_id = s.id
                LEFT JOIN res_partner par ON p.partner_id = par.id
                LEFT JOIN res_partner_address addr ON p.address_id = addr.id
                LEFT JOIN res_country co ON addr.country_id = co.id
                """ + sql_lines_join + """
            WHERE p.id IN %s
            GROUP BY p.id, p.name, p.date, p.origin, s.client_order_ref, inc.name, p.order_category,
                s.delivery_requested_date, COALESCE(s.details, p.details), s.transport_type, s.priority,
                s.ready_to_ship_date, par.name, addr.street, addr.street2, co.name, addr.phone, p.sde_updated, p.state,
                p.line_state""" + sql_lines_group + """
            ORDER BY p.id""" + sql_lines_order + """ OFFSET %s LIMIT %s
        """, (tuple(ids), offset, limit)) # not_a_user_entry

        return cr.fetchall()

    def create_picking_ticket_paginated_export(self, cr, uid, ids, pagi_ref, page, last_page, offset, limit, with_lines=False, context=None):
        '''
        Method to be used in the background to create the paginated exports beyond page 1
        '''
        if context is None:
            context = {}

        new_cr = pooler.get_db(cr.dbname).cursor()

        data = {}
        for pick in self.get_picking_ticket_export_data(new_cr, uid, ids, offset, limit, with_lines=with_lines, context=context):
            if not data.get(pick[0]):
                partner_data = [pick[11], _('Supply Responsible')]
                address_data = []
                if pick[12]:
                    address_data.append(pick[12])
                if pick[13]:
                    address_data.append(pick[13])
                if pick[14]:
                    address_data.append(pick[14])
                if address_data:
                    partner_data.append(' '.join(address_data))
                if pick[15]:
                    partner_data.append(pick[15])

                data[pick[0]] = {
                    'date': pick[1],
                    'origin': pick[2] or '',
                    'client_po_ref': pick[3] or '',
                    'incoming_ref': pick[4] or '',
                    'order_category': pick[5] and LIST_ORDER_CATEGORY[pick[5]] or '',
                    'delivery_requested_date': pick[6] or '',
                    'fo_details': pick[7] or '',
                    'transport_type': pick[8] and LIST_TRANSPORT_TYPE[pick[8]] or '',
                    'priority': pick[9] and LIST_ORDER_PRIORITY[pick[9]] or '',
                    'ready_to_ship_date': pick[10] or '',
                    'delivery_address': partner_data and '; '.join(partner_data) or '',
                    'total_items': pick[16] or 0,
                    'updated_by_sde': pick[17] or False,
                    'state': pick[18] and PICKING_STATE[pick[18]] or '',
                    'line_state': pick[19] and PICKING_LINE_STATE[pick[19]] or '',
                    'latest_log': pick[20] or '',
                    'latest_log_date': pick[21] or '',
                }

            if with_lines and len(pick) > 22:
                if 'move_lines' not in data[pick[0]]:
                    data[pick[0]]['move_lines'] = []
                data[pick[0]]['move_lines'].append({
                    'line_number': pick[23],
                    'product_code': pick[24],
                    'product_name': pick[25],
                    'product_creator': pick[26],
                    'nomen_main_type': pick[27],
                    'changed_product_code': pick[28] or '',
                    'comment': pick[29] or '',
                    'source_location': pick[30],
                    'qty_in_stock': self.get_qty_available(new_cr, uid, pick[38], pick[39], pick[40], context=context) or 0,
                    'product_qty': pick[31] or 0,
                    'qty_to_process': None,  # Left empty to force SDE to change the value
                    'prodlot_id': pick[32] or '',
                    'expired_date': pick[33] or '',
                    'kc_check': pick[34] or False,
                    'dg_check': pick[35] == 'True' and _('True') or pick[35] == 'no_know' and _('Unknown') or _('False'),
                    'np_check': pick[36] or False,
                    'state': pick[37] and MOVE_STATE[pick[37]] or '',
                })

        pagi_vals = {'pagination_json_id': pagi_ref, 'pagination_json_text': json.dumps(data), 'doc_type': 'pick',
                     'page': page, 'last_page': page == last_page, 'with_lines': with_lines}
        self.pool.get('sde.export.pagination').create(new_cr, 1, pagi_vals, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True

    def reset_pick_lines(self, cr, uid, ids, line_numbers, context=None):
        '''
        For each move of the Available Picking Ticket whose line_number is in the import, reset as much data as possible:
            - Merge the quantities of split lines and delete the splits
            - Remove any BN/ED info
            - Sum the quantities and set the quantity to process at 0
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        move_obj = self.pool.get('stock.move')

        ln_sql = ""
        if line_numbers:
            if len(line_numbers) == 1:
                ln_sql = " AND line_number = %s" % (line_numbers[0],)
            else:
                ln_sql = " AND line_number IN %s" % (tuple(line_numbers),)
        cr.execute("""
                   SELECT id, picking_id, line_number, product_qty
                   FROM stock_move
                   WHERE state = 'assigned' AND picking_id IN %s AND product_qty != 0
            """ + ln_sql, (tuple(ids),)) # not_a_user_entry

        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2])
            if key not in data:
                data[key] = {'product_qty': 0, 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['product_qty'] += x[3]
        for key in data:
            move_vals = {'product_qty': data[key]['product_qty'], 'product_uos_qty': data[key]['product_qty'],
                         'qty_to_process': 0, 'prodlot_id': False, 'expired_date': False}
            move_obj.write(cr, uid, data[key]['master'], move_vals, context=context)
        move_obj.unlink(cr, uid, to_del, force=True, context=context)

        return True

    # =============================================================================================================== #
    #                                              OUT (DELIVERY ORDER)                                               #
    # =============================================================================================================== #
    def wizard_sde_out_import(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to import on an OUT
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'out_import', context=context)

    def wizard_sde_out_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to set a banner message on OUTs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'banner_msg', context=context)

    def wizard_sde_out_remove_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to remove a banner message on OUTs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'remove_banner_msg', context=context)

    def wizard_sde_out_check_availability(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to check the availability of OUTs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'check_availability', context=context)

    def wizard_sde_out_export(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export OUTs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'out_export', context=context)

    def wizard_sde_out_export_lines(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export OUTs with lines
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_out_actions(cr, uid, ids, 'out_export_lines', context=context)

    def wizard_sde_out_actions(self, cr, uid, ids, action, context=None):
        '''
        Method to use instead of the JSONRPC
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No JSON data to use'))

        result = []
        if action == 'out_import':
            result = self.sde_out_import(cr, uid, sde_imp['json_text'], context=context)
        elif action == 'banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'out', False, context=context)
        elif action == 'remove_banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'out', True, context=context)
        elif action == 'check_availability':
            result = self.sde_out_check_availability(cr, uid, sde_imp['json_text'], context=context)
        elif action == 'out_export':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'standard', with_lines=False, context=context)
        elif action == 'out_export_lines':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'standard', with_lines=True, context=context)

        return self.write(cr, uid, ids, {'message': json.dumps(result)}, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_out_import')
    def sde_out_import(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to import JSON data.
        A pagination system has been added to the import to allow users to import several JSONs for the same document
        before trying to process the data. The keys sde_pagination_id, sde_pagination_page and sde_pagination_end are
        necessary to allow the pagination.
        '''
        if context is None:
            context = {}

        pagi_obj = self.pool.get('sde.import.pagination')
        pick_obj = self.pool.get('stock.picking')
        out_proc_obj = self.pool.get('outgoing.delivery.processor')
        wiz_imp_obj = self.pool.get('wizard.out.import')

        context['sde_flow'] = True
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        result = {'database': instance_name, 'error': False, 'message': _('Done')}
        pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False
        pagi_json_text = ''
        pagi_json_data, out_ids = [], []
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            sde_pagi_error = False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_end' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_end are mandatory to use the pagination in the SDE OUT import')
                else:
                    sde_pagi_end_msg = json_data.get('sde_pagination_end') and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, 1, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, 1, sde_pagi_id, context=context)
                        if sde_pagi['state'] == 'done':
                            sde_pagi_error = _('This SDE import ID is already finished, please use a new SDE import ID')
                        elif sde_pagi_page - sde_pagi['page'] != 1:
                            sde_pagi_error = _('The page number must be in sequential order without gaps: last page imported %s, imported page %s') \
                                % (sde_pagi['page'], json_data['sde_pagination_page'])
                        else:
                            # Update the existing JSON with the new data in the key move_lines
                            pagi_json_text = sde_pagi['pagination_json_text']
                            pagi_json_data = json.loads(pagi_json_text)

                            pagi_json_data['move_lines'].extend(json_data['move_lines'])
                            pagi_json_text = json.dumps(pagi_json_data)

                            pagi_vals = {
                                'pagination_json_text': pagi_json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, 1, sde_pagi_ids[0], pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s updated%s with page %s') % (
                                json_data['sde_pagination_id'], sde_pagi_end_msg, sde_pagi_page)
                    else:
                        if sde_pagi_page != 1:
                            sde_pagi_error = _('The first page of a paginated SDE import must be 1')
                        else:
                            sde_pagi_vals = {
                                'state': json_data.get('sde_pagination_end') and 'done' or 'progress',
                                'pagination_json_id': json_data['sde_pagination_id'],
                                'pagination_json_text': json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, 1, sde_pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s created%s') % (json_data['sde_pagination_id'], sde_pagi_end_msg)

            if sde_pagi_error:
                raise osv.except_osv(_('Error'), _('An error occurred during the management of the paginated SDE import "%s": %s')
                                     % (json_data.get('sde_pagination_id'), sde_pagi_error))
            elif not json_data.get('sde_pagination_id') or (sde_pagi_end_msg and sde_pagi_id):
                # Get the correct JSON data if the pagination has been used
                if sde_pagi_id and pagi_json_text and pagi_json_data:
                    json_text = pagi_json_text
                    json_data = pagi_json_data

                # Get the OUT from the name
                if not json_data.get('name'):
                    raise osv.except_osv(_('Error'), _('The main key "name" is mandatory and should not be empty'))
                out_ids = self.get_stock_picking_from_refs(cr, uid, [json_data['name']], ['assigned'], 'out', 'standard', context=context)
                out_id = out_ids[0]
                out = pick_obj.read(cr, uid, out_id, ['name', 'sde_updated'], context=context)
                if out['sde_updated']:
                    raise osv.except_osv(_('Error'), _('The OUT %s has already been updated by SDE. Please process the imported data in UniField or reset the SDE update on the popup')
                                         % (out['name'],))

                if not json_data.get('move_lines'):
                    raise osv.except_osv(_('Error'), _('The main key "move_lines" is mandatory and should not be empty'))

                # Get the existing saved data
                out_proc_ids = out_proc_obj.search(cr, uid, [('picking_id', '=', out_id), ('draft', '=', True)], context=context)
                if not out_proc_ids:
                    # Create outgoing.delivery.processor and its lines
                    out_proc_id = out_proc_obj.create(cr, uid, {'picking_id': out_id}, context=context)
                    out_proc_obj.create_lines(cr, uid, out_proc_id, context=context)
                else:
                    out_proc_id = out_proc_ids[0]
                    # Reset the data of the imported lines on the existing wizard
                    lines_to_reset = []
                    for move_data in json_data['move_lines']:
                        if isinstance(move_data.get('line_number', False), int) and move_data['line_number'] not in lines_to_reset:
                            lines_to_reset.append(move_data['line_number'])
                    if lines_to_reset:
                        self.reset_out_proc_lines(cr, uid, [out_proc_id], lines_to_reset, context=context)

                # Import the data
                wiz_id = wiz_imp_obj.create(cr, uid, {'processor_id': out_proc_id, 'json_text': json_text}, context=context)
                imp_res = wiz_imp_obj.import_out_xlsx(cr, uid, [wiz_id], context=context)
                out_proc_obj.write(cr, uid, out_proc_id, {'draft': True, 'sde_updated': True}, context=context)

                final_msg = pagi_msg or _('Done')
                if imp_res:
                    final_msg = final_msg + _('. The lines number %s were ignored during the import') % (', '.join(imp_res),)
                result['message'] = final_msg

                # Set the OUT as sde_updated and remove the banner message
                pick_obj.write(cr, uid, out_id, {'sde_updated': True, 'sde_update_msg': False}, context=context)

                # Log the update
                self.pool.get('sde.update.log').create(cr, 1, {'date': datetime.now(), 'doc_type': 'out', 'doc_ref': out['name']}, context=context)
            elif pagi_msg:
                result['message'] = pagi_msg
        except Exception as e:
            cr.rollback()
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_out_msg')
    def sde_out_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of OUTs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'out', False, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_out_remove_msg')
    def sde_out_remove_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to remove a 'SDE is updating' message on a list of OUTs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'out', True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_out_check_availability')
    def sde_out_check_availability(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of Picking Tickets/OUTs
        '''
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance

        result = {'database': instance_name, 'error': False, 'message': ''}
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            # Get the OUTs with the references given
            out_names = []
            states = ['confirmed', 'assigned']
            if json_data.get('pick_list') and isinstance(json_data['pick_list'], list):
                try:
                    json_data['pick_list'] = [str(out_name).strip() for out_name in json_data['pick_list']]
                except:
                    raise osv.except_osv(_('Error'), _('One or more of the OUT names in the key "pick_list" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one'))
                out_names = json_data['pick_list']
                out_ids = self.get_stock_picking_from_refs(cr, uid, out_names, states, 'out', 'standard', context=context)
            else:
                out_domain = [('state', 'in', states), ('type', '=', 'out'), ('subtype', '=', 'standard')]
                out_ids = pick_obj.search(cr, uid, out_domain, context=context)

            if not out_ids:
                raise osv.except_osv(_('Error'), _('There is no OUT to check the availability on'))

            # Create sde.availability.check that will be updated every time the availability is checked on an OUT
            sde_avchk_name = self.pool.get('ir.sequence').get(cr, uid, 'sde.availability.check')
            sde_avchk_vals = {'name': sde_avchk_name, 'doc_type': 'out', 'nb_to_check': len(out_ids)}
            sde_avchk_id = self.pool.get('sde.availability.check').create(cr, 1, sde_avchk_vals, context=context)

            # Check the availability of each OUT one by one in the background
            threaded_exp_pagi = threading.Thread(target=self.sde_out_check_availability_update,
                                                 args=(cr, uid, sde_avchk_id, out_ids, context))
            threaded_exp_pagi.start()

            result.update({
                'message': _('Check Availability is in progress on %s OUTs%s')
                % (len(out_ids), out_names and ': ' + ', '.join(out_names) or ''),
                'sde_availability_check_id': sde_avchk_name,
                'nb_to_check': len(out_ids),
            })
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_out_export_lines')
    def sde_out_export_lines(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on OUTs with lines
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'standard', with_lines=True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_out_export')
    def sde_out_export(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on OUTs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'standard', with_lines=False, context=context)

    def get_out_export_data(self, cr, uid, ids, offset, limit, with_lines=False, context=None):
        """
        Get info from PICKs, its latest Track Change and info from their moves when needed
        """
        if context is None:
            context = {}

        sql_lines_col, sql_lines_join, sql_lines_group, sql_lines_order = '', '', '', ''
        if with_lines:  # Additional data for the lines
            sql_lines_col = """,
                    m.id, -- 19
                    m.line_number, -- 20
                    pp.default_code, -- 21
                    pt.name, -- 22
                    pis.name, -- 23
                    pno.name, -- 24
                    m.comment, -- 25
                    pas.name, -- 26
                    k.composition_reference, -- 27
                    l.name, -- 28
                    l2.name, -- 29
                    m.product_qty, -- 30
                    u.name, -- 31
                    lot.name, -- 33
                    m.expired_date, -- 33
                    pcc.cold_chain, -- 34 kc_check
                    pp.dangerous_goods, -- 35 dg_check
                    pp.controlled_substance, -- 36 np_check
                    m.state -- 37
                """
            sql_lines_join = """
                    LEFT JOIN product_product pp ON m.product_id = pp.id
                    LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN product_cold_chain pcc ON pp.cold_chain = pcc.id
                    LEFT JOIN product_international_status pis ON pp.international_status = pis.id
                    LEFT JOIN product_nomenclature pno ON pt.nomen_manda_0 = pno.id
                    LEFT JOIN product_asset pas ON m.asset_id = pas.id
                    LEFT JOIN composition_kit k ON m.composition_list_id = k.id
                    LEFT JOIN stock_location l ON m.location_id = l.id
                    LEFT JOIN stock_location l2 ON m.location_dest_id = l2.id
                    LEFT JOIN product_uom u ON m.product_uom = u.id
                    LEFT JOIN stock_production_lot lot ON m.prodlot_id = lot.id
                """
            sql_lines_group = """, m.id, m.line_number, pp.default_code, pt.name, pis.name, pno.name, m.comment, pas.name,
                    k.composition_reference, l.name, l2.name, m.product_qty, u.name, lot.name, m.expired_date, pcc.cold_chain,
                    pp.dangerous_goods, pp.controlled_substance, m.state"""
            sql_lines_order = ', m.line_number, m.id'
        cr.execute("""
                SELECT
                    p.name, -- 0
                    p.origin, -- 1
                    p.date, -- 2
                    par.name, -- 3
                    pb.name, -- 4
                    p.order_category, -- 5
                    rt.code, -- 6
                    rt.name, -- 7
                    p.details, -- 8
                    p.min_date, -- 9
                    p.requestor, -- 10
                    addr.street, -- 11
                    addr.street2, -- 12
                    co.name, -- 13
                    addr.phone, -- 14
                    p.sde_updated, -- 15
                    p.state, -- 16
                    MAX(a.log), -- 17
                    MAX(a.timestamp) -- 18
                    """ + sql_lines_col + """
                FROM stock_move m
                    LEFT JOIN stock_picking p ON m.picking_id = p.id
                    LEFT JOIN audittrail_log_line a ON p.id = a.res_id AND object_id = (SELECT id FROM ir_model WHERE model = 'stock.picking' LIMIT 1)
                    LEFT JOIN stock_picking pb ON p.backorder_id = pb.id
                    LEFT JOIN stock_reason_type rt ON p.reason_type_id = rt.id
                    LEFT JOIN res_partner par ON p.partner_id = par.id
                    LEFT JOIN res_partner_address addr ON p.address_id = addr.id
                    LEFT JOIN res_country co ON addr.country_id = co.id
                    """ + sql_lines_join + """
                WHERE p.id IN %s
                GROUP BY p.id, p.name, p.origin, p.date, par.name, pb.name, p.order_category, rt.code, rt.name, p.details, 
                    p.min_date, p.requestor, addr.street, addr.street2, co.name, addr.phone, p.sde_updated, p.state
                    """ + sql_lines_group + """
                ORDER BY p.id""" + sql_lines_order + """ OFFSET %s LIMIT %s
            """, (tuple(ids), offset, limit)) # not_a_user_entry

        return cr.fetchall()

    def create_out_paginated_export(self, cr, uid, ids, pagi_ref, page, last_page, offset, limit, with_lines=False, context=None):
        '''
        Method to be used in the background to create the paginated exports beyond page 1
        '''
        if context is None:
            context = {}

        new_cr = pooler.get_db(cr.dbname).cursor()

        data = {}
        for out in self.get_out_export_data(new_cr, uid, ids, offset, limit, with_lines=with_lines, context=context):
            if not data.get(out[0]):
                partner_data = [_('Supply Responsible')]
                address_data = []
                if out[11]:
                    address_data.append(out[11])
                if out[12]:
                    address_data.append(out[12])
                if out[13]:
                    address_data.append(out[13])
                if address_data:
                    partner_data.append(' '.join(address_data))
                if out[14]:
                    partner_data.append(out[14])

                data[out[0]] = {
                    'origin': out[1] or '',
                    'date': out[2],
                    'partner_name': out[3] or '',
                    'backorder_name': out[4] or '',
                    'order_category': out[5] and LIST_ORDER_CATEGORY[out[5]] or '',
                    'reason_type': out[6] and out[7] and '%s %s' % (out[6], out[7]) or '',
                    'details': out[8] or '',
                    'expected_ship_date': out[9] or '',
                    'requestor': out[10] or '',
                    'delivery_address': partner_data and '; '.join(partner_data) or '',
                    'updated_by_sde': out[15] or False,
                    'state': out[16] and PICKING_STATE[out[16]] or '',
                    'latest_log': out[17] or '',
                    'latest_log_date': out[18] or '',
                }

            if with_lines and len(out) > 18:
                if 'move_lines' not in data[out[0]]:
                    data[out[0]]['move_lines'] = []
                data[out[0]]['move_lines'].append({
                    'line_number': out[20],
                    'product_code': out[21],
                    'product_name': out[22],
                    'product_creator': out[23],
                    'nomen_main_type': out[24],
                    'comment': out[25] or '',
                    'asset': out[26] or '',
                    'kit': out[27] or '',
                    'source_location': out[28],
                    'destination_location': out[29],
                    'product_qty': out[30] or 0,
                    'qty_to_process': None,  # Left empty to force SDE to change the value
                    'uom': out[31] or '',
                    'prodlot_id': out[32] or '',
                    'expired_date': out[33] or '',
                    'kc_check': out[34] or False,
                    'dg_check': out[35] == 'True' and _('True') or out[35] == 'no_know' and _('Unknown') or _('False'),
                    'np_check': out[36] or False,
                    'state': out[37] and MOVE_STATE[out[37]] or '',
                })

        pagi_vals = {'pagination_json_id': pagi_ref, 'pagination_json_text': json.dumps(data), 'doc_type': 'out',
                     'page': page, 'last_page': page == last_page, 'with_lines': with_lines}
        self.pool.get('sde.export.pagination').create(new_cr, 1, pagi_vals, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True

    def sde_out_check_availability_update(self, cr, uid, sde_avchk_id, out_ids, context=None):
        '''
        Method to be used in the background to update the availability of a list of OUTs
        '''
        if context is None:
            context = {}

        sde_avchk_obj = self.pool.get('sde.availability.check')
        sde_avchk_vals = {}
        nb_checked = 0
        error_msg = ''
        for out_id in out_ids:
            nb_checked += 1
            new_cr = pooler.get_db(cr.dbname).cursor()
            try:
                self.pool.get('stock.picking').check_availability_manually(new_cr, uid, [out_id], context=context)
                sde_avchk_vals['checked_pick_ids'] = [(4, out_id)]
            except Exception as e:
                nb_checked -= 1
                # Rejection message
                if isinstance(e, osv.except_osv):
                    error_msg = e.value
                else:
                    error_msg = e.args and '. '.join(e.args) or e
                sde_avchk_vals.update({'state': 'error', 'error_msg': error_msg})
            finally:
                sde_avchk_vals['nb_checked'] = nb_checked
                sde_avchk_obj.write(new_cr, 1, sde_avchk_id, sde_avchk_vals, context=context)
                new_cr.commit()
                new_cr.close(True)
                if error_msg:
                    break

        return True

    def reset_out_proc_lines(self, cr, uid, ids, line_numbers, context=None):
        '''
        For each move of the Outgoing Delivery Processor whose line_number is in the import, reset as much data as possible:
            - Merge the quantities of split lines and delete the splits
            - Remove any asset, kit and BN/ED info
            - Sum the quantities and set the quantity to process at 0
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        proc_move_obj = self.pool.get('outgoing.delivery.move.processor')

        ln_sql = ""
        if line_numbers:
            if len(line_numbers) == 1:
                ln_sql = " AND line_number = %s" % (line_numbers[0],)
            else:
                ln_sql = " AND line_number IN %s" % (tuple(line_numbers),)
        cr.execute("""
           SELECT id, wizard_id, line_number, ordered_quantity
           FROM outgoing_delivery_move_processor WHERE wizard_id IN %s AND ordered_quantity != 0
        """ + ln_sql, (tuple(ids),)) # not_a_user_entry
        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2])
            if key not in data:
                data[key] = {'ordered_quantity': 0, 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['ordered_quantity'] += x[3]
        for key in data:
            proc_move_vals = {'ordered_quantity': data[key]['ordered_quantity'], 'quantity': 0, 'asset': False,
                              'composition_list_id': False, 'prodlot_id': False, 'expired_date': False}
            proc_move_obj.write(cr, uid, data[key]['master'], proc_move_vals, context=context)
        proc_move_obj.unlink(cr, uid, to_del, context=context)

        return True

    # =============================================================================================================== #
    #                                       PACK ONLY: PPL (Pre-Packing List)                                         #
    # =============================================================================================================== #
    def wizard_sde_pack_only_import(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to import on a PPL
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'pack_only_import', context=context)

    def wizard_sde_pack_only_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to set a banner message on PPLs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'banner_msg', context=context)

    def wizard_sde_pack_only_remove_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to remove a banner message on PPLs
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'remove_banner_msg', context=context)

    def wizard_sde_pack_only_export(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export PPL
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'pack_only_export', context=context)

    def wizard_sde_pack_only_export_lines(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export PPLs with lines
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'pack_only_export_lines', context=context)

    def wizard_sde_pack_types_export(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export Pack Types
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pack_only_actions(cr, uid, ids, 'pack_types_export', context=context)

    def wizard_sde_pack_only_actions(self, cr, uid, ids, action, context=None):
        '''
        Method to use instead of the JSONRPC
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No JSON data to use'))

        result = []
        if action == 'pack_only_import':
            result = self.sde_pack_only_import(cr, uid, sde_imp['json_text'], context=context)
        elif action == 'banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'ppl', False, context=context)
        elif action == 'remove_banner_msg':
            result = self.sde_stock_picking_msg(cr, uid, sde_imp['json_text'], 'ppl', True, context=context)
        elif action == 'pack_only_export':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'ppl', with_lines=False, context=context)
        elif action == 'pack_only_export_lines':
            result = self.sde_stock_picking_export(cr, uid, sde_imp['json_text'], 'out', 'ppl', with_lines=True, context=context)
        elif action == 'pack_types_export':
            result = self.sde_pack_types_export(cr, uid, sde_imp['json_text'], context=context)

        return self.write(cr, uid, ids, {'message': json.dumps(result)}, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_only_import')
    def sde_pack_only_import(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to import JSON data.
        A pagination system has been added to the import to allow users to import several JSONs for the same document
        before trying to process the data. The keys sde_pagination_id, sde_pagination_page and sde_pagination_end are
        necessary to allow the pagination.
        '''
        if context is None:
            context = {}

        pagi_obj = self.pool.get('sde.import.pagination')
        pick_obj = self.pool.get('stock.picking')
        wiz_imp_obj = self.pool.get('wizard.import.ppl.to.create.ship')

        context['sde_flow'] = True
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        result = {'database': instance_name, 'error': False, 'message': _('Done')}
        pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False
        pagi_json_text = ''
        pagi_json_data, ppl_ids = [], []
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)') % (json_data['database'], instance_name))

            sde_pagi_error = False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_end' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_end are mandatory to use the pagination in the SDE PPL import')
                else:
                    sde_pagi_end_msg = json_data.get('sde_pagination_end') and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, 1, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, 1, sde_pagi_id, context=context)
                        if sde_pagi['state'] == 'done':
                            sde_pagi_error = _('This SDE import ID is already finished, please use a new SDE import ID')
                        elif sde_pagi_page - sde_pagi['page'] != 1:
                            sde_pagi_error = _('The page number must be in sequential order without gaps: last page imported %s, imported page %s') \
                                % (sde_pagi['page'], json_data['sde_pagination_page'])
                        else:
                            # Update the existing JSON with the new data in the key move_lines
                            pagi_json_text = sde_pagi['pagination_json_text']
                            pagi_json_data = json.loads(pagi_json_text)

                            pagi_json_data['move_lines'].extend(json_data['move_lines'])
                            pagi_json_text = json.dumps(pagi_json_data)

                            pagi_vals = {
                                'pagination_json_text': pagi_json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, 1, sde_pagi_ids[0], pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s updated%s with page %s') % (json_data['sde_pagination_id'], sde_pagi_end_msg, sde_pagi_page)
                    else:
                        if sde_pagi_page != 1:
                            sde_pagi_error = _('The first page of a paginated SDE import must be 1')
                        else:
                            sde_pagi_vals = {
                                'state': json_data.get('sde_pagination_end') and 'done' or 'progress',
                                'pagination_json_id': json_data['sde_pagination_id'],
                                'pagination_json_text': json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, 1, sde_pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s created%s') % (json_data['sde_pagination_id'], sde_pagi_end_msg)

            if sde_pagi_error:
                raise osv.except_osv(_('Error'), _('An error occurred during the management of the paginated SDE import "%s": %s')
                                     % (json_data.get('sde_pagination_id'), sde_pagi_error))
            elif not json_data.get('sde_pagination_id') or (sde_pagi_end_msg and sde_pagi_id):
                # Get the correct JSON data if the pagination has been used
                if sde_pagi_id and pagi_json_text and pagi_json_data:
                    json_text = pagi_json_text
                    json_data = pagi_json_data

                # Get the PPL from the name
                if not json_data.get('name'):
                    raise osv.except_osv(_('Error'), _('The main key "name" is mandatory and should not be empty'))
                ppl_ids = self.get_stock_picking_from_refs(cr, uid, [json_data['name']], ['assigned'], 'out', 'ppl', context=context)
                ppl_id = ppl_ids[0]
                ppl = pick_obj.read(cr, uid, ppl_id, ['name', 'sde_updated'], context=context)
                if ppl['sde_updated']:
                    raise osv.except_osv(_('Error'), _('The PPL %s has already been updated by SDE. Please process the imported data in UniField or reset the SDE update there') % (ppl['name'],))

                # Reset the data of the imported lines
                if not json_data.get('move_lines'):
                    raise osv.except_osv(_('Error'), _('The main key "move_lines" is mandatory and should not be empty'))
                lines_to_reset = []
                for move_data in json_data['move_lines']:
                    if isinstance(move_data.get('line_number', False), int) and move_data['line_number'] not in lines_to_reset:
                        lines_to_reset.append(move_data['line_number'])
                if lines_to_reset:
                    self.reset_ppl_lines(cr, uid, [ppl_id], lines_to_reset, context=context)

                # Import the data, the PPL's state is set back to Assigned at the end of _import
                pick_obj.write(cr, uid, ppl_id, {'state': 'import'}, context)
                wiz_id = wiz_imp_obj.create(cr, uid, {'picking_id': ppl_id, 'file': False, 'json_text': json_text, 'state': 'in_progress'}, context=context)
                error_log, qty_errors, from_to_pack_errors = wiz_imp_obj._import(cr, uid, [wiz_id], context=context)
                if error_log or qty_errors or from_to_pack_errors:
                    raise osv.except_osv(_('Error'),  _('Some errors occurred during the import: %s')
                                         % ('; '.join([err for err in [error_log, qty_errors, from_to_pack_errors] if err]),))

                result['message'] = pagi_msg or _('Done')

                # Set the PPL as sde_updated, remove the banner message
                pick_obj.write(cr, uid, ppl_id, {'sde_updated': True, 'sde_update_msg': False}, context=context)

                # Log the update
                self.pool.get('sde.update.log').create(cr, 1, {'date': datetime.now(), 'doc_type': 'ppl', 'doc_ref': ppl['name']}, context=context)
            elif pagi_msg:
                result['message'] = pagi_msg
        except Exception as e:
            cr.rollback()
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_only_msg')
    def sde_pack_only_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of PPLs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'ppl', False, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_only_remove_msg')
    def sde_pack_only_remove_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to remove a 'SDE is updating' message on a list of PPLs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_msg(cr, uid, json_text, 'ppl', True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_only_export_lines')
    def sde_pack_only_export_lines(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on PPLs with lines
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'ppl', with_lines=True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_only_export')
    def sde_pack_only_export(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info on PPLs
        '''
        if context is None:
            context = {}

        return self.sde_stock_picking_export(cr, uid, json_text, 'out', 'ppl', with_lines=False, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pack_types_export')
    def sde_pack_types_export(self, cr, uid, json_text, context=None):
        """
        Method used by the SDE script to export info on Pack Types
        Group the data to prevent exporting exact duplicates
        """
        if context is None:
            context = {}

        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        result = {'database': instance_name, 'error': False, 'message': '', 'data': []}
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            # Get the documents with the references given
            ptype_names = []
            ptype_data = {}
            if json_data.get('pack_types') and isinstance(json_data['pack_types'], list):
                try:
                    json_data['pack_types'] = [str(pick_name).strip() for pick_name in json_data['pack_types']]
                except:
                    raise osv.except_osv(_('Error'),  _('One or more of the names in the key "pack_types" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one'))
                ptype_names = json_data['pack_types']
                cr.execute("""
                    SELECT pt.name, pt.width, pt.length, pt.height, MAX(a.log), MAX(a.timestamp)
                    FROM pack_type pt
                    LEFT JOIN audittrail_log_line a ON pt.id = a.res_id AND a.object_id = (SELECT id FROM ir_model WHERE model = 'pack.type' LIMIT 1)
                    WHERE pt.name ILIKE ANY(%s) GROUP BY pt.name, pt.width, pt.length, pt.height
                """, (ptype_names,))
            else:
                cr.execute("""
                    SELECT pt.name, pt.width, pt.length, pt.height, MAX(a.log), MAX(a.timestamp)
                    FROM pack_type pt
                    LEFT JOIN audittrail_log_line a ON pt.id = a.res_id AND a.object_id = (SELECT id FROM ir_model WHERE model = 'pack.type' LIMIT 1)
                    GROUP BY pt.name, pt.width, pt.length, pt.height
                """)
            for x in cr.fetchall():
                ptype_data.update({x[0]: {'width': x[1], 'length': x[2], 'height': x[3],'latest_log': x[4] or '',
                                          'latest_log_date': x[5] or ''}})

            if not ptype_data:
                with_names = ''
                if ptype_names:
                    with_names = _(' with the names %s') % (', '.join(ptype_names),)
                raise osv.except_osv(_('Error'), _('There is no Pack Type%s to export') % (with_names,))

            result.update({
                'data': ptype_data,
                'message': _('The data of %s Pack Types have been exported') % (len(ptype_data),)
            })
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    def get_pack_only_export_data(self, cr, uid, ids, offset, limit, with_lines=False, context=None):
        """
        Get info from PPLs, its latest Track Change, info from their moves when needed and the existing Pack Types
        """
        if context is None:
            context = {}

        sql_lines_col, sql_lines_join, sql_lines_group, sql_lines_order = '', '', '', ''
        if with_lines:  # Additional data for the lines
            sql_lines_col = """,
                m.id, -- 17
                m.line_number, -- 18
                pp.default_code, -- 9
                pt.name, -- 20
                pis.name, -- 21
                pno.name, -- 22
                m.comment, -- 23
                m.product_qty, -- 24
                lot.name, -- 25
                m.expired_date, -- 26
                pcc.cold_chain, -- 27 kc_check
                pp.dangerous_goods, -- 28 dg_check
                pp.controlled_substance, -- 29 np_check
                m.from_pack, -- 30
                m.to_pack, -- 31
                m.weight, -- 32
                ptype.name, -- 33
                m.width, -- 34
                m.length, -- 35
                m.height -- 36
            """
            sql_lines_join = """
                LEFT JOIN product_product pp ON m.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_cold_chain pcc ON pp.cold_chain = pcc.id
                LEFT JOIN product_international_status pis ON pp.international_status = pis.id
                LEFT JOIN product_nomenclature pno ON pt.nomen_manda_0 = pno.id
                LEFT JOIN stock_production_lot lot ON m.prodlot_id = lot.id
                LEFT JOIN pack_type ptype ON m.pack_type = ptype.id
            """
            sql_lines_group = """, m.id,  m.line_number, pp.default_code, pt.name, pis.name, pno.name, m.comment,
                m.product_qty, lot.name, m.expired_date, pcc.cold_chain, pp.dangerous_goods, pp.controlled_substance,
                m.from_pack, m.to_pack, m.weight, m.width, m.length, m.height, ptype.name"""
            sql_lines_order = ', m.line_number, m.id'
        cr.execute("""
            SELECT
                p.name, -- 0
                p.date, -- 1
                s.client_order_ref, -- 2
                p.origin, -- 3
                s.date_order, -- 4
                s.delivery_requested_date, -- 5
                s.ready_to_ship_date, -- 6
                s.transport_type, -- 7
                par.name, -- 8
                addr.street, -- 9
                addr.street2, -- 10
                co.name, -- 11
                addr.phone, -- 12
                dl.name, -- 13
                p.sde_updated, -- 14
                MAX(a.log), -- 15
                MAX(a.timestamp) -- 16
                """ + sql_lines_col + """
            FROM stock_move m
                LEFT JOIN stock_picking p ON m.picking_id = p.id
                LEFT JOIN audittrail_log_line a ON p.id = a.res_id AND object_id = (SELECT id FROM ir_model WHERE model = 'stock.picking' LIMIT 1)
                LEFT JOIN sale_order s ON p.sale_id = s.id
                LEFT JOIN res_partner par ON p.partner_id = par.id
                LEFT JOIN res_partner_address addr ON p.address_id = addr.id
                LEFT JOIN res_country co ON addr.country_id = co.id
                LEFT JOIN stock_location dl ON p.ext_cu = dl.id
                """ + sql_lines_join + """
            WHERE p.id IN %s AND m.state = 'assigned'
            GROUP BY p.id, p.name, p.date, s.client_order_ref, s.name, s.date_order, s.delivery_requested_date,
                s.ready_to_ship_date, s.transport_type, par.name, addr.street, addr.street2, co.name, addr.phone,
                dl.name, p.sde_updated""" + sql_lines_group + """
            ORDER BY p.id""" + sql_lines_order + """ OFFSET %s LIMIT %s
        """, (tuple(ids), offset, limit)) # not_a_user_entry

        return cr.fetchall()

    def create_pack_only_paginated_export(self, cr, uid, ids, pagi_ref, page, last_page, offset, limit, with_lines=False, context=None):
        '''
        Method to be used in the background to create the paginated exports beyond page 1
        '''
        if context is None:
            context = {}

        new_cr = pooler.get_db(cr.dbname).cursor()

        data, pack_types_data = {}, {}
        shipper_data = self.get_shipper_data(new_cr, uid, context=context)
        for ppl in self.get_pack_only_export_data(new_cr, uid, ids, offset, limit, with_lines=with_lines, context=context):
            if not data.get(ppl[0]):
                partner_data = [ppl[8], _('Supply Responsible')]
                address_data = []
                if ppl[9]:
                    address_data.append(ppl[9])
                if ppl[10]:
                    address_data.append(ppl[10])
                if ppl[11]:
                    address_data.append(ppl[11])
                if address_data:
                    partner_data.append(' '.join(address_data))
                if ppl[12]:
                    partner_data.append(ppl[12])

                data[ppl[0]] = {
                    'date': ppl[1],
                    'client_po_ref': ppl[2] or '',
                    'origin': ppl[3] or '',
                    'fo_date': ppl[4] or '',
                    'packing_date': ppl[5] or '',
                    'ready_to_ship_date': ppl[6] or '',
                    'transport_type': ppl[7] and LIST_TRANSPORT_TYPE[ppl[7]] or '',
                    'shipper_address': shipper_data and '; '.join(shipper_data) or '',
                    'consignee_address': partner_data and '; '.join(partner_data) or '',
                    'destination_location': ppl[13] or '',
                    'updated_by_sde': ppl[14] or False,
                    'latest_log': ppl[15] or '',
                    'latest_log_date': ppl[16] or '',
                }

            if with_lines and len(ppl) > 17:
                if 'move_lines' not in data[ppl[0]]:
                    data[ppl[0]]['move_lines'] = []
                data[ppl[0]]['move_lines'].append({
                    'line_number': ppl[18],
                    'product_code': ppl[19],
                    'product_name': ppl[20],
                    'product_creator': ppl[21],
                    'nomen_main_type': ppl[22],
                    'comment': ppl[23] or '',
                    'product_qty': ppl[24] or 0,
                    'prodlot_id': ppl[25] or '',
                    'expired_date': ppl[26] or '',
                    'kc_check': ppl[27] or False,
                    'dg_check': ppl[28] == 'True' and _('True') or ppl[28] == 'no_know' and _('Unknown') or _('False'),
                    'np_check': ppl[29] or False,
                    'from_pack': ppl[30] or 0,
                    'to_pack': ppl[31] or 0,
                    'weight': ppl[32] or 0.00,
                    'pack_type': ppl[33] or '',
                    'width': ppl[34] or 0.00,
                    'length': ppl[35] or 0.00,
                    'height': ppl[36] or 0.00,
                })

        pagi_vals = {'pagination_json_id': pagi_ref, 'pagination_json_text': json.dumps(data), 'doc_type': 'ppl',
                     'page': page, 'last_page': page == last_page, 'with_lines': with_lines}
        self.pool.get('sde.export.pagination').create(new_cr, 1, pagi_vals, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True

    def reset_ppl_lines(self, cr, uid, ids, line_numbers, context=None):
        '''
        For each move of the Available PPL whose line_number is in the import, reset as much data as possible:
            - Merge the quantities of split lines by BN and delete the splits
            - Reset from/to pack to 1/1
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        move_obj = self.pool.get('stock.move')

        ln_sql = ""
        if line_numbers:
            if len(line_numbers) == 1:
                ln_sql = " AND line_number = %s" % (line_numbers[0],)
            else:
                ln_sql = " AND line_number IN %s" % (tuple(line_numbers),)
        cr.execute("""
           SELECT id, picking_id, line_number, product_qty, prodlot_id FROM stock_move
           WHERE state = 'assigned' AND picking_id IN %s AND product_qty != 0
        """ + ln_sql, (tuple(ids),)) # not_a_user_entry

        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2], x[4])
            if key not in data:
                data[key] = {'product_qty': 0, 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['product_qty'] += x[3]
        for key in data:
            move_vals = {'product_qty': data[key]['product_qty'], 'product_uos_qty': data[key]['product_qty'],
                         'from_pack': 1, 'to_pack': 1, 'weight': False, 'pack_type': False, 'width': False,
                         'length': False, 'height': False}
            move_obj.write(cr, uid, data[key]['master'], move_vals, context=context)
        move_obj.unlink(cr, uid, to_del, force=True, context=context)

        return True

    # =============================================================================================================== #
    #                                                ALL stock.picking                                                #
    # =============================================================================================================== #
    def sde_stock_picking_msg(self, cr, uid, json_text, doc_type, to_remove, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of Picking Tickets/OUTs/PPLs
        '''
        if context is None:
            context = {}
        if not doc_type:
            raise osv.except_osv(_('Error'), _('Please specify a doc_type if you want to search for a stock_picking'))

        pick_obj = self.pool.get('stock.picking')
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance

        doc = _('Picking Ticket')
        pick_type = 'out'
        pick_subtype = 'picking'
        if doc_type == 'out':
            doc = _('OUT')
            pick_subtype = 'standard'
        elif doc_type == 'ppl':
            doc = _('PPL')
            pick_subtype = 'ppl'

        result = {'database': instance_name, 'error': False, 'message': ''}
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            # Get the documents with the references given
            if not json_data.get('pick_list') or not isinstance(json_data['pick_list'], list):
                raise osv.except_osv(_('Error'), _('The main key "pick_list" is mandatory and should be a non-empty list of %s names') % (doc,))
            try:
                json_data['pick_list'] = [str(pick_name).strip() for pick_name in json_data['pick_list']]
            except:
                raise osv.except_osv(_('Error'), _('One or more of the %s names in the key "pick_list" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one') % (doc,))
            pick_ids = self.get_stock_picking_from_refs(cr, uid, json_data['pick_list'], ['assigned'], pick_type, pick_subtype, context=context)

            if to_remove:
                pick_obj.write(cr, uid, pick_ids, {'sde_update_msg': False}, context=context)
            else:
                update_msg = _('This %s is currently being updated via SDE since %s, please avoid making any direct change in UniField') \
                    % (doc, datetime.now().strftime('%d/%m/%Y %H:%M'),)
                pick_obj.write(cr, uid, pick_ids, {'sde_update_msg': update_msg}, context=context)

            result['message'] = _('The "updated via SDE" banner message has been %s on the %s %s') \
                % (to_remove and _('removed') or _('put'), doc, ', '.join(json_data['pick_list']),)
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    def sde_stock_picking_export(self, cr, uid, json_text, pick_type, pick_subtype, with_lines=False, context=None):
        '''
        Method used by the SDE script to export info on Picking Tickets/OUTs. Doesn't export lines' data unless specified
        '''
        if context is None:
            context = {}
        if not pick_type or not pick_subtype:
            raise osv.except_osv(_('Error'), _('Please specify a pick_type and pick_subtype'))

        pick_obj = self.pool.get('stock.picking')
        sde_avchk_obj = self.pool.get('sde.availability.check')
        pagi_exp_obj = self.pool.get('sde.export.pagination')

        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        if pick_type == 'out' and pick_subtype == 'standard':
            doc = _('OUTs')
            export_type = 'out'
        elif pick_type == 'out' and pick_subtype == 'ppl':
            doc = _('PPLs')
            export_type = 'ppl'
        else:
            doc = _('Picking Tickets')
            export_type = 'pick'

        result = {'database': instance_name, 'error': False, 'message': '', 'data': []}
        pagi_msg, avchk_msg = '', ''
        avchk_data = False
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            if json_data.get('sde_availability_check_id'):
                # Check and get the availability check data
                avchk_domain = [('doc_type', '=', export_type), ('name', '=', json_data['sde_availability_check_id'])]
                avchk_ids = sde_avchk_obj.search(cr, 1, avchk_domain, context=context)
                if avchk_ids:
                    avchk_data = sde_avchk_obj.browse(cr, 1, avchk_ids[0], context=context)
                    result.update({
                        'sde_availability_check_id': json_data['sde_availability_check_id'],
                        'nb_checked': avchk_data.nb_checked,
                        'nb_to_check': avchk_data.nb_to_check,
                        'checked_availability': [p.name for p in avchk_data.checked_pick_ids]
                    })
                else:
                    raise osv.except_osv(_('Error'), _('There is no availability being checked for %s with the "sde_availability_check_id" %s')
                                         % (doc, json_data['sde_availability_check_id'],))

            if not avchk_data or (avchk_data and avchk_data.state == 'done'):
                if json_data.get('sde_pagination_id'):
                    # Check the pagination data
                    if not json_data.get('sde_pagination_page'):
                        raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" is mandatory and should not be empty when using "sde_pagination_id"'))
                    try:
                        json_data['sde_pagination_page'] = int(json_data['sde_pagination_page'])
                    except:
                        raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" must be an integer'))
                    if json_data['sde_pagination_page'] <= 0:
                        raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" must be above 0'))

                    pagi_exp_domain = [('doc_type', '=', export_type), ('pagination_json_id', '=', json_data['sde_pagination_id']),
                                       ('page', '=', json_data['sde_pagination_page'])]
                    pagi_exp_ids = pagi_exp_obj.search(cr, 1, pagi_exp_domain, context=context)
                    if pagi_exp_ids:
                        pagi_exp = pagi_exp_obj.read(cr, 1, pagi_exp_ids[0], ['pagination_json_text', 'with_lines'], context=context)
                        result.update({
                            'sde_pagination_id': json_data['sde_pagination_id'],
                            'sde_pagination_page': json_data['sde_pagination_page'],
                            'message': _('The header%s data from the page %s of %s have been exported')
                            % (pagi_exp['with_lines'] and _(' and lines') or '', json_data['sde_pagination_page'], json_data['sde_pagination_id']),
                            'data': json.loads(pagi_exp['pagination_json_text']),
                        })
                    else:
                        raise osv.except_osv(_('Error'), _('No %s export data was found with the "sde_pagination_id" %s and the "sde_pagination_page" %s')
                                             % (doc, json_data['sde_pagination_id'], json_data['sde_pagination_page']))
                else:
                    # Get the documents with the references given
                    pick_ids, pick_names = [], []
                    states = ['assigned']
                    if export_type ==  'pick':
                        states.append('confirmed')
                    if json_data.get('pick_list') and isinstance(json_data['pick_list'], list):
                        try:
                            json_data['pick_list'] = [str(pick_name).strip() for pick_name in json_data['pick_list']]
                        except:
                            raise osv.except_osv(_('Error'),  _('One or more of the %s names in the key "pick_list" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one')
                                                 % (doc,))
                        pick_names = json_data['pick_list']
                        pick_ids = self.get_stock_picking_from_refs(cr, uid, pick_names, states, pick_type, pick_subtype, context=context)
                    else:
                        pick_domain = [('state', 'in', states), ('type', '=', pick_type), ('subtype', '=', pick_subtype)]
                        if pick_type == 'out' and pick_subtype == 'picking':
                            pick_domain.append(('backorder_id', '!=', False))
                        pick_ids = pick_obj.search(cr, uid, pick_domain, context=context)

                    if not pick_ids:
                        raise osv.except_osv(_('Error'), _('There is no %s %s to export')
                                             % ('/'.join([PICKING_STATE[state] for state in states]), doc))

                    # Default number of lines per page is 100 if not specified
                    lines_per_page = 100
                    if json_data.get('lines_per_page'):
                        try:
                            json_data['lines_per_page'] = int(json_data['lines_per_page'])
                        except:
                            raise osv.except_osv(_('Error'), _('The main key "lines_per_page" must be an integer'))
                        if json_data['lines_per_page'] <= 0:
                            raise osv.except_osv(_('Error'), _('The main key "lines_per_page" must be above 0'))
                        lines_per_page = json_data['lines_per_page']

                    # Count the number of lines
                    if with_lines:
                        cr.execute("""SELECT COUNT(id) FROM stock_move WHERE picking_id IN %s AND state != 'cancel'""", (tuple(pick_ids),))
                        nb_lines = cr.fetchone()[0]
                    else:
                        nb_lines = len(pick_ids)

                    data = {}
                    offset = 0
                    if pick_type == 'out' and pick_subtype == 'standard':
                        threaded_method = self.create_out_paginated_export
                        for out in self.get_out_export_data(cr, uid, pick_ids, offset, lines_per_page, with_lines=with_lines, context=context):
                            if not data.get(out[0]):
                                partner_data = [_('Supply Responsible')]
                                address_data = []
                                if out[11]:
                                    address_data.append(out[11])
                                if out[12]:
                                    address_data.append(out[12])
                                if out[13]:
                                    address_data.append(out[13])
                                if address_data:
                                    partner_data.append(' '.join(address_data))
                                if out[14]:
                                    partner_data.append(out[14])

                                data[out[0]] = {
                                    'origin': out[1] or '',
                                    'date': out[2],
                                    'partner_name': out[3] or '',
                                    'backorder_name': out[4] or '',
                                    'order_category': out[5] and LIST_ORDER_CATEGORY[out[5]] or '',
                                    'reason_type': out[6] and out[7] and '%s %s' % (out[6], out[7]) or '',
                                    'details': out[8] or '',
                                    'expected_ship_date': out[9] or '',
                                    'requestor': out[10] or '',
                                    'delivery_address': partner_data and '; '.join(partner_data) or '',
                                    'updated_by_sde': out[15] or False,
                                    'state': out[16] and PICKING_STATE[out[16]] or '',
                                    'latest_log': out[17] or '',
                                    'latest_log_date': out[18] or '',
                                }

                            if with_lines and len(out) > 18:
                                if 'move_lines' not in data[out[0]]:
                                    data[out[0]]['move_lines'] = []
                                data[out[0]]['move_lines'].append({
                                    'line_number': out[20],
                                    'product_code': out[21],
                                    'product_name': out[22],
                                    'product_creator': out[23],
                                    'nomen_main_type': out[24],
                                    'comment': out[25] or '',
                                    'asset': out[26] or '',
                                    'kit': out[27] or '',
                                    'source_location': out[28],
                                    'destination_location': out[29],
                                    'product_qty': out[30] or 0,
                                    'qty_to_process': None,  # Left empty to force SDE to change the value
                                    'uom': out[31] or '',
                                    'prodlot_id': out[32] or '',
                                    'expired_date': out[33] or '',
                                    'kc_check': out[34] or False,
                                    'dg_check': out[35] == 'True' and _('True') or out[35] == 'no_know' and _('Unknown') or _('False'),
                                    'np_check': out[36] or False,
                                    'state': out[37] and MOVE_STATE[out[37]] or '',
                                })
                    elif pick_type == 'out' and pick_subtype == 'ppl':
                        threaded_method = self.create_pack_only_paginated_export
                        shipper_data = self.get_shipper_data(cr, uid, context=context)
                        for ppl in self.get_pack_only_export_data(cr, uid, pick_ids, offset, lines_per_page, with_lines=with_lines, context=context):
                            if not data.get(ppl[0]):
                                partner_data = [ppl[8], _('Supply Responsible')]
                                address_data = []
                                if ppl[9]:
                                    address_data.append(ppl[9])
                                if ppl[10]:
                                    address_data.append(ppl[10])
                                if ppl[11]:
                                    address_data.append(ppl[11])
                                if address_data:
                                    partner_data.append(' '.join(address_data))
                                if ppl[12]:
                                    partner_data.append(ppl[12])

                                data[ppl[0]] = {
                                    'date': ppl[1],
                                    'client_po_ref': ppl[2] or '',
                                    'origin': ppl[3] or '',
                                    'fo_date': ppl[4] or '',
                                    'packing_date': ppl[5] or '',
                                    'ready_to_ship_date': ppl[6] or '',
                                    'transport_type': ppl[7] and LIST_TRANSPORT_TYPE[ppl[7]] or '',
                                    'shipper_address': shipper_data and '; '.join(shipper_data) or '',
                                    'consignee_address': partner_data and '; '.join(partner_data) or '',
                                    'destination_location': ppl[13] or '',
                                    'updated_by_sde': ppl[14] or False,
                                    'latest_log': ppl[15] or '',
                                    'latest_log_date': ppl[16] or '',
                                }

                            if with_lines and len(ppl) > 17:
                                if 'move_lines' not in data[ppl[0]]:
                                    data[ppl[0]]['move_lines'] = []
                                data[ppl[0]]['move_lines'].append({
                                    'line_number': ppl[18],
                                    'product_code': ppl[19],
                                    'product_name': ppl[20],
                                    'product_creator': ppl[21],
                                    'nomen_main_type': ppl[22],
                                    'comment': ppl[23] or '',
                                    'product_qty': ppl[24] or 0,
                                    'prodlot_id': ppl[25] or '',
                                    'expired_date': ppl[26] or '',
                                    'kc_check': ppl[27] or False,
                                    'dg_check': ppl[28] == 'True' and _('True') or ppl[28] == 'no_know' and _('Unknown') or _('False'),
                                    'np_check': ppl[29] or False,
                                    'from_pack': ppl[30] or 0,
                                    'to_pack': ppl[31] or 0,
                                    'weight': ppl[32] or 0.00,
                                    'pack_type': ppl[33] or '',
                                    'width': ppl[34] or 0.00,
                                    'length': ppl[35] or 0.00,
                                    'height': ppl[36] or 0.00,
                                })
                    else:
                        threaded_method = self.create_picking_ticket_paginated_export
                        for pick in self.get_picking_ticket_export_data(cr, uid, pick_ids, offset, lines_per_page, with_lines=with_lines, context=context):
                            if not data.get(pick[0]):
                                partner_data = [pick[11], _('Supply Responsible')]
                                address_data = []
                                if pick[12]:
                                    address_data.append(pick[12])
                                if pick[13]:
                                    address_data.append(pick[13])
                                if pick[14]:
                                    address_data.append(pick[14])
                                if address_data:
                                    partner_data.append(' '.join(address_data))
                                if pick[15]:
                                    partner_data.append(pick[15])

                                data[pick[0]] = {
                                    'date': pick[1],
                                    'origin': pick[2] or '',
                                    'client_po_ref': pick[3] or '',
                                    'incoming_ref': pick[4] or '',
                                    'order_category': pick[5] and LIST_ORDER_CATEGORY[pick[5]] or '',
                                    'delivery_requested_date': pick[6] or '',
                                    'fo_details': pick[7] or '',
                                    'transport_type': pick[8] and LIST_TRANSPORT_TYPE[pick[8]] or '',
                                    'priority': pick[9] and LIST_ORDER_PRIORITY[pick[9]] or '',
                                    'ready_to_ship_date': pick[10] or '',
                                    'delivery_address': partner_data and '; '.join(partner_data) or '',
                                    'total_items': pick[16] or 0,
                                    'updated_by_sde': pick[17] or False,
                                    'state': pick[18] and PICKING_STATE[pick[18]] or '',
                                    'line_state': pick[19] and PICKING_LINE_STATE[pick[19]] or '',
                                    'latest_log': pick[20] or '',
                                    'latest_log_date': pick[21] or '',
                                }

                            if with_lines and len(pick) > 22:
                                if 'move_lines' not in data[pick[0]]:
                                    data[pick[0]]['move_lines'] = []
                                data[pick[0]]['move_lines'].append({
                                    'line_number': pick[23],
                                    'product_code': pick[24],
                                    'product_name': pick[25],
                                    'product_creator': pick[26],
                                    'nomen_main_type': pick[27],
                                    'changed_product_code': pick[28] or '',
                                    'comment': pick[29] or '',
                                    'source_location': pick[30],
                                    'qty_in_stock': self.get_qty_available(cr, uid, pick[38], pick[39], pick[40], context=context) or 0,
                                    'product_qty': pick[31] or 0,
                                    'qty_to_process': None,  # Left empty to force SDE to change the value
                                    'prodlot_id': pick[32] or '',
                                    'expired_date': pick[33] or '',
                                    'kc_check': pick[34] or False,
                                    'dg_check': pick[35] == 'True' and _('True') or pick[35] == 'no_know' and _('Unknown') or _('False'),
                                    'np_check': pick[36] or False,
                                    'state': pick[37] and MOVE_STATE[pick[37]] or '',
                                })

                    if nb_lines > lines_per_page:
                        sde_pagi_id = self.pool.get('ir.sequence').get(cr, uid, 'sde.export.pagination')
                        sde_pagi_page = 1
                        last_page = math.ceil(nb_lines / lines_per_page)

                        pagi_exp_obj.create(cr, 1, {'pagination_json_id': sde_pagi_id, 'pagination_json_text': json.dumps(data),
                                                    'doc_type': export_type, 'page': sde_pagi_page, 'last_page': False,
                                                    'with_lines': with_lines}, context=context)
                        result.update({'sde_pagination_id': sde_pagi_id, 'sde_pagination_page': sde_pagi_page,
                                       'sde_pagination_last_page': last_page})

                        pagi_msg = _('. The export have been paginated into %s pages. If you want to retrieve the other pages, please use the "sde_pagination_id" data given') % (last_page,)

                        # Create the remaining pages in the background
                        while sde_pagi_page < last_page:
                            sde_pagi_page += 1
                            offset += lines_per_page
                            threaded_exp_pagi = threading.Thread(target=threaded_method,
                                                                 args=(cr, uid, pick_ids, sde_pagi_id, sde_pagi_page,
                                                                       last_page, offset, lines_per_page, with_lines, context))
                            threaded_exp_pagi.start()

                    final_msg_pick = pick_names and ', '.join(pick_names) or _('%s %s') % (len(pick_ids), doc)
                    if avchk_data:
                        avchk_msg = _('The Availability Check has been successfully completed (%s/%s). ') \
                            % (avchk_data.nb_checked, avchk_data.nb_to_check)
                    result.update({
                        'data': data,
                        'message': _('%sThe header%s data of %s have been exported%s')
                        % (avchk_msg, with_lines and _(' and lines') or '', final_msg_pick, pagi_msg)
                    })
            else:
                if avchk_data.state == 'error':
                    avchk_msg = (_('An error occurred during the Availability Check of %s (%s/%s): %s')
                                 % (doc, avchk_data.nb_checked, avchk_data.nb_to_check, avchk_data.error_msg))
                else:
                    avchk_msg = _('The Availability Check is still in progress (%s/%s)') % (avchk_data.nb_checked, avchk_data.nb_to_check)
                result.update({'data': [], 'message': avchk_msg})

        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    def get_stock_picking_from_refs(self, cr, uid, pick_list, states, pick_type, pick_subtype, context=None):
        if context is None:
            context = {}
        if not pick_type or not pick_subtype:
            raise osv.except_osv(_('Error'), _('Please specify a pick_type and pick_subtype'))

        pick_obj = self.pool.get('stock.picking')

        pick_ids, not_found = [], []
        for pick_name in pick_list:
            pick_domain = [('state', 'in', states), ('type', '=', pick_type), ('subtype', '=', pick_subtype), ('name', '=', pick_name)]
            if pick_type == 'pick':
                pick_domain.append(('backorder_id', '!=', False))
            pick_id = pick_obj.search(cr, uid, pick_domain, context=context)
            if pick_id:
                pick_ids.append(pick_id[0])
            else:
                not_found.append(pick_name)

        if not_found:
            if pick_type == 'out' and pick_subtype == 'standard':
                doc = _('OUTs')
            elif pick_type == 'out' and pick_subtype == 'ppl':
                doc = _('PPLs')
            else:
                doc = _('Picking Tickets')
            raise osv.except_osv(_('Error'), _('The %s %s %s could not be found')
                                 % ('/'.join([PICKING_STATE[state] for state in states]), doc, ', '.join(not_found),))

        return pick_ids

    def get_qty_available(self, cr, uid, product_id, location_id, prodlot_id, context=None):
        """
        Get the available quantity for a move, with the product id and the info put in the context
        """
        if context is None:
            context = {}

        if location_id:
            context.update({'location': location_id, 'location_id': location_id, 'prodlot_id': prodlot_id})

        prod = self.pool.get('product.product').read(cr, uid, product_id, ['qty_available'], context=context)
        qty_available = prod and prod['qty_available'] or 0.00

        return qty_available

    def get_shipper_data(self, cr, uid, context=None):
        """
        Get data from the instance's partner
        """
        if context is None:
            context = {}

        instance_partner = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id
        instance_addr_id = self.pool.get('res.partner').address_get(cr, uid, instance_partner.id)['default']
        instance_addr = self.pool.get('res.partner.address').browse(cr, uid, instance_addr_id, context=context)
        shipper_data = [instance_partner.name, _('Supply Responsible')]
        shipper_address = []
        if instance_addr:
            if instance_addr.street:
                shipper_address.append(instance_addr.street)
            if instance_addr.street2:
                shipper_address.append(instance_addr.street2)
            if instance_addr.zip:
                shipper_address.append(instance_addr.zip)
            if instance_addr.city:
                shipper_address.append(instance_addr.city)
            if instance_addr.country_id:
                shipper_address.append(instance_addr.country_id.name)
        if shipper_address:
            shipper_data.append(' '.join(shipper_address))
        if instance_addr.phone:
            shipper_data.append(instance_addr.phone)
        if instance_addr.email:
            shipper_data.append(instance_addr.email)

        return shipper_data

    # =============================================================================================================== #
    #                                               Physical Inventory                                                #
    # =============================================================================================================== #
    def wizard_sde_pi_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to set a banner message on Physical Inventories
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pi_actions(cr, uid, ids, 'banner_msg', context=context)

    def wizard_sde_pi_remove_msg(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to remove a banner message on Physical Inventories
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pi_actions(cr, uid, ids, 'remove_banner_msg', context=context)
    
    def wizard_sde_pi_counting_sheet_import(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to import on a Physical Inventory's Counting Sheet
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pi_actions(cr, uid, ids, 'pi_counting_sheet_import', context=context)

    def wizard_sde_pi_counting_sheet_export(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the JSONRPC to export Physical Inventories' Counting Sheet
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_pi_actions(cr, uid, ids, 'pi_counting_sheet_export', context=context)

    def wizard_sde_pi_actions(self, cr, uid, ids, action, context=None):
        '''
        Method to use instead of the JSONRPC
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No JSON data to use'))

        result = []
        if action == 'banner_msg':
            result = self.sde_physical_inventory_msg(cr, uid, sde_imp['json_text'], False, context=context)
        elif action == 'remove_banner_msg':
            result = self.sde_physical_inventory_msg(cr, uid, sde_imp['json_text'], True, context=context)
        elif action == 'pi_counting_sheet_import':
            result = self.sde_pi_counting_sheet_import(cr, uid, sde_imp['json_text'], context=context)
        elif action == 'pi_counting_sheet_export':
            result = self.sde_pi_export(cr, uid, sde_imp['json_text'], 'count', context=context)
        # elif action == 'pi_discr_lines_import':
        #     result = self.sde_pi_discr_lines_import(cr, uid, sde_imp['json_text'], context=context)
        # elif action == 'pi_cdiscr_lines_export':
        #     result = self.sde_pi_export(cr, uid, sde_imp['json_text'], 'discr', context=context)

        return self.write(cr, uid, ids, {'message': json.dumps(result)}, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pi_msg')
    def sde_pi_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of Physical Inventories
        '''
        if context is None:
            context = {}

        return self.sde_physical_inventory_msg(cr, uid, json_text, False, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pi_remove_msg')
    def sde_pi_remove_msg(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to remove a 'SDE is updating' message on a list of Physical Inventories
        '''
        if context is None:
            context = {}

        return self.sde_physical_inventory_msg(cr, uid, json_text, True, context=context)

    @jsonrpc_orm_exposed('sde.import', 'sde_pi_counting_sheet_export')
    def sde_pi_counting_sheet_export(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to export info of Physical Inventories' Counting sheet
        '''
        if context is None:
            context = {}

        return self.sde_pi_export(cr, uid, json_text, 'count', context=context)

    def sde_physical_inventory_msg(self, cr, uid, json_text, to_remove, context=None):
        '''
        Method used by the SDE script to set a 'SDE is updating' message on a list of Physical Inventories
        '''
        if context is None:
            context = {}

        pi_obj = self.pool.get('physical.inventory')
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance

        result = {'database': instance_name, 'error': False, 'message': ''}
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            # Get the documents with the references given
            if not json_data.get('pi_list') or not isinstance(json_data['pi_list'], list):
                raise osv.except_osv(_('Error'), _('The main key "pi_list" is mandatory and should be a non-empty list of Physical Inventory names'))
            try:
                json_data['pi_list'] = [str(pi_name).strip() for pi_name in json_data['pi_list']]
            except:
                raise osv.except_osv(_('Error'), _('One or more of the Physical Inventory names in the key "pi_list" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one'))
            pi_ids = self.get_pi_from_refs(cr, uid, json_data['pi_list'], False, context=context)

            if to_remove:
                pi_obj.write(cr, uid, pi_ids, {'sde_update_msg': False}, context=context)
            else:
                update_msg = _('This Physical Inventory is currently being updated via SDE since %s, please avoid making any direct change in UniField') \
                    % (datetime.now().strftime('%d/%m/%Y %H:%M'),)
                pi_obj.write(cr, uid, pi_ids, {'sde_update_msg': update_msg}, context=context)

            result['message'] = _('The "updated via SDE" banner message has been %s on the Physical Inventories %s') \
                % (to_remove and _('removed') or _('put'), ', '.join(json_data['pi_list']),)
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    @jsonrpc_orm_exposed('sde.import', 'sde_pi_counting_sheet_import')
    def sde_pi_counting_sheet_import(self, cr, uid, json_text, context=None):
        '''
        Method used by the SDE script to import JSON data.
        A pagination system has been added to the import to allow users to import several JSONs for the same document
        before trying to process the data. The keys sde_pagination_id, sde_pagination_page and sde_pagination_end are
        necessary to allow the pagination.
        '''
        if context is None:
            context = {}

        pagi_obj = self.pool.get('sde.import.pagination')
        pi_obj = self.pool.get('physical.inventory')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        counting_obj = self.pool.get('physical.inventory.counting')

        context['sde_flow'] = True
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        result = {'database': instance_name, 'error': False, 'message': _('Done')}
        pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False
        pagi_json_text = ''
        pagi_json_data, pi_ids = [], []
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)') % (json_data['database'], instance_name))

            sde_pagi_error = False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_end' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_end are mandatory to use the pagination in the SDE Physical Inventory Counting sheet import')
                else:
                    sde_pagi_end_msg = json_data.get('sde_pagination_end') and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, 1, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, 1, sde_pagi_id, context=context)
                        if sde_pagi['state'] == 'done':
                            sde_pagi_error = _('This SDE import ID is already finished, please use a new SDE import ID')
                        elif sde_pagi_page - sde_pagi['page'] != 1:
                            sde_pagi_error = _('The page number must be in sequential order without gaps: last page imported %s, imported page %s') \
                                % (sde_pagi['page'], json_data['sde_pagination_page'])
                        else:
                            # Update the existing JSON with the new data in the key move_lines
                            pagi_json_text = sde_pagi['pagination_json_text']
                            pagi_json_data = json.loads(pagi_json_text)

                            pagi_json_data['move_lines'].extend(json_data['move_lines'])
                            pagi_json_text = json.dumps(pagi_json_data)

                            pagi_vals = {
                                'pagination_json_text': pagi_json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, 1, sde_pagi_ids[0], pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s updated%s with page %s') % (json_data['sde_pagination_id'], sde_pagi_end_msg, sde_pagi_page)
                    else:
                        if sde_pagi_page != 1:
                            sde_pagi_error = _('The first page of a paginated SDE import must be 1')
                        else:
                            sde_pagi_vals = {
                                'state': json_data.get('sde_pagination_end') and 'done' or 'progress',
                                'pagination_json_id': json_data['sde_pagination_id'],
                                'pagination_json_text': json_text,
                                'pagination_keys': json_data.get('name', ''),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, 1, sde_pagi_vals, context=context)
                            pagi_msg = _('SDE pagination for %s created%s') % (json_data['sde_pagination_id'], sde_pagi_end_msg)

            if sde_pagi_error:
                raise osv.except_osv(_('Error'), _('An error occurred during the management of the paginated SDE import "%s": %s')
                                     % (json_data.get('sde_pagination_id'), sde_pagi_error))
            elif not json_data.get('sde_pagination_id') or (sde_pagi_end_msg and sde_pagi_id):
                # Get the correct JSON data if the pagination has been used
                if sde_pagi_id and pagi_json_text and pagi_json_data:
                    json_text = pagi_json_text
                    json_data = pagi_json_data

                # Get the Physical Inventory from the name
                if not json_data.get('name'):
                    raise osv.except_osv(_('Error'), _('The main key "name" is mandatory and should not be empty'))
                pi_ids = self.get_pi_from_refs(cr, uid, [json_data['name']], 'count', context=context)
                pi_id = pi_ids[0]
                pi = pi_obj.browse(cr, uid, pi_id, fields_to_fetch=['ref', 'sde_updated', 'location_id'], context=context)
                if pi.sde_updated:
                    raise osv.except_osv(_('Error'), _('The Physical Inventory %s has already been updated by SDE. Please process the imported data in UniField or reset the SDE update there') % (pi.ref,))

                if not json_data.get('location'):
                    raise osv.except_osv(_('Error'), _('The main key "location" is mandatory and should not be empty'))

                # Reset the quantity of the counting sheet lines
                cr.execute("""UPDATE physical_inventory_counting SET quantity = NULL WHERE inventory_id = %s""", (pi_id,))

                # Import the data
                line_items, errors, warnings = [], [], []

                all_uom = {}
                uom_ids = uom_obj.search(cr, uid, [], context=context)
                for uom in uom_obj.read(cr, uid, uom_ids, ['name'], context=context):
                    all_uom[uom['name'].lower()] = uom['id']

                if not json_data.get('location') or json_data.get('location').lower() != pi.location_id.name.lower():
                    errors.append(_('Location is different to inventory location'))

                # Check for additional errors and update/create the counting lines
                line_errors, line_warnings = pi_obj.import_counting_sheet_manage_lines(cr, uid, pi_id, json_data.get('lines', []), context=context)
                for line_warn in line_warnings:
                    if line_warnings[line_warn]:
                        warnings.append(_('Line number %s: %s') % (line_warn or _('empty'), '. '.join(line_warnings[line_warn])))
                for line_error in line_errors:
                    if line_errors[line_error]:
                        if line_warnings and line_warnings[line_error]:
                            line_errors[line_error].extend(line_warnings[line_error])
                        errors.append(_('Line number %s: %s') % (line_error or _('empty'), '. '.join(line_errors[line_error])))

                if errors:
                    error_msg = _('Some errors occurred during the import: %s') % ('; '.join(errors),)
                    if warnings:
                        error_msg += _('. Warning: %s') % ('; '.join(warnings),)
                    raise osv.except_osv(_('Error'), error_msg)

                result['message'] = pagi_msg or _('Done')
                if warnings:
                    result['message'] += _('. Warning: %s') % ('; '.join(warnings),)

                # Set the Physical Inventory as sde_updated, remove the banner message, and update Responsible
                pi_data = {'responsible': json_data.get('responsible', ''), 'sde_updated': True, 'sde_update_msg': False}
                pi_obj.write(cr, uid, pi_id, pi_data, context=context)

                # Log the update
                self.pool.get('sde.update.log').create(cr, 1, {'date': datetime.now(), 'doc_type': 'pi_count', 'doc_ref': pi.ref}, context=context)
            elif pagi_msg:
                result['message'] = pagi_msg
        except Exception as e:
            cr.rollback()
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return result

    def sde_pi_export(self, cr, uid, json_text, pi_type, context=None):
        '''
        Method used by the SDE script to export info on Physical Inventories Counting/Discrepancy lines
        '''
        if context is None:
            context = {}
        if not pi_type:
            raise osv.except_osv(_('Error'), _('Please specify a pi_type'))

        pi_obj = self.pool.get('physical.inventory')
        pagi_exp_obj = self.pool.get('sde.export.pagination')

        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.instance
        # if pi_type == 'discr':
        #     export_name = _('Discrepancy lines')
        #     export_type = 'pi_discr'
        # else:
        export_name = _('Counting sheet')
        export_type = 'pi_count'

        result = {'database': instance_name, 'error': False, 'message': '', 'data': []}
        pagi_msg = ''
        try:
            json_data = json.loads(json_text)

            # Check if the call was to the correct instance
            if not json_data.get('database'):
                raise osv.except_osv(_('Error'), _('The main key "database" is mandatory and should not be empty'))
            if json_data['database'] != instance_name:
                raise osv.except_osv(_('Error'), _('The database name in the given JSON (%s) does not correspond to the current instance (%s)')
                                     % (json_data['database'], instance_name))

            if json_data.get('sde_pagination_id'):
                # Check the pagination data
                if not json_data.get('sde_pagination_page'):
                    raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" is mandatory and should not be empty when using "sde_pagination_id"'))
                try:
                    json_data['sde_pagination_page'] = int(json_data['sde_pagination_page'])
                except:
                    raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" must be an integer'))
                if json_data['sde_pagination_page'] <= 0:
                    raise osv.except_osv(_('Error'), _('The main key "sde_pagination_page" must be above 0'))

                pagi_exp_domain = [('doc_type', '=', export_type), ('pagination_json_id', '=', json_data['sde_pagination_id']),
                                   ('page', '=', json_data['sde_pagination_page'])]
                pagi_exp_ids = pagi_exp_obj.search(cr, 1, pagi_exp_domain, context=context)
                if pagi_exp_ids:
                    pagi_exp = pagi_exp_obj.read(cr, 1, pagi_exp_ids[0], ['pagination_json_text'], context=context)
                    result.update({
                        'sde_pagination_id': json_data['sde_pagination_id'],
                        'sde_pagination_page': json_data['sde_pagination_page'],
                        'message': _('The Physical Inventory %s data from the page %s of %s have been exported')
                        % (export_name, json_data['sde_pagination_page'], json_data['sde_pagination_id']),
                        'data': json.loads(pagi_exp['pagination_json_text']),
                    })
                else:
                    raise osv.except_osv(_('Error'), _('No Physical Inventory %s export data was found with the "sde_pagination_id" %s and the "sde_pagination_page" %s')
                                         % (export_name, json_data['sde_pagination_id'], json_data['sde_pagination_page']))
            else:
                # Get the data with the references given
                pi_ids, pi_names = [], []
                if json_data.get('pi_list') and isinstance(json_data['pi_list'], list):
                    try:
                        json_data['pi_list'] = [str(pi_name).strip() for pi_name in json_data['pi_list']]
                    except:
                        raise osv.except_osv(_('Error'),  _('One or more of the Physical Inventory names in the key "pi_list" are not usable. Please ensure that all the entries in this list are a character string or can be converted to one'))
                    pi_names = json_data['pi_list']
                    pi_ids = self.get_pi_from_refs(cr, uid, pi_names, pi_type, context=context)
                else:
                    # if pi_type == 'discr':
                    #     pi_domain = [('state', 'in', ['counted', 'validated', 'confirmed']), ('discrepancies_generated', '=', True)]
                    # else:
                    pi_domain = [('state', 'in', ['counting', 'counted']), ('discrepancies_generated', '=', False)]
                    pi_ids = pi_obj.search(cr, uid, pi_domain, context=context)

                if not pi_ids:
                    raise osv.except_osv(_('Error'), _('There is no Physical Inventory %s to export') % (export_name,))

                # Default number of lines per page is 100 if not specified
                lines_per_page = 100
                if json_data.get('lines_per_page'):
                    try:
                        json_data['lines_per_page'] = int(json_data['lines_per_page'])
                    except:
                        raise osv.except_osv(_('Error'), _('The main key "lines_per_page" must be an integer'))
                    if json_data['lines_per_page'] <= 0:
                        raise osv.except_osv(_('Error'), _('The main key "lines_per_page" must be above 0'))
                    lines_per_page = json_data['lines_per_page']

                # Count the number of lines
                # if pi_type == 'discr':
                #     cr.execute("""SELECT COUNT(id) FROM physical_inventory_discrepancy WHERE inventory_id IN %s AND ignored = False""", (tuple(pi_ids),))
                # else:
                cr.execute("""SELECT COUNT(id) FROM physical_inventory_counting WHERE inventory_id IN %s""", (tuple(pi_ids),))
                nb_lines = cr.fetchone()[0]

                data = {}
                offset = 0
                # if pi_type == 'discr':
                #     threaded_method = self.create_pi_discrepancy_paginated_export
                #     for pi in self.get_pi_discrepancy_export_data(cr, uid, pi_ids, offset, lines_per_page, context=context):
                #         if not data.get(pi[0]):
                #             data[pi[0]] = {
                #                 'name': pi[1] or '',
                #                 'lines': [],
                #             }
                #
                #         data[pi[0]]['lines'].append({
                #             'product_code': pi[2],
                #         })
                # else:
                threaded_method = self.create_pi_counting_paginated_export
                for pi in self.get_pi_counting_export_data(cr, uid, pi_ids, offset, lines_per_page, context=context):
                    if not data.get(pi[0]):
                        data[pi[0]] = {
                            'details': pi[1] or '',
                            'responsible': pi[2] or '',
                            'date': pi[3] or '',
                            'location': pi[4] or '',
                            'updated_by_sde': pi[5] or False,
                            # 'latest_log': pi[6] or '',
                            # 'latest_log_date': pi[7] or '',
                            'lines': [],
                        }

                    data[pi[0]]['lines'].append({
                        'line_number': pi[7],
                        'product_code': pi[8],
                        'product_name': pi[9],
                        'product_creator': pi[10],
                        'nomen_main_type': pi[11],
                        'uom': pi[12] or '',
                        'product_qty': pi[13] and int(pi[13]) or False,
                        'prodlot_id': pi[14] or '',
                        'expired_date': pi[15] or '',
                        'kc_check': pi[16] or False,
                        'dg_check': pi[17] == 'True' and _('True') or pi[17] == 'no_know' and _('Unknown') or _('False'),
                        'np_check': pi[18] or False,
                        'batch_managed': pi[19] or False,
                        'expiry_managed': pi[20] or False,
                    })

                if nb_lines > lines_per_page:
                    sde_pagi_id = self.pool.get('ir.sequence').get(cr, uid, 'sde.export.pagination')
                    sde_pagi_page = 1
                    last_page = math.ceil(nb_lines / lines_per_page)

                    pagi_exp_obj.create(cr, 1, {'pagination_json_id': sde_pagi_id, 'pagination_json_text': json.dumps(data),
                                                'doc_type': export_type, 'page': sde_pagi_page, 'last_page': False,
                                                'with_lines': True}, context=context)
                    result.update({'sde_pagination_id': sde_pagi_id, 'sde_pagination_page': sde_pagi_page,
                                   'sde_pagination_last_page': last_page})

                    pagi_msg = _('. The export have been paginated into %s pages. If you want to retrieve the other pages, please use the "sde_pagination_id" data given') % (last_page,)

                    # Create the remaining pages in the background
                    while sde_pagi_page < last_page:
                        sde_pagi_page += 1
                        offset += lines_per_page
                        threaded_exp_pagi = threading.Thread(target=threaded_method,
                                                             args=(cr, uid, pi_ids, sde_pagi_id, sde_pagi_page,
                                                                   last_page, offset, lines_per_page, context))
                        threaded_exp_pagi.start()

                final_msg_pi = pi_names and ', '.join(pi_names) or _('%s Physical Inventories') % (len(pi_ids), )
                result.update({
                    'data': data,
                    'message': _('The Physical Inventory %s data of %s have been exported%s')% (export_name, final_msg_pi, pagi_msg)
                })
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                error_msg = e.value
            else:
                error_msg = e.args and '. '.join(e.args) or e
            result.update({'error': True, 'message': error_msg})

        return result

    def get_pi_from_refs(self, cr, uid, pi_list, type, context=None):
        if context is None:
            context = {}

        pi_obj = self.pool.get('physical.inventory')

        states_msg, type_msg = '', ''
        # if type == 'count':
        pi_default_domain = [('state', 'in', ['counting', 'counted']), ('discrepancies_generated', '=', False)]
        type_msg = _('with a Counting sheet ')
        # elif type == 'discr':
        #     pi_default_domain = [('state', 'in', ['counted', 'validated', 'confirmed']), ('discrepancies_generated', '=', True))]
        #     type_msg = _('with Discrepancy Lines ')
        # else:
        #     states = ['counting', 'counted', 'validated', 'confirmed']
        #     states_msg = _('%s ') % ('/'.join([PI_STATES[state] for state in states]))
        #     pi_default_domain = [('state', 'in', states)]

        pi_ids, not_found = [], []
        for pi_name in pi_list:
            pi_domain = pi_default_domain.copy()
            pi_domain.append(('ref', '=', pi_name))
            pi_id = pi_obj.search(cr, uid, pi_domain, context=context)
            if pi_id:
                pi_ids.append(pi_id[0])
            else:
                not_found.append(pi_name)

        if not_found:
            raise osv.except_osv(_('Error'), _('The %sPhysical Inventories %s%s could not be found')
                                 % (states_msg, type_msg, ', '.join(not_found),))

        return pi_ids

    def get_pi_counting_export_data(self, cr, uid, ids, offset, limit, context=None):
        """
        Get info from PIs, its Counting sheet, its latest Track Change
        """
        if context is None:
            context = {}

        cr.execute("""
            SELECT
                pi.ref, -- 0
                pi.name, -- 1
                pi.responsible, -- 2
                pi.date, -- 3
                l.name, -- 4
                pi.sde_updated, -- 5
                -- MAX(a.log), -- 6
                -- MAX(a.timestamp), -- 7
                picount.id, -- 8
                picount.line_no, -- 9
                pp.default_code, -- 10
                pt.name, -- 11
                pis.name, -- 12
                pno.name, -- 13
                u.name, -- 14
                picount.quantity, -- 15
                picount.batch_number, -- 16
                picount.expiry_date, -- 17
                pcc.cold_chain, -- 18 kc_check
                pp.dangerous_goods, -- 19 dg_check
                pp.controlled_substance, -- 20 np_check
                pp.batch_management, -- 21
                pp.perishable -- 22
            FROM physical_inventory_counting picount
                LEFT JOIN physical_inventory pi ON picount.inventory_id = pi.id
                LEFT JOIN audittrail_log_line a ON pi.id = a.res_id AND object_id = (SELECT id FROM ir_model WHERE model = 'physical.inventory' LIMIT 1)
                LEFT JOIN stock_location l ON pi.location_id = l.id
                LEFT JOIN product_product pp ON picount.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_cold_chain pcc ON pp.cold_chain = pcc.id
                LEFT JOIN product_international_status pis ON pp.international_status = pis.id
                LEFT JOIN product_nomenclature pno ON pt.nomen_manda_0 = pno.id
                LEFT JOIN product_uom u ON picount.product_uom_id = u.id
            WHERE pi.id IN %s
            GROUP BY pi.id, pi.ref, pi.name, pi.responsible, pi.date, l.name, picount.line_no, picount.id, picount.id,
                picount.line_no, pp.default_code, pt.name, pis.name, pno.name, u.name, picount.quantity,
                picount.batch_number, picount.expiry_date, pcc.cold_chain, pp.dangerous_goods, pp.controlled_substance,
                pp.batch_management, pp.perishable
            ORDER BY pi.id, picount.line_no, picount.id OFFSET %s LIMIT %s
        """, (tuple(ids), offset, limit)) # not_a_user_entry

        return cr.fetchall()

    def create_pi_counting_paginated_export(self, cr, uid, ids, pagi_ref, page, last_page, offset, limit, context=None):
        '''
        Method to be used in the background to create the paginated exports beyond page 1
        '''
        if context is None:
            context = {}

        new_cr = pooler.get_db(cr.dbname).cursor()

        data = {}
        for pi in self.get_pi_counting_export_data(cr, uid, ids, offset, limit, context=context):
            if not data.get(pi[0]):
                data[pi[0]] = {
                    'details': pi[1] or '',
                    'responsible': pi[2] or '',
                    'date': pi[3] or '',
                    'location': pi[4] or '',
                    'updated_by_sde': pi[5] or False,
                    # 'latest_log': pi[6] or '',
                    # 'latest_log_date': pi[7] or '',
                    'lines': [],
                }

            data[pi[0]]['lines'].append({
                'line_number': pi[7],
                'product_code': pi[8],
                'product_name': pi[9],
                'product_creator': pi[10],
                'nomen_main_type': pi[11],
                'uom': pi[12] or '',
                'product_qty': pi[13] and int(pi[13]) or False,
                'prodlot_id': pi[14] or '',
                'expired_date': pi[15] or '',
                'kc_check': pi[16] or False,
                'dg_check': pi[17] == 'True' and _('True') or pi[17] == 'no_know' and _('Unknown') or _('False'),
                'np_check': pi[18] or False,
                'batch_managed': pi[19] or False,
                'expiry_managed': pi[20] or False,
            })

        pagi_vals = {'pagination_json_id': pagi_ref, 'pagination_json_text': json.dumps(data), 'doc_type': 'pi_count',
                     'page': page, 'last_page': page == last_page, 'with_lines': True}
        self.pool.get('sde.export.pagination').create(new_cr, 1, pagi_vals, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True


sde_import()


class sde_update_log(osv.osv):
    _name = 'sde.update.log'
    _description = 'SDE Update Logs'
    _order = 'id desc'

    _columns = {
        'date': fields.datetime('Update Date', required=True, readonly=True),
        'doc_type': fields.selection(string='Document Type', selection=[('in', 'Incoming Shipment'), ('pick', 'Picking Ticket'),
                                                                        ('out', 'Delivery Order'), ('ppl', 'Pre-Packing List'),
                                                                        ('pi_count', 'Physical Inventory Counting Sheet')], required=True, readonly=True),
        'doc_ref': fields.char(string='Reference', size=64, required=True, readonly=True),
    }


sde_update_log()


class sde_import_pagination(osv.osv):
    _name = 'sde.import.pagination'
    _description = 'SDE Paginated Imports'
    _order = 'id desc'

    _columns = {
        'state': fields.selection(string='State', selection=[('progress', 'In progress'), ('done', 'Done')], readonly=True),
        'pagination_json_id': fields.char(string='Pagination JSON ID', size=16, required=True, readonly=True),
        'pagination_json_text': fields.text(string='Pagination JSON text', required=True, readonly=True),
        'pagination_keys': fields.text(string='Pagination keys', required=True, readonly=True),
        'page': fields.integer(string='SDE import page', required=True, readonly=True),
        'last_modification': fields.datetime(string='Last modification', readonly=True),
    }

    _defaults = {
        'state': 'progress',
    }


sde_import_pagination()


class sde_export_pagination(osv.osv):
    _name = 'sde.export.pagination'
    _description = 'SDE Paginated Exports'
    _order = 'pagination_json_id desc, page desc'

    _columns = {
        'pagination_json_id': fields.char(string='Pagination JSON ID', size=32, required=True, readonly=True),
        'pagination_json_text': fields.text(string='Pagination JSON text', required=True, readonly=True),
        'doc_type': fields.selection(string='Document Type', selection=[('pick', 'Picking Ticket'), ('out', 'Delivery Order'),
                                                                        ('ppl', 'Pre-Packing List'), ('pi_count', 'Physical Inventory Counting Sheet')],
                                     required=True, readonly=True),
        'page': fields.integer(string='SDE import page', required=True, readonly=True),
        'last_page': fields.boolean(string='Last page of the export', readonly=True),
        'with_lines': fields.boolean(string='Exported with lines', readonly=True),
    }

    _defaults = {
        'last_page': False,
        'with_lines': False,
    }


sde_export_pagination()


class sde_availability_check(osv.osv):
    _name = 'sde.availability.check'
    _description = 'SDE Availability Checks'
    _order = 'name desc'

    def _get_state(self, cr, uid, ids, fields, arg, context=None):
        '''
        Get the State
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for sde_avchk in self.read(cr, uid, ids, ['state', 'nb_checked', 'nb_to_check'], context=context):
            res[sde_avchk['id']] = sde_avchk['state'] != 'error' and sde_avchk['nb_checked'] >= sde_avchk['nb_to_check'] \
                and 'done' or sde_avchk['state']

        return res

    _columns = {
        'name': fields.char(string='SDE Availability Check Reference', size=32, required=True, readonly=True),
        'state': fields.function(_get_state, method=True, type='selection', selection=[('progress', 'In progress'), ('done', 'Successfully Completed'), ('error', 'Error')],
                                 string='State', eadonly=True, store={'sde.availability.check': (lambda self, cr, uid, ids, c=None: ids, ['nb_checked'], 10)}),
        'doc_type': fields.selection(string='Document Type', selection=[('out', 'Delivery Order')], required=True, readonly=True),
        'checked_pick_ids': fields.many2many('stock.picking', 'sde_availability_check_pick_rel', 'picking_id', 'sde_availability_check_id',
                                             string='Affected documents', help='List of documents that had their Availability checked', readonly=True),
        'nb_checked': fields.integer(string='Number of checked documents', readonly=True),
        'nb_to_check': fields.integer(string='Number of documents to check', required=True, readonly=True),
        'error_msg': fields.text(string='Error Message', readonly=True),
    }

    _defaults = {
        'state': 'progress',
        'nb_checked': 0,
    }


sde_availability_check()
