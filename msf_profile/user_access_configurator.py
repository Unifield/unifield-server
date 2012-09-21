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


class user_access_configurator(osv.osv_memory):
    _name = 'user.access.configurator'
    _columns = {'file_to_import_uac': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Initial Average Cost, Location*, Batch, Expiry Date, Quantity'),
                'number_of_non_group_columns_uac': fields.integer(string='Number of columns not containing group name')}
    _defaults = {'number_of_non_group_columns_uac': 4}
    
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
    
    def _get_ids_from_group_names(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return ids corresponding to group names
        '''
        # objects
        group_obj = self.pool.get('res.groups')
        # group names
        group_names = kwargs['group_names']
        if not isinstance(group_names, list):
            group_names = [group_names]
        
        group_ids = group_obj.search(cr, uid, [('name', 'in', group_names)], context=context)
        return group_ids
    
    def _get_admin_user_rights_group_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return admin_user_rights_group
        '''
        admin_user_rights_group = 'Administration / Access Rights'
        return admin_user_rights_group
    
    def _get_admin_user_rights_group_id(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return admin_user_rights_group id
        '''
        admin_group_name = self._get_admin_user_rights_group_name(cr, uid, ids, context=context)
        admin_group_ids = self._get_ids_from_group_names(cr, uid, ids, context=context, group_names=[admin_group_name])
        return admin_group_ids[0]
    
    def _get_DNCGL_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return do not change groups
        '''
        group_immunity_list = [u'Useability / No One', u'Useability / Multi Companies']
        return group_immunity_list
    
    def _get_DNCGL_ids(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return do not change groups ids
        '''
        group_names = self._get_DNCGL_name(cr, uid, ids, context=context)
        return self._get_ids_from_group_names(cr, uid, ids, context=context, group_names=group_names)
    
    def _get_IGL_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return immunity groups
        '''
        group_immunity_list = [u'Administration / Access Rights', u'Useability / No One']
        return group_immunity_list
    
    def _group_name_is_immunity(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return True if group_name is immune
        '''
        group_immunity_list = self._get_IGL_name(cr, uid, ids, context=context)
        group_name = kwargs['group_name']
        return group_name in group_immunity_list
        
    def _remove_group_immune(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        clear groups of immune groups
        '''
        group_names = kwargs['group_names']
        return [group_name for group_name in group_names if not self._group_name_is_immunity(cr, uid, ids, context=context, group_name=group_name)]
    
    def _import_data_uac(self, cr, uid, ids, context=None):
        '''
        import data and generate data structure
        
        {id: {
              'group_name_list': [group_names],
              'menus_groups': {'menu_id': [group_names]}, - we only take the group_name into account if True - if the same group is defined multiple times, it will be deleted at the end of import function
              'groups_info': {'activated': [group_names], 'deactivated': [group_names], 'created': [group_names], 'warnings': [], 'errors': []},
              'users_info': {'activated': [user_names], 'deactivated': [user_names], 'created': [user_names], 'updated': [(old_name, new_name)] 'warnings': [], 'errors': []},
              'menus_info': {'warnings': [], 'errors': []},
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
                                            'groups_info': {'activated': [], 'deactivated': [], 'created': [], 'warnings': [], 'errors': []},
                                            'users_info': {'activated': [], 'deactivated': [], 'created': [], 'warnings': [], 'errors': []},
                                            'menus_info': {'warnings': [], 'errors': []},
                                            }})
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
                        group_name = False
                        # if no name of the group, create a new group No Name
                        if not row.cells[i].data:
                            group_name = 'No Name'
                        else:
                            group_name = row.cells[i].data
                        # if the same group is defined multiple times
                        if group_name in data_structure[obj.id]['group_name_list']:
                            # display a warning, the same group is displayed multiple times, columns values are aggregated (OR)
                            data_structure[obj.id]['groups_info']['warnings'].append('The group %s is defined multiple times. Values from all these groups are aggregated (OR function).'%group_name)
                        # we add the column, even if defined multiple times, as we need it for name matching when setting menu rights
                        data_structure[obj.id]['group_name_list'].append(row.cells[i].data)
                else:
                    # information rows
                    try:
                        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, row.cells[0], row.cells[1])[1]
                    except ValueError:
                        # menu is in the file but not in the database
                        data_structure[obj.id]['menus_info']['errors'].append('The menu %s (%s.%s) is defined in the file but is missing in the database.'%(row.cells[3], row.cells[0], row.cells[1]))
                        continue
                    
                    # test if a menu is defined multiple times
                    if menu_id in data_structure[obj.id]['menus_groups']:
                        data_structure[obj.id]['menus_info']['warnings'].append('The menu %s (%s.%s) is defined multiple times. Groups from all these rows are aggregated (OR function).'%(row.cells[3], row.cells[0], row.cells[1]))
                    
                    # skip information rows - find related groups
                    for i in range(obj.number_of_non_group_columns_uac, len(row)):
                        # group is true for this menu
                        if self._cell_is_true(cr, uid, ids, context=context, cell=row.cells[i]):
                            # name of group
                            group_name = data_structure[obj.id]['group_name_list'][i - obj.number_of_non_group_columns_uac]
                            menu_group_list = data_structure[obj.id]['menus_groups'].setdefault(menu_id, [])
                            # if the column is defined multiple times, we only add one time the name, but the access selection is aggregated from all related columns
                            if group_name not in menu_group_list:
                                menu_group_list.append(group_name)
            
            # all rows have been treated, the order of group_name_list is not important anymore, we can now exclude groups which are defined multiple times
            data_structure[obj.id]['group_name_list'] = list(set(data_structure[obj.id]['group_name_list']))
                    
        return data_structure
    
    def _activate_immunity_groups(self, cr, uid, ids, context=None):
        '''
        activate immunity groups
        
        return immunity group
        '''
        # objects
        group_obj = self.pool.get('res.groups')
        
        group_immunity_name_list = self._get_IGL_name(cr, uid, ids, context=context)
        return self._activate_group_name(cr, uid, ids, context=context, group_names=group_immunity_name_list)
    
    def _activate_group_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        activate groups names
        
        return activated groups names
        '''
        # objects
        group_obj = self.pool.get('res.groups')
        
        group_names = kwargs['group_names']
        activate_ids = self._get_ids_from_group_names(cr, uid, ids, context=context, group_names=group_names)
        group_obj.write(cr, uid, activate_ids, {'active': True}, context=context)
        return group_names
    
    def _process_groups_uac(self, cr, uid, ids, context=None):
        '''
        create / active / deactivate groups according to policy defined in the file
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        group_obj = self.pool.get('res.groups')
        # data structure
        data_structure = context['data_structure']
        # load all groups from database
        group_ids = group_obj.search(cr, uid, [], context=context)
        group_names = group_obj.read(cr, uid, group_ids, ['name'], context=context)
        group_names = [x['name'] for x in group_names]
        
        # IGL groups are activated
        self._activate_immunity_groups(cr, uid, ids, context=context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            # work copy of groups present in the file - will represent the missing groups to be created
            missing_group_names = list(data_structure[obj.id]['group_name_list'])
            # all groups from file are activated (in case a new group in the file which was deactivated previously)
            self._activate_group_name(cr, uid, ids, context=context, group_names=missing_group_names)
            # will represent the groups present in the database but not in the file, to be deactivated
            deactivate_group_names = []
            # loop through groups in the database - pop from file list if already exist
            for group_name in group_names:
                if group_name in missing_group_names:
                    # the group from file already exists
                    missing_group_names.remove(group_name)
                elif not self._group_name_is_immunity(cr, uid, ids, context=context, group_name=group_name):
                    # the group from database is not immune and not in the file
                    deactivate_group_names.append(group_name)
            
            # create the new groups from the file
            for missing_group_name in missing_group_names:
                new_group_id = group_obj.create(cr, uid, {'name': missing_group_name, 'from_file_import_res_groups': True}, context=context)
            # deactivate the groups not present in the file
            deactivate_ids = group_obj.search(cr, uid, [('name', 'in', deactivate_group_names)], context=context)
            assert len(deactivate_ids) == len(deactivate_group_names), 'this line should be impossible to reach - some groups to deactivate where not found'
            group_obj.write(cr, uid, deactivate_ids, {'active': False}, context=context)
        
        return True
    
    def _activate_user_ids(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        activate user ids
        
        return activated user ids
        '''
        # objects
        user_obj = self.pool.get('res.users')
        
        user_ids = kwargs['user_ids']
        user_obj.write(cr, uid, user_ids, {'active': True}, context=context)
        return user_ids
    
    def _deactivate_user_ids(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        activate user ids
        
        return activated user ids
        '''
        # objects
        user_obj = self.pool.get('res.users')
        
        user_ids = kwargs['user_ids']
        user_obj.write(cr, uid, user_ids, {'active': False}, context=context)
        return user_ids
    
    def _process_users_uac(self, cr, uid, ids, context=None):
        '''
        create user corresponding to file groups if not already present
        
        default values for users
        
        res_user:
        'groups_id': fields.many2many('res.groups', 'res_groups_users_rel', 'uid', 'gid', 'Groups'),
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        user_obj = self.pool.get('res.users')
        # data structure
        data_structure = context['data_structure']
        # default password value
        default_password_value = 'temp'
        
        for obj in self.browse(cr, uid, ids, context=context):
            # get admin user id
            admin_ids = user_obj.search(cr, uid, [('login', '=', 'admin')], context=context)
            if not admin_ids:
                # log error and return
                data_structure[obj.id]['users_info']['errors'].append('The Administrator user does not exist. This is a big issue.')
                return
            # group ids - used to set all groups to admin user
            group_ids_list = []
            # user ids - used to deactivate users for which group is not in the file
            # we do not want to deactivate admin user (even if not in the file)
            user_ids_list = [admin_ids[0]]
            for group_name in data_structure[obj.id]['group_name_list']:
                # login format from group_name
                login_name = '_'.join(group_name.lower().split())
                # check if a user already exist
                user_ids = user_obj.search(cr, uid, [('login', '=', login_name)], context=context)
                if not user_ids:
                    # create a new user, copied from admin user
                    user_ids = [user_obj.copy(cr, uid, admin_ids[0], {'name': group_name,
                                                                      'login': login_name,
                                                                      'password': default_password_value,
                                                                      'date': False}, context=context)]
                else:
                    # we make sure that the user name is up to date, as Manager gives the same login name as mAnAgER.
                    user_obj.write(cr, uid, user_ids, {'name': group_name}, context=context)
                # update the group of the user with (6, 0, 0) resetting the data
                group_ids = self._get_ids_from_group_names(cr, uid, ids, context=context, group_names=[group_name])
                user_obj.write(cr, uid, user_ids, {'groups_id': [(6, 0, group_ids)]}, context=context)
                # keep group_id for updating admin user
                group_ids_list.extend(group_ids)
                # keep user_id for deactivate users not present in the file
                user_ids_list.extend(user_ids)
                
            # get all users
            all_user_ids = user_obj.search(cr, uid, [], context=context)
            # deactivate user not present in the file and not ADMIN
            deactivate_user_ids = [x for x in all_user_ids if x not in user_ids_list]
            self._deactivate_user_ids(cr, uid, ids, context=context, user_ids=deactivate_user_ids)
            # activate user from the file (could have been deactivate previously)
            self._activate_user_ids(cr, uid, ids, context=context, user_ids=user_ids_list)
            # get admin group id
            group_ids_list.append(self._get_admin_user_rights_group_id(cr, uid, ids, context=context))
            # for admin user, set all unifield groups + admin group (only user to have this group)
            user_obj.write(cr, uid, admin_ids, {'groups_id': [(6, 0, group_ids_list)]}, context=context)
        
        return True
    
    def _process_menus_uac(self, cr, uid, ids, context=None):
        '''
        set menus group relation as specified in file
        
        ir.ui.menu: groups_id
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        menu_obj = self.pool.get('ir.ui.menu')
        # data structure
        data_structure = context['data_structure']
        # get all menus from database
        all_menus_context = dict(context)
        all_menus_context.update({'ir.ui.menu.full_list': True})
        db_menu_ids = menu_obj.search(cr, uid, [], context=all_menus_context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            # check each menus from database
            for db_menu_id in db_menu_ids:
                # group ids to be linked to
                group_ids = []
                if db_menu_id not in data_structure[obj.id]['menus_groups'] or not data_structure[obj.id]['menus_groups'][db_menu_id]:
                    # we modify the groups to admin only if the menu is not linked to one of the group of DNCGL
                    skip_update = False
                    db_menu = menu_obj.browse(cr, uid, db_menu_id, context=context)
                    dncgl_ids = self._get_DNCGL_ids(cr, uid, ids, context=context)
                    for group in db_menu.groups_id:
                        if group.id in dncgl_ids:
                            skip_update = True
                    # the menu does not exist in the file OR the menu does not belong to any group
                    # link (6,0,[id]) to administration / access rights
                    if not skip_update:
                        admin_group_id = self._get_admin_user_rights_group_id(cr, uid, ids, context=context)
                        group_ids = [admin_group_id]
                else:
                    # find the id of corresponding groups, and write (6,0, ids) in groups_id
                    group_ids = self._get_ids_from_group_names(cr, uid, ids, context=context, group_names=data_structure[obj.id]['menus_groups'][db_menu_id])
                # link the menu to selected group ids
                if group_ids:
                    menu_obj.write(cr, uid, [db_menu_id], {'groups_id': [(6, 0, group_ids)]}, context=context)
        
        return True
    
    def _process_objects_uac(self, cr, uid, ids, context=None):
        '''
        reset ACL lines
        
        
        ir.model:
        'access_ids': fields.one2many('ir.model.access', 'model_id', 'Access'),
        
        ir.model.access:
        'model_id': fields.many2one('ir.model', 'Object', required=True, domain=[('osv_memory','=', False)], select=True, ondelete='cascade'),
        'group_id': fields.many2one('res.groups', 'Group', ondelete='cascade', select=True),
        'perm_read': fields.boolean('Read Access'),
        'perm_write': fields.boolean('Write Access'),
        'perm_create': fields.boolean('Create Access'),
        'perm_unlink': fields.boolean('Delete Access'),
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        model_obj = self.pool.get('ir.model')
        access_obj = self.pool.get('ir.model.access')
        # list all ids of objects from the database
        model_ids = model_obj.search(cr, uid, [('osv_memory', '=', False)], context=context)
        # list all ids of acl
        access_ids = access_obj.search(cr, uid, [], context=context)
        # admin user group id
        admin_group_user_rights_id = self._get_admin_user_rights_group_id(cr, uid, ids, context=context)
        # list of all acl linked to Administration / Access Rights -> two lines for those models
        admin_group_access_ids = access_obj.search(cr, uid, [('group_id', '=', admin_group_user_rights_id)], context=context)
        # get the list of corresponding model ids
        data = access_obj.read(cr, uid, admin_group_access_ids, ['model_id'], context=context)
        # we only keep one ACL with link to admin for one model thanks to dictionary structure
        two_lines_ids = dict((x['model_id'][0], x['id']) for x in data if x['model_id'])
        # drop all ACL
        access_obj.unlink(cr, uid, access_ids, context=context)
        # one line data
        acl_one_line_read_no_group_values = {'name': 'not admin',
                                             'group_id': False,
                                             'perm_read': True,
                                             'perm_write': True,
                                             'perm_create': True,
                                             'perm_unlink': True,
                                             }
        # create one line for all objects no linked to admin
        no_linked_to_admin_ids = [x for x in model_ids if x not in two_lines_ids.keys()]
        model_obj.write(cr, uid, no_linked_to_admin_ids, {'access_ids' : [(0, 0, acl_one_line_read_no_group_values)]}, context=context)
        # first line, for admin group, all access
        acl_admin_values = {'name': 'admin',
                            'group_id': admin_group_user_rights_id,
                            'perm_read': True,
                            'perm_write': True,
                            'perm_create': True,
                            'perm_unlink': True,
                            }
        acl_read_values = {'name': 'admin',
                           'group_id': False,
                           'perm_read': True,
                           'perm_write': False,
                           'perm_create': False,
                           'perm_unlink': False,
                           }
        # create lines for theses models with deletion of existing ACL
        # [(0, 0, {'field_name':field_value_record1, ...}), (0, 0, {'field_name':field_value_record2, ...})]
        model_obj.write(cr, uid, two_lines_ids.keys(), {'access_ids' : [(0, 0, acl_admin_values), (0, 0, acl_read_values)]}, context=context)
        
        return True
    
    def _process_record_rules_uac(self, cr, uid, ids, context=None):
        '''
        drop all
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        rule_obj = self.pool.get('ir.rule')
        all_ids = rule_obj.search(cr, uid, [], context=context)
        rule_obj.unlink(cr, uid, all_ids, context=context)
        
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
        
        # we need to take inactive groups into acount, in order to reactivate them and avoid creation of the same group multiple time
        context=dict(context, active_test=False)
        # gather data structure corresponding to selected file
        data_structure = self._import_data_uac(cr, uid, ids, context=context)
        # process the groups
        self._process_groups_uac(cr, uid, ids, context=dict(context, data_structure=data_structure))
        # process users
        self._process_users_uac(cr, uid, ids, context=dict(context, data_structure=data_structure))
        # process menus - groups relation
        self._process_menus_uac(cr, uid, ids, context=dict(context, data_structure=data_structure))
        # process ACL
        self._process_objects_uac(cr, uid, ids, context=context)
        # process rules
        self._process_record_rules_uac(cr, uid, ids, context=context)
        # error/warning logging
        # TODO
        
        return {'type': 'ir.actions.act_window_close'}

user_access_configurator()


class res_groups(osv.osv):
    '''
    add an active column
    '''
    _inherit = 'res.groups'
    _columns = {'active': fields.boolean('Active', readonly=True),
                'from_file_import_res_groups': fields.boolean('Active', readonly=True),
                }
    _defaults = {'active': True,
                 'from_file_import_res_groups': False,
                 }

res_groups()


class ir_model_access(osv.osv):
    _inherit = 'ir.model.access'
    
    def _ir_model_access_check_groups_hook(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the check_groups method from server/bin/addons/base/ir>ir_model.py>ir_model_access
        
        - allow to modify the criteria for group display
        '''
        if context is None:
            context = {}
        
        never_displayed_groups = {'group_multi_company': 'base',
                                  'group_no_one': 'base',
                                  'group_product_variant': 'product'}
        
        # original criteria is not used at all -> no link with groups of the user as groups= stay in original openERP modules - only call if some // modifications are executed by the hooks
        super(ir_model_access, self)._ir_model_access_check_groups_hook(cr, uid, context=context, *args, **kwargs)
        group = kwargs['group']
        
        grouparr  = group.split('.')
        if not grouparr:
            return False
        # if the group belongs to group not to display, we return False
        # we check module *and* group name
        if grouparr[1] in never_displayed_groups.keys() and grouparr[0] == never_displayed_groups[grouparr[1]]:
            return False
        return True
    
ir_model_access()
