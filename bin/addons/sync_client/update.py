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
from datetime import datetime

import re
import logging

from sync_common import sync_log, \
    add_sdref_column, translate_column, migrate_sequence_to_sequence_number, \
    fancy_integer, \
    split_xml_ids_list, normalize_xmlid

from msf_field_access_rights.osv_override import _get_instance_level


re_fieldname = re.compile(r"^\w+")
re_subfield_separator = re.compile(r"[./]")


# US-2837: in case update of the following models is received and the
# corresponding object has been deleted, it will be recreated.
# For other models not in this list, they will be set as run and get a message:
# 'Manually set to run by the system. Due to a delete'
OBJ_TO_RECREATE = [
    'res.partner',
    'account.period',
    'ir.model.access',
    'msf_field_access_rights.field_access_rule',
    'msf_field_access_rights.field_access_rule_line',
    'msf_button_access_rights.button_access_rule',
    'ir.rule',
    'hr.payment.method',
    'account.analytic.journal',
    'account.journal',
    'account.mcdb',
    'wizard.template',
    'account.analytic.account',
    'dest.cc.link',
    'replenishment.segment.line.amc',
    'replenishment.segment.line',
    'replenishment.segment.line.amc.month_exp',
    'replenishment.segment.date.generation',
]


class fv_formatter:
    def fmt(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for x in self.read(cr, uid, ids, ['fields', 'values'], context):
            if not x['fields'] or not x['values']:
                res[x['id']] = ''
            else:
                try:
                    values = eval(x['values'])
                    fields = eval(x['fields'])
                    i = 0
                    fmt = ""
                    for f in fields:
                        fmt += f + " -> " + tools.ustr(values[i]) + "\n"
                        i += 1
                    res[x['id']] = fmt
                except:
                    # Exceptions here would come from incorrectly formatted
                    # field/value strings, which will be caught in other places
                    # and logged better there.
                    res[x['id']] = '(exception)'
        return res

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
        'type' : fields.char('Group Type', size=256),
        'handle_priority': fields.boolean('Handle Priority'),
        'direction': fields.char('Direction', size=128, readonly=True),
    }

    _defaults = {
        'included_fields' : '[]',
        'active' : True,
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

            # Check model exists and is not null
            if not vals.get('model'):
                vals['active'] = False
            elif not self.pool.get('ir.model').search(cr, uid, [('model', '=',
                                                                 vals['model'])], limit=1, order='NO_ORDER', context=context):
                self._logger.debug("The following rule doesn't apply to your database and has been disabled. Reason: model %s does not exists!\n%s" % (vals['model'], vals))
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
        if remaining_ids:
            self.write(cr, uid, list(remaining_ids), {'active':False}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'active':False}, context=context)

    _order = 'sequence_number asc'

local_rule()

class update_to_send(osv.osv,fv_formatter):
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
        'sdref' : fields.char('SD ref', size=128, readonly=True, required=True, select=True),
        'fields':fields.text('Fields', size=128, readonly=True),
        'fieldsvalues': fields.function(fv_formatter.fmt, method=True, type='char'),
        'is_deleted' : fields.boolean('Is deleted?', readonly=True, select=True),
        'force_recreation' : fields.boolean('Force record recreation', readonly=True),
        'handle_priority': fields.boolean('Handle Priority'),
    }

    _defaults = {
        'sent' : False,
        'is_deleted' : False,
    }

    _logger = logging.getLogger('sync.client')

    @translate_column('model', 'ir_model', 'model', 'character varying(64)')
    @add_sdref_column
    def _auto_init(self, cr, context=None):
        super(update_to_send, self)._auto_init(cr, context=context)

    def create_update(self, cr, uid, rule_id, session_id, context=None):
        rule = self.pool.get('sync.client.rule').browse(cr, uid, rule_id, context=context)
        update = self

        def create_normal_update(self, rule, context):
            domain = eval(rule.domain or '[]')
            export_fields = eval(rule.included_fields or '[]')
            if 'id' not in export_fields:
                export_fields.append('id')
            ids_need_to_push = self.need_to_push(cr, uid, [],
                                                 [m.group(0) for m in map(re_fieldname.match, export_fields)],
                                                 empty_ids=True,
                                                 context=context)
            if not ids_need_to_push:
                return 0
            domain.append(('id', 'in', ids_need_to_push))

            order = None
            if hasattr(self, '_sync_order'):
                # keep same id order at HQ and lower level
                order = self._sync_order

            ids_to_compute = self.search_ext(cr, uid, domain, order=order, context=context)
            if not ids_to_compute:
                return 0

            owners = self.get_destination_name(cr, uid,
                                               ids_to_compute, rule.owner_field, context)

            if rule.direction == 'mission-private' and owners:
                for _id in owners:
                    own = owners[_id]
                    if not isinstance(own, (list, tuple)):
                        own = [own]
                    if self.pool.get('msf.instance').search_exists(cr, uid, [('instance', 'in', own), ('level', '!=', 'coordo')], context=context):
                        assert False, "mission-private rule, object: %s, id: %s, owner must be a coordo: %s" % (self._name, _id, own)

            min_offset = 0
            max_offset = len(ids_to_compute)

            while min_offset < max_offset:
                offset = min_offset + 200 < max_offset and min_offset +200 or max_offset
                datas = self.export_data(cr, uid, ids_to_compute[min_offset:offset],
                                         export_fields, context=context)['datas']
                sdrefs = self.get_sd_ref(cr, uid, ids_to_compute[min_offset:offset],
                                         field=['name','version','force_recreation','id'], context=context)
                ustr_export_fields = tools.ustr(export_fields)
                for (id, row) in zip(ids_to_compute[min_offset:offset], datas):
                    sdref, version, force_recreation, data_id = sdrefs[id]
                    for owner in (owners[id] if isinstance(owners[id], list) else [owners[id]]):
                        update_id = update.create(cr, uid, {
                            'session_id' : session_id,
                            'rule_id' : rule.id,
                            'owner' : owner,
                            'model' : self._name,
                            'sdref' : sdref,
                            'version' : version + 1,
                            'force_recreation' : force_recreation,
                            'fields' : ustr_export_fields,
                            'values' : tools.ustr(row),
                            'handle_priority' : rule.handle_priority,
                        }, context=context)
                        update._logger.debug("Created 'normal' update model=%s id=%d (rule sequence=%d)" % (self._name, update_id, rule.id))
                min_offset += 200

            self.clear_synchronization(cr, uid, ids_to_compute, context=context)

            return len(ids_to_compute)

        def create_delete_update(self, rule, context):
            if not rule.can_delete:
                return 0

            ids_to_delete = self.search_deleted(cr, uid, module='sd', context=context, for_sync=True)

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

            self.clear_synchronization(cr, uid, ids_to_delete, context=context)

            return len(ids_to_delete)

        update_context = dict(context or {}, sync_update_creation=True)
        obj = self.pool.get(rule.model)
        assert obj, "Cannot find model %s of rule id=%d!" % (rule.model, rule.id)
        return (create_normal_update(obj, rule, update_context), create_delete_update(obj, rule, update_context))

    def create_package(self, cr, uid, session_id=None, packet_size=None, context=None):
        domain = session_id and [('session_id', '=', session_id), ('sent', '=', False)] or [('sent', '=', False)]
        ids = self.search(cr, uid, domain, limit=packet_size,  order='id asc', context=context)

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
                    'force_recreation' : update.force_recreation,
                    'handle_priority' : update.handle_priority,
                })
            ids_in_package.append(update.id)
        data['load'] = values
        data['unload'] = deleted
        self._logger.debug("package created for update ids=%s" % ids_in_package)
        return (ids_in_package, data)

    def sync_finished(self, cr, uid, session_id, sync_field='sync_date', context=None):
        # specific case to split the active field on product.product
        # i.e: at COO an update received on product must not block a possible update on active field to the project
        cr.execute('''
            update product_product set active_sync_change_date = upd.create_date
                from sync_client_update_to_send upd, ir_model_data d, sync_client_rule rule
            where
                rule.id = upd.rule_id and
                rule.sequence_number in (602, 603) and
                d.model = 'product.product' and
                d.name = upd.sdref and
                product_product.id = d.res_id and
                upd.session_id = %s
        ''', (session_id, ))


        cr.execute('''update ir_model_data d set
                version=upd.version, '''+sync_field+'''=upd.create_date, resend='f'
            from sync_client_update_to_send upd
            where
                upd.session_id=%s and
                upd.sdref=d.name and
                d.module='sd'
        ''', (session_id, )) # not_a_user_entry

        cr.execute('''update sync_client_update_to_send set sent='t', sent_date=%s where session_id=%s ''', (fields.datetime.now(), session_id))
        self._logger.debug(_("Push finished: %d updates") % cr.rowcount)

    _order = 'create_date desc, id desc'
update_to_send()

class update_received(osv.osv,fv_formatter):

    _name = "sync.client.update_received"
    _rec_name = 'source'
    _sync_field = 'sync_field'

    _columns = {
        'source': fields.char('Source Instance', size=128, readonly=True),
        'owner': fields.char('Owner Instance', size=128, readonly=True),
        'model' : fields.char('Model', size=64, readonly=True, select=True),
        'sdref' : fields.char('SD ref', size=128, readonly=True, required=True, select=1),
        'is_deleted' : fields.boolean('Is deleted?', readonly=True, select=True),
        'force_recreation' : fields.boolean('Force record recreation', readonly=True),
        'sequence_number' : fields.integer('Sequence', readonly=True, group_operator='count'),
        'rule_sequence' : fields.integer('Rule Sequence', readonly=True, select=1),
        'version' : fields.integer('Version', readonly=True),
        'fancy_version' : fields.function(fancy_integer, method=True, string="Version", type='char', readonly=True),
        'fields' : fields.text("Fields"),
        'values' : fields.text("Values"),
        'fieldsvalues': fields.function(fv_formatter.fmt, method=True, type='char'),
        'run' : fields.boolean("Run", readonly=True, select=True),
        'log' : fields.text("Execution Messages", readonly=True),
        'log_first_notrun' : fields.text("First not run message", readonly=True),
        'fallback_values':fields.text('Fallback values'),
        'handle_priority': fields.boolean('Handle Priority', readonly=True),

        'create_date':fields.datetime('Synchro date/time', readonly=True),
        'execution_date':fields.datetime('Execution date', readonly=True),
        'editable' : fields.boolean("Set editable"),
        'manually_ran': fields.boolean('Has been manually tried', readonly=True),
        'manually_set_run_date': fields.datetime('Manually to run Date', readonly=True),
    }


    line_error_re = re.compile(r"^Line\s+(\d+)\s*:\s*(.+)", re.S)

    _logger = logging.getLogger('sync.client')

    def _set_not_run(self, cr, uid, ids, log, context=None):
        data = {
            'run': False,
            'editable': False,
            'execution_date': datetime.now()
        }
        if log:
            data['log'] = log
        self.write(cr, uid, ids, data, context=context)

        # store 1st not run message
        if log:
            if isinstance(ids, int):
                ids = [ids]
            cr.execute("""update sync_client_update_received set log_first_notrun=%s
                where id in %s and
                coalesce(log_first_notrun, '')=''
            """, (log, tuple(ids)))

        return True


    @translate_column('model', 'ir_model', 'model', 'character varying(64)')
    @add_sdref_column
    @migrate_sequence_to_sequence_number
    def _auto_init(self, cr, context=None):
        super(update_received, self)._auto_init(cr, context=context)

    def unfold_package(self, cr, uid, packet, context=None):
        if not packet:
            return 0
        self._logger.debug("Unfold package %s" % packet['model'])
        if not self.pool.get('ir.model').search(cr, uid, [('model', '=',
                                                           packet['model'])], limit=1, order='NO_ORDER', context=context):
            sync_log(self, "Model %s does not exist" % packet['model'], data=packet)
        packet_type = packet.get('type', 'import')
        if packet_type == 'import':
            data = {
                'source' : packet['source_name'],
                'model' : packet['model'],
                'fields' : packet['fields'],
                'sequence_number' : packet['sequence'],
                'fallback_values' : packet['fallback_values'],
                'rule_sequence' : packet['rule'],
            }
            for load_item in packet['load']:
                data.update({
                    'version' : load_item['version'],
                    'values' : load_item['values'],
                    'owner' : load_item['owner_name'],
                    'sdref' : load_item['sdref'],
                    'force_recreation' : load_item['force_recreation'],
                    'handle_priority' : load_item['handle_priority'],
                })
                self.create(cr, uid, data, context=context)
            return len(packet['load'])
        elif packet_type == 'delete':
            data = {
                'source' : packet['source_name'],
                'model' : packet['model'],
                'sequence_number' : packet['sequence'],
                'rule_sequence' : -packet['rule'],
                'is_deleted' : True,
            }
            for sdref in packet['unload']:
                self.create(cr, uid, dict(data, sdref=sdref), context=context)
            return len(packet['unload'])
        else:
            raise Exception("Unable to unfold unknown packet type: " % packet_type)

    def manual_set_as_run(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'run': True, 'log': 'Set manually to run without execution', 'manually_set_run_date': fields.datetime.now(), 'editable': False}, context=context)
        return True

    def run(self, cr, uid, ids, context=None):
        try:
            self.execute_update(cr, uid, ids, context=context)
        except BaseException as e:
            sync_log(self, e)
        finally:
            self.write(cr, uid, ids, {'manually_ran': True})
        return True

    def execute_update(self, cr, uid, ids=None, priorities=None, context=None):
        context = dict(context or {}, sync_update_execution=True)
        context['lang'] = 'en_US'

        # force user to user_sync
        uid = self.pool.get('res.users')._get_sync_user_id(cr)

        local_entity = self.pool.get('sync.client.entity').get_entity(
            cr, uid, context=context)
        instance_level = _get_instance_level(self, cr, uid)
        if ids is None:
            update_ids = self.search(cr, uid, [('run','=',False)], order='id asc', context=context)
        else:
            update_ids = ids
        if not update_ids:
            return ''

        if priorities is None:
            self._logger.warn(
                "Executing update without having entity priorities... "
                "this may results in a lost of modification to push")

        # Sort updates by rule_sequence
        whole = self.browse(cr, uid, update_ids, context=context)
        update_groups = {}
        for update in whole:
            if update.is_deleted:
                group_key = (update.sequence_number, 1, update.rule_sequence)
            else:
                group_key = (update.sequence_number, 0,  update.rule_sequence)
            update_groups.setdefault(group_key, []).append(update)

        def secure_import_data(obj, fields, values):
            try:
                cr.rollback_org, cr.rollback = cr.rollback, lambda:None
                cr.commit_org, cr.commit = cr.commit, lambda:None
                cr.execute("SAVEPOINT import_data")
                res = obj.import_data(cr, uid, fields, values, mode='update', current_module='sd', noupdate=True, context=context)
            except BaseException as e:
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

        def secure_unlink_data(obj, ids):
            try:
                cr.execute("SAVEPOINT unlink_update")
                # Keep a trace of the deletion
                if obj._name == 'account.move':
                    obj.unlink(cr, uid, ids, context=context, check=False) #ITWG-84: Send this flag to not check on lines - otherwise it takes too much!
                else:
                    obj.unlink(cr, uid, ids, context=context)
            except:
                cr.execute("ROLLBACK TO SAVEPOINT unlink_update")
                raise
            else:
                cr.execute("RELEASE SAVEPOINT unlink_update")

        def group_import_update_execution(obj, updates):
            import_fields = eval(updates[0].fields)
            fallback = eval(updates[0].fallback_values or '{}')
            message = ""
            values = []
            update_ids = []
            versions = []
            logs = {}

            def success(update_ids, versions):
                # write only for ids not in log as another write is performed
                # for those in logs. This avoid two writes on the same object
                ids_not_in_logs = list(set(update_ids) - set(logs.keys()))
                ids_in_logs = list(set(update_ids).intersection(list(logs.keys())))
                execution_date = datetime.now()
                if ids_not_in_logs:
                    self.write(cr, uid, ids_not_in_logs, {
                        'execution_date': execution_date,
                        'editable' : False,
                        'run' : True,
                        'log' : '',
                    }, context=context)
                for update_id in ids_in_logs:
                    self.write(cr, uid, [update_id], {
                        'execution_date': execution_date,
                        'editable' : False,
                        'run' : True,
                        'log' : logs[update_id],
                    }, context=context)
                logs.clear()
                for sdref, version in list(versions.items()):
                    try:
                        self.pool.get('ir.model.data').update_sd_ref(
                            cr, uid, sdref,
                            {
                                'version': version,
                                self._sync_field: fields.datetime.now(),
                                'force_recreation' : False,
                                'touched' : '[]',
                            },
                            consider_resend=True,
                            context=context)
                    except ValueError:
                        self._logger.warning("Cannot find record %s during update execution process!" % update.sdref)

            #3 check for missing field : report missing fields
            bad_fields = self._check_fields(cr, uid, obj._name, import_fields, context=context)
            if bad_fields:
                message += "Missing or unauthorized fields found : %s\n" % ", ".join(bad_fields)
                bad_fields = [import_fields.index(x) for x in bad_fields]

            # Prepare updates
            # TODO: skip updates not preparable
            for update in updates:
                prev_nr_ids = self.search(cr, uid,
                                          [('sdref', '=', update.sdref),
                                           ('is_deleted', '=', False),
                                              ('run', '=', False),
                                              ('rule_sequence', '=', update.rule_sequence),
                                              ('sequence_number', '<', update.sequence_number)])
                # previous not run on the same (sdref, rule_sequence): do not execute
                if prev_nr_ids:
                    if update.rule_sequence in (602, 603):
                        # update on product state, we don't care of previous NR
                        self.write(cr, uid, prev_nr_ids, {'run': 't', 'log': 'Set as Run due to a later update on the same record/rule.', 'editable': False, 'execution_date': datetime.now()}, context=context)
                    else:
                        self._set_not_run(cr, uid, [update.id], log="Cannot execute due to previous not run on the same record/rule.", context=context)
                        continue

                row = eval(update.values)

                if update.model == 'product.merged':
                    old_product_sdref = row[import_fields.index('old_product_id/id')]
                    new_product_sdref = row[import_fields.index('new_product_id/id')]
                    if self.search_exists(cr, uid, [('sdref', 'in', [old_product_sdref, new_product_sdref]), ('run', '=', False), ('sequence_number', '<=', update.sequence_number)]):
                        self._set_not_run(cr, uid, [update.id], log="Cannot execute due to previous not run on produts %s or %s" % (old_product_sdref, new_product_sdref), context=context)
                        continue

                #4 check for fallback value : report missing fallback_value
                #US-852: in case the account_move_line is given but not exist, then do not let the import of the current entry
                #US-2147: same thing for property_product_pricelist and property_product_pricelist_purchase
                result = self._check_and_replace_missing_id(cr, uid,
                                                            import_fields, row, fallback, message, update, local_level=instance_level, context=context)

                if bad_fields :
                    row = [row[i] for i in range(len(import_fields)) if i not in bad_fields]

                if result['res']: #US-852: if everything is Ok, then do import as normal
                    if result.get('run_without_exec'):
                        self.write(cr, uid, update.id, {
                            'run': True,
                            'editable': False,
                            'execution_date': datetime.now(),
                            'log': 'Set as run without exec: %s' % (result['error_message'],),
                        })
                    elif obj._name == 'hr.employee' and obj._set_sync_update_as_run(cr, uid, dict(list(zip(import_fields, row))), update.sdref, context=context):
                        self.write(cr, uid, update.id, {
                            'run': True,
                            'editable': False,
                            'execution_date': datetime.now(),
                            'log': 'Set as Run because this employee already exists in the instance',
                        })
                    else:
                        values.append(row)
                        update_ids.append(update.id)
                        versions.append( (update.sdref, update.version) )

                        #1 conflict detection
                        if self._conflict(cr, uid, update.sdref, update.version, context=context):
                            #2 if conflict => manage conflict according rules : report conflict and how it's solve
                            index_id = eval(update.fields).index('id')
                            sd_ref = eval(update.values)[index_id]
                            logs[update.id] = "Warning: Conflict detected! in content: (%s, %r)" % (update.id, sd_ref)
                else: #US-852: if account_move_line is missing then ignore the import, and set it as not run
                    self._set_not_run(cr, uid, [update.id],
                                      log=result['error_message'],
                                      context=context
                                      )

            if bad_fields:
                import_fields = [import_fields[i] for i in range(len(import_fields)) if i not in bad_fields]

            # Import batch of values
            while values:
                try:
                    res = secure_import_data(obj, import_fields, values)
                except Exception as import_error:
                    import_error = "Error during importation in model %s!\nUpdate ids: %s\nReason: %s\nData imported:\n%s\n" % (obj._name, update_ids, tools.ustr(import_error), "\n".join([tools.ustr(v) for v in values]))
                    # Rare Exception: import_data raised an Exception
                    self._set_not_run(cr, uid, update_ids,
                                      log=import_error.strip(),
                                      context=context
                                      )
                    raise Exception(message+import_error)
                # end of the loop: all remaining values has been imported
                if res[0] == len(values):
                    success( update_ids, \
                             dict(versions) )
                    break
                # import_data error detection
                elif res[0] == -1:
                    # Regular exception
                    import_message = res[2]
                    line_error = self.line_error_re.search(import_message)
                    if line_error:
                        # Extract the failed data
                        value_index, import_message = int(line_error.group(1))-1, line_error.group(2)
                        data = dict(list(zip(import_fields, values[value_index])))
                        if "('warning', 'Warning !')" == import_message:
                            import_message = "Unknown! Please check the constraints of linked models. The use of raise Python's keyword in constraints typically give this message."
                        import_message = "Cannot import in model %s:\nData: %s\nReason: %s\n" % (obj._name, data, import_message)
                        message += import_message
                        # remove the row that failed
                        values.pop(value_index)
                        versions.pop(value_index)
                        self._set_not_run(cr, uid, [update_ids.pop(value_index)],
                                          log=import_message.strip(),
                                          context=context
                                          )
                    else:
                        # Rare case where no line is given by import_data
                        self.write(cr, uid, update_ids, {
                            'execution_date': datetime.now(),
                        }, context=context)
                        message += "Cannot import data in model %s:\nReason: %s\n" % (obj._name, import_message)
                        raise Exception(message)
                    # Re-start import_data on rows that succeeds before
                    if value_index > 0:
                        # Try to import the beginning of the values and permit the import of the rest
                        # db rollback, previous updates will be replayed, clear the id cache
                        self.pool.get('ir.model.data')._get_id.clear_cache(cr.dbname)
                        try:
                            res = secure_import_data(obj, import_fields, values[:value_index])
                            assert res[0] == value_index, res[2]
                        except Exception as import_error:
                            raise Exception(message+import_error.message)
                        success( update_ids[:value_index], \
                                 dict(versions[:value_index]) )
                        # truncate the rows just after the last non-failing row
                        values = values[value_index:]
                        update_ids = update_ids[value_index:]
                        versions = versions[value_index:]
                else:
                    # Rare exception, should never occur
                    raise AssertionError(message+"Wrong number of imported rows in model %s (expected %s, but %s imported)!\nUpdate ids: %s\n" % (obj._name, len(values), res[0], update_ids))

            if obj._name == 'ir.translation':
                self.pool.get('ir.translation')._get_reset_cache_at_sync(cr, uid)
            elif obj._name == 'ir.model.access':
                self.pool.get('ir.ui.menu')._clean_cache(cr.dbname)

            # Obvious
            assert len(values) == len(update_ids) == len(versions), \
                message+"""This error must never occur. Please contact the developper team of this module.\n"""

            return message

        def group_unlink_update_execution(obj, sdref_update_ids):
            obj_ids = obj.find_sd_ref(cr, uid, list(sdref_update_ids.keys()), context=context)
            done_ids = []
            for sdref, id in list(obj_ids.items()):
                try:
                    update_id = sdref_update_ids[sdref]
                    secure_unlink_data(obj, [id])
                except BaseException as e:
                    if isinstance(e, osv.except_osv):
                        error = '%s: %s' % (e.name, e.value)
                    else:
                        error = e
                    e = "Error during unlink on model %s!\nid: %s\nUpdate id: %s\nReason: %s\nSD ref:\n%s\n" \
                        % (obj._name, id, update_id, tools.ustr(error), update.sdref)
                    self._set_not_run(cr, uid, [update_id],
                                      log=tools.ustr(e),
                                      context=context
                                      )

                    ########################################################################
                    #
                    # UFTP-116: Cannot raise the exception here, because it will stop the whole sync!!!! Just set this line to become not run, OR set it run but error message
                    # If we just set it not run, it will be again and again executed but never successfully, and thus it will remain for every not run, attempt to execute EVERYTIME!
                    # ???? So, just set it RUN?
                    ########################################################################

#                    raise
                else:
                    done_ids.append(update_id)

            self.write(cr, uid, done_ids, {
                'execution_date': datetime.now(),
                'editable' : False,
                'run' : True,
                'log' : '',
            }, context=context)
            sdrefs = [elem['sdref'] for elem in self.read(cr, uid, done_ids, ['sdref'], context=context)]
            for sdref in sdrefs:
                self.pool.get('ir.model.data').update_sd_ref(
                    cr, uid, sdref, {
                        'sync_date': fields.datetime.now(),
                        'touched' : '[]',
                        'resend': False,
                    },
                    context=context)
            return

        error_message = ""
        imported, deleted = 0, 0
        rule_seq_list = list(update_groups.keys())
        rule_seq_list.sort()
        for rule_seq in rule_seq_list:
            updates = update_groups[rule_seq]
            context['sync_update_session'] = rule_seq[0]
            obj, do_deletion = self.pool.get(updates[0].model), updates[0].is_deleted
            assert obj is not None, "Cannot find object model=%s" % updates[0].model
            # Remove updates about deleted records in the list
            duplicates = []
            sdref_update_ids = {}
            for update in updates:
                if do_deletion and update.sdref in sdref_update_ids:
                    duplicates.append(update.id)
                else:
                    sdref_update_ids[update.sdref] = update.id
            if duplicates:
                self.write(cr, uid, duplicates, {
                    'execution_date': datetime.now(),
                    'editable' : False,
                    'run' : True,
                    'log' : "This update has been ignored because it is duplicated.",
                }, context=context)
            # For bi-private rules, it is possible that the sdref doesn't exists /!\
            # - In case of import update, if sdref doesn't exists, the initial
            #   value is False in order to keep it for group execution
            # - For delete updates, if sdref doesn't exists, the initial value
            #   is True in order to keep ignore it from group deletion
            sdref_are_deleted = dict.fromkeys(list(sdref_update_ids.keys()), do_deletion)
            sdref_are_deleted.update(
                obj.find_sd_ref(cr, uid, list(sdref_update_ids.keys()), field='is_deleted', context=context) )
            update_id_are_deleted = {}
            for key in sdref_update_ids:
                update_id_are_deleted[sdref_update_ids[key]] = sdref_are_deleted[key]
            deleted_update_ids = [update_id for update_id, is_deleted in list(update_id_are_deleted.items()) if is_deleted]


            if deleted_update_ids:
                sdrefs = [elem['sdref'] for elem in self.read(cr, uid, deleted_update_ids, ['sdref'], context=context)]
                generic_domain = [
                    ('sdref', 'in', sdrefs),
                    ('run', '=', False),
                    ('is_deleted', '=', False)]
                to_set_run_domain = generic_domain + [('model', 'not in', OBJ_TO_RECREATE)]
                to_set_recreate_domain = generic_domain + [('model', 'in', OBJ_TO_RECREATE)]

                to_set_run_ids = self.search(cr, uid, to_set_run_domain,
                                             order='NO_ORDER', context=context)
                if to_set_run_ids:
                    self.write(cr, uid, to_set_run_ids, {
                        'execution_date': datetime.now(),
                        'editable' : False,
                        'run' : True,
                        'log' : 'Manually set to run by the system. Due to a delete',
                    }, context=context)

                # US-2837: check if some objects have to be recreated in case
                # an update is received after the object was deleted
                to_set_recreate_ids = self.search(cr, uid, to_set_recreate_domain,
                                                  order='NO_ORDER', context=context)
                if to_set_recreate_ids:
                    deleted_update_ids = [x for x in deleted_update_ids if x not in to_set_recreate_ids]
                    self.write(cr, uid, to_set_recreate_ids, {
                        'force_recreation': True,
                    }, context=context)

                update_ignored = list(set(deleted_update_ids) - set(to_set_run_ids + to_set_recreate_ids))
                if update_ignored:
                    self.write(cr, uid, update_ignored, {
                        'execution_date': datetime.now(),
                        'editable' : False,
                        'run' : True,
                        'log' : "This update has been ignored because the record is marked as deleted or does not exists.",
                    }, context=context)

            updates = [update for update in updates if update.id not in deleted_update_ids or
                       (not do_deletion and update.force_recreation)]

            if not updates:
                continue
            # ignore updates of instances that have lower priorities
            if priorities is not None and not do_deletion:
                assert local_entity.name in priorities, \
                    "Oops! I don't even know my own priority."
                import_fields = [
                    re_subfield_separator.split(field)[0]
                    for field in eval(updates[0].fields)
                ]
                sdref_res_id = obj.find_sd_ref(cr, uid,
                                               list(sdref_update_ids.keys()),
                                               context=context)
                confilcting_ids = obj.need_to_push(cr, uid,
                                                   list(sdref_res_id.values()), import_fields, context=context)
                confilcting_updates = [update for update in updates if update.handle_priority and \
                                       update.sdref in sdref_res_id and \
                                       sdref_res_id[update.sdref] in confilcting_ids]
                updates_to_ignore = [update for update in confilcting_updates if priorities[update.source] \
                                     > priorities[local_entity.name]]
                for update in confilcting_updates:
                    if update not in updates_to_ignore:
                        self._logger.warn(
                            "The update %d has overwritten your modification "
                            "on record sd.%s because of higher priority "
                            "(update source: %s > local instance: %s)"
                            % (update.id, update.sdref,
                               update.source, local_entity.name))
                if updates_to_ignore:
                    self.write(cr, uid,
                               [update.id for update in updates_to_ignore],
                               {
                                   'execution_date': datetime.now(),
                                   'editable' : False,
                                   'run' : True,
                                   'log' : \
                                   "This update has been ignored because it " \
                                   "interfere with a local modification while the " \
                                   "origin instance has a lower priority.\n\n" \
                                   "(update source: %s < local instance: %s)" \
                                   % (update.source, local_entity.name),
                               },
                               context=context)
                    updates = [update for update in updates if update not in updates_to_ignore]
            # Proceed
            if not updates:
                continue
            elif do_deletion:
                group_unlink_update_execution(obj, dict((update.sdref, update.id) for update in updates if update.id not in duplicates))
                deleted += len(updates)
            else:
                error_message += group_import_update_execution(obj, updates)
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

    def _check_and_replace_missing_id(self, cr, uid, fields, values, fallback,
                                      message, update, local_level=None, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        result = {
            'res': True,
            'error_message': ''
        }

        def check_xmlid(xmlid):
            module, sep, xmlid = xmlid.partition('.')
            assert sep, "Cannot find an xmlid without specifying its module: xmlid=%s" % module
            return not ir_model_data_obj.is_deleted(cr, uid, module, xmlid, context=context)

        for i, field, value in zip(list(range(len(fields))), fields, values):
            # replace English by MSF English for the updates on partners where English had been selected at some point
            # (so that the initial synchro on new instances isn't blocked)
            if update.model == 'res.partner' and field == 'lang' and value == 'en_US':
                values[i] = 'en_MF'
            if '/id' not in field: continue
            if not value: continue
            res_val = []
            for xmlid in map(normalize_xmlid, split_xml_ids_list(value)):
                try:
                    if not check_xmlid(xmlid):
                        raise ValueError
                except ValueError:
                    try:
                        #US-852: if account_move_line is given, then cannot use the fallback value, but exit the import!
                        # THIS FIX COULD ALSO OPEN FOR OTHER BUG, BUT CHECK IF THE RULES THAT CONTAIN THE OBJECT (HERE account_move_line)
                        if 'account_move_line' in xmlid:
                            m, sep, sdref = xmlid.partition('.')
                            if self.search(cr, uid, [('sdref', '=', sdref), ('run', '=', False)], order='NO_ORDER', context=context):
                                result['res'] = False
                                result['error_message'] = 'Cannot execute due to missing the %s' % field
                                return result
                        if '/analytic_distribution/' in xmlid:
                            self.pool.get('analytic.distribution').import_data(cr, uid, ['name', 'id'], [['Auto created', xmlid]], mode='update', current_module='sd', noupdate=True, context=context)
                            res_val.append(xmlid)
                            continue

                        #US-2147: property_product_pricelist/id and
                        # property_product_pricelist_purchase/id are required
                        # fields, return False if the xmlid don't exists
                        # US-2478 return False if a Cost Center is synched without its parent
                        property_product_pricelist_missing = field in ('property_product_pricelist/id',
                                                                       'property_product_pricelist_purchase/id')
                        cc_parent_missing = 'account_analytic_account' in xmlid and 'category' in fields \
                                            and values[fields.index('category')] == 'OC' and field == 'parent_id/id'
                        if property_product_pricelist_missing or cc_parent_missing:
                            result['res'] = False
                            result['error_message'] = 'Cannot execute due to missing the %s' % field
                            return result

                        if update.model == 'res.partner.address' and field == 'partner_id/id':
                            # ignore update except if we have a previous NR on the partner
                            m, sep, sdref = xmlid.partition('.')
                            if self.search_exists(cr, uid, [
                                ('sdref', '=', sdref),
                                ('run', '=', False),
                                ('sequence_number', '<=', update.sequence_number)
                            ], context=context):
                                return {'res': False, 'error_message': 'partner_id %s not found' % xmlid}
                            return {'res': True, 'run_without_exec': True, 'error_message': 'partner_id %s not found' % xmlid}
                        if update.model == 'account.tax' and field == 'partner_id/id':
                            return {'res': False, 'error_message': 'partner_id %s not found' % xmlid}
                        if update.model == 'account.analytic.line' and field in ('cost_center_id/id', 'destination_id/id'):
                            return {'res': False, 'error_message': 'Analytic Account %s not found' % xmlid}

                        if update.model == 'account.move.reconcile' and field in ['line_id/id', 'partial_line_ids/id']:
                            # not an issue if we are a project and no NR in the pipe
                            if local_level != 'project' or self.search(cr, uid, [('sdref', '=', sdref), ('run', '=', False)], order='NO_ORDER', context=context):
                                return {'res': False, 'error_message': 'JI %s not found' % xmlid}

                        fb = fallback.get(field, False)
                        if not fb:
                            raise ValueError("no fallback value defined")
                        elif check_xmlid(fb):
                            raise ValueError("fallback value %s has been deleted" \
                                             % fb)
                    except ValueError as e:
                        message += 'Missing record %s and %s, set to False\n' \
                                   % (xmlid, e)
                    else:
                        message += 'Missing record %s replaced by %s\n' \
                                   % (xmlid, fb)
                        res_val.append(fb)
                else:
                    res_val.append(xmlid)
            values[i] = ','.join(res_val) if res_val else False
        return result


    _order = 'id desc'

update_received()


class update_link(osv.osv_memory):
    _name = 'update.link'
    _description = 'Handling of the Links to Updates Sent and Received'

    def _open_update_list(self, cr, uid, ids, update_type='received', context=None):
        """
        Returns the Update Received or Sent View for the selected entries.
        :param update_type: String. If 'received', will open the Update Received View. Else will open the Update Sent View.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if context.get('active_ids'):
            ids = context.get('active_ids')

        model = context.get('model')
        if model and isinstance(model, str):
            ir_model_obj = self.pool.get('ir.model.data')
            ir_model_data_ids = ir_model_obj.search(cr, uid, [('module', '=', 'sd'),
                                                              ('model', '=', model),
                                                              ('res_id', 'in', ids)], context=context)

            # get the names of all the selected entries if possible, else the name of the object
            model_obj = self.pool.get(model)
            try:
                obj_names = model_obj.name_get(cr, uid, ids, context=context)
                descr = ' / '.join([x[1] for x in obj_names])
            except KeyError:
                descr = model_obj._description or model_obj._name or ''

            if ir_model_data_ids:
                sdrefs = ir_model_obj.browse(cr, uid, ir_model_data_ids, fields_to_fetch=['name'],
                                             context=context)

                domain = [('sdref', 'in', [sdref.name for sdref in sdrefs])]
        tree_view = update_type == 'received' and 'update_received_tree_view' or 'sync_client_update_to_send_tree_view'
        view_id = ir_model_obj.get_object_reference(cr, uid, 'sync_client', tree_view)
        view_id = view_id and view_id[1] or False
        search_view = update_type == 'received' and 'update_received_search_view' or 'update_sent_search_view'
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'sync_client', search_view)
        search_view_id = search_view_id and search_view_id[1] or False
        res_model = update_type == 'received' and 'sync.client.update_received' or 'sync.client.update_to_send'
        return {
            'name': '%s %s' % (update_type == 'received' and _('Update Received Monitor') or _('Update Sent Monitor'), descr),
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': [search_view_id],
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def open_updates_received(self, cr, uid, ids, context):
        return self._open_update_list(cr, uid, ids, update_type='received', context=context)

    def open_updates_sent(self, cr, uid, ids, context):
        return self._open_update_list(cr, uid, ids, update_type='sent', context=context)

update_link()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
