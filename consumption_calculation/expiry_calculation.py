# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from datetime import date, timedelta

class expiry_quantity_report(osv.osv_memory):
    _name = 'expiry.quantity.report'
    _description = 'Products Expired'
    
    def _get_date_to(self, cr, uid, ids, field_name, arg, context={}):
        res = {}
        
        for report in self.browse(cr, uid, ids, context=context):
            res[report.id] = (date.today() + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d')
            
        return res
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='Location'),
        'week_nb': fields.integer(string='Period of calculation (Today till XX weeks)', required=True),
        'date_to': fields.function(_get_date_to, method=True, type='date', string='Limit date', readonly=True),
        'line_ids': fields.one2many('expiry.quantity.report.line', 'report_id', string='Products', readonly=True),
    }
    
    def process_lines(self, cr, uid, ids, context={}):
        '''
        Creates all lines of expired products
        '''
        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        lots = {}
        
        report = self.browse(cr, uid, ids[0], context=context)
        lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', (date.today() + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d'))])        
        domain = [('date_expected', '<=', date.today().strftime('%Y-%m-%d')), ('state', '=', 'done'), ('prodlot_id', 'in', lot_ids)]
        
        
        if report.location_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'expiry_quantity_report_processed_view')[1],
            domain.append(('location_dest_id', '=', report.location_id.id))
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'expiry_quantity_report_processed_loc_view')[1],
            
        move_ids = move_obj.search(cr, uid, domain, context=context)
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            if move.prodlot_id:
                lot_id = move.prodlot_id.id
                # Add the lot in the list
                if lot_id not in lots:
                    lots[lot_id] = {}
                
                # Add the location in the lot list
                if move.location_dest_id.id not in lots[lot_id]:
                    lots[lot_id][move.location_dest_id.id] = 0.00
                    
                lots[lot_id][move.location_dest_id.id] += move.product_qty
                
        for lot_location in lots:
            product = lot_obj.browse(cr, uid, lot_location, context=context).product_id
            lot_name = lot_obj.browse(cr, uid, lot_location, context=context).name
            for location in lots[lot_location]:
                context.update({'location': location})
                real_qty = lot_obj.browse(cr, uid, lot_location, context=context).product_id.qty_available
                self.pool.get('expiry.quantity.report.line').create(cr, uid, {'product_id': product.id,
                                                                              'uom_id': product.uom_id.id,
                                                                              'real_stock': real_qty,
                                                                              'expired_qty': lots[lot_location][location],
                                                                              'batch_number': lot_name,
                                                                              'location_id': location,
                                                                              'report_id': ids[0],
                                                                              })        
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'expiry.quantity.report',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': ids[0],
        }
    
expiry_quantity_report()


class expiry_quantity_report_line(osv.osv_memory):
    _name = 'expiry.quantity.report.line'
    _description = 'Products expired line'
    
    _columns = {
        'report_id': fields.many2one('expiry.quantity.report', string='Report', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_code': fields.related('product_id', 'default_code', string='Reference', type='char'),
        'product_name': fields.related('product_id', 'name', string='Name', type='char'),
        'uom_id': fields.related('product_id', 'uom_id', string='UoM', type='many2one', relation='product.uom'),
        'real_stock': fields.float(digits=(16, 2), string='Real stock'),
        'expired_qty': fields.float(digits=(16, 2), string='Expired quantity'),
        'batch_number': fields.many2one('production.lot', string='Batch number'),
        'location_id': fields.many2one('stock.location', string='SLoc'),
    }
    
expiry_quantity_report_line()

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
