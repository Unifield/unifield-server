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
import uuid
import tools
import pprint
pp = pprint.PrettyPrinter(indent=4)

def check_validated(f):
    def check(self, cr, uid, uuid, *args, **kargs):
        entity_pool = self.pool.get("sync.server.entity")
        id = entity_pool.get(cr, uid, uuid=uuid)
        if not id:
            return (False, "Error: entity does not exist in the server database")
        entity = entity_pool.browse(cr, uid, id)[0]
        if entity.state == 'updated':
            return (False, 'This entity has been updated and the update procedure has to be launched at your side')
        if not (entity.state == 'validated' and entity.user_id.id == uid):
            return (False, "Error: entity has not been validated yet by the parent")
        return f(self, cr, uid, entity, *args, **kargs)
        
    return check

class entity_group0(osv.osv):
    """ OpenERP group of entities """
    _name = "sync.server.entity_group"
entity_group0()

class entity0(osv.osv):
    _name = "sync.server.entity"
entity0()

class group_type(osv.osv):
    """ OpenERP type of group of entities """
    
    _name = "sync.server.group_type"
    _description = "Synchronization Instance Group Type"

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

    _columns = {
        'name': fields.char('Group Name', size = 64, required=True),
        'entity_ids': fields.many2many('sync.server.entity', 'sync_entity_group_rel', 'group_id', 'entity_id', string="Instances"),
        'type_id': fields.many2one('sync.server.group_type', 'Group Type', ondelete="set null", required=True),
    }
    
    def get_group_name(self, cr, uid, context=None):
        ids = self.search(cr, uid, [], context=context)
        res = []
        for group in self.browse(cr, uid, ids, context=context):
            res.append({'name': group.name, 'type': group.type_id.name})
        return res
     
    def get(self, cr, uid, name, context=None):
        return self.search(cr, uid, [('name', '=', name)], context=context)
    
    #Check that the group has an unique name
    _sql_constraints = [('unique_name', 'unique(name)', 'Group name must be unique')]
    
entity_group()

class entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _name = "sync.server.entity"
    _description = "Synchronization Instance"

    _columns = {
        'name':fields.char('Instance Name', size=64, required=True),
        'identifier':fields.char('Identifier', size=64, readonly=True),
        'parent_id':fields.many2one('sync.server.entity', 'Parent Instance', ondelete='set null', ),
        'group_ids':fields.many2many('sync.server.entity_group', 'sync_entity_group_rel', 'entity_id', 'group_id', string="Groups"),
        'state' : fields.selection([('pending', 'Pending'), ('validated', 'Validated'), ('invalidated', 'Invalidated'), ('updated', 'Updated')], 'State'),
        'email':fields.char('Contact Email', size=512),
        'user_id': fields.many2one('res.users', 'User', ondelete='restrict', required=True),
        
        #just in case, since the many2one exist it has no cost in database
        'children_ids' : fields.one2many('sync.server.entity', 'parent_id', 'Children Instances'),
        'update_token' : fields.char('Update security token', size=256)
    }
    
    def get_security_token(self):
        return uuid.uuid4().hex
    
    def _check_duplicate(self, cr, uid, name, uuid, context=None):
        duplicate_id = self.search(cr, uid, [('user_id', '!=', uid), '|', ('name', '=', name), ('identifier', '=', uuid)], context=context)
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
        def _get_children_rec(entity, child_list):
            if entity and entity.children_ids:
                for child in entity.children_ids:
                    child_list.append(child.id)
                    _get_children_rec(child, child_list)
            return child_list

        entity = self.browse(cr, uid, id, context=context)
        return _get_children_rec(entity, [])
    
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
    def activate_entity(self, cr, uid, name, identifier, context=None):
        """
            Allow to change uuid,
            and reactivate the link between an local instance and his data on the server
        """
        ids = self.search(cr, uid, [('user_id', '=', uid), ('name', '=', name), ('state', '=', 'updated')], context=context)
        if not ids:
            return (False, 'No entity matches with this name')
        
        token = uuid.uuid4().hex
        self.write(cr, 1, ids, {'identifier': identifier, 'update_token': token}, context=context)
        entity = self.browse(cr, uid, ids, context=context)[0]
        groups = [group.name for group in entity.group_ids]
        data = {
                'name': entity.name,
                'parent': entity.parent_id.name,
                'email': entity.email,
                'groups': groups,
                'security_token': token,
        }
        return (True, data)
    
    def update(self, cr, uid, identifier, context=None):
        ids = self.search(cr, uid, [('identifier', '=' , identifier), ('user_id', '=', uid), ('state', '=', 'updated')], context=context)
        if not ids:
            return (False, 'No update is ready for your entity. If you cannot synchronize data, check that your parent has validated your registration')
        
        token = uuid.uuid4().hex
        self.write(cr, 1, ids, {'update_token' : token}, context=context)
        entity = self.browse(cr, uid, ids, context=context)[0]
        groups = [group.name for group in entity.group_ids]
        data = {
                'name': entity.name,
                'parent': entity.parent_id.name,
                'email': entity.email,
                'groups': groups,
                'security_token': token,
        }
        return (True, data)
    
    def ack_update(self, cr, uid, uuid, token, context=None):
        ids = self.search(cr, uid, [('identifier', '=' , uuid), ('user_id', '=', uid), ('state', '=', 'updated'), ('update_token', '=', token)], context=context)
        if not ids:
            return (False, 'Ack not valid')
        self.write(cr, 1, ids, {'state' : 'validated'}, context=context)
        return (True, "Instance Validated")
    
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}
        update = context.get('update', False)
        
        if update:
            vals['state'] = 'updated'
            
        return super(entity, self).write(cr, uid, ids, vals, context=context)
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        update = context.get('update', False)
        
        if update:
            vals['state'] = 'updated'
            
        return super(entity, self).create(cr, uid, vals, context=context)
        
    def register(self, cr, uid, data, context=None):
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
    def validate(self, cr, uid, entity, uuid_list, context=None):
        if not self._check_children(cr, uid, entity, uuid_list, context=context):
            return (False, "Error: One of the entity you want to validate is not one of your children")
        ids_to_validate = self.search(cr, uid, [('identifier', 'in', uuid_list)], context=context)
        self.write(cr, 1, ids_to_validate, {'state': 'validated'}, context=context)
        self._send_validation_email(cr, uid, entity, ids_to_validate, context=context)
        return (True, "Instance %s are now validated" % ", ".join(uuid_list))
    
    @check_validated
    def invalidate(self, cr, uid, entity, uuid_list, context=None):
        if not self._check_children(cr, uid, entity, uuid_list, context=context):
            return (False, "Error: One of the entity you want validate is not one of your children")
        ids_to_validate = self.search(cr, uid, [('identifier', 'in', uuid_list)], context=context)
        self.write(cr, 1, ids_to_validate, {'state': 'invalidated'}, context=context)
        self._send_invalidation_email(cr, uid, entity, ids_to_validate, context=context)
        return (True, "Instance %s are now invalidated" % ", ".join(uuid_list))
        
    def validate_action(self, cr, uid, ids, context=None):
        if not context:
            context = {}
            
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
    
    _constraints = [
        (_check_recursion, 'Error! You cannot create cycle in entities structure.', ['parent_id']),
    ]
entity()


class sync_manager(osv.osv):
    _name = "sync.server.sync_manager"
    
    
    """
        Data synchronization
    """
    def _generate_session_id(self):
        return uuid.uuid4().hex
    
    @check_validated
    def get_model_to_sync(self, cr, uid, entity, context=None):
        """
            Initialize a Push session, send the session id and the list of rule
            @param entity: string : uuid of the synchronizing entity
            @return tuple : (a, b, c):
                    a is True is if the call is succesfull, False otherwise
                    b : if a is False, b is the error message
                        if a is True b is the synchronization session_id
                    c : is a list of dictionaries that contains all the rule 
                        that apply for the synchronizing instance.
                        The format of the dict that contains a single rule definition
                        {
                            'server_id' : integer : id of the rule server side,
                            'name' : string : Name of the rule,
                            'model' : string : Name of the model on which the rule applies,
                            'domain' : string : The domain to filter the record to synchronize, format : standard domain [(),()]
                            'sequence_number' : integer : Sequence number of the rule,
                            'included_fields' : string : list of fields to include, same format as the one needed for export data
                        }
                    
        """
        res = self.pool.get('sync_server.sync_rule')._get_rule(cr, uid, entity, context=context)
        return (True, self._generate_session_id(), res[1])
        
    @check_validated
    def receive_package(self, cr, uid, entity, packet, context=None):
        """
            Synchronizing entity sending it's packet to the sync server.
            @param entity : string : uuid of the synchronizing entity
            @param packet : list of dictionaries : List of update to send to the server, a pakcet contains at max all the update generate by the same rule
                            format :
                            {
                                'session_id': string : id of the push session, given by get_model_to_sync,
                                'model': string : model's name of the update,
                                'rule_id': integer : server_side rule's id given,
                                'fields': string : list of fields to include, format : a list of string, same format as the one needed for export data
                                'load' : list of dictionaries : content of the packet, it the list of values and version
                                        format [{
                                                    'version' : integer : version of the update
                                                    'values' : string : list of values in the matching order of fields
                                                             format "['value1', 'value2']"
                                                }, ...]
                            
                            }
            @return: tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : string : is an error message if a is False
        """
        res = self.pool.get("sync.server.update").unfold_package(cr, 1, entity, packet, context=context)
        return (True, res)
            
    @check_validated
    def confirm_update(self, cr, uid, entity, session_id, context=None):
        """
            Synchronizing entity confirm that all the packet of this session are sent
            @param entity: string : uuid of the synchronizing entity
            @param session_id: string : the synchronization session_id given at the begining of the session by get_model_sync.
            @return tuple : (a, b) 
                a : boolean : is True is if the call is succesfull, False otherwise
                b : string : an infromative message
        """
        return self.pool.get("sync.server.update").confirm_updates(cr, 1, entity, session_id, context=context)

    
    @check_validated
    def get_max_sequence(self, cr, uid, entity, context=None):
        """
            Give to the synchronizing client the sequence of the last complete push, the pull session will pull until this sequence.
            @param entity: string : uuid of the synchronizing entity
            @return a tuple (a, b)
                a : boolean :is True is if the call is succesfull, False otherwise
                b : integer : is the sequence number of the last successfull push session by any entity
        
        """
        return (True, self.pool.get('sync.server.update').get_last_sequence(cr, uid, context=context))
    
    @check_validated
    def get_update(self, cr, uid, entity, last_seq, offset, max_size, max_seq, context=None):
        """
            @param entity: string : uuid of the synchronizing entity
            @param last_seq: integer : Last sequence of update receive succefully in the previous pull session. 
            @param offset: integer : Number of record receive after the last_seq
            @param max_size: integer : The number of record max per packet. 
            @param max_seq: interger : The sequence max that the update the sync server send to the client in get_max_sequence, to tell the server don't send me
                            newer update then the one already their when the pull session start.
            @return tuple :(a,b,c) 
                a : boolean : True if the call is successfull, False otherwise
                b : list of dictionaries : Package if there is some update to send remaining, False otherwise
                c : boolean : False if there is some update to send remaining, True otherwise
                              Package format : 
                              {
                                    'model': string : model's name of the update
                                    'source_name' : string : source entity's name
                                    'fields' : string : list of fields to include, format : a list of string, same format as the one needed for export data
                                    'sequence' : update's sequence number, a integer
                                    'fallback_values' : update_master.rule_id.fallback_values
                                    'load' : a list of dict that contain record's values and record's version
                                            [{
                                                'version' : int version of the update
                                                'values' : string : list of values in the matching order of fields
                                                             format "['value1', 'value2']"
                                            }, ..]
                              }
                              
        """
        package = self.pool.get("sync.server.update").get_package(cr, uid, entity, last_seq, offset, max_size, max_seq, context)
        if not package:
            return (True, False, True)
        return (True, package, False)
    
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
        return (True, res)
    
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
        return self.pool.get('sync.server.message').unfold_package(cr, 1, entity, packet, context=context)

    @check_validated
    def get_message(self, cr, uid, entity, max_packet_size, context=None):
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
        
        res = self.pool.get('sync.server.message').get_message_packet(cr, uid, entity, max_packet_size, context=context)
        return (True, res)
        
    @check_validated
    def message_received(self, cr, uid, entity, message_ids, context=None):
        """
            @param entity: string : uuid of the synchronizing entity
            @param message_ids: list of string : The list of message identifier : ['message_uuid1', 'message_uuid2', ....]
            @return: tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : message : is an error message if a is False
              
        """
        return (True, self.pool.get('sync.server.message').set_message_as_received(cr, 1, entity, message_ids, context=context))

sync_manager()

