# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO consulting, MSF
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


# Class to save all configuration value
class unifield_setup_configuration(osv.osv):
    _name = 'unifield.setup.configuration'
    
    def _check_uniqueness(self, cr, uid, ids, context=None):
        '''
        Limit the creation of one and only one instance configuration
        '''
        setup_ids = self.pool.get('unifield.setup.configuration').search(cr, uid, [], context=context)
        if len(setup_ids) > 1:
            return False
        
        return True
    
    def _non_uniqueness_msg(self, cr, uid, ids, context=None):
        return _('An instance of Unifield setup is already running.')
    
    _columns = {
        'name': fields.char(size=64, string='Name'),
        'delivery_process': fields.selection([('simple', 'Simple OUT'), ('complex', 'PICK/PACK/SHIP')], string='Delivery process'),
        'allocation_setup': fields.selection([('allocated', 'Allocated'),
                                              ('unallocated', 'Unallocated'),
                                              ('mixed', 'Mixed')], string='Allocated stocks'),
        'sale_price': fields.float(digits=(16,2), string='Fields price percentage',
                                   help='This percentage will be applied on field price from product form view.'),
        'restrict_country_ids': fields.many2many('res.country', 'restrictive_countries', 'wizard_id', 'country_id', 
                                                 string='Restrictive countries'),
        'field_orders_ok': fields.boolean(string='Activate the Field Orders feature ?'),
        'lang_id': fields.char(size=5, string='Default language'),
    }
    
    _defaults = {
        'name': lambda *a: 'Unifield setup',
        'delivery_process': lambda *a: 'complex',
        'allocation_setup': lambda *a: 'allocated',
        'sale_price': lambda *a: 0.00,
        'field_orders_ok': lambda *a: True,
        'lang_id': lambda *a: 'en_MF',
    }
    
    _constraints = [
        (_check_uniqueness, _non_uniqueness_msg, ['id'])
    ]
    
unifield_setup_configuration()

class res_config_view(osv.osv_memory):
    _name = 'res.config.view'
    _inherit = 'res.config.view'

    _defaults={
        'view': lambda *a: 'extended',
    }

res_config_view()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: