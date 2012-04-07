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

#TODO réécrire le create pour creer un nouveau ir.model.data si besoin
#Dans auto-init : créer un méthode qui parse tout les ir.model.data existant 

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

from osv.orm import *
from datetime import datetime

import pprint
pp = pprint.PrettyPrinter(indent=4)

from tools.safe_eval import safe_eval as eval

class write_info(osv.osv):
    
    _name = 'sync.client.write_info'
    
    _rec_name = 'fields_modif'
    
    _columns= {
        'create_date' :fields.datetime('Create Date'),
        'model' : fields.char('model', size=64), 
        'res_id' : fields.integer('Ressource Id'),
        'fields_modif' : fields.text('Fields Modified'),
    }
    

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
        real_modif_field = []
        for k, val in read_res.items():
            if k in field and (not isinstance(values[k], list) or values[k]) and val != values[k]:
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
            args = {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'model' : values.get('model'),
                    'module' : 'sd',#model._module,
                    'name' : name,
                    'res_id' : values.get('res_id'),
                    }
            super(ir_model_data_sync, self).create(cr, uid, args, context=context)
    
        return res_id

    def get(self, cr, uid, model, res_id, context=None):
        ids = self.search(cr, uid, [('model', '=', model._name), ('res_id', '=', res_id), ('module', '=', 'sd')], context=context)
        if ids:
            return ids[0]
        return False
    
    def get_record(self, cr, uid, xml_id, context=None):
        ir_record = self.get_ir_record(cr, uid, xml_id, context=context)
        if not ir_record:
            return False
        model = ir_record.model
        id = ir_record.res_id
        ids = self.pool.get(model).search(cr, uid, [('id', '=', id)], context=context)
        return ids and ids[0] or False
        
    
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
         
        ids = self.search(cr, uid, [('name', '=', name), ('module', '=', module)], context=context)
        if ids: 
            return self.browse(cr, uid, ids[0], context=context)
        return False
    
    def need_to_push(self, cr ,uid, id, included_fields, context=None):
        ir_model = self.browse(cr, uid, id, context=context)
        
        if not ir_model.sync_date:
            return True
        if not ir_model.last_modification:
            return False
        
        if ir_model.last_modification >= ir_model.sync_date:
            modif_field = self.pool.get('sync.client.write_info').get_last_modification(cr, uid, ir_model.model, ir_model.res_id, ir_model.sync_date, context=context)
            res = set(self._clean_included_fields(included_fields)) & modif_field
            if res:
                return True
            else:
                return False
            
    def _clean_included_fields(self, included_fields):
        return [field.split('/')[0] for field in included_fields]
        
    def sync(self, cr, uid, xml_id, date=False, version=False, context=None):
        ir_data = self.get_ir_record(cr, uid, xml_id, context=context)
        if not ir_data:
            raise ValueError('No references to %s' % (xml_id))
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not version: 
            version = ir_data.version + 1
        self.write(cr, uid, ir_data.id, {'sync_date' : date, 'version' : version}, context=context)
        self.pool.get('sync.client.write_info').delete_old_log(cr, uid, ir_data.model, ir_data.res_id, date, context=context)
        
    _order = 'id desc'
    
        
ir_model_data_sync()


def sync_client_install(model):
    ir_model = model.pool.get('ir.model.data')
    return hasattr(ir_model, 'get')
    
def version(self, cr, uid, id, context=None):
    model_data = self.pool.get('ir.model.data')
    data_id = model_data.get(cr, uid, self, id, context=context)
    if not data_id:
        return 1
    return model_data.browse(cr, uid, data_id, context=context).version
    
osv.osv.version = version


def need_to_push(self, cr, uid, res_id, included_fields, context=None):
    """
        @return True if last modification date is greater than last sync date
    """
    
    model_data_pool = self.pool.get('ir.model.data')
    xml_id = model_data_pool.get(cr, uid, self, res_id, context=context)
    return  model_data_pool.need_to_push(cr, uid, xml_id, included_fields, context=context)
    
osv.osv.need_to_push = need_to_push    



    
# we modify the create method such that it creates a line in ir_model_data for each creation
old_create=osv.osv.create
def create(model,cr,uid,values,context=None):
    if not context:
        context = {}
    
    res_id = old_create(model,cr,uid,values,context=context)
    if sync_client_install(model) and (model._name not in MODELS_TO_IGNORE) and (not(context.get('no_model_data_line'))):
        link_with_ir_model(model, cr, uid, res_id, context=context)
        modif_o2m(model,cr,uid,res_id,values,context=context)
    
    return res_id
    
osv.osv.create=create

#to be sure to access last_modification for every record
old_write=osv.osv.write
def write(model,cr,uid,ids,values,context=None):
    if not context:
        context = {}
    
    
    if sync_client_install(model) and (model._name not in MODELS_TO_IGNORE) and (not(context.get('no_model_data_line'))):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        for id in ids:
            ir_id = link_with_ir_model(model, cr, uid, id, context=context)
            model.pool.get('ir.model.data').write(cr, uid, ir_id, {'last_modification' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)
            model.pool.get('sync.client.write_info').log_write(cr, uid, model._name, id, values, context=context)
            modif_o2m(model, cr, uid, id, values, context=context)
    res = old_write(model, cr, uid, ids, values,context=context)
    return res
    
osv.osv.write=write

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
    model.get_xml_id(cr, uid, [id], context={'sync' : True})
    model_data_pool = model.pool.get('ir.model.data')
    res_id = model_data_pool.get(cr, uid, model, id, context=context)
    if res_id:
        return res_id
    
    entity_uuid = model.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
    args = {
        'noupdate' : False, # don't set to True otherwise import won't work
        'model' : model._name,
        'module' : 'sd',#model._module,
        'name' : model.get_unique_xml_name(cr, uid, entity_uuid, model._table, id),
        'res_id' : id,
        'last_modification' : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    fields_ref = self.fields_get(cr, uid, context=context)
    field = fields_ref.get(dest_field)
    result = {}
    data_list = self.read(cr, uid, ids, ['id', dest_field], context=context)
    for data in data_list:
        if not data[dest_field]:
            result[data['id']] = False
            
        if field['type'] == 'many2one':
            result[data['id']] = data[dest_field][1]
        elif field['type'] == 'char' or field['type'] == 'text':
            result[data['id']] = data[dest_field]
        else:
            result[data['id']] = False 
            #TODO other case 
    return result
    
    
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
                json_data[field[0]] = self.get_xml_id(cr, uid, [row.id]).get(row.id)
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

