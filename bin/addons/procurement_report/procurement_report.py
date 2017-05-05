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

class procurement_rules_report(osv.osv):
    _name = 'procurement.rules.report'
    _rec_name = 'product_id'
    _auto = False
    _order = 'product_reference, product_name, product_id, location_id'
    
    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        value = {}
        for f in fields:
            value[f] = False

        ret = {}
        for id in ids:
            ret[id] = value
        return ret
    
    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):

        if not args:
            return []
        narg = []
        for arg in args:
            el = arg[0].split('_')
            el.pop()
            narg=[('_'.join(el), arg[1], arg[2])]
        
        return narg
    
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'location_id': fields.many2one('stock.location', string='Location', readonly=True),
        'product_reference': fields.char(size=64, string='Reference', type='char'),
        'product_name': fields.char(size=128, string='Name', type='char'),
        'auto_supply_ok': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Auto Supply', readonly=True),
        'order_cycle_ok': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Order Cycle', readonly=True),
        'min_max_ok': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Min/Max', readonly=True),
        'threshold_ok': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Threshold value', readonly=True),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True, select=1),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True, select=1),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True, select=1),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True, select=1),
        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),
    }
    
    def init(self, cr):
        '''
        Creates the SQL view on database
        '''
        tools.drop_view_if_exists(cr, 'procurement_rules_report')
        cr.execute("""
            CREATE OR REPLACE view procurement_rules_report AS (
                SELECT 
                    row_number() OVER(ORDER BY product_id) AS id,
                    al.product_id AS product_id,
                    al.location_id AS location_id,
                    CASE WHEN sum(al.swas_ok) > 0 THEN 'yes' ELSE 'no' END auto_supply_ok,
                    CASE WHEN sum(al.swoc_ok) > 0 THEN 'yes' ELSE 'no' END order_cycle_ok,
                    CASE WHEN sum(al.swop_ok) > 0 THEN 'yes' ELSE 'no' END min_max_ok,
                    CASE WHEN sum(al.swtv_ok) > 0 THEN 'yes' ELSE 'no' END threshold_ok,
                    prod.default_code AS product_reference,
                    temp.name AS product_name,
                    temp.nomen_manda_0 AS nomen_manda_0,
                    temp.nomen_manda_1 AS nomen_manda_1,
                    temp.nomen_manda_2 AS nomen_manda_2,
                    temp.nomen_manda_3 AS nomen_manda_3
                FROM (
                ((((SELECT
                    1 AS swas_ok,
                    0 AS swoc_ok,
                    0 AS swop_ok,
                    0 AS swtv_ok,
                    swasl.product_id AS product_id,
                    swas.location_id AS location_id
                FROM
                    stock_warehouse_automatic_supply_line swasl
                    LEFT JOIN
                        stock_warehouse_automatic_supply swas
                    ON swasl.supply_id = swas.id
                WHERE swas.active = True)
                UNION
                (SELECT
                    0 AS swas_ok,
                    1 AS swoc_ok,
                    0 AS swop_ok,
                    0 AS swtv_ok,
                    ocpr.product_id AS product_id,
                    swoc.location_id AS location_id
                FROM
                    stock_warehouse_order_cycle_line ocpr
                    LEFT JOIN
                    stock_warehouse_order_cycle swoc
                    ON ocpr.order_cycle_id = swoc.id
                    WHERE swoc.active=True))
                UNION
                (SELECT
                    0 AS swas_ok,
                    0 AS swoc_ok,
                    1 AS swop_ok,
                    0 AS swtv_ok,
                    swopl.product_id AS product_id,
                    swop.location_id AS location_id
                FROM
                    stock_warehouse_orderpoint_line swopl
                    LEFT JOIN
                        stock_warehouse_orderpoint swop
                    ON swopl.supply_id = swop.id
                WHERE swop.active = True))
                UNION
                (SELECT
                    0 AS swas_ok,
                    0 AS swoc_ok,
                    0 AS swop_ok,
                    1 AS swtv_ok,
                    swtvl.product_id AS product_id,
                    swtv.location_id AS location_id
                 FROM
                    threshold_value_line swtvl
                    LEFT JOIN
                    threshold_value swtv
                    ON swtvl.threshold_value_id = swtv.id
                    WHERE swtv.active=True))
                ) AS al
                LEFT JOIN
                    product_product prod
                    ON al.product_id = prod.id
                LEFT JOIN
                    product_template temp
                    ON prod.product_tmpl_id = temp.id
                WHERE temp.type not in ('service', 'service_recep', 'consu')
                GROUP BY al.product_id, al.location_id, prod.default_code, temp.name, temp.nomen_manda_0, temp.nomen_manda_1, temp.nomen_manda_2, temp.nomen_manda_3
                ORDER BY prod.default_code, temp.name, al.product_id, al.location_id
            )
            """)
    
procurement_rules_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
