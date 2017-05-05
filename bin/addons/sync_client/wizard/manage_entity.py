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
from osv import orm
from tools.translate import _

import logging
from sync_common import sync_log

class entity_manager(osv.osv_memory):
    _name = "sync.client.entity_manager"
    _description = "Wizard invalidate and more"
    _logger = logging.getLogger('sync.client')
    
    _columns = {
        'entity_ids' : fields.one2many('sync.client.child_entity', 'manage_id', 'Children Instances'),
        'state' : fields.selection([('data_needed','Need Data'),('ready','Ready')], 'State', required=True),
        'entity_status' : fields.char("Instance Status", size=64, readonly=True),
        'group' : fields.char("Groups", size=2048, readonly=True),
        'email' : fields.char("Contact E-mail", size=64, readonly=True),
        'parent' : fields.char("Parent", size=64, readonly=True),
        'identifier' : fields.char("Identifier", size=64, readonly=True),
        'name' : fields.char("Identifier", size=64, readonly=True),
    }
    
    def retrieve(self, cr, uid, ids, context=None):
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context).identifier
        hardware_id = self.pool.get('sync.client.entity')._hardware_id
        try:
            res = proxy.get_entity(uuid, hardware_id, context)
            if res and not res[0]: raise StandardError, res[1]
            my_infos = res[1]
            res = proxy.get_children(uuid, hardware_id, context)
            if res and not res[0]: raise StandardError, res[1]
            my_infos.update({'entity_ids' : [(0,0, data) for data in res[1]], 'state' : 'ready' })
        except StandardError, e:
            sync_log(self, e, 'error')
            raise osv.except_osv(_('Error !'), res[1])
        else:
            self.write(cr, uid, ids, my_infos, context=context)
        return True 
        
    _defaults = { 
        'state' : 'data_needed',
    }
    
    
entity_manager()   
    
    
class child_entity(osv.osv_memory):
    _name = "sync.client.child_entity"
    _description = "Representation of a child entity for the parent"
    
    
    _columns = {
        'name': fields.char('Instance Name', size=64, readonly=True, required=True),
        'identifier': fields.char('Identifier', size=64, readonly=True), 
        'parent': fields.char('Parent Instance', size=64, readonly=True),
        'email' : fields.char('Contact Email', size=512, readonly=True),
        'state' : fields.selection([('pending','Pending'),('validated','Validated'), ('updated', 'Updated'), ('invalidated','Invalidated')], 'State', required=True),
        'manage_id' : fields.many2one('sync.client.entity_manager','Instance Manager'), 
        'group': fields.text('Group Name', size=512, readonly=True),     
    
    }
    
    def validation(self, cr, uid, ids, context=None):
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context).identifier
        hardware_id = self.pool.get('sync.client.entity')._hardware_id
        uuid_validate = [] 
        for entity in self.browse(cr, uid, ids, context=context):
            uuid_validate.append(entity.identifier)
        
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        res = proxy.validate(uuid, hardware_id, uuid_validate, context)
        if res and res[0]:
            self.write(cr, uid, ids, {'state' : 'validated'}, context=context)
        elif res and not res[0]:
            raise osv.except_osv(_('Error !'), res[1])
        return True
    
    def invalidation(self, cr, uid, ids, context=None):
        uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context).identifier
        hardware_id = self.pool.get('sync.client.entity')._hardware_id
        uuid_validate = [] 
        for entity in self.browse(cr, uid, ids, context=context):
            uuid_validate.append(entity.identifier)
        
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
        res = proxy.invalidate(uuid, hardware_id, uuid_validate, context)
        if res and res[0]:
            self.write(cr, uid, ids, {'state' : 'invalidated'}, context=context)
        elif res and not res[0]:
            raise osv.except_osv(_('Error !'), res[1])
        return True
    
child_entity()
