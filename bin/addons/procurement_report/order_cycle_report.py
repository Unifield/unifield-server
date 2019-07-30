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

class order_cycle_rules_report(osv.osv):
    _name = 'order.cycle.rules.report'
    _rec_name = 'rule_id'
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

    def _get_nomen_name(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns a string with all nomenclature levels separated by '/'
        '''
        res = {}

        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = ''
            if rule.nomen_manda_0:
                res[rule.id] = rule.nomen_manda_0.name
            if rule.nomen_manda_1:
                res[rule.id] += '/'
                res[rule.id] += rule.nomen_manda_1.name
            if rule.nomen_manda_2:
                res[rule.id] += '/'
                res[rule.id] += rule.nomen_manda_2.name
            if rule.nomen_manda_3:
                res[rule.id] += '/'
                res[rule.id] += rule.nomen_manda_3.name

        return res

    def _get_stock(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns stock value of a product
        '''
        if context is None:
            context = {}
        res = {}

        ir_data = self.pool.get('ir.model.data')
        stock_location = ir_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        # TODO: Change msf_profile by msf_location_setup module
        intermediate_stock = ir_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
        consumption_stock = ir_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')[1]

        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = {'stock': 0.00,
                            'intermediate_stock': 0.00,
                            'consumption_stock': 0.00,
                            'amc': 0.00,
                            'fmc': 0.00}

            if rule.product_id:
                res[rule.id]['amc'] = rule.product_id.product_amc
                res[rule.id]['fmc'] = rule.product_id.reviewed_consumption

                c = context.copy()
                c.update({'location': stock_location, 'compute_child': True})
                product = self.pool.get('product.product').browse(cr, uid, rule.product_id.id, context=c)
                res[rule.id]['stock'] = product.qty_available

                c2 = context.copy()
                c2.update({'location': consumption_stock, 'compute_child': True})
                product2 = self.pool.get('product.product').browse(cr, uid, rule.product_id.id, context=c2)
                res[rule.id]['consumption_stock'] = product2.qty_available

                c3 = context.copy()
                c3.update({'location': intermediate_stock, 'compute_child': True})
                product3 = self.pool.get('product.product').browse(cr, uid, rule.product_id.id, context=c3)
                res[rule.id]['intermediate_stock'] = product3.qty_available

            total_stock = res[rule.id]['stock'] + res[rule.id]['intermediate_stock'] + res[rule.id]['consumption_stock']
            moh = res[rule.id]['amc'] > 0 and total_stock / res[rule.id]['amc'] or 0.00

            res[rule.id].update({'total_stock': total_stock, 'moh': moh})

        return res

    _columns = {
        'rule_id': fields.many2one('stock.warehouse.order.cycle', string='Rules reference', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'location_id': fields.many2one('stock.location', string='Location', readonly=True),
        'product_reference': fields.char(size=64, string='Reference', type='char'),
        'product_name': fields.char(size=128, string='Name', type='char'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True, select=1),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True, select=1),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True, select=1),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True, select=1),
        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_name': fields.function(_get_nomen_name, method=True, type='char', string='Nomenclature level', readonly=True),
        'product_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'frequency_id': fields.many2one('stock.frequence', string='Frequency', readonly=True),
        'delivery_lt': fields.float(digits=(16,2), string='Delivery LT', readonly=True, related_uom='product_uom_id'),
        'order_coverage': fields.float(digits=(16,2), string='Order coverage', readonly=True, related_uom='product_uom_id'),
        'safety_time': fields.float(digits=(16,2), string='Safety stock (in months)', readonly=True),
        'safety_stock': fields.float(digits=(16,2), string='Safety stock', readonly=True, related_uom='product_uom_id'),
        'consumption': fields.char(size=64, string='Consumption', readonly=True),
        'total_stock': fields.function(_get_stock, method=True, type='float', string='Total stock', readonly=True, multi='stock', related_uom='product_uom_id'),
        'stock': fields.function(_get_stock, method=True, type='float', string='Stock (stock & children)', readonly=True, multi='stock', related_uom='product_uom_id'),
        'intermediate_stock': fields.function(_get_stock, method=True, type='float', string='ISi stocks', readonly=True, multi='stock', related_uom='product_uom_id'),
        'consumption_stock': fields.function(_get_stock, method=True, type='float', string='CUi stocks', readonly=True, multi='stock', related_uom='product_uom_id'),
        'amc': fields.function(_get_stock, method=True, type='float', string='AMC', readonly=True, multi='stock'),
        'moh': fields.function(_get_stock, method=True, type='float', string='MoH', readonly=True, multi='stock'),
        'fmc': fields.function(_get_stock, method=True, type='float', string='FMC', readonly=True, multi='stock'),
    }

    def init(self, cr):
        '''
        Creates the SQL view on database
        '''
        tools.drop_view_if_exists(cr, 'order_cycle_rules_report')
        cr.execute("""
            CREATE OR REPLACE view order_cycle_rules_report AS (
                SELECT 
                    row_number() OVER(ORDER BY line.product_id) AS id,
                    min.id AS rule_id,
                    line.product_id AS product_id,
                    min.location_id AS location_id,
                    min.frequence_id AS frequency_id,
                    temp.uom_id AS product_uom_id,
                    min.leadtime AS delivery_lt,
                    min.order_coverage AS order_coverage,
                    min.safety_stock_time AS safety_time,
                    line.safety_stock AS safety_stock,
                    CASE WHEN min.past_consumption = 't' THEN 'AMC' ELSE 'FMC' END consumption,
                    prod.default_code AS product_reference,
                    temp.name AS product_name,
                    temp.nomen_manda_0 AS nomen_manda_0,
                    temp.nomen_manda_1 AS nomen_manda_1,
                    temp.nomen_manda_2 AS nomen_manda_2,
                    temp.nomen_manda_3 AS nomen_manda_3
                FROM
                    stock_warehouse_order_cycle min
                    LEFT JOIN
                        stock_warehouse_order_cycle_line line
                        ON
                        line.order_cycle_id = min.id
                    LEFT JOIN
                        product_product prod
                        ON
                        line.product_id = prod.id
                    LEFT JOIN
                        product_template temp
                        ON
                        prod.product_tmpl_id = temp.id
            )
            """)

order_cycle_rules_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
