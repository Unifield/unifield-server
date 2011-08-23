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

import sync_client.rpc
import uuid
import tools
import time
import sys
import traceback

import sync_client

class test(osv.osv_memory):
    _name = "sync.client.test"
    
    
    def set_connection(self, cr, uid, name, server_db, host, port, password, max_size, context=None):
        """
            Set the connection to the server
        """
        con_obj = self.pool.get('sync.client.sync_server_connection')
        con = con_obj._get_connection_manager(cr, uid, context=None)
        con_obj.write(cr, uid, con.id, {'login' : name,
                                    'host' : host,
                                    'database' : server_db,
                                    'port' : port,
                                    'login' : name,
                                    'password' : password,
                                    'max_size' : max_size})
        con_obj.connect(cr, uid, [con.id], None)
        con = con_obj._get_connection_manager(cr, uid, context=None)
        return con.uid
    
    def activate(self, cr, uid, name, context=None):
        activate_obj = self.pool.get('sync.client.activate_entity')
        res_id = activate_obj.create(cr, uid, {'name' : name}, context=context)
        activate_obj.activate(cr, uid, [res_id], context=context)
        return self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).parent
    
    def register(self, cr, uid, name, parent_name, email, group_name_list, context=None):
        re_obj = self.pool.get('sync.client.register_entity')
        group_ids = []
        for gname in group_name_list:
            id_res = self.pool.get('sync.client.entity_group').create(cr, uid,  {'name' : gname}, context=context)
            group_ids.append(id_res)
        res_id = re_obj.create(cr, uid, {'name' : name, 
                                         'email' : email,
                                         'parent' : parent_name,
                                         'group_ids' : [(6, 0, group_ids)]}, context=context)
        re_obj.validate(cr, uid, [res_id], context=context)
        return True
    
    def activate_by_parent(self, cr, uid, child_name, context=None):
        #create wizard
        em_obj = self.pool.get("sync.client.entity_manager")
        res_id = em_obj.create(cr, uid, {'state' : 'data_needed'}, context=context)
        #retreive info 
        em_obj.retreive(cr, uid, [res_id], context=context)
        #check for child exist and validate
        wiz = em_obj.browse(cr, uid, res_id, context=context)
        for entity in wiz.entity_ids:
            if entity.name == child_name:
                return self.pool.get("sync.client.child_entity").validation(cr, uid, [entity.id], context=context)
        return False
       
    def synchronize(self, cr, uid, context=None): 
        self.pool.get('sync.client.entity').sync(cr, uid, context=context)
        return True
    
    def check_model_info(self, cr, uid, model, data, context=None):
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data.get('name'))], context=context)
        if not ids:
            return False
        
        for partner in self.pool.get(model).browse(cr, uid, ids, context=context):
            for key, value in data.items():
                if not getattr(partner, key) == value:
                    return False
        return True
    
    def create_record(self, cr, uid, model, data, context=None):
        print 'model', model
        res_id = self.pool.get(model).create(cr, uid, data, context=context)
        return res_id
    
    def write_record(self, cr, uid, model, data, context=None):
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data.get('name'))], context=context)
        if not ids:
            return False
        self.pool.get(model).write(cr, uid, ids, data)
        return True
    
    def get_record_id(self, cr, uid, model, data, context=None):
        ids = self.pool.get(model).search(cr, uid, [('name', '=', data)], context=context)
        return ids and ids[0] or False

    def delete_record(self, cr, uid, model, name, context=None):
        ids = self.pool.get(model).search(cr, uid, [('name', '=', name)], context=context)
        if not ids:
            return False
        self.pool.get(model).unlink(cr, uid, ids, context=context)
        return True
        
    def get_record_data(self, cr, uid, model, id, fields, context=None):
        return self.pool.get(model).read(cr, uid, id, fields, context=context)
        
        
                                    
test()

