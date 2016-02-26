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


class ir_actions_todo(osv.osv):
    _name = 'ir.actions.todo'
    _inherit = 'ir.actions.todo'

    def action_launch(self, cr, uid, ids, context=None):
        """ Launch Action of Wizard"""
        res = super(ir_actions_todo, self).action_launch(cr, uid, ids, context=context)
        if res.get('res_model') == 'restrictive.country.setup':
            res_id = self.pool.get('restrictive.country.setup').create(cr, uid, {})
            c = context.copy()
            c.update({'active_id': res_id})
            res.update({'res_id': res_id, 'context': c})
        return res
    
ir_actions_todo()

class restrictive_country_setup(osv.osv_memory):
    _name = 'restrictive.country.setup'
    _inherit = 'res.config'
    
    _columns = {
        'restrict_country_ids': fields.one2many('res.country.restriction.memory', 'wizard_id', string='Country restriction'),
        'error_msg': fields.text(string='Error', readonly=True),
        'error': fields.boolean(string='Error'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for country restrictions
        '''
        if not context:
            context = {}
        
        res = super(restrictive_country_setup, self).default_get(cr, uid, fields, context=context)

        res['restrict_country_ids'] = []
        
        country_ids = self.pool.get('res.country.restriction').search(cr, uid, [], context=context)
        for country in self.pool.get('res.country.restriction').browse(cr, uid, country_ids, context=context):
            res['restrict_country_ids'].append({'name': country.name, 'restrict_id': country.id})

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
        to_delete = []
        for country in payload.restrict_country_ids:
            if not country.restrict_id or (country.restrict_id and country.restrict_id.id not in restriction_ids):
                self.pool.get('res.country.restriction').create(cr, uid, {'name': country.name}, context=context)
            else:
                country_ids.append(country.restrict_id.id)
                
        for restrict_id in restriction_ids:
            if restrict_id not in country_ids:
                to_delete.append(restrict_id)
                
        self.pool.get('res.country.restriction').unlink(cr, uid, to_delete, context=context)
            
            
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

class res_country_restriction_memory(osv.osv_memory):
    _name = 'res.country.restriction.memory'
    
    _columns = {
        'name': fields.char(size=64, string='Name'),
        'restrict_id': fields.many2one('res.country.restriction', string='Restriction'),
        'wizard_id': fields.many2one('restrictive.country.setup', string='Wizard'),
    }
    
    def unlink(self, cr, uid, ids, context=None):
        for restrict in self.browse(cr, uid, ids, context=context):
            for product in restrict.restrict_id.product_ids:
                # Raise an error only if the restriction box is checked
                if product.restricted_country:
                    raise osv.except_osv(_('Error'), _('You cannot remove this restriction because it is in use in product(s)'))
            
        return super(res_country_restriction_memory, self).unlink(cr, uid, ids, context=context)
    
res_country_restriction_memory()
