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

import logging
import tools
from os import path


# Class to save all configuration value
class unifield_setup_configuration(osv.osv):
    _name = 'unifield.setup.configuration'
    
    def init(self, cr):
        """
        Load setup_data.xml before self
        """
        if hasattr(super(unifield_setup_configuration, self), 'init'):
            super(unifield_setup_configuration, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module unifield_setup: loading setup_data.xml')
        pathname = path.join('unifield_setup', 'setup_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'unifield_setup', file, {}, mode='init', noupdate=False)
    
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
        'unallocated_ok': fields.boolean(string='System uses the unallocated stocks ?'),
        'fixed_asset_ok': fields.boolean(string='System manages fixed asset ?'),
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
        'unallocated_ok': lambda *a: False,
        'fixed_asset_ok': lambda *a: False,
    }
    
    _constraints = [
        (_check_uniqueness, _non_uniqueness_msg, ['id'])
    ]
    
    def get_config(self, cr, uid):
        '''
        Return the current config or create a new one
        '''
        setup_ids = self.search(cr, uid, [])
        if not setup_ids:
            setup_id = self.create(cr, uid, {})
        else:
            setup_id = setup_ids[0]
            
        return self.browse(cr, uid, setup_id)
    
unifield_setup_configuration()

class res_config_view(osv.osv_memory):
    _name = 'res.config.view'
    _inherit = 'res.config.view'

    _defaults={
        'view': 'extended',
    }

res_config_view()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: