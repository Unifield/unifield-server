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
from osv import fields,osv
from decimal_precision import decimal_precision as dp


class report_procurement_policies(osv.osv):
    _name = 'report.procurement.policies'
    _description = "Procurement Statistics"
    _auto = False
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='S. Location'),
        'categ_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Product'),
        'automatic_supply_id': fields.many2one('stock.warehouse.automatic.supply', string='Auto. Supply'),
        'order_cycle_id': fields.many2one('stock.warehouse.order.cycle', string='Order Cycle'),
        'mini_rule_id': fields.many2one('stock.warehouse.orderpoint', string='Mini. Stock'),
    }

    
    def init(self, cr):
        '''
        Creates the SQL view on database
        '''
        tools.drop_view_if_exists(cr, 'report_procurement_policies')
        cr.execute("""
            CREATE OR REPLACE view report_procurement_policies AS (
                SELECT row_number() OVER(ORDER BY product_id) AS id,
                       al.location_id AS location_id,
                       al.product_id AS product_id,
                       al.categ_id AS categ_id,
                       al.automatic_supply_id AS automatic_supply_id,
                       al.order_cycle_id AS order_cycle_id,
                       al.mini_rule_id AS mini_rule_id
                FROM(SELECT 
                       sloc.id AS location_id,
                       p.id AS product_id,
                       t.categ_id AS categ_id,
                       swas.id AS automatic_supply_id,
                       swoc.id AS order_cycle_id,
                       swo.id AS mini_rule_id
                FROM
                    stock_location sloc
                    JOIN product_product p
                        ON True
                    JOIN product_template t
                        ON p.product_tmpl_id = t.id
                    LEFT JOIN stock_warehouse_automatic_supply swas
                        ON swas.location_id = sloc.id AND (swas.product_id = p.id OR
                                                            (swas.category_id = t.categ_id AND
                                                             p.id IN (SELECT swasl.product_id FROM stock_warehouse_automatic_supply_line swasl
                                                                      WHERE swasl.supply_id = swas.id)))
                    LEFT JOIN stock_warehouse_order_cycle swoc
                        ON swoc.location_id = sloc.id AND (swoc.product_id = p.id OR
                                                            (swoc.category_id = t.categ_id AND
                                                             p.id NOT IN (SELECT ocpr.product_id FROM order_cycle_product_rel ocpr
                                                                          WHERE ocpr.order_cycle_id = swoc.id)))
                    LEFT JOIN stock_warehouse_orderpoint swo
                        ON swo.location_id = sloc.id AND swo.product_id = p.id
                WHERE p.active = TRUE AND (swas.id IS NOT NULL OR swoc.id IS NOT NULL OR swo.id IS NOT NULL)
 UNION SELECT 
                       NULL AS location_id,
                       p.id AS product_id,
                       t.categ_id AS categ_id,
                       NULL AS automatic_supply_id,
                       NULL AS order_cycle_id,
                       NULL AS mini_rule_id
                FROM
                    product_product p
                    JOIN product_template t
                        ON p.product_tmpl_id = t.id
                WHERE p.active = TRUE 
              AND p.id NOT IN (SELECT 
                       p.id AS product_id
                FROM
                    product_product p
                    JOIN product_template t
                        ON p.product_tmpl_id = t.id
                    LEFT JOIN stock_warehouse_automatic_supply swas
                        ON (swas.product_id = p.id OR
                                                            (swas.category_id = t.categ_id AND
                                                             p.id IN (SELECT swasl.product_id FROM stock_warehouse_automatic_supply_line swasl
                                                                      WHERE swasl.supply_id = swas.id)))
                    LEFT JOIN stock_warehouse_order_cycle swoc
                        ON (swoc.product_id = p.id OR
                                                            (swoc.category_id = t.categ_id AND
                                                             p.id NOT IN (SELECT ocpr.product_id FROM order_cycle_product_rel ocpr
                                                                          WHERE ocpr.order_cycle_id = swoc.id)))
                    LEFT JOIN stock_warehouse_orderpoint swo
                        ON swo.product_id = p.id
                WHERE p.active = TRUE AND (swas.id IS NOT NULL OR swoc.id IS NOT NULL OR swo.id IS NOT NULL))
        GROUP BY p.id, t.categ_id
                ) AS al
            )
        """)
        
report_procurement_policies()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: