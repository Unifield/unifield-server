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

from osv import osv
from osv import fields

import decimal_precision as dp


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def _get_include_transport(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns for all entries, the total cost included transport cost
        '''
        res = {}

        for order in self.browse(cr, uid, ids, context=context):
            cur_obj = self.pool.get('res.currency')
            transport_cost = order.transport_cost
            if order.transport_currency_id.id != order.pricelist_id.currency_id.id:
                transport_cost = cur_obj.compute(cr, uid, order.transport_currency_id.id,
                                                 order.pricelist_id.currency_id.id, order.transport_cost, round=True)

            total_cost = order.amount_total + transport_cost

            try:
                func_transport_cost = cur_obj.compute(cr, uid, order.pricelist_id.currency_id.id,
                                                      order.functional_currency_id.id, total_cost, round=True)
            except:
                func_transport_cost = total_cost
            res[order.id] = {'total_price_include_transport': total_cost,
                             'func_total_price_include_transport': func_transport_cost,}

        return res

    def create(self, cr, uid, vals, context=None):
        '''
        If the partner is international, set 'display_intl_transport_ok' to True
        '''
        if 'partner_id' in vals:
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context)
            if partner.zone == 'international':
                vals.update({'display_intl_transport_ok': True, 'intl_supplier_ok': True})

        if not 'transport_currency_id' in vals and 'pricelist_id' in vals:
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, vals['pricelist_id'], context=context).currency_id.id
            vals.update({'transport_currency_id': currency_id})

        return super(purchase_order, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        If the partner is international, set 'display_intl_transport_ok' to True
        '''
        if not ids:
            return True
        if 'partner_id' in vals:
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], context=context)
            if partner.zone == 'international':
                vals.update({'display_intl_transport_ok': True, 'intl_supplier_ok': True})

        if not vals.get('transport_currency_id', False):
            for po in self.browse(cr, uid, ids, context=context):
                if not po.transport_currency_id:
                    self.write(cr, uid, po.id, {'transport_currency_id': po.pricelist_id.currency_id.id}, context=context)

        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        Remove the linked documents on copy
        '''
        if default is None:
            default = {}
        default.update({'transport_order_id': False,
                        'shipment_transport_ids': []})

        return super(purchase_order, self).copy(cr, uid, ids, default, context=context)

    _columns = {
        'display_intl_transport_ok': fields.boolean(string='Displayed intl transport'),
        'intl_supplier_ok': fields.boolean(string='International Supplier'),
        'transport_cost': fields.float(string='Transport cost', digits_compute=dp.get_precision('Purchase Price')),
        'transport_currency_id': fields.many2one('res.currency', string='Currency'),
        'total_price_include_transport': fields.function(_get_include_transport, method=True, string="Total incl. transport", type='float', digits_compute=dp.get_precision('Purchase Price'), readonly=True, multi='cost'),
        'func_total_price_include_transport': fields.function(_get_include_transport, method=True, string="Functionnal total incl. transport", type='float', digits_compute=dp.get_precision('Purchase Price'), readonly=True, multi='cost'),
        'incoterm_id': fields.many2one('stock.incoterms', string='Incoterm'),
        'transport_order_id': fields.many2one('purchase.order', string='Linked Purchase Order', domain=[('categ', '!=', 'transport')]),
        'picking_transport_ids': fields.one2many('stock.picking', 'transport_order_id', string='Linked deliveries'),
        'shipment_transport_ids': fields.one2many('shipment', 'transport_order_id', string='Linked shipments'),
    }

    _defaults = {
        'display_intl_transport_ok': lambda *a: False,
        'intl_supplier_ok': lambda *a: False,
    }

    def display_transport_line(self, cr, uid, ids, context=None):
        '''
        Set the visibility of the transport line to True
        '''
        for order in self.browse(cr, uid, ids, context=context):
            if order.display_intl_transport_ok:
                self.write(cr, uid, [order.id], {'display_intl_transport_ok': False}, context=context)
            else:
                self.write(cr, uid, [order.id], {'display_intl_transport_ok': True}, context=context)

        return True

    def onchange_partner_id(self, cr, uid, ids, partner_id=False, *a, **b):
        '''
        Display or not the line of international transport costs
        '''
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, partner_id, *a, **b)
        func_currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        currency_id = False

        if not 'domain' in res:
            res.update({'domain': {}})

        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            # Update the currency of the PO
            currency_id = partner.property_product_pricelist_purchase.currency_id.id
            if partner.partner_type == 'esc' or partner.zone == 'international':
                res['value'].update({'display_intl_transport_ok': True, 'intl_supplier_ok': True, 'transport_currency_id': currency_id})
            else:
                res['value'].update({'display_intl_transport_ok': False, 'intl_supplier_ok': False, })

        else:
            res['value'].update({'display_intl_transport_ok': False, 'intl_supplier_ok': False})

        if func_currency_id and currency_id and func_currency_id != currency_id:
            res['domain'].update({'transport_currency_id': [('id', 'in', [func_currency_id, currency_id])]})
        elif (func_currency_id and not currency_id) or (func_currency_id == currency_id):
            res['domain'].update({'transport_currency_id': [('id', '=', func_currency_id)]})
        elif not func_currency_id and currency_id:
            res['domain'].update({'transport_currency_id': [('id', '=', currency_id)]})
        else:
            res['domain'].update({'transport_currency_id': [('id', 'in', [])]})

        if res.get('value', {}).get('pricelist_id') and partner_id:
            if ids:
                if isinstance(ids, int):
                    ids = [ids]

                order = self.pool.get('purchase.order').browse(cr, uid, ids[0])
                partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
                pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'purchase'), ('in_search', '=', partner.partner_type)])
                if order.pricelist_id.id not in pricelist_ids:
                    res['value'].pop('pricelist_id')
                    res.update({'warning': {'title': 'Warning',
                                            'message': 'The currency used on the order is not compatible with the new partner. Please change the currency to choose a compatible currency.'}})

        return res

    def onchange_pricelist_id(self, cr, uid, ids, partner_id, pricelist_id, transport_currency_id=False):
        '''
        Change the domain of the transport currency according to the currency and the functional currency
        '''
        res = {}

        # Set at least, the functional currency
        currency_ids = [self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id]

        # Set the currency of the pricelist of the supplier
        if partner_id and pricelist_id:
            cur_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist_id).currency_id.id
            currency_ids.append(cur_id)
            if not transport_currency_id or transport_currency_id not in currency_ids:
                res.setdefault('value', {}).update({'transport_currency_id': cur_id})

            if ids:
                order = self.browse(cr, uid, ids[0])
                if pricelist_id != order.pricelist_id.id and order.order_line:
                    res.update({'warning': {'title': 'Currency change',
                                            'message': 'You have changed the currency of the order. \
                                            Please note that all order lines in the old currency will be changed to the new currency without conversion !'}})

        res.update({'domain': {'transport_currency_id': [('id', 'in', currency_ids)]}})

        return res


purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
