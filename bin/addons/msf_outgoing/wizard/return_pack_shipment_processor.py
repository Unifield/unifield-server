# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

class return_pack_shipment_processor(osv.osv):
    """
    Wizard to return Packs from shipment
    """
    _name = 'return.pack.shipment.processor'
    _inherit = 'return.shipment.processor'
    _description = 'Wizard to return Packs from shipment'

    _columns = {
        'family_ids': fields.one2many(
            'return.pack.shipment.family.processor',
            'wizard_id',
            string='Lines',
        ),
    }

    def select_all(self, cr, uid, ids, context=None):
        """
        Select all button, write max number of packs in each pack family line
        """
        # Objects
        family_obj = self.pool.get(self._columns['family_ids']._obj)  # Get the object of the o2m field because of heritage

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            for family in wiz.family_ids:
                family_obj.write(cr, uid, [family.id], {
                    'return_from': family.from_pack,
                    'return_to': family.to_pack,
                }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Packs from Shipment'),
            'res_model': self._name,
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': ids[0],
            'nodestroy': True,
            'target': 'new',
            'context': context,
        }

    def deselect_all(self, cr, uid, ids, context=None):
        """
        De-select all button, write 0 as number of packs in each pack family line
        """
        # Objects
        family_obj = self.pool.get(self._columns['family_ids']._obj)  # Get the object of the o2m field because of heritage
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        family_ids = []
        for wiz in self.browse(cr, uid, ids, context=context):
            for family in wiz.family_ids:
                family_ids.append(family.id)

        family_obj.write(cr, uid, family_ids, {
            'return_from': 0,
            'return_to': 0,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Packs from Shipment'),
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'nodestroy': True,
            'target': 'new',
            'context': context,
        }

    def do_return_pack_from_shipment(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the do_return_pack_from_shipment method of shipment object
        """
        # Objects
        shipment_obj = self.pool.get('shipment')

        if context is None:
            context = {}

        # UF-2531: Run the creation of message if it's at RW at some important point
        picking_obj = self.pool.get('stock.picking')
        usb_entity = picking_obj._get_usb_entity_type(cr, uid)
        if usb_entity == picking_obj.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            picking_obj._manual_create_rw_messages(cr, uid, context=context)

        if isinstance(ids, int):
            ids = [ids]


        for wizard in self.browse(cr, uid, ids, context=context):
            error = False
            no_sequence = True


            for family in wizard.family_ids:
                if family.integrity_status != 'empty':
                    error = True
                    break
                if family.return_from != 0 or family.return_to != 0:
                    no_sequence = False
                    break


            if error:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': ids[0],
                    'target': 'new',
                    'context': context,
                }

            if no_sequence:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('You must enter the number of packs you want to return before performing the return.'),
                )
        return shipment_obj.do_return_packs_from_shipment(cr, uid, ids, context=context)

return_pack_shipment_processor()


class return_pack_shipment_family_processor(osv.osv):
    """
    Family of the wizard to be returned from shipment
    """
    _name = 'return.pack.shipment.family.processor'
    _inherit = 'return.shipment.family.processor'
    _description = 'Family to be returned from shipment'
    _order = 'sale_order_id, ppl_id, from_pack, id'


    def _get_pack_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Set information on line with pack information
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            num_of_packs = line.return_to - line.return_from + 1
            res[line.id] = {
                'volume': (line.length * line.width * line.height * float(num_of_packs)) / 100.0,
                'num_of_packs': num_of_packs,
                'selected_weight': line.weight * line.selected_number,
                'integrity_status': 'empty',
                'parcel_ids_error': False,
                'has_parcels_info': False,
            }
            selected_number = line.return_to - line.return_from + 1
            if line.return_to and selected_number and line['parcel_ids']:
                nb_parcel = len(line['parcel_ids'].split(','))
                if not line['selected_parcel_ids']:
                    nb_parcel_selected = 0
                else:
                    nb_parcel_selected = len(line['selected_parcel_ids'].split(','))

                if nb_parcel:
                    res[line.id]['has_parcels_info'] = True
                if selected_number != nb_parcel and selected_number != nb_parcel_selected:
                    res[line.id]['parcel_ids_error'] = True
                    res[line.id]['integrity_status'] = 'parcels'

            if line.return_from or line.return_to:
                if line.return_from > line.return_to:
                    res[line.id]['integrity_status'] = 'to_smaller_than_from'
                elif not (line.return_from >= line.from_pack and line.return_to <= line.to_pack):
                    res[line.id]['integrity_status'] = 'seq_out_of_range'

        return res

    _columns = {
        'wizard_id': fields.many2one(
            'return.pack.shipment.processor',
            string='Wizard',
            required=True,
            readonly=True,
            ondelete='cascade',
            help="Wizard to process the return of the pack from the shipment",
        ),
        'return_from': fields.integer(string='Return from'),
        'return_to': fields.integer(string='Return to'),
        'volume': fields.function(
            _get_pack_info,
            method=True,
            string='Volume [dm³]',
            type='float',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'num_of_packs': fields.function(
            _get_pack_info,
            method=True,
            string='# Packs',
            type='integer',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'parcel_ids_error': fields.function(_get_pack_info, method=True, type='boolean', string='Parcel Error', multi='pack_info'),
        'has_parcels_info': fields.function(_get_pack_info, method=True, type='boolean', string='Has Parcel', multi='pack_info'),
        'selected_weight': fields.function(
            _get_pack_info,
            method=True,
            string='Selected Weight',
            type='float',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'comment': fields.text(
            string='Comment',
            readonly=True,
        ),
        'integrity_status': fields.function(_get_pack_info, method=True, type='selection',  string=' ',
                                            selection=[
                                                ('empty', ''),
                                                ('ok', 'Ok'),
                                                ('to_smaller_than_from', 'To value must be greater or equal to From value'),
                                                ('seq_out_of_range', 'Selected Sequence is out of range'),
                                                ('parcels', 'Selected Parcel IDs'),
                                            ],
                                            multi='pack_info',
                                            ),
    }

    def select_parcel_ids(self, cr, uid, ids, context=None):
        ship_line = self.read(cr, uid, ids[0], ['parcel_ids', 'selected_parcel_ids', 'return_from', 'return_to'], context=context)
        if not ship_line['parcel_ids']:
            raise osv.except_osv(_('Error !'), _('Parcel list is not defined.'))
        wiz = self.pool.get('shipment.parcel.selection').create(cr, uid, {
            'return_shipment_line_id': ids[0],
            'parcel_number': ship_line['return_to'] - ship_line['return_from'] + 1,
            'selected_item_ids': ship_line['selected_parcel_ids'],
            'available_items_ids': ship_line['parcel_ids'],
        }, context=context)

        return {
            'name': _("Select Parcel Ids to Return from Shipment"),
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.parcel.selection',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': wiz,
            'target': 'new',
            'keep_open': True,
            'context': context,
        }

return_pack_shipment_family_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
