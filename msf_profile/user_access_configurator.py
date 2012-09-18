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

from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from msf_supply_doc_import.check_line import *

MAX_LINES_NB = 5000


class user_access_configurator(osv.osv_memory):
    _name = 'user.access.configurator'
    _columns = {'file_to_import_uac': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Initial Average Cost, Location*, Batch, Expiry Date, Quantity'),
                'number_of_non_group_columns_uac': fields.integer(string='Number of columns not containing group name')}
    _defaults = {#'file_to_import_uac': '/home/chloups208/Dropbox/patrick/unifield/wm/uf1334/merged.xml',
                 'number_of_non_group_columns_uac': 4}
    
    def _row_is_empty(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        return True if row is empty
        """
        row = kwargs['row']
        return all([not cell.data for cell in row.cells])
    
    def _cell_is_true(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        return True if row is empty
        """
        cell = kwargs['cell']
        if cell.data and cell.data.upper() == 'YES':
            return True
        return False
    
    def import_data_uac(self, cr, uid, ids, context=None):
        '''
        import data and generate data structure
        
        {id: {
              'group_name_list': [group_names],
              'menus_groups': {'menu_id': [group_names]}, - we only take the group_name into account if True
              'errors': ['list of errors'],
              'warnings': ['list of warnings'],
              }
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # data structure returned with processed data from file
        data_structure = {}
        
        for obj in self.browse(cr, uid, ids, context=context):
            # data structure returned with processed data from file
            data_structure.update({obj.id: {'group_name_list': [],
                                            'menus_groups': {},
                                            'errors': [],
                                            'warnings': []}})
            # file to process
            file = obj.file_to_import_uac
            # file is mandatory for import process
            if not file:
                raise osv.except_osv(_('Warning'), _('No File Selected.'))
            # load the selected file according to XML OUTPUT
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file))
            # iterator on rows
            rows = fileobj.getRows()
            # first row flag
            first_row = True
            # loop the rows for groups-menus relation
            for row in rows:
                # skip empty lines
                if self._row_is_empty(cr, uid, ids, context=context, row=row):
                    continue
                
                # first row, gather group names
                if first_row:
                    first_row = False
                    # skip information rows
                    for i in range(obj.number_of_non_group_columns_uac, len(row)):
                        data_structure[obj.id]['group_name_list'].append(row.cells[i].data)
                else:
                    # information rows
                    try:
                        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, row.cells[0], row.cells[1])[1]
                    except ValueError:
                        # menu is in the file but not in the database
                        data_structure[obj.id]['errors'].append('The menu %s (%s.%s) is missing in the database.'%(row.cells[3], row.cells[0], row.cells[1]))
                        continue
                        
                    # skip information rows - find related groups
                    for i in range(obj.number_of_non_group_columns_uac, len(row)):
                        # group is true for this menu
                        if self._cell_is_true(cr, uid, ids, context=context, cell=row.cells[i]):
                            # name of group
                            group_name = data_structure[obj.id]['group_name_list'][i - obj.number_of_non_group_columns_uac]
                            data_structure[obj.id]['menus_groups'].setdefault(menu_id, []).append(group_name)
                    
        return data_structure
    
    def process_groups_uac(self, cr, uid, ids, context=None):
        '''
        
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # data structure
        data_structure = context['data_structure']
        # load the groups from file if not present
        for group in data_structure[obj.id]['group_name_list']:
            
        
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
        
        # gather data structure corresponding to selected file
        data_structure = self.import_data_uac(cr, uid, ids, context=context)
        # process the groups
        self.process_groups_uac(cr, uid, ids, context=dict(context, data_structure=data_structure)
        
        return {'type': 'ir.actions.act_window_close'}

user_access_configurator()


class res_groups(osv.osv):
    '''
    add an active column
    '''
    _inherit = 'res.groups'
    _columns = {'active': fields.boolean('Active', readonly=True)}
    _defaults = {'active': True}

res_groups()

