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
