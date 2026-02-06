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
from tools.rpc_decorators import jsonrpc_orm_exposed


class sde_import(osv.osv_memory):
    _name = 'sde.import'
    _description = 'SDE Tools'

    _columns = {
        'json_text': fields.text(string='JSON data', help='Please put the data on a single line, with no line return'),
        'file': fields.binary(string='File', filters='*.xml, *.xls'),
        'filename': fields.char(string='Imported filename', size=256),
        'message': fields.text(string='Message'),
        'po_ref_for_in': fields.char(string='PO reference to find the IN', size=128),
        'pack_ref_for_in': fields.char(string='Ship/OUT reference to find the IN', size=128),
        'partner_fo_ref_for_in': fields.char(string='Supplier FO reference to find the IN', size=128),
    }

    def wizard_sde_import_in_updated(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the XMLRPC script to import data in an Available Updated IN
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        return self.wizard_sde_import_in(cr, uid, ids, context=context, in_updated=True)

    def wizard_sde_import_in(self, cr, uid, ids, context=None, in_updated=False):
        '''
        Method to use instead of the XMLRPC script to import data in an Available/Available Shipped IN
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        sde_imp = self.read(cr, uid, ids[0], ['json_text'], context=context)
        if not sde_imp['json_text']:
            raise osv.except_osv(_('Warning'), _('No data to import'))
        msg = self.sde_in_import(cr, uid, sde_imp['json_text'], in_updated, context=context)

        return self.write(cr, uid, ids, {'message': msg}, context=context)

    def wizard_sde_file_to_in(self, cr, uid, ids, context=None):
        '''
        Method to use instead of the XMLRPC script
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
        Method to use instead of the XMLRPC script
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
        msg, pagi_msg, sde_pagi_end_msg, sde_pagi_id = False, False, False, False
        pagi_json_text = ''
        pagi_json_data = []
        try:
            json_data = json.loads(json_text)

            sde_pagi_state, sde_pagi_error = False, False
            if json_data.get('sde_pagination_id'):
                if 'sde_pagination_page' not in json_data or 'sde_pagination_type' not in json_data:
                    sde_pagi_error = _('The 3 keys sde_pagination_id, sde_pagination_page and sde_pagination_type are mandatory to use the pagination in the SDE import')
                else:
                    sde_pagi_end_msg = json_data['sde_pagination_type'] == 'end' and _(' and finished') or ''
                    sde_pagi_page = json_data['sde_pagination_page']
                    try:
                        sde_pagi_page = int(sde_pagi_page)
                    except ValueError:
                        sde_pagi_error = _('The page number must be an integer')
                    sde_pagi_ids = pagi_obj.search(cr, uid, [('pagination_json_id', '=', json_data['sde_pagination_id'])], context=context)
                    if sde_pagi_ids:
                        sde_pagi_id = sde_pagi_ids[0]
                        sde_pagi = pagi_obj.read(cr, uid, sde_pagi_id, context=context)
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
                            parcel_keys = sde_pagi['pagination_parcel_keys'].split(',')
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
                                'pagination_parcel_keys': ','.join(parcel_keys),
                                'page': sde_pagi_page,
                                'last_modification': datetime.now(),
                            }
                            if sde_pagi_end_msg:
                                pagi_vals['state'] = 'done'
                            pagi_obj.write(cr, uid, sde_pagi_ids[0], pagi_vals, context=context)
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
                                'pagination_parcel_keys': ','.join(parcel_keys),
                                'page': 1,
                                'last_modification': datetime.now(),
                            }
                            sde_pagi_id = pagi_obj.create(cr, uid, sde_pagi_vals, context=context)
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

                # If the IN is Available Updated reset as much data as possible, compared to the PO
                if in_updated and self.pool.get('stock.picking').read(cr, uid, in_id, ['state'], context=context)['state'] == 'updated':
                    self.reset_in_available_updated(cr, uid, [in_id], context=context)

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

                in_simu_obj.launch_simulate(cr, uid, [simu_id], context=context)
                file_res = pick_obj.generate_simulation_screen_report(cr, uid, simu_id, context=context)

                simu_data = in_simu_obj.read(cr, uid, simu_id, ['import_error_ok', 'message'], context=context)
                msg = simu_data['message'] or pagi_msg or 'Done'
                # Only import when all the data is correct
                if not simu_data['import_error_ok']:
                    in_simu_obj.launch_import(cr, uid, [simu_id], context=context)
                    # Log the update
                    in_name = pick_obj.read(cr, uid, in_id, ['name'], context=context)['name']
                    self.pool.get('sde.update.log').create(cr, uid, {'date': datetime.now(), 'doc_type': 'in', 'doc_ref': in_name}, context=context)

                # attach the simulation report to the IN
                self.pool.get('ir.attachment').create(cr, uid, {
                    'name': 'SDE_simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                    'datas_fname': 'SDE_simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                    'description': 'IN simulation screen',
                    'res_model': 'stock.picking',
                    'res_id': in_id,
                    'datas': file_res.get('result'),
                })
            else:
                msg = pagi_msg or 'Done'
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                msg = e.value
            else:
                msg = e.args and '. '.join(e.args) or e
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')

        return msg

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
        ship_ref = json_data.get('freight') and json_data['freight'].strip().upper() or False

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

        return in_id[0]

    def reset_in_available_updated(self, cr, uid, ids, context=None):
        '''
        For each move of the Available Updated IN, reset as much data as possible:
            - Merge the quantities of split lines and delete the splits
            - Remove any BN/ED info
            - Restore the product of the linked PO line
        '''
        if context is None:
            context = {}
        if not ids:
            return True

        move_obj = self.pool.get('stock.move')

        cr.execute("""
            SELECT m.id, m.picking_id, m.line_number, m.purchase_line_id, m.product_qty, COALESCE(pl.product_id, m.product_id)
            FROM stock_move m LEFT JOIN purchase_order_line pl ON m.purchase_line_id = pl.id
            WHERE m.state = 'assigned' AND m.picking_id in %s and m.product_qty != 0
            """, (tuple(ids),))
        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2], x[3])
            if key not in data:
                data[key] = {'product_id': x[5], 'product_qty': 0, 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['product_qty'] += x[4]
        for key in data:
            move_vals = {'product_id': data[key]['product_id'], 'product_qty': data[key]['product_qty'],
                         'product_uos_qty': data[key]['product_qty'], 'prodlot_id': False, 'expired_date': False}
            move_obj.write(cr, uid, data[key]['master'], move_vals, context=context)
        move_obj.unlink(cr, uid, to_del, force=True, context=context)

        return True


sde_import()


class sde_update_log(osv.osv):
    _name = 'sde.update.log'
    _description = 'SDE Update Logs'
    _order = 'id desc'

    _columns = {
        'date': fields.datetime('Update Date', required=True, readonly=True),
        'doc_type': fields.selection(string='Document', selection=[('in', 'Incoming Shipment')], required=True, readonly=True),
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
        'pagination_parcel_keys': fields.text(string='Pagination parcels keys', required=True, readonly=True),
        'page': fields.integer(string='SDE import page', required=True, readonly=True),
        'last_modification': fields.datetime(string='Last modification', readonly=True),
    }

    _defaults = {
        'state': 'progress',
    }


sde_import_pagination()
