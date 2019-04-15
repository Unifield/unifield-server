# -*- coding: utf-8 -*-
from osv import fields
from osv import osv


class shipment_add_pack_processor(osv.osv):
    _name = 'shipment.add.pack.processor'
    _inherit = 'return.shipment.processor'
    _description = 'Add Packs to Shipment'
    _rec_name = 'shipment_id'

    _columns = {
        'shipment_id': fields.many2one('shipment', 'Shipment', required=True, ondelete='cascade'),
        'family_ids': fields.one2many('shipment.add.pack.processor.line', 'wizard_id', 'Packs'),
    }

    def do_add_packs(self, cr, uid, ids, context=None):
        ship_obj = self.pool.get('shipment')

        wiz = self.browse(cr, uid, ids[0], context=context)
        shipment_id = wiz.shipment_id.id

        for pack_fam in wiz.family_ids:
            ship_obj.attach_draft_pick_to_ship(cr, uid, shipment_id, pack_fam, context=context)

        return {'type': 'ir.actions.act_window_close'}

shipment_add_pack_processor()

class shipment_add_pack_processor_line(osv.osv):
    _name = 'shipment.add.pack.processor.line'
    _inherit = 'return.shipment.family.processor'
    _description ='Pack to add'

    _columns = {
        'wizard_id': fields.many2one('shipment.add.pack.processor', 'Processor'),
        'num_of_packs': fields.integer('Nb. Parcels'),
        'volume': fields.float(digits=(16, 2), string=u'Volume[dm³]'),
        'weight': fields.float(digits=(16, 2), string=u'Weight P.P [Kg]'),
    }

shipment_add_pack_processor_line()
