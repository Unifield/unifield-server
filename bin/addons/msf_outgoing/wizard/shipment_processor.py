# -*- coding: utf-8 -*-
from osv import fields
from osv import osv
from tools.translate import _


class shipment_add_pack_processor(osv.osv):
    _name = 'shipment.add.pack.processor'
    _inherit = 'return.shipment.processor'
    _description = 'Add Packs to Shipment'
    _rec_name = 'shipment_id'

    _columns = {
        'shipment_id': fields.many2one('shipment', 'Shipment', required=True, ondelete='cascade'),
        'family_ids': fields.one2many('shipment.add.pack.processor.line', 'wizard_id', 'Packs'),
    }

    def do_add_packs_bg(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        cr.execute('''
            select
                count(m.id)
            from
                shipment_add_pack_processor_line pc, stock_move m
            where
                m.picking_id = pc.ppl_id and
                pc.selected_number > 0 and
                pc.wizard_id=%s
            ''', (ids[0],)
        )
        nb_lines = cr.fetchone()[0] or 0
        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, ids, 'shipment', self.do_add_packs, nb_lines, _('Add Packs'), main_object_id=wiz.shipment_id.id, return_success={'type': 'ir.actions.act_window_close'}, context=context)

    def do_add_packs(self, cr, uid, ids, context=None, job_id=False):
        ship_obj = self.pool.get('shipment')

        wiz = self.browse(cr, uid, ids[0], context=context)
        shipment_id = wiz.shipment_id.id

        nb_processed = 0
        for pack_fam in wiz.family_ids:
            nb_processed = ship_obj.attach_draft_pick_to_ship(cr, uid, shipment_id, pack_fam.shipment_line_id, selected_number=pack_fam.selected_number, context=context, job_id=job_id, nb_processed=nb_processed)

        return True


shipment_add_pack_processor()


class shipment_add_pack_processor_line(osv.osv):
    _name = 'shipment.add.pack.processor.line'
    _inherit = 'return.shipment.family.processor'
    _description = 'Pack to add'

    _columns = {
        'wizard_id': fields.many2one('shipment.add.pack.processor', 'Processor'),
        'num_of_packs': fields.integer('Nb. Parcels'),
        'volume': fields.float(digits=(16, 2), string='Volume[dm³]'),
        'weight': fields.float(digits=(16, 2), string='Weight P.P [Kg]'),
    }


shipment_add_pack_processor_line()
