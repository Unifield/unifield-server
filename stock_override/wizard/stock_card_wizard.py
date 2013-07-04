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

from osv import fields, osv
from tools.translate import _
import time


class stock_card_wizard(osv.osv_memory):
    _name = 'stock.card.wizard'
    _description = 'Stock card'

    _columns = {
        'location_id': fields.many2one('stock.location', string='Location', 
                                       required=True),
        'product_id': fields.many2one('product.product', string='Product', 
                                      required=True),
        'perishable': fields.boolean(string='Perishable'),
        'prodlot_id': fields.many2one('stock.production.lot', 
                                      string='Batch number'),
        'from_date': fields.date(string='From date'),
        'to_date': fields.date(string='To date'),
    }


    def _get_default_product(self, cr, uid, context=None):
        '''
        If a product is passed in the context, set it on wizard form
        '''
        if not context:
            context = {}

        return context.get('product_id', False)


    _defaults = {
        'product_id': _get_default_product,
        'to_date': lambda *a: time.strftime('%Y-%m-%d'),
    }


    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        Set the 'perishable' field if the selected product is perishable.
        '''
        prod_obj = self.pool.get('product.product')

        if not context:
            context = {}

        if not product_id:
            return {'value': {'perishable': False}}

        product = prod_obj.browse(cr, uid, product_id, context=context)

        return {'value': {'perishable': product.perishable}}

    def print_pdf(self, cr, uid, ids, context=None):
        '''
        Print the PDF report according to parameters
        '''
        if not context:
            context = {}

        if isistance(ids, (int, long)):
            ids = [ids]

        raise NotImplementedError

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Print the Excel (XML) report according to parameters
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        raise NotImplementedError

stock_card_wizard()


class stock_card_wizard_line(osv.osv_memory):
    _name = 'stock.card.wizard.line'
    _description = 'Stock card line'

    _columns = {
        'date_done': fields.datetime(string='Date'),
        'picking_id': fields.many2one('stock.picking', string='Doc. Ref.'),
        'origin': fields.char(size=64, string='Origin'),
        'qty_in': fields.float(digits=(16,2), string='Qty IN'),
        'qty_out': fields.float(digits=(16,2), string='Qty OUT'),
        'balance': fields.float(digits=(16,2), string='Balance'),
        'location_id': fields.many2one('stock.location', string='Source/Destination'),
        'notes': fields.text(string='Notes'),
    }

stock_card_wizard_line()
