# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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


def _order_nomenclature_get_product_code_name(module, cr, uid, ids, fieldname, args, context=None):
    res = {}
    if not ids:
        return res
    fields = {  # field to read /res field
        'default_code': 'default_code',
        'name': 'default_name',
    }
    if isinstance(ids, int):
        ids = [ids]
    for rpol in module.read(cr, uid, ids, ['product_id'], context=context):
        res[rpol['id']] = {}
        for f in fields:
            res[rpol['id']][fields[f]] = ''
        if rpol['product_id']:
            rp = module.pool.get('product.product').read(cr, uid,
                                                         [rpol['product_id'][0]], list(fields.keys()), context=context)
            if rp and rp[0]:
                for f in fields:
                    res[rpol['id']][fields[f]] = rp[0].get(f, '')
    return res

#
# PO
#
class purchase_order_line(osv.osv):
    '''
    1. add new fields :
       - nomenclature_id : contains the nomenclature id
       - nomenclature_code : contains the corresponding code
       - nomenclature_description : contains the corresponding description
    '''
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
                          partner_id, date_order=False, fiscal_position=False, date_planned=False,
                          name=False, price_unit=False, notes=False):
        '''
        overriden on_change function
        '''
        result = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
                                                                    partner_id, date_order, fiscal_position, date_planned,
                                                                    name, price_unit, notes)

        # comment is cleared
        result['value'].update({'comment':False})

        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
            # product has been selected, nomenclatures are readonly and empty
            self.pool.get('product.product')._resetNomenclatureFields(result['value'])
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            # name is the name of the product
            result['value'].update({'name':productObj.name})
            result['value'].update({'default_code':productObj.default_code})
            result['value'].update({'default_name':productObj.name})
        else:
            result['value'].update({'default_code':False})
            result['value'].update({'default_name':False})

        return result

    def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
                           partner_id, date_order=False, fiscal_position=False, date_planned=False,
                           name=False, price_unit=False, notes=False):
        '''
        override product_uom_change to avoid the reset of Comment when the UOM is changed
        '''
        # call to super
        result = super(purchase_order_line, self).product_uom_change(cr, uid, ids, pricelist, product, qty, uom,
                                                                     partner_id, date_order, fiscal_position, date_planned,
                                                                     name, price_unit, notes)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']

        if qty:
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, qty, 'product_qty', result=result)

        return result

    def check_digits(self, cr, uid, result, pol, qty=0, price_unit=0, context=None):
        if context is None:
            context = {}
        new_qty = result.get('value', {}).get('product_qty', qty)
        new_price = result.get('value', {}).get('price_unit', price_unit)
        if new_qty >= self._max_qty or new_qty * new_price >= self._max_amount:
            result.setdefault('warning', {'title': '', 'message': ''})
            result['warning'].setdefault('title', '')
            result['warning'].setdefault('message', '')
            result['warning']['message'] = "\n".join([result['warning']['message'], _(self._max_msg)])
            if new_qty >= self._max_qty:
                result.update({
                    'value': {'product_qty': pol.get('product_qty', 0.00)},
                })
        return True

    def product_qty_change(self, cr, uid, ids, pricelist, product, qty, uom,
                           partner_id, date_order=False, fiscal_position=False, date_planned=False,
                           name=False, price_unit=False, notes=False, state=False, old_unit_price=False,
                           nomen_manda_0=False, comment=False,context=None):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed
        '''

        if not context:
            context = {}

        pol = {}
        if ids:
            pol = self.read(cr, uid, ids[0], ['product_qty', 'price_unit'], context=context)

        if not product and not comment and not nomen_manda_0 and qty != 0.00:
            if qty >= self._max_qty or qty*price_unit >= self._max_amount:
                return {
                    'value': {'product_qty': pol.get('product_qty', 0.00), 'price_unit': pol.get('price_unit', 0.00)},
                    'warning': {'title': '', 'message': _(self._max_msg)}
                }
            return {}

        prod_context = context.copy()
        if 'categ' in prod_context:
            del prod_context['categ']

        result = self.product_id_on_change(cr, uid, ids, pricelist, product, qty, uom,
                                           partner_id, date_order, fiscal_position, date_planned,
                                           name, price_unit, notes, state, old_unit_price,nomen_manda_0,comment,context=prod_context)

        if result.get('warning') and result['warning'].get('title') == 'Short Shelf Life product':
            del result['warning']

        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']

        if qty:
            uom = uom or result.get('value', {}).get('product_uom')
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, qty, 'product_qty', result=result)

        self.check_digits(cr, uid, result, pol, context=context)
        return result

    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description':False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            productObj = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
            vals.update({'name':productObj.name})
            vals.update({'default_code':productObj.default_code})
            vals.update({'default_name':productObj.name})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            if 'nomen_manda_0' in vals:
                sale = self.pool.get('sale.order.line')
                sale._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code':False})
            vals.update({'default_name':False})

            if 'comment' in vals:
                vals.update({'name':vals['comment']})

        # clear nomenclature filter values
        #self.pool.get('product.product')._resetNomenclatureFields(vals)

    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)

        return super(purchase_order_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        if not ids:
            return True
        self._relatedFields(cr, uid, vals, context)

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        direct call to sale processes
        '''
        sale = self.pool.get('sale.order.line')
        return sale.nomenChange(cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                                nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)

    def codeChange(self, cr, uid, id, fieldNumber, code, nomenclatureType,
                   nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        direct call to sale processes
        '''
        sale = self.pool.get('sale.order.line')
        return sale.codeChange(cr, uid, id, fieldNumber, code, nomenclatureType,
                               nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)

    def _get_product_code_name(self, cr, uid, ids, fieldname, args, context=None):
        return _order_nomenclature_get_product_code_name(self, cr, uid, ids, fieldname, args, context=context)

    # PO/SO - IDENTICAL
    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=1024),
        'comment': fields.char('Comment', size=1024),
        'name': fields.char('Product description', size=1024, required=True),
        'default_code': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Code', multi="product", sort_column='product_id'),
        'default_name': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Description', multi="product", sort_column='product_id.name'),

        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),

        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
    }
    ### END OF COPY

    _defaults = {
    }

    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)

    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, fo_id=False, context=None):
        fo_is_ir = fo_id and self.pool.get('sale.order').read(cr, uid, fo_id, ['procurement_request'])['procurement_request'] or False
        nomen_srv_domain = [('name', '=', 'SRV'), ('type', '=', 'mandatory'), ('level', '=', 0)]
        data_nomen_srv = self.pool.get('product.nomenclature').search(cr, uid, nomen_srv_domain, limit=1)
        if isinstance(position, int) and position == 0 and nomen_manda_0 and fo_id and not fo_is_ir and \
                data_nomen_srv and nomen_manda_0 == data_nomen_srv[0]:
            return {
                'value': {'nomen_manda_0': False},
                'warning': {
                    'title': _('Warning'),
                    'message': _("You can not select SRV as Nomenclature Main Type if the line is linked to a FO"),
                }
            }
        return self.pool.get('sale.order.line').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)

    def onChangeSubNom(self, cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context=None):
        return self.pool.get('sale.order.line').onChangeSubNom(cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context)


purchase_order_line()


class purchase_order_merged_line(osv.osv):
    _name = 'purchase.order.merged.line'
    _inherit = 'purchase.order.merged.line'

    def _get_product_code_name(self, cr, uid, ids, fieldname, args, context=None):
        return _order_nomenclature_get_product_code_name(self, cr, uid, ids, fieldname, args, context=context)

    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=1024),
        'comment': fields.char('Comment', size=1024),
        'name': fields.char('Comment', size=1024, required=True),
        'default_code': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Code', multi="product",),
        'default_name': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Description', multi="product",),

        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),

        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
    }

purchase_order_merged_line()

#
# SO
#
class sale_order_line(osv.osv):
    '''
    1. add new fields :
       - nomenclature_id : contains the nomenclature id
       - nomenclature_code : contains the corresponding code
       - nomenclature_description : contains the corresponding description
    '''
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='',
                          partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False,
                          fiscal_position=False, flag=False, context=None):
        '''
        overriden on_change function
        '''
        if context is None:
            context = {}

        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom, qty_uos, uos,
                                                                name, partner_id, lang, update_tax, date_order, packaging,
                                                                fiscal_position, flag, context=context)

        # comment is cleared
        result['value'].update({'comment':False})

        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
            # product has been selected, nomenclatures are readonly and empty
            self.pool.get('product.product')._resetNomenclatureFields(result['value'])
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            # name is the name of the product
            result['value'].update({'name':productObj.name})
            result['value'].update({'default_code':productObj.default_code})
            result['value'].update({'default_name':productObj.name})
        else:
            result['value'].update({'default_code':False})
            result['value'].update({'default_name':False})

        return result

    def product_uom_change(self, cr, uid, ids, pricelist, product, qty=0,
                           uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                           lang=False, update_tax=True, date_order=False):
        '''
        override product_uom_change to avoid the reset of Comment when the UOM is changed
        '''
        # call to super
        result = super(sale_order_line, self).product_uom_change(cr, uid, ids, pricelist, product, qty,
                                                                 uom, qty_uos, uos, name, partner_id, lang, update_tax, date_order)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']

        # Round up the quantity
        if qty:
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, qty, 'product_qty', result=result)

        return result

    def check_digits(self, cr, uid, result, sol, qty=0, price_unit=0, context=None):
        if context is None:
            context = {}
        new_qty = result.get('value', {}).get('product_uom_qty', qty)
        new_price = result.get('value', {}).get('price_unit', price_unit)
        if new_qty >= self._max_value or new_qty * new_price >= self._max_value:
            result.setdefault('warning', {'title': '', 'message': ''})
            result['warning'].setdefault('title', '')
            result['warning'].setdefault('message', '')
            result['warning']['message'] = "\n".join([result['warning']['message'], _(self._max_msg)])
            if new_qty >= self._max_value:
                result.update({
                    'value': {'product_uom_qty': sol.get('product_uom_qty', 0.00), 'product_uos_qty': sol.get('product_uos_qty', 0.00)},
                })
        return True

    def change_price_unit(self, cr, uid, ids, product_uom_qty, price_unit, context=None):
        if context is None:
            context = {}
        result = {}
        sol = {}
        if ids:
            sol = self.read(cr, uid, ids[0], ['product_uom_qty', 'product_uos_qty'], context=context)
        self.check_digits(cr, uid, result, sol, product_uom_qty, price_unit, context=context)
        return result

    def product_qty_change(self, cr, uid, ids, pricelist, product, qty=0,
                           uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                           lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, price_unit=0, context=None):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed
        '''
        sol = {}
        if ids:
            sol = self.read(cr, uid, ids[0], ['product_uom_qty', 'product_uos_qty'], context=context)

        result = self.product_id_change(cr, uid, ids, pricelist, product, qty,
                                        uom, qty_uos, uos, name, partner_id,
                                        lang, update_tax, date_order, packaging, fiscal_position, flag)

        if result.get('warning') and result['warning'].get('title') == 'Short Shelf Life product':
            del result['warning']

        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']
        # drop modification to qty
        if 'product_uos_qty' in result['value']:
            del result['value']['product_uos_qty']
        # drop modification to qty
        if 'product_uom_qty' in result['value']:
            del result['value']['product_uom_qty']

        # Round up the quantity
        if qty:
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, qty, ['product_uom_qty', 'product_uos_qty'], result=result)

        self.check_digits(cr, uid, result, sol, qty, price_unit, context=context)
        return result

    def product_packaging_change(self, cr, uid, ids, pricelist, product, qty=0,
                                 uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                                 lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed
        '''
        result = self.product_qty_change(cr, uid, ids, pricelist, product, qty,
                                         uom, qty_uos, uos, name, partner_id,
                                         lang, update_tax, date_order, packaging, fiscal_position, flag)

        return result

    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description':False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            productObj = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
            vals.update({'name':productObj.name})
            vals.update({'default_code':productObj.default_code})
            vals.update({'default_name':productObj.name})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            self._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code':False})
            vals.update({'default_name':False})

            if 'comment' in vals:
                vals.update({'name':vals['comment']})
        # clear nomenclature filter values
        #self.pool.get('product.product')._resetNomenclatureFields(vals)

    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)

        return super(sale_order_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        if not ids:
            return True
        self._relatedFields(cr, uid, vals, context)

        return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

    def _setNomenclatureInfo(self, cr, uid, values, context=None):
        '''
        set nomenclature_description
        '''
        if not values:
            return {}

        constants = self.pool.get('product.nomenclature')._returnConstants()

        # the last selected level
        mandaDesc = ''
        levels = constants['levels']
        ids = [x for x in range(levels) if ('nomen_manda_%i'%x in values) and (values['nomen_manda_%i'%x])]
        if len(ids) > 0:
            id = values['nomen_manda_%i'%max(ids)]
            mandaDesc = self.pool.get('product.nomenclature').name_get(cr, uid, [id], context)[0][1]

        description = [mandaDesc]

        # add optional names
        sublevels = constants['sublevels']
        ids = [x for x in range(sublevels) if ('nomen_sub_%i'%x in values) and (values['nomen_sub_%i'%x])]
        ids = [values['nomen_sub_%i'%x] for x in ids]
        subNomenclatures = self.pool.get('product.nomenclature').read(cr, uid, ids, ['name'], context=context)

        for n in subNomenclatures:
            description.append(n['name'])

        values.update({'nomenclature_description': ':'.join(description)})

    def _productDomain(self, cr, uid, id, context=None):
        '''
        product the dynamic product's domain
        '''
        # all values are updated from 'result' in context
        # loop through these values
        # if the value is not False, create a new domain rule
        assert context, 'No context, error on function call'

        # check and create domain dictionary
        if 'domain' in context['result']:
            domain = context['result']['domain']
        else:
            domain = {}
            context['result']['domain'] = domain

        # empty product domain list
        productList = []
        domain.update({'product_id': productList})


        values = context['result']['value']
        for k,v in list(values.items()):
            if v:
                newRule = (k, '=', v)
                productList.append(newRule)

    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        first call the standard product_nomenclature process
        secondly complete dynamic domain
        '''
        assert context, 'No context, error on function call'

        product = self.pool.get('product.product')
        product.nomenChange(cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                            nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
        #self._productDomain(cr, uid, id, context)
        self._setNomenclatureInfo(cr, uid, context['result']['value'], context)

        result = context['result']

        return result

    def codeChange(self, cr, uid, id, fieldNumber, code, nomenclatureType,
                   nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        first call the standard product_nomenclature process
        secondly complete dynamic domain
        '''
        assert context, 'No context, error on function call'


        product = self.pool.get('product.product')
        product.codeChange(cr, uid, id, fieldNumber, code, nomenclatureType,
                           nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
        #self._productDomain(cr, uid, id, context)
        self._setNomenclatureInfo(cr, uid, context['result']['value'], context)

        result = context['result']
        return result

    def _get_product_code_name(self, cr, uid, ids, fieldname, args, context=None):
        return _order_nomenclature_get_product_code_name(self, cr, uid, ids, fieldname, args, context=context)

    # PO/SO - IDENTICAL
    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=1024),
        'comment': fields.char('Comment', size=1024),
        'name': fields.char('Product description', size=1024, required=True, select=True, readonly=True, states={'draft': [('readonly', False)]}),
        'default_code': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Code', multi="product",),
        'default_name': fields.function(_get_product_code_name, type='char', size=1024,
                                        method=True, string='Product Description', multi="product",),

        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),

        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
    }
    ### END OF COPY

    _defaults = {
    }

    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)

    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=False, instance_sync_order_ref=False, context=None):
        ret = self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
        newval = {}
        if isinstance(position, int) and position == 0 and nomen_manda_0 and instance_sync_order_ref:
            nomen_srv_domain = [('name', '=', 'SRV'), ('type', '=', 'mandatory'), ('level', '=', 0)]
            data_nomen_srv = self.pool.get('product.nomenclature').search(cr, uid, nomen_srv_domain, limit=1)
            if data_nomen_srv and nomen_manda_0 == data_nomen_srv[0] and \
                    'FO' in self.pool.get('sync.order.label').read(cr, uid, instance_sync_order_ref)['name']:
                return {
                    'value': {'nomen_manda_0': False},
                    'warning': {
                        'title': _('Warning'),
                        'message': _("You can not select SRV as Nomenclature Main Type if the Order in sync. instance is a FO"),
                    }
                }
        for i in range(0, 4):
            if 'nomen_manda_%s'%i not in ret.get('value',{}):
                newval['nomen_manda_%s'%i] = eval('nomen_manda_%s'%i)
        self._setNomenclatureInfo(cr, uid, newval)
        if 'value' not in ret:
            ret['value'] = {}
        ret['value']['nomenclature_description'] = newval.get('nomenclature_description')
        return ret

    def onChangeSubNom(self, cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context=None):
        newval = {}
        for i in range(0, 6):
            if i < 4:
                newval['nomen_manda_%s'%i] = eval('nomen_manda_%s'%i)
            newval['nomen_sub_%s'%i] = eval('nomen_sub_%s'%i)
        self._setNomenclatureInfo(cr, uid, newval)
        ret = {'value': {}}
        ret['value']['nomenclature_description'] = newval.get('nomenclature_description')
        return ret



sale_order_line()
