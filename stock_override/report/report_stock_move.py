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

import tools
from osv import fields,osv
from decimal_precision import decimal_precision as dp


class report_stock_move(osv.osv):
    _name = "report.stock.move"
    _description = "Moves Statistics"
    _auto = False

    def _get_order_information(self, cr, uid, ids, fields_name, arg, context=None):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}
        
        for report in self.browse(cr, uid, ids, context=context):
            move = report.move
            res[report.id] = {'order_priority': False,
                            'order_category': False,
                            'order_type': False}
            order = False
            
            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id
                
            if order:
                res[report.id] = {}
                if 'order_priority' in fields_name:
                    res[report.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[report.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[report.id]['order_type'] = order.order_type
        
        return res

    _columns = {
        'date': fields.date('Date', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'),
            ('05','May'), ('06','June'), ('07','July'), ('08','August'), ('09','September'),
            ('10','October'), ('11','November'), ('12','December')], 'Month',readonly=True),
        'partner_id':fields.many2one('res.partner', 'Partner', readonly=True),
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'product_uom': fields.many2one('product.uom', 'UoM', readonly=True),
        'company_id':fields.many2one('res.company', 'Company', readonly=True),
        'picking_id':fields.many2one('stock.picking', 'Reference', readonly=True),
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('other', 'Others')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'location_id': fields.many2one('stock.location', 'Source Location', readonly=True, select=True, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', readonly=True, select=True, help="Location where the system will stock the finished products."),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Closed'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True),
        'product_qty':fields.integer('Quantity',readonly=True),
        'categ_id': fields.many2one('product.nomenclature', 'Family', ),
        'product_qty_in':fields.integer('In Qty',readonly=True),
        'product_qty_out':fields.integer('Out Qty',readonly=True),
        'value' : fields.float('Total Value', required=True),
        'day_diff2':fields.float('Lag (Days)',readonly=True,  digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'day_diff1':fields.float('Planned Lead Time (Days)',readonly=True, digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'day_diff':fields.float('Execution Lead Time (Days)',readonly=True,  digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'stock_journal': fields.many2one('stock.journal','Stock Journal', select=True),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection', 
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                                 ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                                 ('direct', 'Direct Purchase Order')], multi='move_order'),
        'comment': fields.char(size=128, string='Comment'),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', states={'done': [('readonly', True)]}, help="Batch number is used to put a serial number on the production", select=True),
        'tracking_id': fields.many2one('stock.tracking', 'Pack', select=True, states={'done': [('readonly', True)]}, help="Logistical shipping unit: pallet, box, pack ..."),
        'origin': fields.related('picking_id','origin',type='char', size=512, relation="stock.picking", string="Origin", store=True),
        'move': fields.many2one('stock.move', string='Move'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'currency_id': fields.many2one('res.currency', string='Currency'),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_stock_move')
        cr.execute("""
            CREATE OR REPLACE view report_stock_move AS (
                SELECT
                        min(sm_id) as id,
                        date_trunc('day',al.dp) as date,
                        al.curr_year as year,
                        al.curr_month as month,
                        al.curr_day as day,
                        al.curr_day_diff as day_diff,
                        al.curr_day_diff1 as day_diff1,
                        al.curr_day_diff2 as day_diff2,
                        al.location_id as location_id,
                        al.picking_id as picking_id,
                        al.company_id as company_id,
                        al.location_dest_id as location_dest_id,
                        al.product_qty,
                        al.out_qty as product_qty_out,
                        al.in_qty as product_qty_in,
                        al.partner_id as partner_id,
                        al.product_id as product_id,
                        al.state as state ,
                        al.product_uom as product_uom,
                        al.categ_id as categ_id,
                        al.sm_id as move,
                        al.tracking_id as tracking_id,
                        al.comment as comment,
                        al.prodlot_id as prodlot_id,
                        al.origin as origin,
                        al.reason_type_id as reason_type_id,
                        coalesce(al.type, 'other') as type,
                        al.stock_journal as stock_journal,
                        sum(al.in_value - al.out_value) as value,
                        1 as currency_id
                    FROM (SELECT
                        CASE WHEN sp.type in ('out') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                            ELSE 0.0
                            END AS out_qty,
                        CASE WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                            ELSE 0.0
                            END AS in_qty,
                        CASE WHEN sp.type in ('out') THEN
                            sum((sm.product_qty / pu.factor) * u.factor) * pt.standard_price
                            ELSE 0.0
                            END AS out_value,
                        CASE WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor) * pt.standard_price
                            ELSE 0.0
                            END AS in_value,
                        min(sm.id) as sm_id,
                        sm.date as dp,
                        to_char(date_trunc('day',sm.date), 'YYYY') as curr_year,
                        to_char(date_trunc('day',sm.date), 'MM') as curr_month,
                        to_char(date_trunc('day',sm.date), 'YYYY-MM-DD') as curr_day,
                        avg(date(sm.date)-date(sm.create_date)) as curr_day_diff,
                        avg(date(sm.date_expected)-date(sm.create_date)) as curr_day_diff1,
                        avg(date(sm.date)-date(sm.date_expected)) as curr_day_diff2,
                        sm.location_id as location_id,
                        sm.location_dest_id as location_dest_id,
                        sm.prodlot_id as prodlot_id,
                        sm.comment as comment,
                        sm.tracking_id as tracking_id,
                        CASE 
                          WHEN sp.type in ('out') THEN
                            sum((-sm.product_qty / pu.factor) * u.factor)
                          WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                          ELSE 0.0
                          END AS product_qty,
                        pt.nomen_manda_2 as categ_id,
                        sp.partner_id2 as partner_id,
                        sm.product_id as product_id,
                        sm.origin as origin,
                        sm.reason_type_id as reason_type_id,
                        sm.picking_id as picking_id,
                            sm.company_id as company_id,
                            sm.state as state,
                            pt.uom_id as product_uom,
                            sp.type as type,
                            sp.stock_journal_id AS stock_journal
                    FROM
                        stock_move sm
                        LEFT JOIN stock_picking sp ON (sm.picking_id=sp.id)
                        LEFT JOIN product_product pp ON (sm.product_id=pp.id)
                        LEFT JOIN product_uom pu ON (sm.product_uom=pu.id)
                        LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                        LEFT JOIN product_uom u ON (pt.uom_id = u.id)
                        LEFT JOIN stock_location sl ON (sm.location_id = sl.id)

                    GROUP BY
                        sm.id,sp.type, sm.date,sp.partner_id2,
                        sm.product_id,sm.state,pt.uom_id,sm.date_expected, sm.origin,
                        sm.product_id,pt.standard_price, sm.picking_id, sm.product_qty, sm.prodlot_id, sm.comment, sm.tracking_id,
                        sm.company_id,sm.product_qty, sm.location_id,sm.location_dest_id,pu.factor,pt.nomen_manda_2, sp.stock_journal_id, sm.reason_type_id)
                    AS al

                    GROUP BY
                        al.out_qty,al.in_qty,al.curr_year,al.curr_month,
                        al.curr_day,al.curr_day_diff,al.curr_day_diff1,al.curr_day_diff2,al.dp,al.location_id,al.location_dest_id,
                        al.partner_id,al.product_id,al.state,al.product_uom, al.sm_id, al.origin,
                        al.picking_id,al.company_id,al.type,al.product_qty, al.categ_id, al.stock_journal, al.tracking_id, al.comment, al.prodlot_id, al.reason_type_id
               )
        """)

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        if fields is None:
            fields = []
        context['with_expiry'] = 1
        return super(report_stock_move, self).read(cr, uid, ids, fields, context, load)
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        '''
        Add functional currency on all lines
        '''
        res = super(report_stock_move, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby)
        if self._name == 'report.stock.move':
            for data in res:
                # If no information to display, don't display the currency
                if not '__count' in data or data['__count'] != 0:
                    currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
                    data.update({'currency_id': (currency.id, currency.name)})

                product_id = 'product_id' in data and data['product_id'] and data['product_id'][0] or False
                if data.get('__domain'):
                    for x in data.get('__domain'):
                        if x[0] == 'product_id':
                            product_id = x[2]

                if isinstance(product_id, str):
                    product_id = self.pool.get('product.product').search(cr, uid, [('default_code', '=', product_id)], context=context)
                    if product_id:
                        product_id = product_id[0]
                if product_id:
                    uom = self.pool.get('product.product').browse(cr, uid, product_id, context=context).uom_id
                    data.update({'product_uom': (uom.id, uom.name)})

                if not product_id and 'product_qty' in data:
                    data.update({'product_qty': ''})
                if not product_id and 'product_qty_in' in data:
                    data.update({'product_qty_in': ''})
                if not product_id and 'product_qty_out' in data:
                    data.update({'product_qty_out': ''})
                
        return res

report_stock_move()
