# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from osv import osv
from osv import fields

from tools.translate import _


class mission_stock_wizard(osv.osv_memory):
    _name = 'mission.stock.wizard'
    
    _columns = {
        'report_id': fields.many2one('stock.mission.report', string='Report', required=True),
        'with_valuation': fields.boolean(string='Display stock valuation ?'),
    }
    
    def open_products_view(self, cr, uid, ids, context=None):
        '''
        Open the product list with report information
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not context:
            context = {}
            
        wiz_id = self.browse(cr, uid, ids[0], context=context)
        c = context.copy()
        c.update({'mission_report_id': wiz_id.report_id.id, 'with_valuation': wiz_id.with_valuation})
        
        view_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'mission_stock', 'mission_stock_product_list_view')
        if not view_ids or len(view_ids) <= 1 or not view_ids[1]:
            raise osv.except_osv(_('Error'), _('View not found for mission stock report !'))
        
        view_id = view_ids[1]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'target': 'current',
                'context': c}
        
mission_stock_wizard()