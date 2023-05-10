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
import uuid

from sync_client import get_sale_purchase_logger
from sync_client import SyncException
from sync_client.log_sale_purchase import RunWithoutException


class purchase_order_line_sync(osv.osv):
    _inherit = 'purchase.order.line'

    def _get_sync_local_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.partner_id.partner_type not in ['internal','section','intermission']:
                res[pol.id] = False
            elif pol.state == 'draft':
                res[pol.id] = False
            elif pol.state.startswith('validated'):
                pol_identifier = self.get_sd_ref(cr, uid, pol.id, context=context)
                sent_ok = self.pool.get('sync.client.message_to_send').search_exist(cr, 1, [
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

        debug = False
        logger = logging.getLogger('------sync.purchase.order.line')

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
            raise Exception("Cannot find the parent PO with partner ref %s" % partner_ref)

        # search the PO line to update:
        pol_id = self.search(cr, uid, [('sync_linked_sol', '=', sol_dict['sync_local_id'])], limit=1, context=context)
        if not pol_id and sol_dict.get('sync_linked_pol'):
            pol_id_msg = sol_dict['sync_linked_pol'].split('/')[-1]
            pol_id = self.search(cr, uid, [('order_id', '=', po_ids[0]), ('id', '=', int(pol_id_msg))], context=context)

        # retrieve data
        try:
            pol_values = self.pool.get('so.po.common').get_line_data(cr, uid, source, sol_info, context)
        except Exception as e:
            if not pol_id:
                if hasattr(e, 'value'):
                    msg = e.value
                else:
                    msg = '%s' % e
                raise SyncException(msg, target_object='purchase.order', target_id=po_ids[0])
            else:
                raise

        order_name = sol_dict['order_id']['name']
        pol_values['order_id'] = po_ids[0]
        pol_values['sync_linked_sol'] = sol_dict['sync_local_id']
        pol_values['modification_comment'] = sol_dict.get('modification_comment', False)
        pol_values['from_dpo_line_id'] = sol_dict.get('dpo_line_id') and sol_dict.get('dpo_line_id', {}).get('.id', False) or False
        pol_values['from_dpo_id'] = sol_dict.get('dpo_id') and sol_dict.get('dpo_id', {}).get('.id', False) or False
        pol_values['from_dpo_esc'] = sol_dict.get('dpo_id') and sol_dict.get('dpo_id', {}).get('partner_type', False) == 'esc' or False
        pol_values['esti_dd'] = sol_dict.get('esti_dd', False)
        if 'line_number' in pol_values:
            del(pol_values['line_number'])



        if debug:
            logger.info('sol_dict: %s' % sol_dict)

        # the current line has been resourced in other instance, so we set it as "sourced_n" in current instance PO in order to
        # create the resourced line in current instance IR:
        ress_fo = False
        original_sol_id = False
        if sol_dict.get('resourced_original_line'):
            pol_values['set_as_resourced'] = True
            if sol_dict.get('resourced_original_remote_line') and not pol_id:
                pol_values['resourced_original_line'] = int(sol_dict['resourced_original_remote_line'].split('/')[-1])
            elif sol_dict.get('original_line_id') and not sol_dict.get('is_line_split') and not pol_id:
                original_sol_id = sol_dict['original_line_id']['id'].split('/')[-1]
            elif sol_dict['resourced_original_line'].get('id') and not pol_id:
                original_sol_id = sol_dict['resourced_original_line']['id'].split('/')[-1]

            if original_sol_id:
                orig_line_ids = self.search(cr, uid, [
                    ('order_id', '=', pol_values['order_id']),
                    ('sync_linked_sol', 'ilike', '%%/%s' % original_sol_id)
                ], context=context)
                if orig_line_ids:
                    pol_values['resourced_original_line'] = orig_line_ids[0]

                # link our resourced PO line with corresponding resourced FO line:
            if pol_values.get('resourced_original_line'):
                orig_po_line = self.browse(cr, uid, pol_values['resourced_original_line'], fields_to_fetch=['linked_sol_id', 'analytic_distribution_id', 'origin'], context=context)
                in_lines_ids = self.pool.get('stock.move').search(cr, uid, [
                    ('purchase_line_id', '=', orig_po_line.id),
                    ('type', '=', 'in'),
                    ('in_forced', '=', True)
                ], context=context)
                if in_lines_ids:
                    orig_po_line = self.browse(cr, uid, pol_values['resourced_original_line'], fields_to_fetch=['line_number', 'order_id'], context=context)
                    real_forced = self.pool.get('stock.move').search(cr, uid, [('id', 'in', in_lines_ids), ('state', 'in', ['cancel', 'cancel_r', 'done'])], limit=3, context=context)
                    in_forced = self.pool.get('stock.move').browse(cr, uid, real_forced or in_lines_ids[0:4], fields_to_fetch=['picking_id'], context=context)
                    raise RunWithoutException("%s: Line %s forced on %s, unable to C/R" % (orig_po_line.order_id.name, orig_po_line.line_number, ','.join([x.picking_id.name for x in in_forced])))
                if orig_po_line.linked_sol_id:
                    resourced_sol_id = self.pool.get('sale.order.line').search(cr, uid, [('resourced_original_line', '=', orig_po_line.linked_sol_id.id)], context=context)
                    ress_fo = orig_po_line.linked_sol_id.order_id.id
                    if resourced_sol_id:
                        pol_values['linked_sol_id'] = resourced_sol_id[0]
                        self.pool.get('sale.order.line').write(cr, uid, resourced_sol_id, {'set_as_sourced_n': True}, context=context)
                    pol_values['origin'] = orig_po_line.origin
                if orig_po_line.analytic_distribution_id and not pol_values.get('analytic_distribution_id'):
                    # intersection / mission: copy original AD
                    pol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, orig_po_line.analytic_distribution_id.id, {}, context=context)

        # update PO line:
        kind = ""
        pol_updated = False
        if not pol_id: # then create new PO line
            kind = 'new line'
            pol_values['line_number'] = sol_dict['line_number']
            pol_values['created_by_sync'] = True
            if sol_dict['is_line_split']:
                sync_linked_sol = int(sol_dict['original_line_id'].get('id').split('/')[-1]) if sol_dict['original_line_id'] else False
                if not sync_linked_sol:
                    raise Exception("Original PO line not found when trying to split the PO line")
                sync_linked_sol = '%s/%s' % (order_name, sync_linked_sol)
                orig_pol = self.search(cr, uid, [('sync_linked_sol', '=', sync_linked_sol)], context=context)
                if not orig_pol:
                    raise Exception("Original PO line not found when trying to split the PO line")
                orig_pol_info = self.browse(cr, uid, orig_pol[0], fields_to_fetch=['linked_sol_id', 'line_number', 'origin', 'state', 'analytic_distribution_id'], context=context)
                pol_values['original_line_id'] = orig_pol[0]
                pol_values['line_number'] = orig_pol_info.line_number
                if orig_pol_info.analytic_distribution_id and not pol_values.get('analytic_distribution_id'):
                    # intersection / mission: copy original AD
                    pol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, orig_pol_info.analytic_distribution_id.id, {}, context=context)
                if orig_pol_info.linked_sol_id:
                    pol_values['origin'] = orig_pol_info.linked_sol_id.order_id.name
                    # re-synch : line split on last partner, should trigger update to original partner even if the state on the original line is not changed
                    if not orig_pol_info.linked_sol_id.order_id.procurement_request and orig_pol_info.linked_sol_id.order_id.partner_type not in ('esc', 'external'):
                        self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', orig_pol_info.linked_sol_id.id, {},
                                                                                              'purchase.order.line.sol_update_original_pol', self.pool.get('sale.order.line')._logger, check_identifier=False, context=context)

            if sol_dict['in_name_goods_return'] and not sol_dict['is_line_split']:
                # in case of FO from missing/replacement claim
                original_claim_line = self.pool.get('purchase.order.line').search(cr, uid, [('line_number', '=', pol_values['line_number']), ('order_id', '=', po_ids[0]), ('state', 'not in', ['cancel', 'cancel_r'])])
                if original_claim_line:
                    pol_values['resourced_original_line'] = original_claim_line[0]
                    # if SOL claim if for full qty of PO line, just link the existing POL with the new claim SOL
                    claim_po_lines = self.pool.get('purchase.order.line').browse(cr, uid, original_claim_line, fields_to_fetch=['origin', 'product_qty', 'state'], context=context)
                    for claim_po_line in claim_po_lines:
                        if claim_po_line.state == 'confirmed' and claim_po_line.product_qty == pol_values['product_uom_qty']:
                            self.pool.get('purchase.order.line').write(cr, uid, [claim_po_line.id], {'sync_linked_sol': pol_values['sync_linked_sol']}, context=context)
                            return 'Claim missing processed'

                pol_values['origin'] = self.pool.get('purchase.order').browse(cr, uid, po_ids[0], fields_to_fectch=['origin'], context=context).origin
                pol_values['from_synchro_return_goods'] = True

            # case of PO line doesn't exists, so created in FO (COO) and pushed back in PO (PROJ)
            # so we have to create this new PO line:
            pol_values['set_as_sourced_n'] = True if not sol_dict.get('resourced_original_line') and not sol_dict.get('is_line_split') else False
            if sol_dict['state'] in ['cancel', 'cancel_r']:
                pol_values['cancelled_by_sync'] = True
            try:
                new_pol = self.create(cr, uid, pol_values, context=context)
            except Exception as e:
                raise SyncException(hasattr(e, 'value') and e.value or '%s' % e , target_object='purchase.order', target_id=po_ids[0])
            if debug:
                logger.info("create pol id: %s, values: %s" % (new_pol, pol_values))

            # if original pol has already been confirmed (and so has linked IN moves), then we re-attach moves to the right new split pol:
            if sol_dict['is_line_split']:
                in_picking = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', '=', pol_values['order_id']), ('state', '=', 'assigned')], context=context)
                in_dom = [('purchase_line_id', '=', orig_pol[0]), ('type', '=', 'in'), ('state', '=', 'assigned'), ('picking_id', 'in', in_picking)]
                linked_in_moves = self.pool.get('stock.move').search(cr, uid, in_dom + [('product_qty', '=', pol_values['product_qty'])], limit=1, context=context)
                if not linked_in_moves:
                    linked_in_moves = self.pool.get('stock.move').search(cr, uid, in_dom + [('product_qty', '>', pol_values['product_qty'])], limit=1, context=context)
                    if linked_in_moves:
                        new_move = self.pool.get('stock.move').split(cr, uid, linked_in_moves[0], pol_values['product_uom_qty'], False, context=context)
                        self.pool.get('stock.move').write(cr, uid, new_move, {'purchase_line_id': new_pol}, context=context)
                else:
                    self.pool.get('stock.move').write(cr, uid, linked_in_moves, {'purchase_line_id': new_pol}, context=context)

                # also SYS-INT
                if linked_in_moves:
                    sys_int_picking_ids = self.pool.get('stock.picking').search(cr, uid, [
                        ('type', '=', 'internal'), ('subtype', '=', 'sysint'), ('state', 'not in', ['cancel', 'done']), ('purchase_id', '=', pol_values['order_id'])
                    ], context=context)
                    sys_move_dom = [('picking_id', 'in', sys_int_picking_ids), ('purchase_line_id','=', orig_pol[0]), ('state', '=', 'confirmed')]
                    sys_int_move_ids = self.pool.get('stock.move').search(cr, uid, sys_move_dom + [('product_qty', '>', pol_values['product_qty'])], limit=1, context=context)
                    if sys_int_move_ids:
                        new_sys_int = self.pool.get('stock.move').split(cr, uid, sys_int_move_ids[0], pol_values['product_uom_qty'], False, context=context)
                        self.pool.get('stock.move').write(cr, uid, new_sys_int, {'purchase_line_id': new_pol}, context=context)
                    else:
                        sys_int_move_ids = self.pool.get('stock.move').search(cr, uid, sys_move_dom + [('product_qty', '=', pol_values['product_qty'])], limit=1, context=context)
                        if sys_int_move_ids:
                            self.pool.get('stock.move').write(cr, uid, sys_int_move_ids, {'purchase_line_id': new_pol}, context=context)

            if sol_dict['in_name_goods_return'] and not sol_dict['is_line_split']:  # update the stock moves PO line id
                in_name = sol_dict['in_name_goods_return'].split('.')[-1]
                pick_id = pick_obj.search(cr, uid, [('name', '=', in_name)], limit=1, context=context)[0]
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', pick_id),
                                                     ('line_number', '=', pol_values['line_number'])], context=context)
                move_obj.write(cr, uid, move_ids, ({'purchase_line_id': new_pol}), context=context)
                # update qty on original claim pol line
                claim_pol_id = self.pool.get('purchase.order.line').search(cr, uid, [('line_number', '=', pol_values['line_number']), ('order_id', '=', po_ids[0]), ('product_qty', '>=', pol_values['product_uom_qty']), ('state', '=', 'confirmed')], context=context)
                if claim_pol_id:
                    orig_qty = self.pool.get('purchase.order.line').read(cr, uid, claim_pol_id[0], ['product_qty'], context=context)['product_qty']
                    self.pool.get('purchase.order.line').write(cr, uid, claim_pol_id[0], {'product_qty': orig_qty - pol_values['product_uom_qty'], 'is_line_split': True}, context=context)
                    self.update_fo_lines(cr, uid, [claim_pol_id[0]], for_claim=pol_values['product_uom_qty'], context=context)
                    # check if original claim po line must be closed
                    pending_move = self.pool.get('stock.move').search(cr, uid, [('type', '=', 'in'), ('purchase_line_id', '=', claim_pol_id[0]), ('state', 'not in', ['done', 'cancel', 'cancel_r'])], context=context)
                    if not pending_move:
                        wf_service.trg_validate(uid, 'purchase.order.line', claim_pol_id[0], 'done', cr)
            pol_updated = new_pol
            pol_state = ''
            parent_so_id = False

            #### Create the linked IR/FO line: except when set_as_validated_n=True (new line added in PO coo, this value already creates an IR/FO line when pol is created)
            if not pol_values.get('origin') and ress_fo:
                parent_so_id = ress_fo
            elif not pol_values.get('origin') and sol_dict.get('sync_pushed_from_po'):
                # resync try to push to original FO/IR
                cr.execute('''
                    select so.id
                    from purchase_order_line pol, sale_order_line sol, sale_order so
                    where
                        pol.order_id=%s and
                        pol.linked_sol_id = sol.id and
                        sol.order_id = so.id and
                        so.state not in ('draft', 'cancel', 'done')
                    limit 1
                ''', (pol_values['order_id'],))
                result = cr.fetchone()
                if result and result[0]:
                    parent_so_id = result[0]
            if pol_values.get('origin'):
                parent_so_ids = self.pool.get('sale.order').search(cr, uid, [
                    ('name', '=', pol_values['origin']),
                    ('procurement_request', 'in', ['t', 'f']),
                ], context=context)
                if parent_so_ids:
                    parent_so_id = parent_so_ids[0]
            if parent_so_id:
                #self.create_sol_from_pol(cr, uid, [new_pol], parent_so_id, context=context)
                self.update_fo_lines(cr, uid, [new_pol], so_id=parent_so_id, context=context)

        else: # regular update
            pol_updated = pol_id[0]
            kind = 'update'
            pol_to_update = [pol_updated]
            confirmed_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, [], 'confirmed', context=context)
            po_line = self.browse(cr, uid, pol_updated, fields_to_fetch=['state', 'product_qty', 'price_unit', 'cv_line_ids'], context=context)
            pol_state = po_line.state
            if sol_dict['state'] in ['cancel', 'cancel_r']:
                pol_values['cancelled_by_sync'] = True
            if self.pool.get('purchase.order.line.state').get_sequence(cr, uid, [], po_line.state, context=context) <= confirmed_sequence:
                # if the state is less than confirmed we update the PO line
                if debug:
                    logger.info("Write pol id: %s, values: %s" % (pol_to_update, pol_values))
                if po_line.cv_line_ids and po_line.cv_line_ids[0] and po_line.state == 'confirmed' and po_line.product_qty - pol_values.get('product_qty', po_line.product_qty) > 0.01:
                    # update qty on confirmed po line: update CV line if any
                    # from_cancel = True : do not trigger wkf transition draft -> open
                    self.pool.get('account.invoice')._update_commitments_lines(cr, uid, [po_ids[0]], cvl_amount_dic={
                        po_line.cv_line_ids[0].id: round((po_line.product_qty - pol_values['product_qty'])*po_line.price_unit, 2)
                    }, from_cancel=True, context=context)
                self.pool.get('purchase.order.line').write(cr, uid, pol_to_update, pol_values, context=context)

        if debug:
            logger.info("%s pol_id: %s, sol state: %s" % (kind, pol_updated, sol_dict['state']))
            cr.execute("select act.name, inst.res_id from wkf_instance inst ,wkf_workitem item, wkf_activity act where act.id=item.act_id and item.inst_id=inst.id and inst.res_id=%s and inst.res_type='purchase.order.line'", (pol_updated,))
            logger.info("Wkf pol state: %s" % cr.fetchall())
            dd = self.pool.get('purchase.order.line').read(cr, uid, pol_updated, ['line_number', 'state', 'product_qty', 'order_id', 'linked_sol_id', 'product_id'])

            logger.info('Pol data %s ' % dd)
            all_pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', dd['order_id'][1])])
            logger.info('other pol: %s' % self.pool.get('purchase.order.line').read(cr, uid, all_pol_ids, ['line_number', 'state', 'product_qty', 'linked_sol_id', 'product_id']))
            logger.info('pol_state %s' % pol_state)


        cancel_type = False
        # Wkf action:
        if sol_dict['state'] in ('sourced', 'sourced_v'):
            if pol_state in 'sourced_n':
                self.pool.get('purchase.order.line').action_sourced_v(cr, uid, [pol_updated], context=context)
            elif pol_state in ('sourced_sy', 'sourced_v'):
                self.update_fo_lines(cr, uid, [pol_updated], context=context)

        if sol_dict['state'] in ('sourced', 'sourced_n'):
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'sourced_sy', cr)
        elif sol_dict['state'] == 'sourced_v':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'sourced_v', cr)
        elif sol_dict['state'] == 'validated':
            wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'validated', cr)
        elif sol_dict['state'] == 'confirmed':
            if pol_state == 'confirmed':
                # pol already confirmed: just update the linked IR line but do no recreate IN
                self.update_fo_lines(cr, uid, [pol_updated], context=context)
            else:
                try:
                    wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, 'confirmed', cr)
                except Exception as e:
                    pol_info = self.pool.get('purchase.order.line').browse(cr, uid, pol_updated, fields_to_fetch=['analytic_distribution_id', 'order_id', 'created_by_sync', 'line_number'], context=context)
                    if pol_info.created_by_sync and not pol_info.analytic_distribution_id and not pol_info.order_id.analytic_distribution_id:
                        if hasattr(e, 'value'):
                            msg = e.value
                        else:
                            msg = '%s' % e
                        raise SyncException(msg, target_object='purchase.order.ad', target_id=po_ids[0], line_number=pol_info.line_number)
                    raise
        elif sol_dict['state'] == 'cancel' or (sol_dict['state'] == 'done' and sol_dict.get('from_cancel_out')):
            cancel_type = 'cancel'
        elif sol_dict['state'] == 'cancel_r':
            cancel_type = 'cancel_r'
        elif debug:
            logger.info('No wkf trigger')

        if cancel_type:
            in_lines_ids = self.pool.get('stock.move').search(cr, uid, [
                ('purchase_line_id', '=', pol_updated),
                ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                ('type', '=', 'in'),
                ('in_forced', '=', True)
            ], context=context)
            if in_lines_ids:
                if cancel_type == 'cancel':
                    self.pool.get('stock.move').action_cancel(cr, uid, in_lines_ids, context=context)
            else:
                wf_service.trg_validate(uid, 'purchase.order.line', pol_updated, cancel_type, cr)
        pol_data = self.pool.get('purchase.order.line').read(cr, uid, pol_updated, ['order_id', 'line_number'], context=context)
        message = "+++ Purchase Order %s %s: line number %s (id:%s) has been updated +++" % (kind, pol_data['order_id'][1], pol_data['line_number'], pol_updated)
        logger.info(message)

        ## Debug
        if debug and pol_updated:
            linked_fo_ir = self.pool.get('purchase.order.line').browse(cr, uid, pol_updated, fields_to_fetch=['linked_sol_id', 'order_id'])
            if not linked_fo_ir.linked_sol_id:
                logger.info("Not linked to any FO/IR")
            else:
                ir_l_ids = self.pool.get('sale.order.line').search(cr, uid, [('order_id', '=', linked_fo_ir.linked_sol_id.order_id.id)])
                if ir_l_ids:
                    logger.info( 'FO/IR %s, lines: %s' % (linked_fo_ir.linked_sol_id.order_id.name, self.pool.get('sale.order.line').read(cr, uid, ir_l_ids, ['line_number', 'state', 'product_uom_qty'])))
                    cr.execute("select act.name, inst.res_id from wkf_instance inst ,wkf_workitem item, wkf_activity act where act.id=item.act_id and item.inst_id=inst.id and inst.res_id in %s and inst.res_type='sale.order.line'", (tuple(ir_l_ids),))
                    logger.info("Wkf foline: %s" % cr.fetchall())

            all_pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', linked_fo_ir.order_id.id)])
            logger.info('Final pol %s' % self.pool.get('purchase.order.line').read(cr, uid, all_pol_ids, ['line_number', 'state', 'product_qty']))
        ## Debug

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
            raise Exception("No Order line DB ID given in the sync. message")

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
                    cr, 1,
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
            string="Validated and Synced"),
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
            raise Exception("Cannot find the original PO with the given info.")

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
            if so_info.order_type in ('loan', 'loan_return', 'donation_st', 'donation_exp'):
                if 'analytic_distribution_id' in header_result:
                    del header_result['analytic_distribution_id']
            else:
                raise Exception("Sorry, Push Flow for intersection partner is only available for Donation or Loan FOs! " + source)

        # the case of intermission, the AD will be updated below, after creating the PO
        if partner_type == 'intermission' and 'analytic_distribution_id' in header_result:
            del header_result['analytic_distribution_id']

        default = {}
        default.update(header_result)

        if po_id: # only update the PO - should never be in here!
            self.write(cr, uid, po_id, default, context=context)
        else:
            # create a new PO, then send it to Validated state

            # do not eat a seq
            tmp_name = '%s' % uuid.uuid4()
            default['name'] = tmp_name
            po_id = self.create(cr, uid, default , context=context)

            # no constraint raised, we can create the default name and save gap in ref
            new_name = self.pool.get('ir.sequence').get(cr, uid, 'purchase.order')
            self.write(cr, uid, po_id, {'name': new_name}, context=context)
            audit_log_line = self.pool.get('audittrail.log.line')
            audit_ids = audit_log_line.search(cr, uid,
                                              [('method', '=', 'create'), ('res_id', '=', po_id), ('new_value', '=', tmp_name), ('object_id.model', '=', 'purchase.order')],
                                              context=context)
            if audit_ids:
                audit_log_line.write(cr, uid, audit_ids, {'new_value': new_name, 'new_value_text': new_name}, context=context)

        # update the next line number for the PO if needed
        so_po_common.update_next_line_number_fo_po(cr, uid, po_id, self, 'purchase_order_line', context)

        name = self.browse(cr, uid, po_id, context=context).name
        message = "The PO " + name + " is created by sync and linked to the FO " + so_info.name + " by Push Flow at " + source
        self._logger.info(message)

        return message

    def check_existing_po(self, cr, uid, source, so_dict):
        if not source:
            raise Exception("The partner is missing!")

        name = source + '.' + so_dict.get('name')
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            return False
        return po_ids[0]


    def check_mandatory_fields(self, cr, uid, so_dict):
        if not so_dict.get('delivery_confirmed_date'):
            raise Exception("The delivery confirmed date is missing - please verify the values of the sync message!")

        if not so_dict.get('state'):
            raise Exception("The state of the split FO is missing - please verify the values of the sync message!")

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
            raise Exception("Cannot find the original PO with the given info.")

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
            raise Exception("The split PO linked to " + so_info.name + "at " + source + " not found!")

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
