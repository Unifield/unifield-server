# -*- coding: utf-8 -*-

from osv import fields
from osv import osv

from tools.translate import _


class shipment_parcel_selection(osv.osv):
    _name = 'shipment.parcel.selection'
    _description = 'Select Parcel IDs'
    _rec_name = 'date'

    _columns = {
        'shipment_line_id': fields.many2one('pack.family.memory', string='Shipment Line', required=True, readonly=True, ondelete='cascade'),
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

        self.pool.get('pack.family.memory').write(cr, uid, sel.shipment_line_id.id, {'selected_parcel_ids': sel.selected_item_ids}, context=context)

        return {'type': 'ir.actions.act_window_close'}

shipment_parcel_selection()
