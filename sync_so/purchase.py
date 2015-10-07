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
import pdb
import time
from tools.translate import _

from sync_client import get_sale_purchase_logger


class purchase_order_line_sync(osv.osv):
    _inherit = 'purchase.order.line'

    _columns = {
        'original_purchase_line_id': fields.text(string='Original purchase line id'),
        'dest_partner_id': fields.related('order_id', 'dest_partner_id', string='Destination partner', readonly=True, type='many2one', relation='res.partner', store=True),
    }

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
            digits=(16,2),
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

    def _is_confirmed_and_synced(self, cr, uid, ids, field_name, arg, context=None):
        """fields.function 'is_confirmed_and_synced'."""
        if context is None:
            context = {}
        res = {}
        sync_msg_obj = self.pool.get('sync.client.message_to_send')
        for po in self.browse(cr, uid, ids, context=context):
            res[po.id] = False
            if po.state == 'confirmed' \
                and po.partner_id and po.partner_id.partner_type != 'esc':  # uftp-88 PO for ESC partner are never to synchronised, no warning msg in PO form
                po_identifier = self.get_sd_ref(cr, uid, po.id, context=context)
                sync_msg_ids = sync_msg_obj.search(
                    cr, uid,
                    [('sent', '=', True),
                     ('remote_call', '=', 'sale.order.create_so'),
                     ('identifier', 'like', po_identifier),
                     ],
                    context=context)
                res[po.id] = bool(sync_msg_ids)
        return res

    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
        'push_fo': fields.boolean('The Push FO case', readonly=False),
        'from_sync': fields.boolean('Updated by synchronization', readonly=False),
        'po_updated_by_sync': fields.boolean('PO updated by sync', readonly=False),
        'fo_sync_date': fields.datetime(string='FO sync. date', readonly=True),
        'is_confirmed_and_synced': fields.function(
            _is_confirmed_and_synced, method=True,
            type='boolean',
            string=u"Confirmed and Synced"),
    }

    _defaults = {
        'push_fo': False,
        'sended_by_supplier': True,
        'po_updated_by_sync': False,
        'is_confirmed_and_synced': False,
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
                already_pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('sync_order_line_db_id', '=', spl_brw.new_sync_order_line_db_id)], context=context)
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

    def create_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Create the split PO at destination (at %s) from the split FO at supplier (at %s)"%(cr.dbname,source))

        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        header_result = {}

        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context) # This should be the original PO, not the split one of POx-2/3
        if not po_id:
            # UF-1830: TODO: DO NOT CREATE ANYTHING FROM A RESTORE CASE!
            if context.get('restore_flag'):
                # UF-1830: Cannot create PO from a recovery message
                so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
                return "Recovery: cannot create the PO. Please inform the owner of the FO " + so_info.name + " at " + source + " to cancel it and to recreate a new process."
            raise Exception, "Cannot find the original PO that links to " + so_info.name + " at " + source

        self.manage_split_po_lines(cr, uid, po_id, context=context)

        # UF-1830: if the PO exists, double check if this PO is really a normal PO, and not a split PO with suffix of -1,2,3!
        # if yes, then just return without continuing
        original_po = self.browse(cr, uid, po_id, context=context)
        if original_po.name[-2] == '-' and original_po.name[-1] in ['1', '2', '3']:
            message = "The PO split " + original_po.name + " exists already in the system, linked to " + so_info.name + " at " + source + ". The message is ignored."
            self._logger.info(message)
            return message

        # Name the new split PO to stick with the name of FO (FOxxxx-1, FOxxxx-2 or FOxxxx-3)
        if so_info.name[-2] == '-' and so_info.name[-1] in ['1', '2', '3']:
            header_result['name'] = original_po.name + so_info.name[-2:]
        else:
            text = "The given format of the split FO is not valid" + so_info.name
            self._logger.error(text)
            raise Exception, text

        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)

        header_result['order_line'] = so_po_common.get_lines(cr, uid, source, so_info, False, False, False, False, context)
        header_result['split_po'] = True

        if so_info.state == 'sourced':
            header_result['state'] = 'sourced'

        # UF-1830: Check if the future FO split exists in the system, if it is the case, then the message is coming from a recovery from the partner!
        check_exist = self.search(cr, uid, [('name', '=', header_result['name'])])
        if check_exist:
            # if it is the case, then just update the reference to the newly created FO-split at the partner side
            self.write(cr, uid, check_exist, {'partner_ref': header_result['partner_ref']} , context=context)
            message = "The PO split " + original_po.name + " is re-updated to " + so_info.name + " due to the recovery event at " + source
            self._logger.info(message)
            return message


        # UTP-163: Get the 'source document' of the original PO, and add it into the split PO, if existed
        header_result['origin'] = original_po.origin

        # UF-2267: Copy the link to original PO from the split PO to the new PO-2/3
        if original_po.parent_order_name and original_po.parent_order_name.id:
            header_result['parent_order_name'] = original_po.parent_order_name.id

        # UTP-661: Get the 'Cross Docking' value of the original PO, and add it into the split PO
        header_result['cross_docking_ok'] = original_po['cross_docking_ok']
        header_result['location_id'] = original_po.location_id.id

        # UTP-952: If the partner is section or intermission, then take the AD from the original PO, not from the source instance
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type in ['section', 'intermission']:
            analytic_distribution_id = self.browse(cr, uid, po_id, context=context)['analytic_distribution_id']
            header_result['analytic_distribution_id'] = analytic_distribution_id.id

        default = {}
        default.update(header_result)

        line_obj = self.pool.get('purchase.order.line')
        #to_split = {}
        for line in default['order_line']:
        #    if line[2].get('is_line_split') and line[2].get('original_purchase_line_id') and line[2].get('original_purchase_line_id') in to_split:
        #        to_split[line[2].get('original_purchase_line_id')].append(line[2])
        #        del default['order_line'][default['order_line'].index(line)]
        #    elif line[2].get('original_purchase_line_id') and line[2].get('original_purchase_line_id') not in to_split:
        #        to_split.setdefault(line[2].get('original_purchase_line_id'), [])
            orig_line = line_obj.search(cr, uid, [('sync_order_line_db_id', '=', line[2].get('original_purchase_line_id'))])
            if orig_line:
                orig_line = line_obj.browse(cr, uid, orig_line[0], context=context)
                line[2].update({'move_dest_id': orig_line.move_dest_id and orig_line.move_dest_id.id or False})
                line[2].update({'origin': orig_line.origin}) # UF-2291: set also the origin into the new line of the split PO

        # If partner is intermission or section, copy the ADs from the lines of original PO
        if partner_type in ['section', 'intermission']:
            for line in default['order_line']:
                orig_line = line_obj.search(cr, uid, [('order_id', '=', po_id), ('line_number', '=', line[2].get('line_number'))])
                if orig_line:
                    orig_line = line_obj.browse(cr, uid, orig_line[0], context=context)
                    line[2].update({'analytic_distribution_id': orig_line.analytic_distribution_id and orig_line.analytic_distribution_id.id or False})
                    line[2].update({'have_analytic_distribution_from_header': False})

        res_id = self.create(cr, uid, default , context=context)
        so_po_common.update_next_line_number_fo_po(cr, uid, res_id, self, 'purchase_order_line', context)

        #self.manage_split_po_lines(cr, uid, res_id, context=context)

        proc_ids = []
        order_ids = []
        order = self.browse(cr, uid, res_id, context=context)
        origin_lines = []
        #pdb.set_trace()
        for order_line in order.order_line:
            if order_line.original_purchase_line_id:
                orig_line = line_obj.search(cr, uid, [('sync_order_line_db_id', '=', order_line.original_purchase_line_id)], context=context)
                if not orig_line:
                    cancel_ids = self.pool.get('sale.order.line.cancel').search(cr, uid, [('sync_order_line_db_id', '=', order_line.original_purchase_line_id), ('resource_sync_line_db_id', '!=', False)], context=context)
                    orig_line_txt = ''
                    if cancel_ids:
                        orig_line_txt = self.pool.get('sale.order.line.cancel').read(cr, uid, cancel_ids[0], ['resource_sync_line_db_id'], context=context)['resource_sync_line_db_id']
                        orig_line = line_obj.search(cr, uid, [('sync_order_line_db_id', '=', orig_line_txt)], context=context)

                if orig_line:
                    line = line_obj.browse(cr, uid, orig_line[0], context=context)
                    origin_lines.append(line.id)
                    if line.procurement_id:
                        line_obj.write(cr, uid, [order_line.id], {'procurement_id': line.procurement_id.id})
                        proc_ids.append(line.procurement_id.id)
                    if line.order_id:
                        order_ids.append(line.order_id.id)

        # Remove the original PO lines that are not in the split PO
#        for original_line in original_po.order_line:
#            if original_line.id not in origin_lines:
#                line_obj.fake_unlink(cr, uid, [original_line.id], context=context)
        
        self.manage_split_po_lines(cr, uid, res_id, context=context)

        if proc_ids:
            self.pool.get('procurement.order').write(cr, uid, proc_ids, {'purchase_id': res_id}, context=context)
            netsvc.LocalService("workflow").trg_change_subflow(uid, 'procurement.order', proc_ids, 'purchase.order', order_ids, res_id, cr)

#        for orig_line, split_lines in to_split.iteritems():
#            pol_ids = line_obj.search(cr, uid, [('order_id', '=', res_id), ('original_purchase_line_id', '=', orig_line)], context=context)
#            if pol_ids:
#                pol_brw = line_obj.browse(cr, uid, pol_ids[0], context=context)
#                for sp in split_lines:
#                    line_obj.write(cr, uid, pol_ids[0], {'product_qty': pol_brw.product_qty + sp.get('product_qty')}, context=context)
#                    split_obj = self.pool.get('split.purchase.order.line.wizard')
#                    split_id = split_obj.create(cr, uid, {
#                        'purchase_line_id': pol_brw.id,
#                        'original_qty': pol_brw.product_qty + sp.get('product_qty'),
#                        'old_line_qty': pol_brw.product_qty,
#                        'new_line_qty': sp.get('product_qty'),
#                    }, context=context)
#                    split_obj.split_line(cr, uid, [split_id], context=context)
#                    new_line_ids = line_obj.search(cr, uid, [('order_id', '=', res_id)], order='id desc', limit=1)
#                    if new_line_ids and sp.get('sync_order_line_db_id'):
#                        line_obj.write(cr, uid, new_line_ids, {'sync_order_line_db_id': sp.get('sync_order_line_db_id')}, context=context)

        fo_ids = self.pool.get('sale.order').search(cr, uid, [('loan_id', '=', po_id)], context=context)
        if fo_ids:
            netsvc.LocalService("workflow").trg_change_subflow(uid, 'sale.order', fo_ids, 'purchase.order', [po_id], res_id, cr)

        # after created this splitted PO, pass it to the confirmed, as the split SO has been done so too.
        if so_info.state in ('confirmed', 'progress'):
            netsvc.LocalService("workflow").trg_validate(uid, 'purchase.order', res_id, 'purchase_confirm', cr)
        else:
            self.write(cr, uid, res_id, {'state': 'sourced' } , context=context)

        # Set the original PO to "split" state -- cannot do anything with this original PO, and update the partner_ref
        partner_ref = so_po_common.get_full_original_fo_ref(source, so_info.name)
        self.write(cr, uid, po_id, {'state' : 'split', 'active': False, 'partner_ref': partner_ref} , context=context)

        # if it is a loan type, then update the source
        if 'order_type' in header_result:
            if header_result['order_type'] == 'loan':
                # UTP-392: In the push flow, the FO counterpart could be created first by the sync, then the original PO will be created
                # so in this case, when creating the PO, the FO counterpart must be linked to the new split PO
                name = self.browse(cr, uid, res_id, context).partner_ref # get the partner_ref from Coordo
                so_object = self.pool.get('sale.order')
                so_ids = so_object.search(cr, uid, [('origin', '=', name)], context=context) # search the existing FO counterpart
                if so_ids and so_ids[0]: # if exist, then update the link to it with this new split PO
                    name = so_object.browse(cr, uid, so_ids[0], context).name
                    self.write(cr, uid, [res_id], {'origin': name}, context=context)
                    so_object.write(cr, uid, so_ids, {'origin': False} , context=context) # reset this origin value of the FO counterpart back to null

        message = "The split PO " + order.name + " is created by sync and linked to the split FO " + so_info.name + " at " + source
        self._logger.info(message)
        return message


    # UTP-953: This case is not allowed for the intersection partner due to the missing of Analytic Distribution!!!!!
    def normal_fo_create_po(self, cr, uid, source, so_info, context=None):
        self._logger.info("+++ Create a PO (at %s) from an FO (push flow) (from %s)"%(cr.dbname, source))
        if not context:
            context = {}

        so_po_common = self.pool.get('so.po.common')
        line_obj = self.pool.get('purchase.order.line')
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type == 'section':
            raise Exception, "Sorry, the push low is not available for intersection partner! " + source

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
        header_result['order_line'] = so_po_common.get_lines(cr, uid, source, so_info, po_id, False, False, False, context)
        header_result['push_fo'] = True
        header_result['origin'] = so_dict.get('name', False)

        # the case of intermission, the AD will be updated below, after creating the PO
        if partner_type == 'intermission':
            del header_result['analytic_distribution_id']

        default = {}
        default.update(header_result)

        if po_id: # only update the PO - should never be in here!
            res_id = self.write(cr, uid, po_id, default, context=context)
        else:
            # create a new PO, then send it to Validated state
            po_id = self.create(cr, uid, default , context=context)
        
        for line in self.browse(cr, uid, po_id, context=context).order_line:
            if line.sync_order_line_db_id:
                cancel_ids = self.pool.get('sale.order.line.cancel').search(cr, uid, [('resource_sync_line_db_id', '=', line.sync_order_line_db_id)], context=context)
                sol_ids = []
                for cancel in self.pool.get('sale.order.line.cancel').browse(cr, uid, cancel_ids, context=context):
                    sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('sync_order_line_db_id', '=', cancel.fo_sync_order_line_db_id)], context=context)
                    for sol in self.pool.get('sale.order.line').browse(cr, uid, sol_ids, context=context):
                        if sol.procurement_id and sol.procurement_id.purchase_id:
                            self.pool.get('procurement.order').write(cr, uid, [sol.procurement_id.id], {'purchase_id': po_id}, context=context)
                            line_obj.write(cr, uid, [line.id], {'procurement_id': sol.procurement_id.id}, context=context)
                            netsvc.LocalService("workflow").trg_change_subflow(uid, 'procurement.order', [sol.procurement_id.id], 'purchase.order', [sol.procurement_id.purchase_id.id], po_id, cr)
                        if sol.order_id and (not sol.order_id.procurement_request or sol.order_id.location_requestor_id.usage == 'customer'):
                            self.write(cr, uid, [po_id], {'cross_docking_ok': True}, context=context)

        # UTP-952: If the partner is intermission, then use the intermission CC to create a default AD
        if partner_type == 'intermission':
            # create the default AD with intermission CC and default FP
            intermission_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_intermission')
            ana_obj = self.pool.get('analytic.distribution')
            for po in self.browse(cr, uid, [po_id], context=context):
                for line in po.order_line:
                    account_id = line.account_4_distribution and line.account_4_distribution.id or False
                    # Search default destination_id
                    destination_id = self.pool.get('account.account').read(cr, uid, account_id, ['default_destination_id']).get('default_destination_id', False)
                    distrib_id = ana_obj.create(cr, uid, {'purchase_line_ids': [(4,line.id)],
                        'cost_center_lines': [(0, 0, {'destination_id': destination_id[0], 'analytic_id': intermission_cc[1] , 'percentage':'100', 'currency_id': po.currency_id.id})]})

        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)

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

    def check_update(self, cr, uid, source, so_dict):
        if not source:
            raise Exception, "The partner is missing!"

        name = so_dict.get('name')
        if not name:
            raise Exception, "The split PO name is missing - please check at the message rule!"

        name = source + '.' + name
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if po_ids:
            return po_ids[0]
        return False

    def check_mandatory_fields(self, cr, uid, so_dict):
        if not so_dict.get('delivery_confirmed_date'):
            raise Exception, "The delivery confirmed date is missing - please verify the values of the sync message!"

        if not so_dict.get('state'):
            raise Exception, "The state of the split FO is missing - please verify the values of the sync message!"

    def update_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Update the split POs at %s when the sourced FO at %s got confirmed"%(cr.dbname, source))
        so_po_common = self.pool.get('so.po.common')

        so_dict = so_info.to_dict()
        po_id = self.check_update(cr, uid, source, so_dict)

        # UF-1830: TODO: if the PO does not exist in the system, just warn that the message is failed to be executed, and create a message to the partner
        if not po_id:
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
                return "Recovery: the reference to " + so_info.name + " at " + source + " will be set to void."
            raise Exception, "The split PO linked to " + so_info.name + "at " + source + " not found!"

        # UF-1830: Check if the PO needs to be updated, if it is confirmed/closed or split, then no need to update, just ignore
        original_po = self.browse(cr, uid, po_id, context=context)
        if original_po.state in ('approved', 'done', 'split'):
            message = "Nothing to update for the split PO " + original_po.name + " as its state is already in (Confirmed, Closed, Split)"
            self._logger.info(message)
            return message

        self.check_mandatory_fields(cr, uid, so_dict)

        self.manage_split_po_lines(cr, uid, po_id, context=context)

        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, source, so_info, po_id, False, True, False, context)
        header_result['po_updated_by_sync'] = True

        # UTP-952: If the partner is section or intermission, remove the AD
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type in ['section', 'intermission']:
            del header_result['analytic_distribution_id']

        # UTP-661: Get the 'Cross Docking' value of the original PO, and add it into the split PO
        header_result['cross_docking_ok'] = original_po['cross_docking_ok']
        header_result['location_id'] = original_po.location_id.id

        default = {}
        default.update(header_result)

        res_id = self.write(cr, uid, po_id, default, context=context)
        if so_info.original_so_id_sale_order:
            wf_service = netsvc.LocalService("workflow")
            if so_info.state == 'validated':
                ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
            else:
                ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
                res = self.purchase_approve(cr, uid, [po_id], context=context) # UTP-972: Use a proper workflow to confirm a PO
                # UFTP-49: the call to wf_service.trg_validate does not trigger any write to PO, so there is no log recorded, set it manually here
                logger = get_sale_purchase_logger(cr, uid, self, po_id, context=context)
                logger.is_status_modified = True

        message = "The split PO " + original_po.name + " is updated by sync as its partner FO " + so_info.name + " got updated at " + source
        self._logger.info(message)
        return message

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

        partner_ref = source + "." + so_info.name
        header_result['partner_ref'] = partner_ref
        header_result['po_updated_by_sync'] = True

        # UTP-952: If the partner is section or intermission, remove the AD
        partner_type = so_po_common.get_partner_type(cr, uid, source, context)
        if partner_type in ['section', 'intermission']:
            del header_result['analytic_distribution_id']

        original_po = self.browse(cr, uid, po_id, context=context)
        # UTP-661: Get the 'Cross Docking' value of the original PO, and add it into the split PO
        header_result['cross_docking_ok'] = original_po['cross_docking_ok']
        header_result['location_id'] = original_po.location_id.id

        default = {}
        default.update(header_result)

        res_id = self.write(cr, uid, po_id, default, context=context)

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

    def canceled_fo_cancel_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Cancel the original PO at %s due to the cancel of the FO at %s"%(cr.dbname,source))
        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)

        # UF-1830: TODO: if the PO does not exist in the system, just warn that the message is failed to be executed, and create a message to the partner
        if not po_id:
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common.create_invalid_recovery_message(cr, uid, source, so_info.name, context)
                return "Recovery: The PO " + so_info.name + " does not exist any more. The reference to it will be set to void."
            raise Exception, "Cannot find the original PO with the given info."

        self.write(cr, uid, po_id, {'from_sync': True}, context)
        # Cancel the PO
        wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_cancel', cr)

        name = self.browse(cr, uid, po_id, context).name
        message = "The PO " + name + " is canceled by sync as its partner FO " + so_info.name + " got canceled at " + source
        self._logger.info(message)
        return message

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

purchase_order_sync()
