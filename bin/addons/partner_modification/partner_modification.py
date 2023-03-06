# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from datetime import datetime
from dateutil.relativedelta import relativedelta
from osv import osv, fields


from msf_order_date import TRANSPORT_TYPE
from msf_order_date import ZONE_SELECTION

NUMBER_OF_CHOICE = 3

class product_template(osv.osv):
    _inherit = 'product.template'

    def _get_delay_for_supplier(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        ret = {}
        if 'delay_supplier_id' not in context:
            for id in ids:
                ret[id] = False
            return ret

        partner_obj = self.pool.get('res.partner')
        for prod in self.browse(cr, uid, ids, fields_to_fetch=['seller_ids']):
            ret[prod.id] = False
            for seller in prod.seller_ids:
                if context['delay_supplier_id'] == seller.name.id:
                    ret[prod.id] = seller.delay
                    break
            if not ret[prod.id]:
                ret[prod.id] = int(partner_obj.read(cr, uid, context['delay_supplier_id'], ['default_delay'])['default_delay'])
        return ret


    _columns = {
        'delay_for_supplier': fields.function(_get_delay_for_supplier, type='integer', string='Default delay for a supplier', method=True)
    }

product_template()


class res_partner(osv.osv):
    _description='Partner'
    _inherit = "res.partner"

    def _calc_dellay(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        for partner in self.browse(cr, uid, ids, context=context):
            result[partner.id] = {}
            for field in fields:
                result[partner.id].update({field:0})

            # get the default transport, the smallest sequence
            value_list = self.read(cr, uid, [partner.id], ['transport_0', 'transport_0_lt',], context=context)
            if not value_list:
                continue

            # it's a list, get the first element
            value = value_list[0]
            # preferred transport values
            transport_0 = value['transport_0']
            transport_0_lt = value['transport_0_lt']
            # no favorite transport selected, return 0
            if transport_0 == '':
                continue
            # the default transport lead time
            result[partner.id]['default_delay'] = transport_0_lt + partner.procurement_lt

        return result

    def get_transport_lead_time(self, cr, uid, ids, transport_name, context=None):
        '''
        for a given transport name (road, air, sea), 
        '''
        if not ids:
            return 0.0
        if ids and isinstance(ids, int):
            ids = [ids]
        # result values
        result = {}
        # get corresponding lt
        for partner in self.browse(cr, uid, ids, context=context):
            result[partner.id] = 0
            if transport_name:
                for i in range(NUMBER_OF_CHOICE):
                    if getattr(partner, 'transport_%s'%i) == transport_name:
                        val = getattr(partner, 'transport_%s_lt'%i)
                        result[partner.id] = val

        return result

    def on_change_lead_time(self, cr, uid, ids, transport_0_lt, procurement_lt, context=None):
        '''
        change supplier_lt and customer_lt according to preferred lead time and internal lead time
        '''
        return {'value': {'supplier_lt': transport_0_lt + procurement_lt,
                          'customer_lt': transport_0_lt + procurement_lt}}

    _columns = {'zone': fields.selection(selection=ZONE_SELECTION, string='Zone', required=True),
                'customer_lt': fields.integer('Customer Lead Time'),
                'supplier_lt': fields.integer('Supplier Lead Time'),
                'procurement_lt': fields.integer('Internal Lead Time'),
                'transport_0_lt': fields.integer('1st Transport Lead Time'),
                'transport_0': fields.selection(selection=TRANSPORT_TYPE, string='1st (favorite) Mode of Transport',),
                'transport_1_lt': fields.integer('2nd Transport Lead Time'),
                'transport_1': fields.selection(selection=TRANSPORT_TYPE, string='2nd Mode of Transport'),
                'transport_2_lt': fields.integer('3rd Transport Lead Time'),
                'transport_2': fields.selection(selection=TRANSPORT_TYPE, string='3nd Mode of Transport'),
                'default_delay': fields.function(_calc_dellay, method=True, type='integer', string='Supplier Lead Time (computed)', multi="seller_delay"),
                'po_by_project': fields.selection([
                    ('all', 'All requirements'),
                    ('project', 'Requirements by Project'),
                    ('category', 'Requirements by Category'),
                    ('category_project', 'Requirements by Category and Project'),
                    ('isolated', 'Requirements by Order')],
        string='Order creation mode',
        help='''When option “All requirements” is set for 
                                            a given supplier, the system will create a PO that merge all requirements
                                            for this supplier. 
                                            If option “Requirements by Project” is set, the POs will
                                            be created by original requestor (customer of the SO origin), meaning
                                            system creates one PO by project for this supplier.
                                            If option "Requirements by Category" is set, the system will create a PO
                                            that merge all requirements by category for this supplier.
                                            If option "Requirements by Category and Project" is set, the system
                                            will create a PO that merge only the requirements of one customer
                                            and one category.
                                            If option "Requirements by Order" is set, the system will create a PO
                                            that merge lines coming from the same FO/IR.'''),
    }

    _defaults = {'zone': 'national',
                 'customer_lt': 0,
                 'supplier_lt': 0,
                 'procurement_lt': 0,
                 'transport_0': TRANSPORT_TYPE[0][0], # empty
                 'transport_0_lt': 0,
                 'transport_1': TRANSPORT_TYPE[0][0], # empty
                 'transport_1_lt': 0,
                 'transport_2': TRANSPORT_TYPE[0][0], # empty
                 'transport_2_lt': 0,
                 'po_by_project': lambda *a: 'all',
                 }

res_partner()


class purchase_order_line(osv.osv):
    '''
    this modify the onchange function for product, set the date_planned value
    '''
    _inherit = 'purchase.order.line'

    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
                          partner_id, date_order=False, fiscal_position=False, date_planned=False,
                          name=False, price_unit=False, notes=False):

        res = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
                                                                 partner_id, date_order, fiscal_position, date_planned,
                                                                 name, price_unit, notes)

        if product:
            # product obj
            product_obj = self.pool.get('product.product')
            # product
            product = product_obj.browse(cr, uid, product)

            lt_date = (datetime.now() + relativedelta(days=int(product.seller_delay))).strftime('%Y-%m-%d')
            res.update(date_planned=lt_date)

        return res

purchase_order_line()


class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'

    def onchange_supplier_id(self, cr, uid, ids, name):
        '''
        set the default delay value
        '''
        if name:
            # supplier object
            partner_obj = self.pool.get('res.partner')
            # partner
            partner = partner_obj.browse(cr, uid, name)

            return {'value': {'delay': partner.default_delay}}
        else:
            return {'value': {'delay': False}}

product_supplierinfo()

