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

from osv import osv, fields
import netsvc

import logging
import time

from sync_common import xmlid_to_sdref
from sync_client import get_sale_purchase_logger
from sync_client.log_sale_purchase import RunWithoutException
from sync_client.message import dict_to_obj

from tools.translate import _


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def _get_sent_ok(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = m.state == 'cancel' and m.picking_id and m.picking_id.sale_id and m.picking_id.sale_id.state in ['done', 'cancel'] or False

        return res

    def _src_sent_ok(self, cr, uid, obj, name, args, context=None):
        if not len(args):
            return []

        for arg in args:
            if arg[0] == 'to_be_sent':
                if arg[1] != '=' and arg[2] is True:
                    raise osv.except_osv(
                        _('Error'),
                        _('Only \'=\' operator is accepted for \'to_be_sent\' field')
                    )

                res = [('state', '=', 'cancel')]
                order_ids = self.pool.get('sale.order').search(cr, uid, [('state', 'in', ['done', 'cancel'])])
                picking_ids = self.pool.get('stock.picking').search(cr, uid, [('type', '=', 'out'), ('sale_id', 'in', order_ids)])
                res.append(('picking_id', 'in', picking_ids))

        return res

    _columns = {
        'to_be_sent': fields.function(
            _get_sent_ok,
            fnct_search=_src_sent_ok,
            method=True,
            type='boolean',
            string='Send to other instance ?',
            readonly=True,
        ),
        'date_cancel': fields.datetime(string='Date cancel'),
    }

    def action_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'date_cancel': time.strftime('%Y-%m-%d %H:%M:%S')})
        return super(stock_move, self).action_cancel(cr, uid, ids, context=context)

stock_move()


class stock_picking(osv.osv):
    '''
    synchronization methods related to stock picking objects
    '''
    _inherit = "stock.picking"
    _logger = logging.getLogger('------sync.stock.picking')

    def format_data(self, cr, uid, data, source, context=None):
        '''
        we format the data, gathering ids corresponding to objects
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        # product
        product_name = data['product_id']['name']

        default_code = False
        if data.get('product_id', {}).get('default_code'):
            partner_type = self.pool.get('so.po.common').get_partner_type(cr, uid, source, context)
            if partner_type in ['section', 'intermission']:
                default_code = data['product_id']['default_code']

        product_id = self.pool.get('so.po.common').get_product_id(cr, uid, data['product_id'], default_code, context=context)
        if not product_id:
            product_ids = prod_obj.search(cr, uid, [('name', '=', product_name)], context=context)
            if not product_ids:
                raise Exception, "The corresponding product does not exist here. Product name: %s" % product_name
            product_id = product_ids[0]

        # UF-1617: asset form
        asset_id = False
        if data.get('asset_id') and data['asset_id']['id']:
            asset_id = self.pool.get('product.asset').find_sd_ref(cr, uid, xmlid_to_sdref(data['asset_id']['id']), context=context)

        # uom
        uom_id = uom_obj.find_sd_ref(cr, uid, xmlid_to_sdref(data['product_uom']['id']), context=context)
        if not uom_id:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s" % uom_id

        # UF-1617: Handle batch and asset object
        batch_id = False
        batch_values = data.get('prodlot_id')
        expired_date = False
        if batch_values and product_id:
            prodlot_obj = self.pool.get('stock.production.lot')
            prod = prod_obj.browse(cr, uid, product_id, context=context)
            if prod.perishable and not prod.batch_management and batch_values.get('life_date'):
                # In case it's a ED only product, then search for date and product, no need to search for batch name
                batch_id = prodlot_obj._get_prodlot_from_expiry_date(cr, uid, batch_values['life_date'], product_id, comment=batch_values.get('comment'), context=context)
                expired_date = data['expired_date']
            elif prod.perishable and prod.batch_management and batch_values.get('name') and batch_values.get('life_date'):
                is_internal = False
                if 'type' not in batch_values:
                    # old msg: type was not sent
                    is_internal = batch_values['name'].startswith('MSFBN')
                else:
                    is_internal = batch_values['type'] == 'internal'
                if not is_internal:
                    # US-838: for BN, retrieve it or create it, in the follwing method
                    batch_id, msg = self.retrieve_batch_number(cr, uid, product_id, batch_values, context)
                    expired_date = data['expired_date']

        # UTP-872: Add also the state into the move line, but if it is done, then change it to assigned (available)
        state = data['state']
        if state == 'done':
            state = 'assigned'

        # UF-2301: Take care of DPO reception
        dpo_line_id = data.get('dpo_line_id', False)

        # build a dic which can be used directly to update the stock move
        result = {
            'line_number': data['line_number'],
            'product_id': product_id,
            'product_uom': uom_id,
            'product_uos': uom_id,
            'uom_id': uom_id,
            'date': data['date'],
            'date_expected': data['date_expected'],
            'state': state,

            'original_qty_partial': data.get('original_qty_partial'),  # UTP-972

            'prodlot_id': batch_id,
            'expired_date': expired_date,

            'dpo_line_id': dpo_line_id,
            'sync_dpo': dpo_line_id and True or False,

            'asset_id': asset_id,
            'change_reason': data.get('change_reason') or None,
            'name': data['name'],
            'quantity': data['product_qty'] or 0.0,
            'note': data.get('note', False),
            'comment': data.get('comment'),
            'sale_line_id': data.get('sale_line_id', False) and data['sale_line_id'].get('id', False) or False,
            'resourced_original_remote_line': data.get('sale_line_id', False) and data['sale_line_id'].get('resourced_original_remote_line', False) or False,

        }
        for k in ['from_pack', 'to_pack', 'weight', 'height', 'length', 'width']:
            result[k] = data.get(k)
        return result

    def package_data_update_in(self, cr, uid, source, pick_dict, context=None):
        '''
        package the data to get info concerning already processed or not
        '''
        result = {}
        for out_info_dict_to_obj in pick_dict:
            out_info = out_info_dict_to_obj.to_dict()
            if out_info.get('move_lines', False):
                for line in out_info['move_lines']:
                    # Don't get the returned pack lines
                    if line.get('location_dest_id', {}).get('usage', 'customer') == 'customer':
                        # aggregate according to line number
                        line_dic = result.setdefault(line.get('line_number'), {})
                        # set the data
                        line_dic.setdefault('data', []).append(self.format_data(cr, uid, line, source, context=context))
                        # set the flag to know if the data has already been processed (partially or completely) in Out side
                        line_dic.update({'out_processed':  line_dic.setdefault('out_processed', False) or line['processed_stock_move']})
                        line_dic['data'][-1].update({'packing_list': out_info.get('packing_list'), 'ppl_name': out_info.get('previous_step_id') and out_info.get('previous_step_id').get('name') or out_info.get('name')})


        return result

    def picking_data_update_in(self, cr, uid, source, pick_info, context=None):
        '''
        If data come from a stock move (DPO), re-arrange data to match with partial_shipped_fo_updates_in_po method
        '''
        result = []

        for data in pick_info:
            out_info = data.to_dict()
            res = {}
            for key in out_info.keys():
                if key != 'move_lines':
                    res[key] = out_info.get(key)

            if out_info.get('subtype', False) in ('standard', 'picking') and out_info.get('move_lines', False):
                for line in out_info['move_lines']:
                    # Don't get the lines without dpo_line_id
                    if line.get('dpo_line_id', False):
                        res.setdefault('move_lines', [])
                        res['move_lines'].append(line)
            result.append(dict_to_obj(res))

        return result

    def partial_shippped_dpo_updates_in_po(self, cr, uid, source, out_info, context=None):
        if context is None:
            context = {}

        context.update({'for_dpo': True})
        return self.partial_shipped_fo_updates_in_po(cr, uid, source, out_info, context=context)


    # US-1294: Add the shipped qty into the move lines
    def _add_to_shipped_moves(self, already_shipped_moves, move_id, quantity):
        if move_id in already_shipped_moves:
            already_shipped_moves[move_id] += quantity
        else:
            already_shipped_moves[move_id] = quantity

    def partial_shipped_fo_updates_in_po(self, cr, uid, source, *pick_info, **kwargs):
        '''
        ' This sync method is used for updating the IN of Project side when the OUT/PICK at Coordo side became done.
        ' In partial shipment/OUT, when the last shipment/OUT is made, the original IN will become Available Shipped, no new IN will
        ' be created, as the whole quantiy of the IN is delivered (but not yet received at Project side)
        '''

        context = kwargs.get('context')
        move_proc = self.pool.get('stock.move.in.processor')
        if context is None:
            context = {}
        self._logger.info("+++ Call to update partial shipment/OUT from supplier %s to INcoming Shipment of PO at %s" % (source, cr.dbname))
        context['InShipOut'] = ""

        # Load common data (mainly for reason type) into context
        self.pool.get('data.tools').load_common_data(cr, uid, [], context=context)

        #if not isinstance(out_info, dict):
        #    pick_dict = out_info.to_dict()
        #else:
        #    pick_dict = out_info

        if context.get('for_dpo'):
            self.picking_data_update_in(cr, uid, source, pick_info, context=context)
            #US-1352: Reset this flag immediately, otherwise it will impact on other normal shipments!
            context.update({'for_dpo': False})

        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        move_obj = self.pool.get('stock.move')
        warehouse_obj = self.pool.get('stock.warehouse')

        # package data
        pack_data = self.package_data_update_in(cr, uid, source, pick_info, context=context)
        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        pick_dict = pick_info[0].to_dict()
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        # prepare the shipment/OUT reference to update to IN
        shipment = pick_dict.get('shipment_id', False)
        if shipment:
            shipment_ref = shipment['name'] # shipment made
        else:
            shipment_ref = pick_dict.get('name', False) # the case of OUT
        if not po_id and pick_dict.get('sale_id') and pick_dict.get('sale_id', {}).get('claim_name_goods_return'):
            po_sync_name = pick_dict.get('sale_id', {}).get('client_order_ref')
            if po_sync_name:
                po_split_name = po_sync_name.split('.')
                po_split_name.pop(0)
                po_name = '.'.join(po_split_name)
                po_ids = po_obj.search(cr, uid, [('name', '=', po_name)], context=context)
                if po_ids:
                    po_id = po_ids[0]


        if not po_id and not pick_dict.get('claim', False):
            # UF-1830: Check if the PO exist, if not, and in restore mode, send a warning and create a message to remove the ref on the partner document
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common.create_invalid_recovery_message(cr, uid, source, shipment_ref, context)
                return "Recovery: the reference to " + shipment_ref + " at " + source + " will be set to void."

            raise Exception, "The PO is not found for the given FO Ref: " + so_ref

        if shipment_ref:
            shipment_ref = source + "." + shipment_ref

        if po_id:
            po_name = po_obj.browse(cr, uid, po_id, context=context)['name']
            in_name_goods_return = False
            for move_line in pick_dict['move_lines']:
                if move_line.get('sale_line_id') and move_line.get('sale_line_id', {}).get('in_name_goods_return'):
                    in_name_goods_return = move_line['sale_line_id']['in_name_goods_return'].split(".")[-1]
            if in_name_goods_return:
                # search for the right IN in case of synchro of multiple missing/replacement IN
                in_id = self.pool.get('stock.picking')\
                    .search(cr, uid, [('name', '=', in_name_goods_return), ('purchase_id', '=', po_id), ('state', '=', 'assigned')], limit=1, context=context)[0]
            else:
                # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
                in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po_name, ['assigned'], context)
                if not in_id:
                    in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po_name, ['shipped'], context)
        else:
            # locations
            warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
            location_input_id = warehouse_obj.read(cr, uid, warehouse_ids, ['lot_input_id'])[0]['lot_input_id'][0]
            msf_supplier_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')[1]

            partner_id = self.pool.get('res.partner').search(cr, uid, [('name', '=', source)], context=context)[0]
            move_lines = []
            line_number = 0
            for line in pack_data:
                for x in pack_data[line]['data']:
                    prod_id = x.get('product_id')
                    if not prod_id:
                        raise Exception("Product %s not found" % x.get('name'))
                    line_number += 1
                    move_lines.append((0, 0, {
                        'change_reason': x.get('change_reason', False),
                        'comment': x.get('comment', False),
                        'date': x.get('date', False),
                        'date_expected': x.get('date_expected', False),
                        'expired_date': x.get('expired_date', False),
                        'prodlot_id': x.get('prodlot_id', False),
                        'line_number': line_number,
                        'name': x.get('name', False),
                        'note': x.get('note', False),
                        'original_qty_partial': x.get('product_qty', False),
                        'product_id': prod_id,
                        'product_qty': x.get('product_qty', False),
                        'product_uom': x.get('product_uom'),
                        'reason_type_id': context['common']['rt_goods_return'],
                        'location_id': msf_supplier_id,
                        'location_dest_id': location_input_id,
                    }))
                    x['line_number'] = line_number


            in_claim_dict = {
                'claim': pick_dict.get('claim', False),
                'min_date': pick_dict.get('min_date', False),
                'note': pick_dict.get('note', False),
                'partner_id': partner_id,
                'partner_id2': partner_id,
                'origin': pick_dict.get('origin', False),
                'partner_type_stock_picking': pick_dict.get('partner_type_stock_picking', False),
                'reason_type_id': context['common']['rt_goods_return'],
                'type': 'in',
                'subtype': 'standard',
                'shipment_ref': shipment_ref,
                'move_lines': move_lines
            }

            # when OUT line has been split in Pick or PLL
            for line in pack_data:
                for data in pack_data[line]['data']:
                    data['original_qty_partial'] = -1

            in_id = self.create(cr, uid, in_claim_dict, context=context)

        pack_info_obj = self.pool.get('wizard.import.in.pack.simulation.screen')
        pack_info_created = {}

        if in_id:
            in_name = self.read(cr, uid, in_id, ['name'], context=context)['name']
            in_processor = self.pool.get('stock.incoming.processor').create(cr, uid, {'picking_id': in_id}, context=context)
            self.pool.get('stock.incoming.processor').create_lines(cr, uid, in_processor, context=context)
            partial_datas = {}
            partial_datas[in_id] = {}
            context['InShipOut'] = "IN"  # asking the IN object to be logged
            already_set_moves = []
            line_processed = 0
            ignored_lines = []
            line_found = False
            for line in pack_data:
                line_processed += 1
                line_data = pack_data[line]

                #US-1294: Keep this list of pair (move_line: shipped_qty) as amount already shipped
                already_shipped_moves = {}
                split_processed = 0
                # get the corresponding picking line ids
                for data in line_data['data']:
                    split_processed += 1
                    if data.get('from_pack') and data.get('to_pack'):
                        pack_key = '%s-%s-%s' % (data.get('from_pack'), data.get('to_pack'), data.get('ppl_name'))
                        if pack_key not in pack_info_created:
                            pack_info_created[pack_key] = pack_info_obj.create(cr, uid, {
                                'parcel_from': data['from_pack'],
                                'parcel_to': data['to_pack'],
                                'total_weight': data['weight'],
                                'total_height': data['height'],
                                'total_length': data['length'],
                                'total_width': data['width'],
                                'packing_list': data.get('packing_list'),
                                'ppl_name': data.get('ppl_name'),
                            })
                        data['pack_info_id'] = pack_info_created[pack_key]
                    ln = data.get('line_number')
                    # UF-2148: if the line contains 0 qty, just ignore it!
                    qty = data.get('quantity', 0)
                    if qty == 0:
                        message = "Line number " + str(ln) + " with quantity 0 is ignored!"
                        self._logger.info(message)
                        continue

                    # If the line is canceled, then just ignore it!
                    state = data.get('state', 'cancel')
                    if state == 'cancel':
                        message = "Line number " + str(ln) + " with state cancel is ignored!"
                        self._logger.info(message)
                        continue

                    # JFB: already_set_moves not useful ?
                    search_move = [('id', 'not in', already_set_moves), ('picking_id', '=', in_id), ('line_number', '=', data.get('line_number')), ('state', '!=', 'cancel'), ('in_forced', '=', False)]

                    original_qty_partial = data.get('original_qty_partial')
                    orig_qty = data.get('quantity')

                    # JFB: original_qty_partial is always set except the stock move is cancelled
                    if original_qty_partial != -1:
                        search_move.append(('product_qty', '=', original_qty_partial))
                        orig_qty = original_qty_partial

                    move_ids = move_obj.search(cr, uid, search_move, context=context)
                    # JFB: already_set_moves not useful ?
                    if not move_ids:
                        #US-1294: Reduce the search condition
                        del search_move[0]
                        move_ids = move_obj.search(cr, uid, search_move, context=context)

                    #US-1294: If there is only one move line found, must check if this has already all taken in shipped moves list
                    if move_ids and len(move_ids) == 1:  # if there is only one move, take it for process
                        move = move_obj.read(cr, uid, move_ids[0], ['product_qty'], context=context)
                        if already_shipped_moves.get(move['id']) == move['product_qty']:
                            move_ids = False # search again
                            break

                    if not move_ids and original_qty_partial != -1:
                        #US-1294: Reduce the search condition
                        search_move = [('picking_id', '=', in_id), ('line_number', '=', data.get('line_number')), ('original_qty_partial', '=', original_qty_partial), ('state', '!=', 'cancel'), ('in_forced', '=', False)]
                        move_ids = move_obj.search(cr, uid, search_move, context=context)

                    #US-1294: But still no move line with exact qty as the amount shipped
                    already_closed = False
                    if not move_ids:
                        #US-1294: Now search all moves of the given IN and line number
                        search_move = [('picking_id', '=', in_id), ('line_number', '=', data.get('line_number')), ('state', '!=', 'cancel'), ('in_forced', '=', False)]
                        move_ids = move_obj.search(cr, uid, search_move, order='product_qty ASC', context=context)
                        if not move_ids:
                            # SLL edit, if move cannot be found, then use sync_linked_sol to find it:
                            sol_id = data.get('sale_line_id', False) and int(data['sale_line_id'].split('/')[-1]) or False
                            remote_partner = self.pool.get('so.po.common').get_partner_id(cr, uid, source, context=context)
                            if sol_id and remote_partner:
                                pol_id = self.pool.get('purchase.order.line').search(cr, uid, [
                                    ('order_id.partner_id', '=', remote_partner),
                                    ('sync_linked_sol', 'ilike', '%%/%s' % sol_id),
                                ], context=context)
                                if pol_id:
                                    move_ids = move_obj.search(cr, uid, [('purchase_line_id', 'in', pol_id), ('state', 'not in', ['done', 'cancel']), ('in_forced', '=', False)], context=context)
                                if not move_ids:
                                    already_closed = move_obj.search_exists(cr, uid, [('purchase_line_id', 'in', pol_id), ('state', 'in', ['done', 'cancel'])], context=context)
                        if not move_ids:
                            #US-1294: absolutely no moves -> probably they are closed, just show the error message then ignore
                            if not already_closed:
                                closed_pick_ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', '=', po_id), ('state', 'in', ['done', 'cancel'])], context=context)
                                if closed_pick_ids:
                                    already_closed = move_obj.search_exists(cr, uid, [('picking_id', 'in', closed_pick_ids), ('line_number', '=', data.get('line_number'))], context=context)

                            if not already_closed:
                                if data.get('resourced_original_remote_line'):
                                    resourced_po_line_id = data['resourced_original_remote_line'].split('/')[-1]
                                    if resourced_po_line_id:
                                        move_forced_id = self.pool.get('stock.move').search(cr, uid, [
                                            ('purchase_line_id', '=', int(resourced_po_line_id)),
                                            ('type', '=', 'in'),
                                            ('in_forced', '=', True)
                                        ], limit=1, order='state desc', context=context)
                                        if move_forced_id:
                                            move_forced = move_obj.browse(cr, uid, move_forced_id[0], fields_to_fetch=['picking_id', 'purchase_line_id'], context=context)
                                            ignored_lines.append('Line %s ignored because orignal line number %s forced in %s' % (data.get('line_number'), move_forced.purchase_line_id.line_number, move_forced.picking_id.name))
                                            continue
                                elif data.get('sale_line_id'):
                                    identifier = data.get('sale_line_id').split('.')[-1]
                                    prev_nr_id = self.pool.get('sync.client.message_received').search(cr, uid, [('target_id', '=', po_id), ('target_object', '=', 'in_forced_cr'), ('identifier', '=like', '%s_%%' % identifier)], limit=1, context=context)
                                    if prev_nr_id:
                                        ignored_lines.append('Line %s ignored because orignal line number forced, see NR id: %s_XX' % (data.get('line_number'), identifier))
                                        continue

                                message = "Line number " + str(ln) + " is not found in the original IN or PO"
                                self._logger.info(message)
                                raise Exception(message)
                            else:
                                # do not set the whole msg as NR if there are other lines to process
                                if len(pack_data) > line_processed or len(line_data['data']) > split_processed or line_found:
                                    ignored_lines.append('Line %s ignored because already processed (forced)' % (data.get('line_number')))
                                    continue
                                message = "Unable to receive Shipment Details into an Incoming Shipment in this instance as IN %s (%s) already fully/partially cancelled/Closed" % (
                                    in_name, po_name,
                                )
                                raise RunWithoutException(message)

                    move_id = False
                    if move_ids and len(move_ids) == 1:  # if there is only one move, take it for process
                        move_id = move_ids[0]
                    else:  # if there are more than 1 moves, then pick the next one not existing in the partial_datas[in_id]
                        # Search the best matching move
                        best_diff = False
                        for move in move_obj.read(cr, uid, move_ids, ['product_qty'], context=context):
                            line_proc_ids = move_proc.search(cr, uid, [
                                ('wizard_id', '=', in_processor),
                                ('move_id', '=', move['id']),
                            ], context=context)
                            if line_proc_ids:
                                diff = move['product_qty'] - orig_qty
                                # US-1294: If the same move has already been chosen in the previous round, then the shipped amount must be taken into account
                                if move['id'] in already_shipped_moves:
                                    diff -= already_shipped_moves[move['id']]

                                if diff >= 0 and (not best_diff or diff < best_diff):
                                    best_diff = diff
                                    move_id = move['id']
                                    if best_diff == 0.00:
                                        break
                        if not move_id:
                            move_id = move_ids[0]

                    if data.get('dpo_line_id'):
                        move_obj.write(cr, uid, [move_id], {'dpo_line_id': data.get('dpo_line_id')}, context=context)

                    # If we have a shipment with 10 packs and return from shipment
                    # the pack 2 and 3, the IN shouldn't be splitted in three moves (pack 1 available,
                    # pack 2 and 3 not available and pack 4 to 10 available) but splitted into
                    # two moves (one move for all products available and one move for all
                    # products not available in IN)
                    line_proc_ids = move_proc.search(cr, uid, [
                        ('wizard_id', '=', in_processor),
                        ('move_id', '=', move_id),
                        ('quantity', '=', 0.00),
                    ], context=context)
                    data['move_id'] = move_id
                    data['wizard_id'] = in_processor
                    already_set_moves.append(move_id)
                    if not line_proc_ids:
                        data['ordered_quantity'] = data['quantity']
                        new_id = move_proc.create(cr, uid, data, context=context)
                        if data.get('comment'):
                            move_proc.write(cr, uid, new_id, {'comment': data['comment']}, context=context)
                    else:
                        for line in move_proc.browse(cr, uid, line_proc_ids, context=context):
                            if line.product_id.id == data.get('product_id') and \
                               line.uom_id.id == data.get('uom_id') and \
                               (line.prodlot_id and line.prodlot_id.id == data.get('prodlot_id')) or (not line.prodlot_id and not data.get('prodlot_id')) and \
                               (line.asset_id and line.asset_id.id == data.get('asset_id')) or (not line.asset_id and not data.get('asset_id')):
                                move_proc.write(cr, uid, [line.id], data, context=context)
                                # comment is ovewritten in previous write
                                if data.get('comment'):
                                    move_proc.write(cr, uid, line.id, {
                                        'comment': data['comment']
                                    }, context=context)
                                break
                        else:
                            data['ordered_quantity'] = data['quantity']
                            move_proc_id = move_proc.create(cr, uid, data, context=context)
                            # comment is ovewritten in previous write
                            if data.get('comment'):
                                move_proc.write(cr, uid, move_proc_id, {'comment': data['comment']}, context=context)
                    line_found = True
                    #US-1294: Add this move and quantity as already shipped, since it's added to the wizard for processing
                    self._add_to_shipped_moves(already_shipped_moves, move_id, data['quantity'])

            # for the last Shipment of an FO, no new INcoming shipment will be created --> same value as in_id
            new_picking = self.do_incoming_shipment(cr, uid, in_processor, shipment_ref=shipment_ref, context=context)

            # Set the backorder reference to the IN !!!! THIS NEEDS TO BE CHECKED WITH SUPPLY PM!
            if new_picking != in_id:
                self.write(cr, uid, in_id, {'backorder_id': new_picking}, context)

            #UFTP-332: Check if shipment/out is given
            if shipment_ref:
                self.write(cr, uid, new_picking, {'already_shipped': True, 'shipment_ref': shipment_ref}, context)
            else:
                self.write(cr, uid, new_picking, {'already_shipped': True}, context)

            in_name = self.browse(cr, uid, new_picking, context=context)['name']
            if po_id:
                message = "The INcoming " + in_name + "(" + po_name + ") has now become shipped available!"
            else:
                message = "The INcoming " + in_name + "(no PO) has now become shipped available!"
            if ignored_lines:
                message = "\n".join([message]+ignored_lines)
                context['partial_sync_run'] = True
            self._logger.info(message)
            return message
        else:
            # still try to check whether this IN has already been manually processed
            in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po_name, ['done', 'shipped'], context)
            if not in_id:
                message = "The IN linked to " + po_name + " is not found in the system!"
                self._logger.info(message)
                raise Exception(message)

            #UFTP-332: Check if shipment/out is given
            if shipment_ref:
                same_in = self.search(cr, uid, [('id', '=', in_id), ('shipment_ref', '=', shipment_ref)], context=context)
                processed_in = None
                if not same_in:
                    # Check if the IN has not been manually processed (forced)
                    processed_in = self.search(cr, uid, [('id', '=', in_id), ('state', '=', 'done')], context=context)
                    if processed_in:
                        in_name = self.browse(cr, uid, in_id, context=context)['name']
                        message = "Unable to receive Shipment Details into an Incoming Shipment in this instance as IN %s (-%s-) already fully/partially cancelled/Closed" % (
                            in_name, po_name,
                        )
                        raise RunWithoutException(message)
                if not same_in and not processed_in:
                    message = "Sorry, this seems to be an extra ship. This feature is not available now!"
            else:
                same_in = self.search(cr, uid, [('id', '=', in_id)], context=context)
                message = "Sorry, this seems to be an extra ship. This feature is not available now!"
            if not same_in:
                self._logger.info(message)
                raise Exception(message)

            self.write(cr, uid, in_id, {'already_shipped': True, 'shipment_ref': shipment_ref}, context)
            in_name = self.browse(cr, uid, in_id, context=context)['name']
            message = "The INcoming " + in_name + "(" + po_name + ") has already been MANUALLY processed!"
            self._logger.info(message)
            return message

    def _manual_create_sync_picking_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        rule_obj = self.pool.get("sync.client.message_rule")
        rule_obj._manual_create_sync_message(cr, uid, self._name, res_id, return_info, rule_method, self._logger, context=context)


    def cancel_out_pick_cancel_in(self, cr, uid, source, out_info, context=None):
        '''
        ' USED ONLY FOR SLL MIG, to delete after
        ' Cancel the OUT/PICK at the supplier side cancels the corresponding IN at the project side
        '''
        if not context:
            context = {}
        self._logger.info("+++ Cancel the relevant IN at %s due to the cancel of OUT at supplier %s" % (cr.dbname, source))

        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        pick_dict = out_info.to_dict()

        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)

        if po_id:
            # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
            in_id = so_po_common.get_in_id_from_po_id(cr, uid, po_id, context)
            if in_id:
                # Cancel the IN object
                wf_service.trg_validate(uid, 'stock.picking', in_id, 'button_cancel', cr)

                name = self.browse(cr, uid, in_id, context).name
                message = "The IN " + name + " is canceled by sync as its partner " + out_info.name + " got canceled at " + source
                self._logger.info(message)
                return message
            else:
                # UTP-872: If there is no IN corresponding to the give OUT/SHIP/PICK, then check if the PO has any line
                # if it has no line, then no need to raise error, because PO without line does not generate any IN
                po = po_obj.browse(cr, uid, [po_id], context=context)[0]
                if len(po.order_line) == 0:
                    message = "The message is ignored as there is no corresponding IN (because the PO " + po.name + " has no line)"
                    self._logger.info(message)
                    return message

        elif context.get('restore_flag'):
            # UF-1830: Create a message to remove the invalid reference to the inexistent document
            shipment_ref = pick_dict['name']
            so_po_common.create_invalid_recovery_message(cr, uid, source, shipment_ref, context)
            return "Recovery: the reference to " + shipment_ref + " at " + source + " will be set to void."

        raise Exception("There is a problem (no PO or IN found) when cancel the IN at project")


    def closed_in_confirms_dpo_reception(self, cr, uid, source, out_info, context=None):
        """  deprecated """
        return True

    def closed_in_validates_delivery_out_ship(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        context['InShipOut'] = ""
        self._logger.info("+++ Closed INcoming at %s confirms the delivery of the relevant OUT/SHIP at %s" % (source, cr.dbname))

        so_po_common = self.pool.get('so.po.common')
        pick_dict = out_info.to_dict()

        shipment_ref = pick_dict.get('shipment_ref', False)
        in_name = pick_dict.get('name', False)
        if not shipment_ref or not in_name:
            raise Exception("The shipment reference is empty. The action cannot be executed.")

        ship_split = shipment_ref.split('.')
        if len(ship_split) != 2:
            message = "Invalid shipment reference format"
            self._logger.info(message)
            raise Exception(message)

        # Check if it an SHIP --_> call Shipment object to proceed the validation of delivery, otherwise, call OUT to validate the delivery!
        message = False
        out_doc_name = ship_split[1]
        if 'SHIP' in out_doc_name:
            shipment_obj = self.pool.get('shipment')
            ship_ids = shipment_obj.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'done')], context=context)

            if ship_ids:
                # set the Shipment to become delivered
                context['InShipOut'] = ""  # ask the PACK object not to log (model stock.picking), because it is logged in SHIP
                shipment_obj.set_delivered(cr, uid, ship_ids, context=context)
                message = "The shipment " + out_doc_name + " has been well delivered to its partner " + source + ": " + out_info.name
                shipment_obj.write(cr, uid, ship_ids, {'state': 'delivered',}, context=context) # trigger an on_change in SHIP
            else:
                ship_ids = shipment_obj.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'delivered')], context=context)
                if ship_ids:
                    message = "The shipment " + out_doc_name + " has been MANUALLY confirmed as delivered."
                elif context.get('restore_flag'):
                    # UF-1830: Create a message to remove the invalid reference to the inexistent document
                    so_po_common = self.pool.get('so.po.common')
                    so_po_common.create_invalid_recovery_message(cr, uid, source, in_name, context)
                    return "Recovery: the reference to " + in_name + " at " + source + " will be set to void."

        elif 'OUT' in out_doc_name:
            out_ids = self.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'done')], context=context)
            if out_ids:
                # set the Shipment to become delivered
                context['InShipOut'] = "OUT"  # asking OUT object to be logged (model stock.picking)
                self.set_delivered(cr, uid, out_ids, context=context)
                message = "The OUTcoming " + out_doc_name + " has been well delivered to its partner " + source + ": " + out_info.name
            else:
                out_ids = self.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'delivered')], context=context)
                if out_ids:
                    message = "The OUTcoming " + out_doc_name + " has been MANUALLY confirmed as delivered."
                elif context.get('restore_flag'):
                    # UF-1830: Create a message to remove the invalid reference to the inexistent document
                    so_po_common = self.pool.get('so.po.common')
                    so_po_common.create_invalid_recovery_message(cr, uid, source, in_name, context)
                    return "Recovery: the reference to " + in_name + " at " + source + " will be set to void."
        elif 'PICK' in out_doc_name:
            return "Msg ignored"

        if message:
            self._logger.info(message)
            return message

        message = "Something goes wrong with this message and no confirmation of delivery"

        # UF-1830: precise the error message for restore mode

        self._logger.info(message)
        raise Exception(message)

    # UF-1830: Added this message to update the IN reference to the OUT or SHIP
    def update_in_ref(self, cr, uid, source, values, context=None):
        self._logger.info("+++ Update the IN reference to OUT/SHIP document from %s to the PO %s"%(source, cr.dbname))
        if not context:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        shipment_ref = values.shipment_ref
        in_name = values.name
        message = False

        if not shipment_ref or not in_name:
            message = "The IN name or shipment reference is empty. The message cannot be executed."
        else:
            ship_split = shipment_ref.split('.')
            if len(ship_split) != 2:
                message = "Invalid shipment reference format. It must be in this format: instance.document"
        # if there is any problem, just stop here without doing anything further, ignore the message
        if message:
            self._logger.info(message)
            return message

        in_name = source + "." + in_name
        out_doc_name = ship_split[1]
        if 'SHIP' in out_doc_name:
            shipment_obj = self.pool.get('shipment')
            ids = shipment_obj.search(cr, uid, [('name', '=', out_doc_name)], context=context)

            if ids:
                # TODO: Add the IN ref into the existing one if the SHIP is for various POs!

                cr.execute('update shipment set in_ref=%s where id in %s', (in_name, tuple(ids)))
                message = "The shipment " + out_doc_name + " is now referred to " + in_name + " at " + source
            elif context.get('restore_flag'):
                # UF-1830: TODO: Create a message to remove the reference of the SO on the partner instance!!!!! to make sure that the SO does not link to a wrong PO in this instance
                so_po_common = self.pool.get('so.po.common')
                so_po_common.create_invalid_recovery_message(cr, uid, source, in_name, context)
                message = "Recovery: the reference to " + in_name + " at " + source + " will be set to void."
        elif 'OUT' in out_doc_name:
            ids = self.search(cr, uid, [('name', '=', out_doc_name)], context=context)
            if ids:
                # TODO: Add the IN ref into the existing one if the OUT is for various POs!

                cr.execute('update stock_picking set in_ref=%s where id in %s', (in_name, tuple(ids)))
                message = "The outcoming " + out_doc_name + " is now referred to " + in_name + " at " + source
            elif context.get('restore_flag'):
                # UF-1830: TODO: Create a message to remove the reference of the SO on the partner instance!!!!! to make sure that the SO does not link to a wrong PO in this instance
                so_po_common = self.pool.get('so.po.common')
                so_po_common.create_invalid_recovery_message(cr, uid, source, in_name, context)
                message = "Recovery: the reference to " + in_name + " at " + source + " will be set to void."

        if message:
            self._logger.info(message)
            return message

        message = "Something goes wrong with this message and no confirmation of delivery"
        self._logger.info(message)
        return message


    # US-838: Retrieve batch object, if not found then create new
    def retrieve_batch_number(self, cr, uid, product_id, batch_dict, context=None):
        if not context:
            context = {}
        #self._logger.info("+++ Retrieve batch number for the SHIP/OUT from %s")
        batch_obj = self.pool.get('stock.production.lot')

        if 'name' not in batch_dict or 'life_date' not in batch_dict:
            # Search for the batch object with the given data
            return False, "Batch Number: Missing batch name or expiry date!"

        existing_bn = batch_obj.search(cr, uid, [('name', '=', batch_dict['name']), ('product_id', '=', product_id),
                                                 ('life_date', '=', batch_dict['life_date'])], context=context)
        if existing_bn:  # existed already, then don't need to create a new one
            # Add comment through synchro
            if batch_dict.get('comment'):
                batch_obj.write(cr, uid, existing_bn[0], {'comment': batch_dict['comment']}, context=context)
            message = "Batch object exists in the current system. No new batch created."
            self._logger.info(message)
            return existing_bn[0], message

        # If not exists, then create this new batch object
        new_bn_vals = {
            'name': batch_dict['name'],
            'product_id': product_id,
            'life_date': batch_dict['life_date'],
            'comment': batch_dict.get('comment', False),  # Add comment through synchro
        }
        message = "The new BN " + batch_dict['name'] + " has been created"
        self._logger.info(message)
        bn_id = batch_obj.create(cr, uid, new_bn_vals, context=context)
        return bn_id, message

    def create_asset(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Create asset form that comes with the SHIP/OUT from %s" % source)
        asset_obj = self.pool.get('product.asset')

        asset_dict = out_info.to_dict()
        error_message = ""

        asset_dict['partner_name'] = source

        existing_asset = asset_obj.search(cr, uid, [('xmlid_name', '=', asset_dict['xmlid_name']), ('partner_name', '=', source)], context=context)
        if existing_asset:  # existed already, then don't need to create a new one
            message = "Create Asset: the given asset form exists already at local instance, no new asset will be created"
            self._logger.info(message)
            return message

        default_code = False
        if asset_dict.get('product_id', {}).get('default_code') and self.pool.get('so.po.common').get_partner_type(cr, uid, source, context) in ['section', 'intermission']:
            default_code = asset_dict['product_id']['default_code']

        if asset_dict.get('product_id'):
            rec_id = self.pool.get('so.po.common').get_product_id(cr, uid, out_info.product_id, default_code, context=context)
            if rec_id:
                asset_dict['product_id'] = rec_id
            else:
                error_message += "\n Invalid product reference for the asset. The asset cannot be created"

            if out_info.asset_type_id:
                rec_id = self.pool.get('product.asset.type').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.asset_type_id.id), context=context)
                if rec_id:
                    asset_dict['asset_type_id'] = rec_id
                else:
                    error_message += "\n Invalid asset type reference for the asset. The asset cannot be created"
            else:
                error_message += "\n Invalid asset type reference for the asset. The asset cannot be created"

            if out_info.invo_currency:
                rec_id = self.pool.get('res.currency').find_sd_ref(cr, uid, xmlid_to_sdref(out_info.invo_currency.id), context=context)
                if rec_id:
                    asset_dict['invo_currency'] = rec_id
                else:
                    error_message += "\n Invalid currency reference for the asset. The asset cannot be created"
            else:
                error_message += "\n Invalid currency reference for the asset. The asset cannot be created"
        else:
            error_message += "\n Invalid reference to product for the asset. The asset cannot be created"

        # If error message exists --> raise exception and no esset will be created
        if error_message:
            self._logger.info(error_message)
            raise Exception(error_message)
        asset_obj.create(cr, uid, asset_dict, context=context)
        message = "The new asset (" + asset_dict['name'] + ", " + source + ") has been created"
        self._logger.info(message)
        return message


    # UF-1617: Override the hook method to create sync messages manually for some extra objects once the OUT/Partial is done
    def _hook_create_sync_messages(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        so_po_common = self.pool.get('so.po.common')

        res = super(stock_picking, self)._hook_create_sync_messages(cr, uid, ids, context=context)
        for pick in self.browse(cr, uid, ids, context=context):
            partner = pick.partner_id
            if not partner or partner.partner_type == 'external':
                return True

            list_batch = []
            list_asset = []
            # only treat for the internal partner
            for move in pick.move_lines:
                if move.state not in ('done', 'cancel'):
                    continue
                # Get batch number object
                if move.prodlot_id:
                    # put the new batch number into the list, and create messages for them below
                    list_batch.append(move.prodlot_id.id)

                # Get asset object
                if move.asset_id:
                    # put the new batch number into the list, and create messages for them below
                    list_asset.append(move.asset_id.id)


            # for each new batch number object and for each partner, create messages and put into the queue for sending on next sync round
            # for each new asset object and for each partner, create messages and put into the queue for sending on next sync round
            for item in list_asset:
                so_po_common.create_message_with_object_and_partner(cr, uid, 1002, item, partner, context)
        return res

    def msg_create_invoice(self, cr, uid, source, stock_picking, context=None):
        """
        Create an invoice for a picking. This is used in the RW to CP rule for pickings
        that are in 'done' state and '2binvoiced' invoice_state so invoices are created
        at CP after synchronisation
        """
        # get stock pickings to process using name from message
        stock_picking_ids = self.search(cr, uid, [('name','=',stock_picking.name)])

        if stock_picking_ids:

            picking_obj = self.pool.get('stock.picking')
            picking = picking_obj.browse(cr, uid, stock_picking_ids[0])

            if picking.state == 'done' and picking.invoice_state == '2binvoiced':
                self._create_invoice(cr, uid, picking)
                return 'Invoice created for picking %s' % stock_picking.name
        else:
            return 'Picking %s state should be done and invoice_state should be 2binvoiced. Actual values were: %s and %s' \
                % (stock_picking.name, picking.state, picking.invoice_state)

    def on_create(self, cr, uid, id, values, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        logger = get_sale_purchase_logger(cr, uid, self, id, context=context)
        logger.action_type = 'creation'
        logger.is_product_added |= (len(values.get('move_lines', [])) > 0)

    def on_change(self, cr, uid, changes, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function') \
           or not (context.get('InShipOut', "") in ["IN", "OUT"]):  # log only for the 2 cases IN and OUT, not for SHIP
            return

        # monitor changes on purchase.order
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                                              context=context)
            logger.is_date_modified |= 'date' in changes
            logger.is_status_modified |= 'state' in changes or 'delivered' in changes
            logger.is_quantity_modified |= 'backorder_id' in changes
            logger.is_product_price_modified |= 'price_unit' in changes

    def action_invoice_create(self, cr, uid, ids, journal_id=False,
                              group=False, type='out_invoice', context=None):
        """
        If Remote Warehouse module is installed, only create supplier invoice at Central Platform
        """
        invoice_result = {}
        do_invoice = True

        # Handle purchase pickings only
        if type == 'in_invoice' and self.pool.get('sync_remote_warehouse.update_to_send'):
            # Are we setup as a central platform?
            rw_type = self._get_usb_entity_type(cr, uid)
            if rw_type == 'remote_warehouse':
                do_invoice = False

        if do_invoice:
            invoice_result = super(stock_picking, self).action_invoice_create(cr, uid, ids,
                                                                              journal_id=journal_id, group=group, type=type, context=context)
        return invoice_result

    def goods_expecting_picking_from_claim_creates_fo(self, cr, uid, source, stock_picking, context=None):
        '''
        Create a new FO and its lines to internal partner if the IN has '-replacement' or '-missing' in its name and
        its state is available
        '''
        if context is None:
            context = {}

        sale_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        partner_adress_obj = self.pool.get('res.partner.address')
        pricelist_obj = self.pool.get('product.pricelist')
        sp_com_obj = self.pool.get('so.po.common')
        distrib_obj = self.pool.get('analytic.distribution')

        po_info = stock_picking.purchase_id
        lines = stock_picking.move_lines
        partner_id = partner_obj.search(cr, uid, [('name', '=', source)], limit=1, context=context)[0]
        partner_type = partner_obj.read(cr, uid, partner_id, ['partner_type'], context=context)['partner_type']
        partner_address_id = partner_adress_obj.search(cr, uid, [('partner_id', '=', partner_id)], limit=1, context=context)[0]
        po_analytic_distrib = False
        if partner_type == 'internal':
            po_analytic_distrib = sp_com_obj.get_analytic_distribution_id(cr, uid, po_info.to_dict(), context)
        else:
            # set FO AD from orginal FO
            orig_fo_id = sale_obj.search(cr, uid, [('client_order_ref', '=', source + '.' + po_info.name)], limit=1, context=context)
            if orig_fo_id:
                orignal_so = sale_obj.browse(cr, uid, orig_fo_id[0], fields_to_fetch=['analytic_distribution_id'], context=context)
                if orignal_so.analytic_distribution_id:
                    po_analytic_distrib = distrib_obj.copy(cr, uid, orignal_so.analytic_distribution_id.id, {}, context=context)

        fo_data = {
            'client_order_ref': source + '.' + po_info.name,
            'delivery_requested_date': po_info.delivery_requested_date,
            'details': po_info.details,
            'note': po_info.notes,
            'categ': po_info.categ,
            'partner_id': partner_id,
            'partner_type': partner_type,
            'partner_order_id': partner_address_id,
            'partner_invoice_id': partner_address_id,
            'partner_shipping_id': partner_address_id,
            'order_type': po_info.order_type,
            'priority': po_info.priority,
            'loan_duration': po_info.loan_duration,
            'is_a_counterpart': po_info.is_a_counterpart,
            'stock_take_date': po_info.stock_take_date,
            'claim_name_goods_return': source + '.' + stock_picking.claim_name,
            'pricelist_id': pricelist_obj.search(cr, uid, [('name', '=', po_info.pricelist_id.name)], limit=1, context=context)[0],
            'analytic_distribution_id': po_analytic_distrib,
            'procurement_request': False,
        }

        fo_id = sale_obj.create(cr, uid, fo_data, context=context)
        fo_name = sale_obj.read(cr, uid, fo_id, ['name'], context=context)['name']

        # Create FO Lines
        for line in lines:
            if hasattr(line.product_id, 'id') and hasattr(line.product_id, 'default_code'):
                line_product = self.pool.get('so.po.common').get_product_id(cr, uid, line.product_id, line.product_id.default_code, context=context)
            else:
                line_product = product_obj.search(cr, uid, [('name', '=', line.product_id.name)], limit=1, context=context)[0]
            line_uom = uom_obj.search(cr, uid, [('name', '=', line.product_uom.name)], limit=1, context=context)
            # Search the analytic distribution of the original SO line
            original_sol_analytic_distrib_id = False
            original_sol_id = sol_obj.search(cr, uid, [('sync_linked_pol', '=', line.purchase_line_id.sync_local_id)],
                                             limit=1, context=context)
            if not original_sol_id and hasattr(line.purchase_line_id, 'original_line_id') and line.purchase_line_id.original_line_id and hasattr(line.purchase_line_id.original_line_id, 'sync_local_id') and line.purchase_line_id.original_line_id.sync_local_id:
                # try to retrieve the AD on the original line
                original_sol_id = sol_obj.search(cr, uid, [('sync_linked_pol', '=', line.purchase_line_id.original_line_id.sync_local_id)],
                                                 limit=1, context=context)
            if original_sol_id:
                current_analytic_distrib_id = sol_obj.browse(cr, uid, original_sol_id[0],
                                                             fields_to_fetch=['analytic_distribution_id'],
                                                             context=context).analytic_distribution_id.id
                original_sol_analytic_distrib_id = distrib_obj.copy(cr, uid, current_analytic_distrib_id, {}, context=context)


            else:
                original_sol_analytic_distrib_id = sp_com_obj.get_analytic_distribution_id(cr, uid, line.purchase_line_id.to_dict(), context)


            fo_line_data = {
                'order_id': fo_id,
                'name': line.name,
                'line_number': line.line_number,
                'product_id': line_product or False,
                'product_uom_qty': line.product_qty,
                'product_uom': line_uom[0] or False,
                'price_unit': line.price_unit,
                'order_partner_id': partner_id,
                'comment': line.comment,
                'in_name_goods_return': source + '.' + stock_picking.name,
                'date_planned': po_info.delivery_requested_date,
                'stock_take_date': po_info.stock_take_date,
                'analytic_distribution_id': original_sol_analytic_distrib_id,
                'sync_linked_pol': line.purchase_line_id.sync_local_id,
            }
            sol_obj.create(cr, uid, fo_line_data, context=context)

        message = _('IN %s processed to FO %s by Push Flow at %s.') % (stock_picking.name, fo_name, source)
        self._logger.info(message)

        return message

    def create_batch_number(self, *a, **b):
        """
        deprecated
        """
        return True

    def dpo_reception(self, cr, uid, source, sync_data, context=None):
        move_obj = self.pool.get('stock.move')
        purchase_line_obj = self.pool.get('purchase.order.line')
        curr_obj = self.pool.get('res.currency')

        data = sync_data.to_dict()
        remote_po_name = '%s.%s' % (source, data['purchase_id']['name'])


        location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')[1]
        stock_location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
        pick_data_header = {
            'physical_reception_date': data['physical_reception_date'],
            'reason_type_id': reason_type_id,
            'state': data['state'],
            'type': 'in',
            'purchase_id': False,
            'customers': source,
            'shipment_ref': '%s.%s' % (source, data['name']),
            'invoice_state': '2binvoiced',
            'sync_dpo_in': True,
        }

        currency_cache = {}
        move_lines_cancelled = {}
        out_data = {}
        po_currency_id = {}
        pick_data = {}
        for move_line in data.get('move_lines'):
            move_data = self.format_data(cr, uid, move_line, source, context=context)
            dpo_line_id = move_data['dpo_line_id']
            if not dpo_line_id:
                continue
            move_data['dpo_line_id'] = False
            move_data['sync_dpo'] = False
            move_data['purchase_line_id'] = dpo_line_id
            pol = purchase_line_obj.browse(cr, uid, dpo_line_id, fields_to_fetch=['order_id', 'sale_order_line_id', 'confirmation_date'], context=context)
            po = pol.order_id
            if po.order_type != 'direct':
                raise Exception('PO %s is not a DPO !' % (po.name,))
            if remote_po_name not in po.customer_ref:
                raise Exception('PO %s is not linked to %s !' % (po.name, remote_po_name))
            if po.po_version == 1:
                continue
            if po.id not in pick_data:
                pick_data[po.id] = pick_data_header.copy()
                pick_data[po.id]['move_lines'] = []
                pick_data[po.id]['purchase_id'] = po.id
                pick_data[po.id]['partner_id'] = po.partner_id.id
                pick_data[po.id]['partner_id2'] = po.partner_id.id
                pick_data[po.id]['address_id'] = po.partner_address_id.id
                pick_data[po.id]['origin'] = po.name
                po_currency_id[po.id] = po.pricelist_id.currency_id.id
            move_data['product_qty'] = move_data['quantity']
            del(move_data['quantity'])

            if move_data['state'] != 'cancel' and pol.sale_order_line_id:
                out_data.setdefault(pol.sale_order_line_id.order_id, []).append({'sol': pol.sale_order_line_id,  'product_qty': move_data['product_qty']})

            cur_sdref = move_line.get('price_currency_id', {}).get('id')
            if cur_sdref:
                if cur_sdref not in currency_cache:
                    currency_cache[cur_sdref] = curr_obj.find_sd_ref(cr, uid, xmlid_to_sdref(cur_sdref), context=context)
                move_data['price_currency_id'] = currency_cache.get(cur_sdref)
            if move_data.get('price_currency_id') and move_data['price_currency_id'] != po_currency_id[po.id] and move_line['price_unit']:
                ctx_fx = context.copy()
                if pol.confirmation_date:
                    ctx_fx['currency_date'] = pol.confirmation_date
                move_data['price_unit'] = curr_obj.compute(cr, uid, move_data['price_currency_id'], po_currency_id[po.id], move_line['price_unit'], round=False, context=ctx_fx)
                move_data['price_currency_id'] = po_currency_id[po.id]
            else:
                move_data['price_unit'] = move_line['price_unit']
            move_data['location_id'] = location_id
            move_data['location_dest_id'] = location_id
            move_data['reason_type_id'] = reason_type_id
            if move_data['state'] == 'cancel' and data['state'] != 'cancel':
                if po.id not in move_lines_cancelled:
                    move_lines_cancelled[po.id] = []
                # mix of cancelled and done moves in the same pick
                move_lines_cancelled[po.id].append(move_data)
            else:
                pick_data[po.id]['move_lines'].append((0, 0, move_data))
            move_data['state'] = 'assigned'

        if not pick_data:
            return "Ignored because old DPO flow no po found"

        msg_txt = []
        to_cancel = data['state'] == 'cancel'
        pick_to_done = []
        for po_id in pick_data:
            ctx_picking = context.copy()
            ctx_picking['keep_date'] = True
            pick_id = self.create(cr, uid, pick_data[po_id], context=ctx_picking)
            if to_cancel:
                self.action_cancel(cr, uid, [pick_id])
            else:
                pick_to_done.append(pick_id)
            pick_name = self.read(cr, uid, pick_id, ['name'], context=context)
            msg_txt.append('%s as %s state' % (pick_name['name'], data['state']))

        if not to_cancel:
            # create the OUT
            for so in out_data:
                out_pick_data = self.pool.get('sale.order')._get_picking_data(cr, uid, so, context=context, force_simple=True)
                out_pick_data['move_lines'] = []
                out_pick_data['dpo_out'] = True
                out_pick_data['new_dpo_out'] = True
                for move_out in out_data[so]:
                    out_move_data = self.pool.get('sale.order')._get_move_data(cr, uid, so, move_out['sol'], False, context=context)
                    out_move_data['location_id'] = stock_location_id
                    out_move_data['location_dest_id'] = stock_location_id
                    out_move_data['product_qty'] = move_out['product_qty']
                    out_move_data['product_uos_qty'] =  move_out['product_qty']
                    out_pick_data['move_lines'].append((0, 0, out_move_data))
                # do not touch locations on non stockable
                non_stock_ctx = context.copy()
                non_stock_ctx['non_stock_noupdate'] = True
                out_id = self.create(cr, uid, out_pick_data, context=non_stock_ctx)
                self.action_done(cr, uid, [out_id], context=context)
                self.set_delivered(cr, uid, [out_id], context=context)

        for po_id in move_lines_cancelled:
            for cancelled in move_lines_cancelled[po_id]:
                cancelled['picking_id'] = pick_id
                move_id = move_obj.create(cr, uid, cancelled, context=context)
                move_obj.action_cancel(cr, uid, move_id, context=context)

        for pick_id in pick_to_done:
            self.action_done(cr, uid, [pick_id])
        return "\n".join(msg_txt)

stock_picking()

class shipment(osv.osv):
    _inherit = "shipment"

    def on_change(self, cr, uid, changes, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                                              context=context)
            logger.is_status_modified = True

shipment()
