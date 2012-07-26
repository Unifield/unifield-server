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

from osv import osv
from osv import fields

from tools.translate import _

class restrictive_country_setup(osv.osv_memory):
    _name = 'restrictive.country.setup'
    _inherit = 'res.config'
    
    _columns = {
        'restrict_country_ids': fields.many2many('res.country.restriction', 'wiz_restric_country', 'country_id', 'wizard_id', string='Country restriction'),
        'error_msg': fields.text(string='Error', readonly=True),
        'error': fields.boolean(string='Error'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for country restrictions
        '''
        res = super(restrictive_country_setup, self).default_get(cr, uid, fields, context=context)
        
        country_ids = self.pool.get('res.country.restriction').search(cr, uid, [], context=context)
        
        res['restrict_country_ids'] = country_ids
        res['error_msg'] = ''
        res['error'] = False
        
        return res
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        country_obj = self.pool.get('res.country.restriction')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        restriction_ids = self.pool.get('res.country.restriction').search(cr, uid, [], context=context)

        # Update all restrictive countries
        country_ids = []
        to_create = []
        to_delete = []
        for country in payload.restrict_country_ids:
            country_ids.append(country.id)
            if country.id not in restriction_ids:
                to_create.append(country)
                
        for restrict_id in restriction_ids:
            if restrict_id not in country_ids:
                to_delete.append(restrict_id)
            
        product_ids = self.pool.get('product.product').search(cr, uid, [('country_restriction', 'not in', country_ids)], order='country_restriction')
        error_msg = ''
        for p in self.pool.get('product.product').browse(cr, uid, product_ids):
            error_msg += '\n'
            error_msg += '%s : Already in use on product [%s] %s' % (p.country_restriction.name, p.default_code, p.name)
            if p.country_restriction.id in to_delete:
                to_delete.remove(p.country_restriction.id)
        
        # Create the new restrictions
        for rest in to_create:
            country_obj.create(cr, uid, {'name': rest.name}, context=context)
        
        # Delete the old restrictions
        country_obj.unlink(cr, uid, to_delete, context=context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'unifield_setup', 'view_restrictive_countries_setup')[1]
        
        if error_msg:
            self.write(cr, uid, ids, {'error_msg': error_msg, 'error': True})
            return {'type': 'ir.actions.act_window',
                    'res_model': 'restrictive.country.setup',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': payload.id,
                    'view_id': [view_id],
                    'context': {'product_ids': product_ids, 'error': True}}
            
    def go_to_products(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        country_ids = []
        for country in payload.restrict_country_ids:
            country_ids.append(country.id)
            
        product_ids = self.pool.get('product.product').search(cr, uid, [('country_restriction', 'not in', country_ids)], order='country_restriction')
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product', 'product_normal_form_view')[1]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'domain': [('id', 'in', product_ids)],
                'nodestroy': True}
        
restrictive_country_setup()
