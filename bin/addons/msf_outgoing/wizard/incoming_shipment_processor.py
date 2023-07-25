# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields
from osv import osv
from tools.translate import _

from msf_outgoing import INTEGRITY_STATUS_SELECTION
from msf_outgoing import PACK_INTEGRITY_STATUS_SELECTION
import threading



class in_family_processor(osv.osv):
    """
    IN family that merge some stock moves into one pack
    """
    _name = 'in.family.processor'
    _description = 'IN family'
    _rec_name = 'from_pack'
    _order = 'packing_list, from_pack'
    _columns = {
        'name': fields.char('IN family', size=64),
        'wizard_id': fields.many2one(
            'stock.incoming.processor',
            string='Wizard',
            required=True,
            ondelete='cascade',
            help="IN processing wizard",
        ),
        'from_pack': fields.integer(string='From p.'),
        'to_pack': fields.integer(string='To p.'),
        'pack_type': fields.many2one(
            'pack.type',
            string='Pack Type',
            ondelete='set null',
        ),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        'volume': fields.float('Volume', digits=(16,2)),
        'packing_list': fields.char('Supplier Packing List', size=30),
        'integrity_status': fields.selection(
            string='Integrity status',
            selection=[
                ('empty', ''),
                ('missing_weight', 'Weight is missing'),
            ],
            readonly=True,
        ),
        'move_ids': fields.one2many(
            'stock.move.in.processor',
            'pack_id',
            string='Moves',
        ),
    }

    _defaults = {
        'integrity_status': 'empty',
    }


    """
    Controller methods
    """
    def onchange_pack_type(self, cr, uid, ids, pack_type):
        """
        Update values of the in family from the stock pack selecetd
        """
        # Objects
        p_type_obj = self.pool.get('pack.type')

        res = {}

        if pack_type :
            # if 'pack_type' is not a list, turn it into list
            if isinstance(pack_type, (int, long)):
                pack_type = [pack_type]

            p_type = p_type_obj.browse(cr, uid, pack_type[0])

            res.update({
                'value': {
                    'length': p_type.length,
                    'width': p_type.width,
                    'height': p_type.height,
                },
            })

        return res

in_family_processor()


class stock_incoming_processor(osv.osv):
    """
    Incoming shipment processing wizard
    """
    _name = 'stock.incoming.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process an incoming shipment'


    def _get_display_process_to_ship_button(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}

        res = {}
        for wiz in self.browse(cr, uid, ids, fields_to_fetch=['linked_to_out', 'picking_id'], context=context):
            res[wiz.id] = False
            if wiz.picking_id and wiz.linked_to_out:
                if not self.pool.get('stock.move.in.processor').search_exist(cr, uid, [('wizard_id', '=', wiz.id),('pack_info_id', '=', False)], context=context):
                    res[wiz.id] = wiz.linked_to_out

        return res


    def _get_location_dest_active_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if there is draft moves on Picking Ticket
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = True
            if not wiz.picking_id:
                break
            sys_int_moves = self.pool.get('stock.move').search(cr, uid, [
                ('linked_incoming_move', 'in', [x.id for x in wiz.picking_id.move_lines]),
                ('type', '=', 'internal'),
            ], context=context)
            for sys_move in self.pool.get('stock.move').browse(cr, uid, sys_int_moves, context=context):
                if not sys_move.location_dest_id.active:
                    res[wiz.id] = False
                    break

        return res

    _columns = {
        'move_ids': fields.one2many(
            'stock.move.in.processor',
            'wizard_id',
            string='Moves',
        ),
        'family_ids': fields.one2many(
            'in.family.processor',
            'wizard_id',
            string='Families',
            help="Pack of products",
        ),
        'dest_type': fields.selection([
            ('to_cross_docking', 'To Cross Docking'),
            ('to_stock', 'To Stock'),
            ('default', 'Other Types'),
        ],
            string='Destination Type',
            readonly=False,
            required=True,
            help="The default value is the one set on each stock move line.",
        ),
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'),
        ],
            string='Source Type',
            readonly=False,
        ),
        'direct_incoming': fields.boolean(
            string='Direct to Requesting Location',
        ),
        'draft': fields.boolean('Draft'),
        'already_processed': fields.boolean('Already processed'),
        'linked_to_out': fields.char('If the IN is linked to a single Pick (same FO) give the type of delivery doc (standard / picking)', size=16),
        'register_a_claim': fields.boolean(
            string='Register a Claim to Supplier',
        ),
        'claim_partner_id': fields.many2one(
            'res.partner',
            string='Supplier',
            required=False,
        ),
        'claim_in_has_partner_id': fields.boolean(
            string='IN has Partner specified.',
            readonly=True,
        ),
        'claim_type': fields.selection(
            lambda s, cr, uid, context={}: s.pool.get('return.claim').get_in_claim_event_type(),
            string='Claim Type',
        ),
        'claim_replacement_picking_expected': fields.boolean(
            string='Replacement expected for Claim ?',
            help="An Incoming Shipment will be automatically created corresponding to returned products.",
        ),
        'claim_description': fields.text(
            string='Claim Description',
        ),
        'display_process_to_ship_button': fields.function(_get_display_process_to_ship_button, method=True, type='char', string='Process to ship'),
        'location_dest_active_ok': fields.function(_get_location_dest_active_ok, method=True, type='boolean', string='Dest location is inactive ?', store=False),
        'fields_as_ro': fields.boolean('Hide split/change prod', internal=True),
        'sequence_issue': fields.boolean('Issue with To ship'),
        'physical_reception_date': fields.datetime('Physical Reception Date'),
        'imp_shipment_ref': fields.char(string='Ship Reference from the IN VI import', size=256, readonly=True),
        'imp_filename': fields.char(size=128, string='Filename', readonly=True),
    }

    _defaults = {
        'dest_type': 'default',
        'direct_incoming': True,
        'draft': lambda *a: False,
        'already_processed': lambda *a: False,
    }


    # Models methods
    def create(self, cr, uid, vals, context=None):
        """
        Update the dest_type value according to picking
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        if not vals.get('picking_id', False):
            raise osv.except_osv(
                _('Error'),
                _('No picking defined !'),
            )

        picking = picking_obj.browse(cr, uid, vals.get('picking_id'), context=context)

        cr.execute("""
            select so.id, array_agg(distinct(out.name)), count(distinct(so.procurement_request)) from
            stock_move m
            left join stock_picking p on m.picking_id = p.id
            left join purchase_order_line pol on m.purchase_line_id = pol.id
            left join sale_order_line sol on sol.id = pol.linked_sol_id
            left join sale_order so on so.id = sol.order_id
            left join stock_picking out on out.sale_id = so.id and out.type = 'out' and (out.subtype = 'picking' and out.state='draft' or out.subtype = 'standard' and out.state in ('draft', 'confirmed', 'assigned'))
            where
                m.picking_id = %s and
                coalesce(p.claim, 'f') = 'f'
            group by so.id
            """, (vals.get('picking_id'), ))
        if cr.rowcount == 1:
            fetch_data = cr.fetchone()
            if fetch_data[2] > 1:
                # IN mixed with FO/IR
                vals['linked_to_out'] = False

            out_names = fetch_data[1]
            out_type = False
            for out_name in out_names:
                if out_name and out_name.startswith('OUT/'):
                    out_type = out_name
                    break
            if not out_type:
                out_type = out_names and len(out_names) == 1 and out_names[0] and out_names[0].startswith('PICK/') and 'picking' or False
            vals['linked_to_out'] = out_type
        else:
            vals['linked_to_out'] = False

        if not vals.get('dest_type', False):
            cd_move = move_obj.search(cr, uid, [
                ('picking_id', '=', picking.id),
                ('location_dest_id.cross_docking_location_ok', '=', True),
            ], count=True, context=context)
            in_move = move_obj.search(cr, uid, [
                ('picking_id', '=', picking.id),
                ('location_dest_id.input_ok', '=', True),
            ], count=True, context=context)

            if cd_move and in_move:
                vals['dest_type'] = 'default'
            elif not picking.backorder_id:
                if picking.purchase_id and picking.purchase_id.cross_docking_ok:
                    vals['dest_type'] = 'to_cross_docking'
                elif picking.purchase_id:
                    vals['dest_type'] = 'to_stock'
            elif picking.cd_from_bo or (cd_move and not in_move):
                vals['dest_type'] = 'to_cross_docking'
            elif not picking.cd_from_bo or (in_move and not cd_move):
                vals['dest_type'] = 'to_stock'

        if not vals.get('source_type', False):
            vals['source_type'] = 'default'

        if not vals.get('claim_partner_id', False):
            vals['claim_partner_id'] = picking.partner_id2.id

        return super(stock_incoming_processor, self).create(cr, uid, vals, context=context)

    def do_incoming_shipment(self, cr, uid, ids, context=None, check_mml=True):
        """
        Made some integrity check on lines and run the do_incoming_shipment of stock.picking
        """
        # Objects
        in_proc_obj = self.pool.get('stock.move.in.processor')
        picking_obj = self.pool.get('stock.picking')
        data_obj = self.pool.get('ir.model.data')
        wizard_obj = self.pool.get('stock.incoming.processor')

        if context is None:
            context = {}

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !'),
            )

        # Delete drafts
        wizard_obj.write(cr, uid, ids, {'draft': False}, context=context)

        to_unlink = []

        picking_id = None
        for proc in self.browse(cr, uid, ids, context=context):

            check_proc_mml = check_mml and proc.picking_id.type == 'in' and not proc.picking_id.purchase_id
            has_mml_error = []

            picking_id = proc.picking_id.id

            if proc.picking_id.type != 'in':
                raise osv.except_osv(
                    _('Error'),
                    _('This object: %s is not an Incoming Shipment') % (proc.picking_id.name)
                )

            total_qty = 0.00

            if proc.already_processed:
                raise osv.except_osv(
                    _('Error'),
                    _('You cannot process two times the same IN. Please '\
                      'return to IN form view and re-try.'),
                )

            if proc.picking_id.state not in ('assigned', 'shipped', 'updated'):
                raise osv.except_osv(
                    _('Error'),
                    _('You can not process an Incoming Shipment which is not Available, Available Shipped or Available Updated.'),
                )

            for line in proc.move_ids:
                if line.product_id and line.quantity:  # Check constraints on products
                    self.pool.get('product.product')._get_restriction_error(cr, uid, [line.product_id.id],
                                                                            {'location_id': line.location_id.id, 'location_dest_id': line.move_id.location_dest_id.id, 'obj_type': 'in', 'partner_type': proc.picking_id.partner_id.partner_type},
                                                                            context=context)
                # If one line as an error, return to wizard
                if line.integrity_status not in ['empty', 'missing_1', 'to_smaller_than_from', 'overlap', 'gap', 'missing_weight']:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': proc._name,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'res_id': line.wizard_id.id,
                        'target': 'new',
                        'context': context,
                    }
                if check_proc_mml and line.quantity and line.mml_status == 'F':
                    has_mml_error.append('L%s %s' % (line.line_number, line.product_id.default_code))

            self.write(cr, uid, [proc.id], {
                'already_processed': True,
            }, context=context)

            if has_mml_error:
                cr.rollback()
                msg = self.pool.get('message.action').create(cr, uid, {
                    'title':  _('Warning'),
                    'message': '<h2>%s</h2><h3>%s</h3>' % (_('You are about to process  this line(s) containing a product which does not conform to MML:'),
                                                           ', '.join(has_mml_error)),
                    'yes_action': lambda cr, uid, context: self.do_incoming_shipment(cr, uid, ids, context=context, check_mml=False),
                    'yes_label': _('Process Anyway'),
                    'no_label': _('Close window'),
                }, context=context)
                return self.pool.get('message.action').pop_up(cr, uid, [msg], context=context)




            for line in proc.move_ids:
                # if no quantity, don't process the move
                if not line.quantity:
                    to_unlink.append(line.id)
                    continue

                total_qty += line.quantity

                if line.exp_check \
                   and not line.lot_check \
                   and not line.prodlot_id \
                   and line.expiry_date:
                    if line.type_check == 'in':
                        # US-838: The method has been moved to addons/stock_batch_recall/product_expiry.py
                        prodlot_id = self.pool.get('stock.production.lot')._get_prodlot_from_expiry_date(cr, uid, line.expiry_date, line.product_id.id, context=context)
                        in_proc_obj.write(cr, uid, [line.id], {'prodlot_id': prodlot_id}, context=context)
                    else:
                        # Should not be reached thanks to UI checks
                        raise osv.except_osv(
                            _('Error !'),
                            _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...')
                        )

            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _("You have to enter the quantities you want to process before processing the move")
                )

            if proc.direct_incoming and not proc.location_dest_active_ok:
                self.write(cr, uid, [proc.id], {'direct_incoming': False}, context=context)

        if to_unlink:
            in_proc_obj.unlink(cr, uid, to_unlink, context=context)

        cr.commit()
        new_thread = threading.Thread(target=picking_obj.do_incoming_shipment_new_cr, args=(cr, uid, ids, context))
        new_thread.start()
        new_thread.join(30.0)

        if new_thread.isAlive():
            view_id = data_obj.get_object_reference(cr, uid, 'delivery_mechanism', 'stock_picking_processing_info_form_view')[1]
            prog_id = picking_obj.update_processing_info(cr, uid, picking_id, prog_id=False, values={}, context=context)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking.processing.info',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': prog_id,
                'view_id': [view_id],
                'context': context,
                'target': 'new',
            }

        if context.get('from_simu_screen'):
            view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_picking_in_form')[1]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': picking_id,
                'view_id': [view_id],
                'view_mode': 'form, tree',
                'view_type': 'form',
                'target': 'crush',
                'context': context,
            }

        return {'type': 'ir.actions.act_window_close'}

    """
    Controller methods
    """
    def onchange_dest_type(self, cr, uid, ids, dest_type, picking_id=False, context=None):
        """
        Raise a message if the user change a default dest type (cross docking or IN stock).
        @param dest_type: Changed value of dest_type.
        @return: Dictionary of values.
        """
        # Objects
        pick_obj = self.pool.get('stock.picking')
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

        if context is None:
            context = {}

        if not picking_id:
            return {}

        result = {}

        picking = pick_obj.browse(cr, uid, picking_id, context=context)
        if picking.purchase_id and dest_type != 'to_cross_docking'and picking.purchase_id.cross_docking_ok:
            # display warning
            result['warning'] = {
                'title': _('Error'),
                'message': _('You want to receive the IN into a location which is NOT Cross Docking but "Cross docking" was originally checked. As you are re-routing these products to a different destination, please ensure you cancel any transport document(OUT/PICK etc) if it is no longer needed for the original requesting location.')
            }
        elif picking.purchase_id and dest_type == 'to_cross_docking' and not picking.purchase_id.cross_docking_ok:
            # display warning
            result['warning'] = {
                'title': _('Error'),
                'message': _('You want to receive the IN on Cross Docking but "Cross docking" was not checked.')
            }

        if dest_type == 'to_cross_docking' and setup.allocation_setup == 'unallocated':
            result['value'].update({
                'dest_type': 'default'
            })

            result['warning'] = {'title': _('Error'),
                                 'message': _('The Allocated stocks setup is set to Unallocated.' \
                                              'In this configuration, you cannot made moves from/to Cross-docking locations.')
                                 }

        return result

    def onchange_claim_type(self, cr, uid, ids, claim_type, context=None):
        """
        Put True to claim_replacement_picking_expected when claim_type is 'missing'.
        """
        if context is None:
            context = {}

        result = {'value': {'claim_replacement_picking_expected': False}}

        if claim_type == 'missing':
            result['value'].update({
                'claim_replacement_picking_expected': True
            })

        return result

    def onchange_register_a_claim(self, cr, uid, ids, register_a_claim, onchange_dest_type, context=None):
        """
        Put True to direct_incoming when register_a_claim is checked.
        """
        if context is None:
            context = {}

        result = {'value': {'direct_incoming': str(onchange_dest_type)}}

        if register_a_claim:
            result['value'].update({
                'direct_incoming': 't',
            })

        return result

    def do_reset(self, cr, uid, ids, context=None):
        incoming_obj = self.pool.get('stock.incoming.processor')
        stock_p_obj = self.pool.get('stock.picking')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )
        incoming_ids = incoming_obj.browse(cr, uid, ids, context=context)
        res_id = []
        for incoming in incoming_ids:
            res_id = incoming['picking_id']['id']
        incoming_obj.write(cr, uid, ids, {'draft': False}, context=context)
        return stock_p_obj.action_process(cr, uid, res_id, context=context)

    def do_save_draft(self, cr, uid, ids, context=None):
        incoming_obj = self.pool.get('stock.incoming.processor')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # make sure that the current incoming proc is not already processed :
        for r in incoming_obj.read(cr, uid, ids, ['already_processed']):
            if not r['already_processed']:
                incoming_obj.write(cr, uid, ids, {'draft': True}, context=context)
            else:
                raise osv.except_osv(
                    _('Error'), _('The incoming shipment has already been processed, you cannot save it as draft.')
                )

        return {}

    def force_process(self, cr, uid, ids, context=None):
        '''
        Go to the processing wizard
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def launch_simulation(self, cr, uid, ids, context=None):
        '''
        Launch the simulation screen
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No picking defined.')
            )

        simu_obj = self.pool.get('wizard.import.in.simulation.screen')

        for wizard in self.browse(cr, uid, ids, context=context):
            picking_id = wizard.picking_id.id

            simu_id = simu_obj.create(cr, uid, {'picking_id': picking_id, 'physical_reception_date': wizard.physical_reception_date}, context=context)
            context.update({'simu_id': simu_id})

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.in.simulation.screen',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'same',
                'res_id': simu_id,
                'context': context}


    def check_if_has_import_file_in_attachment(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        in_id = self.read(cr, uid, ids[0], ['picking_id'], context=context)['picking_id'][0]

        attach_ids = self.pool.get('ir.attachment').search(cr, uid, [
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', in_id),
            ('name', 'like', 'SHPM_%%'),
        ], context=context)

        if len(attach_ids) > 1:
            raise osv.except_osv(_('Error'), _('Too many import files in attachment for the same IN, only 1 import file prefixed with "SHPM_" is allowed'))

        attach_data = False
        if attach_ids:
            attach_data = self.pool.get('ir.attachment').read(cr, uid, attach_ids[0], ['name', 'datas'], context=context)

        return attach_data


    def launch_simulation_pack(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('auto_import_ok'):
            out = self.read(cr, uid, ids[0], ['linked_to_out'], context=context)
            if out['linked_to_out'] != 'picking':
                raise osv.except_osv(_('Warning'), _('This type of import cannot be used because related PICK document has been converted to %s') % out['linked_to_out'])

        data = self.launch_simulation(cr, uid, ids, context)
        self.pool.get('wizard.import.in.simulation.screen').write(cr, uid, data['res_id'], {'with_pack': True})


        data['name'] = _('Incoming shipment simulation screen (pick and pack mode)')

        file_attached = self.check_if_has_import_file_in_attachment(cr, uid, ids, context=context)
        if file_attached:
            self.pool.get('wizard.import.in.simulation.screen').write(cr, uid, data['res_id'], {
                'file_to_import': file_attached['datas'], # base64
                'filetype': self.pool.get('stock.picking').get_import_filetype(cr, uid, file_attached['name'], context=context),
            }, context=context)
            self.pool.get('wizard.import.in.simulation.screen').launch_simulate(cr, uid, data['res_id'], context=context)
            # the following line process the IN but display the simu screen
            #self.pool.get('wizard.import.in.simulation.screen').launch_import_pack(cr, uid, data['res_id'], context=context)
        return data


    def check_before_creating_pack_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wizard = self.browse(cr, uid, ids[0], context=context)

        sequence_ok = True
        rounding_issues = []
        total_qty = 0
        sequences = {}
        for move in wizard.move_ids:
            total_qty += move.quantity
            if move.quantity:
                sequences.setdefault(move.packing_list, []).append((move.from_pack, move.to_pack, move.id))
                num_of_packs = move.to_pack - move.from_pack + 1
                if num_of_packs:
                    if not self.pool.get('ppl.processor')._check_rounding(cr, uid, move.uom_id, num_of_packs, move.quantity, context=context):
                        rounding_issues.append(move.line_number)

        if not total_qty:
            raise osv.except_osv(
                _('Processing Error'),
                _("You have to enter the quantities you want to process before processing the move")
            )

        if not sequences:
            sequence_ok = False
            return (rounding_issues, sequence_ok)
        for pl in sequences:
            sequence_ok = sequence_ok and self.pool.get('ppl.processor').check_sequences(cr, uid, sequences[pl], self.pool.get('stock.move.in.processor'), field='sequence_issue')

        return (rounding_issues, sequence_ok)


    def process_to_ship(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        out = self.read(cr, uid, ids[0], ['linked_to_out'], context=context)
        if out['linked_to_out'] != 'picking':
            raise osv.except_osv(_('Warning'), _('This type of import cannot be used because related PICK document has been converted to %s') % out['linked_to_out'])

        rounding_issues, sequence_ok = self.check_before_creating_pack_lines(cr, uid, ids, context=context)
        cr.execute('''
            select wiz_line.line_number, pol.linked_sol_id, sum(wiz_line.quantity)
            from stock_move_in_processor wiz_line
            left join stock_incoming_processor wiz on wiz.id = wiz_line.wizard_id
            left join stock_move move_in on move_in.picking_id = wiz.picking_id and move_in.id = wiz_line.move_id
            left join purchase_order_line pol on pol.id = move_in.purchase_line_id
            where
                wiz.id = %s
            group by wiz_line.line_number, pol.linked_sol_id
        ''', (ids[0],))
        sol_id_to_wiz_line = {}
        sol_id_sum = {}
        for x in cr.fetchall():
            sol_id_to_wiz_line[x[1]] = x[0]
            sol_id_sum[x[1]] = x[2]

        error_pick = self.pool.get('wizard.import.in.simulation.screen').error_pick_already_processed(cr, uid, sol_id_sum, sol_id_to_wiz_line, context)
        if error_pick:
            raise osv.except_osv(_('Error'), error_pick)

        if not sequence_ok:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_incoming_processor_form_view')[1]
            self.write(cr, uid, ids, {'sequence_issue': True}, context=context)

            return {
                'name': _('Products to Process'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.incoming.processor',
                'res_id': ids[0],
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
            }

        if rounding_issues:
            rounding_issues.sort()

            wiz_check_ppl_id = self.pool.get('check.ppl.integrity').create(cr, uid, {
                'incoming_processor_id': ids[0],
                'line_number_with_issue': ', '.join([str(x) for x in rounding_issues]),
            }, context=context)
            return {
                'name': _("PPL integrity"),
                'type': 'ir.actions.act_window',
                'res_model': 'check.ppl.integrity',
                'target': 'new',
                'res_id': [wiz_check_ppl_id],
                'view_mode': 'form',
                'view_type': 'form',
                'context': context,
            }

        self.pool.get('stock.picking').do_incoming_shipment(cr, uid, ids, context=context, with_ppl=True)
        return {'type': 'ir.actions.act_window_close'}


    def do_in_back(self, cr, uid, ids, context=None):
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_incoming_processor_form_view')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_id': ids[0],
            'target': 'new',
            'context': context,
        }

    def do_in_step2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        for in_proc in self.browse(cr, uid, ids, context=context):
            for fam in in_proc.family_ids:
                # fill fields 'pack_info_id' with new 'wizard.import.in.pack.simulation.screen':
                pack_info = {
                    # 'wizard_id':,
                    'parcel_from': fam.from_pack,
                    'parcel_to': fam.to_pack,
                    # 'parcel_qty': ,
                    'total_weight': fam.weight,
                    # 'total_volume': ,
                    'total_height': fam.height,
                    'total_length': fam.length,
                    'total_width': fam.width,
                    'total_volume': fam.volume,
                    'integrity_status': fam.integrity_status,
                    'packing_list': fam.packing_list,
                }
                for manda_field in ['parcel_from', 'parcel_to']:
                    if not pack_info.get(manda_field):
                        raise osv.except_osv(_('Error'), _('Field %s should not be empty in case of pick and pack mode') % manda_field)
                pack_info_id = self.pool.get('wizard.import.in.pack.simulation.screen').create(cr, uid, pack_info, context=context)
                self.pool.get('stock.move.in.processor').write(cr, uid, [m.id for m in fam.move_ids], {'pack_info_id': pack_info_id}, context=context)

            new_picking = self.pool.get('stock.picking').do_incoming_shipment(cr, uid, [in_proc.id], context=context)

        return new_picking


stock_incoming_processor()


class stock_move_in_processor(osv.osv):
    """
    Incoming moves processing wizard
    """
    _name = 'stock.move.in.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard lines for incoming shipment processing'
    _order = 'line_number, from_pack, id'

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        return super(stock_move_in_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(stock_move_in_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

    def _get_integrity_status(self, cr, uid, ids, field_name, args, context=None):
        res = super(stock_move_in_processor, self)._get_integrity_status(cr, uid, ids, field_name, args, context=context)
        for move in self.browse(cr, uid, ids, fields_to_fetch=['sequence_issue'], context=context):
            if res.get(move.id, '') == 'empty' and move.sequence_issue and move.sequence_issue != 'empty':
                res[move.id] = move.sequence_issue
        return res

    def _get_batch_location_ids(self, cr, uid, ids, field_name, args, context=None):
        """
        UFTP-53: specific get stock locations ids for incoming shipment
        in batch numbers:
            - From FO:     CD + Main Stock & children (For example LOG/MED)
            - From non-FO: Main Stock & children (For example LOG/MED)
        """
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]

        main_stock_id = self.pool.get('ir.model.data').get_object_reference(cr,
                                                                            uid, 'stock', 'stock_location_stock')[1]
        cd_id = False

        # get related move ids and map them to ids
        moves_to_ids = {}
        for r in self.read(cr, uid, ids, ['move_id'], context=context):
            if r['move_id']:
                moves_to_ids[r['move_id'][0]] = r['id']

        # scan moves' purchase line and check if associated with a SO/FO
        po_obj = self.pool.get('purchase.order')
        sol_obj = self.pool.get('sale.order.line')
        # store the result as most of the time lines have same order_id
        move_purchase_line = self.pool.get('stock.move').read(cr,
                                                              uid, moves_to_ids.keys(), ['id', 'purchase_line_id'],
                                                              context=context)

        move_id_to_purchase_line_id = {}
        for ret in move_purchase_line:
            if ret['purchase_line_id']:
                move_id_to_purchase_line_id[ret['id']] = ret['purchase_line_id'][0]

        purchase_line_order_id = self.pool.get('purchase.order.line').read(cr,
                                                                           uid, set(move_id_to_purchase_line_id.values()), ['id', 'order_id'], context=context)

        purchase_line_id_by_order_id = dict([(ret['id'], ret['order_id'][0])
                                             for ret in purchase_line_order_id])
        order_id_set = set(purchase_line_id_by_order_id.values())

        order_id_location_dict = {}
        for order_id in order_id_set:
            sol_ids = po_obj.get_sol_ids_from_po_ids(cr, uid,
                                                     [order_id], context=context)
            if sol_ids:
                location_ids = [main_stock_id] if main_stock_id else []
                # move associated with a SO, check not with an IR (so is FO)
                is_from_fo = True
                for sol in sol_obj.browse(cr, uid, sol_ids,
                                          context=context):
                    if sol.order_id and sol.order_id.procurement_request and sol.order_id.location_requestor_id.usage != 'customer':
                        # from an IR then not from FO
                        is_from_fo = False
                        break

                if is_from_fo:
                    if not cd_id:
                        cd_id = self.pool.get('ir.model.data').get_object_reference(
                            cr, uid, 'msf_cross_docking',
                            'stock_location_cross_docking')[1]
                    location_ids.append(cd_id)
                order_id_location_dict[order_id] = location_ids

        for move_id, id in moves_to_ids.iteritems():
            location_ids = [main_stock_id] if main_stock_id else []

            if move_id in move_id_to_purchase_line_id:
                purchase_line_id = move_id_to_purchase_line_id[move_id]
                if purchase_line_id in purchase_line_id_by_order_id:
                    order_id = purchase_line_id_by_order_id[purchase_line_id]
                    if order_id in order_id_location_dict:
                        location_ids = order_id_location_dict[order_id]

            res[id] = ','.join(map(lambda id: str(id), location_ids))

        # set ids default value for ids with no specific location
        for id in ids:
            if id not in res:
                res[id] = False
        return res

    def _set_comment(self, cr, uid, ml_id, name=None, value=None, fnct_inv_arg=None, context=None):
        """
        Just used to not break default OpenERP behaviour
        """
        if name and value:
            sql = "UPDATE "+ self._table + " SET " + name + " = %s WHERE id = %s"  # not_a_user_entry
            cr.execute(sql, (value, ml_id))
        return True

    def _get_pack_info(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, fields_to_fetch=['from_pack', 'to_pack'], context=context):
            if wiz['from_pack']:
                res[wiz.id] = '%s-%s' % (wiz['from_pack'], wiz['to_pack'])
            else:
                res[wiz.id] = False
        return res

    def _search_pack_info(self, cr, uid, obj, name, args, context):
        dom = []
        for arg in args:
            if arg[2]:
                d_p = arg[2].split('-')
                if d_p and d_p[0] and d_p[0].strip():
                    dom = [('from_pack', '=', d_p[0].strip())]
                if d_p and len(d_p)>1 and d_p[1] and d_p[1].strip():
                    dom.append(('to_pack', '=', d_p[1].strip()))
        return dom

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'stock.incoming.processor',
            string='Wizard',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
        ),
        'state': fields.char(size=32, string='State', readonly=True),
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected product to receive",
            multi='move_info',
        ),
        'comment': fields.function(
            _get_move_info,
            fnct_inv=_set_comment,
            method=True,
            string='Comment',
            type='text',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Comment of the move",
            multi='move_info',
        ),
        'ordered_uom_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM',
            type='many2one',
            relation='product.uom',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected UoM to receive",
            multi='move_info',
        ),
        'ordered_uom_category': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM category',
            type='many2one',
            relation='product.uom.categ',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Category of the expected UoM to receive",
            multi='move_info'
        ),
        'location_id': fields.function(
            _get_move_info,
            method=True,
            string='Location',
            type='many2one',
            relation='stock.location',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Source location of the move",
            multi='move_info'
        ),
        'batch_location_ids': fields.function(
            _get_batch_location_ids,
            method=True,
            string='Locations',
            type='char',
            help="Specific locations with batch number",
            invisible=True,
        ),
        'location_supplier_customer_mem_out': fields.function(
            _get_move_info,
            method=True,
            string='Location Supplier Customer',
            type='boolean',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            multi='move_info',
            help="",
        ),
        'integrity_status': fields.function(
            _get_integrity_status,
            method=True,
            string='',
            type='selection',
            selection=INTEGRITY_STATUS_SELECTION,
            store={
                'stock.move.in.processor': (
                    lambda self, cr, uid, ids, c=None: ids,
                    ['product_id', 'wizard_id', 'quantity', 'asset_id', 'prodlot_id', 'expiry_date', 'sequence_issue'],
                    20
                ),
            },
            readonly=True,
            help="Integrity status (e.g: check if a batch is set for a line with a batch mandatory product...)",
        ),
        'type_check': fields.function(
            _get_move_info,
            method=True,
            string='Picking Type Check',
            type='char',
            size=32,
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Return the type of the picking",
            multi='move_info',
        ),
        'lot_check': fields.function(
            _get_product_info,
            method=True,
            string='B.Num',
            type='boolean',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A batch number is required on this line",
        ),
        'exp_check': fields.function(
            _get_product_info,
            method=True,
            string='Exp.',
            type='boolean',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An expiry date is required on this line",
        ),
        'asset_check': fields.function(
            _get_product_info,
            method=True,
            string='Asset',
            type='boolean',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An asset is required on this line",
        ),
        'kit_check': fields.function(
            _get_product_info,
            method=True,
            string='Kit',
            type='boolean',
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A kit is required on this line",
        ),
        'kc_check': fields.function(
            _get_product_info,
            method=True,
            string='CC',
            type='char',
            size=8,
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a cold Chain Item",
        ),
        'ssl_check': fields.function(
            _get_product_info,
            method=True,
            string='SSL',
            type='char',
            size=8,
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Short Shelf Life product",
        ),
        'dg_check': fields.function(
            _get_product_info,
            method=True,
            string='DG',
            type='char',
            size=8,
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Dangerous Good",
        ),
        'np_check': fields.function(
            _get_product_info,
            method=True,
            string='CS',
            type='char',
            size=8,
            store={
                'stock.move.in.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
        'pack_info_id': fields.many2one('wizard.import.in.pack.simulation.screen', 'Pack Info'),
        'from_pack': fields.integer_null(string='From p.'),
        'to_pack': fields.integer_null(string='To p.'),
        'weight': fields.float_null('Weight', digits=(16,2)),
        'volume': fields.float_null('Volume', digits=(16,2)),
        'height': fields.float_null('Height', digits=(16,2)),
        'total_volume': fields.float_null(u'Total Volume [dm³]', digits=(16,0)),
        'total_weight': fields.float_null(u'Total Weight [kg]', digits=(16,0)),
        'length': fields.float_null('Length', digits=(16,2)),
        'width': fields.float_null('Width', digits=(16,2)),
        'pack_id': fields.many2one('in.family.processor', string='Pack', ondelete='set null'),
        'packing_list': fields.char('Supplier Packing List', size=30),
        'ppl_name': fields.char('Packing List', size=128),
        'sequence_issue': fields.selection(PACK_INTEGRITY_STATUS_SELECTION, 'Sequence issue', readonly=True),
        'split_move_ok': fields.boolean(string='Is split move ?'),
        'filter_pack': fields.function(_get_pack_info, method=True, type='char', string='Pack', fnct_search=_search_pack_info),
        'cost_as_ro': fields.boolean('Set Cost Price as RO', internal=1),
    }


    _defaults = {
        'split_move_ok': lambda *a: False,
    }


    """
    Model methods
    """
    def create(self, cr, uid, vals, context=None):
        """
        Add default values for cost and currency if not set in vals
        """
        # Objects
        product_obj = self.pool.get('product.product')
        user_obj = self.pool.get('res.users')

        if context is None:
            context = {}

        if not vals.get('cost'):
            # issue on IN processor from sync if new line created (because of a split in coordo)
            # then the price_unit should not come from product standard_price but from the original stock.move (i.e: from POL)
            # before this the unit price was temporary set to the standard_price, but changed on IN processing, this was too late
            if vals.get('move_id'):
                move_data = self.pool.get('stock.move').browse(cr, uid, vals['move_id'], fields_to_fetch=['price_unit', 'currency_id'], context=context)
                vals['cost'] = move_data.price_unit
                vals['currency'] = move_data.currency_id.id

        if vals.get('product_id', False):
            if not vals.get('cost', False):
                price = product_obj.browse(cr, uid, vals['product_id'], context=context).standard_price
                vals['cost'] = price
            if not vals.get('currency', False):
                vals['currency'] = user_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id
        return super(stock_move_in_processor, self).create(cr, uid, vals, context=context)


    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        if 'from_pack' in vals or 'to_pack' in vals:
            vals['sequence_issue'] = 'empty'

        return super(stock_move_in_processor, self).write(cr, uid, ids, vals, context=context)


    def _get_line_data(self, cr, uid, wizard=False, move=False, context=None):
        """
        Update the unit price and the currency of the move line wizard if the
        move is attached to a purchase order line
        """
        line_data = super(stock_move_in_processor, self)._get_line_data(cr, uid, wizard, move, context=context)
        if wizard.picking_id.purchase_id and move.purchase_line_id and move.product_id.cost_method == 'average':
            line_data.update({
                'cost': move.purchase_line_id.price_unit,
                'currency': wizard.picking_id.purchase_id.pricelist_id.currency_id.id,
            })

        return line_data

    def open_change_product_wizard(self, cr, uid, ids, context=None):
        """
        Change the locations on which product quantities are computed
        """
        # Objects
        wiz_obj = self.pool.get('change.product.move.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = super(stock_move_in_processor, self).\
            open_change_product_wizard(cr, uid, ids, context=context)

        wiz_id = res.get('res_id', False)
        if wiz_id:
            in_move = self.browse(cr, uid, ids[0], context=context)
            if in_move.batch_location_ids:
                wiz_obj.write(cr, uid, [wiz_id], {
                    'move_location_ids': in_move.batch_location_ids,
                }, context=context)

        return res

    def onchange_from_pack_to_pack(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        return {'value': {'integrity_status': 'empty'}}

stock_move_in_processor()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
