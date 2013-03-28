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
import StringIO
import traceback
import re
from sync_client.ir_model_data import link_with_ir_model

import logging
from sync_common.common import sync_log

from tools.safe_eval import safe_eval as eval

def eval_poc_domain(obj, cr, uid, domain, context=None):
    if not context:
        context = {}
    
    domain_new = []
    for tp in domain:
        if isinstance(tp, tuple):
            if len(tp) != 3:
                raise osv.except_osv(_('Domain malformed : ' + tools.ustr(domain)), _('Error') )
            if isinstance(tp[2], tuple) and len(tp[2]) == 3 and isinstance(tp[2][0], basestring) and isinstance(tp[2][1], basestring) and isinstance(tp[2][2], list):
                model  = tp[2][0]
                sub_domain = tp[2][2]
                field = tp[2][1]
                sub_obj = obj.pool.get(model)
                ids_list = eval_poc_domain(sub_obj, cr, uid, sub_domain)
                if ids_list:
                    new_ids = []
                    data = sub_obj.read(cr, uid, ids_list, [field], context=context)
                    for d in data:
                        if isinstance(d[field], list):
                            new_ids.extend(d[field])
                        elif isinstance(d[field], tuple):
                            new_ids.append(d[field][0])
                        else:
                            new_ids.append(d[field])
                    ids_list = new_ids
                domain_new.append((tp[0], tp[1], ids_list))
            else:
                domain_new.append(tp)
        else:
            domain_new.append(tp)
    return obj.search(cr, uid, domain_new, context=context)

class local_rule(osv.osv):
    _name = "sync.client.rule"

    _columns = {
        'server_id' : fields.integer('Server ID', required=True, readonly=True),
        'name' : fields.char('Rule name', size=64, readonly=True),
        'model' : fields.many2one('ir.model','Model', readonly=True, select=True),
        'domain' : fields.text('Domain', required = False, readonly=True),
        'sequence_number' : fields.integer('Sequence', readonly=True),
        'included_fields' : fields.text('Included Fields', readonly=True),
        'owner_field' : fields.char('Owner Field', size=128, readonly=True),
    }
    
    _logger = logging.getLogger('sync.client')

    def save(self, cr, uid, data_list, context=None):
        self._delete_old_rules(cr, uid, context)
        for data in data_list:
            model_name = data.get('model')
            model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name)], context=context)
            if not model_id:
                sync_log(self, "Model %s does not exist" % model_name, data=data)
                continue #do not save the rule if there is no valid model
            data['model'] = model_id[0]
            
            self.create(cr, uid, data, context=context)
                
    def _delete_old_rules(self, cr, uid, context=None):
        ids_to_unlink = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, ids_to_unlink, context=context)
        
    _order = 'sequence_number asc'
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
        'values':fields.text('Values', size=128, readonly=True),
        'model' : fields.many2one('ir.model','Model', readonly=True),
        'owner' : fields.char('Owner', size=128, readonly=True),
        'sent' : fields.boolean('Sent ?', readonly=True, select=True),
        'sync_date' : fields.datetime('Start date',readonly=True),
        'sent_date' : fields.datetime('Sent date', readonly=True),
        'session_id' : fields.char('Session Id', size=128, readonly=True, select=True),
        'version' : fields.integer('Record Version', readonly=True),
        'rule_id' : fields.many2one('sync.client.rule','Generating Rule', readonly=True, ondelete="set null"),
        'xml_id' : fields.many2one('ir.model.data', 'Synchronization information', readonly=True, ondelete="set null"),
        'fields':fields.text('Fields', size=128, readonly=True),
        
    }
    
    _defaults = {
        'sync_date' : lambda *a : datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        'sent' : False,
    }

    _logger = logging.getLogger('sync.client')

    def create_update(self, cr, uid, rule_id, session_id, context={}):
        rule = self.pool.get('sync.client.rule').browse(cr, uid, rule_id, context=context)
        obj = self.pool.get(rule.model.model)
        
        # Boring!
        included_fields = eval(rule.included_fields)
        if not 'id' in included_fields: 
            included_fields.append('id')
        # --end
        
        if rule.domain:
            domain = eval(rule.domain)
        else:
            domain = []

        ids_to_compute = obj.need_to_push(cr, uid,
            eval_poc_domain(obj, cr, uid, domain, context=context),
            included_fields, context=context)
        if not ids_to_compute:
            return 0

        sync_context = dict(context, sync_context=True)
        fields_ref = obj.fields_get(cr, uid, [], context=sync_context)
        fields_ref['id'] = dict()
        ustr_included_fields = tools.ustr(included_fields)
        owners = obj.get_destination_name(cr, uid, ids_to_compute, rule.owner_field, sync_context)
        datas = obj.export_data(cr, uid, ids_to_compute, included_fields, context=sync_context)['datas']
        xml_ids = [link_with_ir_model(obj, cr, uid, id, context=sync_context) for id in ids_to_compute]
        versions = obj.version(cr, uid, ids_to_compute, context=sync_context)
        clean_included_fields = self._clean_included_fields(cr, uid, included_fields)
        for (i, row) in enumerate(datas):
            update_owners = []
            if not issubclass(type(owners[i]), (list, tuple)):
                update_owners = [owners[i]]
            else:
                update_owners = owners[i]
            for update_owner in update_owners:
                self.create(cr, uid, {
                    'session_id' : session_id,
                    'values' : tools.ustr(row),
                    'model' : rule.model.id,
                    'version' : versions[i] + 1,
                    'rule_id' : rule.id,
                    'xml_id' : xml_ids[i],
                    'fields' : ustr_included_fields,
                    'owner' : update_owner,
                }, context=context)
                self._logger.debug("Create update %s, id : %s, for rule %s" % (rule.model.model, id, rule.id))

        return len(datas)

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
                           'owner' : update.owner,
                           })
            ids_in_package.append(update.id)
        data['load'] = values
        #for update in 
        self._logger.debug("package create for %s" % (ids_in_package))
        return (ids_in_package, data)
    
    def sync_finished(self, cr, uid, update_ids, context=None):
        model_data_pool = self.pool.get('ir.model.data')

        for update in self.browse(cr, uid, update_ids, context=context):
            model_data_pool._sync(cr, uid, update.xml_id, date=update.sync_date, version=update.version, context=context)
        self.write(cr, uid, update_ids, {'sent' : True, 'sent_date' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)    
        self._logger.debug("Pushed finished")
        
    _order = 'id asc'
update_to_send()

class update_received(osv.osv):

    _name = "sync.client.update_received"
    _rec_name = 'source'

    _columns = {
        'source': fields.char('Source Instance', size=128, readonly=True), 
        'owner': fields.char('Owner Instance', size=128, readonly=True), 
        'model' : fields.many2one('ir.model','Model', readonly=True, select=True),
        'sequence' : fields.integer('Sequence', readonly=True),
        'rule_sequence' : fields.integer('Rule Sequence', readonly=True),
        'version' : fields.integer('Record Version', readonly=True),
        'fields' : fields.text("Fields"),
        'values' : fields.text("Values"),
        'run' : fields.boolean("Run", readonly=True, select=True),
        'log' : fields.text("Execution Messages", readonly=True),
        'fallback_values':fields.text('Fallback values'),

        'create_date':fields.datetime('Synchro date/time', readonly=True),
        'execution_date':fields.datetime('Execution date', readonly=True),
        'editable' : fields.boolean("Set editable"),
    }

    line_error_re = re.compile(r"^Line\s+(\d+)\s*:\s*(.+)")
    
    _logger = logging.getLogger('sync.client')

    def unfold_package(self, cr, uid, packet, context=None):
        if not packet:
            return 0
        model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', packet['model'])], context=context)
        if not model_id:
            sync_log(self, "Model %s does not exist" % packet['model'], data=packet)
        data = {
            'source' : packet['source_name'],
            'model' : model_id[0],
            'fields' : packet['fields'],
            'sequence' : packet['sequence'],
            'fallback_values' : packet['fallback_values'],
            'rule_sequence' : packet['rule'],
            # Retrieve synchro date/time from the packet and store it
            #'create_date' : packet['create_date'],
        }
        for load_item in packet['load']:
            data.update({
                'version' : load_item['version'],
                'values' : load_item['values'],
                'owner' : load_item['owner_name'],
            })
            self.create(cr, uid, data ,context=context)
        self._logger.debug("Unfold package %s" % model_id[0])
        return len(packet['load'])

    def run(self, cr, uid, ids, context=None):
        try:
            self.execute_update(cr, uid, ids, context=context)
        except BaseException, e:
            sync_log(self, e)
        return True

    def execute_update(self, cr, uid, ids=None, context=None):
        context = dict(context or {})
        context['sync_data'] = True

        if ids is None:
            update_ids = self.search(cr, uid, [('run', '=', False)], context=context)
        else:
            update_ids = ids
        if not update_ids:
            return ''

        # Sort updates by rule_sequence
        whole = self.browse(cr, uid, update_ids, context=context)
        update_groups = dict()
        
        for update in whole:
            group_key = (update.sequence, update.rule_sequence)
            try:
                update_groups[group_key].append(update)
            except KeyError:
                update_groups[group_key] = [update]
        sync_log(self, data="received update ids = %s, models = %s" % (update_ids, map(lambda x:x[0].model.model, update_groups.values())))
        self.write(cr, uid, update_ids, {'execution_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, context=context)

        def secure_import_data(obj, fields, values):
            try:
                cr.rollback_org, cr.rollback = cr.rollback, lambda:None
                cr.commit_org, cr.commit = cr.commit, lambda:None
                cr.execute("SAVEPOINT import_data")
                res = obj.import_data(cr, uid, fields, values, mode='update', current_module='sd', noupdate=True, context=context)
            except BaseException, e:
                cr.execute("ROLLBACK TO SAVEPOINT import_data")
                self._logger.exception("import failure")
                raise Exception(tools.ustr(e))
            else:
                if res[0] == len(values):
                    cr.execute("RELEASE SAVEPOINT import_data")
                else:
                    cr.execute("ROLLBACK TO SAVEPOINT import_data")
            finally:
                cr.rollback = cr.rollback_org
                cr.commit = cr.commit_org
            return res

        def group_update_execution(updates):
            obj = self.pool.get(updates[0].model.model)
            fields = eval(updates[0].fields)
            fallback = eval(updates[0].fallback_values or '{}')
            message = ""
            values = []
            update_ids = []
            versions = []
            logs = {}

            def success(update_ids, versions):
                self.write(cr, uid, update_ids, {
                    'editable' : False,
                    'run' : True,
                    'log' : '',
                }, context=context)
                for update_id, log in logs.items():
                    self.write(cr, uid, [update_id], {
                        'log' : log,
                    }, context=context)
                logs.clear()
                for xml_id, version in versions.items():
                    self.pool.get('ir.model.data').sync(cr, uid, xml_id, version=version, context=context)

            #3 check for missing field : report missing fields
            bad_fields = self._check_fields(cr, uid, obj._name, fields, context=context)
            if bad_fields: 
                message += "Missing or unauthorized fields found : %s\n" % ", ".join(bad_fields)
                bad_fields = [fields.index(x) for x in bad_fields]

            i_id = fields.index('id')

            for update in updates:
                       
                row = eval(update.values)

                #4 check for fallback value : report missing fallback_value
                row = self._check_and_replace_missing_id(cr, uid, row, fields, fallback, message, context=context)
                xml_id = row[i_id]

                if bad_fields : 
                    row = [row[i] for i in range(len(fields)) if i not in bad_fields]

                values.append(row)
                update_ids.append(update.id)
                versions.append( (xml_id, update.version) )

                #1 conflict detection
                if self._conflict(cr, uid, update, context):
                    #2 if conflict => manage conflict according rules : report conflict and how it's solve
                    logs[update.id] = sync_log(self, "Conflict detected!", 'warning', data=(update.id, update.fields, update.values)) + "\n"
                    #TODO manage other conflict rules here (tfr note)

            if bad_fields:
                fields = [fields[i] for i in range(len(fields)) if i not in bad_fields]

            #5 import data : report error
            while values:
                try:
                    res = secure_import_data(obj, fields, values)
                except Exception, import_error:
                    import_error = "Error during importation in model %s!\nUpdate ids: %s\nReason: %s\nData imported:\n%s\n" % (obj._name, update_ids, str(import_error), "\n".join([str(v) for v in values]))
                    # Rare Exception: import_data raised an Exception
                    self.write(cr, uid, update_ids, {
                        'run' : False,
                        'log' : import_error.strip(),
                    }, context=context)
                    raise Exception(message+import_error)
                if res[0] == len(values):
                    success( update_ids, \
                             dict(versions) )
                    break
                elif res[0] == -1:
                    # Regular exception
                    import_message = res[2]
                    line_error = self.line_error_re.search(import_message)
                    if line_error:
                        # Extract the failed data
                        value_index, import_message = int(line_error.group(1))-1, line_error.group(2)
                        data = dict(zip(fields, values[value_index]))
                        if "('warning', 'Warning !')" == import_message:
                            import_message = "Unknown! Please check the constraints of linked models. The use of raise Python's keyword in constraints typically give this message."
                        import_message = "Cannot import in model %s:\nData: %s\nReason: %s\n" % (obj._name, data, import_message)
                        message += import_message
                        values.pop(value_index)
                        versions.pop(value_index)
                        self.write(cr, uid, [update_ids.pop(value_index)], {
                            'run' : False,
                            'log' : import_message.strip(),
                        }, context=context)
                    else:
                        # Rare case where no line is given by import_data
                        message += "Cannot import data in model %s:\nReason: %s\n" % (obj._name, import_message)
                        raise Exception(message)
                    if value_index > 0:
                        # Try to import the beginning of the values and permit the import of the rest
                        try:
                            res = secure_import_data(obj, fields, values[:value_index])
                            assert res[0] == value_index, res[2]
                        except Exception, import_error:
                            raise Exception(message+import_error.message)
                        success( update_ids[:value_index], \
                                 dict(versions[:value_index]) )
                        values = values[value_index:]
                        update_ids = update_ids[value_index:]
                        versions = versions[value_index:]
                else:
                    # Rare exception, should never occur
                    raise Exception(message+"Wrong number of imported rows in model %s (expected %s, but %s imported)!\nUpdate ids: %s\n" % (updates[0].model.model, len(values), res[0], update_ids))

            # Obvious
            assert len(values) == len(update_ids) == len(versions), \
                message+"""This error must never occur. Please contact the developper team of this module.\n"""

            return message

        error_message = ""
        for rule_seq in sorted(update_groups.keys()):
            updates = update_groups[rule_seq]
            error_message += group_update_execution(updates)
        
        return error_message.strip()

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
        if update.version < ir_data.version: #not a higher version conflict
            return True
        return False
    
    def _check_and_replace_missing_id(self, cr, uid, values, fields, fallback, message, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        for i in xrange(0, len(fields)):
            if '/id' in fields[i] and values[i]:
                xml_id_raw = values[i]
                res_val = []
                if xml_id_raw:
                    xml_ids = xml_id_raw.split(',')
                    for xml_id in xml_ids:
                        if xml_id and not ir_model_data_obj.get_record(cr, uid, xml_id, context=context):
                            fb = fallback.get(fields[i])
                            if fb and ir_model_data_obj.get_record(cr, uid, fb, context=context):
                                message += 'Missing record %s replace by %s\n' % (fields[i], fb)
                                res_val.append(fb)
                            else:
                                message += 'Missing record %s and no fallback value defined or missing fallback value, set to False\n' % fields[i]
                        else:
                            res_val.append(xml_id)
                if not res_val:
                    values[i] = False
                else:
                    values[i] = ','.join(res_val)
        return values
                 
        
            
            
    _order = 'id asc'
update_received()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

