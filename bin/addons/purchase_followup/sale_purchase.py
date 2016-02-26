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

from osv import osv
from osv import fields


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    
    def _shipped_rate(self, cr, uid, ids, name, arg, context=None):
        uom_obj = self.pool.get('product.uom')
        if not ids: return {}
        res = {}
        
        for order in self.browse(cr, uid, ids, context=context):
            # Direct PO is 100.00% received when a user confirm the reception at customer side
            if order.order_type == 'direct' and order.state == 'done':
                res[order.id] = 100.00
                continue
            elif order.order_type == 'direct' and order.state != 'done':
                res[order.id] = 0.00
                continue
            res[order.id] = 0.00
            amount_total = 0.00
            amount_received = 0.00
            for line in order.order_line:
                amount_total += line.product_qty*line.price_unit
                for move in line.move_ids:
                    if move.state == 'done':
                        move_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                        if move.type == 'out':
                            amount_received -= move_qty*line.price_unit
                        elif move.type == 'in':
                            amount_received += move_qty*line.price_unit
                        elif move.type == 'internal':
                            # not taken into account
                            pass
                    
            if amount_total:
                res[order.id] = (amount_received/amount_total)*100
            
        return res
    
    _columns = {
            'shipped_rate': fields.function(_shipped_rate, method=True, string='Received', type='float'),
    }

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=80):
        '''
        Search all PO by internal or customer reference
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            ids = []
            if name and len(name) > 1:
                ids.extend(self.search(cr, uid, [('partner_ref', operator, name)], context=context))
            return self.name_get(cr, uid, ids, context=context)
        elif context.get('from_followup2'):
            # receive input name as a customer name, get customer ids by operator
            # then search customer ids in PO
            ids = []
            if name and len(name) > 1:
                # search for customer
                customer_ids = self.pool.get('res.partner').search(cr, uid,
                    [('name', operator, name)], context=context)
                if customer_ids:
                    # search for m2o 'dest_partner_id' dest_customer in PO (direct PO) 
                    po1_ids = ids.extend(self.search(cr, uid,
                        [('dest_partner_id', 'in', customer_ids)],
                        context=context))
                    # search for m2m 'dest_partner_ids' dest_customer in PO (sourcing PO)
                    query = "SELECT purchase_order_id FROM res_partner_purchase_order_rel"
                    query += " WHERE partner_id in (" + ",".join(map(str, customer_ids)) + ")"
                    cr.execute(query)
                    if cr.rowcount:
                        po2_ids = cr.fetchall()
                        if po1_ids:
                            # po1_ids, po2_ids union
                            for po_id in po1_ids:
                                if po_id not in po2_ids:
                                    po2_ids.append(po_id)
                        ids = po2_ids
                    if ids:
                        domain = [
                            ('rfq_ok', '=', False),
                            ('id', 'in', ids),
                        ]
                        ids = self.search(cr, uid, domain, context=context)
            return self.name_get(cr, uid, ids, context=context)
        else:
            return super(purchase_order, self).name_search(cr, uid, name, args, operator, context, limit)

    def name_get(self, cr, uid, ids, context=None):
        '''
        If the method is called from followup wizard, set the supplier ref in brackets
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            res = []
            for r in self.browse(cr, uid, ids, context=context):
                if r.partner_ref:
                    res.append((r.id, '%s' % r.partner_ref))
                else:
                    res.append((r.id, '%s' % r.name))
            return res
        elif context.get('from_followup2'):
            res = []
            for r in self.browse(cr, uid, ids, context=context):
                name = r.name
                customer_names = []
                if r.dest_partner_id:
                    # direct customer
                    customer_names.append(r.dest_partner_id.name)
                if r.dest_partner_ids:
                    # customer from sourcing
                    for customer in r.dest_partner_ids:
                        if r.dest_partner_id and not customer.id == r.dest_partner_id.id:
                            customer_names.append(customer.name)
                        else:
                            customer_names.append(customer.name)
                if customer_names:
                    # display PO and Customers
                    name += " (%s)" % ("; ".join(customer_names),)
                res.append((r.id, name))
            return res
        else:
            return super(purchase_order, self).name_get(cr, uid, ids, context=context)
    
purchase_order()


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    def _picked_rate(self, cr, uid, ids, name, arg, context=None):
        uom_obj = self.pool.get('product.uom')
        if not ids:
            return {}
        res = {}
        
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = 0.00
            amount_total = 0.00
            amount_received = 0.00
            for line in order.order_line:
                amount_total += line.product_uom_qty*line.price_unit
                for move in line.move_ids:
                    if move.state == 'done' and move.location_dest_id.usage == 'customer':
                        move_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                        amount_received += move_qty*line.price_unit
                    
            if amount_total:
                res[order.id] = (amount_received/amount_total)*100   
        
        return res
    
    _columns = {
        'picked_rate': fields.function(_picked_rate, method=True, string='Picked', type='float'),
    }
    
sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
