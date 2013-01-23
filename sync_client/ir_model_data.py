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

MODELS_TO_IGNORE=[
                    'ir.actions.wizard',
                    'ir.actions.act_window.view',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.actions.act_window.view',
                    'ir.actions.wizard',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.ui.view',
                    'ir.sequence',
                    'ir.actions.url',
                    'ir.values',
                    'ir.report.custom.fields',
                    'ir.cron',
                    'ir.actions.report.xml',
                    'ir.property',
                    'ir.actions.todo',
                    'ir.sequence.type',
                    'ir.actions.act_window',
                    'ir.module.module',
                    'ir.ui.view',
                    'ir.module.repository',
                    'ir.model',
                    'ir.model.data',
                    'ir.model.fields',
                    'ir.model.access',
                    'ir.ui.view_sc', 
                    'ir.config_parameter',
                    
                    'sync.monitor',
                    'sync.client.rule',
                    'sync.client.push.data.information',  
                    'sync.client.update_to_send', 
                    'sync.client.update_received', 
                    'sync.client.entity',         
                    'sync.client.sync_server_connection', 
                    'sync.client.message_rule',
                    'sync.client.message_to_send',
                    'sync.client.message_received',
                    'sync.client.message_sync',  
                    'sync.client.write_info',
                    
                    'sync.server.test',
                    'sync_server.version.manager',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.group_type',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.sync_manager',
                    'sync_server.sync_rule',
                    'sync_server.message_rule',
                    'sync_server.sync_rule.forced_values',
                    'sync_server.sync_rule.fallback_values',
                    'sync_server.rule.validation.message',
                    'sync.server.update',
                    'sync.server.message',
                    'sync_server.version',

                    'res.widget',
                    
                    #'res.currency'
                  ]

XML_ID_TO_IGNORE = [
                'main_partner',
                'main_address',
                'main_company', 
                    ]

from osv import osv
from osv import fields
from tools.translate import _
import logging

from osv.orm import *
from datetime import datetime

import pprint
pp = pprint.PrettyPrinter(indent=4)

from tools.safe_eval import safe_eval as eval

class write_info(osv.osv):
    
    _logger = logging.getLogger('sync.client')
    
    _name = 'sync.client.write_info'
    
    _rec_name = 'fields_modif'
    
    _columns= {
        'create_date' :fields.datetime('Create Date', select=1),
        'model' : fields.char('model', size=64, select=1),
        'res_id' : fields.integer('Ressource Id', select=1),
        'fields_modif' : fields.text('Fields Modified'),
    }
    
    def purge(self, cr, uid, context=None):
        self._logger.info("Start purging write_info....")
        cr.execute("DELETE FROM sync_client_write_info WHERE NOT id IN (SELECT MAX(id) FROM sync_client_write_info GROUP BY model, res_id, fields_modif)")
        self._logger.info("Number of purged rows: %d" % cr.rowcount)
        return True

    def get_last_modification(self, cr, uid, model_name, res_id, last_sync, context=None):
        ids = self.search(cr, uid, [('res_id', '=', res_id), ('model', '=', model_name), ('create_date', '>', last_sync)], context=context)
        if not ids:
            return set()
        field_set = set()
        for data in self.read(cr, uid, ids, ['fields_modif'], context=context):
            field_set.update(eval(data['fields_modif']))
        return field_set
        
    def log_write(self, cr, uid, model_name, res_id, values, context=None):
        field = [key for key in values.keys()]
        read_res = self.pool.get(model_name).read(cr, uid, res_id, field, context=context)
        if not read_res: 
            self._logger.warning("No read res found for model %s id %s" % (model_name, res_id))
            return
        real_modif_field = []
        for k, val in read_res.items():
            #TODO
            #if k in field and (not isinstance(values[k], list) or values[k]):
            #    print "####", val, '!=', values[k], type(val), type(values[k])
            if k in field and (not isinstance(values[k], list) or values[k]) and val != tools.ustr(values[k]):
                real_modif_field.append(k)
        if real_modif_field:
            self.create(cr, uid, {'model' : model_name, 'res_id' : res_id, 'fields_modif' : str(real_modif_field)}, context=context )
        
    def delete_old_log(self, cr, uid, model_name, res_id, sync_date, context=None):
        ids = self.search(cr, uid, [('res_id', '=', res_id), ('model', '=', model_name), ('create_date', '<', sync_date)], context=context)
        if ids:
            self.unlink(cr, uid, ids, context=context)
write_info()     
        
class ir_model_data_sync(osv.osv):
    """ ir_model_data with sync date """

    _inherit = "ir.model.data"
    
    _columns={
        'sync_date':fields.datetime('Last Synchronization Date'),
        'version':fields.integer('Version'),
        'last_modification':fields.datetime('Last Modification Date'),
    }
    
    _defaults={
        'version' : 1
    }
    
    def _auto_init(self,cr,context=None):
        res = super(ir_model_data_sync, self)._auto_init(cr,context=context)
        ids = self.search(cr, 1, [('model', 'not in', MODELS_TO_IGNORE), ('module', '!=', 'sd'), ('name', 'not in', XML_ID_TO_IGNORE)], context=context)
        for rec in self.browse(cr, 1, ids):
            name = "%s_%s" % (rec.module, rec.name)
            res_ids = self.search(cr, 1, [('module', '=', 'sd'), ('name', '=', name)] )
            if res_ids:
                continue
            args = {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'model' :rec.model,
                    'module' : 'sd',#model._module,
                    'name' : name,
                    'res_id' : rec.res_id,
                    }
            self.create(cr, 1, args)
        return res
    
    def create(self,cr,uid,values,context=None):
        res_id = super(ir_model_data_sync, self).create(cr, uid, values, context=context)
        if values.get('module') and values.get('module') != 'sd':
            name = "%s_%s" % (values.get('module'), values.get('name'))
            duplicate_ids  = super(ir_model_data_sync, self).search(cr, uid, [('module', '=', 'sd'), ('name', '=', name)], context=context)
            if duplicate_ids:
                record = self.get_record(cr, uid, 'sd.' + name, context)
            args = {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'model' : values.get('model'),
                    'module' : 'sd',#model._module,
                    'name' : name,
                    'res_id' : duplicate_ids and record or values.get('res_id'),
                    }
            
            if duplicate_ids:
                super(ir_model_data_sync, self).write(cr, uid, duplicate_ids, args, context=context)
            else:
                super(ir_model_data_sync, self).create(cr, uid, args, context=context)
    
        return res_id

    def get(self, cr, uid, model, ids, context=None):
        res_type = type(ids)
        ids = ids if isinstance(ids, (tuple, list)) else [ids]
        result = list()
        for id in ids:
            data_ids = self.search(cr, uid, [('model', '=', model._name), ('res_id', '=', id), ('module', '=', 'sd')], limit=1, context=context)
            result.append(data_ids[0] if data_ids else False)
        return result if issubclass(res_type, (list, tuple)) else result[0]
    
    def get_record(self, cr, uid, xml_id, context=None):
        ir_record = self.get_ir_record(cr, uid, xml_id, context=context)
        if not ir_record:
            return False
        model = ir_record.model
        id = ir_record.res_id
        obj = self.pool.get(model)
        #check if record properly exist in the database
        cr.execute("select id from %s where id = %s;" % (obj._table, id))
        return id if cr.fetchone() else False

    def get_ir_record(self, cr, uid, xml_id, context=None):
        xml_id_split = xml_id.split('.')
        if len(xml_id_split) > 2:
            return False
        if len(xml_id_split) == 1:
            module = ''
            name = xml_id_split[0]
        else:
            module = xml_id_split[0]
            name = xml_id_split[1]
         
        ids = self.search(cr, uid, [('name', '=', name), ('module', '=', module)], limit=1, context=context)
        if ids: 
            return self.browse(cr, uid, ids[0], context=context)
        return False
    
    def need_to_push(self, cr, uid, ids, included_fields, context=None):
        if not ids:
            return ids
        get_last_modification = self.pool.get('sync.client.write_info').get_last_modification
        watch_fields = set(self._clean_included_fields(cr, uid, included_fields))
        res_type = type(ids)
        ids = filter(bool, (ids if isinstance(ids, (tuple, list)) else [ids]))
        result = filter(
            lambda rec: (not rec.sync_date or \
                         watch_fields & get_last_modification(cr, uid, rec.model, rec.res_id, rec.sync_date, context=context)), \
            self.browse(cr, uid, ids, context=context) )
        result = [rec.id for rec in result]
        return result if issubclass(res_type, (list, tuple)) else bool(result)
           
    def _sync(self, cr, uid, rec, date=False, version=False, context=None):
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not version: 
            version = rec.version + 1
        self.write(cr, uid, rec.id, {'sync_date' : date, 'version' : version}, context=context)
        self.pool.get('sync.client.write_info').delete_old_log(cr, uid, rec.model, rec.res_id, date, context=context)

    def sync(self, cr, uid, xml_id, date=False, version=False, context=None):
        ir_data = self.get_ir_record(cr, uid, xml_id, context=context)
        if not ir_data:
            raise ValueError('No references to %s' % (xml_id))
        self._sync(cr, uid, ir_data, date=date, version=version, context=context)
        
    _order = 'id desc'
    
        
ir_model_data_sync()


def sync_client_install(model):
    ir_model = model.pool.get('ir.model.data')
    return hasattr(ir_model, 'get')
    
def version(self, cr, uid, ids, context=None):
    res_type = type(ids)
    ids = ids if isinstance(ids, (tuple, list)) else [ids]
    model_data = self.pool.get('ir.model.data')
    data_ids = model_data.get(cr, uid, self, ids, context=context)
    if False in data_ids:
        bad_ids = zip(ids, data_ids)
        raise osv.except_osv(_('Error !'), _("In object %(object)s, ids %(ids)s: cannot get version of record where ir.model.data for that records doesn't exists!") % {'object':self._name,'ids':map(lambda x:x[0], filter(lambda x:x[1] is False, bad_ids))})
    result = [(rec.version or 1) for rec in model_data.browse(cr, uid, data_ids, context=context)]
    return result if issubclass(res_type, (list, tuple)) else result[0]
    
osv.osv.version = version


def need_to_push(self, cr, uid, ids, included_fields, context=None):
    """
        @return True if last modification date is greater than last sync date
    """
    if not ids:
        return ids
    model_data = self.pool.get('ir.model.data')
    cr.execute("""SELECT id, res_id FROM %s WHERE
                      module = 'sd' AND
                      model = '%s' AND
                      res_id IN (%s) AND
                      (sync_date < last_modification OR sync_date IS NULL)""" \
               % (model_data._table, self._name, ",".join(map(str, ids))))
    rel_data = dict(cr.fetchall())
    data_ids = rel_data.keys()
    return [rel_data[x] for x in model_data.need_to_push(cr, uid, data_ids, included_fields, context=context)]
    
osv.osv.need_to_push = need_to_push    

def _clean_included_fields(self, cr, uid, included_fields, context=None):
    result = [field.split('/')[0] for field in included_fields]
    result.pop(result.index('id'))
    return result
    
osv.osv._clean_included_fields = _clean_included_fields    


    
# we modify the create method such that it creates a line in ir_model_data for each creation
old_create=orm.create
def create(model,cr,uid,values,context=None):
    if not context:
        context = {}
    
    link_ir_model_data = context.get('no_model_data_line')
    context['no_model_data_line'] = False
    res_id = old_create(model,cr,uid,values,context=context)
    if sync_client_install(model) and (model._name not in MODELS_TO_IGNORE) and (not(link_ir_model_data)):
        link_with_ir_model(model, cr, uid, res_id, context=context)
        modif_o2m(model,cr,uid,res_id,values,context=context)
    
    return res_id
    
orm.create=create

#to be sure to access last_modification for every record
old_write = orm.write
def write(model,cr,uid,ids,values,context=None):
    if not context:
        context = {}
    
    link_ir_model_data = context.get('no_model_data_line')
    context['no_model_data_line'] = False
    if sync_client_install(model) and (model._name not in MODELS_TO_IGNORE) and (not(link_ir_model_data)):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        for id in ids:
            ir_id = link_with_ir_model(model, cr, uid, id, context=context)
            model.pool.get('ir.model.data').write(cr, uid, ir_id, {'last_modification' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)
            model.pool.get('sync.client.write_info').log_write(cr, uid, model._name, id, values, context=context)
            modif_o2m(model, cr, uid, id, values, context=context)
    res = old_write(model, cr, uid, ids, values,context=context)
    return res
    
orm.write = write

def generate_message_for_destination(self, cr, uid, destination_name, xml_id, instance_name, send_to_parent_instances):
    instance_obj = self.pool.get('msf.instance')
    
    if not destination_name:
        return
    if destination_name != instance_name:
        message_data = {
                'identifier' : 'delete_%s_to_%s' % (xml_id, destination_name),
                'sent' : False,
                'generate_message' : True,
                'remote_call': self._name + ".message_unlink",
                'arguments': "[{'model' :  '%s', 'xml_id' : '%s'}]" % (self._name, xml_id),
                'destination_name': destination_name
        }
        self.pool.get("sync.client.message_to_send").create(cr, uid, message_data)
        
    if destination_name != instance_name or send_to_parent_instances:
        # generate message for parent instance
        instance_ids = instance_obj.search(cr, uid, [("instance", "=", destination_name)])
        if instance_ids:
            instance_record = instance_obj.browse(cr, uid, instance_ids[0])
            parent = instance_record.parent_id and instance_record.parent_id.instance or False
            if parent:
                generate_message_for_destination(self, cr, uid, parent, xml_id, instance_name, send_to_parent_instances)

old_unlink = orm.unlink

from sync_common.common import format_data_per_id 

def unlink(self, cr, uid, ids, context=None):
    if isinstance(ids, (int, long)):
        ids = [ids]
    old_uid = uid
    uid = 1
    if hasattr(self, '_delete_owner_field'):
        instance_name = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).name
        xml_ids = self.pool.get('ir.model.data').get(cr, uid, self, ids, context=context)
        data = self.read(cr, uid, ids, [self._delete_owner_field], context=context)
        data = format_data_per_id(data)
        destination_names = self.get_destination_name(cr, uid, ids, self._delete_owner_field, context=context)
        for i, xml_id_record in enumerate(self.pool.get('ir.model.data').browse(cr, uid, xml_ids, context=context)):
            xml_id = '%s.%s' % (xml_id_record.module, xml_id_record.name)
            generate_message_for_destination(self, cr, uid, destination_names[i], xml_id, instance_name, send_to_parent_instances=True)
            
    #raise osv.except_osv(_('Error !'), "Cannot Delete")
    uid = old_uid
    old_unlink(self, cr, uid, ids, context=None)
    return True
    
orm.unlink = unlink

def message_unlink(model, cr, uid, source, unlink_info, context=None):
    model_name = unlink_info.model
    xml_id =  unlink_info.xml_id
    if model_name != model._name:
        return "Model not consistant"
        
    res_id = model.pool.get("ir.model.data").get_record(cr, uid, xml_id, context=context)
    if not res_id:
        return "Object %s %s does not exist in destination" % (model_name, xml_id)
    
    return old_unlink(model, cr, uid, [res_id], context=context)
    
    
orm.message_unlink = message_unlink

"""
How to activate deletion on the branch. 
Need to specify field to extract the final destination of the delete. 
All record that are on the path of the current instance to destination will be deleted 
(only if destination is lower in the instance tree then the current instance)

class partner(osv.osv):
    _inherit = 'res.partner'
    _delete_owner_field = 'ref'

partner()
"""

def message_write_reference(model, cr, uid, source, write_info, context=None):
    model_name = write_info.model
    xml_id =  write_info.xml_id
    reference_field = write_info.field
    reference_xml_id = write_info.reference
    if not reference_xml_id:
        return
    
    reference_ir_record = model.pool.get('ir.model.data').get_ir_record(cr, uid, reference_xml_id, context=context)
    if not reference_ir_record:
        return
    
    reference = reference_ir_record.model + ',' + str(reference_ir_record.res_id)
    
    if model_name != model._name:
        return "Model not consistant"
        
    res_id = model.pool.get("ir.model.data").get_record(cr, uid, xml_id, context=context)
    if not res_id:
        return "Object %s %s does not exist in destination" % (model_name, xml_id)

    return old_write(model, cr, uid, [res_id], {reference_field: reference}, context=context)    
    
orm.message_write_reference = message_write_reference

#record modification of m2o if the corresponding o2m is modified
def modif_o2m(model,cr,uid,id,values,context=None):
    fields_ref = model.fields_get(cr, uid, context=context)
    for key in values.keys():
        if fields_ref.get(key) and fields_ref[key]['type'] == 'one2many' and values[key]:
            sub_model = fields_ref[key]['relation']
            o = model.browse(cr, uid, id, context=context)
            sub_ids= [obj.id for obj in getattr(o, key)]
            for sub_id in sub_ids:
                ir_id = link_with_ir_model(model.pool.get(sub_model), cr, uid, sub_id, context=context)
                model.pool.get('ir.model.data').write(cr, uid, ir_id, {'last_modification' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)
                log_o2m_write(model.pool.get(sub_model), cr, uid, sub_id, model._name, id, context=context)
                
def log_o2m_write(model, cr, uid, id, relation, parent_id, context=None):   
    fields_ref = model.fields_get(cr, uid, context=context)  
    for key, val in fields_ref.items():
        if val['type'] == "many2one" and val['relation'] == relation:
            model.pool.get('sync.client.write_info').log_write(cr, uid, model._name, id, {key : parent_id}, context=context)
    
def link_with_ir_model(model, cr, uid, id, context=None):
    
    #model.get_xml_id(cr, uid, [id], context={'sync' : True})
    model_data_pool = model.pool.get('ir.model.data')
    res_id = model_data_pool.get(cr, uid, model, id, context=context)
    if res_id:
        return res_id
    
    entity_uuid = model.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
    xml_name = model.get_unique_xml_name(cr, uid, entity_uuid, model._table, id)
    assert '.' not in xml_name, "The unique xml name must not contains dots: "+xml_name
    args = {
        'noupdate' : False, # don't set to True otherwise import won't work
        'model' : model._name,
        'module' : 'sd',#model._module,
        'name' : xml_name,
        'res_id' : id,
        'last_modification' : fields.datetime.now(),
    }
    return model_data_pool.create(cr,uid,args,context=context)

  
# we modify the import method such that no line in ir_model_data is created if
old_import_data = osv.osv.import_data

def import_data(model, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
    if not context:
        context = {}
    context['sync_data'] = True
    if 'id' in fields:
        context['no_model_data_line'] = True
    res = old_import_data(model,cr,uid,fields,datas,mode,current_module,noupdate=noupdate,context=context,filename=filename)
    context['no_model_data_line'] = False
    return res
    
osv.osv.import_data = import_data 



def get_destination_name(self, cr, uid, ids, dest_field, context=None):
    """
        @param ids : ids of the record from which we need to find the destination
        @param dest_field : field of the record from where the name will be extract
        @return a dictionnary with ids : dest_fields
    """
    res_type = type(ids)
    ids = ids if isinstance(ids, (tuple, list)) else [ids]
    if not dest_field:
        return [False for x in ids] if issubclass(res_type, (list, tuple)) else False
    
    field = self.fields_get(cr, uid, context=context).get(dest_field)
    
    if field['type'] == 'many2one' and not field['relation'] == 'msf.instance':
        values = self.read(cr, uid, ids, [dest_field], context)
        names = dict([
            (x['id'],(x[dest_field][1] if x[dest_field] else False)) for x in values
        ])
        return [names[id] for id in ids] if issubclass(res_type, (list, tuple)) \
            else names[ids[0]]

    result = list()
    for rec in self.browse(cr, uid, ids, context=context):
        value = rec[dest_field]
        if value is False:
            result.append(False)
        if field['type'] == 'many2one':
            result.append(value.instance or False)
        elif field['type'] in ('char', 'text'):
            result.append(value)
        else:
            raise osv.except_osv(_('Error !'), _("%(method)s doesn't implement field of type %(type)s, please contact system administrator to upgrade.") % {'method':'get_destination_name()', 'type':field['type']})

    return result if issubclass(res_type, (list, tuple)) else result[0]

osv.osv.get_destination_name = get_destination_name


def get_message_arguments(self, cr, uid, res_id, rule=None, context=None):
    """
        @param res_id: Id of the record from which we need to extract the args of the call
        @param rule: the message generating rule (browse record)
        @return a list : each element of the list will be an arg after uid
            If the call is create_po(self, cr, uid, arg1, arg2, context=None)
            the list should contains exactly 2 element
            
        The default method will extract object information from the rule and return a list with a single element
        the object information json serialized
    
    """
    fields = eval(rule.arguments)
    res =  self.export_data_json(cr, uid, [res_id], fields, context=context)
    return res['datas']

osv.osv.get_message_arguments = get_message_arguments  
    
def __export_row_json(self, cr, uid, row, fields, json_data, context=None):
        if not context:
            context = {}
    
        
        def get_name(row):
            name_relation = self.pool.get(row._table_name)._rec_name
            if isinstance(row[name_relation], browse_record):
                row = row[name_relation]
            row_name = self.pool.get(row._table_name).name_get(cr, uid, [row.id], context=context)
            return row_name and row_name[0] and row_name[0][1] or ''
               
        def export_list(field, record_list, json_list):
            if not json_list: #if the list was not created before
                json_list = [{} for i in record_list]

            for i in xrange(0, len(record_list)):
                if len(field) > 1:
                    if not record_list[i]:
                        json_list[i] = {}
                    json_list[i] = export_field(field[1:], record_list[i], json_list[i])
                else:
                    json_list[i] = get_name(record_list[i]) 

            return json_list
        
        def export_relation(field, record, json):
            if len(field) > 1:
                if not json: #if the list was not create before
                    json = {}
                return export_field(field[1:], record, json)
            else:
                return get_name(record) 
                        
        def export_field(field, row, json_data):
            """
                @param field: a list 
                    size = 1 ['cost_price']
                    size > 1 ['partner_id', 'id']
                @param row: the browse record for which field[0] is a valid field
                @param json_data: json seralisation of row
                
            """
            if field[0] == 'id':
                json_data[field[0]] = row.get_xml_id(cr, uid, [row.id]).get(row.id)
            elif field[0] == '.id':
                json_data[field[0]] = row.id
            else: #TODO manage more case maybe selection or reference
                r = row[field[0]]
                if isinstance(r, (browse_record_list, list)):
                    json_data[field[0]] = export_list(field, r, json_data.get(field[0]))
                elif isinstance(r, (browse_record)):
                    json_data[field[0]] = export_relation(field, r, json_data.get(field[0]))
                elif not r:
                    json_data[field[0]] = False
                else:
                    if len(field) > 1:
                        raise ValueError('%s is not a relational field cannot use / to go deeper' % field[0])
                    json_data[field[0]] = r
                   
            return json_data 
            
        json_data = {}
        for field in fields:
            json_data = export_field(field, row, json_data)
            
        return json_data
osv.osv.__export_row_json = __export_row_json

def export_data_json(self, cr, uid, ids, fields_to_export, context=None):
        """
        Export fields for selected objects

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param fields_to_export: list of fields
        :param context: context arguments, like lang, time zone
        :rtype: dictionary with a *datas* matrix

        This method is used when exporting data via client menu

        """
        def fsplit(x):
            if x=='.id': return [x]
            return x.replace(':id','/id').replace('.id','/.id').split('/')
        
        fields_to_export = map(fsplit, fields_to_export)
        datas = []
        for row in self.browse(cr, uid, ids, context):
            datas.append(self.__export_row_json(cr, uid, row, fields_to_export, context))
        return {'datas': datas}

osv.osv.export_data_json = export_data_json


class dict_to_obj(object):
    def __init__(self, d):
        self.d = d
        seqs = tuple, list, set, frozenset
        for i, j in d.items():
            if isinstance(j, dict):
                setattr(self, i, dict_to_obj(j))
            elif isinstance(j, seqs):
                setattr(self, i, type(j)(dict_to_obj(sj) if isinstance(sj, dict) else sj for sj in j))
            else:
                setattr(self, i, j)
    def __str__(self):
        return str(self.d)
    
    def to_dict(self):
        return self.d



def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
    return uuid + '/' + table_name + '/' + str(res_id)

osv.osv.get_unique_xml_name = get_unique_xml_name

