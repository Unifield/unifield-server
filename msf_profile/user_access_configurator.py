# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import osv, fields
from tools.translate import _
import base64
from os.path import join as opj
import tools


class user_access_configurator(osv.osv_memory):
    _name = 'user.access.configurator'
    _columns = {'file_to_import': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Initial Average Cost, Location*, Batch, Expiry Date, Quantity')}
    
    def import_data_uacc(self, cr, uid, ids, context=None):
        '''
        import data and generate data structure
        
        {
        'group_list': [group_names],
        'menus_groups': {'menu_name': [group_names]} - we only take the group_name into account if True
        }
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # data structure returned with processed data from file
            
        return False
    
    def process_groups_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        return False
    
    def process_users_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        return False
    
    def process_menus_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        return False
    
    def process_objects_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        return False
    
    def process_record_rules_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        return False
    
    def do_process_uac(self, cr, uid, ids, context=None):
        '''
        main function called from wizard
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        return False

user_access_configurator()

