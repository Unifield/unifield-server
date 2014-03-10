# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

from sourcing.sale_order_line import _SELECTION_PO_CFT


class procurement_order(osv.osv):
    """
    Procurement Orders

    Modififed workflow to take into account
    the supplier specified during sourcing step
    """
    _name = 'procurement.order'
    _inherit = 'procurement.order'

    _columns = {
        'supplier': fields.many2one('res.partner', 'Supplier'),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
    }

    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order

        - allow to modify the data for purchase order line creation
        '''
        if not context:
            context = {}
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        origin_line = False
        if 'procurement' in kwargs:
            order_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', kwargs['procurement'].id)])
            if order_line_ids:
                origin_line = self.pool.get('sale.order.line').browse(cr, uid, order_line_ids[0])
                line.update({'origin': origin_line.order_id.name, 'product_uom': origin_line.product_uom.id, 'product_qty': origin_line.product_uom_qty})
            else:
                # Update the link to the original FO to create new line on it at PO confirmation
                procurement = kwargs['procurement']
                if procurement.origin:
                    link_so = self.pool.get('purchase.order.line').update_origin_link(cr, uid, procurement.origin, context=context)
                    if link_so.get('link_so_id'):
                        line.update({'origin': procurement.origin, 'link_so_id': link_so.get('link_so_id')})

            # UTP-934: If the procurement is a rfq, the price unit must be taken from this rfq, and not from the pricelist or standard price
            procurement = kwargs['procurement']
            if procurement.po_cft in ('cft', 'rfq') and procurement.price_unit:
                line.update({'price_unit': procurement.price_unit})

        if line.get('price_unit', False) == False:
            cur_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            if 'pricelist' in kwargs:
                if 'procurement' in kwargs and 'partner_id' in context:
                    procurement = kwargs['procurement']
                    pricelist = kwargs['pricelist']
                    st_price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist.id], procurement.product_id.id, procurement.product_qty, context['partner_id'], {'uom': line.get('product_uom', procurement.product_id.uom_id.id)})[pricelist.id]
                st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, kwargs['pricelist'].currency_id.id, st_price, round=False, context=context)
            if not st_price:
                product = self.pool.get('product.product').browse(cr, uid, line['product_id'])
                st_price = product.standard_price
                if 'pricelist' in kwargs:
                    st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, kwargs['pricelist'].currency_id.id, st_price, round=False, context=context)
                elif 'partner_id' in context:
                    partner = self.pool.get('res.partner').browse(cr, uid, context['partner_id'], context=context)
                    st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, partner.property_product_pricelist_purchase.currency_id.id, st_price, round=False, context=context)
                if origin_line:
                    st_price = self.pool.get('product.uom')._compute_price(cr, uid, product.uom_id.id, st_price or product.standard_price, to_uom_id=origin_line.product_uom.id)
            line.update({'price_unit': st_price})

        return line

    def action_check_finished(self, cr, uid, ids):
        res = super(procurement_order, self).action_check_finished(cr, uid, ids)

        # If the procurement has been generated from an internal request, close the order
        for order in self.browse(cr, uid, ids):
            line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', order.id)])
            for line in self.pool.get('sale.order.line').browse(cr, uid, line_ids):
                if line.order_id.procurement_request and line.order_id.location_requestor_id.usage != 'customer':
                    return True

        return res

    def create_po_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        if a purchase order for the same supplier and the same requested date,
        don't create a new one
        '''
        po_obj = self.pool.get('purchase.order')
        procurement = kwargs['procurement']
        values = kwargs['values']
        priority_sorted = {'emergency': 1, 'priority': 2, 'normal': 3}
        # Make the line as price changed manually to do not raise an error on purchase order line creation
#        if 'order_line' in values and len(values['order_line']) > 0 and len(values['order_line'][0]) > 2 and 'price_unit' in values['order_line'][0][2]:
#            values['order_line'][0][2].update({'change_price_manually': True})

        partner = self.pool.get('res.partner').browse(cr, uid, values['partner_id'], context=context)

        purchase_domain = [('partner_id', '=', partner.id),
                           ('state', '=', 'draft'),
                           ('rfq_ok', '=', False),
                           ('delivery_requested_date', '=', values.get('delivery_requested_date'))]

        if procurement.po_cft == 'dpo':
            purchase_domain.append(('order_type', '=', 'direct'))
        else:
            purchase_domain.append(('order_type', '!=', 'direct'))

        line = None
        sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if sale_line_ids:
            line = self.pool.get('sale.order.line').browse(cr, uid, sale_line_ids[0], context=context)

        if partner.po_by_project in ('project', 'category_project') or (procurement.po_cft == 'dpo' and partner.po_by_project == 'all'):
            if line:
                if line.procurement_request:
                    customer_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
                else:
                    customer_id = line.order_id.partner_id.id
                values.update({'customer_id': customer_id})
                purchase_domain.append(('customer_id', '=', customer_id))

        # Isolated requirements => One PO for one IR/FO
        if partner.po_by_project == 'isolated':
            purchase_domain.append(('origin', '=', procurement.origin))

        # Category requirements => Search a PO with the same category than the IR/FO category
        if partner.po_by_project in ('category_project', 'category'):
            if line:
                purchase_domain.append(('categ', '=', line.order_id.categ))

        # if we are updating the sale order from the corresponding on order purchase order
        # the purchase order to merge the new line to is locked and provided in the procurement
        if procurement.so_back_update_dest_po_id_procurement_order:
            purchase_ids = [procurement.so_back_update_dest_po_id_procurement_order.id]
        else:
            # search for purchase order according to defined domain
            purchase_ids = po_obj.search(cr, uid, purchase_domain, context=context)

        # Set the origin of the line with the origin of the Procurement order
        if procurement.origin:
            values['order_line'][0][2].update({'origin': procurement.origin})

        if procurement.tender_id:
            if values.get('origin'):
                values['origin'] = '%s; %s' % (values['origin'], procurement.tender_id.name)
            else:
                values['origin'] = procurement.tender_id.name

        if procurement.rfq_id:
            if values.get('origin'):
                values['origin'] = '%s; %s' % (values['origin'], procurement.rfq_id.name)
            else:
                values['origin'] = procurement.rfq_id.name

        # Set the analytic distribution on PO line if an analytic distribution is on SO line or SO
        sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        location_id = False
        categ = False
        if sol_ids:
            sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
            if sol.order_id:
                categ = sol.order_id.categ

            if sol.analytic_distribution_id:
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(cr, uid,
                                                    sol.analytic_distribution_id.id, context=context)
                values['order_line'][0][2].update({'analytic_distribution_id': new_analytic_distribution_id})
            elif sol.order_id.analytic_distribution_id:
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(cr,
                                                    uid, sol.order_id.analytic_distribution_id.id, context=context)
                values['order_line'][0][2].update({'analytic_distribution_id': new_analytic_distribution_id})
        elif procurement.product_id:
            if procurement.product_id.type == 'consu':
                location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
            elif procurement.product_id.type == 'service_recep':
                location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]
            else:
                wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
                if wh_ids:
                    location_id = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_input_id.id
                else:
                    location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]

        if purchase_ids:
            line_values = values['order_line'][0][2]
            line_values.update({'order_id': purchase_ids[0], 'origin': procurement.origin})
            po = self.pool.get('purchase.order').browse(cr, uid, purchase_ids[0], context=context)
            # Update the origin of the PO with the origin of the procurement
            # and tender name if exist
            origins = set([po.origin, procurement.origin, procurement.tender_id and procurement.tender_id.name, procurement.rfq_id and procurement.rfq_id.name])
            # Add different origin on 'Source document' field if the origin is nat already listed
            origin = ';'.join(o for o in list(origins) if o and (not po.origin or o == po.origin or o not in po.origin))
            write_values = {'origin': origin}

            # update categ and prio if they are different from the existing po one's.
            if values.get('categ') and values['categ'] != po.categ:
                write_values['categ'] = 'other'
            if values.get('priority') and values['priority'] in priority_sorted.keys() and values['priority'] != po.priority:
                if priority_sorted[values['priority']] < priority_sorted[po.priority]:
                    write_values['priority'] = values['priority']

            self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], write_values, context=dict(context, import_in_progress=True))

            po_values = {}
            if categ and po.categ != categ:
                po_values.update({'categ': 'other'})

            if location_id:
                po_values.update({'location_id': location_id, 'cross_docking_ok': False})

            if po_values:
                self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], po_values, context=dict(context, import_in_progress=True))
            self.pool.get('purchase.order.line').create(cr, uid, line_values, context=context)
            return purchase_ids[0]
        else:
            if procurement.po_cft == 'dpo':
                sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
                if sol_ids:
                    sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
                    if not sol.procurement_request:
                        values.update({'order_type': 'direct',
                                       'dest_partner_id': sol.order_id.partner_id.id,
                                       'dest_address_id': sol.order_id.partner_shipping_id.id})

                #  Force the destination location of the Po to Input location
                company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
                warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)
                if warehouse_id:
                    input_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id[0], context=context).lot_input_id.id
                    values.update({'location_id': input_id, })
            if categ:
                values.update({'categ': categ})
            purchase_id = super(procurement_order, self).create_po_hook(cr, uid, ids, context=context, *args, **kwargs)
            return purchase_id

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override for workflow modification
        '''
        return super(procurement_order, self).write(cr, uid, ids, vals, context)

    def _partner_check_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        check the if supplier is available or not

        the new selection field does not exist when the procurement has been produced by
        an order_point (minimum stock rules). in this case we take the default supplier from product

        same cas if no supplier were selected in the sourcing tool

        return True if a supplier is available
        '''
        procurement = kwargs['procurement']
        # add supplier check in procurement object from sourcing tool
        result = procurement.supplier or super(procurement_order, self)._partner_check_hook(cr, uid, ids, context=context, *args, **kwargs)
        return result

    def _partner_get_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        returns the partner from procurement or suppinfo

        the new selection field does not exist when the procurement has been produced by
        an order_point (minimum stock rules). in this case we take the default supplier from product

        same cas if no supplier were selected in the sourcing tool
        '''
        procurement = kwargs['procurement']
        # the specified supplier in sourcing tool has priority over suppinfo
        partner = procurement.supplier or super(procurement_order, self)._partner_get_hook(cr, uid, ids, context=context, *args, **kwargs)
        if partner.id == self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id:
            cr.execute('update procurement_order set message=%s where id=%s',
                           (_('Impossible to make a Purchase Order to your own company !'), procurement.id))
        return partner

    def get_delay_qty(self, cr, uid, ids, partner, product, context=None):
        '''
        find corresponding values for seller_qty and seller_delay from product supplierinfo or default values
        '''
        result = {}
        # if the supplier is present in product seller_ids, we take that quantity from supplierinfo
        # otherwise 1
        # seller_qty default value
        seller_qty = 1
        seller_delay = -1
        for suppinfo in product.seller_ids:
            if suppinfo.name.id == partner.id:
                seller_qty = suppinfo.qty
                seller_delay = int(suppinfo.delay)

        # if not, default delay from supplier (partner.default_delay)
        if seller_delay < 0:
            seller_delay = partner.default_delay

        result.update(seller_qty=seller_qty,
                      seller_delay=seller_delay,)

        return result

    def get_partner_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        get data from supplier

        return also the price_unit
        '''
        # get default values
        result = super(procurement_order, self).get_partner_hook(cr, uid, ids, context=context, *args, **kwargs)
        procurement = kwargs['procurement']

        # this is kept here and not moved in the tender_flow module
        # because we have no control on the order of inherited function call (do we?)
        # and if we have tender and supplier defined and supplier code is ran after
        # tender one, the supplier will be use while tender has priority
        if procurement.is_tender:
            # tender line -> search for info about this product in the corresponding tender
            # if nothing found, we keep default values from super
            for sol in procurement.sale_order_line_ids:
                for tender_line in sol.tender_line_ids:
                    # if a tender rfq has been selected for this sale order line
                    if tender_line.purchase_order_line_id:
                        partner = tender_line.supplier_id
                        price_unit = tender_line.price_unit
                        # get corresponding delay and qty
                        delay_qty = self.get_delay_qty(cr, uid, ids, partner, procurement.product_id, context=None)
                        seller_delay = delay_qty['seller_delay']
                        seller_qty = delay_qty['seller_qty']
                        result.update(partner=partner,
                                      seller_qty=seller_qty,
                                      seller_delay=seller_delay,
                                      price_unit=price_unit)
        elif procurement.supplier:
            # not tender, we might have a selected supplier from sourcing tool
            # if not, we keep default values from super
            partner = procurement.supplier
            # get corresponding delay and qty
            delay_qty = self.get_delay_qty(cr, uid, ids, partner, procurement.product_id, context=None)
            seller_delay = delay_qty['seller_delay']
            seller_qty = delay_qty['seller_qty']
            result.update(partner=partner,
                          seller_qty=seller_qty,
                          seller_delay=seller_delay)

        return result

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
