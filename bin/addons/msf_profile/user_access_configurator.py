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
import logging

from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

RESULT_MODELS_SELECTION = [('group', 'Group'), ('user', 'User'), ('menu', 'Menu')]
RESULT_TYPES_SELECTION = [('error', 'Error'), ('warning', 'Warning'), ('created', 'Created'), ('activated', 'Activated'), ('deactivated', 'Deactivated'), ('updated', 'Updated')]

LEVEL_SELECTION = {'hq': 'hq', 'co': 'coordo', 'pr': 'project'}

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

    def _get_ids_from_group_names(self, cr, uid, context=None, *args, **kwargs):
        '''
        return ids corresponding to group names
        '''
        # objects
        group_obj = self.pool.get('res.groups')
        # group names
        group_names = kwargs['group_names']
        # additional search criteria
        additional_criterias = kwargs.get('additional_criterias', [])
        if not isinstance(group_names, list):
            group_names = [group_names]

        # add additional criterias
        criterias = [('name', 'in', group_names)]
        criterias.extend(additional_criterias)
        group_ids = group_obj.search(cr, uid, criterias, context=context)
        return group_ids

    def _get_all_access_objects_ids(self, cr, uid, context=None, *args, **kwargs):
        '''
        return ids of object which need full access even if originally admin rights only
        '''
        # objects
        model_obj = self.pool.get('ir.model')
        # group names
        all_access_group_names = self._get_all_access_objects_name(cr, uid, context=context)
        all_access_group_ids = model_obj.search(cr, uid, [('model', 'in', all_access_group_names)], context=context)

        return all_access_group_ids

    def _get_all_access_objects_name(self, cr, uid, context=None, *args, **kwargs):
        '''
        return names of object which need full access even if originally admin rights only
        '''
        all_access_object_names = ['ir.model.data']
        return all_access_object_names

    def _get_admin_user_rights_group_name(self, cr, uid, context=None, *args, **kwargs):
        '''
        return admin_user_rights_group
        '''
        admin_user_rights_group = 'Administration / Access Rights'
        return admin_user_rights_group

    def _get_admin_user_rights_group_id(self, cr, uid, context=None, *args, **kwargs):
        '''
        return admin_user_rights_group id
        '''
        admin_group_name = self._get_admin_user_rights_group_name(cr, uid, context=context)
        admin_group_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=[admin_group_name])
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
        return self._get_ids_from_group_names(cr, uid, context=context, group_names=group_names)

    def _get_IGL_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return immunity groups
        '''
        group_immunity_list = [u'Administration / Access Rights']
        # CNCGL names are temporarily added as non active groups are considered to be part of no groups, and therefore always displayed?
#        group_immunity_list.extend(self._get_DNCGL_name(cr, uid, ids, context=context))

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
              'group': {'activated': [group_names], 'deactivated': [group_names], 'created': [group_names], 'warning': [], 'error': [], 'updated': []},
              'user': {'activated': [user_names], 'deactivated': [user_names], 'created': [user_names], 'warning': [], 'error': []},
              'menu': {'warning': [], 'error': []},
              }
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        data_obj = self.pool.get('ir.model.data')

        # data structure returned with processed data from file
        data_structure = {}

        for obj in self.browse(cr, uid, ids, context=context):
            # data structure returned with processed data from file
            data_structure.update({obj.id: {'group_name_list': [],
                                            'menus_groups': {},
                                            'group': {'activated': [], 'deactivated': [], 'created': [], 'warning': [], 'error': [], 'updated':[]},
                                            'user': {'activated': [], 'deactivated': [], 'created': [], 'warning': [], 'error': []},
                                            'menu': {'warning': [], 'error': []},
                                            }})
            # file to process
            f = obj.file_to_import_uac
            # file is mandatory for import process
            if not f:
                raise osv.except_osv(_('Warning'), _('No File Selected.'))
            # load the selected file according to XML OUTPUT
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(f))
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
                        if not row.cells[i].data or row.cells[i].data == '':
                            group_name = 'No Name'
                        else:
                            group_name = row.cells[i].data
                        # if the same group is defined multiple times
                        if group_name in data_structure[obj.id]['group_name_list']:
                            # display a warning, the same group is displayed multiple times, columns values are aggregated (OR)
                            data_structure[obj.id]['group']['warning'].append('The group %s is defined multiple times. Values from all these groups are aggregated (OR function).'%group_name)
                        # we add the column, even if defined multiple times, as we need it for name matching when setting menu rights
                        data_structure[obj.id]['group_name_list'].append(group_name)
                else:
                    # information rows
                    try:
                        menu_id = data_obj.get_object_reference(cr, uid, row.cells[0], row.cells[1])[1]
                    except ValueError:
                        # menu is in the file but not in the database
                        data_structure[obj.id]['menu']['error'].append('The menu %s (%s.%s) is defined in the file but is missing in the database.'%(row.cells[3], row.cells[0], row.cells[1]))
                        continue

                    # test if a menu is defined multiple times
                    if menu_id in data_structure[obj.id]['menus_groups']:
                        data_structure[obj.id]['menu']['warning'].append('The menu %s (%s.%s) is defined multiple times. Groups from all these rows are aggregated (OR function).'%(row.cells[3], row.cells[0], row.cells[1]))

                    # skip information rows - find related groups
                    for i in range(obj.number_of_non_group_columns_uac, len(row)):
                        # name of group
                        menu_group_list = data_structure[obj.id]['menus_groups'].setdefault(menu_id, [])
                        # group is true for this menu
                        if self._cell_is_true(cr, uid, ids, context=context, cell=row.cells[i]):
                            group_name = data_structure[obj.id]['group_name_list'][i - obj.number_of_non_group_columns_uac]
                            # if the column is defined multiple times, we only add one time the name, but the access selection is aggregated from all related columns
                            if group_name.split('$')[0] not in menu_group_list:
                                menu_group_list.append(group_name.split('$')[0])

            # all rows have been treated, the order of group_name_list is not important anymore, we can now exclude groups which are defined multiple times
            data_structure[obj.id]['group_name_list'] = list(set(data_structure[obj.id]['group_name_list']))

        return data_structure

    def _activate_immunity_groups(self, cr, uid, ids, context=None):
        '''
        activate immunity groups

        return immunity group
        '''
        group_immunity_name_list = self._get_IGL_name(cr, uid, ids, context=context)
        return self._set_active_group_name(cr, uid, ids, context=context, group_names=group_immunity_name_list, active_value=True)

    def _set_active_group_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        activate groups names

        return activated groups names
        '''
        # objects
        group_obj = self.pool.get('res.groups')
        # data structure
        data_structure = context['data_structure']

        group_names = kwargs['group_names']
        active_value = kwargs['active_value']
        set_active_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=group_names, additional_criterias=[('visible_res_groups', '=', not active_value)])
        group_obj.write(cr, uid, set_active_ids, {'visible_res_groups': active_value}, context=context)

        # info logging - activated/deactivated groups
        set_active_names = [x['name'] for x in group_obj.read(cr, uid, set_active_ids, ['name'], context=context)]
        for i in ids:
            if active_value:
                data_structure[i]['group']['activated'].extend(set_active_names)
            else:
                data_structure[i]['group']['deactivated'].extend(set_active_names)

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
        context['bypass_group_level'] = True

        # IGL groups are activated
        self._activate_immunity_groups(cr, uid, ids, context=context)

        read_group_names = group_obj.read(cr, uid, group_ids, ['name'], context=context)
        db_group_names = [x['name'] for x in read_group_names]
        deactivate_group_names = []

        for obj in self.browse(cr, uid, ids, context=context):

            # work copy of groups present in the file - will represent the missing groups to be created
            level_group_names = list(data_structure[obj.id]['group_name_list'])

            # build a dict with group_name as key and level as value (or False if no level)
            file_level_dict = {}
            for group_name in level_group_names:
                if len(group_name.split('$')) == 2:
                    group, level = group_name.split('$')
                    file_level_dict[group] = level
                elif len(group_name.split('$')) > 2:
                    raise osv.except_osv(_('Error'),
                                         _("The group '%s' contain more than one '$' character, it should contain only one maximum") % group_name)
                else:
                    file_level_dict[group_name] = False

            for db_group_name in db_group_names:
                if db_group_name in file_level_dict:
                    # the group exists in the file and in the db, check the level
                    group_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=[db_group_name])
                    if group_ids:
                        level = group_obj.read(cr, uid, group_ids[0], ['level'], context=context)['level']
                        new_level = file_level_dict[db_group_name]
                        if new_level and new_level.lower() not in LEVEL_SELECTION:
                            raise osv.except_osv(_('Error'),
                                                 _("The keyword '%s' after '$' character should be one of the following : %s. Check the group name '%s'.") % (new_level, ', '.join([x.upper() for x in LEVEL_SELECTION.keys()]), '%s$%s' % (db_group_name, new_level)))
                        new_level = new_level and LEVEL_SELECTION[new_level.lower()] or False
                        if level != new_level:
                            # the level change
                            # update it with the one from the file
                            group_obj.write(cr, uid, group_ids, {'level': new_level}, context)
                            data_structure[obj.id]['group']['updated'].append(db_group_name)
                elif not self._group_name_is_immunity(cr, uid, ids, context=context, group_name=db_group_name):
                    # the group from database is not immune and not in the file
                    deactivate_group_names.append(db_group_name)

            # create the new groups from the file
            for group, level in file_level_dict.items():
                if group not in db_group_names:
                    if level and level.lower() not in LEVEL_SELECTION:
                        raise osv.except_osv(_('Error'),
                                             _("The keyword '%s' after '$' character should be one of the following : %s. Check the group name '%s'.") % (level, ', '.join([x.upper() for x in LEVEL_SELECTION.keys()]), '%s$%s' % (group, level)))
                    level = level and LEVEL_SELECTION[level.lower()] or False
                    group_obj.create(cr, uid,
                                     {'name': group,
                                      'from_file_import_res_groups': True,
                                      'level': level}, context=context)
                    # info logging - created groups
                    data_structure[obj.id]['group']['created'].append(group)

            # deactivate the groups not present in the file
            # UF-1996 : Don't deactivate groups not present in the file
            #self._set_active_group_name(cr, uid, ids, context=context, group_names=deactivate_group_names, active_value=False)

        return True

    def _set_active_user_ids(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        change active value of user ids

        return modified user ids
        '''
        # objects
        user_obj = self.pool.get('res.users')
        # data structure
        data_structure = context['data_structure']

        user_ids = kwargs['user_ids']
        active_value = kwargs['active_value']
        # only with active not active_value
        set_active_ids = user_obj.search(cr, uid, [('id', 'in', user_ids), ('active', '=', not active_value)], context=context)
        user_obj.write(cr, uid, set_active_ids, {'active': active_value}, context=context)

        # info logging - activated/deactivated users
        set_active_names = [x['name'] for x in user_obj.read(cr, uid, set_active_ids, ['name'], context=context)]
        for i in ids:
            if active_value:
                data_structure[i]['user']['activated'].extend(set_active_names)
            else:
                data_structure[i]['user']['deactivated'].extend(set_active_names)

        return set_active_ids

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
                data_structure[obj.id]['user']['error'].append('The Administrator user does not exist. This is a big issue.')
                return
            # group ids - used to set all groups to admin user
            group_ids_list = []
            # user ids - used to deactivate users for which group is not in the file
            # we do not want to deactivate admin user (even if not in the file)
            user_ids_list = [admin_ids[0]]
            group_names_with_level = list(data_structure[obj.id]['group_name_list'])
            # remove the $XX extension
            group_names = [group.split('$')[0] for group in
                           group_names_with_level if group]
            data_structure[obj.id]['group_name_list'] = group_names

            for group_name in group_names:
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
                    # info logging - created users
                    data_structure[obj.id]['user']['created'].append(group_name)

                else:
                    # we make sure that the user name is up to date, as Manager gives the same login name as mAnAgER.
                    user_obj.write(cr, uid, user_ids, {'name': group_name}, context=context)
                # update the group of the user with (6, 0, 0) resetting the data
                group_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=[group_name])
                user_obj.write(cr, uid, user_ids, {'groups_id': [(6, 0, group_ids)]}, context=context)
                # keep group_id for updating admin user
                group_ids_list.extend(group_ids)
                # keep user_id for deactivate users not present in the file
                user_ids_list.extend(user_ids)

            # get all users
            #all_user_ids = user_obj.search(cr, uid, [], context=context)
            # deactivate user not present in the file and not ADMIN
            # UF-1996 : Don't deactivate user not present in the file
            #deactivate_user_ids = [x for x in all_user_ids if x not in user_ids_list]
            #self._set_active_user_ids(cr, uid, ids, context=context, user_ids=deactivate_user_ids, active_value=False)
            # activate user from the file (could have been deactivate previously)
            self._set_active_user_ids(cr, uid, ids, context=context, user_ids=user_ids_list, active_value=True)
            # get admin group id
            group_ids_list.append(self._get_admin_user_rights_group_id(cr, uid, context=context))
            group_ids_list = list(set(group_ids_list))  # remove duplicates
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
        groups_obj = self.pool.get('res.groups')
        # data structure
        data_structure = context['data_structure']
        # get all menus from database
        all_menus_context = dict(context)
        all_menus_context.update({'ir.ui.menu.full_list': True})
        db_menu_ids = menu_obj.search(cr, uid, [], context=all_menus_context)
        admin_group_id = self._get_admin_user_rights_group_id(cr, uid, context=context)
        groups_to_write = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # check each menus from database
            for db_menu_id in db_menu_ids:
                # group ids to be linked to
                group_ids = []
                groups_not_in_file = []
                db_menu = menu_obj.browse(cr, uid, db_menu_id, context=context)
                # UF-1996 : If the items found in the import file, then modify accordingly (do not delete and re create).
                # If the menu entry is in file but with no groups, set the Admin rights on it
                if db_menu_id in data_structure[obj.id]['menus_groups'] and not data_structure[obj.id]['menus_groups'].get(db_menu_id):
                    # we modify the groups to admin only if the menu is not linked to one of the group of DNCGL
                    skip_update = False
                    dncgl_ids = self._get_DNCGL_ids(cr, uid, ids, context=context)
                    for group in db_menu.groups_id:
                        if group.id in dncgl_ids:
                            skip_update = True
                    # the menu does not exist in the file OR the menu does not belong to any group
                    # link (6,0,[id]) to administration / access rights
                    if not skip_update:
                        group_ids = [admin_group_id]
                elif data_structure[obj.id]['menus_groups'].get(db_menu_id, []):
                    # find the id of corresponding groups, and write (6,0, ids) in groups_id
                    group_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=data_structure[obj.id]['menus_groups'][db_menu_id])
                for group in db_menu.groups_id:
                    if group.name not in data_structure[obj.id]['group_name_list'] and group.id != admin_group_id:
                        groups_not_in_file.append(group.id)

                # link the menu to selected group ids
                if group_ids:
                    if groups_not_in_file:
                        # remove from menu object groups not listed in the file
                        menu_obj.write(cr, uid, [db_menu_id], {'groups_id': [(3,x) for x in groups_not_in_file]}, context=context)
                    for gp_id in group_ids:
                        groups_to_write.setdefault(gp_id, [])
                        groups_to_write[gp_id].append(db_menu_id)
            grp_ids = groups_obj.search(cr, uid, [], context=context)
            all_menu_in_file = data_structure[obj.id]['menus_groups'].keys()

            # keep in group menu not listed in the file
            for group in groups_obj.browse(cr, uid, grp_ids):
                if group.id in groups_to_write:
                    access_not_in_file = [x.id for x in group.menu_access if x.id not in all_menu_in_file]
                    if access_not_in_file:
                        groups_to_write[group.id] += access_not_in_file
                if group.name in data_structure[obj.id]['group_name_list'] and group.id not in groups_to_write:
                    groups_obj.write(cr, uid, [group.id], {'menu_access': [(6, 0, [])]}, context=context)

            for gp_id in groups_to_write:
                groups_obj.write(cr, uid, [gp_id], {'menu_access': [(6, 0, groups_to_write[gp_id])]}, context=context)

        return True

    def _process_objects_uac(self, cr, uid, context=None):
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

        # objects
        model_obj = self.pool.get('ir.model')
        access_obj = self.pool.get('ir.model.access')
        # list all ids of acl
        access_ids = access_obj.search(cr, uid, [], context=context)
        # admin user group id
        admin_group_user_rights_id = self._get_admin_user_rights_group_id(cr, uid, context=context)
        # list of objects which have wild card for all access
        all_access_object_ids = self._get_all_access_objects_ids(cr, uid, context=context)
        # list of all acl linked to Administration / Access Rights -> two lines for those models - ONLY IF NOT PART OF ALL ACCESS OBJECTS
        admin_group_access_ids = access_obj.search(cr, uid, [('group_id', '=', admin_group_user_rights_id),
                                                             ('model_id', 'not in', all_access_object_ids)], context=context)
        # get the list of corresponding model ids
        data = access_obj.read(cr, uid, admin_group_access_ids, ['model_id'], context=context)
        # we only keep one ACL with link to admin for one model thanks to dictionary structure
        two_lines_ids = dict((x['model_id'][0], x['id']) for x in data if x['model_id'])
        # drop all ACL
        access_obj.unlink(cr, uid, access_ids, context=context)
        # first line, for admin group, all access
        acl_admin_values = {
            'name': 'admin',
            'group_id': admin_group_user_rights_id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
            'from_system': True,
        }
        acl_read_values = {
            'name': 'user read',
            'group_id': False,
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
            'from_system': True,
        }
        # create lines for theses models with deletion of existing ACL
        # [(0, 0, {'field_name':field_value_record1, ...}), (0, 0, {'field_name':field_value_record2, ...})]
        model_obj.write(cr, uid, two_lines_ids.keys(), {'access_ids' : [(0, 0, acl_admin_values), (0, 0, acl_read_values)]}, context=context)

        return True

    def _process_record_rules_uac(self, cr, uid, context=None):
        '''
        drop all
        '''
        # Some verifications
        if context is None:
            context = {}

        # objects
        rule_obj = self.pool.get('ir.rule')
        all_ids = rule_obj.search(cr, uid, [], context=context)
        rule_obj.unlink(cr, uid, all_ids, context=context)

        return False

    def _do_process_uac(self, cr, uid, ids, context=None):
        '''
        private method, used in the yaml tests to get data_structure
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # we need to take inactive groups and users into acount, in order to reactivate them and avoid creation of the same group multiple time
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
        # UF-1996 : Don't reset the Object ACL at reloading of Menu Access from file
        # self._process_objects_uac(cr, uid, context=context)
        # process rules
        #self._process_record_rules_uac(cr, uid, context=context)
        return data_structure

    def do_process_uac(self, cr, uid, ids, context=None):
        '''
        main function called from wizard
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        data_structure = self._do_process_uac(cr, uid, ids, context=context)
        # data
        name = _("Results from User Rights Import")
        model = 'user.access.results'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context,
                                                                                                data_structure=data_structure))
        return res

    def do_update_after_module_install(self, cr, uid, mode, context=None):
        '''
        special method called after module install

        reset data potentially reset to default values
        '''
        logger = logging.getLogger('ACL')
        cr.execute("select name, model_id from ir_model_access group by name, model_id having (count(*) > 1)")
        for x in cr.fetchall():
            logger.error('Duplicates ACL (ir.model.access) name: %s module_id: %s'% (x[0], x[1]))
        if mode == 'init':
            # process ACL
            self._process_objects_uac(cr, uid, context=context)
            # process rules
            self._process_record_rules_uac(cr, uid, context=context)
            # deactivate all default groups (except Admin)
            no_group_ids = self._get_ids_from_group_names(cr, uid, context=context, group_names=['Useability / Extended View', 'Useability / No One', 'Sync / User'])
            no_group_ids.append(self._get_admin_user_rights_group_id(cr, uid, context=context))
            group_ids = self.pool.get('res.groups').search(cr, uid, [('id', 'not in', no_group_ids)], context=context)
            self.pool.get('res.groups').write(cr, uid, group_ids, {'visible_res_groups': False}, context=context)
        else:
            """
                if addons modules updated we have to clean default OpenERP user access defined in data.xml
                OpenERP data records have a xmlid with a specific module name (!= sd)

            """
            models_to_clean = ['ir.model.access', 'ir.rule']
            for model in models_to_clean:
                m_obj = self.pool.get(model)
                cr.execute('''select m.id from %s m
                    left join ir_model_data d on d.res_id = m.id and d.model = %%s
                    where module not in ('sd', 'sync_client', 'sync_server', 'sync_common', 'sync_so', 'update_client', 'update_server', '')
                ''' % m_obj._table, (model,))  # not_a_user_entry
                ids_to_del = [x[0] for x in cr.fetchall()]
                if ids_to_del:
                    m_obj.unlink(cr, 1, ids_to_del)

        return True

user_access_configurator()


class user_access_results(osv.osv_memory):
    _name = 'user.access.results'
    _columns = {'group_ids_user_access_results': fields.one2many('user.access.results.groups.line', 'wizard_id_user_access_results_line', string='Groups Info'),
                'user_ids_user_access_results': fields.one2many('user.access.results.users.line', 'wizard_id_user_access_results_line', string='Users Info'),
                'menu_ids_user_access_results': fields.one2many('user.access.results.menus.line', 'wizard_id_user_access_results_line', string='Menus Info'),
                }

    def default_get(self, cr, uid, fields, context=None):
        '''
        fill the lines with default create_values
        '''
        # Some verifications
        if context is None:
            context = {}
        # data structure
        data_structure = context['data_structure']
        # super
        res = super(user_access_results, self).default_get(cr, uid, fields, context=context)
        # wizard id
        wizard_id = context['active_ids'][0]
        # model
        for model_t in RESULT_MODELS_SELECTION:
            # model
            model = model_t[0]
            # values
            result = []
            # type
            for type_t in RESULT_TYPES_SELECTION:
                # type
                tmp_type = type_t[0]
                # fill groups data
                if tmp_type in data_structure[wizard_id][model]:
                    datas = data_structure[wizard_id][model][tmp_type]
                    # errors
                    for value in datas:
                        create_values  = {'model_user_access_results_line': model,
                                          'type_user_access_results_line': tmp_type,
                                          'value_user_access_results_line': value}
                        result.append(create_values)

            # add to one2many
            # kit list
            if '%s_ids_user_access_results'%model in fields:
                res.update({'%s_ids_user_access_results'%model: result})

        return res

    def close_results_uar(self, cr, uid, ids, context=None):
        '''
        close wizard
        '''
        return {'type' : 'ir.actions.act_window_close'}

user_access_results()


class user_access_results_groups_line(osv.osv_memory):
    _name = 'user.access.results.groups.line'

    def _vals_get_user_access_results_line(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})
            # name
            string_value = False
            if obj.type_user_access_results_line in ['created', 'activated', 'deactivated', 'updated']:
                string_value = 'The %s %s has been %s.'%(obj.model_user_access_results_line, obj.value_user_access_results_line, obj.type_user_access_results_line)
            elif obj.type_user_access_results_line in ['warning', 'error']:
                string_value = '%s.'%(obj.value_user_access_results_line)
            result[obj.id].update({'name': string_value})

        return result

    _columns = {'wizard_id_user_access_results_line': fields.many2one('user.access.results', string='Wizard'),
                'name': fields.function(_vals_get_user_access_results_line, method=True, type='char', size=1024, string='Name', multi='get_vals_user_access_results_line', readonly=True),
                'model_user_access_results_line': fields.selection(RESULT_MODELS_SELECTION, string='Model', readonly=True),
                'type_user_access_results_line': fields.selection(RESULT_TYPES_SELECTION, string='Type', readonly=True),
                'value_user_access_results_line': fields.char(string='Value', size=1024, readonly=True),
                }

user_access_results_groups_line()


class user_access_results_users_line(osv.osv_memory):
    _name = 'user.access.results.users.line'
    _inherit = 'user.access.results.groups.line'

user_access_results_users_line()


class user_access_results_menus_line(osv.osv_memory):
    _name = 'user.access.results.menus.line'
    _inherit = 'user.access.results.groups.line'

user_access_results_menus_line()


class res_groups(osv.osv):
    '''
    add an active column
    '''
    _inherit = 'res.groups'
    _columns = {
        'visible_res_groups': fields.boolean('Visible', readonly=False),
        'from_file_import_res_groups': fields.boolean('From file Import', readonly=True),
        'is_an_admin_profile': fields.boolean('Is an admin profile', help="User group members allowed to set default value for all users."),
    }
    _defaults = {
        'visible_res_groups': True,
        'from_file_import_res_groups': False,
        'is_an_admin_profile': False,
    }

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        If 'show_invisible' is in context, return only not Visible groups
        '''
        if context is None:
            context = {}

        if context.get('show_invisible'):
            new_args = [('visible_res_groups', '=', False)]
            for arg in args:
                if arg[0] != 'visible_res_groups':
                    new_args.append(arg)

            args = new_args

        return super(res_groups, self).search(cr, uid, args, offset, limit,
                                              order, context=context, count=count)

    def _update_inactive(self, cr, uid, ids, vals, context=None):
        '''
        If the group becomes inactive, remove :
            * the inactive group should be removed from all users who got it
            * the access control list line for the inactive group should be removed
            * the associated button control list should be removed for the inactive group
            * associated field access rule (lines) should be removed for the inactive group
        '''
        conf_obj = self.pool.get('user.access.configurator')
        data_obj = self.pool.get('ir.model.data')
        user_obj = self.pool.get('res.users')
        menu_obj = self.pool.get('ir.ui.menu')
        far_obj = self.pool.get('msf_field_access_rights.field_access_rule')
        bar_obj = self.pool.get('msf_button_access_rights.button_access_rule')
        acl_obj = self.pool.get('ir.model.access')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'visible_res_groups' in vals and not vals['visible_res_groups']:
            admin_group_id = conf_obj._get_admin_user_rights_group_id(cr, uid, context=context)
            no_one_id = conf_obj._get_DNCGL_ids(cr, uid, ids, context=context)
            extended_ids = conf_obj._get_ids_from_group_names(cr, uid, context=context, group_names=['Useability / Extended View'])
            hidden_menu_id = data_obj.get_object_reference(cr, uid, 'useability_dashboard_and_menu', 'menu_hidden')[1]

            if admin_group_id in ids:
                raise osv.except_osv(_('Error'), _('You cannot remove or inactive the Administration / Access Rights group'))

            if no_one_id in ids:
                raise osv.except_osv(_('Error'), _('You cannot remove or inactive the Useability / No One group'))

            if extended_ids and extended_ids[0] in ids:
                raise osv.except_osv(_('Error'), _('You cannot remove or inactive the Useability / Extended View group'))

            for i in ids:
                # Remove the link between groups and users
                user_ids = user_obj.search(cr, uid, [('groups_id', '=', i)], context=context)
                user_obj.write(cr, uid, user_ids, {'groups_id': [(3, i)]}, context=context)

                # Remove the link between groups and menu
                # Change the context because of the filtering of top menus
                # in base module (i.e. : addons/base/ir/ir_ui_menu.py:115)
                menu_context = context.copy()
                menu_context.update({'ir.ui.menu.full_list': True})
                menu_ids = menu_obj.search(cr, uid, [('groups_id', '=', i)], context=menu_context)
                # If the removing of group in menus give back public access of
                # the menu, add Admin groups on menus accesses
                for menu in menu_obj.browse(cr, uid, menu_ids, context=context):
                    menu_vals = {'groups_id': [(3, i)]}
                    if menu.id == hidden_menu_id:
                        menu_vals['groups_id'].append((6, 0, no_one_id))
                    elif len(menu.groups_id) == 1:
                        menu_vals['groups_id'].append((6, 0, [admin_group_id]))
                    menu_obj.write(cr, uid, [menu.id], menu_vals, context=context)

                # Remove the field access rules associated to this group
                far_ids = far_obj.search(cr, uid, [('group_ids', '=', i), ('active', 'in', ('t', 'f'))], context=context)
                far_obj.write(cr, uid, far_ids, {'group_ids': [(3, i)]}, context=context)

                # Remove the button access rules associated to this group
                bar_ids = bar_obj.search(cr, uid, [('group_ids', '=', i)], context=context)
                bar_obj.write(cr, uid, bar_ids, {'group_ids': [(3, i)]}, context=context)

            # Remove the control list lines associated to this group
            acl_ids = acl_obj.search(cr, uid, [('group_id', 'in', ids)], context=context)
            acl_obj.unlink(cr, uid, acl_ids, context=context)

            # Add Useability / Extended View group to Admin user
            user_obj.write(cr, uid, [1], {'view': 'extended'}, context=context)

        return True

    def create(self, cr, uid, vals, context=None):
        '''
        Call the inactive function if the group is inactive
        '''
        res = super(res_groups, self).create(cr, uid, vals, context=context)
        self._update_inactive(cr, uid, res, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Call the inactive function if the group is inactive
        '''
        if not ids:
            return True
        res = super(res_groups, self).write(cr, uid, ids, vals, context=context)
        self._update_inactive(cr, uid, ids, vals, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        '''
        Call the inactive function if the group is deleted
        '''
        self._update_inactive(cr, uid, ids, dict(visible_res_groups=False), context=context)
        return super(res_groups, self).unlink(cr, uid, ids, context=context)

res_groups()


class res_users(osv.osv):
    _inherit = 'res.users'

    def get_admin_profile(self, cr, uid, context=None):
        """
        It is called from the web.
        It enables to display certain fields if the user belongs to a group profiled 'admin'.
        """
        res = self.read(cr, uid, uid, ['groups_id'], context=context)
        if res.get('groups_id', False):
            if self.pool.get('res.groups').search_exist(cr, uid, [('id', 'in',
                                                                   res['groups_id']), ('is_an_admin_profile', '=', True)], context=context):
                return True
        return False

    def _get_fake(self, cr, uid, ids, field_names, args, context=None):
        res = {}
        if not ids:
            return res

        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _search_get_is_admin(self, cr, uid, obj, name, args, context=None):
        """
        US-42: 'is_admin' field search for ir.rule domain
        - if we are here, we are not logged as admin as ir rules are not applied
        - we just return a domain to exclude admin record when applying rule
          of id 'res_users_model_res_users_Administrator_User_Profile_Access'
          (Consolidated Record Rules.csv)
        """
        if context is None:
            context = {}
        if not obj or not args or len(args) != 1:
            return []
        if args[0][1] not in ('=', '!=', ):
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)

        admin_id = self._get_admin_id(cr)
        return admin_id and [('id', 'not in', [admin_id])] or []

    _columns = {
        'is_admin': fields.function(_get_fake, fnct_search=_search_get_is_admin,
                                    type='boolean', method=True, string='Is editable user ?'),
    }

    _defaults = {
        'groups_id': lambda *a: [],
        'is_admin': False,
    }
res_users()


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

class ir_values(osv.osv):
    _inherit = 'ir.values'
    _name = 'ir.values'

    def delete_default(self, cr, uid, ids, model, field, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        is_admin = self.pool.get('res.users').get_admin_profile(cr, uid, context)
        dom = [('id', 'in', ids), ('key', '=', 'default'), ('model', '=', model), ('name', '=', field)]
        if not is_admin:
            dom.append(('user_id', '=', uid))
        else:
            dom.append(('user_id', 'in', [uid, False]))
        new_ids = self.search(cr, uid, dom)
        if new_ids:
            self.unlink(cr, 1, new_ids)
        return True

ir_values()


class board_board(osv.osv):
    '''
    Override the board object because the ACL aren't used on dashboard
    and user can show an error message if he tries to open a dashboard
    containing a view of an object on which he doesn't have access.
    '''
    _inherit = 'board.board'
    _logger = logging.getLogger('board_board')

    def remove_unauthorized_children(self,cr, uid, node):
        iaaw_obj = self.pool.get('ir.actions.act_window')
        ima_obj = self.pool.get('ir.model.access')
        user_groups_id = self.pool.get('res.users').read(cr, uid, uid, ['groups_id'])['groups_id']
        for child in node.iterchildren():
            if child.tag == 'action':
                if child.get('invisible'):
                    node.remove(child)
                    continue
                elif child.get('name'):
                    action_id = int(child.get('name'))

                    # check the group has write permission on the model
                    model = iaaw_obj.browse(cr, uid, action_id).res_model
                    write_perm = ima_obj.check_group(cr, uid, model, 'write',
                                                     user_groups_id)

                    if not child.get('menu_ref'):
                        self._logger.warn('The dashboard \'%s\' does not have menu_ref attribute.'
                                          'This is needed to define security.' % child.get('string'))

                    menu_access = True
                    # if the group has no write permission, check if the
                    # user has access to the sub menu of the related dashboard.
                    if not write_perm and child.get('menu_ref'):
                        menu_ids = child.get('menu_ref').split(',')
                        if not isinstance(menu_ids, list):
                            menu_ids = [menu_ids]

                        menu_ids = [int(menu_id) for menu_id in menu_ids]
                        if not self.pool.get('ir.ui.menu').search(cr, uid,
                                                                  [('id', 'in', menu_ids)]):
                            menu_access = False

                    # if no access on the menu or on the model, delete the node
                    if not(write_perm or menu_access):
                        node.remove(child)
            else:
                child = self.remove_unauthorized_children(cr, uid, child)

        return node

    def _arch_preprocessing(self, cr, user, arch, context=None):
        from lxml import etree

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        archnode = etree.fromstring(encode(arch))
        return etree.tostring(self.remove_unauthorized_children(cr, user, archnode),pretty_print=True)


board_board()
