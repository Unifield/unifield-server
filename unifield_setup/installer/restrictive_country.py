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
        'restrict_country_ids': fields.many2many('res.country', 'restrictive_countries', 'wizard_id', 'country_id', 
                                                 string='Restrictive countries'),
    }
    
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for sale price
        '''
        res = super(restrictive_country_setup, self).default_get(cr, uid, fields, context=context)
        
        country_ids = self.pool.get('res.country').search(cr, uid, [('is_restrictive', '=', True)], context=context)
        
        res['restrict_country_ids'] = country_ids
        
        return res
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        country_obj = self.pool.get('res.country')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        # Update all restrictive countries
        country_ids = []
        for country in payload.restrict_country_ids:
            country_ids.append(country.id)
            
        product_ids = self.pool.get('product.product').search(cr, uid, [('restricted_country', '=', True), ('country_restriction', 'not in', country_ids)])
        if product_ids:
            raise osv.except_osv(_('Error'), _('You cannot change the restrictive countries because one or more products have a restriction on a country which is not in the new selection.'))
        
        all_countries_ids = country_obj.search(cr, uid, [('is_restrictive', '=', True)], context=context)
        country_obj.write(cr, uid, all_countries_ids, {'is_restrictive': False}, context=context)
        
        country_obj.write(cr, uid, country_ids, {'is_restrictive': True}, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'restrict_country_ids': [(6,0,country_ids)]}, context=context)
        
restrictive_country_setup()