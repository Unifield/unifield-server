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
from tools.translate import _

class client_entity_group(osv.osv_memory):
    """ OpenERP group of entities """
    
    _name = "sync.client.entity_group"
    _description = "Synchronization Entity Group"

    _columns = {
        'name':fields.char('Group Name', size=64, required=True, readonly=True),
        'type':fields.char('Group Type', size=64, readonly=True),
        'entity_ids':fields.many2many('sync.client.register_entity','sync_entity_group_rel','group_id','entity_id', string="Entities"),         
    }
    
    def set_group(self, cr, uid, data_list, context=None):
        for data in data_list:
            ids = self.search(cr, uid, [('name', '=', data['name'])], context=context)
            if ids:
                self.write(cr, uid, ids, data, context=context)
            else:
                self.create(cr, uid, data, context=context)
                
    
client_entity_group()

class register_entity(osv.osv_memory):
    """ OpenERP entity name and unique identifier """
    
    _name = "sync.client.register_entity"
    _description = "Synchronization Entity"

    _columns = {
        'name':fields.char('Entity Name', size=64, required=True),
        'message' : fields.text('Message'),
        'max_size' : fields.integer("Max Packet Size"),
        'parent':fields.char('Parent Entity', size=64),
        'email' : fields.char('Contact Email', size=256, required=True),
        'identifier':fields.char('Identifier', size=64, readonly=True), 
        'group_ids':fields.many2many('sync.client.entity_group','sync_entity_group_rel','entity_id','group_id',string="Groups"), 
        'state':fields.selection([('register','Register'),('parents','Parents'),('groups','Groups'), ('message', 'Message')], 'State', required=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        values = super(register_entity, self).default_get(cr, uid, fields, context)
        proxy = self.pool.get('sync.client.entity')
        entity = proxy.get_entity(cr, uid, context=context)
        
        values.update({
                'identifier': entity.identifier,
                'name': entity.name or cr.dbname,
                'parent' : entity.parent,
                'email' : entity.email,
            })
        
        return values
    
    _defaults = {
        'state' : 'register',
        'max_size' : 5,
    }
    
    def previous(self, cr, uid, ids, state, context=None):
        map = {'parents' : 'register',
               'groups' : 'parents',
               'message' : 'groups'}
        
        for id in ids:
            state = self.browse(cr, uid, id, context=context).state
            self.write(cr, uid, [id], {'state' : map[state]}, context=context)
        return True
    
    def next(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state' : 'parents'}, context=context)
        return True
    
    def group_state(self, cr, uid, ids, context=None):
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity_group")
        res = proxy.get_group_name(context)
        if res:
            self.pool.get("sync.client.entity_group").set_group(cr, uid, res, context=context)
        self.write(cr, uid, ids, {'state' : 'groups'}, context=context)
        return True
    
    def validate(self, cr, uid, ids, context=None):
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        for entity in self.browse(cr, uid, ids, context=context):
            data = {'name' : entity.name,
                    'parent_name' : entity.parent,
                    'identifier' : entity.identifier,
                    'email' : entity.email,
                    'group_names' : [group.name for group in entity.group_ids],
                    }
            res = proxy.register(data, context)
        if res and res[0]:
            self.save_value(cr, uid, ids, context)
            self.write(cr, uid, ids, {'message' : res[1], 'state' : 'message'})
        elif res and not res[0]:
            raise osv.except_osv(_('Error !'), res[1])
        
        return True  
    
    def save_value(self, cr, uid, ids, context=None):
        cur = self.browse(cr, uid, ids, context=context)[0] 
        entity = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
        data = { 
                'identifier' : cur.identifier, 
                'name' : cur.name,
                'parent' : cur.parent,
                'email' : cur.email,
                'max_size' : cur.max_size,
            }
        self.pool.get('sync.client.entity').write(cr, uid, [entity.id], data, context=context )
    
    def generate_uuid(self, cr, uid, ids, context=None):
        uuid = self.pool.get('sync.client.entity').generate_uuid()
        self.write(cr, uid, ids, {"identifier" : uuid}, context=context) 
        return True 
    
register_entity()



class update_entity(osv.osv_memory):
    _name = "sync.client.update_entity"
    
    def get_update(self, cr, uid, ids, context=None):
        entity_obj = self.pool.get('sync.client.entity') 
        entity = entity_obj.get_entity(cr, uid, context=context)
        uuid = entity.identifier
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        res = proxy.update(uuid, context)
        if res and not res[0]:
            raise osv.except_osv(_('Error !'), res[1])
        if res and res[0]:
            security = res[1]['security_token']
            entity_obj.write(cr, uid, [entity.id], {
                'name' : res[1]['name'],
                'parent': res[1]['parent'],
                'email' : res[1]['email']}, context=context)
            print "groups", res[1]['groups']
            res = proxy.ack_update(uuid, security, context)
            if res and not res[0]:
                raise osv.except_osv(_('Error !'), res[1])
        return True
    
    
update_entity()

class activate_entity(osv.osv_memory):
    _name = "sync.client.activate_entity"
    
    _columns = {
        'name' : fields.char("Entity Name", size=64, required=True)      
    }
    
    def activate(self, cr, uid, ids, context=None):
        entity_obj = self.pool.get('sync.client.entity') 
        uuid = entity_obj.generate_uuid()
        entity = entity_obj.get_entity(cr, uid, context=context)
        current = self.browse(cr, uid, ids, context=context)[0]
        name = current.name
        if not name:
            raise osv.except_osv(_('Error !'), _('Entity name cannot be empty'))
        
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        res = proxy.activate_entity(name, uuid, context)
        if res and not res[0]:
            raise osv.except_osv(_('Error !'), res[1])
        if res and res[0]:
            security = res[1]['security_token']
            entity_obj.write(cr, uid, [entity.id], {
                'name' : res[1]['name'],
                'parent': res[1]['parent'],
                'email' : res[1]['email'], 
                'identifier' : uuid}, context=context)
            print "groups", res[1]['groups']
            res = proxy.ack_update(uuid, security, context)
            if res and not res[0]:
                raise osv.except_osv(_('Error !'), res[1])
        return True
        
        
activate_entity()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

