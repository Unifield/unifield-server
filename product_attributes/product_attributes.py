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
        'code': fields.char('Section code', size=4),
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

class product_attributes(osv.osv):
    _inherit = "product.product"
    
    _columns = {
        'type': fields.selection([('product','Stockable Product'),('consu', 'Non-Stockable Consumable'),('service','Service')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
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
            ('1','1-Expectional'),
            ('2','2-Specific'),
            ('3','3-Important'),
            ('4','4-Medium'),
            ('5','5-Common'),
            ('x','X-Other')], 'Criticism'),
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
        'order_list': fields.boolean('Order List'),
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
            ('1','Class I (General controls)'),
            ('2','Class II (General control with special controls)'),
            ('3','Class III (General controls and premarket)')], 'Cold Chain'),
        'closed_article': fields.boolean('Closed Article'),
        'dangerous_goods': fields.boolean('Dangerous Goods'),
        'gmdn_code' : fields.char('GMDN Code', size=5),
        'gmdn_description' : fields.char('GMDN Description', size=64),
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
    
    _constraints = [
        (_check_gmdn_code, 'Warning! GMDN code must be digits!', ['gmdn_code'])
    ]

product_attributes()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
