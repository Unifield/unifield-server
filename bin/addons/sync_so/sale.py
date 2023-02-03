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

import logging

from osv import osv, fields
import so_po_common
assert so_po_common # needed by rw
import time
from sync_client import get_sale_purchase_logger
from sync_client import SyncException


class sale_order_line_sync(osv.osv):
    _inherit = "sale.order.line"
    _logger = logging.getLogger('------sync.sale.order.line')

    def _get_sync_local_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for sol in self.read(cr, uid, ids, ['order_id'], context=context):
            ret[sol['id']] = '%s/%s' % (sol['order_id'][1], sol['id'])
        return ret

    _columns = {
        'source_sync_line_id': fields.text(string='Sync DB id of the PO origin line'),
        'sync_local_id': fields.function(_get_sync_local_id, type='char', method=True, string='ID', help='for internal use only'),
        'sync_linked_pol': fields.char(size=256, string='Linked purchase order line at synchro', select=1),
        'resourced_original_remote_line': fields.char(size=256, string='Orig customer PO line', select=1, help='INTERNAL USE: id of the remote cancelled and resourced line, the parent of the current line. Usefull to fill the field resourced_original_line in the other instance'),
    }

    def create_so_line(self, cr, uid, source, line_info, context=None):
        if context is None:
            context = {}
        pol_dict = line_info.to_dict()

        # search for the parent sale.order:
        order_ref = '%s.%s' % (source, pol_dict['order_id']['name'])
        sale_order_ids = self.pool.get('sale.order').search(cr, uid, [('client_order_ref', '=', order_ref)])
        if not sale_order_ids:
            raise Exception, "Cannot find the parent FO with client order ref = %s" % order_ref
        so_name = self.pool.get('sale.order').read(cr, uid, sale_order_ids[0], ['name'], context=context)['name'] or ''

        try:
            # from purchase.order.line to sale.order.line:
            sol_values = self.pool.get('so.po.common').get_line_data(cr, uid, source, line_info, context)
            sol_values['order_id'] = sale_order_ids[0]
            sol_values['sync_linked_pol'] = pol_dict.get('sync_local_id', False)
            sol_values['ir_name_from_sync'] = pol_dict.get('ir_name_for_sync', False)
            sol_values['original_instance'] = pol_dict.get('original_instance', False)
            if line_info.product_id and not sol_values.get('product_id'):
                raise Exception('FO: %s , Product %s not found' % (so_name, line_info.default_code or ''))
            if sol_values.get('product_id'):
                sol_values['original_product'] = sol_values['product_id']
            if sol_values.get('product_qty') or sol_values.get('product_uom_qty'):
                sol_values['original_qty'] = sol_values.get('product_qty', False) or sol_values.get('product_uom_qty', False)
            new_sol_id = self.pool.get('sale.order.line').create(cr, uid, sol_values, context=context)

            message = ": New line #%s (id:%s) added to Sale Order %s ::" % (pol_dict['line_number'], new_sol_id, so_name)
            self._logger.info(message)

            return message
        except Exception, e:
            if hasattr(e, 'value'):
                msg = e.value
            else:
                msg = '%s' % e
            raise SyncException(msg, target_object='sale.order', target_id=sale_order_ids[0])


sale_order_line_sync()


class sale_order_line_cancel(osv.osv):
    _inherit = 'sale.order.line.cancel'
    _logger = logging.getLogger('------sale.order.line.cancel')

    def create_line(self, cr, uid, source, line_info, context=None):
        self._logger.info("+++ Create an sale.order.line.cancel at %s from a sale.order.line.cancel at %s"%(cr.dbname, source))
        if not context:
            context = {}

        line_dict = line_info.to_dict()
        line_dict['partner_id'] = False

        sync_order_line_db_id = line_dict.get('sync_order_line_db_id', False)
        so_order_line_db_id = False
        if sync_order_line_db_id:
            pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('sync_order_line_db_id', '=', sync_order_line_db_id)], context=context)
            sol_ids = self.pool.get('purchase.order.line').get_sol_ids_from_pol_ids(cr, uid, pol_ids, context=context)
            if sol_ids:
                so_order_line_db_id = self.pool.get('sale.order.line').read(cr, uid, sol_ids[0], ['sync_order_line_db_id'], context=context)['sync_order_line_db_id']

        if so_order_line_db_id:
            line_dict['fo_sync_order_line_db_id'] = so_order_line_db_id

        self.create(cr, uid, line_dict, context=context)

        return True


sale_order_line_cancel()


class sale_order_sync(osv.osv):
    _inherit = "sale.order"
    _logger = logging.getLogger('------sync.sale.order')

    def _get_sync_date(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for so_id in ids:
            res[so_id] = time.strftime('%Y-%m-%d %H:%M:%S')

        return res

    _columns = {
        'received': fields.boolean('Received by Client', readonly=True),
        'fo_created_by_po_sync': fields.boolean('FO created by PO after SYNC', readonly=True),
        'sync_date': fields.function(
            _get_sync_date,
            method=True,
            string='Sync Date',
            type='datetime',
            store=False,
            readonly=True,
        ),
    }

    _defaults = {
        'fo_created_by_po_sync': False,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        if not default.get('name', False) or not '-2' in default.get('name', False).split('/')[-1]:
            default.update({'fo_created_by_po_sync': False})
        return super(sale_order_sync, self).copy(cr, uid, id, default, context=context)

    def _manual_create_sync_picking_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        rule_obj = self.pool.get("sync.client.message_rule")
        rule_obj._manual_create_sync_message(cr, uid, self._name, res_id, return_info, rule_method, self._logger, context=context)

    def create_so(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Create an FO at %s from a PO (normal flow) at %s"%(cr.dbname, source))
        if not context:
            context = {}

        so_po_common_obj = self.pool.get('so.po.common')
        if context.get('restore_flag'):
            # UF-1830: Cannot create an FO from a recovery message
            so_po_common_obj.create_invalid_recovery_message(cr, uid, source, po_info.name, context)
            return "Recovery: cannot create the SO from a PO. Please inform the owner of the PO " + po_info.name + " to cancel it and to recreate a new process."

        context['no_check_line'] = True
        po_dict = po_info.to_dict()

        header_result = {}
        so_po_common_obj.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)

        if header_result.get('currency_id') and header_result.get('pricelist_id'):
            if not self.pool.get('product.pricelist').search_exist(cr, uid, [('id', '=', header_result['pricelist_id']), ('currency_id', '=', header_result['currency_id'])]):
                po_cur = self.pool.get('res.currency').read(cr, uid, header_result['currency_id'], ['name'], context=context)
                raise Exception, "Wrong FO/PO Currency on partner: please set FO/PO currency to %s on partner %s" % (po_cur['name'], source)

        header_result['order_line'] = so_po_common_obj.get_lines(cr, uid, source, po_info, False, False, False, True, context)
        # [utp-360] we set the confirmed_delivery_date to False directly in creation and not in modification
        order_line = []
        for line in header_result['order_line']:
            line[2].update({'confirmed_delivery_date': False, 'source_sync_line_id': line[2]['sync_order_line_db_id'], 'sync_linked_pol': so_po_common_obj.migrate_ref(line[2]['sync_order_line_db_id'])})
            order_line.append((0, 0, line[2]))
        header_result['order_line'] = order_line

        default = {}
        default.update(header_result)
        default['fo_created_by_po_sync'] = True
        default['procurement_request'] = False

        context['procurement_request'] = False

        so_id = self.create(cr, uid, default , context=context)
        name = self.browse(cr, uid, so_id, context).name
        if 'order_type' in header_result:
            if header_result['order_type'] in ['loan', 'loan_return']:
                # UTP-392: Look for the PO of this loan, and update the reference of source document of that PO to this new FO
                # First, search the original PO via the client_order_ref stored in the FO
                ref = po_info.origin
                if ref:
                    ref = source + "." + ref
                    po_object = self.pool.get('purchase.order')
                    po_ids = po_object.search(cr, uid, [('partner_ref', '=',
                                                         ref)], order='NO_ORDER', context=context)

                    # in both case below, the FO become counter part
                    if po_ids: # IF the PO Loan has already been created, if not, just update the value reference, then when creating the PO loan, this value will be updated
                        # link the FO loan to this PO loan
                        po_object.write(cr, uid, po_ids, {'origin': name}, context=context)

        # reset confirmed_delivery_date to all lines
#        so_line_obj = self.pool.get('sale.order.line')

        # [utp-360] we set the confirmed_delivery_date to False directly in creation and not in modification
#        for order in self.browse(cr, uid, [so_id], context=context):
#            for line in order.order_line:
#                so_line_obj.write(cr, uid, [line.id], {'confirmed_delivery_date': False})

        so_po_common_obj.update_next_line_number_fo_po(cr, uid, so_id, self, 'sale_order_line', context)

        # Just to print the result message when the sync message got executed
        message = "The FO " + name + " created successfully, linked to the PO " + po_info.name + " at " + source
        self._logger.info(message)
        return message

    def validated_po_update_validated_so(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Update the validated FO at %s when the relevant PO got validated at %s"%(cr.dbname, source))
        if not context:
            context = {}
        context['no_check_line'] = True

        po_dict = po_info.to_dict()
        so_po_common_obj = self.pool.get('so.po.common')

        header_result = {}
        so_po_common_obj.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        so_id = so_po_common_obj.get_original_so_id(cr, uid, po_info.partner_ref, context)

        header_result['order_line'] = so_po_common_obj.get_lines(cr, uid, source, po_info, False, so_id, True, False, context)

        default = {}
        default.update(header_result)

        self.write(cr, uid, so_id, default, context=context)

        # Just to print the result message when the sync message got executed
        name = self.browse(cr, uid, so_id, context).name
        message = "The FO " + name + " updated successfully, as its PO partner got updated " + po_info.name + " at " + source
        self._logger.info(message)
        return message

    def update_sub_so_ref(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Update the PO references from %s to the FO, including its sub-FOs at %s"%(source, cr.dbname))
        if not context:
            context = {}

        context['no_check_line'] = True
        so_po_common_obj = self.pool.get('so.po.common')
        so_id = so_po_common_obj.get_original_so_id(cr, uid, po_info.partner_ref, context)
        if not so_id:
            if context.get('restore_flag'):
                # UF-1830: Create a message to remove the invalid reference to the inexistent document
                so_po_common_obj = self.pool.get('so.po.common')
                so_po_common_obj.create_invalid_recovery_message(cr, uid, source, po_info.name, context)
                return "Recovery: the reference on " + po_info.name + " at " + source + " will be set to void."
            raise Exception, "Cannot find the original FO with the given info."

        so_value = self.browse(cr, uid, so_id)
        client_order_ref = source + "." + po_info.name

        if not so_value.client_order_ref or client_order_ref != so_value.client_order_ref: # only issue a write if the client_order_reference is not yet set!
            self.write(cr, uid, so_id, {'client_order_ref': client_order_ref} , context=context)

        '''
            Now search all sourced-FOs and update the reference if they have not been set at the moment of sourcing
            The person at coordo just does the whole push flow FO process until the end (sourcing the FO without sync before and thus the client_ref
            of the sourced FO will have no client_ref)
        '''
        line_ids = self.search(cr, uid, [('original_so_id_sale_order', '=', so_id)], context=context)
        for line in line_ids:
            temp = self.browse(cr, uid, line).client_order_ref
            if not temp: # only issue a write if the client_order_reference is not yet set!
                self.write(cr, uid, line, {'client_order_ref': client_order_ref} , context=context)

        # Just to print the result message when the sync message got executed
        message = "The FO " + so_value.name + " updated successfully, as the partner PO " + po_info.name + " got updated at " + source
        self._logger.info(message)
        return message

    # UF-1830: reset automatically the reference to the partner object to become void due to the recovery event
    def reset_ref_by_recovery_mode(self, cr, uid, source, values, context=None):
        self._logger.info("+++!!! Reset the reference in %s due to the recovery in %s"%(cr.dbname, source))
        if not context:
            context = {}
        context.update({'active_test': False})
        message = False
        recovery = source + ".invalid_by_recovery"

        # Get the type of the object, in order to retrieve the right documents for resetting the reference
        # If there is no document referred to the given ref, just ignore it
        name = values.name
        if name:
            if name.find("PO") >= 0:
                object = self.pool.get('purchase.order')
                ids = object.search(cr, uid, [('name', '=', name)], context=context)
                if ids and ids[0]:
                    cr.execute('update purchase_order set partner_ref=%s where id in %s', (recovery, tuple(ids)))

            elif name.find("FO") >= 0:
                object = self.pool.get('sale.order')
                ids = object.search(cr, uid, [('name', '=', name)], context=context)
                if ids and ids[0]:
                    cr.execute('update sale_order set client_order_ref=%s where id in %s', (recovery,tuple(ids)))

            elif name.find("OUT") >= 0:
                object = self.pool.get('stock.picking')
                ids = object.search(cr, uid, [('name', '=', name)], context=context)
                if ids and ids[0]:
                    cr.execute('update stock_picking set in_ref=%s where id in %s', (recovery, tuple(ids)))
            elif name.find("SHIP") >= 0:
                object = self.pool.get('shipment')
                ids = object.search(cr, uid, [('name', '=', name)], context=context)
                if ids and ids[0]:
                    cr.execute('update shipment set in_ref=%s where id in %s', (recovery, tuple(ids)))
            elif name.find("IN") >= 0:
                object = self.pool.get('stock.picking')
                ids = object.search(cr, uid, [('name', '=', name)], context=context)
                if ids and ids[0]:
                    cr.execute('update stock_picking set shipment_ref=%s where id in %s', (recovery, tuple(ids)))
            else:
                message = "The reference object is not found in the current instance: " + name

        if not message:
            message = "The reference in " + name + " becomes now VOID due to the recovery event at " + source
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

sale_order_sync()
