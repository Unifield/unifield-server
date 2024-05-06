# -*- coding: utf-8 -*-

from osv import osv, fields


class rfq_has_service_not_service_product_wizard(osv.osv_memory):
    _name = 'rfq.has.service.not.service.product.wizard'

    _columns = {
        'rfq_id': fields.many2one('purchase.order', string='Request for Quotation'),
    }

    def continue_continue_sourcing(self, cr, uid, ids, context=None):
        '''
        Continue the PO creation from the Tender
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('purchase.order').continue_sourcing(cr, uid, [wiz.rfq_id.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def close_wizard(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


rfq_has_service_not_service_product_wizard()
