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
import logging
import re
import tools
from os import path

class product_section_code(osv.osv):
    _name = "product.section.code"
    _columns = {
        'code': fields.char('Code', size=4),
        'section': fields.char('Section', size=32),
        'description': fields.char('Description', size=128),
    }
product_section_code()


class product_status(osv.osv):
    _name = "product.status"
    _columns = {
        'name': fields.char('Name', size=256),
    }
product_status()


class product_international_status(osv.osv):
    _name = "product.international.status"
    _columns = {
        'name': fields.char('Name', size=256),
    }
product_international_status()

class product_heat_sensitive(osv.osv):
    _name = "product.heat_sensitive"
    _columns = {
        'name': fields.char('Name', size=256),
    }
product_heat_sensitive()

class product_cold_chain(osv.osv):
    _name = "product.cold_chain"
    _columns = {
        'name': fields.char('Name', size=256),
    }
product_cold_chain()

class product_supply_source(osv.osv):
    _name = "product.supply.source"
    _columns = {
        'source': fields.char('Supply source', size=32),
    }
product_supply_source()


class product_justification_code(osv.osv):
    _name = "product.justification.code"
    _columns = {
        'code': fields.char('Justification Code', size=32),
        'description': fields.char('Justification Description', size=256),
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


class product_attributes(osv.osv):
    _inherit = "product.product"

    def init(self, cr):
        if hasattr(super(product_attributes, self), 'init'):
            super(product_attributes, self).init(cr)
        logging.getLogger('init').info('HOOK: module product_attributes: loading product_attributes_data.xml')
        pathname = path.join('product_attributes', 'product_attributes_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'product_attributes', file, {}, mode='init', noupdate=False)
    
    def _get_nomen(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []
            res[product.id].append(product.nomen_manda_0.id)
            res[product.id].append(product.nomen_manda_1.id)
            res[product.id].append(product.nomen_manda_2.id)
            res[product.id].append(product.nomen_manda_3.id)
            res[product.id].append(product.nomen_sub_0.id)
            res[product.id].append(product.nomen_sub_1.id)
            res[product.id].append(product.nomen_sub_2.id)
            res[product.id].append(product.nomen_sub_3.id)
            res[product.id].append(product.nomen_sub_4.id)
            res[product.id].append(product.nomen_sub_5.id)
            
        return res
    
    def _search_nomen(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        if not context:
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
    
    _columns = {
        'duplicate_ok': fields.boolean('Is a duplicate'),
        'loc_indic': fields.char('Indicative Location', size=64),
        'description2': fields.text('Description 2'),
        'old_code' : fields.char('Old code', size=64),
        'new_code' : fields.char('New code', size=64),

        'international_status': fields.many2one('product.international.status', 'Product Creator', required=True),
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
    }
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(product_attributes, self).default_get(cr, uid, fields, context=context)
        id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1') and self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1')[1] or 1
        res.update({'international_status': id })
        return res

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
    }

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
    
    def create(self, cr, uid, vals, context=None):
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
        return super(product_attributes, self).create(cr, uid, vals, context=context)
    
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
        return super(product_attributes, self).write(cr, uid, ids, vals, context=context)
    
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
        copy_pattern = _("%s (copy)")
        copydef = dict(name=(copy_pattern % product2copy['name']),
                       default_code="XXX",
                       # we set international_status to "temp" so that it won't be synchronized with this status
                       international_status='temp',
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
        'state': fields.many2one('product.status', 'Status', help="Tells the user if he can use the product or not."),
    }

product_template()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
