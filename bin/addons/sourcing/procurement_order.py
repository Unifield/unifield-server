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
from osv.orm import browse_record
from workflow.wkf_expr import _eval_expr
from tools.translate import _

from sourcing.sale_order_line import _SELECTION_PO_CFT

from datetime import datetime
from dateutil.relativedelta import relativedelta

import netsvc


class procurement_order(osv.osv):
    """
    Procurement Orders

    Modififed workflow to take into account
    the supplier specified during sourcing step
    """
    _name = 'procurement.order'
    _inherit = 'procurement.order'

    """
    Other methods
    """
    def _check_browse_param(self, param, method):
        """
        Returns an error message if the parameter is not a
        browse_record instance

        :param param: The parameter to test
        :param method: Name of the method that call the _check_browse_param()

        :return True
        """
        if not isinstance(param, browse_record):
            raise osv.except_osv(
                _('Bad parameter'),
                _("""Exception when call the method '%s' of the object '%s' :
The parameter '%s' should be an browse_record instance !""") % (method, self._name, param)
            )

        return True

    _columns = {
        'supplier': fields.many2one('res.partner', 'Supplier'),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
        'related_sourcing_id': fields.many2one(
            'related.sourcing',
            string='Group',
        ),
        'unique_rule_type': fields.char(
            size=128,
            string='Unique Replenishment rule type',
            readonly=True,
            help="""This field is used to have only one PO by replenishment
rules if the supplier 'Order creation method' is set to 'Requirements by Order'.
""",
        ),
        'from_splitted_po_line': fields.boolean(string='From splitted PO line'),
    }

    def copy_data(self, cr, uid, copy_id, default_values=None, context=None):
        if default_values is None:
            default_values = {}

        if not default_values.get('from_splitted_po_line'):
            default_values['from_splitted_po_line'] = False

        if not default_values.get('related_sourcing_id'):
            default_values['related_sourcing_id'] = False

        return super(procurement_order, self).copy_data(cr, uid, copy_id, default_values, context=context)

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
                line.update({'origin': origin_line.order_id.name})
                if origin_line.stock_take_date:
                    line.update({'stock_take_date': origin_line.stock_take_date})
                if origin_line.original_product:
                    line.update({'original_product': origin_line.original_product.id})
                if origin_line.original_qty:
                    line.update({'original_qty': origin_line.original_qty})
                if origin_line.original_uom:
                    line.update({'original_uom': origin_line.original_uom.id})
            else:
                # Update the link to the original FO to create new line on it at PO confirmation
                procurement = kwargs['procurement']
                if procurement.origin:
                    link_so = self.pool.get('purchase.order.line').update_origin_link(cr, uid, procurement.origin, context=context)
                    if link_so.get('link_so_id'):
                        line.update({'origin': procurement.origin, 'link_so_id': link_so.get('link_so_id')})
                if procurement.unique_rule_type:
                    line.update({'stock_take_date': procurement.date_planned[0:10]})
            # UTP-934: If the procurement is a rfq, the price unit must be taken from this rfq, and not from the pricelist or standard price
            procurement = kwargs['procurement']
            if procurement.po_cft in ('cft', 'rfq') and procurement.price_unit:
                line.update({'price_unit': procurement.price_unit})

            if procurement and procurement.tender_line_id:
                if procurement.tender_line_id.comment:
                    line['comment'] = procurement.tender_line_id.comment

        if not line.get('price_unit', False):
            cur_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            if 'pricelist' in kwargs:
                if 'procurement' in kwargs and 'partner_id' in context:
                    procurement = kwargs['procurement']
                    pricelist = kwargs['pricelist']
                    st_price = self.pool.get('product.pricelist').price_get(
                        cr,
                        uid,
                        [pricelist.id],
                        procurement.product_id.id,
                        procurement.product_qty,
                        context['partner_id'],
                        {'uom': line.get('product_uom', procurement.product_id.uom_id.id)}
                    )[pricelist.id]
                st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, kwargs['pricelist'].currency_id.id, st_price, round=False, context=context)
            if not st_price:
                product = self.pool.get('product.product').browse(cr, uid, line['product_id'])
                st_price = product.standard_price
                if 'pricelist' in kwargs:
                    st_price = self.pool.get('res.currency').compute(
                        cr,
                        uid,
                        cur_id,
                        kwargs['pricelist'].currency_id.id,
                        st_price,
                        round=False,
                        context=context,
                    )
                elif 'partner_id' in context:
                    partner = self.pool.get('res.partner').browse(cr, uid, context['partner_id'], context=context)
                    st_price = self.pool.get('res.currency').compute(
                        cr,
                        uid,
                        cur_id,
                        partner.property_product_pricelist_purchase.currency_id.id,
                        st_price,
                        round=False,
                        context=context,
                    )
                if origin_line:
                    st_price = self.pool.get('product.uom')._compute_price(
                        cr,
                        uid,
                        product.uom_id.id,
                        st_price or product.standard_price,
                        to_uom_id=origin_line.product_uom.id,
                    )
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
                           ('delivery_requested_date', '=', values.get('delivery_requested_date')),
                           ('stock_take_date', '=', values.get('stock_take_date'))]

        if procurement.po_cft == 'dpo':
            purchase_domain.append(('order_type', '=', 'direct'))
        else:
            purchase_domain.append(('order_type', '!=', 'direct'))

        if procurement.related_sourcing_id:
            purchase_domain.append(('related_sourcing_id', '=', procurement.related_sourcing_id.id))
            values['related_sourcing_id'] = procurement.related_sourcing_id.id
        else:
            purchase_domain.append(('related_sourcing_id', '=', False))
            values['related_sourcing_id'] = False

        if procurement.tender_line_id and procurement.tender_line_id.purchase_order_line_id:
            purchase_domain.append(('pricelist_id', '=', procurement.tender_line_id.purchase_order_line_id.order_id.pricelist_id.id))
        elif procurement.rfq_id:
            purchase_domain.append(('pricelist_id', '=', procurement.rfq_id.pricelist_id.id))

        line = None
        order_customer_id = None
        sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if sale_line_ids:
            line = self.pool.get('sale.order.line').browse(cr, uid, sale_line_ids[0], context=context)
            order_customer_id = line.order_partner_id.id
            if line.product_id.type in ('service', 'service_recep') and not line.order_id.procurement_request:
                if ('order_type', '!=', 'direct') in purchase_domain:
                    purchase_domain.remove(('order_type', '!=', 'direct'))
                purchase_domain.append(('order_type', '=', 'direct'))
            elif procurement.po_cft != 'dpo' and line.order_id.order_type not in ('loan', 'donation_st', 'donation_exp'):
                purchase_domain.append(('order_type', 'in', ['regular', 'purchase_list']))

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
            if line and line.order_id:
                purchase_domain.append(('unique_fo_id', '=', line.order_id.id))
                values['unique_fo_id'] = line.order_id.id
            elif procurement.unique_rule_type:
                purchase_domain.append(('unique_rule_type', '=', procurement.unique_rule_type))
                values['unique_rule_type'] = procurement.unique_rule_type

        if procurement.unique_rule_type:
            values['po_from_rr'] = True
            values['stock_take_date'] = values['date_planned'][0:10]

        # Category requirements => Search a PO with the same category than the IR/FO category
        if partner.po_by_project in ('category_project', 'category'):
            if line:
                purchase_domain.append(('categ', '=', line.order_id.categ))

        # if we are updating the sale order from the corresponding on order purchase order
        # the purchase order to merge the new line to is locked and provided in the procurement
        if procurement.so_back_update_dest_po_id_procurement_order:
            purchase_ids = [procurement.so_back_update_dest_po_id_procurement_order.id]
        elif procurement.from_splitted_po_line and procurement.purchase_id:
            purchase_ids = [procurement.purchase_id.id]
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
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(
                    cr, uid, sol.analytic_distribution_id.id, context=context)
                values['order_line'][0][2].update({'analytic_distribution_id': new_analytic_distribution_id})
            elif sol.order_id.analytic_distribution_id:
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(
                    cr, uid, sol.order_id.analytic_distribution_id.id, context=context)
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
            if order_customer_id:
                write_values['dest_partner_ids'] = [(4, order_customer_id)]

            self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], write_values, context=dict(context, import_in_progress=True))

            po_values = {}
            if categ and po.categ != categ:
                po_values.update({'categ': 'other'})

            if location_id:
                po_values.update({'location_id': location_id, 'cross_docking_ok': False})

            if values.get('cross_docking_ok') == True:
                po_values['cross_docking_ok'] = values.get('cross_docking_ok')

            if po_values:
                self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], po_values, context=dict(context, import_in_progress=True))
            pol_id = self.pool.get('purchase.order.line').create(cr, uid, line_values, context=context)

            if line:
                self.infolog(cr, uid, "The FO/IR line id:%s (line number: %s) has been sourced on order to the PO line id:%s (line number: %s) of the PO id:%s (%s)" % (
                    line.id, line.line_number,
                    pol_id, self.pool.get('purchase.order.line').read(cr, uid, pol_id, ['line_number'], context=context)['line_number'],
                    purchase_ids[0], self.pool.get('purchase.order').read(cr, uid, purchase_ids[0], ['name'], context=context)['name'],
                ))

            return purchase_ids[0]
        else:
            if procurement.po_cft == 'dpo' or procurement.product_id.type in ('service', 'service_recep'):
                sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
                if sol_ids:
                    sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
                    if not sol.order_id.procurement_request:
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
            if order_customer_id:
                values['dest_partner_ids'] = [(4, order_customer_id)]
            purchase_id = super(procurement_order, self).create_po_hook(cr, uid, ids, context=context, *args, **kwargs)

            if line:
                self.infolog(cr, uid, "The FO/IR line id:%s (line number: %s) has been sourced on order to the PO id:%s (%s)" % (
                    line.id, line.line_number,
                    purchase_id, self.pool.get('purchase.order').read(cr, uid, purchase_id, ['name'], context=context)['name'],
                ))

            return purchase_id

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override for workflow modification
        '''
        if not ids:
            return True
        return super(procurement_order, self).write(cr, uid, ids, vals, context)

    def get_delay_qty(self, product, partner):
        '''
        find corresponding values for seller_qty and seller_delay from product supplierinfo or default values
        '''
        """
        Find corresponding values from seller_qty and seller_delay
        from product supplierinfo or default values

        :param product: A browse_record of product.product
        :param partner: A browse_record of res.partner

        :return A dictionnary with the seller_qty and the seller_delay
        :rtype dict
        """
        self._check_browse_param(product, 'get_delay_qty')
        self._check_browse_param(partner, 'get_delay_qty')

        result = {
            'seller_qty': 1,
            'seller_delay':-1,
        }

        for suppinfo in product.seller_ids:
            if suppinfo.name.id == partner.id:
                result.update({
                    'seller_qty': suppinfo.qty,
                    'seller_delay': int(suppinfo.delay),
                })
                break

        # if not, default delay from supplier (partner.default_delay)
        if result['seller_delay'] < 0:
            result['seller_delay'] = partner.default_delay

        return result

    def _get_info_from_tender_line(self, sale_order_line, procurement):
        """
        Search for info about the product of the procurement in the corresponding tender.

        :param sale_order_line: A browse_record of the sale.order.line sourced by
                                 the procurement order.
        :param procurement: A browse_record of the procurement.order to treat

        :return A dictionary with values of the tender lines or an empty dictionary
                 if no corresponding tender lines found.
        :rtype dict
        """
        self._check_browse_param(sale_order_line, '_get_info_from_tender_line')
        self._check_browse_param(procurement, '_get_info_from_tender_line')

        result = {}

        for tender_line in sale_order_line.tender_line_ids:
            # if a tender rfq has been selected for this sale order line
            if tender_line.purchase_order_line_id:
                result.update({
                    'partner': tender_line.supplier_id,
                    'price_unit': tender_line.price_unit,
                })

                delay_info = self.get_delay_qty(procurement.product_id, tender_line.supplier_id)
                result.update(delay_info)
                break

        return result

    def _get_partner(self, cr, uid, procurement, context=None):
        """
        Return information about the partner choosen to source this procurement.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param procurement: A browse_record of a procurement.order
        :param context: Context of the call

        :return A dictionnary with these information:
            * partner: A browse_record of the res.partner choosen
            * seller_qty: The quantity of this partner
            * seller_delay: The delay of this partner
            * price_unit: The unit price (if any) given by this partner
        :rtype dict
        """
        result = {}

        # this is kept here and not moved in the tender_flow module
        # because we have no control on the order of inherited function call (do we?)
        # and if we have tender and supplier defined and supplier code is ran after
        # tender one, the supplier will be use while tender has priority
        if procurement.is_tender:
            # tender line -> search for info about this product in the corresponding tender
            # if nothing found, we keep default values from super
            for sol in procurement.sale_order_line_ids:
                tl_infos = self._get_info_from_tender_line(sol, procurement)
                if tl_infos:
                    result['unit_price'] = 0.00
                    result.update(tl_infos)
                    break
        elif procurement.supplier:
            # not tender, we might have a selected supplier from sourcing tool
            # if not, we keep default values from super
            result.update({
                'partner': procurement.supplier,
                'unit_price': 0.00,
            })
            # get corresponding delay and qty
            delay_info = self.get_delay_qty(procurement.product_id, procurement.supplier)
            result.update(delay_info)

        if not result:
            result.update({
                'partner': procurement.product_id.seller_id,  # Taken Main Supplier of Product of Procurement
                'seller_qty': procurement.product_id.seller_qty,
                'seller_delay': int(procurement.product_id.seller_delay),
                'unit_price': 0.00,
            })

        return result

    # @@@override procurement>procurement_order>test_cancel()
    def test_cancel(self, cr, uid, ids):
        """ Tests whether state of move is cancelled or not.
        @return: True or False
        """
        cancel = self.search(cr, uid, [
            ('id', 'in', ids),
            ('move_id', '!=', False),
            ('move_id.state', '=', 'cancel'),
        ], count=True)

        return cancel and True or False
    # @@@END override

    # @@@override procurement->procurement_order->check_buy()
    def check_buy(self, cr, uid, ids):
        """ Checks product type.
        @return: True or Product Id.
        """
        # Objects
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')

        if isinstance(ids, (int, long)):
            ids = [ids]

        company_id = user_obj.browse(cr, uid, uid).company_id.partner_id.id

        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.product_tmpl_id.supply_method <> 'buy':
                return False

            if procurement.purchase_id:
                return True

            if procurement.supplier:
                partner = procurement.supplier
            elif procurement.product_id.seller_id:
                partner = procurement.product_id.seller_id
            else:
                cr.execute(
                    """update procurement_order set message=%s where id=%s""",
                    (_('No default supplier defined for this product'), procurement.id),
                )
                return False

            if partner.id == company_id:
                cr.execute(
                    """UPDATE procurement_order SET message=%s WHERE id = %s""",
                    (_('Impossible to make a Purchase Order to your own company !'), procurement.id),
                )
                return False

            address_id = partner_obj.address_get(cr, uid, [partner.id], ['delivery'])['delivery']
            if not address_id:
                cr.execute(
                    """update procurement_order set message=%s where id=%s""",
                    (_('No address defined for the supplier'), procurement.id),
                )
                return False

        return True
    # @@@END override

    # @@@override purchase>procurement_order>make_po()
    def make_po(self, cr, uid, ids, context=None):
        """
        Make purchase order from procurement

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of procurement orders to source
        :param context: Context of the call

        :return New created Purchase Orders procurement wise
        """
        # Objects
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        uom_obj = self.pool.get('product.uom')
        pricelist_obj = self.pool.get('product.pricelist')
        prod_obj = self.pool.get('product.product')
        acc_pos_obj = self.pool.get('account.fiscal.position')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        company = user_obj.browse(cr, uid, uid, context=context).company_id

        for procurement in self.browse(cr, uid, ids, context=context):
            res_id = procurement.move_id.id

            p_infos = self._get_partner(cr, uid, procurement, context=context)

            partner = p_infos['partner']
            address_id = partner_obj.address_get(cr, uid, [partner.id], ['delivery'])['delivery']
            pricelist_id = partner.property_product_pricelist_purchase

            uom_id = procurement.product_id.uom_po_id.id

            qty = uom_obj._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if p_infos['seller_qty']:
                qty = max(qty, p_infos['seller_qty'])

            price = pricelist_obj.price_get(cr, uid, [pricelist_id.id], procurement.product_id.id, qty, partner.id, {'uom': uom_id})[pricelist_id.id]
            if p_infos['unit_price']:
                price = p_infos['unit_price']

            newdate = datetime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S')
            newdate = (newdate - relativedelta(days=int(company.po_lead))) - relativedelta(days=int(p_infos['seller_delay']))

            # Passing partner_id to context for purchase order line integrity of Line name
            context.update({'lang': partner.lang, 'partner_id': partner.id})

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
                'stock_take_date': procurement.sale_id.stock_take_date,
            }

            # line values modification from hook
            line = self.po_line_values_hook(cr, uid, ids, context=context, line=line, procurement=procurement, pricelist=pricelist_id)

            taxes_ids = procurement.product_id.product_tmpl_id.supplier_taxes_id
            taxes = acc_pos_obj.map_tax(cr, uid, partner.property_account_position, taxes_ids)
            line.update({
                'taxes_id': [(6, 0, taxes)]
            })
            values = {
                'origin': procurement.origin,
                'partner_id': partner.id,
                'partner_address_id': address_id,
                'location_id': procurement.location_id.id,
                'pricelist_id': pricelist_id.id,
                'order_line': [(0, 0, line)],
                'company_id': procurement.company_id.id,
                'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                'stock_take_date': procurement.sale_id.stock_take_date,
            }
            # values modification from hook
            values = self.po_values_hook(cr, uid, ids, context=context, values=values, procurement=procurement, line=line,)
            # purchase creation from hook
            purchase_id = self.create_po_hook(cr, uid, ids, context=context, values=values, procurement=procurement)
            res[procurement.id] = purchase_id
            self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': purchase_id})
        return res
    # @@@END override

    def _do_create_proc_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        Puth the unique rule type on the procurement order
        """
        res = super(procurement_order, self)._do_create_proc_hook(cr, uid, ids, context=context, *args, **kwargs)

        if res is None:
            res = {}

        res['unique_rule_type'] = 'stock.warehouse.orderpoint'

        return res
    def set_manually_done(self, cr, uid, ids, all_doc=False, context=None):
        """
        Detach the workflow of the procurement.order object and set state
        to done.
        """
        wf_service = netsvc.LocalService("workflow")

        if isinstance(ids, (int, long)):
            ids = [ids]

        for proc_id in ids:
            wf_service.trg_delete(uid, 'procurement.order', proc_id, cr)
            # Search the method called when the workflow enter in the last activity
            wkf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement', 'act_done')[1]
            activity = self.pool.get('workflow.activity').browse(cr, uid, wkf_id, context=context)
            _eval_expr(cr, [uid, 'procurement.order', proc_id], False, activity.action)

        return True

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
