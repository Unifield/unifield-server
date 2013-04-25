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

from osv import osv, fields
import tools
from tools.translate import _
from tools.safe_eval import safe_eval as eval

import re
import logging

from sync_common import sync_log, add_sdref_column, fancy_integer

class local_rule(osv.osv):
    _name = "sync.client.rule"

    _columns = {
        'server_id' : fields.integer('Server ID', required=True, readonly=True),
        'name' : fields.char('Rule name', size=64, readonly=True),
        'model' : fields.char('Model', size=64, readonly=True, select=True),
        'domain' : fields.text('Domain', readonly=True),
        'sequence_number' : fields.integer('Sequence', readonly=True),
        'included_fields' : fields.text('Included Fields', readonly=True),
        'owner_field' : fields.char('Owner Field', size=128, readonly=True),
        'can_delete': fields.boolean('Can delete record?', readonly=True, help='Propagate the delete of old unused records'),
        'active' : fields.boolean('Active', select=True),
        
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('Remote Warehouse Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
        
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization', required=True),
    }

    _defaults = {
        'included_fields' : '[]',
        'active' : True,
        
        'usb': False,
        'direction_usb': 'bidirectional',
    }

    _sql_constraints = [
        ('server_rule_id_unique','UNIQUE(server_id)','Duplicate rule server id'),
    ]

    _logger = logging.getLogger('sync.client')

    def save(self, cr, uid, data_list, context=None):
        # Get the whole ids of existing and active rules
        remaining_ids = set(self.search(cr, uid, [], context=context))

        for vals in (dict(data) for data in data_list):
            assert 'server_id' in vals, "The following rule doesn't seem to have the required field server_id: %s" % vals

            # Check model exists or is null
            if not vals.get('model'):
                vals['active'] = False
            elif not self.pool.get('ir.model').search(cr, uid, [('model', '=', vals['model'])], limit=1, context=context):
                self._logger.error("The following rule doesn't apply to your database and has been disabled. Reason: model %s does not exists!\n%s" % (vals['model'], vals))
                continue #do not save the rule if there is no valid model
            elif 'active' not in vals:
                vals['active'] = True

            ids = self.search(cr, uid, [('server_id','=',vals['server_id']),'|',('active','=',True),('active','=',False)], context=context)
            if ids:
                remaining_ids.discard(ids[0])
                self.write(cr, uid, ids, vals, context=context)
            else:
                self.create(cr, uid, vals, context=context)

        # The rest is just disabled
        self.write(cr, uid, list(remaining_ids), {'active':False}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'active':False}, context=context)

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
        'model' : fields.char('Model', size=64, readonly=True, select=True),
        'owner' : fields.char('Owner', size=128, readonly=True),
        'sent' : fields.boolean('Sent?', readonly=True, select=True),
        'create_date' : fields.datetime('Start date',readonly=True),
        'sent_date' : fields.datetime('Sent date', readonly=True),
        'session_id' : fields.char('Session Id', size=128, readonly=True, select=True),
        'version' : fields.integer('Version', readonly=True),
        'fancy_version' : fields.function(fancy_integer, method=True, string="Version", type='char', readonly=True),
        'rule_id' : fields.many2one('sync.client.rule','Generating Rule', readonly=True, ondelete="set null"),
        'sdref' : fields.char('SD ref', size=128, readonly=True),
        'fields':fields.text('Fields', size=128, readonly=True),
        'is_deleted' : fields.boolean('Is deleted?', readonly=True, select=True),
    }
    
    _defaults = {
        'sent' : False,
        'is_deleted' : False,
    }

    _logger = logging.getLogger('sync.client')

    @add_sdref_column
    def _auto_init(self, cr, context=None):
        super(update_to_send, self)._auto_init(cr, context=context)

    def create_update(self, cr, uid, rule_id, session_id, context=None):
        rule = self.pool.get('sync.client.rule').browse(cr, uid, rule_id, context=context)
        update = self
        
        context = context or {}
        sync_field = context.get('last_sync_date_field', 'sync_date')

        def create_normal_update(self, rule, context):
            domain = eval(rule.domain or '[]')
            included_fields = eval(rule.included_fields or '[]') 
            if not 'id' in included_fields: 
                included_fields.append('id')

            ids_to_compute = self.need_to_push(cr, uid,
                self.search_ext(cr, uid, domain, context=context),
                included_fields, sync_field=sync_field, context=context)
            if not ids_to_compute:
                return 0

            owners = self.get_destination_name(cr, uid, ids_to_compute, rule.owner_field, context)
            datas = self.export_data(cr, uid, ids_to_compute, included_fields, context=context)['datas']
            sdrefs = self.get_sd_ref(cr, uid, ids_to_compute, context=context)
            versions = self.version(cr, uid, ids_to_compute, context=context)
            ustr_included_fields = tools.ustr(included_fields)
            for (id, row) in zip(ids_to_compute, datas):
                for owner in (owners[id] if hasattr(owners[id], '__iter__') else [owners[id]]):
                    update_id = update.create(cr, uid, {
                        'session_id' : session_id,
                        'values' : tools.ustr(row),
                        'model' : self._name,
                        'version' : versions[id] + 1,
                        'rule_id' : rule.id,
                        'sdref' : sdrefs[id],
                        'fields' : ustr_included_fields,
                        'owner' : owner,
                    }, context=context)
                    update._logger.debug("Created 'normal' update model=%s id=%d (rule sequence=%d)" % (self._name, update_id, rule.id))

            return len(ids_to_compute)

        def create_delete_update(self, rule, context):
            if not rule.can_delete:
                return 0

            ids_to_delete = self.need_to_push(cr, uid,
                self.search_deleted(cr, uid, [('module','=','sd')], context=context),
                [], sync_field=sync_field, context=context)

            if not ids_to_delete:
                return 0

            sdrefs = self.get_sd_ref(cr, uid, ids_to_delete, context=context)
            for id in ids_to_delete:
                update_id = update.create(cr, uid, {
                    'session_id' : session_id,
                    'model' : self._name,
                    'rule_id' : rule.id,
                    'sdref' : sdrefs[id],
                    'is_deleted' : True,
                }, context=context)
                update._logger.debug("Created 'delete' update: model=%s id=%d (rule sequence=%d)" % (self._name, update_id, rule.id))

            self.purge(cr, uid, ids_to_delete, context=context)
            return len(ids_to_delete)

        update_context = dict(context or {}, sync_update_creation=True)
        obj = self.pool.get(rule.model)
        assert obj, "Cannot find model %s of rule id=%d!" % (rule.model, rule.id)
        return (create_normal_update(obj, rule, update_context), create_delete_update(obj, rule, update_context))

    def create_package(self, cr, uid, session_id, packet_size, context=None):
        ids = self.search(cr, uid, [('session_id', '=', session_id), ('sent', '=', False)], limit=packet_size, context=context)
        if not ids:
            return False
        update_master = self.browse(cr, uid, ids[0], context=context)
        data = {  
            'session_id' : update_master.session_id,
            'model' : update_master.model,
            'rule_id' : update_master.rule_id.server_id,
            'fields' : update_master.fields,
        }
        ids_in_package = []
        values = []
        deleted = []
        for update in self.browse(cr, uid, ids, context=context):
            #only update from the same rules in the same package
            if update.rule_id.server_id != data['rule_id']:
                break
            if update.is_deleted:
                deleted.append(update.sdref)
            else:
                values.append({
                    'version' : update.version,
                    'values' : update.values,
                    'owner' : update.owner,
                    'sdref' : update.sdref,
                })
            ids_in_package.append(update.id)
        data['load'] = values
        data['unload'] = deleted
        self._logger.debug("package created for update ids=%s" % ids_in_package)
        return (ids_in_package, data)

    def sync_finished(self, cr, uid, update_ids, sync_field='sync_date', context=None):
        self.pool.get('ir.model.data').update_sd_ref(cr, uid,
            dict((update.sdref, {'version':update.version,sync_field:update.create_date}) for update in self.browse(cr, uid, update_ids, context=context)),
            context=context)
        self.write(cr, uid, update_ids, {'sent' : True, 'sent_date' : fields.datetime.now()}, context=context)
        self._logger.debug(_("Push finished: %d updates") % len(update_ids))

    _order = 'id asc'

update_to_send()

class update_received(osv.osv):

    _name = "sync.client.update_received"
    _rec_name = 'source'

    _columns = {
        'source': fields.char('Source Instance', size=128, readonly=True), 
        'owner': fields.char('Owner Instance', size=128, readonly=True), 
        'model' : fields.char('Model', size=64, readonly=True, select=True),
        'sdref' : fields.char('SD ref', size=128, readonly=True),
        'is_deleted' : fields.boolean('Is deleted?', readonly=True, select=True),
        'sequence' : fields.integer('Sequence', readonly=True),
        'rule_sequence' : fields.integer('Rule Sequence', readonly=True),
        'version' : fields.integer('Version', readonly=True),
        'fancy_version' : fields.function(fancy_integer, method=True, string="Version", type='char', readonly=True),
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

    @add_sdref_column
    def _auto_init(self, cr, context=None):
        super(update_received, self)._auto_init(cr, context=context)

    def unfold_package(self, cr, uid, packet, context=None):
        if not packet:
            return 0
        self._logger.debug("Unfold package %s" % packet['model'])
        if not self.pool.get('ir.model').search(cr, uid, [('model', '=', packet['model'])], context=context):
            sync_log(self, "Model %s does not exist" % packet['model'], data=packet)
        packet_type = packet.get('type', 'import')
        if packet_type == 'import':
            data = {
                'source' : packet['source_name'],
                'model' : packet['model'],
                'fields' : packet['fields'],
                'sequence' : packet['sequence'],
                'fallback_values' : packet['fallback_values'],
                'rule_sequence' : packet['rule'],
            }
            for load_item in packet['load']:
                data.update({
                    'version' : load_item['version'],
                    'values' : load_item['values'],
                    'owner' : load_item['owner_name'],
                })
                self.create(cr, uid, data, context=context)
            return len(packet['load'])
        elif packet_type == 'delete':
            data = {
                'source' : packet['source_name'],
                'model' : packet['model'],
                'sequence' : packet['sequence'],
                'rule_sequence' : packet['rule'],
                'is_deleted' : True,
            }
            for sdref in packet['unload']:
                self.create(cr, uid, dict(data, sdref=sdref), context=context)
            return len(packet['unload'])
        else:
            raise Exception("Unable to unfold unknown packet type: " % packet_type)

    def run(self, cr, uid, ids, context=None):
        try:
            self.execute_update(cr, uid, ids, context=context)
        except BaseException, e:
            sync_log(self, e)
        return True

    def execute_update(self, cr, uid, ids=None, context=None):
        context = dict(context or {}, sync_update_execution=True)

        if ids is None:
            update_ids = self.search(cr, uid, [('run','=',False)], context=context)
        else:
            update_ids = ids
        if not update_ids:
            return ''

        # Sort updates by rule_sequence
        whole = self.browse(cr, uid, update_ids, context=context)
        update_groups = {}
        
        for update in whole:
            if update.is_deleted:
                group_key = (update.sequence, 1, -update.rule_sequence)
            else:
                group_key = (update.sequence, 0,  update.rule_sequence)
            try:
                update_groups[group_key].append(update)
            except KeyError:
                update_groups[group_key] = [update]
        self.write(cr, uid, update_ids, {'execution_date': fields.datetime.now()}, context=context)

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

        def secure_purge_data(obj, ids):
            try:
                cr.execute("SAVEPOINT unlink_update")
                # Don't try to purge, we never know if there
                obj.purge(cr, uid, ids, context=context)
            except:
                cr.execute("ROLLBACK TO SAVEPOINT unlink_update")
                raise
            else:
                cr.execute("RELEASE SAVEPOINT unlink_update")

        def group_import_update_execution(updates):
            obj = self.pool.get(updates[0].model)
            import_fields = eval(updates[0].fields)
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
                self.pool.get('ir.model.data').update_sd_ref(cr, uid,
                    dict((sdref, {'version':version,'sync_date':fields.datetime.now()}) for sdref, version in versions.items()),
                    context=context)

            #3 check for missing field : report missing fields
            bad_fields = self._check_fields(cr, uid, obj._name, import_fields, context=context)
            if bad_fields: 
                message += "Missing or unauthorized fields found : %s\n" % ", ".join(bad_fields)
                bad_fields = [import_fields.index(x) for x in bad_fields]

            i_id = import_fields.index('id')

            for update in updates:
                       
                row = eval(update.values)

                #4 check for fallback value : report missing fallback_value
                row = self._check_and_replace_missing_id(cr, uid, row, import_fields, fallback, message, context=context)
                xml_id = row[i_id]

                if bad_fields : 
                    row = [row[i] for i in range(len(import_fields)) if i not in bad_fields]

                values.append(row)
                update_ids.append(update.id)
                versions.append( (xml_id, update.version) )

                #1 conflict detection
                if self._conflict(cr, uid, update.sdref, update.version, context=context):
                    #2 if conflict => manage conflict according rules : report conflict and how it's solve
                    logs[update.id] = sync_log(self, "Conflict detected!", 'warning', data=(update.id, update.fields, update.values)) + "\n"
                    #TODO manage other conflict rules here (tfr note)

            if bad_fields:
                import_fields = [import_fields[i] for i in range(len(import_fields)) if i not in bad_fields]

            #5 import data : report error
            while values:
                try:
                    res = secure_import_data(obj, import_fields, values)
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
                        data = dict(zip(import_fields, values[value_index]))
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
                            res = secure_import_data(obj, import_fields, values[:value_index])
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
                    raise Exception(message+"Wrong number of imported rows in model %s (expected %s, but %s imported)!\nUpdate ids: %s\n" % (obj._name, len(values), res[0], update_ids))

            # Obvious
            assert len(values) == len(update_ids) == len(versions), \
                message+"""This error must never occur. Please contact the developper team of this module.\n"""

            return message

        def group_unlink_update_execution(updates):
            obj = self.pool.get(updates[0].model)
            assert obj is not None, "Cannot find object model=%s" % updates[0].model

            for update in updates:
                try:
                    update_vals = {
                        'editable' : False,
                        'run' : True,
                        'log' : '',
                    }
                    id = obj.find_sd_ref(cr, uid, update.sdref, context=context)
                    if not id:
                        update_vals['log'] = "Cannot find SD ref %s, skipped...\n\nReason: The record could be already deleted by another update." % update.sdref
                    else:
                        secure_purge_data(obj, [id])
                except BaseException, e:
                    e = "Error during unlink on model %s!\nUpdate ids: %s\nReason: %s\nSD ref:\n%s\n" \
                        % (obj._name, update_ids, tools.ustr(e), update.sdref)
                    self.write(cr, uid, [update.id], {
                        'run' : False,
                        'log' : tools.ustr(e)
                    }, context=context)
                    raise
                else:
                    self.write(cr, uid, update.id, update_vals, context=context)

            return

        error_message = ""
        imported, deleted = 0, 0
        for rule_seq in sorted(update_groups.keys()):
            updates = update_groups[rule_seq]
            if updates[0].is_deleted:
                group_unlink_update_execution(updates)
                deleted += len(updates)
            else:
                error_message += group_import_update_execution(updates)
                imported += len(updates)
        
        return (error_message.strip(), imported, deleted)

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
    
    def _conflict(self, cr, uid, sdref, next_version, context=None):
        ir_data = self.pool.get('ir.model.data')
        data_id = ir_data.find_sd_ref(cr, uid, sdref, context=context)
        # no data => no record => no conflict
        if not data_id: return False
        data_rec = ir_data.browse(cr, uid, data_id, context=context)
        return (not data_rec.is_deleted                                       # record doesn't exists => no conflict
                and (not data_rec.sync_date                                   # never synced => conflict
                     or (data_rec.last_modification                           # if last_modification exists, try the next
                         and data_rec.sync_date < data_rec.last_modification) # modification after synchro => conflict
                     or next_version < data_rec.version))                     # next version is lower than current version
    
    def _check_and_replace_missing_id(self, cr, uid, values, fields, fallback, message, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        for i in xrange(0, len(fields)):
            if '/id' in fields[i] and values[i]:
                res_val = []
                for full_xmlid in values[i].split(','):
                    if full_xmlid:
                        try:
                            module, sep, xmlid = full_xmlid.partition('.')
                            assert sep, "Cannot find an xmlid without specifying its module: xmlid=%s" % full_xmlid
                            if ir_model_data_obj.is_deleted(cr, uid, module, xmlid, context=context):
                                raise ValueError
                        except ValueError:
                            try:
                                fb = fallback.get(fields[i])
                                if not fb: raise ValueError
                                module, sep, xmlid = fb.partition('.')
                                assert sep, "Cannot find an xmlid without specifying its module: xmlid=%s" % fb
                                if ir_model_data_obj.is_deleted(cr, uid, module, xmlid, context=context): raise ValueError
                            except ValueError:
                                message += 'Missing record %s and no fallback value defined or missing fallback value, set to False\n' % full_xmlid
                            else:
                                message += 'Missing record %s replace by %s\n' % (full_xmlid, fb)
                                res_val.append(fb)
                        else:
                            res_val.append(full_xmlid)
                if not res_val:
                    values[i] = False
                else:
                    values[i] = ','.join(res_val)
        return values

    _order = 'id asc'

update_received()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
