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

class stock_batch_recall(osv.osv_memory):
    _name = 'stock.batch.recall'
    _description = 'Batch Recall'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product'),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'expired_date': fields.date(string='Expired Date')
    }
    
    def get_ids(self, cr, uid, ids, context={}):
        '''
        Returns all stock moves according to parameters
        '''
        move_obj = self.pool.get('stock.move')
        
        domain = []
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
    
    def return_view(self, cr, uid, ids, context={}):
        '''
        Print the report on Web client (search view)
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        
        context = {'group_by': [],
                   'full':'1',
                   'group_by_no_leaf': 1}
        
        domain =self.get_ids(cr, uid, ids)
        
        result = mod_obj._get_id(cr, uid, 'stock_batch_recall', 'action_report_batch_recall')
        id = mod_obj.read(cr, uid, [result], ['res_id'], context=context)[0]['res_id']
        
        result = act_obj.read(cr, uid, [id], context=context)[0]
        
        for d in domain:
            context.update({'search_default_%s' %d[0]: d[2]})

        result['domain'] = domain
        result['context'] = context
        
        return result
        
stock_batch_recall()

class report_batch_recall(osv.osv):
    _name = 'report.batch.recall'
    _description = 'Batch Recall'
    _auto = False
    _columns = {
        'date': fields.datetime('Date', readonly=True),
        'partner_id':fields.many2one('res.partner.address', 'Partner', readonly=True),
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'product_categ_id':fields.many2one('product.category', 'Product Category', readonly=True),
        'location_id': fields.many2one('stock.location', 'Location', readonly=True),
        'prodlot_id': fields.many2one('stock.production.lot', 'Lot', readonly=True),
        'expired_date': fields.date('Expired Date', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'product_qty':fields.float('Quantity',  digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'value' : fields.float('Total Value',  digits_compute=dp.get_precision('Account'), required=True),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Confirmed'), ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
              help='When the stock move is created it is in the \'Draft\' state.\n After that it is set to \'Confirmed\' state.\n If stock is available state is set to \'Avaiable\'.\n When the picking it done the state is \'Done\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'location_type': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production'), ('transit', 'Transit Location for Inter-Companies Transfers')], 'Location Type', required=True),
    }
    
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_batch_recall')
        cr.execute("""
CREATE OR REPLACE view report_batch_recall AS (
    (SELECT
        min(m.id) as id, m.date as date,
        m.address_id as partner_id, m.location_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.expired_date::date,
        m.state as state, m.prodlot_id as prodlot_id,
        coalesce(sum(-pt.standard_price * m.product_qty)::decimal, 0.0) as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(-m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(-m.product_qty * pu.factor)::decimal, 0.0) END as product_qty
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_id=l.id)
    WHERE l.usage in ('internal', 'customer')
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id,  m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
) UNION ALL (
    SELECT
        -m.id as id, m.date as date,
        m.address_id as partner_id, m.location_dest_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.expired_date::date,
        m.state as state, m.prodlot_id as prodlot_id,
        coalesce(sum(pt.standard_price * m.product_qty )::decimal, 0.0) as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(m.product_qty * pu.factor)::decimal, 0.0) END as product_qty
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_dest_id=l.id)
    WHERE l.usage in ('internal', 'customer')
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id, m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
    )
);
        """)

report_batch_recall()

class stock_production_lot(osv.osv):
    _name = 'stock.production.lot'
    _inherit = 'stock.production.lot'

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=80):
        '''
        Add the possibility to search a lot with its prefix
        '''
        res = super(stock_production_lot, self).name_search(cr, uid, name, args, operator, context, limit)
        
        ids = []
        res_ids = []
        prefix = False
        obj_name = False
        domain = []
        
        if len(name) > 1:
            tab_name = name.split('/')
            prefix = tab_name[0]
            if tab_name and len(tab_name) > 1:
                obj_name = name.split('/')[1][1:-1]
                
        if obj_name:
            domain.append(('name', '=ilike', '%%%s' %obj_name))
        if prefix:
            domain.append(('prefix', '=ilike', '%%%s' %prefix))
            
        ids = self.search(cr, uid, domain)
        
        for r in res:
            if r[0] not in ids:
                ids.append(r[0])

        return self.name_get(cr, uid, ids)

stock_production_lot()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
