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
                                 relation='product.uom', string='UoM', write_relate=False),
        'perishable': fields.boolean(string='Perishable'),
        'prodlot_id': fields.many2one('stock.production.lot',
                                      string='Batch number'),
        'expiry_date': fields.related(
            'prodlot_id',
            'life_date',
            type='date',
            string='Expiry date',
            readonly=True,
        ),
        'from_date': fields.date(string='From date'),
        'to_date': fields.date(string='To date'),
        'real_stock': fields.float(digits=(16,2), string='Real stock'),
        'card_lines': fields.one2many('stock.card.wizard.line', 'card_id',
                                      string='Card lines'),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        res = super(stock_card_wizard, self).default_get(cr, uid, fields, context=context, from_web=from_web)
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

    def onchange_all_inout(self, cr, uid, ids, all_inout, context=None):
        '''
        Empty the 'location_id' field if the 'all_inout' field is selected.
        '''
        if not context:
            context = {}

        if all_inout:
            return {'value': {'location_id': False}}

        return {}

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
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('stock.card.wizard.line')
        pi_line_obj = self.pool.get('physical.inventory.counting')
        # 'Old' physical inventories
        oldinv_line_obj = self.pool.get('stock.inventory.line')

        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        card = self.browse(cr, uid, ids[0], context=context)
        location_id = card.location_id and card.location_id.id or False
        location_ids = []
        location_usage = ['customer', 'supplier', 'inventory']

        if location_id:
            context.update({'location': location_id})
            location_ids = [location_id]

        # Set the context to compute stock qty at the start date
        context.update({'to_date': card.from_date})

        prodlot_id = card.prodlot_id and card.prodlot_id.id or False
        product = product_obj.browse(cr, uid, card.product_id.id, context=context)
        if not card.from_date:
            initial_stock = 0.00
        else:
            initial_stock = product.qty_available

        domain = [('product_id', '=', product.id), ('state', '=', 'done')]
        if prodlot_id:
            domain.append(('prodlot_id', '=', prodlot_id))

        # "Old" physical inventory
        inv_dom = [
            ('product_id', '=', product.id),
            ('prod_lot_id', '=', prodlot_id),
            ('dont_move', '=', True),
            ('inventory_id.state', '=', 'done')
        ]

        pi_counting_dom = [
            ('product_id', '=', product.id),
            ('prod_lot_id', '=', prodlot_id),
            ('discrepancy', '=', False),
            ('inventory_id.state', 'in', ['confirmed', 'closed'])
        ]

        if card.from_date:
            domain.append(('date', '>=', card.from_date))
            inv_dom.append(('inventory_id.date_done', '>=', card.from_date))
            pi_counting_dom.extend([
                '|',
                ('inventory_id.date_done', '>=', card.from_date),
                '&',
                ('inventory_id.state', '=', 'confirmed'),
                ('inventory_id.date_confirmed', '>=', card.from_date),
            ])

        if card.to_date:
            domain.append(('date', '<=', card.to_date))
            inv_dom.append(('inventory_id.date_done', '<=', card.to_date + ' 23:59:00'))
            pi_counting_dom.extend([
                '|',
                ('inventory_id.date_done', '<=', card.to_date + ' 23:59:00'),
                '&',
                ('inventory_id.state', '=', 'confirmed'),
                ('inventory_id.date_confirmed', '>=', card.to_date),
            ])

        if location_id:
            domain.extend(['|',
                           ('location_id', '=', location_id),
                           ('location_dest_id', '=', location_id)])
            inv_dom.append(('location_id', '=', location_id))
            pi_counting_dom.append(('inventory_id.location_id', '=', location_id))
        else:
            domain.extend(['|',
                           ('location_id.usage', 'in', location_usage),
                           ('location_dest_id.usage', 'in', location_usage)])

        # Lines from "old" physical inventories
        inv_line_ids = oldinv_line_obj.search(cr, uid, inv_dom, context=context)
        inv_line_to_add = {}
        for line in oldinv_line_obj.browse(cr, uid, inv_line_ids, context=context):
            inv_line_to_add.setdefault(line.inventory_id.date_done, []).append({
                'card_id': ids[0],
                'date_done': line.inventory_id.date_done,
                'doc_ref': line.inventory_id.name,
                'origin': False,
                'qty_in': 0,
                'qty_out': 0,
                'balance': 0,
                'src_dest': line.product_id.property_stock_inventory and line.product_id.property_stock_inventory.name or False,
                'notes': '',
            })

        inv_line_dates = list(inv_line_to_add.keys())
        inv_line_dates.sort()

        pi_counting_line_ids = pi_line_obj.search(cr, uid, pi_counting_dom, context=context)
        pi_counting_line_to_add = {}
        for line in pi_line_obj.browse(cr, uid, pi_counting_line_ids, context=context):
            pi_counting_line_to_add.setdefault(line.inventory_id.date_done or line.inventory_id.date_confirmed, []).append({
                'card_id': ids[0],
                'date_done': line.inventory_id.date_done or line.inventory_id.date_confirmed,
                'doc_ref': 'INV:' + str(line.inventory_id.id) + ':' + line.inventory_id.name,
                'origin': False,
                'qty_in': 0,
                'qty_out': 0,
                'balance': 0,
                'src_dest': line.product_id.property_stock_inventory and line.product_id.property_stock_inventory.name or False,
                'notes': '',
            })

        pi_counting_line_dates = list(pi_counting_line_to_add.keys())
        pi_counting_line_dates.sort()


        # Create one line per stock move
        move_ids = move_obj.search(cr, uid, domain, order='date asc', context=context)

        for move in move_obj.browse(cr, uid, move_ids, context=context):
            # If the move is from the same location as destination
            if move.location_dest_id.id in location_ids and move.location_id.id in location_ids:
                continue

            # If the move doesn't pass through stock
            if move.location_dest_id.usage in location_usage and move.location_id.usage in location_usage:
                continue

            if move.product_qty == 0.00:
                continue

            while inv_line_dates and inv_line_dates[0] < move.date:
                inv_data = inv_line_dates.pop(0)
                for new_line in inv_line_to_add[inv_data]:
                    new_line['balance'] = initial_stock
                    line_obj.create(cr, uid, new_line, context=context)

            while pi_counting_line_dates and pi_counting_line_dates[0] < move.date:
                inv_data = pi_counting_line_dates.pop(0)
                for new_line in pi_counting_line_to_add[inv_data]:
                    new_line['balance'] = initial_stock
                    line_obj.create(cr, uid, new_line, context=context)

            in_qty, out_qty = 0.00, 0.00
            move_location = False
            to_unit = False
            if move.product_uom.id != move.product_id.uom_id.id:
                to_unit = move.product_id.uom_id.id
            qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, to_unit)

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
                      (move.inventory_ids and move.inventory_ids[0].name) or move.name or ''

            partner_or_loc = False
            if move.type == 'out':
                if not move.sale_line_id and not move.purchase_line_id and not move.picking_id.sale_id and \
                        not move.picking_id.purchase_id:  # from scratch OUT move
                    partner_or_loc = move.location_dest_id.name
                elif move.sale_line_id:
                    if move.sale_line_id.procurement_request:  # OUT move linked to IR
                        partner_or_loc = move.sale_line_id.order_id.location_requestor_id.name
                    else:  # OUT move linked to FO
                        partner_or_loc = move.sale_line_id.order_id.partner_id.name
            elif move.type == 'in':
                if (not move.sale_line_id and not move.purchase_line_id and not move.picking_id.sale_id and
                        not move.picking_id.purchase_id) or (move.sale_line_id and move.sale_line_id.procurement_request) \
                        or (move.purchase_line_id and move.purchase_line_id.linked_sol_id
                            and move.purchase_line_id.linked_sol_id.procurement_request):  # from scratch IN move or IN move linked to IR
                    partner_or_loc = move.location_id.name
                elif move.purchase_line_id:  # IN move linked to PO
                    partner_or_loc = move.purchase_line_id.order_id.partner_id.name

            line_values = {
                'card_id': ids[0],
                'date_done': move.date,
                'doc_ref': doc_ref,
                'origin': move.picking_id and move.picking_id.origin or False,
                'partner_or_loc': partner_or_loc,
                'qty_in': in_qty,
                'qty_out': out_qty,
                'balance': initial_stock,
                'src_dest': move_location,
                'notes': move.picking_id and move.picking_id.note  or '',
            }

            line_obj.create(cr, uid, line_values, context=context)

        for inv_date in inv_line_dates:
            for new_line in inv_line_to_add[inv_date]:
                new_line['balance'] = initial_stock
                line_obj.create(cr, uid, new_line, context=context)

        for pi_counting_date in pi_counting_line_dates:
            for new_line in pi_counting_line_to_add[pi_counting_date]:
                new_line['balance'] = initial_stock
                line_obj.create(cr, uid, new_line, context=context)

        self.write(cr, uid, [ids[0]], {'real_stock': initial_stock},
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

        if isinstance(ids, int):
            ids = [ids]

        raise NotImplementedError

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Print the Excel (XML) report according to parameters
        '''
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        raise NotImplementedError

stock_card_wizard()


class stock_card_wizard_line(osv.osv_memory):
    _name = 'stock.card.wizard.line'
    _description = 'Stock card line'
    _order = 'date_done desc'  # To calculate the balance from older to newer, then display newer first

    _columns = {
        'card_id': fields.many2one('stock.card.wizard', string='Card', required=True),
        'date_done': fields.datetime(string='Date'),
        'doc_ref': fields.char(size=64, string='Doc. Ref.'),
        'origin': fields.char(size=512, string='Origin'),
        'partner_or_loc': fields.char(size=512, string='Partner/Location'),
        'qty_in': fields.float(digits=(16,2), string='Qty IN', related_uom='uom_id'),
        'qty_out': fields.float(digits=(16,2), string='Qty OUT', related_uom='uom_id'),
        'balance': fields.float(digits=(16,2), string='Balance', related_uom='uom_id'),
        'src_dest': fields.char(size=128, string='Source/Destination'),
        'partner_id': fields.many2one('res.partner', string='Source/Destination'),
        'notes': fields.text(string='Notes'),
        'uom_id': fields.related('card_id', 'uom_id', type='many2one', relation='product.uom', readonly=1, write_relate=False, string='UoM'),
    }

stock_card_wizard_line()
