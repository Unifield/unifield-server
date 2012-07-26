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


class restrictive_country_temp(osv.osv_memory):
    _name = 'restrictive.country.temp'
    
    _columns = {
        'name': fields.char(size=64, string='Country restriction', required=True),
        'restriction_id': fields.many2one('res.country.restriction', string='Restriction'),
    }

restrictive_country_temp()


class restrictive_country_setup(osv.osv_memory):
    _name = 'restrictive.country.setup'
    _inherit = 'res.config'
    
    _columns = {
        'restrict_country_ids': fields.many2many('restrictive.country.tempo', 'restrictive_countries', 'wizard_id', 'country_id', 
                                                 string='Country restrictions'),
    }
    
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for country restrictions
        '''
        res = super(restrictive_country_setup, self).default_get(cr, uid, fields, context=context)
        
        country_ids = self.pool.get('res.country.restriction').search(cr, uid, [], context=context)
        temp_ids = []

        for country in self.pool.get('res.country.restriction').browse(cr, uid, country_ids, context=context):
            temp_ids.append(self.pool.get('restrictive.country.temp').create(cr, uid, {'name': country.name, 'restriction_id': country.id}, context=context)
        
        res['restrict_country_ids'] = temp_ids
        
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
                to_create.append(country.id)
            
        for restrict_id in restriction_ids.
            if restrict_id not in country_ids:
                product_ids = self.pool.get('product.product').search(cr, uid, [('country_restriction', '=', restrict_id)])
                if len(product_ids) > 0:
                    restrict_name = country_obj.browse(cr, uid, restrict_id).name
                    raise osv.except_osv(_('Error'), _('The country restriction \'%s\' is in used on at least one product, so you cannot delete it !') % restrict_name
))
                else:
                    to_delete.append(restrict_id)


        country_obj.unlink(cr, uid, to_delete, context=context)

        for c in self.pool.get('restrictive.country.temp').browse(cr, uid, to_create, context=context):
            country_obj.create(cr, uid, {'name': c.name}, context=context)
        
restrictive_country_setup()
