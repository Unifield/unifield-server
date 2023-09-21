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

from osv import osv, fields
from tools.translate import _


class purchase_order_line(osv.osv):
    '''
    information from product are repacked
    '''
    _inherit = 'purchase.order.line'

    def _get_manufacturers(self, cr, uid, ids, field_name, arg, context=None):
        '''
        get manufacturers info
        '''
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            result[record.id] = {
                'manufacturer_id': False,
                'second_manufacturer_id': False,
                'third_manufacturer_id': False,
            }
            po_supplier = record.order_id.partner_id
            if record.product_id:
                for seller_id in record.product_id.seller_ids:
                    if seller_id.name == po_supplier:
                        result[record.id] = {
                            'manufacturer_id': seller_id.manufacturer_id.id,
                            'second_manufacturer_id': seller_id.second_manufacturer_id.id,
                            'third_manufacturer_id': seller_id.third_manufacturer_id.id,
                        }
                        break

        return result

    def _getProductInfo(self, cr, uid, ids, field_name, arg, context=None):
        '''
        compute function fields related to product identity
        '''
        prod_obj = self.pool.get('product.product')
        order_obj = self.pool.get('purchase.order')
        seller_obj = self.pool.get('product.supplierinfo')
        # the name of the field is used to select the data to display
        result = {}
        for i in ids:
            result[i] = {}
            for f in field_name:
                result[i].update({f:False,})

        line_result = self.read(cr, uid, ids, ['product_id', 'order_id'], context=context)
        product_list = [x['product_id'][0] for x in line_result if x['product_id']]
        product_dict = dict((x['id'], x) for x in prod_obj.read(cr, uid, product_list,
                                                                ['default_code', 'name', 'seller_ids'], context=context))

        order_ids = set([line['order_id'][0] for line in line_result])
        results_order = order_obj.read(cr, uid, list(order_ids), ['id', 'partner_id'], context=context)
        order_id_to_partnerid = {}
        for result_order in results_order:
            if result_order['partner_id']:
                order_id_to_partnerid[result_order['id']] = result_order['partner_id'][0]

        seller_ids = set()
        for line in line_result:
            if line['product_id']:
                prod = product_dict[line['product_id'][0]]
                for seller_id in prod['seller_ids']:
                    seller_ids.add(seller_id)

        supplierinfos_by_id = dict([(x['id'], x) for x in seller_obj.read(cr, uid,
                                                                          list(seller_ids), ['name', 'product_code', 'product_name'], context=context)])

        for line in line_result:
            # default values
            internal_code = False
            internal_name = False
            supplier_code = False
            supplier_name = False
            if line['product_id']:
                prod = product_dict[line['product_id'][0]]
                # new fields
                internal_code = prod['default_code']
                internal_name = prod['name']
                # filter the seller list - only select the seller which corresponds
                # to the supplier selected during PO creation
                # if no supplier selected in product, there is no specific supplier info
                if prod['seller_ids']:
                    order_id = line['order_id'][0]
                    partner_id = order_id_to_partnerid[order_id]

                    sellers = [x for x in prod['seller_ids'] if supplierinfos_by_id[x]['name'][0] == partner_id]
                    if sellers:
                        cr.execute('''
                            SELECT i.id FROM product_supplierinfo i 
                            LEFT JOIN pricelist_partnerinfo p ON p.suppinfo_id = i.id 
                            WHERE i.id in %s 
                            ORDER BY COALESCE(p.valid_from, '1970-01-01') DESC LIMIT 1
                        ''', (tuple(sellers),))  # Search for the most recent Supplier
                        seller_id = cr.fetchone()[0]
                        supplierinfo = supplierinfos_by_id[seller_id]
                        supplier_code = supplierinfo['product_code']
                        supplier_name = supplierinfo['product_name']
            # update dic
            result[line['id']].update(internal_code=internal_code,
                                      internal_name=internal_name,
                                      supplier_code=supplier_code,
                                      supplier_name=supplier_name,
                                      )

        return result

    def _generate_order_by(self, order_spec, query, context=None):
        if order_spec and 'supplier_code' in order_spec:
            order_specs = order_spec.split(',')
            if len(order_specs) > 1 and not order_specs[1].strip().startswith('id'):
                raise osv.except_osv(_('Warning !'), _("You can't combine order by supplier_code with other order fields"))
            order_split = order_specs[0].split(' ')
            direction = order_split[1].strip() if len(order_split) > 1 else ''
            query.join([self._table, 'purchase_order', 'order_id', 'id'], outer=False)
            join = ' left join "product_supplierinfo" on "product_supplierinfo".id = (select id from product_supplierinfo si where si.name="purchase_order"."partner_id" and si."product_id"="purchase_order_line"."product_id" order by sequence limit 1)'
            return ' ORDER BY %s %s, "purchase_order_line"."id"' % ('"product_supplierinfo"."product_code"',direction), [join]

        return super(purchase_order_line, self)._generate_order_by(order_spec, query, context=context)

    _columns = {'internal_code': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Internal code', multi='get_vals',),
                'internal_name': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Internal name', multi='get_vals',),
                'supplier_code': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Supplier code', multi='get_vals', sort_column='supplier_code'),
                'supplier_name': fields.function(_getProductInfo, method=True, type='char', size=1024, string='Supplier name', multi='get_vals',),
                # new colums to display product manufacturers linked to the purchase order supplier
                'manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Manufacturer", store=False, multi="all"),
                'second_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Second Manufacturer", store=False, multi="all"),
                'third_manufacturer_id': fields.function(_get_manufacturers, method=True, type='many2one', relation="res.partner", string="Third Manufacturer", store=False, multi="all"),
                }

purchase_order_line()

class product_product(osv.osv):

    _inherit = 'product.product'
    _description = 'Product'

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            code = d.get('default_code',False)
            if code and not name:
                name = code
            elif code:
                name = '[%s] %s' % (code,name)
            if d.get('variants'):
                name = '%s - %s' % (name, d['variants'],)
            return (d['id'], name)

        result = []

        if context.get('default_code_only'):
            fields_to_read = ['id', 'default_code']
        elif context.get('default_description_only'):
            fields_to_read = ['id', 'name']
        else:
            fields_to_read = ['id', 'name', 'default_code', 'variants']
        read_result = self.read(cr, user, ids,
                                fields_to_read,
                                context=context)

        for product_dict in read_result:
            result.append(_name_get(product_dict))
        return result

product_product()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
