# -*- coding: utf-8 -*-

from osv import fields
from osv import osv

from tools.translate import _


class shipment_parcel_selection(osv.osv):
    _name = 'shipment.parcel.selection'
    _description = 'Select Parcel IDs'
    _rec_name = 'date'

    _columns = {
        'shipment_line_id': fields.many2one('pack.family.memory', string='Shipment Line', readonly=True, ondelete='cascade'),
        'return_line_id': fields.many2one('return.shipment.family.processor', string='Return to stock line', readonly=True, ondelete='cascade'),
        'return_shipment_line_id': fields.many2one('return.pack.shipment.family.processor', string='Return from Sub Ship to draft Ship line', readonly=True, ondelete='cascade'),
        'add_pack_line_id': fields.many2one('shipment.add.pack.processor.line', string='Sub ship, add pack from draft pick', readonly=True, ondelete='cascade'),
        'parcel_number': fields.integer('Nb parcel to select', readonly=True),
        'selected_item_ids': fields.text('Selected Parcels'),
        'available_items_ids': fields.text('Available Parcels'),
    }

    _defaults = {
    }

    def select_parcels(self, cr, uid, ids, context=None):
        sel = self.browse(cr, uid, ids[0], context=context)
        nb_selected = 0
        if sel.selected_item_ids:
            nb_selected = len(sel.selected_item_ids.split(','))
        if nb_selected != sel.parcel_number:
            raise osv.except_osv(_('Error !'), _('%d Parcels expected, %d selected.') % (sel.parcel_number, nb_selected))

        if sel.shipment_line_id:
            # from draft ship form view
            write_obj = self.pool.get('pack.family.memory')
            ship_line_id = sel.shipment_line_id.id
        elif sel.return_line_id:
            # from draft ship return wizard
            write_obj = self.pool.get('return.shipment.family.processor')
            ship_line_id = sel.return_line_id.id
        elif sel.return_shipment_line_id:
            # from sub ship to draft ship
            write_obj = self.pool.get('return.pack.shipment.family.processor')
            ship_line_id = sel.return_shipment_line_id.id
        else:
            # wizard add pack to sub ship
            write_obj = self.pool.get('shipment.add.pack.processor.line')
            ship_line_id = sel.add_pack_line_id.id

        write_obj.write(cr, uid, ship_line_id, {'selected_parcel_ids': sel.selected_item_ids}, context=context)


        if sel.shipment_line_id:
            return {'type': 'ir.actions.act_window_close'}

        return {'type': 'ir.actions.refresh_popupo2m', 'o2m_refresh': 'family_ids'}

shipment_parcel_selection()
