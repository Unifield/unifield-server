# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import osv, fields


class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'purchase_id': fields.many2one('purchase.order', 'Purchase Order'),
    }

    def action_po_assign(self, cr, uid, ids, context=None):
        """ This is action which call from workflow to assign purchase order to procurements
        @return: True
        """
        res = self.make_po(cr, uid, ids, context=context)
        res = res.values()
        return len(res) and res[0] or 0 #TO CHECK: why workflow is generated error if return not integer value

    def get_partner_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return a dictionary with partner, seller_qty and seller_delay
        '''
        result = {}

        procurement = kwargs['procurement']
        partner = procurement.product_id.seller_id # Taken Main Supplier of Product of Procurement.
        seller_qty = procurement.product_id.seller_qty
        seller_delay = int(procurement.product_id.seller_delay)

        result.update(partner=partner,
                      seller_qty=seller_qty,
                      seller_delay=seller_delay)

        return result

    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order

        - allow to modify the data for purchase order line creation
        '''
        line = kwargs['line']
        return line

    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order

        - allow to modify the data for purchase order creation
        '''
        values = kwargs['values']
        return values

    def create_po_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        creation of purchase order
        return the id of newly created po
        '''
        po_obj = self.pool.get('purchase.order')
        values = kwargs['values']
        purchase_id = po_obj.create(cr, uid, values, context=context)
        return purchase_id

    def make_po(self, cr, uid, ids, context=None):
        """ Make purchase order from procurement
        @return: New created Purchase Orders procurement wise
        """
        res = {}
        if context is None:
            context = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        partner_obj = self.pool.get('res.partner')
        uom_obj = self.pool.get('product.uom')
        pricelist_obj = self.pool.get('product.pricelist')
        prod_obj = self.pool.get('product.product')
        acc_pos_obj = self.pool.get('account.fiscal.position')
        for procurement in self.browse(cr, uid, ids, context=context):
            res_id = procurement.move_id.id

            # partner, seller_qty and seller_delay are computed with hook
            hook = self.get_partner_hook(cr, uid, ids, context=context, procurement=procurement)
            partner = hook['partner']
            seller_qty = hook['seller_qty']
            seller_delay = hook['seller_delay']
            partner_id = partner.id
            address_id = partner_obj.address_get(cr, uid, [partner_id], ['delivery'])['delivery']
            pricelist_id = partner.property_product_pricelist_purchase

            uom_id = procurement.product_id.uom_po_id.id

            qty = uom_obj._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if seller_qty:
                qty = max(qty,seller_qty)

            price = pricelist_obj.price_get(cr, uid, [pricelist_id.id], procurement.product_id.id, qty, partner_id, {'uom': uom_id})[pricelist_id.id]
            if hook.get('price_unit', False):
                price = hook.get('price_unit', False)            

            newdate = datetime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S')
            newdate = (newdate - relativedelta(days=int(company.po_lead))) - relativedelta(days=int(seller_delay))

            #Passing partner_id to context for purchase order line integrity of Line name
            context.update({'lang': partner.lang, 'partner_id': partner_id})

            product = prod_obj.browse(cr, uid, procurement.product_id.id, context=context)

            line = {
                'name': product.partner_ref,
                'product_qty': qty,
                'product_id': procurement.product_id.id,
                'product_uom': uom_id,
                'price_unit': price,
                'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                'move_dest_id': res_id,
                'notes': product.description_purchase,
            }

            # line values modification from hook
            line = self.po_line_values_hook(cr, uid, ids, context=context, line=line, procurement=procurement, pricelist=pricelist_id)

            taxes_ids = procurement.product_id.product_tmpl_id.supplier_taxes_id
            taxes = acc_pos_obj.map_tax(cr, uid, partner.property_account_position, taxes_ids)
            line.update({
                'taxes_id': [(6,0,taxes)]
            })
            values = {
                'origin': procurement.origin,
                'partner_id': partner_id,
                'partner_address_id': address_id,
                'location_id': procurement.location_id.id,
                'pricelist_id': pricelist_id.id,
                'order_line': [(0,0,line)],
                'company_id': procurement.company_id.id,
                'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
            }
            # values modification from hook
            values = self.po_values_hook(cr, uid, ids, context=context, values=values, procurement=procurement, line=line,)
            # purchase creation from hook
            purchase_id = self.create_po_hook(cr, uid, ids, context=context, values=values, procurement=procurement)
            res[procurement.id] = purchase_id
            self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': purchase_id})
        return res

procurement_order()


