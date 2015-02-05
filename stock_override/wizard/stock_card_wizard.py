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
        'location_id': fields.many2one('stock.location', string='Location'),
        'all_inout': fields.boolean(string='Show all IN/OUT'),
        'product_id': fields.many2one('product.product', string='Product',
                                      required=True),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one',
                                 relation='product.uom', string='UoM'),
        'perishable': fields.boolean(string='Perishable'),
        'prodlot_id': fields.many2one('stock.production.lot',
                                      string='Batch number'),
        'from_date': fields.date(string='From date'),
        'to_date': fields.date(string='To date'),
        'available_stock': fields.float(digits=(16,2), string='Available stock'),
        'card_lines': fields.one2many('stock.card.wizard.line', 'card_id',
                                      string='Card lines'),
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_card_wizard, self).default_get(cr, uid, fields, context=context)
        product_id = context.get('product_id', False)
        perishable = False
        if product_id:
            prod_obj = self.pool.get('product.product')
            product_r = prod_obj.read(cr, uid, [product_id], ['perishable'], context=context)
            if product_r:
                perishable = product_r[0]['perishable']
        res.update({
            'product_id': product_id,
            'perishable': perishable,
            'to_date': time.strftime('%Y-%m-%d'),
        })
        return res

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

    def show_card(self, cr, uid, ids, context=None):
        '''
        Create the card lines and display the form view of the card
        according to parameters.

        First, we will compute the stock qty at the start date
        Then, for each stock move, we will create a line and update the
        balance to show the stock qty after the processing of the move
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        loc_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('stock.card.wizard.line')

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        card = self.browse(cr, uid, ids[0], context=context)
        location_id = card.location_id and card.location_id.id or False
        location_ids = []
        location_usage = ['customer', 'supplier', 'inventory']

        if location_id:
            context.update({'location': location_id})
            location_ids = loc_obj.search(cr, uid,
                                    [('location_id', 'child_of', location_id)],
                                    context=context)

        # Set the context to compute stock qty at the start date
        context.update({'to_date': card.from_date})

        prodlot_id = card.prodlot_id and card.prodlot_id.id or False
        product = product_obj.browse(cr, uid, card.product_id.id,
                                                        context=context)
        if not card.from_date:
            initial_stock = 0.00
        else:
            initial_stock = product.qty_available

        domain = [('product_id', '=', product.id),
                  ('prodlot_id', '=', prodlot_id),
                  ('state', '=', 'done')]

        if card.from_date:
            domain.append(('date', '>=', card.from_date))

        if card.to_date:
            domain.append(('date', '<=', card.to_date))

        if location_id:
            domain.extend(['|',
                           ('location_id', 'child_of', location_id),
                           ('location_dest_id', 'child_of', location_id)])
        else:
            domain.extend(['|',
                           ('location_id.usage', 'in', location_usage),
                           ('location_dest_id.usage', 'in', location_usage)])

        # Create one line per stock move
        move_ids = move_obj.search(cr, uid, domain,order='date asc',
                                                        context=context)

        for move in move_obj.browse(cr, uid, move_ids, context=context):
            # If the move is from the same location as destination
            if move.location_dest_id.id in location_ids and \
               move.location_id.id in location_ids:
                continue

            # If the move doesn't pass through stock
            if move.location_dest_id.usage in location_usage and \
                    move.location_id.usage in location_usage:
                continue

            if move.product_qty == 0.00:
                continue

            in_qty, out_qty = 0.00, 0.00
            move_location = False
            qty = uom_obj._compute_qty(cr, uid, move.product_uom.id,
                                                move.product_qty,
                                                move.product_id.uom_id.id)

            if location_ids:
                if move.location_dest_id.id in location_ids:
                    in_qty = qty
                    move_location = move.location_id.name
                elif move.location_id.id in location_ids:
                    out_qty = qty
                    move_location = move.location_dest_id.name
            else:
                if move.location_dest_id.usage not in location_usage:
                    in_qty = qty
                    move_location = move.location_id.name
                elif move.location_id.usage not in location_usage:
                    out_qty = qty
                    move_location = move.location_dest_id.name
                if move.picking_id and move.picking_id.partner_id:
                    move_location = move.picking_id.partner_id.name

            initial_stock = initial_stock + in_qty - out_qty

            doc_ref = (move.picking_id and move.picking_id.name) or \
                      (move.init_inv_ids and move.init_inv_ids[0].name) or \
                      (move.inventory_ids and move.inventory_ids[0].name) or ''

            line_values = {
                'card_id': ids[0],
                'date_done': move.date,
                'doc_ref': doc_ref,
                'origin': move.picking_id and move.picking_id.origin or False,
                'qty_in': in_qty,
                'qty_out': out_qty,
                'balance': initial_stock,
                'src_dest': move_location,
                'notes': move.picking_id and move.picking_id.note  or '',
            }

            line_id = line_obj.create(cr, uid, line_values, context=context)

        self.write(cr, uid, [ids[0]], {'available_stock': initial_stock},
                                                            context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.card.wizard',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'res_id': ids[0],
                'target': 'current',
                'nodestroy': True,
                'context': context}

    def print_pdf(self, cr, uid, ids, context=None):
        '''
        Print the PDF report according to parameters
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
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
        'card_id': fields.many2one('stock.card.wizard', string='Card',
                                   required=True),
        'date_done': fields.datetime(string='Date'),
        'doc_ref': fields.char(size=64, string='Doc. Ref.'),
        'origin': fields.char(size=512, string='Origin'),
        'qty_in': fields.float(digits=(16,2), string='Qty IN'),
        'qty_out': fields.float(digits=(16,2), string='Qty OUT'),
        'balance': fields.float(digits=(16,2), string='Balance'),
        'src_dest': fields.char(size=128, string='Source/Destination'),
        'partner_id': fields.many2one('res.partner', string='Source/Destination'),
        'notes': fields.text(string='Notes'),
    }

stock_card_wizard_line()
