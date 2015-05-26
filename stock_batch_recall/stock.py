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

import tools

from osv import osv, fields
from tools.translate import _
from decimal_precision import decimal_precision as dp
from tools.sql import drop_view_if_exists


class stock_batch_recall(osv.osv_memory):
    _name = 'stock.batch.recall'
    _description = 'Batch Recall'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product'),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'expired_date': fields.date(string='Expired Date')
    }
    
    def get_ids(self, cr, uid, ids, context=None):
        '''
        Returns all stock moves according to parameters
        '''
        move_obj = self.pool.get('stock.move')
        
        domain = [('product_qty', '>', 0.00)]
        for track in self.browse(cr, uid, ids):
            if not track.product_id and not track.prodlot_id and not track.expired_date:
                raise osv.except_osv(_('Error'), _('You should at least enter one information'))
            
            if track.expired_date:
                domain.append(('expired_date', '>=', track.expired_date))
                domain.append(('expired_date', '<=', track.expired_date))
            if track.product_id:
                domain.append(('product_id', '=', track.product_id.id))
            if track.prodlot_id:
                domain.append(('prodlot_id', '=', track.prodlot_id.id))
        return domain
    
    def return_view(self, cr, uid, ids, context=None):
        '''
        Print the report on Web client (search view)
        '''
        if context is None:
            context = {}
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        
        view_context = {}
        #view_context = {'group_by_ctx': ['product_id', 'location_id'], 'group_by_no_leaf': 1}
        
        domain = self.get_ids(cr, uid, ids)
        
        result = mod_obj._get_id(cr, uid, 'stock_batch_recall', 'action_report_batch_recall')
        id = mod_obj.read(cr, uid, [result], ['res_id'], context=context)[0]['res_id']
        
        result = act_obj.read(cr, uid, [id], context=context)[0]

        result['domain'] = domain
        result['context'] = context
        result['target'] = 'crush'
        
        return result
        
stock_batch_recall()

class report_batch_recall(osv.osv):
    _name = 'report.batch.recall'
    _rec_name = 'product_id'
    _description = 'Batch Recall'
    _auto = False
    _columns = {
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'location_id': fields.many2one('stock.location', 'Location', readonly=True),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch Number', readonly=True),
        'expired_date': fields.date('Expired Date', readonly=True),
        'product_qty':fields.float('Quantity',  digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'location_type': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production'), ('transit', 'Transit Location for Inter-Companies Transfers')], 'Location Type', required=True),
    }
    
    def init(self, cr):
        drop_view_if_exists(cr, 'report_batch_recall')
        cr.execute("""
         CREATE OR REPLACE VIEW report_batch_recall AS (
            SELECT
                row_number() OVER(ORDER BY rec.product_id,
                                           lot.name,
                                           rec.location_id) AS id,
                rec.product_id AS product_id,
                rec.prodlot_id AS prodlot_id,
                rec.expired_date AS expired_date,
                rec.location_id AS location_id,
                rec.usage AS location_type,
                sum(rec.product_qty) AS product_qty
            FROM
                (
                    (SELECT
                        m.product_id AS product_id,
                        m.prodlot_id AS prodlot_id,
                        m.expired_date AS expired_date,
                        m.location_dest_id AS location_id,
                        loc.usage AS usage,
                        CASE when pt.uom_id = m.product_uom
                        THEN
                            sum(m.product_qty)
                        ELSE
                            sum(round((((m.product_qty/mu.factor)) * pu.factor)/pu.rounding)*pu.rounding)
                        END AS product_qty
                    FROM
                        stock_move m
                      LEFT JOIN
                        stock_production_lot lot
                          ON m.prodlot_id = lot.id
                      LEFT JOIN
                        stock_picking p
                          ON m.picking_id = p.id
                      LEFT JOIN
                        product_product pp
                          ON m.product_id = pp.id
                      LEFT JOIN
                        product_template pt
                          ON pp.product_tmpl_id = pt.id
                      LEFT JOIN
                        product_uom pu
                          ON pt.uom_id = pu.id
                      LEFT JOIN
                        product_uom mu
                          ON m.product_uom = mu.id
                      LEFT JOIN
                        stock_location loc
                          ON m.location_dest_id = loc.id
                    WHERE
                        m.state = 'done'
                        AND
                        loc.usage = 'internal'
                    GROUP BY
                        m.product_id,
                        m.prodlot_id,
                        m.expired_date,
                        m.location_dest_id,
                        pt.uom_id,
                        m.product_uom,
                        p.address_id,
                        loc.usage)
                UNION ALL
                    (SELECT
                        m.product_id AS product_id,
                        m.prodlot_id AS prodlot_id,
                        m.expired_date AS expired_date,
                        m.location_id AS location_id,
                        loc.usage AS usage,
                        CASE when pt.uom_id = m.product_uom
                        THEN
                            -sum(m.product_qty)
                        ELSE
                            -sum(round((((m.product_qty/mu.factor)) * pu.factor)/pu.rounding)*pu.rounding)
                        END AS product_qty
                    FROM 
                        stock_move m
                      LEFT JOIN
                        stock_production_lot lot
                          ON m.prodlot_id = lot.id
                      LEFT JOIN
                        stock_picking p
                          ON m.picking_id = p.id
                      LEFT JOIN
                        product_product pp
                          ON m.product_id = pp.id
                      LEFT JOIN
                        product_template pt
                          ON pp.product_tmpl_id = pt.id
                      LEFT JOIN
                        product_uom pu
                          ON pt.uom_id = pu.id
                      LEFT JOIN
                        product_uom mu
                          ON m.product_uom = mu.id
                      LEFT JOIN
                        stock_location loc
                          ON m.location_id = loc.id
                    WHERE
                        m.state = 'done'
                        AND
                        loc.usage = 'internal'
                    GROUP BY
                        m.product_id,
                        m.prodlot_id,
                        m.expired_date,
                        m.location_id,
                        pt.uom_id,
                        m.product_uom,
                        loc.usage,
                        p.address_id)
            ) AS rec
              LEFT JOIN
                stock_production_lot lot
                  ON rec.prodlot_id = lot.id
            GROUP BY
              rec.product_id,
              rec.expired_date,
              rec.prodlot_id,
              lot.name,
              rec.location_id,
              rec.usage
            ORDER BY
              rec.product_id,
              lot.name,
              rec.location_id
        );""")
        
    def unlink(self, cr, uid, ids, context=None):
        raise osv.except_osv(_('Error !'), _('You cannot delete any record!'))

report_batch_recall()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
