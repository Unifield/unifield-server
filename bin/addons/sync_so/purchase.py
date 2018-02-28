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
from tools.translate import _

from sync_client import get_sale_purchase_logger


class purchase_order_line_sync(osv.osv):
    _inherit = 'purchase.order.line'

    def _get_sync_local_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['order_id'], context=context):
            ret[pol['id']] = '%s/%s' % (pol['order_id'][1], pol['id'])
        return ret

    def _has_pol_been_synched(self, cr, uid, ids, field_name, args, context=None):
        '''
        has the given PO line been already synchronized ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.partner_id.partner_type not in ['internal','section','intermission']:
                res[pol.id] = False
            elif pol.state == 'draft':
                res[pol.id] = False
            elif pol.state.startswith('validated'):
                pol_identifier = self.get_sd_ref(cr, uid, pol.id, context=context)
                sent_ok = self.pool.get('sync.client.message_to_send').search_exist(cr, uid, [
                    ('sent', '=', True),
                    ('remote_call', '=', 'sale.order.line.create_so_line'),
                    ('identifier', 'like', pol_identifier),
                ], context=context)
                res[pol.id] = sent_ok or pol.order_id.push_fo
            else:
                res[pol.id] = True

        return res


    _columns = {
        'original_purchase_line_id': fields.text(string='Original purchase line id'),
        'dest_partner_id': fields.related('order_id', 'dest_partner_id', string='Destination partner', readonly=True, type='many2one', relation='res.partner', store=True),
        'sync_linked_sol': fields.char(size=256, string='Linked sale order line at synchro'),
        'sync_local_id': fields.function(_get_sync_local_id, type='char', method=True, string='ID', help='for internal use only'),
        'has_pol_been_synched': fields.function(_has_pol_been_synched, type='boolean', method=True, string='Synched ?'),
    }


    def sol_update_original_pol(self, cr, uid, source, sol_info, context=None):
        '''
        Update original PO lines from remote SO lines
        '''
        if context is None:
            context = {}
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        sol_dict = sol_info.to_dict()

        po_ids = []
        # search for the parent purchase.order:
        if sol_dict['in_name_goods_return']:
            # FO claim updated, update orignal PO
            in_name = sol_dict['in_name_goods_return'].split('.')
            in_name.pop(0)
            in_name = '.'.join(in_name)
            pick_id = pick_obj.search(cr, uid, [('name', '=', in_name)], context=context)
            if pick_id:
                po_id = pick_obj.read(cr, uid, pick_id[0], ['purchase_id'], context=context)['purchase_id'][0]
                if po_id:
                    po_ids = [po_id]
        else:
            partner_ref = '%s.%s' % (source, sol_dict['order_id']['name'])
            po_ids = self.pool.get('purchase.order').search(cr, uid, [('partner_ref', '=', partner_ref)], context=context)
        if not po_ids:
            # If FO was split during SLL migration the PO is not split
            if partner_ref[-2] == '-' and partner_ref[-1] in ['1', '2', '3']:
                po_ids = self.pool.get('purchase.order').search(cr, uid, [('partner_ref', '=', partner_ref[:-2]), ('split_during_sll_mig', '=', True)], context=context)

        if not po_ids:
            raise Exception, "Cannot find the parent PO with partner ref %s" % partner_ref

        # retrieve data:
        pol_values = self.pool.get('so.po.common').get_line_data(cr, uid, source, sol_info, context)
        order_name = sol_dict['order_id']['name']
        pol_values['order_id'] = po_ids[0]
        pol_values['sync_linked_sol'] = sol_dict['sync_local_id']
        pol_values['modification_comment'] = sol_dict.get('modification_comment', False)
        if 'line_number' in pol_values:
            del(pol_values['line_number'])

        # the current line has been resourced in other instance, so we set it as "sourced_n" in current instance PO in order to
        # create the resourced line in current instance IR:
        if sol_dict.get('resourced_original_line'):
            if sol_dict.get('resourced_original_remote_line'):
                pol_values['resourced_original_line'] = int(sol_dict['resourced_original_remote_line'].split('/')[-1])
                # link our resourced PO line with corresponding resourced FO line:
                if pol_values['resourced_original_line']:
                    orig_po_line = self.browse(cr, uid, pol_values['resourced_original_line'], fields_to_fetch=['linked_sol_id'], context=context)
                    if orig_po_line.linked_sol_id:
                        resourced_sol_id = self.pool.get('sale.order.line').search(cr, uid, [('resourced_original_line', '=', orig_po_line.linked_sol_id.id)], context=context)
                        if resourced_sol_id:
                            pol_values['linked_sol_id'] = resourced_sol_id[0]
                            self.pool.get('sale.order.line').write(cr, uid, resourced_sol_id, {'set_as_sourced_n': True}, context=context)
            elif sol_dict.get('original_line_id') and not sol_dict.get('is_line_split'):
                orig_line_ids = self.search(cr, uid, [
                    ('order_id', '=', pol_values['order_id']),
                    ('sync_linked_sol', 'ilike', '%%%s' % sol_dict['original_line_id']['id'].split('/')[-1])
                ], context=context)
                if orig_line_ids:
                    orig_line = self.browse(cr, uid, orig_line_ids[0], context=context)
                    pol_values['link_so_id'] = orig_line.link_so_id.id
                    self.pool.get('purchase.order.line').write(cr, uid, orig_line_ids, {'block_resourced_line_creation': True}, context=context)

        # search the PO line to update:
        pol_id = self.search(cr, uid, [('sync_linked_sol', '=', sol_dict['sync_local_id'])], limit=1, context=context)
        if not pol_id and sol_dict.get('sync_linked_pol'):
            pol_id_msg = sol_dict['sync_linked_pol'].split('/')[-1]
            pol_id = self.search(cr, uid, [('order_id', '=', pol_values['order_id']), ('id', '=', int(pol_id_msg))], context=context)

        # update PO line:
        kind = ""
        pol_updated = False
        if not pol_id: # then create new PO line
            kind = 'new line'
            pol_values['line_number'] = sol_dict['line_number']
            if sol_dict['is_line_split']:
                sync_linked_sol = int(sol_dict['original_line_id'].get('id').split('/')[-1]) if sol_dict['original_line_id'] else False
                if not sync_linked_sol:
                    raise Exception, "Original PO line not found when trying to split the PO line"
                sync_linked_sol = '%s/%s' % (order_name, sync_linked_sol)
                orig_pol = self.search(cr, uid, [('sync_linked_sol', '=', sync_linked_sol)], context=context)
                if not orig_pol:
                    raise Exception, "Original PO line not found when trying to split the PO line"
                orig_pol_info = self.browse(cr, uid, orig_pol[0], fields_to_fetch=['linked_sol_id', 'line_number', 'origin', 'state'], context=context)
                pol_values['original_line_id'] = orig_pol[0]
                pol_values['line_number'] = orig_pol_info.line_number
                if orig_pol_info.linked_sol_id:
                    pol_values['origin'] = orig_pol_info.origin
            if sol_dict['in_name_goods_return'] and not sol_dict['is_line_split']:
                # in case of FO from missing/replacement claim
                pol_values['origin'] = self.pool.get('purchase.order').browse(cr, uid, po_ids[0], context=context).origin
                pol_values['from_synchro_return_goods'] = True
            # case of PO line doesn't exists, so created in FO (COO) and pushed back in PO (PROJ)
            # so we have to create this new PO line:
            pol_values['set_as_sourced_n'] = True if not sol_dict.get('resourced_original_line') else False
            new_pol = self.create(cr, uid, pol_values, context=context)

            # if original pol has already been confirmed (and so has linked IN moves), then we re-attach moves to the right new split pol:
            if sol_dict['is_line_split']:
                linked_in_moves = self.pool.get('stock.move').search(cr, uid, [('purchase_line_id', '=', orig_pol[0]), ('type', '=', 'in')], context=context)
                if len(linked_in_moves) > 1:
                    for in_move in self.pool.get('stock.move').browse(cr, uid, linked_in_moves, context=context):
                        if in_move.state in ('assigned', 'confirmed') and pol_values['product_qty'] == in_move.product_qty:
                            self.pool.get('stock.move').write(cr, uid, [in_move.id], {'purchase_line_id': new_pol}, context=context)

            if sol_dict['in_name_goods_return'] and not sol_dict['is_line_split']:  # update the stock moves PO line id
                in_name = sol_dict['in_name_goods_return'].split('.')[-1]
                pick_id = pick_obj.search(cr, uid, [('name', '=', in_name)], limit=1, context=context)[0]
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', pick_id),
                                                     ('line_number', '=', pol_values['line_number'])], context=context)
                move_obj.write(cr, uid, move_ids, ({'purchase_line_id': new_pol}), context=context)

            pol_updated = new_pol
        else: # regular update
            pol_updated = pol_id[0]
            kind = 'update'
            pol_to_update = [pol_updated]
            confirmed_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, [], 'confirmed', context=context)
            po_line = self.browse(cr, uid, pol_updated, fields_to_fetch=['state'], context=context)
            if self.pool.get('purchase.order.line.state').get_sequence(cr, uid, [], po_line.state, context=context) < confirmed_sequence:
                # if the state is less than confirmed we update the PO line
                self.pool.get('purchase.order.line').write(cr, uid, pol_to_update, pol_values, context=context)

        # update PO line state:
        if sol_dict['state'] in ('sourced', 'sourced_v'):
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'sourced_sy', cr)
        elif sol_dict['state'] == 'validated':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'validated', cr)
        elif sol_dict['state'] == 'confirmed':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'confirmed', cr)
        elif sol_dict['state'] == 'cancel':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'cancel', cr)
        elif sol_dict['state'] == 'cancel_r':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'cancel_r', cr)

        # log me:
        pol_data = self.pool.get('purchase.order.line').read(cr, uid, pol_updated, ['order_id', 'line_number'], context=context)
        message = "+++ Purchase Order %s %s: line number %s (id:%s) has been updated +++" % (kind, pol_data['order_id'][1], pol_data['line_number'], pol_updated)
        logging.getLogger('------sync.purchase.order.line').info(message)

        return message

    def confirmed_dpo_service_lines_update_in_po(self, cr, uid, source, line_info, context=None):
        """
        Each DPO line with service products update IN lines
        This method parses the line_info values and transform this data to call
        the partial_shipped_fo_updates_in_po() method of stock.picking
        """
        if context is None:
            context ={}

        line_dict = line_info.to_dict()

        out_info = {
            'state': 'draft',
            'subtype': 'picking',
            'partner_type_stock_picking': 'internal',
            'shipment_id': False,
            'name': line_dict.get('order_id', {}).get('name', ''),
            'origin': line_dict.get('origin', False),
            'min_date': line_dict.get('order_id', {}).get('delivery_confirmed_date', time.strftime('%Y-%m-%d %H:%M:%S')),
            'move_lines': [{
                'asset_id': False,
                'processed_stock_move': False,
                'date_expected': line_dict.get('confirmed_delivery_date', time.strftime('%Y-%m-%d %H:%M:%S')),
                'name': line_dict.get('name', ''),
                'product_uom': line_dict.get('product_uom'),
                'line_number': line_dict.get('link_sol_id', {}).get('line_number', 0),
                'dpo_line_id': int(line_dict.get('fake_id', '0')),
                'state': 'done',
                'original_qty_partial': -1,
                'note': line_dict.get('notes', ''),
                'prodlot_id': False,
                'expired_date': False,
                'product_qty': line_dict.get('product_qty', 0.00),
                'date': line_dict.get('confirmed_delivery_date', time.strftime('%Y-%m-%d %H:%M:%S')),
                'change_reason': False,
                'product_id': line_dict.get('product_id'),
                'comment': line_dict.get('comment'),
            }],
        }

        return self.pool.get('stock.picking').partial_shippped_dpo_updates_in_po(cr, uid, source, out_info, context=context)

purchase_order_line_sync()


class purchase_order_line_to_split(osv.osv):
    _name = 'purchase.order.line.to.split'
    _rec_name = 'line_id'

    _columns = {
        'line_id': fields.many2one(
            'purchase.order.line',
            string='Original line',
            readonly=True,
            required=False,
            ondelete='cascade',
        ),
        'order_id': fields.many2one(
            'purchase.order',
            string='Purchase order',
            readonly=True,
            required=False,
            ondelete='cascade',
        ),
        'original_qty': fields.float(
            string='Original qty',
            required=False,
            readonly=True,
        ),
        'new_line_qty': fields.float(
            digits=(16,2),
            string='New line qty',
            required=True,
            readonly=True,
        ),
        'sync_order_line_db_id': fields.text(
            string='Sync Order line DB ID of the new created line',
            readonly=True,
            required=True,
            index=1,
        ),
        'new_sync_order_line_db_id': fields.text(
            string='Sync Order line DB ID of the new created line',
            readonly=True,
            required=True,
            index=1,
        ),
        'splitted': fields.boolean(
            string='Is ran ?',
            readonly=True,
            index=1,
        ),
    }

    def create_from_sync_message(self, cr, uid, source, line_info, context=None):
        """
        Create a record of purchase.order.line.to.split from the sync. messages
        """
        pol_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        lid = line_info.to_dict()
        line_vals = {}
        if 'old_sync_order_line_db_id' in lid:
            pol_ids = pol_obj.search(cr, uid, [
                ('sync_order_line_db_id', '=', lid['old_sync_order_line_db_id'])
            ], context=context)
            if not pol_ids:
                line_vals.update({
                    'original_qty': 0.00,
                    'new_line_qty': lid.get('new_line_qty', 0.00),
                    'sync_order_line_db_id': lid.get('old_sync_order_line_db_id'),
                    'new_sync_order_line_db_id': lid.get('new_sync_order_line_db_id'),
                })
            else:
                pol_brw = pol_obj.browse(cr, uid, pol_ids[0], context=context)
                line_vals.update({
                    'line_id': pol_brw.id,
                    'order_id': pol_brw.order_id.id,
                    'original_qty': lid.get('old_line_qty', pol_brw.product_qty),
                    'new_line_qty': lid.get('new_line_qty', 0.00),
                    'sync_order_line_db_id': lid.get('new_sync_order_line_db_id'),
                    'new_sync_order_line_db_id': lid.get('new_sync_order_line_db_id'),
                })
            self.create(cr, uid, line_vals, context=context)
        else:
            raise Exception, "No Order line DB ID given in the sync. message"

        return


purchase_order_line_to_split()


class purchase_order_sync(osv.osv):
    _inherit = "purchase.order"
    _logger = logging.getLogger('------sync.purchase.order')

    def _is_validated_and_synced(self, cr, uid, ids, field_name, arg, context=None):
        """fields.function 'is_validated_and_synced'."""
        if context is None:
            context = {}
        res = {}
        sync_msg_obj = self.pool.get('sync.client.message_to_send')
        for po in self.browse(cr, uid, ids, context=context):
            res[po.id] = False
            if po.state == 'validated' and po.partner_id and po.partner_id.partner_type != 'esc':  # uftp-88 PO for ESC partner are never synchronised, no warning msg in PO form
                po_identifier = self.get_sd_ref(cr, uid, po.id, context=context)
                sync_msg_ids = sync_msg_obj.search(
                    cr, uid,
                    [('sent', '=', True),
                     ('remote_call', '=', 'sale.order.create_so'),
                     ('identifier', 'like', po_identifier),
                     ],
                    limit=1, order='NO_ORDER', context=context)
                res[po.id] = bool(sync_msg_ids)
        return res

    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
        'push_fo': fields.boolean('The Push FO case', readonly=False),
        'from_sync': fields.boolean('Updated by synchronization', readonly=False),
        'po_updated_by_sync': fields.boolean('PO updated by sync', readonly=False),
        'fo_sync_date': fields.datetime(string='FO sync. date', readonly=True),
        'is_validated_and_synced': fields.function(
            _is_validated_and_synced, method=True,
            type='boolean',
            string=u"Validated and Synced"),
    }

    _defaults = {
        'push_fo': False,
        'sended_by_supplier': True,
        'po_updated_by_sync': False,
        'is_validated_and_synced': False,
    }

    def manage_split_po_lines(self, cr, uid, po_id, context=None):
        """
        Split the PO lines according to split FO lines
        """
        split_po_line_ids = self.pool.get('purchase.order.line.to.split').search(cr, uid, [
            ('splitted', '=', False),
        ], context=context)

        done_ids = []
        for spl_brw in self.pool.get('purchase.order.line.to.split').browse(cr, uid, split_po_line_ids, context=context):
            pol_id = False
            if not spl_brw.line_id:
                already_pol_ids = self.pool.get('purchase.order.line').search(cr, uid,
                                                                              [('sync_order_line_db_id', '=',
                                                                                spl_brw.new_sync_order_line_db_id)],
                                                                              limit=1, order='NO_ORDER', context=context)
                pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('sync_order_line_db_id', '=', spl_brw.sync_order_line_db_id)], context=context)
                if not pol_ids or already_pol_ids:
                    continue
                else:
                    pol_id = pol_ids[0]
            else:
                pol_id = spl_brw.line_id.id

            pol_brw = self.pool.get('purchase.order.line').browse(cr, uid, pol_id, context=context)
            if pol_brw.order_id.id != po_id:
                continue

            if pol_brw.product_qty < spl_brw.new_line_qty + 1:
                self.pool.get('purchase.order.line').write(cr, uid, [pol_brw.id], {'product_qty': pol_brw.product_qty + spl_brw.new_line_qty}, context=context)
                pol_brw = self.pool.get('purchase.order.line').browse(cr, uid, pol_brw.id, context=context)

            split_id = self.pool.get('split.purchase.order.line.wizard').create(cr, uid, {
                'purchase_line_id': pol_brw.id,
                'original_qty': pol_brw.product_qty,
                'old_line_qty': pol_brw.product_qty - spl_brw.new_line_qty,
                'new_line_qty': spl_brw.new_line_qty,
            }, context=context)
            context['split_sync_order_line_db_id'] = spl_brw.new_sync_order_line_db_id
            self.pool.get('split.purchase.order.line.wizard').split_line(cr, uid, split_id, context=context)
            del context['split_sync_order_line_db_id']

            done_ids.append(spl_brw.id)

        self.pool.get('purchase.order.line.to.split').write(cr, uid, done_ids, {'splitted': True}, context=context)

        return


    # UF-2267: Added a new method to update the reference of the FO back to the PO
    def update_fo_ref(self, cr, uid, source, so_info, context=None):
        self._logger.info("+++ Update the FO reference from %s to the PO %s"%(source, cr.dbname))
        if not context:
            context = {}

        context['no_check_line'] = True
        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)

        if not po_id:
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
                return "Recovery: the original PO " + so_info.name + " has been created after the backup and thus cannot be updated"
            raise Exception, "Cannot find the original PO with the given info."

        po_value = self.browse(cr, uid, po_id)
        ref = po_value.partner_ref
        partner_ref = source + "." + so_info.name

        if not ref or partner_ref != ref: # only issue a write if the client_order_reference is not yet set!
            # Sorry: This trick is to avoid creating new useless message to the synchronisation engine!
            cr.execute('update purchase_order set partner_ref=%s where id=%s', (partner_ref, po_id))

        message = "The PO " + po_value.name + " is now linked to " + so_info.name + " at " + source
        self._logger.info(message)
        return message


    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({'active': True, 'split_po' : False, 'push_fo' : False, 'po_updated_by_sync': False})
        return super(purchase_order_sync, self).copy(cr, uid, id, default, context=context)


    # UTP-953: This case is not allowed for the intersection partner due to the missing of Analytic Distribution!!!!!
    def normal_fo_create_po(self, cr, uid, source, so_info, context=None):
        self._logger.info("+++ Create a PO (at %s) from an FO (push flow) (from %s)"%(cr.dbname, source))
        if not context:
            context = {}

        so_po_common = self.pool.get('so.po.common')

        # UF-1830: TODO: DO NOT CREATE ANYTHING FROM A RESTORE CASE!
        if context.get('restore_flag'):
            # UF-1830: Cannot create a PO from a recovery message
            so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
            return "Recovery: Cannot create the PO. Please inform the owner of the SO " + so_info.name + " to cancel it and to recreate a new process."

        so_dict = so_info.to_dict()

        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)

        # check whether this FO has already been sent before! if it's the case, then just update the existing PO, and not creating a new one
        po_id = self.check_existing_po(cr, uid, source, so_dict)
        header_result['push_fo'] = True
        header_result['origin'] = so_dict.get('name', False)

        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type == 'section':
            #US-620: If the FO type is donation or loan, then remove the analytic distribution
            if so_info.order_type in ('loan', 'donation_st', 'donation_exp'):
                if 'analytic_distribution_id' in header_result:
                    del header_result['analytic_distribution_id']
            else:
                raise Exception, "Sorry, Push Flow for intersection partner is only available for Donation or Loan FOs! " + source

        # the case of intermission, the AD will be updated below, after creating the PO
        if partner_type == 'intermission' and 'analytic_distribution_id' in header_result:
            del header_result['analytic_distribution_id']

        default = {}
        default.update(header_result)

        if po_id: # only update the PO - should never be in here!
            self.write(cr, uid, po_id, default, context=context)
        else:
            # create a new PO, then send it to Validated state
            po_id = self.create(cr, uid, default , context=context)

        # update the next line number for the PO if needed
        so_po_common.update_next_line_number_fo_po(cr, uid, po_id, self, 'purchase_order_line', context)

        name = self.browse(cr, uid, po_id, context=context).name
        message = "The PO " + name + " is created by sync and linked to the FO " + so_info.name + " by Push Flow at " + source
        self._logger.info(message)

        return message

    def check_existing_po(self, cr, uid, source, so_dict):
        if not source:
            raise Exception, "The partner is missing!"

        name = source + '.' + so_dict.get('name')
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            return False
        return po_ids[0]


    def check_mandatory_fields(self, cr, uid, so_dict):
        if not so_dict.get('delivery_confirmed_date'):
            raise Exception, "The delivery confirmed date is missing - please verify the values of the sync message!"

        if not so_dict.get('state'):
            raise Exception, "The state of the split FO is missing - please verify the values of the sync message!"

    # UTP-872: If the PO is a split one, then still allow it to be confirmed without po_line
    def _hook_check_po_no_line(self, po, context):
        if not po.split_po and not po.order_line:
            raise osv.except_osv(_('Error !'), _('You can not confirm purchase order without Purchase Order Lines.'))

    def validated_fo_update_original_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Update the original PO at %s when the relevant FO at %s got validated"%(cr.dbname, source))

        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)

        # UF-1830: TODO: if the PO does not exist in the system, just warn that the message is failed to be executed, and create a message to the partner
        if not po_id:
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
                return "Recovery: the FO " + so_info.name + " does not exist any more due to recovery. The reference to it will be set to void"
            raise Exception, "Cannot find the original PO with the given info."

        so_dict = so_info.to_dict()

        self.manage_split_po_lines(cr, uid, po_id, context=context)

        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, source, so_info, po_id, False, True, False, context)

        header_result['po_updated_by_sync'] = True

        # UTP-952: If the partner is section or intermission, remove the AD
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type in ['section', 'intermission'] and 'analytic_distribution_id' in header_result:
            del header_result['analytic_distribution_id']

        original_po = self.browse(cr, uid, po_id, context=context)
        # UTP-661: Get the 'Cross Docking' value of the original PO, and add it into the split PO
        header_result['cross_docking_ok'] = original_po['cross_docking_ok']
        header_result['location_id'] = original_po.location_id.id

        default = {}
        default.update(header_result)

        self.write(cr, uid, po_id, default, context=context)

        message = "The PO " + original_po.name + " is updated by sync as its partner FO " + so_info.name + " got updated at " + source
        self._logger.info(message)
        return message

    def msg_close_filter(self, cr, uid, rule, context=None):
        """
        Called by PO close message rule at RW
        @return: list of ids of unclosed PO's whose pickings are all done
        """
        cr.execute("""\
            SELECT p.id from purchase_order p
            left join stock_picking s on s.purchase_id = p.id
            where p.state = 'approved'
            group by p.id
            having bool_and(s.state = 'done') = true;""")
        return [row[0] for row in cr.fetchall()]

    def msg_close(self, cr, uid, source, po, context=None):
        po_id = self.search(cr, uid, [('name','=',po.name)])
        self.action_done(cr, uid, po_id, context=context)

    def on_create(self, cr, uid, id, values, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        logger = get_sale_purchase_logger(cr, uid, self, id, context=context)
        logger.action_type = 'creation'
        logger.is_product_added |= (len(values.get('order_line', [])) > 0)

    def on_change(self, cr, uid, changes, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        # create a useful mapping purchase.order ->
        #    dict_of_purchase.order.line_changes
        lines = {}
        if 'purchase.order.line' in context['changes']:
            for rec_line in self.pool.get('purchase.order.line').browse(
                    cr, uid,
                    context['changes']['purchase.order.line'].keys(),
                    context=context):
                if self.pool.get('purchase.order.line').exists(cr, uid, rec_line.id, context): # check the line exists
                    lines.setdefault(rec_line.order_id.id, {})[rec_line.id] = context['changes']['purchase.order.line'][rec_line.id]
        # monitor changes on purchase.order
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                                              context=context)
            if 'order_line' in changes:
                old_lines, new_lines = map(set, changes['order_line'])
                logger.is_product_added |= (len(new_lines - old_lines) > 0)
                logger.is_product_removed |= (len(old_lines - new_lines) > 0)

            #UFTP-242: Log if there is lines deleted for this PO
            if context.get('deleted_line_po_id', -1) == id:
                logger.is_product_removed = True
                del context['deleted_line_po_id']

            logger.is_date_modified |= ('delivery_confirmed_date' in changes)
            logger.is_status_modified |= ('state' in changes)
            # handle line's changes
            for line_id, line_changes in lines.get(id, {}).items():
                logger.is_quantity_modified |= ('product_qty' in line_changes)
                logger.is_product_price_modified |= \
                    ('price_unit' in line_changes)

    def create_split_po(self, cr, uid, source, so_info, context=None):
        # deprecated used only to manage SLL migration

        so_po_common = self.pool.get('so.po.common')
        pol_obj = self.pool.get('purchase.order.line')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)
        if not po_id:
            message = 'Received message to split po %s, but PO not found' % (so_info.name, )
            self._logger.info(message)
            return message

        original_po = self.browse(cr, uid, po_id, context=context)
        if original_po.name[-2] == '-' and original_po.name[-1] in ['1', '2', '3']:
            message = "The PO split " + original_po.name + " exists already in the system, linked to " + so_info.name + " at " + source + ". The message is ignored."
            self._logger.info(message)
            return message

        for x in so_info.order_line:
            if x.sync_order_line_db_id and 'FO' in x.sync_order_line_db_id and x.source_sync_line_id:
                pol_ids = pol_obj.search(cr, uid, [('order_id', '=', po_id), ('sync_order_line_db_id', '=', x.source_sync_line_id), ('sync_linked_sol', '=', False)])
                if pol_ids:
                    pol_obj.write(cr, uid, pol_ids, {'sync_linked_sol': so_po_common.migrate_ref(x.sync_order_line_db_id)}, context=context)

        self.write(cr, uid, [po_id], {'split_during_sll_mig': True})
        return True

    def update_split_po(self, cr, uid, source, so_info, context=None):
        # deprecated used only to manage ssl migration
        if not context:
            context = {}
        self._logger.info("+++ Update the split POs at %s when the sourced FO at %s got confirmed"%(cr.dbname, source))
        so_po_common = self.pool.get('so.po.common')

        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)


        if not po_id:
            raise Exception, "The split PO linked to " + so_info.name + "at " + source + " not found!"

        self.check_mandatory_fields(cr, uid, so_dict)

        self.manage_split_po_lines(cr, uid, po_id, context=context)

        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, source=source, line_values=so_info, po_id=po_id, so_id=False, for_update=False, so_called=False, context=context)
        header_result['po_updated_by_sync'] = True

        updated_lines = []
        sync_order_line_db_id = []
        for x in header_result['order_line']:
            if x[0] == 1:
                updated_lines.append(x[1])
                if x[2].get('sync_linked_sol'):
                    sync_order_line_db_id.append(x[2]['sync_linked_sol'])
            elif x[0] == 0 and x[2].get('sync_linked_sol'):
                sync_order_line_db_id.append(x[2]['sync_linked_sol'])

        to_del_ids = self.pool.get('purchase.order.line').search(cr, uid, [
            ('order_id', '=', po_id),
            ('id', 'not in', updated_lines),
            ('state', 'not in', ['draft', 'done', 'cancel', 'cancel_r']),
            '|', ('sync_order_line_db_id', '=like', so_info.name+'_%'), ('sync_linked_sol', '=like', so_info.name+'/%')
        ], context=context)

        if to_del_ids:
            self.pool.get('purchase.order.line').action_cancel(cr, uid, to_del_ids, context=context)

        # UTP-952: If the partner is section or intermission, remove the AD
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type in ['section', 'intermission'] and 'analytic_distribution_id' in header_result:
            del header_result['analytic_distribution_id']

        default = {}
        default.update(header_result)
        self.write(cr, uid, po_id, default, context=context)
        if partner_type == 'intermission':
            self.check_analytic_distribution(cr, uid, [po_id], context=context, create_missing=True)

        if sync_order_line_db_id:
            po_line_obj = self.pool.get('purchase.order.line')
            po_line_ids = po_line_obj.search(cr, uid, [('order_id', '=', po_id), ('sync_linked_sol', 'in', sync_order_line_db_id)], context=context)
            if po_line_ids:
                po_line_obj.action_validate(cr, uid, po_line_ids, context=context)
                if so_info.state != 'validated':
                    po_line_obj.action_confirmed(cr, uid, po_line_ids, context=context)

        message = "The split PO "+ str(po_id)  + " is updated by sync as its partner FO " + so_info.name + " got updated at " + source
        self._logger.info(message)
        return message

purchase_order_sync()
