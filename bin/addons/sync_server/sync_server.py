# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import uuid as pkg_uuid
import tools
from tools.translate import _
import pprint
import logging
from datetime import datetime, timedelta
from sync_common import get_md5, check_md5
import time
import psycopg2
from sync_common import OC_LIST_TUPLE

pp = pprint.PrettyPrinter(indent=4)
MAX_ACTIVITY_DELAY = timedelta(minutes=5)

def check_validated(f):
    def check(self, cr, uid, uuid, hw_id, *args, **kargs):
        entity_pool = self.pool.get("sync.server.entity")
        id = entity_pool.get(cr, uid, uuid=uuid)
        if not id:
            return (False, "Error: Instance does not exist in the server database")
        entity = entity_pool.browse(cr, uid, id)[0]
        if not entity.hardware_id or entity.hardware_id != hw_id:
            logging.getLogger('sync.server').warn('Hardware id mismatch: instance %s, db hw_id: %s, hw_id sent: %s' % (entity.name, entity.hardware_id, hw_id))
            return (False, 'Error: Hardware ID is incorrect, please contact the support')
        if entity.state == 'updated':
            return (False, 'This instance config has been updated and the update procedure has to be launched at your side to apply the changes.')
        if not entity.state == 'validated':
            return (False, "The instance has not yet been validated by its parent")
        if not entity.user_id.id == int(uid):
            return (False, "You are not supposed to use this user to connect to the synchronization server")
        return f(self, cr, uid, entity, *args, **kargs)

    return check

class entity_group0(osv.osv):
    """ OpenERP group of entities """
    _name = "sync.server.entity_group"
    _trace = True
entity_group0()

class entity0(osv.osv):
    _name = "sync.server.entity"
    _trace = True
entity0()

class group_type(osv.osv):
    """ OpenERP type of group of entities """

    _name = "sync.server.group_type"
    _description = "Synchronization Instance Group Type"
    _trace = True

    _columns = {
        'name': fields.char('Type Name', size = 64, required = True),
    }

    #Check that the group type has an unique name
    _sql_constraints = [('unique_name', 'unique(name)', 'Group type name must be unique')]
group_type()

class entity_group(osv.osv):
    """ OpenERP group of entities """

    _name = "sync.server.entity_group"
    _description = "Synchronization Instance Group"
    _trace = True

    _columns = {
        'name': fields.char('Group Name', size = 64, required=True),
        'entity_ids': fields.many2many('sync.server.entity', 'sync_entity_group_rel', 'group_id', 'entity_id', string="Instances", domain="[('oc', '=', oc)]"),
        'type_id': fields.many2one('sync.server.group_type', 'Group Type', ondelete="set null", required=True),
        'oc': fields.selection(OC_LIST_TUPLE, 'Operational Center', required=True, add_empty=True),
    }

    def get_group_name(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        res = []
        for group in self.browse(cr, uid, ids, context=context):
            res.append({
                'name': group.name,
                'type': group.type_id.name,
                'oc': group.oc
            })
        return res

    def get(self, cr, uid, name, context=None):
        return self.search(cr, uid, [('name', '=', name)], context=context)

    def _check_instance_oc(self, cr, uid, ids, context=None):
        cr.execute('''
            select
                e.name
            from
                sync_server_entity_group grp, sync_entity_group_rel rel, sync_server_entity e
            where
                grp.id in %s and
                rel.group_id = grp.id and
                rel.entity_id = e.id and
                e.oc != grp.oc
            ''', (tuple(ids), ))

        mismatch = [x[0] for x in cr.fetchall()]
        if mismatch:
            raise osv.except_osv(_("Error!"), _("OC on these instances does not match OC on group: %s") % (", ".join(mismatch),))

        return True

    def write_web(self, cr, uid, ids, values, context=None, ignore_access_error=False):
        check_entity = False
        if 'entity_ids' in values:
            instance_ids = self.pool.get('sync.server.entity').search(cr, uid, [('state', '=', 'validated'), ('group_ids', 'in', ids)], context=context)
            if len(instance_ids) > 1:
                check_entity = True
        ret = super(entity_group, self).write_web(cr, uid, ids, values, context=context, ignore_access_error=ignore_access_error)

        if check_entity:
            new_instance_ids = self.pool.get('sync.server.entity').search(cr, uid, [('state', '=', 'validated'), ('group_ids', 'in', ids)], context=context)
            if set(instance_ids) != set(new_instance_ids):
                raise osv.except_osv(_("Error!"), _("Sorry you can not change instances list on a group with a least 2 Validated instances"))
        return ret

    #Check that the group has an unique name
    _sql_constraints = [('unique_name', 'unique(name)', 'Group name must be unique')]

    _constraints = [
        (_check_instance_oc, 'Error! OC on group and on instances must match.', []),
    ]

entity_group()

class entity_activity(osv.osv):
    _name = 'sync.server.entity.activity'
    _description = "Instance Activity"
    _log_access = False
    _columns = {
        'entity_id': fields.integer('Entity db id', select=1),
        'datetime': fields.datetime('Last Activity'),
        'activity': fields.char('Activity', size=128),
    }
    _defaults = {
        'activity': 'Inactive',
        'datetime': lambda *a: datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    _sql_constraints = [
        ('entity_id_unique', 'UNIQUE(entity_id)', "Can't have multiple entity activity"),
    ]
entity_activity()

class entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _name = "sync.server.entity"
    _description = "Synchronization Instance"
    _parent_store = True
    _trace = True

    def init(self, cr):
        cr.execute("""select column_name
            from information_schema.columns
            where table_name='sync_server_entity' AND column_name='last_activity'
        """)
        if cr.fetchone():
            # move existing column to the new object
            cr.execute("""select ent.id, ent.last_activity
                from sync_server_entity ent
                left join sync_server_entity_activity act on act.entity_id = ent.id
                where act.entity_id is null
            """)
            for row in cr.fetchall():
                cr.execute("insert into sync_server_entity_activity (entity_id, datetime, activity) values (%s, %s, 'Inactive')", (row[0], row[1]))

    def _get_activity(self, cr, uid, ids, name, arg, context=None):
        res = {}
        act_obj = self.pool.get('sync.server.entity.activity')
        activity_ids = act_obj.search(cr, uid, [('entity_id', 'in', ids)], context=context)
        for id in ids:
            res[id] = {
                'activity': _('Inactive'),
                'last_dateactivity': False
            }
        for activity in act_obj.browse(cr, uid, activity_ids, context=context):
            instance_activity = activity.activity or ''
            if not activity.datetime:
                delay = timedelta()
            else:
                delay = datetime.now() - datetime.strptime(activity.datetime, '%Y-%m-%d %H:%M:%S')

            if delay > MAX_ACTIVITY_DELAY and '...' in instance_activity:
                res[activity.entity_id]['activity'] =  _('%s (stalling)') % instance_activity
            elif instance_activity:
                res[activity.entity_id]['activity'] = instance_activity

            res[activity.entity_id]['last_dateactivity'] = activity.datetime
        return res

    def set_activity(self, cr, uid, entity, activity, wait=False, context=None):
        if context is None:
            context = {}

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if not wait:
                cr.execute("SAVEPOINT update_entity_last_activity")
                cr.execute('select id from sync_server_entity_activity where entity_id=%s for update nowait', (entity.id,), log_exceptions=False)
            cr.execute('update sync_server_entity_activity set datetime=%s, activity=%s where entity_id=%s', (now, activity, entity.id))
        except psycopg2.OperationalError as e:
            if not wait and e.pgcode == '55P03':
                # can't acquire lock: ok the show must go on
                cr.execute("ROLLBACK TO update_entity_last_activity")
                logging.getLogger('sync.server').info("Can't acquire lock to set last_activity")
                return
            raise

    _columns = {
        'name':fields.char('Instance Name', size=64, required=True, select=True),
        'identifier':fields.char('Identifier', size=64, readonly=True, select=True),
        'hardware_id' : fields.char('Hardware Identifier', size=128, select=True),
        'parent_id':fields.many2one('sync.server.entity', 'Parent Instance', ondelete='cascade', domain="[('oc', '=', oc)]"),
        'oc': fields.selection(OC_LIST_TUPLE, 'Operational Center',
                               required=True, add_empty=True),
        'group_ids':fields.many2many('sync.server.entity_group', 'sync_entity_group_rel', 'entity_id', 'group_id', string="Groups", domain="[('oc', '=', oc)]"),
        'state' : fields.selection([('pending', 'Pending'), ('validated', 'Validated'), ('invalidated', 'Invalidated'), ('updated', 'Config updated')], 'State'),
        'email':fields.char('Contact Email', size=512),
        'user_id': fields.many2one('res.users', 'User', ondelete='restrict', required=True),

        #just in case, since the many2one exist it has no cost in database
        'children_ids' : fields.one2many('sync.server.entity', 'parent_id', 'Children Instances', readonly=1),
        'update_token' : fields.char('Update security token', size=256),

        'activity' : fields.function(_get_activity, type='char', string="Activity", method=True, multi="_get_act"),
        'last_dateactivity': fields.function(_get_activity, type='datetime', string="Date of last activity", method=True, multi="_get_act"),
        'date_success_sync': fields.datetime('Date of last success sync', readonly=True),
        #'last_activity' : fields.datetime("Date of last activity", readonly=True),

        'parent_left' : fields.integer("Left Parent", select=1),
        'parent_right' : fields.integer("Right Parent", select=1),

        'msg_ids_tmp':fields.text('List of temporary ids of message to be pulled'),
        'version': fields.integer('version'),
        'last_sequence': fields.integer('Last update sequence pulled',
                                        readonly=True),

        'country_id': fields.many2one('res.country', 'Country', ondelete="restrict"),
        'city': fields.char('City', size=256),
        'mission': fields.char('Mission', size=64),
        'latitude': fields.float('Latitude',digits=(16,6)),
        'longitude': fields.float('Longitude', digits=(16,6)),
        'pgversion': fields.char('Postgres Version', size=64, readonly=1),
        'current_user_rights_name': fields.char('UR Version', size=64, select=1, readonly=1),
    }
    _defaults = {
        'version': lambda *a: 0,
        'last_sequence': lambda *a: 0,
    }
    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.parent_id:
                raise osv.except_osv(_("Error!"), _("Can not delete an instance that have children!"))
        return super(entity, self).unlink(cr, uid, ids, context=None)

    def _check_duplicate(self, cr, uid, name, uuid, context=None):
        duplicate_id = self.search(cr, uid, [('user_id', '!=', uid), '|',
                                             ('name', '=', name), ('identifier', '=', uuid)],
                                   limit=1, order='NO_ORDER', context=context)
        return bool(duplicate_id)

    def _get_ancestor(self, cr, uid, id, context=None):
        def _get_ancestor_rec(entity, ancestor_list):
            if entity and entity.parent_id:
                ancestor_list.append(entity.parent_id.id)
                _get_ancestor_rec(entity.parent_id, ancestor_list)
            return ancestor_list

        entity = self.browse(cr, uid, id, context=context)
        return _get_ancestor_rec(entity, [])

    def _get_all_children(self, cr, uid, id, context=None):
        res = self.search(cr, uid, [('id','child_of',[id])], context=context)
        res.remove(id)
        return res

    def _check_children(self, cr, uid, entity, uuid_list, context=None):
        children_ids = self._get_all_children(cr, uid, entity.id)
        uuid_child = [child.identifier for child in self.browse(cr, uid, children_ids, context=context)]
        for uuid in uuid_list:
            if not uuid in uuid_child:
                return False
        return True

    def _get_entity_id(self, cr, uid, name, uuid, context=None):
        ids = self.search(cr, uid, [('user_id', '=', uid), '|', ('name', '=', name), ('identifier', '=', uuid)])
        return ids and ids[0] or False

    def get(self, cr, uid, name=False, uuid=False, context=None):
        if uuid:
            return self.search(cr, uid, [('identifier', '=', uuid)], context=context)
        if name:
            return self.search(cr, uid, [('name', '=', name)], context=context)
        return False

    """
        Public interface
    """
    def activate_entity(self, cr, uid, name, identifier, hardware_id, context=None):
        """
            Allow to change uuid,
            and reactivate the link between an local instance and his data on the server
        """
        raise NotImplementedError("See US-1809")

    def update(self, cr, uid, identifier, hardware_id, context=None):
        ids = self.search(cr, uid, [('identifier', '=' , identifier),
                                    ('hardware_id', '=', hardware_id),
                                    ('user_id', '=', uid),
                                    ('state', '=', 'updated')], context=context)
        if not ids:
            return (False, 'No update is ready for your entity. If you cannot synchronize data, check that your parent has validated your registration')

        token = pkg_uuid.uuid4().hex
        self.write(cr, 1, ids, {'update_token' : token}, context=context)
        entity = self.browse(cr, uid, ids, context=context)[0]
        groups = [group.name for group in entity.group_ids]
        # Avoid problems serializing None in XML-RPC
        if entity.parent_id.name is None:
            pname = ""
        else:
            pname = entity.parent_id.name
        data = {
            'name': entity.name,
            'parent': pname,
            'email': entity.email,
            'groups': groups,
            'security_token': token,
        }
        return (True, data)

    def ack_update(self, cr, uid, uuid, hardware_id, token, context=None):
        ids = self.search(cr, uid, [('identifier', '=' , uuid),
                                    ('hardware_id', '=', hardware_id),
                                    ('user_id', '=', uid),
                                    ('state', '=', 'updated'),
                                    ('update_token', '=', token)],
                          order='NO_ORDER', context=context)
        if not ids:
            return (False, 'Ack not valid')
        self.write(cr, 1, ids, {'state' : 'validated'}, context=context)
        return (True, "Instance Validated")

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if not context:
            context = {}

        # Be careful to only put it into state updated when something
        # that needs to be sent down to the client changes. (US-1809)
        groups_list = []
        if context.get('update', False):
            for before in self.browse(cr, uid, ids):
                groups_list += [x.id for x in before.group_ids]
                if ('name' in vals and before.name != vals['name'] or
                    'parent_id' in vals and before.parent_id.id != vals['parent_id'] or
                        'email' in vals and before.email != vals['email']):
                    vals['state'] = 'updated'

        ret = super(entity, self).write(cr, uid, ids, vals, context=context)

        if context.get('update', False):
            new_groups = self.pool.get('sync.server.entity_group').search(cr, uid, [('entity_ids', 'in', ids)], context=context)
            if set(new_groups) != set(groups_list):
                super(entity, self).write(cr, uid, ids, {'state': 'updated'}, context=context)
        return ret

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        update = context.get('update', False)

        if update:
            vals['state'] = 'updated'

        newid = super(entity, self).create(cr, uid, vals, context=context)
        self.pool.get('sync.server.entity.activity').create(cr, uid, {'entity_id': newid})
        return newid

    def register(self, cr, uid, data, context=None):
        """
            data = {
                'parent_name' : 'name'
                'group_names' : ['group1', 'group2']
                'identifier' : 'uuid',
                'hardware_id' : 'hardware_id'
                'name' : 'name',
                'email' : 'cur.email',
                'max_size' : '5',
                'oc': 'oca',
            }
        """
        def get_parent(parent_name):
            if parent_name:
                return self.get(cr, uid, name=parent_name, context=context)
            return False

        def get_groups(group_names):
            groups = []
            if group_names:
                for g_name in group_names:
                    group_id = self.pool.get('sync.server.entity_group').get(cr, uid, g_name, context)
                    if group_id:
                        groups.extend(group_id)
                return [(6, 0, groups)]
            return False

        if self._check_duplicate(cr, uid, data['name'], data['identifier'], context=context):
            return (False, "Duplicate Name or identifier, please select another one")

        parent_name = data.pop('parent_name')
        parent_id = get_parent(parent_name)
        parent_id = parent_id and parent_id[0] or False

        if parent_name and not parent_id:
            return (False, "Parent does not exist, please choose an existing one")

        groups_names = data.pop('group_names')
        group_ids = get_groups(groups_names)

        entity_id = self._get_entity_id(cr, uid, data['name'], data['identifier'], context=context)
        data.update({'group_ids' : group_ids, 'parent_id' : parent_id, 'user_id': uid, 'state' : 'pending'})
        if entity_id:
            entity = self.browse(cr, uid, entity_id, context=context)
            if not entity.hardware_id or entity.hardware_id != data['hardware_id']:
                return (False, 'Error: Hardware ID is incorrect, please contact the support')
            res = self.write(cr, 1, [entity_id], data, context=context)
            if res:
                #self._send_registration_email(cr, uid, data, groups_names, context=context)
                return (True, "Modification successfully done, waiting for parent validation")
            else:
                return (False, "Modification failed!")
        else:
            res = self.create(cr, 1, data, context=context)
            if res:
                #self._send_registration_email(cr, uid, data, groups_names, context=context)
                return (True, "Registration successfully done, waiting for parent validation")
            else:
                return (False, "Registration failed!")

    @check_validated
    def get_entity(self, cr, uid, entity, context=None):
        return (True, {
            'name': entity.name,
            'identifier': entity.identifier,
            'parent': entity.parent_id.name or '',
            'email': entity.email,
            'entity_status': entity.state,
            'group': ', '.join([group.name for group in entity.group_ids]),
        })

    @check_validated
    def get_children(self, cr, uid, entity, context=None):
        res = []
        for child in self.browse(cr, uid, self._get_all_children(cr, uid, entity.id), context=context):
            data = {
                'name': child.name,
                'identifier': child.identifier,
                'parent': child.parent_id.name,
                'email': child.email,
                'state': child.state,
                'group': ', '.join([group.name for group in child.group_ids]),
            }
            res.append(data)

        return (True, res)

    @check_validated
    def end_synchronization(self, cr, uid, entity, context=None):
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Inactive'), wait=True)
        return (True, "Instance %s has finished the synchronization" % entity.identifier)

    @check_validated
    def validate(self, cr, uid, entity, uuid_list, context=None):
        for uuid in uuid_list:
            if not uuid:
                return (False, "Error: One of the instance you want validate has no Identifier, the instance should register or be activated")
        if not self._check_children(cr, uid, entity, uuid_list, context=context):
            return (False, "Error: One of the entity you want to validate is not one of your children")
        ids_to_validate = self.search(cr, uid, [('identifier', 'in',
                                                 uuid_list)], context=context)
        self.write(cr, 1, ids_to_validate, {'state': 'validated'}, context=context)
        self._send_validation_email(cr, uid, entity, ids_to_validate, context=context)
        return (True, "Instance %s are now validated" % ", ".join(uuid_list))

    @check_validated
    def invalidate(self, cr, uid, entity, uuid_list, context=None):
        for uuid in uuid_list:
            if not uuid:
                return (False, "Error: One of the instance you want validate has no Identifier, the instance should register or be activated")
        if not self._check_children(cr, uid, entity, uuid_list, context=context):
            return (False, "Error: One of the entity you want validate is not one of your children")
        ids_to_validate = self.search(cr, uid, [('identifier', 'in',
                                                 uuid_list)], context=context)
        self.write(cr, 1, ids_to_validate, {'state': 'invalidated'}, context=context)
        self._send_invalidation_email(cr, uid, entity, ids_to_validate, context=context)
        return (True, "Instance %s are now invalidated" % ", ".join(uuid_list))

    def is_validated(self, cr, uid, uuid, context=None):
        entity_pool = self.pool.get("sync.server.entity")
        id = entity_pool.get(cr, uid, uuid=uuid)
        if not id:
            return (False, "Error: Instance does not exist in the server database")
        entity = entity_pool.browse(cr, uid, id)[0]
        if entity.state == 'validated':
            return (True, "The instance is validated")
        return (False, "The instance has not yet been validated by its parent")

    @check_validated
    def set_pg_version(self, cr, uid, entity, pg_version, context=None):
        """
            deprecated replaced by set_pg_ur_version
        """
        self.write(cr, 1, entity.id, {'pgversion': pg_version}, context=context)
        return True

    @check_validated
    def set_pg_ur_version(self, cr, uid, entity, pg_version, current_user_rights_name, context=None):
        self.write(cr, 1, entity.id, {'pgversion': pg_version, 'current_user_rights_name': current_user_rights_name}, context=context)
        return True

    def validate_action(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for instance in self.browse(cr, uid, ids, fields_to_fetch=['oc', 'group_ids', 'parent_id'], context=context):
            oc = instance.oc
            parent_id = instance.parent_id and instance.parent_id.id

            if instance.parent_id and instance.oc != instance.parent_id.oc:
                raise osv.except_osv(_("Error!"), _("OC on %s and %s is not the same !") % (instance.name, instance.parent_id.name))

            grp_type = []
            for grp in instance.group_ids:
                if grp.oc != oc:
                    raise osv.except_osv(_("Error!"), _("OC on group %s does not match oc on instance %s") % (grp.name, instance.name))
                if parent_id and grp.type_id.name == 'HQ + MISSION':
                    if parent_id not in [x.id for x in  grp.entity_ids]:
                        raise osv.except_osv(_("Error!"), _("Instance %s: the HQ + Mission group %s must contain the parent instance %s") % (instance.name, grp.name, instance.parent_id.name))

                if grp.type_id.name == 'MISSION' and instance.parent_id and instance.parent_id.parent_id:
                    if parent_id not in [x.id for x in  grp.entity_ids]:
                        raise osv.except_osv(_("Error!"), _("Instance %s: the Mission group %s must contain the parent instance %s") % (instance.name, grp.name, instance.parent_id.name))

                grp_type.append(grp.type_id.name)

            if instance.parent_id and instance.parent_id.parent_id:
                # project
                if len(grp_type) != 3 or set(['OC', 'MISSION', 'HQ + MISSION']) != set(grp_type):
                    raise osv.except_osv(_("Error!"), _("A Project instance must be in exactly 3 groups: OC, MISSION and HQ + MISSION"))
            elif instance.parent_id:
                # coordo
                if len(grp_type) != 4 or set(['OC', 'MISSION', 'HQ + MISSION', 'COORDINATIONS']) != set(grp_type):
                    raise osv.except_osv(_("Error!"), _("A Coordo must be in exactly 4 groups: OC, COORDINATIONS, MISSION and HQ + MISSION"))

        context['update'] = False
        self.write(cr, uid, ids, {'state': 'validated'}, context)
        return True

    def invalidate_action(self, cr, uid, ids, context=None):
        if not context:
            context={}

        context['update'] = False
        self.write(cr, uid, ids, {'state': 'invalidated'}, context)
        return True

    def _send_registration_email(self, cr, uid, data, groups_name, context=None):
        parent_id = data.get('parent_id')
        if not parent_id or not data.get('email'):
            return
        email_from = data.get('email').split(',')[0]
        parent = self.browse(cr, uid, [parent_id], context=context)[0]
        if not parent.email:
            return
        email_to = parent.email.split(',')
        tools.email_send(
            email_from,
            email_to,
            "Instance %s register, need your validation" % data.get('name'),
            """
                    Name : %s
                    Identifier : %s
                    Parent : %s
                    Email : %s
                    Group : %s
                """ % (data.get('name'), data.get('identifier'), parent.name, data.get('email'), ', '.join(groups_name)),
        )

    def _send_validation_email(self, cr, uid, entity, ids_validated, context=None):
        email_from = entity.email
        email_to = []
        for child in self.browse(cr, uid, ids_validated, context=None):
            if child.email:
                email_list = child.email and child.email.split(',') or []
                email_to.extend(email_list)

        if not email_from or not email_to:
            return

        tools.email_send(
            email_from,
            email_to,
            "Your registration has been validated by your parent %s" % entity.name,
            "You can start to synchronize your data."
        )

    def _send_invalidation_email(self, cr, uid, entity, ids_validated, context=None):
        email_from = entity.email
        email_to = []
        for child in self.browse(cr, uid, ids_validated, context=None):
            email_list = child.email and child.email.split(',') or []
            email_to.extend(email_list)

        if not email_from or not email_to:
            return

        tools.email_send(
            email_from,
            email_to,
            "Your registration has been invalidated by your parent %s" % entity.name,
            "you or your parent has been invalidated by a parent, if you need more information please contact them by mail at %s" % entity.email
        )

    def _check_recursion(self, cr, uid, ids, context=None):
        for id in ids:
            visited_branch = set()
            visited_node = set()
            res = self._check_cycle(cr, uid, id, visited_branch, visited_node, context=context)
            if not res:
                return False

        return True

    def _check_cycle(self, cr, uid, id, visited_branch, visited_node, context=None):
        if id in visited_branch: #Cycle
            return False

        if id in visited_node: #Already tested don't work one more time for nothing
            return True

        visited_branch.add(id)
        visited_node.add(id)

        #visit child using DFS
        entities = self.browse(cr, uid, id, context=context)
        for child in entities.children_ids:
            res = self._check_cycle(cr, uid, child.id, visited_branch, visited_node, context=context)
            if not res:
                return False

        visited_branch.remove(id)
        return True

    def get_entities_priorities(self, cr, uid, context=None):
        return dict([
            (rec.name, rec.parent_left)
            for rec in self.browse(cr, uid,
                                   self.search(cr, uid, [], context=context),
                                   context=context)
        ])

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        to_order = False
        if not count and order and order != 'NO_ORDER' and ('last_dateactivity' in order or 'activity' in order):
            to_order = True
            init_offset = offset
            init_limit = limit
            offset = 0
            limit = None
        ids = super(entity, self).search(cr, uid, args, offset, limit, order, context, count)
        if ids and to_order:
            order = order.replace('last_dateactivity', 'datetime')
            limit_str = init_limit and ' limit %d' % init_limit or ''
            offset_str = init_offset and ' offset %d' % init_offset or ''
            cr.execute('select entity_id from sync_server_entity_activity where entity_id in %s order by ' + order + limit_str + offset_str, (tuple(ids),))  # not_a_user_entry
            return [x[0] for x in cr.fetchall()]
        return ids

    _constraints = [
        (_check_recursion, 'Error! You cannot create cycle in entities structure.', ['parent_id']),
    ]

    _sql_constraints = [
        ('identifier_unique', 'UNIQUE(identifier)', "Can't have multiple instances with the same identifier!"),
    ]
entity()

class sync_manager(osv.osv):
    _name = "sync.server.sync_manager"
    _logger = logging.getLogger('sync.server')

    """
        Data synchronization
    """
    @check_validated
    def get_last_user_rights_info(self, cr, uid, entity, context=None):
        data = self.pool.get('sync_server.user_rights').get_last_user_rights_info(cr, 1, context)
        self._logger.info("::::::::[%s] get UR info sum: %s" % (entity.name, data['sum']))
        return data

    @check_validated
    def get_last_user_rights_file(self, cr, uid, entity, check_sum, context=None):
        ur_obj = self.pool.get('sync_server.user_rights')
        ids = ur_obj.search(cr, 1, [('sum', '=', check_sum)], context=context)
        self._logger.info("::::::::[%s] download UR (sum: %s)" % (entity.name, check_sum))
        if not ids:
            return ''
        return ur_obj.get_md5_zip(cr, 1, ids[0], context=context)

    @check_validated
    def get_surveys(self, cr, uid, entity, last_date, context=None):
        survey_obj = self.pool.get('sync_server.survey')

        dom = [('activated', '=', True)]
        deactivated_ids = []

        if last_date:
            dom += [('server_write_date', '>', last_date)]
            deactivated_ids = survey_obj.search(cr, 1, ['|', ('active', '=', False), ('activated', '=', False), ('server_write_date', '>', last_date)], context=context)

        survey_ids = survey_obj.search(cr, 1, dom, context=context)
        max_date = survey_obj.get_last_write(cr, 1)

        self._logger.info("::::::::[%s] since %s: %d active surveys, %d inactive" % (entity.name, last_date, len(survey_ids), len(deactivated_ids)))
        if not survey_ids:
            return {'active': [], 'deactivated_ids': deactivated_ids, 'max_date': max_date}

        return {
            'active': survey_obj.read(cr, 1, survey_ids, ['name', 'name_fr',  'profile', 'start_date', 'end_date', 'url_en', 'url_fr', 'server_write_date', 'included_group_txt', 'excluded_group_txt', 'include_condition'], context=context),
            'deactivated_ids': deactivated_ids,
            'max_date': max_date
        }

    @check_validated
    def get_model_to_sync(self, cr, uid, entity, context=None):
        """
            Initialize a Push session, send the session id and the list of rule
            @param entity: string : uuid of the synchronizing entity
            @return tuple : (a, b, c):
                    a is True is if the call is succesfull, False otherwise
                    b : is a list of dictionaries that contains all the rule
                        that apply for the synchronizing instance.
                        The format of the dict that contains a single rule definition
                        {
                            'server_id' : integer : id of the rule server side,
                            'name' : string : Name of the rule,
                            'owner_field' : string : Name of the field that is the owner instance of the record
                            'model' : string : Name of the model on which the rule applies,
                            'domain' : string : The domain to filter the record to synchronize, format : standard domain [(),()]
                            'sequence_number' : integer : Sequence number of the rule,
                            'included_fields' : string : list of fields to include, same format as the one needed for export data
                        }

        """
        res = self.pool.get('sync_server.sync_rule')._get_rule(cr, uid, entity, context=context)
        return (True, res[1], get_md5(res[1]))

    @check_validated
    def receive_package(self, cr, uid, entity, packet, context=None):
        """
            Synchronizing entity sending it's packet to the sync server.
            @param entity : string : uuid of the synchronizing entity
            @param packet : Dictionnary : update to send to the server, a pakcet contains at max all the update generate by the same rule
                            format :
                            {
                                'session_id': string : id of the push session, given by get_model_to_sync,
                                'model': string : model's name of the update,
                                'rule_id': string : server_side rule's id given,
                                'fields': string : list of fields to include, format : a list of string, same format as the one needed for export data
                                'load' : list of dictionaries : content of the packet, it the list of values and version
                                        format [{
                                                    'version' : string : version of the update
                                                    'values' : string : list of values in the matching order of fields
                                                             format "['value1', 'value2']"
                                                }, ...]

                            }
            @return: tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : string : is an error message if a is False
        """
        if context is None:
            context = {}
        if context.get('md5'):
            check_md5(context['md5'], packet, _('server method receive_package'))
        res = self.pool.get("sync.server.update").unfold_package(cr, 1, entity, packet, context=context)
        return (True, res)

    @check_validated
    def confirm_update(self, cr, uid, entity, session_id, context=None):
        """
            Synchronizing entity confirm that all the packet of this session are sent
            @param entity : string : uuid of the synchronizing entity
            @param session_id : string : the synchronization session_id given at the beginning of the session by get_model_sync.
            @return tuple : (a, b)
                a : boolean : is True is if the call is succesfull, False otherwise
                b : int : sequence number given
        """
        if context is None:
            context = {}
        if context.get('md5'):
            check_md5(context['md5'], session_id, _('server method confirm_update'))

        return self.pool.get("sync.server.update").confirm_updates(cr, 1, entity, session_id, context=context)


    @check_validated
    def get_max_sequence(self, cr, uid, entity, context=None):
        """
            Give to the synchronizing client the sequence of the last complete push, the pull session will pull until this sequence.
            @param entity: string : uuid of the synchronizing entity
            @return a tuple (a, b)
                a : boolean : is True is if the call is succesfull, False otherwise
                b : integer : is the sequence number of the last successfull push session by any entity

        """
        last_seq = self.pool.get('sync.server.update').get_last_sequence(cr, uid, context=context)
        return (True, last_seq, get_md5(last_seq))

    @check_validated
    def get_update(self, cr, uid, entity, last_seq, offset, max_size, max_seq, recover=False, init_sync=False, context=None):
        """
            @param entity : string : uuid of the synchronizing entity
            @param last_seq : integer : Last sequence of update receive succefully in the previous pull session.
            @param offset : integer : Number of record receive after the last_seq
            @param max_size : integer : The number of record max per packet.
            @param max_seq : interger : The sequence max that the update the sync server send to the client in get_max_sequence, to tell the server don't send me
                            newer update then the one already their when the pull session start.
            @param recover : flag : If set to True, will recover self-owned package too.
            @return tuple : (a,b,c)
                a : boolean : True if the call is successfull, False otherwise
                b : dictionnary : Package if there is some update to send remaining, False otherwise
                c : boolean : False if there is some update to send remaining, True otherwise
                              Package format :
                              {
                                    'model': string : model's name of the update
                                    'source_name' : string : source entity's name
                                    'fields' : string : list of fields to include, format : a list of string, same format as the one needed for export data
                                    'sequence' : update's sequence number, a integer
                                    'offset' : update's server offset, used to get next updates
                                    'rule' : rule sequence number (for ordering/grouping)
                                    'fallback_values' : update_master.rule_id.fallback_values
                                    'load' : a list of dict that contain record's values and record's version
                                            [{
                                                'version' : int version of the update
                                                'values' : string : list of values in the matching order of fields
                                                             format "['value1', 'value2']"
                                            }, ..]
                              }

        """
        package = self.pool.get("sync.server.update").get_package(cr, uid, entity, last_seq, offset, max_size, max_seq, recover=recover, init_sync=init_sync, context=context)
        return (True, package or False, not package, get_md5(package))

    """
        Message synchronization
    """

    @check_validated
    def get_message_rule(self, cr, uid, entity, context=None):
        """
            Initialize a Push message session, send the list of rule
            @param entity: string : uuid of the synchronizing entity
            @return a Tuple (a, b):
                    a : boolean : is True is if the call is succesfull, False otherwise
                    b : list of dictionaries : if a is True, is a list of dictionaries that contains all the rule
                        that apply for the synchronizing instance.
                        The format of the dict that contains a single rule definition
                        {
                            'name' : string : rule's name,
                            'server_id' : integer : server side rule's id ,
                            'model' : string : Name of the model on which the rule applies,
                            'domain' : string : The domain to filter the record to synchronize, format : standard domain [(),()]
                            'sequence_number' : integer : Sequence number of the rule,
                            'remote_call' : string  : name of the method to call when the receiver will execute the message,
                            'arguments' : string : list of fields use in argument for the remote_call, see fields in receive_package
                            'destination_name' : string : Name of the field that will give the destination name,
                        }

        """
        res = self.pool.get('sync_server.message_rule')._get_message_rule(cr, uid, entity, context=context)
        return (True, res, get_md5(res))

    @check_validated
    def send_message(self, cr, uid, entity, packet, context=None):
        """
            @param entity: string : uuid of the synchronizing entity
            @param packet: list of dictionaries : a list of message, each message is a dictionnary define like this:
                            {
                                'id' : string : message unique id : ensure that we are not creating or executing 2 times the same message
                                'call' : string : name of the method to call when the receiver will execute the message
                                'dest' : string : name of the destination (generaly a partner Name)
                                'args' : string : Arguments of the call, the format is a a dictionnary that represent is object that generate the message serialiaze in json
                                        see export_data_jso in ir_model_data.py
                            }
            @return: tuple : (a, b):
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : string : is an informative message
        """
        if context is None:
            context = {}
        if context.get('md5'):
            check_md5(context['md5'], packet, _('server method send_message'))

        return self.pool.get('sync.server.message').unfold_package(cr, 1, entity, packet, context=context)


    @check_validated
    def get_message_ids(self, cr, uid, entity, context=None):
        # UTP-1179: store temporarily this ids of messages to be sent to this entity at the moment of getting the update
        # to avoid having messages that are not belonging to the same "sequence" of the update
        msg_ids_tmp = self.pool.get("sync.server.message").search(cr, uid,
                                                                  [('destination', '=', entity.id), ('sent', '=', False)],
                                                                  order='NO_ORDER', context=context)

        len_ids = 0
        if msg_ids_tmp:
            len_ids = len(msg_ids_tmp)
            self.pool.get('sync.server.entity').write(cr, 1, entity.id, {'msg_ids_tmp': msg_ids_tmp}, context=context)

        self._logger.info("::::::::[%s] stored %s messages" % (entity.name, len_ids))
        return (True, len_ids)

    @check_validated
    def reset_message_ids(self, cr, uid, entity, context=None):
        # UTP-1179: store temporarily this ids of messages to be sent to this entity at the moment of getting the update
        # to avoid having messages that are not belonging to the same "sequence" of the update
        self.pool.get('sync.server.entity').write(cr, 1, entity.id, {'msg_ids_tmp': False}, context=context)
        return (True, 0)

    @check_validated
    def get_message(self, cr, uid, entity, max_packet_size, last_seq=None, context=None):
        """
            @param entity: string : uuid of the synchronizing entity
            @param max_packet_size: The number of message max per request.
            @return: a tuple (a, b)
                a : boolean : is True is if the call is succesfull, False otherwise
                b : list of dictionaries : is a list of message serialize into a dictionnary if a is True
                [{
                    'id' : string : message unique id : ensure that we are not creating or executing 2 times the same message
                    'call' : string : name of the method to call when the receiver will execute the message
                    'source' : string : name of the entity that generated the message
                    'args' : string : Arguments of the call, the format is a a dictionnary that represent is object that generate the message serialiaze in json
                                         see export_data_jso in ir_model_data.py
                },..]
        """
        # doing the pull message means that the pull update is finished
        # so last_sequence can be stored
        if last_seq:
            self.pool.get('sync.server.entity').write(cr, 1, [entity.id],
                                                      {'last_sequence': last_seq}, context=context)
        res = self.pool.get('sync.server.message').get_message_packet(cr, uid,
                                                                      entity, max_packet_size, context=context)
        return (True, res, get_md5(res))

    @check_validated
    def message_received(self, cr, uid, entity, message_ids, context=None):
        """
        #### deprecated used only for migration
            @param entity: string : uuid of the synchronizing entity
            @param message_ids: list of string : The list of message identifier : ['message_uuid1', 'message_uuid2', ....]
            @return: tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : message : is an error message if a is False

        """
        if context is None:
            context = {}
        if context.get('md5'):
            check_md5(context['md5'], message_ids, _('server method message_received'))
        return (True, self.pool.get('sync.server.message').set_message_as_received(cr, 1, entity, message_uuids=message_ids, context=context))

    @check_validated
    def message_received_by_sync_id(self, cr, uid, entity, message_ids, context=None):
        """
            @param entity: string : uuid of the synchronizing entity
            @param message_ids: list of string : The list of message id
            @return: tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : message : is an error message if a is False

        """
        if context is None:
            context = {}
        if context.get('md5'):
            check_md5(context['md5'], message_ids, _('server method message_received'))
        return (True, self.pool.get('sync.server.message').set_message_as_received(cr, 1, entity, message_ids=message_ids, context=context))

    @check_validated
    def message_recover_from_seq(self, cr, uid, entity, start_seq, context=None):
        return (True, self.pool.get('sync.server.message').recovery(cr, 1, entity, start_seq, context=context))

    @check_validated
    def sync_success(self, cr, uid, entity, context=None):
        self._logger.info("::::::::[%s] success sync" % (entity.name, ))
        self.pool.get('sync.server.entity').write(cr, 1, entity.id, {'date_success_sync': fields.datetime.now()})
        return True

sync_manager()

class sync_server_monitor_email(osv.osv):
    _name = 'sync.server.monitor.email'
    _description = 'Email alert'
    _logger = logging.getLogger('sync.monitor')

    _columns = {
        'name': fields.char('Destination emails', size=1024, help='comma separated list of email addresses'),
        'title': fields.char('Title', size=1024, required=1),
        'nb_days': fields.integer('Notification threshold in days', required=1),
    }

    def check_msg_not_sync(self, cr, uid, out_file, context=None):
        PACK = 1000
        update_obj = self.pool.get('sync.server.update')
        rule_obj = self.pool.get('sync_server.sync_rule')
        group_obj = self.pool.get('sync.server.entity_group')
        entity_obj = self.pool.get('sync.server.entity')

        entities_last_activity = {}
        rules = {}
        ancestors_cache = {}
        children_cache = {}

        entities_id = entity_obj.search(cr, uid, [])
        for entity in entity_obj.read(cr, uid, entities_id, ['last_dateactivity']):
            entities_last_activity[entity['id']] = entity['last_dateactivity']
            ancestors_cache[entity['id']] = entity_obj._get_ancestor(cr, uid, entity['id'])
            children_cache[entity['id']] = entity_obj._get_all_children(cr, uid, entity['id'])

        rule_ids = rule_obj.search(cr, uid, [('active', 'in', ['t', 'f'])])
        for rule in rule_obj.browse(cr, uid, rule_ids):
            rules[rule.id] = {
                'direction': rule.direction,
                'instances': {}
            }
            if rule.applies_to_type:
                grp_ids = group_obj.search(cr, uid, [('type_id', '=', rule.type_id.id)])
            else:
                grp_ids = [rule.group_id.id]
            instances = []
            for group in group_obj.browse(cr, uid, grp_ids):
                rules[rule.id]['instances'][group.id] = [x.id for x in group.entity_ids]
        update_ids = update_obj.search(cr, uid, [])

        self._logger.info("Analyze %s data" % len(update_ids))
        i = 1
        for split_update_ids in tools.misc.split_every(PACK, update_ids, list):
            init_time = time.time()
            for update in update_obj.browse(cr, uid, split_update_ids):
                instances = rules[update.rule_id.id]['instances']

                ancestor = ancestors_cache[update.source.id]
                children = children_cache[update.source.id]

                to_retrieve = []
                if rules[update.rule_id.id]['direction'] == 'up':
                    for x in ancestor:
                        if x in tools.misc.flatten(list(instances.values())):
                            to_retrieve.append(x)
                elif rules[update.rule_id.id]['direction'] == 'down':
                    for x in children:
                        if x in tools.misc.flatten(list(instances.values())):
                            to_retrieve.append(x)
                elif rules[update.rule_id.id]['direction'] == 'bidirectional':
                    for x in instances:
                        if update.source.id in instances[x]:
                            to_retrieve = [j for j in instances[x] if j!=update.source.id]
                            break
                elif rules[update.rule_id.id]['direction'] == 'bi-private':
                    for x in instances:
                        if update.source.id in instances[x]:
                            list_to_retrieve = [j for j in instances[x] if j!=update.source.id]
                            break

                    if update.owner:
                        privates = [ x for x in ancestors_cache[update.owner.id] + [update.owner.id] if x != update.source.id]
                        to_retrieve = []
                        for x in list_to_retrieve:
                            if x in privates:
                                to_retrieve.append(x)
                    else:
                        to_retrieve = list_to_retrieve
                elif rules[update.rule_id.id]['direction'] == 'single-private':
                    if update.owner:
                        to_retrieve.append(update.owner.id)

                elif rules[update.rule_id.id]['direction'] == 'mission-private':
                    if update.owner:
                        to_retrieve = [x for x in ancestors_cache[update.owner.id] + [update.owner.id] + children_cache[update.owner.id] if x != update.source.id]

                puller_ids = [y.entity_id.id for y in update.puller_ids]
                not_pulled = []
                for need_pull in to_retrieve:
                    if need_pull in puller_ids:
                        continue
                    if entities_last_activity[need_pull] < update.create_date:
                        continue
                    not_pulled.append(need_pull)
                for x in puller_ids:
                    if x not in to_retrieve:
                        print('ERROR pulled by', x, to_retrieve, update.rule_id.id, update.id, update.sdref, update.rule_id.direction, update.owner)
                if not_pulled:
                    print(update.id, update.sdref, not_pulled, update.rule_id.direction, update.owner)
            self._logger.info("1000 lines of data analyzed in %lf seconds, %d left" % (time.time() - init_time, len(update_ids) - PACK*i))
            i += 1
        return True

    def check_not_sync(self, cr, uid, context=None):
        entity_obj = self.pool.get('sync.server.entity')
        entity_activity_obj = self.pool.get('sync.server.entity.activity')
        date_tools = self.pool.get('date.tools')

        ids = self.search(cr, uid, [('name', '!=', False)])
        if not ids:
            return False
        template = self.browse(cr, uid, ids[0])
        thresold_date = (datetime.now() + timedelta(days=-template.nb_days)).strftime('%Y-%m-%d %H:%M:%S')
        entity_to_check_ids = entity_obj.search(cr, uid, [('state', 'in', ['validated', 'updated'])])
        if not entity_to_check_ids:
            return False
        activity_ids = entity_activity_obj.search(cr, uid, [('entity_id', 'in', entity_to_check_ids), ('datetime', '<=', thresold_date)])
        if not activity_ids:
            return False
        warn_ids = []
        for act in entity_activity_obj.read(cr, uid, activity_ids, ['entity_id']):
            warn_ids.append(act['entity_id'])

        emails = template.name.split(',')
        subject = _('SYNC_SERVER: instances did not perform any sync')
        body = _('''Hello,
The sync server detected that the following instances did not perform any sync since %d days:
''') % template.nb_days

        for entity in entity_obj.browse(cr, uid, warn_ids):
            body += _("  - %s last sync: %s\n") % (entity.name, entity.last_dateactivity and date_tools.get_date_formatted(cr, uid, 'datetime', entity.last_dateactivity) or _('never'))

        body += _("\n\nThis is an automatically generated email, please do not reply.\n")

        tools.email_send(False, emails, subject, body)
        return True

sync_server_monitor_email()
