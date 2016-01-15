# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
import re
from tools.translate import _
from lxml import etree
import logging
import tools
from os import path

class product_section_code(osv.osv):
    _name = "product.section.code"
    _rec_name = 'section'

    _columns = {
        'code': fields.char('Code', size=4),
        'section': fields.char('Section', size=32),
        'description': fields.char('Description', size=128),
    }
product_section_code()

class product_status(osv.osv):
    _name = "product.status"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True),
        'no_external': fields.boolean(string='External partners orders'),
        'no_esc': fields.boolean(string='ESC partners orders'),
        'no_internal': fields.boolean(string='Internal partners orders'),
        'no_consumption': fields.boolean(string='Consumption'),
        'no_storage': fields.boolean(string='Storage'),
    }

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid,
                [('state','in',ids)], limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this status because it\'s used at least in one product'))
        return super(product_status, self).unlink(cr, uid, ids, context=context)

product_status()

class product_international_status(osv.osv):
    _name = "product.international.status"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True),
        'no_external': fields.boolean(string='External partners orders'),
        'no_esc': fields.boolean(string='ESC partners orders'),
        'no_internal': fields.boolean(string='Internal partners orders'),
        'no_consumption': fields.boolean(string='Consumption'),
        'no_storage': fields.boolean(string='Storage'),
    }
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Raise an error if the status is used in a product
        ids_p = self.pool.get('product.product').search(cr, uid,
                [('international_status','in',ids)],
                limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this product creator because it\'s used at least in one product'))

        # Raise an error if the status is ITC or Temporary because there are used in some product.product methods
        tmp_int_1 = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1')
        int_1 = tmp_int_1[1] or False
        tmp_int_5 = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_5')
        int_5 = tmp_int_5[1] or False

        if int_1 and int_1 in ids:
            raise osv.except_osv(_('Error'), _('You cannot remove the \'ITC\' international status because it\'s a system value'))
        if int_5 and int_5 in ids:
            raise osv.except_osv(_('Error'), _('You cannot remove the \'Temporary\' international status because it\'s a system value'))

        return super(product_international_status, self).unlink(cr, uid, ids, context=context)

product_international_status()

class product_heat_sensitive(osv.osv):
    _name = "product.heat_sensitive"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True),
    }

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid,
                [('heat_sensitive_item','in',ids)],
                limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this heat sensitive because it\'s used at least in one product'))
        return super(product_heat_sensitive, self).unlink(cr, uid, ids, context=context)

product_heat_sensitive()

class product_cold_chain(osv.osv):
    _name = "product.cold_chain"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True),
    }

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid,
                [('cold_chain','in',ids)],
                limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this cold chain because it\'s used at least in one product'))
        return super(product_cold_chain, self).unlink(cr, uid, ids, context=context)

product_cold_chain()

class product_supply_source(osv.osv):
    _name = "product.supply.source"
    _rec_name = 'source'

    _columns = {
        'source': fields.char('Supply source', size=32),
    }
product_supply_source()

class product_justification_code(osv.osv):
    _name = "product.justification.code"
    _rec_name = 'code'
    _columns = {
        'code': fields.char('Justification Code', size=32, required=True, translate=True),
        'description': fields.char('Justification Description', size=256, required=True),
    }

    def name_get(self, cr, user, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, user, ids, ['code'], context=context)
        res = []
        for record in reads:
            code = record['code']
            res.append((record['id'], code))
        return res

product_justification_code()

class product_attributes_template(osv.osv):
    _inherit = "product.template"

    _columns = {
        'type': fields.selection([('product','Stockable Product'),('consu', 'Non-Stockable')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
    }

    _defaults = {
        'type': 'product',
        'cost_method': lambda *a: 'average',
    }

product_attributes_template()


class product_country_restriction(osv.osv):
    _name = 'res.country.restriction'

    _columns = {
        'name': fields.char(size=128, string='Restriction'),
        'product_ids': fields.one2many('product.product', 'country_restriction', string='Products'),
    }

product_country_restriction()

class product_template(osv.osv):
    _inherit = 'product.template'

    _columns = {
        'state': fields.many2one('product.status', 'Status', help="Tells the user if he can use the product or not."),
    }

product_template()

class product_attributes(osv.osv):
    _inherit = "product.product"

    def init(self, cr):
        if hasattr(super(product_attributes, self), 'init'):
            super(product_attributes, self).init(cr)
        mod_obj = self.pool.get('ir.module.module')
        mode = mod_obj.search(cr, 1, [('name', '=', 'product_attributes'), ('state', '=', 'to install')]) and 'init' or 'update'
        logging.getLogger('init').info('HOOK: module product_attributes: loading product_attributes_data.xml')
        pathname = path.join('product_attributes', 'product_attributes_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'product_attributes', file, {}, mode=mode, noupdate=True)

    def _get_nomen(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []
            nomen_field_names = ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3', 'nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5']
            for field in nomen_field_names:
                value = getattr(product, field, False).id
                if value:
                    res[product.id].append(value)
        return res

    def _search_nomen(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        if context is None:
            context = {}

        ids = []

        for arg in args:
            if arg[0] == 'nomen_ids' and arg[1] == '=' and arg[2]:
                nomen = self.pool.get('product.nomenclature').browse(cr, uid, arg[2], context=context)
                if nomen.type == 'mandatory':
                    ids = self.search(cr, uid, [('nomen_manda_%s' % nomen.level, '=', nomen.id)], context=context)
                else:
                    ids = self.search(cr, uid, [('nomen_sub_0', '=', nomen.id)], context=context)
                    ids.append(self.search(cr, uid, [('nomen_sub_1', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_2', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_3', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_4', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_5', '=', nomen.id)], context=context))
            elif arg[0] == 'nomen_ids' and arg[1] == 'in' and arg[2]:
                for nomen in self.pool.get('product.nomenclature').browse(cr, uid, arg[2], context=context):
                    if nomen.type == 'mandatory':
                        ids = self.search(cr, uid, [('nomen_manda_%s' % nomen.level, '=', nomen.id)], context=context)
                    else:
                        ids = self.search(cr, uid, [('nomen_sub_0', '=', nomen.id)], context=context)
                        ids.append(self.search(cr, uid, [('nomen_sub_1', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_2', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_3', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_4', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_5', '=', nomen.id)], context=context))
            else:
                return []

        return [('id', 'in', ids)]

    def _get_restriction(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        product_state = self.pool.get('product.status')
        intl_state = self.pool.get('product.international.status')
        for product in self.read(cr, uid, ids, ['state', 'international_status'], context=context):
            res[product['id']] = {
                'no_external': False,
                'no_esc': False,
                'no_internal': False,
                'no_consumption': False,
                'no_storage': False
            }
            fields = ['no_external', 'no_esc', 'no_internal', 'no_consumption', 'no_storage']
            state = None
            intl = None
            if product['state']:
                state = product_state.read(cr, uid, product['state'][0], fields, context=context)
            if product['international_status']:
                intl = intl_state.read(cr, uid, product['international_status'][0], fields, context=context)

            if state or intl:
                for f in fields:
                    res[product['id']][f] = (state and state[f]) or (intl and intl[f]) or False

        return res

    def _get_product_status(self, cr, uid, ids, context=None):
        return self.pool.get('product.product').search(cr, uid, [('state', 'in', ids)], context=context)

    def _get_international_status(self, cr, uid, ids, context=None):
        return self.pool.get('product.product').search(cr, uid, [('international_status', 'in', ids)], context=context)

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = False

        return res

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    # This method is here because the following domain didn't work on field order/purchase order lines
    # [('no_internal', '=', parent.partner_type != 'internal'), ('no_external', '=', parent.partner_type != 'external'),('no_esc', '=', parent.partner_type != 'esc'),
    def _src_available_for_restriction(self, cr, uid, obj, name, args, context=None):
        '''
        Search available products for the partner given in args
        '''
        if context is None:
            context = {}

        for arg in args:
            if arg[0] == 'available_for_restriction' and arg[1] == '=' and arg[2]:
                if isinstance(arg[2], dict) and arg[2].get('location_id'):
                    # Compute the constraint if a location is passed in vals
                    location = self.pool.get('stock.location').browse(cr, uid, arg[2].get('location_id'), context=context)
                    bef_scrap_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
                    if location.usage != 'inventory' and not location.destruction_location and (not bef_scrap_id or location.id != bef_scrap_id):
                        return [('no_storage', '=', False)]

                if arg[2] == 'external':
                    return [('no_external', '=', False)]
                elif arg[2] == 'esc':
                    return [('no_esc', '=', False)]
                elif arg[2] in ('internal', 'intermission', 'section'):
                    return [('no_internal', '=', False)]
                elif arg[2] == 'consumption':
                    return [('no_consumption', '=', False)]
                elif arg[2] == 'storage':
                    return [('no_storage', '=', False)]
                elif arg[2] in ('picking', 'tender'):
                    return [('no_external', '=', False), ('no_internal', '=', False), ('no_esc', '=', False)]

        return []

    _columns = {
        'duplicate_ok': fields.boolean('Is a duplicate'),
        'loc_indic': fields.char('Indicative Location', size=64),
        'description2': fields.text('Description 2'),
        'old_code' : fields.char('Old code', size=64),
        'new_code' : fields.char('New code', size=64),

        'international_status': fields.many2one('product.international.status', 'Product Creator', required=False),
        'perishable': fields.boolean('Expiry Date Mandatory'),
        'batch_management': fields.boolean('Batch Number Mandatory'),
        'product_catalog_page' : fields.char('Product Catalog Page', size=64),
        'product_catalog_path' : fields.char('Product Catalog Path', size=64),
        'short_shelf_life': fields.boolean('Short Shelf Life'),
        'criticism': fields.selection([('',''),
            ('exceptional','1-Exceptional'),
            ('specific','2-Specific'),
            ('important','3-Important'),
            ('medium','4-Medium'),
            ('common','5-Common'),
            ('other','X-Other')], 'Criticality'),
        'narcotic': fields.boolean('Narcotic/Psychotropic'),
        'abc_class': fields.selection([('',''),
            ('a','A'),
            ('b','B'),
            ('c','C')], 'ABC Class'),
        'section_code_ids': fields.many2many('product.section.code','product_section_code_rel','product_id','section_code_id','Section Code'),
        'library': fields.selection([('',''),
            ('l1','L1'),
            ('l2','L2'),
            ('l3','L3'),
            ('l4','L4')], 'Library'),

        'supply_source_ids': fields.many2many('product.supply.source','product_supply_source_rel','product_id','supply_source_id','Supply Source'),

        'sublist' : fields.char('Sublist', size=64),
        'composed_kit': fields.boolean('Kit Composed of Kits/Modules'),
        'options_ids': fields.many2many('product.product','product_options_rel','product_id','product_option_id','Options'),

        'heat_sensitive_item': fields.many2one('product.heat_sensitive', 'Temperature sensitive item',),
        'cold_chain': fields.many2one('product.cold_chain', 'Cold Chain',),
        'show_cold_chain': fields.boolean('Show cold chain'),
        # Inverse of m2m options_ids
        'options_ids_inv': fields.many2many('product.product', 'product_options_rel', 'product_option_id', 'product_id', 'Options Inv.'),
        'sterilized': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Sterile'),
        'single_use': fields.selection([('yes', 'Yes'),('no', 'No')], string='Single Use'),
        'justification_code_id': fields.many2one('product.justification.code', 'Justification Code'),
        'med_device_class': fields.selection([('',''),
            ('I','Class I (General controls)'),
            ('II','Class II (General control with special controls)'),
            ('III','Class III (General controls and premarket)')], 'Medical Device Class'),
        'closed_article': fields.selection([('yes', 'Yes'), ('no', 'No'),],string='Closed Article'),
        'dangerous_goods': fields.boolean('Dangerous Goods'),
        'restricted_country': fields.boolean('Restricted in the Country'),
        'country_restriction': fields.many2one('res.country.restriction', 'Country Restriction'),
        # TODO: validation on 'un_code' field
        'un_code': fields.char('UN Code', size=7),
        'gmdn_code' : fields.char('GMDN Code', size=5),
        'gmdn_description' : fields.char('GMDN Description', size=64),
        'life_time': fields.integer('Product Life Time',
            help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
            help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
            help='The number of months before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of months after which an alert should be notified about the production lot."),
        'currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'field_currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'nomen_ids': fields.function(_get_nomen, fnct_search=_search_nomen,
                             type='many2many', relation='product.nomenclature', method=True, string='Nomenclatures'),
        'controlled_substance': fields.boolean(string='Controlled substance'),
        'uom_category_id': fields.related('uom_id', 'category_id', string='Uom Category', type='many2one', relation='product.uom.categ'),
        'no_external': fields.function(_get_restriction, method=True, type='boolean', string='External partners orders', readonly=True, multi='restriction',
                                       store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                              'product.status': (_get_product_status, ['no_external'], 10),
                                              'product.international.status': (_get_international_status, ['no_external'], 10),}),
        'no_esc': fields.function(_get_restriction, method=True, type='boolean', string='ESC partners orders', readonly=True, multi='restriction',
                                  store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                         'product.status': (_get_product_status, ['no_esc'], 10),
                                         'product.international.status': (_get_international_status, ['no_esc'], 10),}),
        'no_internal': fields.function(_get_restriction, method=True, type='boolean', string='Internal partners orders', readonly=True, multi='restriction',
                                       store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                              'product.status': (_get_product_status, ['no_internal'], 10),
                                              'product.international.status': (_get_international_status, ['no_internal'], 10),}),
        'no_consumption': fields.function(_get_restriction, method=True, type='boolean', string='Comsumption', readonly=True, multi='restriction',
                                          store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                                 'product.status': (_get_product_status, ['no_consumption'], 10),
                                                 'product.international.status': (_get_international_status, ['no_consumption'], 10),}),
        'no_storage': fields.function(_get_restriction, method=True, type='boolean', string='Storage', readonly=True, multi='restriction',
                                      store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                             'product.status': (_get_product_status, ['no_storage'], 10),
                                             'product.international.status': (_get_international_status, ['no_storage'], 10),}),
        'available_for_restriction': fields.function(_get_dummy, fnct_search=_src_available_for_restriction, method=True, type='boolean',
                                                 store=False, string='Available for the partner', readonly=True),
        'form_value': fields.text(string='Form', translate=True),
        'fit_value': fields.text(string='Fit', translate=True),
        'function_value': fields.text(string='Function', translate=True),
        'standard_ok': fields.boolean(string='Standard'),
        'soq_weight': fields.float(digits=(16,5), string='SoQ Weight'),
        'soq_volume': fields.float(digits=(16,5), string='SoQ Volume'),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
    }

    # US-43: Remove the default_get that set value on Product Creator field. By removing the required = True value
    # in the field (international_status) declaration and put required=True in the XML view, the default value
    # is blank and the field is mandatory before save
    #def default_get(self, cr, uid, fields, context=None):
    #    res = super(product_attributes, self).default_get(cr, uid, fields, context=context)
    #    id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1') and self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1')[1] or 1
    #    res.update({'international_status': id })
    #    return res

    _defaults = {
        'duplicate_ok': True,
        'perishable': False,
        'batch_management': False,
        'short_shelf_life': False,
        'narcotic': False,
        'composed_kit': False,
        'dangerous_goods': False,
        'restricted_country': False,
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'field_currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'vat_ok': lambda obj, cr, uid, c: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
    }

    def _check_uom_category(self, cr, uid, ids, context=None):
        '''
        Check the consistency of UoM category on product form
        '''
        move_obj = self.pool.get('stock.move')
        for product in self.browse(cr, uid, ids, context=context):
            uom_categ_id = product.uom_id.category_id.id
            uom_categ_name = product.uom_id.category_id.name
            move_ids = move_obj.search(cr, uid, [('product_id', '=', product.id)], context=context)
            if move_ids:
                uom_categ_id = move_obj.browse(cr, uid, move_ids[0], context=context).product_uom.category_id.id
                uom_categ_name = move_obj.browse(cr, uid, move_ids[0], context=context).product_uom.category_id.name

            if uom_categ_id != product.uom_id.category_id.id:
                raise osv.except_osv(_('Error'), _('There are some stock moves with this product on the system. So you should keep the same UoM category than these stock moves. UoM category used in stock moves : %s') % uom_categ_name)

        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Add a filter if the 'available_for_restriction' attribute is passed on context
        '''
        if context is None:
            context = {}

        res = super(product_attributes, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

        if view_type == 'search' and context.get('available_for_restriction'):
            context.update({'search_default_not_restricted': 1})
            root = etree.fromstring(res['arch'])
            # xpath of fields to be modified
            xpath = '//filter[@string="Service with Reception"]'
            fields = root.xpath(xpath)

            if not fields:
                return res

            state_index = root.index(fields[0])
            new_separator = """<separator orientation="vertical" />"""
            sep_form = etree.fromstring(new_separator)
            arg = context.get('available_for_restriction')
            if isinstance(arg, str):
                arg = '\'%s\'' % arg
            if 'add_multiple_lines' in context:
                # UFTP-15: parse 'available_for_restriction'
                # to implement it directly in product 'not_restricted' filter
                filter_domain = self._src_available_for_restriction(cr, uid,
                    self, 'available_for_restriction',
                    [('available_for_restriction','=', arg)],
                    context=context)
            else:
                filter_domain = "[('available_for_restriction','=',%s)]" % arg
            new_filter = """<filter string="Only not forbidden" name="not_restricted" icon="terp-accessories-archiver-minus" domain="%s" />""" % filter_domain
            #generate new xml form$
            new_form = etree.fromstring(new_filter)
            # instert new form just after state index position
            root.insert(state_index+1, new_form)
            root.insert(state_index+1, sep_form)
            # generate xml back to string
            res['arch'] = etree.tostring(root)

        return res

    def _test_restriction_error(self, cr, uid, ids, vals={}, context=None):
        '''
        Builds and returns an error message according to the constraints
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        error = False
        error_msg = ''
        constraints = []
        sale_obj = vals.get('obj_type') == 'sale.order'

        # Compute the constraint if a partner is passed in vals
        if vals.get('partner_id'):
            partner_obj = self.pool.get('res.partner')
            partner_type = partner_obj.browse(cr,
                                              uid,
                                              vals.get('partner_id'),
                                              context=context).partner_type
            if partner_type == 'external':
                constraints.append('external')
            elif partner_type == 'esc':
                constraints.append('esc')
            elif partner_type in ('internal', 'intermission', 'section'):
                constraints.append('internal')

        # Compute the constraint if a location is passed in vals
        if vals.get('location_id'):
            location = self.pool.get('stock.location').browse(cr, uid, vals.get('location_id'), context=context)
            bef_scrap_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
            if location.usage != 'inventory' and not location.destruction_location and (not bef_scrap_id or location.id != bef_scrap_id):
                constraints.append('storage')

        # Compute constraints if constraints is passed in vals
        if vals.get('constraints'):
            if isinstance(vals.get('constraints'), list):
                constraints.extend(vals.get('constraints'))
            elif isinstance(vals.get('constraints'), str):
                constraints.append(vals.get('constraints'))

        for product in self.browse(cr, uid, ids, context=context):
            msg = ''
            st_cond = True

            if product.no_external and product.no_esc and product.no_internal and 'picking' in constraints:
                error = True
                msg = _('be exchanged')
                st_cond = product.state.no_external or product.state.no_esc or product.state.no_internal
            elif product.no_external and 'external' in constraints:
                error = True
                msg = _('be %s externally') % (sale_obj and _('shipped') or _('purchased'))
                st_cond = product.state.no_external
            elif product.no_esc and 'esc' in constraints:
                error = True
                msg = _('be %s ESC') % (sale_obj and _('shipped to') or _('purchased at'))
                st_cond = product.state.no_esc
            elif product.no_internal and 'internal' in constraints:
                error = True
                msg = _('be supplied/exchanged internally')
                st_cond = product.state.no_internal
            elif product.no_consumption and 'consumption' in constraints:
                error = True
                msg = _('be consumed internally')
                st_cond = product.state.no_consumption
            elif product.no_storage and 'storage' in constraints:
                error = True
                msg = _('be stored anymore')
                st_cond = product.state.no_storage

            if error:
                # Build the error message
                st_type = st_cond and _('status') or _('product creator')
                st_name = st_cond and product.state.name or product.international_status.name

                error_msg = _('The product [%s] %s gets the %s \'%s\' and consequently can\'t %s') % (product.default_code,
                                                                                                      product.name,
                                                                                                      st_type,
                                                                                                      st_name,
                                                                                                      msg)
        if context.get('noraise'):
            error = False

        return error, error_msg

    def _get_restriction_error(self, cr, uid, ids, vals={}, context=None):
        '''
        Raise an error if the product is not compatible with the order
        '''
        res, error_msg = self._test_restriction_error(cr, uid, ids, vals=vals, context=context)

        if res:
            raise osv.except_osv(_('Error'), error_msg)
            return False

#    _constraints = [
#        (_check_uom_category, _('There are some stock moves with this product on the system. So you should keep the same UoM category than these stock moves.'), ['uom_id', 'uom_po_id']),
#    ]

    def _on_change_restriction_error(self, cr, uid, ids, *args, **kwargs):
        '''
        Update the message on on_change of product
        '''
        field_name = kwargs.get('field_name')
        values = kwargs.get('values')
        vals = kwargs.get('vals')
        context = kwargs.get('context')

        res, error_msg = self._test_restriction_error(cr, uid, ids, vals=vals, context=context)

        result = values.copy()

        if res:
            result.setdefault('value', {})[field_name] = False
            result.setdefault('warning', {})['title'] = _('Warning')
            result.setdefault('warning', {})['message'] = error_msg

        return result, res


    def onchange_heat(self, cr, uid, ids, heat, context=None):
        heat_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_1')[1]
        if not heat or heat == heat_id:
            return {'value': {'show_cold_chain':False}}
        return {'value': {'show_cold_chain':True}}

    def _check_gmdn_code(self, cr, uid, ids, context=None):
        int_pattern = re.compile(r'^\d*$')
        for product in self.browse(cr, uid, ids, context=context):
            if product.gmdn_code and not int_pattern.match(product.gmdn_code):
                return False
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if 'batch_management' in vals:
            vals['track_production'] = vals['batch_management']
            vals['track_incoming'] = vals['batch_management']
            vals['track_outgoing'] = vals['batch_management']
            if vals['batch_management']:
                vals['perishable'] = True
        if 'default_code' in vals:
            if vals['default_code'] == 'XXX':
                vals.update({'duplicate_ok': True})
            else:
                vals.update({'duplicate_ok': False})

        product_uom_categ = []
        if 'uom_id' in vals or 'uom_po_id' in vals:
            if isinstance(ids, (int, long)):
                to_browse = [ids]
            else:
                to_browse = ids
            for product in self.browse(cr, uid, to_browse, context=context):
                category_id = product.uom_id.category_id.id
                if category_id not in product_uom_categ:
                    product_uom_categ.append(category_id)

        res = super(product_attributes, self).write(cr, uid, ids, vals, context=context)

        if product_uom_categ:
            uom_categ = 'uom_id' in vals and vals['uom_id'] and self.pool.get('product.uom').browse(cr, uid, vals['uom_id'], context=context).category_id.id or False
            uos_categ = 'uom_po_id' in vals and vals['uom_po_id'] and self.pool.get('product.uom').browse(cr, uid, vals['uom_po_id'], context=context).category_id.id or False

            if (uom_categ and uom_categ not in product_uom_categ) or (uos_categ and uos_categ not in product_uom_categ):
                raise osv.except_osv(_('Error'), _('You cannot choose an UoM which is not in the same UoM category of default UoM'))

        return res

    def reactivate_product(self, cr, uid, ids, context=None):
        '''
        Re-activate product.
        '''
        for product in self.browse(cr, uid, ids, context=context):
            if product.active:
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already active.') % (product.default_code, product.name))

        self.write(cr, uid, ids, {'active': True}, context=context)

        return True

    def deactivate_product(self, cr, uid, ids, context=None):
        '''
        De-activate product.
        Check if the product is not used in any document in Unifield
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        location_obj = self.pool.get('stock.location')
        po_line_obj = self.pool.get('purchase.order.line')
        tender_line_obj = self.pool.get('tender.line')
        fo_line_obj = self.pool.get('sale.order.line')
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.item')
        inv_obj = self.pool.get('stock.inventory.line')
        in_inv_obj = self.pool.get('initial.stock.inventory.line')
        auto_supply_obj = self.pool.get('stock.warehouse.automatic.supply')
        auto_supply_line_obj = self.pool.get('stock.warehouse.automatic.supply.line')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        cycle_line_obj = self.pool.get('stock.warehouse.order.cycle.line')
        threshold_obj = self.pool.get('threshold.value')
        threshold_line_obj = self.pool.get('threshold.value.line')
        orderpoint_obj = self.pool.get('stock.warehouse.orderpoint')
        orderpoint_line_obj = self.pool.get('stock.warehouse.orderpoint.line')
        invoice_obj = self.pool.get('account.invoice.line')

        error_obj = self.pool.get('product.deactivation.error')
        error_line_obj = self.pool.get('product.deactivation.error.line')

        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)

        c = context.copy()
        c.update({'location_id': internal_loc})

        for product in self.browse(cr, uid, ids, context=context):
            # Raise an error if the product is already inactive
            if not product.active:
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already inactive.') % (product.default_code, product.name))

            # Check if the product is in some purchase order lines or request for quotation lines
            has_po_line = po_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                       ('order_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)

            # Check if the product is in some tender lines
            has_tender_line = tender_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                               ('tender_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)

            # Check if the product is in field order lines or in internal request lines
            context.update({'procurement_request': True})
            has_fo_line = fo_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                       ('order_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)

            # Check if the product is in stock picking
            # All stock moves in a stock.picking not draft/cancel/done or all stock moves in a shipment not delivered/done/cancel
            has_move_line = move_obj.search(cr, uid, [('product_id', '=', product.id),
                                                      ('picking_id', '!=', False),
                                                      '|', ('picking_id.state', 'not in', ['draft', 'done', 'cancel']),
                                                      '&', ('picking_id.shipment_id', '!=', False),
                                                      ('picking_id.shipment_id.state', 'not in', ['delivered', 'done', 'cancel']),
                                                      ], context=context)
#            has_move_line = move_obj.search(cr, uid, [('product_id', '=', product.id),
#                                                      ('picking_id', '!=', False),
#                                                      '|', '&', ('picking_id.state', 'not in', ['draft', 'done', 'cancel']),
#                                                      ('picking_id.shipment_id', '!=', False),
#                                                      ('picking_id.shipment_id.state', 'not in', ['delivered', 'done', 'cancel'])], context=context)

            # Check if the product is in a stock inventory
            has_inventory_line = inv_obj.search(cr, uid, [('product_id', '=', product.id),
                                                          ('inventory_id', '!=', False),
                                                          ('inventory_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)

            # Check if the product is in an initial stock inventory
            has_initial_inv_line = in_inv_obj.search(cr, uid, [('product_id', '=', product.id),
                                                          ('inventory_id', '!=', False),
                                                          ('inventory_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)

            # Check if the product is in a real kit composition
            has_kit = kit_obj.search(cr, uid, [('item_product_id', '=', product.id),
                                               ('item_kit_id.composition_type', '=', 'real'),
                                               ('item_kit_id.state', '=', 'completed'),
                                              ], context=context)
            has_kit2 = self.pool.get('composition.kit').search(cr, uid, [('composition_product_id', '=', product.id),
                                                                         ('composition_type', '=', 'real'),
                                                                         ('state', '=', 'completed')], context=context)
            has_kit.extend(has_kit2)

            # Check if the product is in an invoice
            has_invoice_line = invoice_obj.search(cr, uid, [('product_id', '=', product.id),
                                                            ('invoice_id', '!=', False),
                                                            ('invoice_id.state', 'not in', ['open', 'paid', 'proforma', 'proforma2', 'cancel'])], context=context)

            # Check if the product has stock in internal locations
            has_stock = product.qty_available

            opened_object = has_kit or has_initial_inv_line or has_inventory_line or has_move_line or has_fo_line or has_tender_line or has_po_line or has_invoice_line
            if has_stock or opened_object:
                # Create the error wizard
                wizard_id = error_obj.create(cr, uid, {'product_id': product.id,
                                                       'stock_exist': has_stock and True or False,
                                                       'opened_object': opened_object}, context=context)

                # Create lines for error in PO/RfQ
                po_ids = []
                for po_line in po_line_obj.browse(cr, uid, has_po_line, context=context):
                    if po_line.order_id.id not in po_ids:
                        po_ids.append(po_line.order_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': po_line.order_id.rfq_ok and 'Request for Quotation' or 'Purchase order',
                                                        'internal_type': 'purchase.order',
                                                        'doc_ref': po_line.order_id.name,
                                                        'doc_id': po_line.order_id.id}, context=context)

                # Create lines for error in Tender
                tender_ids = []
                for tender_line in tender_line_obj.browse(cr, uid, has_tender_line, context=context):
                    if tender_line.tender_id.id not in tender_ids:
                        tender_ids.append(tender_line.tender_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Tender',
                                                        'internal_type': 'tender',
                                                        'doc_ref': tender_line.tender_id.name,
                                                        'doc_id': tender_line.tender_id.id}, context=context)

                # Create lines for error in FO/IR
                fo_ids = []
                for fo_line in fo_line_obj.browse(cr, uid, has_fo_line, context=context):
                    if fo_line.order_id.id not in fo_ids:
                        fo_ids.append(fo_line.order_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': fo_line.order_id.procurement_request and 'Internal request' or 'Field order',
                                                        'internal_type': 'sale.order',
                                                        'doc_ref': fo_line.order_id.name,
                                                        'doc_id': fo_line.order_id.id}, context=context)

                # Create lines for error in picking
                pick_ids = []
                ship_ids = []
                pick_type = {'in': 'Incoming shipment',
                             'internal': 'Internal move',
                             'out': 'Delivery Order'}
                pick_subtype = {'standard': 'Delivery Order',
                                'picking': 'Picking Ticket',
                                'ppl': 'PPL',
                                'packing': 'Packing'}
                for move in move_obj.browse(cr, uid, has_move_line, context=context):
                    # Get the name of the stock.picking object
                    picking_type = pick_type.get(move.picking_id.type)
                    if move.picking_id.type == 'out':
                        picking_type = pick_subtype.get(move.picking_id.subtype)

                    # If the error picking is in a shipment, display the shipment instead of the picking
                    if move.picking_id.shipment_id and move.picking_id.id not in ship_ids:
                        ship_ids.append(move.picking_id.shipment_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Shipment',
                                                        'internal_type': 'shipment',
                                                        'doc_ref': move.picking_id.shipment_id.name,
                                                        'doc_id': move.picking_id.shipment_id.id}, context=context)

                    elif not move.picking_id.shipment_id and move.picking_id.id not in pick_ids:
                        pick_ids.append(move.picking_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': picking_type,
                                                        'internal_type': 'stock.picking',
                                                        'doc_ref': move.picking_id.name,
                                                        'doc_id': move.picking_id.id}, context=context)

                # Create lines for error in kit composition
                kit_ids = []
                for kit in kit_obj.browse(cr, uid, has_kit, context=context):
                    if kit.id not in kit_ids:
                        kit_ids.append(kit.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': kit.item_kit_id.composition_type == 'real' and 'Kit Composition' or 'Theorical Kit Composition',
                                                        'internal_type': 'composition.kit',
                                                        'doc_ref': kit.item_kit_id.composition_type == 'real' and kit.item_kit_id.composition_reference or kit.item_kit_id.name,
                                                        'doc_id': kit.item_kit_id.id}, context=context)

                # Create lines for error in inventory
                inv_ids = []
                for inv in inv_obj.browse(cr, uid, has_inventory_line, context=context):
                    if inv.inventory_id.id not in inv_ids:
                        inv_ids.append(inv.inventory_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Physical Inventory',
                                                        'internal_type': 'stock.inventory',
                                                        'doc_ref': inv.inventory_id.name,
                                                        'doc_id': inv.inventory_id.id}, context=context)

                # Create lines for error in inventory
                inv_ids = []
                for inv in in_inv_obj.browse(cr, uid, has_initial_inv_line, context=context):
                    if inv.inventory_id.id not in inv_ids:
                        inv_ids.append(inv.inventory_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Initial stock inventory',
                                                        'internal_type': 'initial.stock.inventory',
                                                        'doc_ref': inv.inventory_id.name,
                                                        'doc_id': inv.inventory_id.id}, context=context)

                # Create lines for error in invoices
                invoice_ids = []
                for invoice in invoice_obj.browse(cr, uid, has_invoice_line, context=context):
                    if invoice.invoice_id.id not in invoice_ids:
                        invoice_ids.append(invoice.invoice_id.id)
                        obj = invoice.invoice_id
                        type_name = 'Invoice'
                        # Customer Refund
                        if obj.type == 'out_refund':
                            type_name = 'Customer Refund'
                        # Supplier Refund
                        elif obj.type == 'in_refund':
                            type_name = 'Supplier Refund'
                        # Debit Note
                        elif obj.type == 'out_invoice' and obj.is_debit_note and not obj.is_inkind_donation:
                            type_name = 'Debit Note'
                        # Donation (in-kind donation)
                        elif obj.type == 'in_invoice' and not obj.is_debit_note and obj.is_inkind_donation:
                            type_name = 'In-kind Donation'
                        # Intermission voucher out
                        elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                            type_name = 'Intermission Voucher Out'
                        # Intermission voucher in
                        elif obj.type == 'in_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                            type_name = 'Intermission Voucher In'
                        # Stock Transfer Voucher
                        elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_inkind_donation:
                            type_name = 'Stock Transfer Voucher'
                        # Supplier Invoice
                        elif obj.type == 'in_invoice' and not obj.register_line_ids and not obj.is_debit_note and not obj.is_inkind_donation:
                            type_name = 'Supplier Invoice'
                        # Supplier Direct Invoice
                        elif obj.type == 'in_invoice' and obj.register_line_ids:
                            type_name = 'Supplier Direct Invoice'

                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': type_name,
                                                        'internal_type': 'account.invoice',
                                                        'doc_ref': invoice.invoice_id.number,
                                                        'doc_id': invoice.invoice_id.id}, context=context)

                return {'type': 'ir.actions.act_window',
                        'res_model': 'product.deactivation.error',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': wizard_id,
                        'target': 'new',
                        'context': context}

        # Remove the replenishment rules associated to this product
        # Automatic supply
        auto_line_ids = auto_supply_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for auto in auto_supply_line_obj.browse(cr, uid, auto_line_ids, context=context):
            if len(auto.supply_id.line_ids) == 1:
                auto_supply_obj.unlink(cr, uid, [auto.supply_id.id], context=context)
            else:
                auto_supply_line_obj.unlink(cr, uid, [auto.id], context=context)

        # Order cycle
        cycle_ids = cycle_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for cycle in cycle_line_obj.browse(cr, uid, cycle_ids, context=context):
            if len(cycle.order_cycle_id.product_line_ids) == 1:
                cycle_obj.unlink(cr, uid, [cycle.order_cycle_id.id], context=context)
            else:
                cycle_line_obj.unlink(cr, uid, [cycle.id], context=context)

        # Threshold value
        threshold_ids = threshold_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for threshold in threshold_line_obj.browse(cr, uid, threshold_ids, context=context):
            if len(threshold.threshold_value_id.line_ids) == 1:
                threshold_obj.unlink(cr, uid, [threshold.threshold_value_id.id], context=context)
            else:
                threshold_line_obj.unlink(cr, uid, [threshold.id], context=context)

        # Minimum stock rules
        orderpoint_line_ids = orderpoint_line_obj.search(cr, uid,
            [('product_id', 'in', ids)], context=context)
        for orderpoint_line in orderpoint_line_obj.browse(cr, uid,
            orderpoint_line_ids, context=context):
            if len(orderpoint_line.supply_id.line_ids) == 1:
                orderpoint_obj.unlink(cr, uid, [orderpoint_line.supply_id.id],
                    context=context)
            else:
                orderpoint_line_obj.unlink(cr, uid, [orderpoint_line.id],
                    context=context)

        self.write(cr, uid, ids, {'active': False}, context=context)

        return True

    def onchange_batch_management(self, cr, uid, ids, batch_management, context=None):
        '''
        batch management is modified -> modification of Expiry Date Mandatory (perishable)
        '''
        if batch_management:
            return {'value': {'perishable': True}}
        return {}

    def copy(self, cr, uid, id, default=None, context=None):
        product_xxx = self.search(cr, uid, [('default_code', '=', 'XXX')])
        if product_xxx:
            raise osv.except_osv(_('Warning'), _('A product with a code "XXX" already exists please edit this product to change its Code.'))
        product2copy = self.read(cr, uid, [id], ['default_code', 'name'])[0]
        if default is None:
            default = {}
        temp_status = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_5')[1]

        copy_pattern = _("%s (copy)")
        copydef = dict(name=(copy_pattern % product2copy['name']),
                       default_code="XXX",
                       # we set international_status to "temp" so that it won't be synchronized with this status
                       international_status=temp_status,
                       # we do not duplicate the o2m objects
                       asset_ids=False,
                       prodlot_ids=False,
                       attribute_ids=False,
                       packaging=False,
                       )
        copydef.update(default)
        return super(product_attributes, self).copy(cr, uid, id, copydef, context)

    def onchange_code(self, cr, uid, ids, default_code):
        '''
        Check if the code already exists
        '''
        res = {}
        if default_code:
            cr.execute("SELECT * FROM product_product pp where pp.default_code = '%s'" % default_code)
            duplicate = cr.fetchall()
            if duplicate:
                res.update({'warning': {'title': 'Warning', 'message':'The Code already exists'}})
        return res

    _constraints = [
        (_check_gmdn_code, 'Warning! GMDN code must be digits!', ['gmdn_code'])
    ]

product_attributes()


class product_template(osv.osv):
    _inherit = 'product.template'

    _columns = {
        'volume': fields.float('Volume', digits=(16,5), help="The volume in m3."),
        'weight': fields.float('Gross weight', digits=(16,5), help="The gross weight in Kg."),
        'weight_net': fields.float('Net weight', digits=(16,5), help="The net weight in Kg."),
    }

product_template()


class product_deactivation_error(osv.osv_memory):
    _name = 'product.deactivation.error'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True, readonly=True),
        'stock_exist': fields.boolean(string='Stocks exist (internal locations)', readonly=True),
        'opened_object': fields.boolean(string='Product is contain in opened documents', readonly=True),
        'error_lines': fields.one2many('product.deactivation.error.line', 'error_id', string='Error lines'),
    }

    _defaults = {
        'stock_exist': False,
        'opened_object': False,
    }

product_deactivation_error()

class product_deactivation_error_line(osv.osv_memory):
    _name = 'product.deactivation.error.line'

    _columns = {
        'error_id': fields.many2one('product.deactivation.error', string='Error', readonly=True),
        'type': fields.char(size=64, string='Documents type'),
        'internal_type': fields.char(size=64, string='Internal document type'),
        'doc_ref': fields.char(size=64, string='Reference'),
        'doc_id': fields.integer(string='Internal Reference'),
        'view_id': fields.integer(string='Reference of the view to open'),
    }

    def open_doc(self, cr, uid, ids, context=None):
        '''
        Open the associated documents
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            view_id, context = self._get_view(cr, uid, line, context=context)
            return {'type': 'ir.actions.act_window',
                    'name': line.type,
                    'res_model': line.internal_type,
                    'res_id': line.doc_id,
                    'view_mode': 'form,tree',
                    'view_type': 'form',
                    'target': 'current',
                    'view_id': view_id,
                    'nodestroy': True,
                    'context': context}

    def _get_view(self, cr, uid, line, context=None):
        '''
        Return the good view according to the type of the object
        '''
        if context is None:
            context = {}

        view_id = False
        data_obj = self.pool.get('ir.model.data')
        obj = self.pool.get(line.internal_type).browse(cr, uid, line.doc_id)

        if line.internal_type == 'composition.kit':
            context.update({'composition_type': 'theoretical'})
            if obj.composition_type == 'real':
                context.update({'composition_type': 'real'})
        elif line.internal_type == 'stock.picking':
            view_id = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, [line.doc_id], context=context, pick=obj)
        elif line.internal_type == 'sale.order':
            context.update({'procurement_request': obj.procurement_request})
        elif line.internal_type == 'purchase.order':
            context.update({'rfq_ok': obj.rfq_ok})
        elif line.internal_type == 'account.invoice':
            view_id = data_obj.get_object_reference(cr, uid, 'account', 'invoice_form')
            # Customer Refund
            if obj.type == 'out_refund':
                context.update({'type':'out_refund', 'journal_type': 'sale_refund'})
            # Supplier Refund
            elif obj.type == 'in_refund':
                context.update({'type':'in_refund', 'journal_type': 'purchase_refund'})
            # Debit Note
            elif obj.type == 'out_invoice' and obj.is_debit_note and not obj.is_inkind_donation:
                context.update({'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True})
            # Donation (in-kind donation)
            elif obj.type == 'in_invoice' and not obj.is_debit_note and obj.is_inkind_donation:
                context.update({'type':'in_invoice', 'journal_type': 'inkind'})
            # Intermission voucher out
            elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                view_id = data_obj.get_object_reference(cr, uid, 'account_override', 'view_intermission_form')
                context.update({'type':'out_invoice', 'journal_type': 'intermission'})
            # Intermission voucher in
            elif obj.type == 'in_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                view_id = data_obj.get_object_reference(cr, uid, 'account_override', 'view_intermission_form')
                context.update({'type':'in_invoice', 'journal_type': 'intermission'})
            # Stock Transfer Voucher
            elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_inkind_donation:
                context.update({'type':'out_invoice', 'journal_type': 'sale'})
            # Supplier Invoice
            elif obj.type == 'in_invoice' and not obj.register_line_ids and not obj.is_debit_note and not obj.is_inkind_donation:
                context.update({'type':'in_invoice', 'journal_type': 'purchase'})
            # Supplier Direct Invoice
            elif obj.type == 'in_invoice' and obj.register_line_ids:
                context.update({'type':'in_invoice', 'journal_type': 'purchase'})

        if view_id:
            view_id = [view_id[1]]

        return view_id, context

product_deactivation_error_line()


class pricelist_partnerinfo(osv.osv):
    _inherit = 'pricelist.partnerinfo'

    def onchange_uom_qty(self, cr, uid, ids, uom_id, min_quantity, min_order_qty):
        '''
        Check the rounding of the qty according to the rounding of the UoM
        '''
        res = {}

        if uom_id and min_quantity:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, min_quantity, 'min_quantity', res)

        if uom_id and min_order_qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, min_order_qty, 'min_order_qty', res)

        return res

pricelist_partnerinfo()


class product_uom(osv.osv):
    _inherit = 'product.uom'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True

        return res


    def _get_compatible_uom(self, cr, uid, obj, name, args, context=None):
        res = []

        for arg in args:
            if arg[0] == 'compatible_product_id':
                if not arg[2]:
                    return []
                elif isinstance(arg[2], (int, long)):
                    product = self.pool.get('product.product').browse(cr, uid, arg[2], context=context)
                    return [('category_id', '=', product.uom_id.category_id.id)]

        return res

    _columns = {
        'compatible_product_id': fields.function(_get_dummy, fnct_search=_get_compatible_uom, method=True, type='boolean', string='Compatible UoM'),
    }

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted product category is not a system one
        """
        data_obj = self.pool.get('ir.model.data')

        uom_data_id = [
            'uom_tbd',
            ]

        for data_id in uom_data_id:
            try:
                uom_id = data_obj.get_object_reference(
                    cr, uid, 'msf_doc_import', data_id)[1]
                if uom_id in ids:
                    uom_name = self.read(cr, uid, uom_id, ['name'])['name'] 
                    raise osv.except_osv(
                        _('Error'),
                        _('''The UoM '%s' is an Unifield internal
Uom, so you can't remove it''' % uom_name),
                    )
            except ValueError:
                pass

        return super(product_uom, self).unlink(cr, uid, ids, context=context)

product_uom()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
