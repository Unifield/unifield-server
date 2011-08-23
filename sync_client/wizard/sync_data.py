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
from datetime import datetime
import tools
import time
import pprint
from sync_client.ir_model_data import link_with_ir_model

pp = pprint.PrettyPrinter(indent=4)

from tools.safe_eval import safe_eval as eval


def log(model, cr, uid, message, ids=False, data=False, context=None):
    #more complete log system
    print("Error : " + message)
    pp.pprint(data)

class local_rule(osv.osv):
    
    _name = "sync.client.rule"
    
    _columns = {
        'server_id' : fields.integer('Server ID', required=True, readonly=True),
        'name' : fields.char('Rule name', size=64, readonly=True),
        'model' : fields.many2one('ir.model','Model', readonly=True),
        'domain' : fields.text('Domain', required = False, readonly=True),
        'sequence' : fields.integer('Sequence', readonly=True),
        'included_fields' : fields.text('Included Fields', readonly=True),
    }
    
    def save(self, cr, uid, data_list, context=None):
        self._delete_old_rules(cr, uid, context)
        for data in data_list:
            model_name = data.get('model')
            model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name)], context=context)
            if not model_id:
                log(cr, uid, "Model %s does not exist" % model_name, data=data, context=context)
                continue #do not save the rule if there is no valid model
            data['model'] = model_id[0]
            
            self.create(cr, uid, data, context=context)
                
    def _delete_old_rules(self, cr, uid, context=None):
        ids_to_unlink = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, ids_to_unlink, context=context)
        
    _order = 'sequence asc'
local_rule()

class update_to_send(osv.osv):
    """
        States : to_send : need to be send to the server or the server ack still not receive
                 sended : Ack for this update receive but session not ended
                 validated : ack for the session of the update received, this update can be deleted
    """
    _name = "sync.client.update_to_send"
    _rec_name = 'values'
    
    

    _columns = {
        'values':fields.text('Values', size=128),
        'model' : fields.many2one('ir.model','Model', readonly=True),
        'sent' : fields.boolean('Sent ?'),
        'sync_date' : fields.datetime('Start date'),
        'session_id' : fields.char('Session Id', size=128),
        'version' : fields.integer('Record Version'),
        'rule_id' : fields.many2one('sync.client.rule','Generating Rule', readonly=True, ondelete="set null"),
        'xml_id' : fields.many2one('ir.model.data', 'Synchronization information', readonly=True, ondelete="set null"),
        'fields':fields.text('Fields', size=128),
        
    }
    
    _defaults = {
        'sync_date' : lambda *a : datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        'sent' : False,
    }
    
    def create_update(self, cr, uid, rule_id, session_id, context=None):
        rule = self.pool.get('sync.client.rule').browse(cr, uid, rule_id, context=context)
        obj = self.pool.get(rule.model.model)
        
        included_fields = eval(rule.included_fields)
        if not 'id' in included_fields: 
            included_fields.append('id')
        
        if rule.domain:
            domain = eval(rule.domain)
        else:
            domain = []
        ids = obj.search(cr, uid, domain, context=context)
        for id in ids:
            xml_id = link_with_ir_model(obj, cr, uid, id, context=context)
            if not obj.need_to_push(cr, uid, id, included_fields, context=context):
                continue
            
            print "create update for ", id, " model", rule.model.model
            values = obj.export_data(cr, uid, [id], included_fields, context=context)['datas'][0]
            data = {
                'session_id' : session_id,
                'values' : tools.ustr(values),
                'model' : rule.model.id,
                'version' : obj.version(cr, uid, id, context=context) + 1,
                'rule_id' : rule.id,
                'xml_id' : xml_id,
                'fields' : tools.ustr(included_fields),
            }
            self.create(cr,uid, data, context=context)
            
    def create_package(self, cr, uid, session_id, packet_size, context=None):
        ids = self.search(cr, uid, [('session_id', '=', session_id), ('sent', '=', False)], limit=packet_size, context=context)
        if not ids:
            return False
        update_master = self.browse(cr, uid, ids[0], context=context)
        data = {  
            'session_id' : update_master.session_id,
            'model' : update_master.model.model,
            'rule_id' : update_master.rule_id.server_id,
            'fields' : update_master.fields,
            
        }
        ids_in_package = []
        values = []
        for update in self.browse(cr, uid, ids, context=context):
            #only update from the same rules in the same package
            if update.rule_id.server_id != data['rule_id']:
                break
            values.append({'version' : update.version,
                           'values' : update.values,
                           })
            ids_in_package.append(update.id)
        data['load'] = values
        #for update in 
        return (ids_in_package, data)
    
    def sync_finished(self, cr, uid, update_ids, context=None):
        model_data_pool = self.pool.get('ir.model.data')
        
        for update in self.browse(cr, uid, update_ids, context=context):
            model_data_pool.write(cr, uid, update.xml_id.id, {'sync_date' : update.sync_date, 'version' : update.version})
        self.write(cr, uid, update_ids, {'sent' : True}, context=context)    
        
        
    _order = 'id asc'
update_to_send()

class update_received(osv.osv):

    _name = "sync.client.update_received"
    _rec_name = 'source'

    _columns = {
        'source': fields.char('Source entity', size=128, readonly=True), 
        'model' : fields.many2one('ir.model','Model', readonly=True),
        'sequence' : fields.integer('Sequence', readonly=True),
        'version' : fields.integer('Record Version', readonly=True),
        'fields' : fields.text("Fields", readonly=True),
        'values' : fields.text("Values", readonly=True),
        'run' : fields.boolean("Run", readonly=True),
        'log' : fields.text("Execution Messages", readonly=True),
        'fallback_values':fields.text('Fallback values', readonly=True),
    }
    
    def unfold_package(self, cr, uid, packet, context=None):
        if not packet:
            return 0
        model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', packet['model'])], context=context)
        if not model_id:
                log(self, cr, uid, "Model %s does not exist" % packet['model'], data=packet, context=context)
        data = {
            'source' : packet['source_name'],
            'model' : model_id[0],
            'fields' : packet['fields'],
            'sequence' : packet['sequence'],
            'fallback_values' : packet['fallback_values'],
        }
        for load_item in packet['load']:
            data.update({
                'version' : load_item['version'],
                'values' : load_item['values']
            })
            self.create(cr, uid, data ,context=context)
        
        
        return len(packet['load'])
    
    def execute_update(self, cr, uid, context=None):
        update_ids = self.search(cr, uid, [('run', '=', False)], context=context)
        for update in self.browse(cr, uid, update_ids, context=context):
            self.single_update_execution(cr, uid, update, context)
            
    def single_update_execution(self, cr, uid, update, context=None):
        message = []
        #1 conflict detection
        #2 if conflict => manage conflict according rules : report conflict and how it's solve
        if self._conflict(cr, uid, update, context):
            message.append("conflict : conflict detected")
            log(self, cr, uid, "Conflict detected", ids=False, data=[update.fields, update.values], context=context)
            #TODO manage other conflict rules here
                
        values = eval(update.values)
        fields = eval(update.fields)
        fallback = update.fallback_values and eval(update.fallback_values) or {}
            
        #3 check for missing field : report missing fields
        bad_fields = self._check_fields(cr, uid, update.model.model, fields, context=context)
        if bad_fields : 
            message.append("Missing or unauthorized fields found : " + ", ".join(bad_fields))
        fields, values = self._remove_bad_fields_values(fields, values, bad_fields)
            
        #4 check for fallback value : report missing fallback_value
        values = self._check_and_replace_missing_id(cr, uid, values, fields, fallback, message, context=context)
            
        #5 import data : report error
        try:
            res = self.pool.get(update.model.model).import_data(cr, uid, fields, [values], mode='update', current_module='sd', noupdate=True, context=context)
            if res and res[2]:
                message.append(res[2])
            run = True
        except Exception, e:
            message.append(str(e))
            run = False
            
        #6 set version and sync_date
        try:
            xml_id = values[fields.index('id')]
            self.pool.get('ir.model.data').sync(cr, uid, xml_id, version=update.version, context=context)
        except ValueError, e:
            message.append(str(e))
                
        message_str = "\n".join(message)
        self.write(cr, uid, update.id, {'run' : run, 'log' : message_str}, context=context)
    
    def run(self, cr, uid, ids, context=None):
        for update in self.browse(cr, uid, ids, context=context):
            self.single_update_execution(cr, uid, update, context)
            
    def _check_fields(self, cr, uid, model, fields, context=None):
        """
            @return  : the list of unknown fields or unautorized field
        """
        bad_field = []
        fields_ref = self.pool.get(model).fields_get(cr, uid, context=context)
        for field in fields:
            if field == "id":
                continue
            if '.id' in field:
                bad_field.append(field)
                continue
            
            part = field.split('/')
            if len(part) > 2 or (len(part) == 2 and part[1] != 'id') or not fields_ref.get(part[0]):
                bad_field.append(field)
        
        return bad_field
         
    def _remove_bad_fields_values(self, fields, values, bad_fields):
        for bad_field in bad_fields:
            i = fields.index(bad_field)
            fields.pop(i)
            values.pop(i)
        
        return (fields, values)
    
    def _conflict(self, cr, uid, update, context=None):
        values = eval(update.values)
        fields = eval(update.fields)
        xml_id = values[fields.index('id')]
        ir_data = self.pool.get('ir.model.data').get_ir_record(cr, uid, xml_id, context=context)
        if not ir_data: #no ir.model.data => no record in db => no conflict
            return False
        if not ir_data.sync_date: #never synced => conflict
            return True
        if not ir_data.last_modification: #never modified not possible but just in case
            return False
        if ir_data.sync_date < ir_data.last_modification: #modify after synchro conflict
            return True
        if update.version <= ir_data.version: #not a higher version conflict
            return True
        return False
    
    def _check_and_replace_missing_id(self, cr, uid, values, fields, fallback, message, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        for i in xrange(0, len(fields)):
            if '/id' in fields[i]:
                xml_id = values[i]
                if xml_id and not ir_model_data_obj.get_record(cr, uid, xml_id, context=context):
                    fb = fallback.get(fields[i])
                    if fb and ir_model_data_obj.get_record(cr, uid, fb, context=context):
                        message.append('Missing record %s replace by %s' % (fields[i], fb))
                        values[i] = fb
                    else:
                        message.append('Missing record %s and no fallback value defined or missing fallback value, set to False' % fields[i])
                        values[i] = False
        return values
                 
        
            
            
    _order = 'id asc'
update_received()






