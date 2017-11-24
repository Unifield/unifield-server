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
        if data['asset_id'] and data['asset_id']['id']:
            asset_id = self.pool.get('product.asset').find_sd_ref(cr, uid, xmlid_to_sdref(data['asset_id']['id']), context=context)

        # uom
        uom_id = uom_obj.find_sd_ref(cr, uid, xmlid_to_sdref(data['product_uom']['id']), context=context)
        if not uom_id:
            raise Exception, "The corresponding uom does not exist here. Uom name: %s" % uom_id

        # UF-1617: Handle batch and asset object
        batch_id = False
        batch_values = data['prodlot_id']
        if batch_values and product_id:
            # us-838: WORK IN PROGRESS ..................................
            # US-838: check first if this product is EP-only? if yes, treat differently, here we treat only for BN 
            prodlot_obj = self.pool.get('stock.production.lot')
            prod = prod_obj.browse(cr, uid,product_id,context=context)

            '''
            US-838: The following block is for treating the sync message in pipeline!
            If the sync message was made with old message rule, then in the message it contains ONLY the xmlid of the batch, NO life_date.
            For this case, we have to retrieve the batch name from this xmlid, by using the double product_code in the search.
            From this batch name + product_id, we can find the batch object in the system. There should only be one batch name for the same product 
            since the migration has already done, which merged all dup batch name into one.

            The old sync message has the following xmlid format: sd.batch_numer_se_HQ1C1_DORADIDA15T_DORADIDA15T_MSFBN/000005
            '''
            xmlid = batch_values['id']
            if 'life_date' not in batch_values and 'batch_numer' in xmlid: # it must have the 'batch_numer' as prefix
                prod_code = "_" + prod.default_code + "_" + prod.default_code + "_" # This is how the old xmlid has been made: using double prod.default_code
                len_code = xmlid.find(prod_code)
                batch_name = 'batch_not_found'
                if len_code != -1:
                    indexOfProdCode = len_code  + len(prod_code)
                    batch_name = xmlid[indexOfProdCode:]
                else: # US-1449+1435, if the product code is not found in this batch number xmlid value, then try to find another way
                    bn_id = xmlid.rfind('_', 0, len(xmlid))
                    if bn_id != -1:
                        batch_name = xmlid[bn_id + 1:]

                existing_bn = prodlot_obj.search(cr, uid, [('name', '=', batch_name), ('product_id', '=', product_id)], context=context)
                if existing_bn:
                    batch_id = existing_bn[0]
            else:
                if prod.perishable and not prod.batch_management:
                    # In case it's a EP only product, then search for date and product, no need to search for batch name
                    if 'life_date' in batch_values:
                        # If name exists in the sync message, search by name and product, not by xmlid 
                        life_date = batch_values['life_date']
                        # US-838: use different way to retrieve the EP object
                        batch_id = prodlot_obj._get_prodlot_from_expiry_date(cr, uid, life_date, product_id, context=context)
                        if not batch_id:
                            raise Exception, "Error while retrieving or creating the expiry date %s for the product %s" % (batch_values, prod.name)
                else:
                    # US-838: for BN, retrieve it or create it, in the follwing method
                    batch_id, msg = self.retrieve_batch_number(cr, uid, product_id, batch_values, context) # return False if the batch object is not found, or cannot be created

            ################## TODO: Treat the case for Remote Warehouse: WORK IN PROGRESS BELOW!!!!!!!!!!

            if not batch_id:
                raise Exception, "Batch Number %s not found for this sync data record" % batch_values

        expired_date = data['expired_date']

        # UTP-872: Add also the state into the move line, but if it is done, then change it to assigned (available)
        state = data['state']
        if state == 'done':
            state = 'assigned'

        # UF-2301: Take care of DPO reception
        dpo_line_id = data.get('dpo_line_id', False)

        # build a dic which can be used directly to update the stock move
        result = {'line_number': data['line_number'],
                  'product_id': product_id,
                  'product_uom': uom_id,
                  'product_uos': uom_id,
                  'uom_id': uom_id,
                  'date': data['date'],
                  'date_expected': data['date_expected'],
                  'state': state,

                  'original_qty_partial': data['original_qty_partial'],  # UTP-972

                  'prodlot_id': batch_id,
                  'expired_date': expired_date,

                  'dpo_line_id': dpo_line_id,
                  'sync_dpo': dpo_line_id and True or False,

                  'asset_id': asset_id,
                  'change_reason': data['change_reason'] or None,
                  'name': data['name'],
                  'quantity': data['product_qty'] or 0.0,
                  'note': data['note'],
                  'comment': data.get('comment'),
                  'sale_line_id': data.get('sale_line_id', False) and data['sale_line_id'].get('id', False) or False,
                  }
        return result

    def package_data_update_in(self, cr, uid, source, out_info, context=None):
        '''
        package the data to get info concerning already processed or not
        '''
        result = {}
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


        return result

    def picking_data_update_in(self, cr, uid, source, out_info, context=None):
        '''
        If data come from a stock move (DPO), re-arrange data to match with partial_shipped_fo_updates_in_po method
        '''
        result = {}

        for key in out_info.keys():
            if key != 'move_lines':
                result[key] = out_info.get(key)

        if out_info.get('subtype', False) in ('standard', 'picking') and out_info.get('move_lines', False):
            for line in out_info['move_lines']:
                # Don't get the lines without dpo_line_id
                if line.get('dpo_line_id', False):
                    result.setdefault('move_lines', [])
                    result['move_lines'].append(line)

        return result

    def partial_shippped_dpo_updates_in_po(self, cr, uid, source, out_info, context=None):
        if context is None:
            context = {}

        context.update({'for_dpo': True})
        return self.partial_shipped_fo_updates_in_po(cr, uid, source, out_info, context=context)


    # US-1294: Add the shipped amount into the move lines
    def _add_to_shipped_moves(self, already_shipped_moves, move_id, quantity):
        found = False
        for elem in already_shipped_moves:
            if move_id in elem:
                # If the move line exists, then add the new shipped amount into line
                elem[move_id] += quantity
                found = True
                break

        if not found:
            already_shipped_moves.append({move_id: quantity})

    def partial_shipped_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        '''
        ' This sync method is used for updating the IN of Project side when the OUT/PICK at Coordo side became done.
        ' In partial shipment/OUT, when the last shipment/OUT is made, the original IN will become Available Shipped, no new IN will
        ' be created, as the whole quantiy of the IN is delivered (but not yet received at Project side)
        '''
        move_proc = self.pool.get('stock.move.in.processor')
        if context is None:
            context = {}
        self._logger.info("+++ Call to update partial shipment/OUT from supplier %s to INcoming Shipment of PO at %s" % (source, cr.dbname))
        context['InShipOut'] = ""

        # Load common data (mainly for reason type) into context
        fake_ids = self.search(cr, uid, [], order='NO_ORDER')
        self.pool.get('data.tools').load_common_data(cr, uid, fake_ids, context=context)

        if not isinstance(out_info, dict):
            pick_dict = out_info.to_dict()
        else:
            pick_dict = out_info

        if context.get('for_dpo'):
            pick_dict = self.picking_data_update_in(cr, uid, source, pick_dict, context=context)
            #US-1352: Reset this flag immediately, otherwise it will impact on other normal shipments!
            context.update({'for_dpo': False})

        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        warehouse_obj = self.pool.get('stock.warehouse')

        # package data
        pack_data = self.package_data_update_in(cr, uid, source, pick_dict, context=context)
        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + pick_dict['origin']
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        # prepare the shipment/OUT reference to update to IN
        shipment = pick_dict.get('shipment_id', False)
        if shipment:
            shipment_ref = shipment['name'] # shipment made
        else:
            #UFTP-332: Check if name is really an OUT, because DPO could have PICk but no SHIP nor OUT --> do not link this PICK to IN
            shipment_ref = pick_dict.get('name', False) # the case of OUT
            if shipment_ref and 'OUT' not in shipment_ref:
                shipment_ref = False
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
                if move_line['sale_line_id']['in_name_goods_return']:
                    in_name_goods_return = move_line['sale_line_id']['in_name_goods_return'].split(".")[-1]
            if in_name_goods_return:
                # search for the right IN in case of synchro of multiple missing/replacement IN
                in_id = self.pool.get('stock.picking')\
                    .search(cr, uid, [('name', '=', in_name_goods_return), ('purchase_id', '=', po_id), ('state', '=', 'assigned')], limit=1, context=context)[0]
            else:
                # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
                in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po_name, ['assigned'], context)
        else:
            # locations
            warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
            location_input_id = warehouse_obj.read(cr, uid, warehouse_ids, ['lot_input_id'])[0]['lot_input_id'][0]
            location_output_id = warehouse_obj.read(cr, uid, warehouse_ids, ['lot_stock_id'])[0]['lot_stock_id'][0]

            in_claim_dict = {
                'claim': pick_dict.get('claim', False),
                'min_date': pick_dict.get('min_date', False),
                'note': pick_dict.get('note', False),
                'partner_id': self.pool.get('res.partner').search(cr, uid, [('name', '=', source)], context=context)[0],
                'origin': pick_dict.get('origin', False),
                'partner_type_stock_picking': pick_dict.get('partner_type_stock_picking', False),
                'reason_type_id': context['common']['rt_goods_return'],
                'type': 'in',
                'subtype': 'standard',
                'shipment_ref': shipment_ref,
                'move_lines': [(0, 0, {
                    'change_reason': x.get('change_reason', False),
                    'comment': x.get('comment', False),
                    'date': x.get('date', False),
                    'date_expected': x.get('date_expected', False),
                    'expired_date': x.get('expired_date', False),
                    'line_number': x.get('line_number', False),
                    'name': x.get('name', False),
                    'note': x.get('note', False),
                    'original_qty_partial': x.get('original_qty_partial', False),
                    'product_id': product_obj.search(cr, uid, [('name', '=', x.get('product_id', False)['name'])],
                                                     limit=1, context=context)[0],
                    'product_qty': x.get('product_qty', False),
                    'product_uom': uom_obj.search(cr, uid, [('name', '=', x.get('product_uom', False)['name'])],
                                                  limit=1, context=context)[0],
                    'reason_type_id': context['common']['rt_goods_return'],
                    'location_id': location_output_id,
                    'location_dest_id': location_input_id,
                }) for x in pick_dict.get('move_lines', False)]
            }

            in_id = self.create(cr, uid, in_claim_dict, context=context)

        if in_id:
            in_name = self.read(cr, uid, in_id, ['name'], context=context)['name']
            in_processor = self.pool.get('stock.incoming.processor').create(cr, uid, {'picking_id': in_id}, context=context)
            self.pool.get('stock.incoming.processor').create_lines(cr, uid, in_processor, context=context)
            partial_datas = {}
            partial_datas[in_id] = {}
            context['InShipOut'] = "IN"  # asking the IN object to be logged
            already_set_moves = []
            for line in pack_data:
                line_data = pack_data[line]

                #US-1294: Keep this list of pair (move_line: shipped_qty) as amount already shipped
                already_shipped_moves = []
                # get the corresponding picking line ids
                for data in line_data['data']:
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

                    search_move = [('id', 'not in', already_set_moves), ('picking_id', '=', in_id), ('line_number', '=', data.get('line_number'))]

                    original_qty_partial = data.get('original_qty_partial')
                    orig_qty = data.get('quantity')
                    if original_qty_partial != -1:
                        search_move.append(('product_qty', '=', original_qty_partial))
                        orig_qty = original_qty_partial

                    move_ids = move_obj.search(cr, uid, search_move, context=context)
                    if not move_ids:
                        #US-1294: Reduce the search condition
                        del search_move[0]
                        move_ids = move_obj.search(cr, uid, search_move, context=context)

                    #US-1294: If there is only one move line found, must check if this has already all taken in shipped moves list
                    if move_ids and len(move_ids) == 1:  # if there is only one move, take it for process
                        move = move_obj.read(cr, uid, move_ids[0], ['product_qty'], context=context)
                        for elem in already_shipped_moves:
                            # If this move has already all shipped, do not take it anymore
                            if move['id'] in elem and move['product_qty'] == elem[move['id']]:
                                move_ids = False # search again
                                break

                    if not move_ids and original_qty_partial != -1:
                        #US-1294: Reduce the search condition
                        search_move = [('picking_id', '=', in_id), ('line_number', '=', data.get('line_number')), ('original_qty_partial', '=', original_qty_partial)]
                        move_ids = move_obj.search(cr, uid, search_move, context=context)

                    #US-1294: But still no move line with exact qty as the amount shipped 
                    if not move_ids:
                        #US-1294: Now search all moves of the given IN and line number
                        search_move = [('picking_id', '=', in_id), ('line_number', '=', data.get('line_number'))]
                        move_ids = move_obj.search(cr, uid, search_move, order='product_qty ASC', context=context)
                        if not move_ids:
                            # SLL edit, if move cannot be found, then use sync_linked_sol to find it:
                            sol_id = data.get('sale_line_id', False) and int(data['sale_line_id'].split('/')[-1]) or False
                            if sol_id:
                                pol_id = self.pool.get('purchase.order.line').search(cr, uid, [('sync_linked_sol', 'ilike', '%%/%s' % sol_id)], context=context)
                                if pol_id:
                                    move_ids = move_obj.search(cr, uid, [('purchase_line_id', 'in', pol_id)], context=context)
                        if not move_ids:
                            #US-1294: absolutely no moves -> probably they are closed, just show the error message then ignore
                            closed_in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po_name, ['done', 'cancel'], context)
                            if closed_in_id:
                                search_move = [('picking_id', '=', closed_in_id), ('line_number', '=', data.get('line_number'))]
                                move_ids = move_obj.search(cr, uid, search_move, context=context)
                            if not move_ids:
                                message = "Line number " + str(ln) + " is not found in the original IN or PO"
                                self._logger.info(message)
                                raise Exception(message)
                            else:
                                message = "Unable to receive Shipment Details into an Incoming Shipment in this instance as IN %s (%s) already fully/partially cancelled/Closed" % (
                                    in_name, po_name,
                                )
                                self._logger.info(message)
                                raise Exception(message)

                    move_id = False # REF-99: declare the variable before using it, otherwise if it go to else, then line 268 "if not move_id" -> problem!
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
                                for elem in already_shipped_moves:
                                    if move['id'] in elem:
                                        # taken into account the amount already shipped previously
                                        diff -= elem[move['id']]
                                        break

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
                    #US-1294: Add this move and quantity as already shipped, since it's added to the wizard for processing
                    self._add_to_shipped_moves(already_shipped_moves, move_id, data['quantity'])

            # for the last Shipment of an FO, no new INcoming shipment will be created --> same value as in_id
            new_picking = self.do_incoming_shipment(cr, uid, in_processor, context)

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
                message = "The INcoming " + in_name + "(" + po_name + ") is now become shipped available!"
            else:
                message = "The INcoming " + in_name + "(no PO) is now become shipped available!"
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
                        message = "Unable to receive Shipment Details into an Incoming Shipment in this instance as IN %s (%s) already fully/partially cancelled/Closed" % (
                            in_name, po_name,
                        )
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

    # REMOVE THIS METHOD, NO MORE USE! do_incoming_shipment_sync

    def cancel_out_pick_cancel_in(self, cr, uid, source, out_info, context=None):
        '''
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

    def cancel_stock_move_of_pick_cancel_in(self, cr, uid, source, out_info, context=None):
        '''
        ' UTP-872: Cancel only a few move lines of a closed PICK ticket in Coordo will also need to cancel the relevant lines at the IN
        '''
        if not context:
            context = {}
        self._logger.info("+++ Cancel the relevant IN at %s due to the cancel of some specific move of the Pick ticket at supplier %s" % (cr.dbname, source))

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
                # Cancel the IN object to have all lines cancelled, but the IN object remained as closed, so the update of state is done right after
                incoming = self.pool.get('stock.picking').browse(cr, uid, in_id, context=context)
                self.pool.get('stock.move').action_cancel(cr, uid, [move.id for move in incoming.move_lines], context=context)
                self.write(cr, uid, in_id, {'state': 'done'}, context) # UTP-872: reset state of the IN to become closed

                name = self.browse(cr, uid, in_id, context).name
                message = "The IN " + name + " is canceled by sync as its partner " + out_info.name + " got canceled at " + source
                self._logger.info(message)
                return message
            else:
                po = po_obj.browse(cr, uid, [po_id], context=context)[0]
                if po.fo_sync_date > pick_dict['date_cancel']:
                    message = "The message is ignored as the stock move has been canceled before update of the PO"
                    self._logger.info(message)
                    return message

                if len(po.order_line) == 0:
                    message = "The message is ignored as there is no corresponding IN (because the PO " + po.name + " has no line)"
                    self._logger.info(message)
                    return message

                # UTP-872: If there is no IN corresponding to the give OUT/SHIP/PICK, then check if the PO has any line
                # if it has no line, then no need to raise error, because PO without line does not generate any IN
                # still try to check whether this IN has already been manually processed
                in_id = so_po_common.get_in_id_by_state(cr, uid, po_id, po.name, ['done'], context)
                if in_id:
                    message = "The IN linked to " + po.name + " has been closed already, this message is thus ignored!"
                    self._logger.info(message)
                    return message
        elif context.get('restore_flag'):
            # UF-1830: Create a message to remove the invalid reference to the inexistent document
            so_po_common = self.pool.get('so.po.common')
            shipment_ref = pick_dict['name']
            so_po_common.create_invalid_recovery_message(cr, uid, source, shipment_ref, context)
            return "Recovery: the reference to " + shipment_ref + " at " + source + " will be set to void."

        raise Exception("There is a problem (no PO or IN found) when cancel the IN at project")


    def closed_in_confirms_dpo_reception(self, cr, uid, source, out_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Closed INcoming at %s confirms the delivery to DPO at %s" % (source, cr.dbname))

        wf_service = netsvc.LocalService("workflow")
        pick_dict = out_info.to_dict()

        dpo_line_id = pick_dict.get('dpo_line_id', False)
        if not dpo_line_id:
            raise Exception("The DPO line reference is empty. The action cannot be executed.")

        message = False
        self.pool.get('purchase.order.line').write(cr, uid, [dpo_line_id], {'dpo_received': True}, context=context)
        po_id = self.pool.get('purchase.order.line').browse(cr, uid, dpo_line_id, context=context).order_id

        if po_id and all(l.dpo_received for l in po_id.order_line):
            wf_service.trg_validate(uid, 'purchase.order', po_id.id, 'dpo_received', cr)
            message = "The reception of the DPO " + po_id.name + " has been confirmed"
        elif po_id:
            message = "The DPO " + po_id.name + " hasn't been confirmed because some goods remain to receive"


        if message:
            self._logger.info(message)
            return message

        message = "Something goes wrong with this message and no confirmation of reception of the DPO %s" % (po_id and po_id.name or '')
        self._logger.info(message)
        raise Exception(message)

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
            ship_ids = self.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'done')], context=context)
            if ship_ids:
                # set the Shipment to become delivered
                context['InShipOut'] = "OUT"  # asking OUT object to be logged (model stock.picking)
                self.set_delivered(cr, uid, ship_ids, context=context)
                message = "The OUTcoming " + out_doc_name + " has been well delivered to its partner " + source + ": " + out_info.name
            else:
                ship_ids = self.search(cr, uid, [('name', '=', out_doc_name), ('state', '=', 'delivered')], context=context)
                if ship_ids:
                    message = "The OUTcoming " + out_doc_name + " has been MANUALLY confirmed as delivered."
                elif context.get('restore_flag'):
                    # UF-1830: Create a message to remove the invalid reference to the inexistent document
                    so_po_common = self.pool.get('so.po.common')
                    so_po_common.create_invalid_recovery_message(cr, uid, source, in_name, context)
                    return "Recovery: the reference to " + in_name + " at " + source + " will be set to void."
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

        if not ('name' in batch_dict and 'life_date' in batch_dict):
            # Search for the batch object with the given data
            return False, "Batch Number: Missing batch name or expiry date!"

        existing_bn = batch_obj.search(cr, uid, [('name', '=', batch_dict['name']), ('product_id', '=', product_id),
                                                 ('life_date', '=', batch_dict['life_date'])], context=context)
        if existing_bn:  # existed already, then don't need to create a new one
            message = "Batch object exists in the current system. No new batch created."
            self._logger.info(message)
            return existing_bn[0], message

        # If not exists, then create this new batch object
        new_bn_vals = {'name': batch_dict['name'], 'product_id': product_id, 'life_date': batch_dict['life_date']}
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

    def check_valid_to_generate_message(self, cr, uid, ids, rule, context):
        # Check if the given object is valid for the rule
        model_obj = self.pool.get(rule.model)
        domain = rule.domain and eval(rule.domain) or []
        domain.insert(0, '&')
        domain.append(('id', '=', ids[0]))  # add also this id to short-list only the given object
        return model_obj.search(cr, uid, domain, context=context)

    def create_manual_message(self, cr, uid, ids, context):
        rule_obj = self.pool.get("sync.client.message_rule")

        ##############################################################################
        # Define the message rule to be fixed, or by given a name for it
        #
        ##############################################################################
        rule = rule_obj.get_rule_by_sequence(cr, uid, 1000, context)

        if not rule or not ids or not ids[0]:
            return

        valid_ids = self.check_valid_to_generate_message(cr, uid, ids, rule, context)
        if not valid_ids:
            return  # the current object is not valid for creating message
        valid_id = valid_ids[0]

        model_obj = self.pool.get(rule.model)
        msg_to_send_obj = self.pool.get("sync.client.message_to_send")

        update_destinations = model_obj.get_destination_name(cr, uid, ids, rule.destination_name, context=context)
        arg = model_obj.get_message_arguments(cr, uid, ids[0], rule, context=context)
        call = rule.remote_call

        identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, rule.model, ids, rule.server_id, context=context)
        if not identifiers or not update_destinations:
            return

        xml_id = identifiers[valid_id]
        existing_message_id = msg_to_send_obj.search(cr, uid, [('identifier', '=', xml_id)], context=context)
        if not existing_message_id:  # if similar message does not exist in the system, then do nothing
            return

        # make a change on the message only now
        msg_to_send_obj.modify_manual_message(cr, uid, existing_message_id, xml_id, call, arg, update_destinations.values()[0], context)


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

    def msg_close(self, cr, uid, source, stock_picking, context=None):
        """
        Trigger a close on a stock.stock_picking
        """
        # get stock pickings to process using name from message
        stock_picking_ids = self.search(cr, uid, [('name', '=', stock_picking.name)])

        if stock_picking_ids:
            # create stock.partial.picking wizard object to perform the close
            partial_obj = self.pool.get("stock.partial.picking")
            partial_id = partial_obj.create(cr, uid, {}, context=dict(context, active_ids=stock_picking_ids))

            if self.pool.get('stock.picking').browse(cr, uid, stock_picking_ids[0]).state == 'done':
                return 'Stock picking %s was already closed' % stock_picking.name

            # set quantity to process on lines
            partial_obj.copy_all(cr, uid, [partial_id], context=dict(context, model='stock.partial.picking'))

            # process partial and return
            try:
                partial_obj.do_partial(cr, uid, partial_id, context=dict(context, active_ids=stock_picking_ids))
            except KeyError:
                raise ValueError('Please set a batch number on all move lines')

            return 'Stock picking %s closed' % stock_picking.name
        else:
            return 'Could not find stock picking %s' % stock_picking.name

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

        # create a useful mapping purchase.order ->
        #    dict_of_stock.move_changes
        lines = {}
        if 'stock.move' in context['changes']:
            for rec_line in self.pool.get('stock.move').browse(
                    cr, uid,
                    context['changes']['stock.move'].keys(),
                    context=context):
                if self.pool.get('stock.move').exists(cr, uid, rec_line.id, context):  # check the line exists
                    lines.setdefault(rec_line.picking_id.id, {})[rec_line.id] = context['changes']['stock.move'][rec_line.id]
        # monitor changes on purchase.order
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                                              context=context)
            if 'move_lines' in changes:
                old_lines, new_lines = map(set, changes['move_lines'])
                logger.is_product_added |= (len(new_lines - old_lines) > 0)
                logger.is_product_removed |= (len(old_lines - new_lines) > 0)
            logger.is_date_modified |= ('date' in changes)
            logger.is_status_modified |= ('state' in changes) | ('delivered' in changes)
            # handle line's changes
            for line_id, line_changes in lines.get(id, {}).items():
                logger.is_quantity_modified |= ('product_qty' in line_changes)

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

        po_info = stock_picking.purchase_id
        lines = stock_picking.move_lines
        partner_id = partner_obj.search(cr, uid, [('name', '=', source)], limit=1, context=context)[0]
        partner_type = partner_obj.read(cr, uid, partner_id, ['partner_type'], context=context)['partner_type']
        partner_address_id = partner_adress_obj.search(cr, uid, [('partner_id', '=', partner_id)], limit=1, context=context)[0]
        po_analytic_distrib = sp_com_obj.get_analytic_distribution_id(cr, uid, po_info.to_dict(), context)

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
        }

        fo_id = sale_obj.create(cr, uid, fo_data, context=context)
        fo_name = sale_obj.read(cr, uid, fo_id, ['name'], context=context)['name']

        # Create FO Lines
        for line in lines:
            line_product = product_obj.search(cr, uid, [('name', '=', line.product_id.name)], limit=1, context=context)
            line_uom = uom_obj.search(cr, uid, [('name', '=', line.product_uom.name)], limit=1, context=context)
            # Search the analytic distribution of the original SO line
            original_sol_analytic_distrib_id = False
            original_sol_id = sol_obj.search(cr, uid, [('sync_linked_pol', '=', line.purchase_line_id.sync_local_id)],
                                             limit=1, context=context)
            if len(original_sol_id) > 0:
                original_sol_analytic_distrib_id = sol_obj.browse(cr, uid, original_sol_id[0],
                                                                  fields_to_fetch=['analytic_distribution_id'],
                                                                  context=context).analytic_distribution_id.id
            fo_line_data = {
                'order_id': fo_id,
                'name': line.name,
                'line_number': line.line_number,
                'product_id': line_product[0] or False,
                'product_uom_qty': line.product_qty,
                'product_uom': line_uom[0] or False,
                'price_unit': line.price_unit,
                'order_partner_id': partner_id,
                'comment': line.comment,
                'in_name_goods_return': source + '.' + stock_picking.name,
                'date_planned': po_info.delivery_requested_date,
                'stock_take_date': po_info.stock_take_date,
                'analytic_distribution_id': original_sol_analytic_distrib_id or po_analytic_distrib or False,
            }
            sol_obj.create(cr, uid, fo_line_data, context=context)

        message = _('IN %s processed to FO %s by Push Flow at %s.' % (stock_picking.name, fo_name, source))
        self._logger.info(message)

        return message

    def create_batch_number(self, *a, **b):
        """
        deprecated
        """
        return True


stock_picking()

class shipment(osv.osv):
    _inherit = "shipment"

    def on_change(self, cr, uid, changes, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        # create a useful mapping purchase.order ->
        #    dict_of_stock.move_changes
        lines = {}
        if 'shipment' in context['changes']:
            for rec_line in self.pool.get('shipment').browse(
                    cr, uid,
                    context['changes']['shipment'].keys(),
                    context=context):
                lines.setdefault(rec_line.id, {})[rec_line.id] = \
                    context['changes']['shipment'][rec_line.id]
        # monitor changes on purchase.order
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                                              context=context)
            logger.is_status_modified |= True

shipment()
