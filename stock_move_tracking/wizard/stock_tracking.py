# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
from tools.translate import _


class stock_move_tracking(osv.osv_memory):
    _name = 'stock.move.tracking'
    _description = 'Stock Move Tracking'
    
    _columns= {
        'product_id': fields.many2one('product.product', string='Product'),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'expired_date': fields.date('Expired date'),
    }
    
    def get_ids(self, cr, uid, ids, context={}):
        '''
        Returns all stock moves according to parameters
        '''
        move_obj = self.pool.get('stock.move')
        
        res = []
        for track in self.browse(cr, uid, ids):
            if not track.product_id and not track.prodlot_id and not track.expired_date:
                raise osv.except_osv(_('Error'), _('You should at least enter one information'))
            
            domain = []
            if track.expired_date:
                domain.append(('expired_date', '=', track.expired_date))
            if track.product_id:
                domain.append(('product_id', '=', track.product_id.id))
            if track.prodlot_id:
                domain.append(('prodlot_id', '=', track.prodlot_id.id))
            
            res.extend(move_obj.search(cr, uid, domain, order='date'))
            
        return res
    
    def print_report(self, cr, uid, ids, context={}):
        '''
        Print the report as PDF file
        '''
        product_name = False
        product_code = False
        prodlot_id = False
        expired_date = False
        
        for track in self.browse(cr, uid, ids):
            product_name = track.product_id and track.product_id.name or False
            product_code = track.product_id and track.product_id.default_code or False
            prodlot_id = track.prodlot_id and track.prodlot_id.name or False
            expired_date = track.expired_date
        
        data = {'move_ids': self.get_ids(cr, uid, ids, context=context),
                'product_id': product_name,
                'product_code': product_code,
                'prodlot_id': prodlot_id,
                'expired_date': expired_date}
        
        datas = {'ids': self.get_ids(cr, uid, ids, context=context),
                 'model': 'stock.move',
                 'form': data}

        return {'type': 'ir.actions.report.xml',
                'report_name': 'tracking.move.report',
                'datas': datas}
    
    def print_view(self, cr, uid, ids, context={}):
        '''
        Print the report on Web client (search view)
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        result_tree = mod_obj._get_id(cr, uid, 'stock_move_tracking', 'stock_move_tracking_tree_view')
        tree_id = mod_obj.read(cr, uid, [result_tree], ['res_id'], context=context)[0]['res_id']

        result_search = mod_obj._get_id(cr, uid, 'stock_move_tracking', 'stock_move_tracking_search_view')
        search_id = mod_obj.read(cr, uid, [result_search], ['res_id'], context=context)[0]['res_id']
        
        result = mod_obj._get_id(cr, uid, 'stock_move_tracking', 'action_stock_move_tracking')
        id = mod_obj.read(cr, uid, [result], ['res_id'], context=context)[0]['res_id']
        
        result = act_obj.read(cr, uid, [id], context=context)[0]
        result['domain'] = [('id', 'in', self.get_ids(cr, uid, ids, context=context))]
        
        return result
    
stock_move_tracking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: