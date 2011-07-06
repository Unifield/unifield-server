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

class product_section_code(osv.osv):
    _name = "product.section.code"
    _columns = {
        'code': fields.char('Code', size=4),
        'section': fields.char('Section', size=32),
        'description': fields.char('Description', size=128),
    }
product_section_code()

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
        'type': fields.selection([('product','Stockable Product'),('consu', 'Non-Stockable'),('service','Service')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
    }
    
    _defaults = {
        'type': 'product',
    }
    
product_attributes_template()

class product_attributes(osv.osv):
    _inherit = "product.product"
    
    _columns = {
        'loc_indic': fields.char('Indicative Location', size=64),
        'description2': fields.text('Description 2'),
        'old_code' : fields.char('Old code', size=64),
        'international_status': fields.selection([('',''),('itc','Approved (ITC)'),('esc', 'Approved (ESC)'),('temp','Temporary'),('local','Not approved (Local)')], 'International Status'),
        'state': fields.selection([('',''),
            ('draft','Introduction'),
            ('sellable','Normal'),
            ('transfer','Transfer'),
            ('end_alternative','End of Life (alternative available)'),
            ('end','End of Life (not supplied anymore)'),
            ('obsolete','Warning list')], 'Status', help="Tells the user if he can use the product or not."),
        'perishable': fields.boolean('Perishable'),
        'batch_management': fields.boolean('Batch Management'),
        'product_catalog_page' : fields.char('Product Catalog Page', size=64),
        'product_catalog_path' : fields.char('Product Catalog Path', size=64),
        'short_shelf_life': fields.boolean('Short Shelf Life'),
        'criticism': fields.selection([('',''),
            ('exceptional','1-Expectional'),
            ('specific','2-Specific'),
            ('important','3-Important'),
            ('medium','4-Medium'),
            ('common','5-Common'),
            ('other','X-Other')], 'Criticism'),
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
        'heat_sensitive_item': fields.selection([('',''),
            ('_','Keep refrigerated but not cold chain (+2 to +8°C) for transport'),
            ('*','* Keep Cool'),
            ('**','** Keep Cool, airfreight'),
            ('***','*** Cold chain, 0° to 8°C strict')], 'Heat-sensitive item'),
        'cold_chain': fields.selection([('',''),
            ('*0','*0 Problem if any window blue'),
            ('*0F','*0F Problem if any window blue or F'),
            ('*A','*A Problem if A and D totally blue'),
            ('*AF','*AF Problem if A and D totally blue or F'),
            ('*B','*B Problem if B and D totally blue'),
            ('*BF','*BF Problem if B and D totally blue or F'),
            ('*C','*C Problem if C and D totally blue'),
            ('*CF','*CF Problem if C and D totally blue or F'),
            ('*F','*F CANNOT be frozen; check FreezeWatch')], 'Cold Chain'),
        'sterilized': fields.boolean('Sterilized'),
        'single_use': fields.boolean('Single Use'),
        'justification_code_id': fields.many2one('product.justification.code', 'Justification Code'),
        'med_device_class': fields.selection([('',''),
            ('I','Class I (General controls)'),
            ('II','Class II (General control with special controls)'),
            ('III','Class III (General controls and premarket)')], 'Medical Device Class'),
        'closed_article': fields.boolean('Closed Article'),
        'dangerous_goods': fields.boolean('Dangerous Goods'),
        'gmdn_code' : fields.char('GMDN Code', size=5),
        'gmdn_description' : fields.char('GMDN Description', size=64),
        'life_time': fields.integer('Product Life Time',
            help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
            help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
            help='The number of months before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of months after which an alert should be notified about the production lot.")
    }
    
    _defaults = {
        'perishable': False,
        'batch_management': False,
        'short_shelf_life': False,
        'composed_kit': False,
        'sterilized': False,
        'single_use': False,
        'closed_article': False,
        'dangerous_goods': False,
    }
    
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
        return super(product_attributes, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'batch_management' in vals:
            vals['track_production'] = vals['batch_management']
            vals['track_incoming'] = vals['batch_management']
            vals['track_outgoing'] = vals['batch_management']
        return super(product_attributes, self).write(cr, uid, ids, vals, context=context)
    
    _constraints = [
        (_check_gmdn_code, 'Warning! GMDN code must be digits!', ['gmdn_code'])
    ]

product_attributes()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
