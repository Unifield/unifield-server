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

import traceback
import logging
from .log_sale_purchase import SyncException
from .log_sale_purchase import RunWithoutException

from tools.safe_eval import safe_eval as eval

class dict_to_obj(object):
    def __init__(self, values):
        assert isinstance(values, dict), "Must be a dictionary"
        self.values = values
        for k, v in list(values.items()):
            if isinstance(v, dict):
                v = dict_to_obj(v)
            elif isinstance(v, (list, tuple)):
                gen = (dict_to_obj(i) if isinstance(i, dict) else i \
                       for i in v)
                v = type(v)(gen)
            setattr(self, k, v)

    def __str__(self):
        return str(self.values)

    def to_dict(self):
        return self.values


class local_message_rule(osv.osv):

    _name = 'sync.client.message_rule'

    _columns = {
        'name' : fields.char('Rule name', size=64, readonly=True),
        'server_id' : fields.integer('Server ID'),
        'model' : fields.char('Model Name',size=128),
        'domain' : fields.text('Domain', required=False, readonly=True),
        'filter_method' : fields.char('Filter Method', size=64, help='The method to use to find target records instead of a domain.', readonly=True),
        'sequence_number' : fields.integer('Sequence', readonly=True),
        'remote_call': fields.text('Method to call', required=True),
        'arguments': fields.text('Arguments of the method', required=True),
        'destination_name': fields.char('Fields to extract destination', size=256, required=True),
        'active' : fields.boolean('Active', select=True),
        'type' : fields.char('Group Type', size=256),
        'wait_while': fields.text('Wait while', required=False, help='Wait during specified domain to send the message'),
    }

    _logger = logging.getLogger('sync.client')

    def save(self, cr, uid, data_list, context=None):
        # Get the whole ids of existing and active rules
        remaining_ids = set(self.search(cr, uid, [], context=context))

        for vals in (dict(data) for data in data_list):
            assert 'server_id' in vals, "The following rule doesn't seem to have the required field server_id: %s" % vals

            # Check model exists or is null
            if not vals.get('model'):
                vals['active'] = False
            elif not self.pool.get('ir.model').search(cr, uid, [('model', '=',
                                                                 vals['model'])], limit=1, order='NO_ORDER', context=context):
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
        if remaining_ids:
            self.write(cr, uid, list(remaining_ids), {'active':False}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'active':False}, context=context)

    def get_rule_by_sequence(self, cr, uid, sequence_number, context=None):
        rules = self.search(cr, uid, [('sequence_number', '=', sequence_number)], context=context)
        if rules:
            return self.browse(cr, uid, rules, context=context)[0]
        return False

    def get_rule_by_remote_call(self, cr, uid, remote_call, context=None):
        rules = self.search(cr, uid, [('remote_call', '=', remote_call)], order='active desc, id', context=context)
        if rules:
            return self.browse(cr, uid, rules, context=context)[0]
        return False

    def _manual_create_sync_message(self, cr, real_uid, model_name, res_id, return_info, rule_method, logger, check_identifier=True, context=None, extra_arg=None, force_domain=False):
        if context is None:
            context ={}
        if True:
            uid = 1
            at = context.get('active_test')
            context['active_test'] = False
            partner_name = 'fake'

            rule = self.get_rule_by_remote_call(cr, uid, rule_method, context)
            if not rule:
                return

            model_obj = self.pool.get(model_name)

            if model_name == 'sale.order.line' and real_uid == self.pool.get('res.users')._get_sync_user_id(cr):
                if model_obj.search_exists(cr, uid, [('id', '=', res_id), ('dpo_line_id', '!=', False)], context=context):
                    # COO: FO lines sourced to DPO are updated by IN sync message from project: do not trigger message from COO
                    cr.execute("update ir_model_data set sync_date=last_modification where model='sale.order.line' and res_id = %s" , (res_id,))
                    return

            new_dom = eval(rule.domain)
            new_dom = ['&', ('id', '=', res_id)] + new_dom
            if not force_domain and not model_obj.search(cr, uid, new_dom, order='NO_ORDER', context=context):
                #if not force_domain and res_id not in model_obj.search(cr, uid, eval(rule.domain), order='NO_ORDER', context=context):
                return

            msg_to_send_obj = self.pool.get("sync.client.message_to_send")
            partner = model_obj.browse(cr, uid, res_id, fields_to_fetch=[rule.destination_name])[rule.destination_name]
            partner_name = partner.name
            arguments = model_obj.get_message_arguments(cr, uid, res_id, rule, destination=partner, context=context)
            if extra_arg:
                arguments[0].update(extra_arg)
            sale_name = ''
            if 'name' in arguments[0]:
                sale_name = arguments[0]['name']

            identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, rule.model, [res_id], rule.server_id, context=context)
            if not identifiers:
                return
            # Still create the message if an existing message was already in the system, as the return action could be repeat
            xml_id = identifiers[res_id]
            if check_identifier and msg_to_send_obj.search(cr, uid, [('identifier', '=', xml_id)], limit=1, order='NO_ORDER', context=context):
                return
            data = {
                'identifier' : xml_id,
                'remote_call': rule.remote_call,
                'arguments': arguments,
                'destination_name': partner_name,
                'sent' : False,
                'res_object': '%s,%s' % (model_name, res_id),
                'generate_message' : True,
            }
            msg_to_send_obj.create(cr, uid, data, context=context)
            if logger:
                logger.info("A manual message for the method: %s, created for the object: %s " % (rule_method, sale_name))
            if at is None:
                del context['active_test']
            else:
                context['active_test'] = at

    #UF-2531: This method is to create manually a RW message for the return pack, of ship or ppl and put into the queue for the next USB sync
    def _manual_create_rw_message(self, cr, uid, model_name, res_id, return_info, rule_method, logger, context=None):
        pick_obj = self.pool.get('stock.picking')
        usb_entity = pick_obj._get_usb_entity_type(cr, uid)
        if usb_entity == pick_obj.REMOTE_WAREHOUSE or not rule_method or not res_id:
            partner_name = 'fake'

            full_method = model_name + "." + rule_method
            rule = self.get_rule_by_remote_call(cr, uid, full_method, context)
            if not rule:
                logger.info("Sorry, there is no RW message rule found for the method %s." % (full_method))
                return

            model_obj = self.pool.get(model_name)
            msg_to_send_obj = self.pool.get("sync_remote_warehouse.message_to_send")

            arguments = model_obj.get_message_arguments(cr, uid, res_id, rule, destination=False, context=context)
            temp = arguments[0]
            temp['picking'] = return_info
            arguments = [temp]

            pick_name = ''
            if 'name' in arguments[0]:
                pick_name = arguments[0]['name']

            identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, rule.model, [res_id], rule.server_id, context=context)
            if not identifiers:
                return
            # Still create the message if an existing message was already in the system, as the return action could be repeat
            xml_id = identifiers[res_id]
            data = {
                'identifier' : xml_id,
                'remote_call': rule.remote_call,
                'arguments': arguments,
                'destination_name': partner_name,
                'sent' : False,
                'generate_message' : True,
            }
            msg_to_send_obj.create(cr, uid, data, context=context)
            logger.info("A manual RW message for the method: %s, created for the object: %s " % (full_method, pick_name))

    _order = 'sequence_number asc'
local_message_rule()


class message_to_send(osv.osv):
    _name = "sync.client.message_to_send"
    _rec_name = 'identifier'

    _columns = {
        'identifier' : fields.char('Identifier', size=128, readonly=True),
        'sent' : fields.boolean('Sent ?', readonly=True),
        'generate_message' : fields.boolean("Generate By system", readonly=True),
        'remote_call':fields.text('Method to call', required = True,readonly=True),
        'arguments':fields.text('Arguments of the method', required = True, readonly=True),
        'destination_name':fields.char('Destination Name', size=256, required = True, readonly=True),
        'sent_date' : fields.datetime('Sent Date', readonly=True),
        'res_object': fields.char('Res object', size=256, readonly=True),
        'waiting': fields.boolean('Waiting ?', readonly=True, help='Is the message waiting to be send'),
    }

    _defaults = {
        'generate_message' : True,
    }

    _logger = logging.getLogger('sync.client.message_to_send')

    """
        Creation from rule
    """

    def create_from_rule(self, cr, uid, rule, order=None, initial=False, context=None):
        context = dict(context or {})
        context['active_test'] = False

        # either use rule filter_method or domain to find records for message
        if rule.filter_method:
            obj_ids_temp_order = getattr(self.pool.get(rule.model), rule.filter_method)(cr, uid, rule, context=context)
        else:
            domain = rule.domain and eval(rule.domain) or []
            obj_ids_temp_order = self.pool.get(rule.model).search_ext(cr, uid, domain, order=order, context=context)

        obj_ids_temp = self.pool.get(rule.model).need_to_push(cr, uid, obj_ids_temp_order)

        '''
            Add only real new messages to sync those haven't been synced before! This reduces significantly the cost of calculating the args (which is heavy)
            The solution is to get the identifiers, then check to remove those exist but not sent, no need to calculate args for them 
        '''
        obj_ids = []
        identifiers = self._generate_message_uuid(cr, uid, rule.model, obj_ids_temp, rule.server_id, context=context)

        allow_duplicates = rule.remote_call == 'purchase.order.line.update_dates_from_pol'

        if not allow_duplicates:
            # UF-2483: Verify if this identifier has already be created, only add for latter calculation if it is completely NEW
            obj_ids = [obj_id for obj_id in obj_ids_temp_order if obj_id in obj_ids_temp and not \
                       self.search(cr, uid, [('identifier', '=',
                                              identifiers[obj_id])], context=context)]
        else:
            obj_ids = obj_ids_temp

        ignored_ids = list(set(obj_ids_temp) - set(obj_ids))
        dest = self.pool.get(rule.model).get_destination_name(cr, uid, obj_ids, rule.destination_name, context=context)
        args = {}
        generated_ids = []

        if obj_ids and rule.model == 'stock.picking' and rule.remote_call in ('stock.picking.partial_shipped_fo_updates_in_po', 'stock.picking.partial_shippped_dpo_updates_in_po'):
            cr.execute("select array_agg(id) from stock_picking where id in %s group by subtype, partner_id, origin, claim, coalesce(shipment_id, id)", (tuple(obj_ids),))
            for picks in cr.fetchall():
                arg = self.pool.get('stock.picking').get_message_arguments(cr, uid, picks[0], rule, context=context)
                first_id = picks[0][0]
                self.create_message(cr, uid, identifiers[first_id], rule.remote_call, arg, dest[first_id], initial, context)
                generated_ids += picks[0]
        else:
            for obj_id in obj_ids:
                if initial == False: # default action
                    args[obj_id] = self.pool.get(rule.model).get_message_arguments(cr, uid, obj_id, rule, context=context)
                else: # UF-2483: fake RW sync on creation of the RW instance
                    args[obj_id] = "Initial RW Sync - Ignore"


            for id in obj_ids:
                for destination in (dest[id] if isinstance(dest[id], list) else [dest[id]]):
                    # UF-2531: allow this when creating usb msg for the INT from scratch from RW to CP
                    if destination is False:
                        destination = 'fake'
                    # UF-2483: By default the "sent" parameter is False
                    self.create_message(cr, uid, identifiers[id], rule.remote_call, args[id], destination, initial, context, allow_duplicates=allow_duplicates)
                generated_ids.append(id)

        if generated_ids and rule.remote_call == 'purchase.order.line.update_dates_from_pol':
            cr.execute("update purchase_order_line set dates_modified='f' where id in %s", (tuple(generated_ids), ))

        return generated_ids, ignored_ids

    def _generate_message_uuid(self, cr, uid, model, ids, server_rule_id, context=None):
        return dict( (id, "%s_%s" % (name, server_rule_id)) \
                     for id, name in list(self.pool.get(model).get_sd_ref(cr, uid, ids, context=context).items()) )

    def create_message(self, cr, uid, identifier, remote_call, arguments, destination_name, sent=False, context=None, allow_duplicates=False):
        data = {
            'identifier' : identifier,
            'remote_call': remote_call,
            'arguments': arguments,
            'destination_name': destination_name,
            'sent' : sent,
            'generate_message' : False,
        }
        if allow_duplicates:
            ids = []
        else:
            ids = self.search(cr, uid, [('identifier', '=', identifier)], context=context)
        if not ids:
            ids = [self.create(cr, uid, data, context=context)]
        return ids[0]

    """
        Sending Part
    """
    def get_message_packet(self, cr, uid, max_size, context=None):
        packet = []
        msg_ids = []
        for message in self.browse(cr, uid,
                                   self.search(cr, uid, [('sent', '=', False)],
                                               limit=max_size, order='id asc', context=context),
                                   context=context):
            if message.res_object:
                res_model, res_id = message.res_object.split(',')
                res_id = int(res_id)
                rule = self.pool.get('sync.client.message_rule').get_rule_by_remote_call(cr, uid, message.remote_call, context=context)
                if rule and rule.wait_while:
                    domain = eval(rule.wait_while)
                    if res_id in self.pool.get(res_model).search(cr, uid, domain, context=context):
                        self.write(cr, uid, [message.id], {'waiting': True}, context=context)
                        continue

            if message.waiting:
                self.write(cr, uid, [message.id], {'waiting': False}, context=context)
            packet.append({
                'id' : message.identifier,
                'call' : message.remote_call,
                'dest' : message.destination_name,
                'args' : message.arguments,
                'client_db_id': message.id,
            })
            msg_ids.append(message.id)

        return msg_ids, packet


    def packet_sent(self, cr, uid, ids, context=None):
        if ids:
            self.write(cr, uid, ids, {'sent' : True, 'sent_date' : fields.datetime.now()}, context=context)
        return True

    _order = 'create_date desc, id desc'

message_to_send()


class message_received(osv.osv):
    _name = "sync.client.message_received"
    _rec_name = 'identifier'
    _order = 'create_date desc, id desc'

    _columns = {
        'identifier' : fields.char('Identifier', size=128, readonly=True),
        'sequence': fields.integer('Sequence', readonly = True),
        'remote_call':fields.text('Method to call', required = True),
        'arguments':fields.text('Arguments of the method', required = True),
        'source':fields.char('Source Name', size=256, required = True, readonly=True),
        'run' : fields.boolean("Run", readonly=True),
        'partial_run': fields.boolean("Partial Run", readonly=True, select=1),
        'manually_set_total_run_date': fields.datetime('Manually to total-run Date', readonly=True),
        'log' : fields.text("Execution Messages",readonly=True),
        'execution_date' :fields.datetime('Execution Date', readonly=True),
        'create_date' :fields.datetime('Receive Date', readonly=True),
        'editable' : fields.boolean("Set editable"),
        'rule_sequence': fields.integer('Sequence of the linked rule', required=True),
        'manually_ran': fields.boolean('Has been manually tried', readonly=True),
        'manually_set_run_date': fields.datetime('Run without execution Date', readonly=True, select=1),
        'sync_id': fields.integer('Sync server seq. id', required=True, select=1),
        'target_object': fields.char('Target Object', size=254, readonly=1, select=1),
        'target_id': fields.integer('Target Id', size=254, readonly=1, select=1),
        'line_number': fields.integer('line number in case of NR', readonly=1),
    }

    _sql_constraints = [
        ('sync_id_uniq', 'unique(sync_id)', 'Duplicates sync_id'),
    ]
    _logger = logging.getLogger('sync.client')

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        vals['rule_sequence'] = False
        parent_rule = self.pool.get('sync.client.message_rule').search(cr, uid, [('remote_call', '=', vals['remote_call'])], context=context)
        if parent_rule:
            vals['rule_sequence'] = self.pool.get('sync.client.message_rule').read(cr, uid, parent_rule, ['sequence_number'], context=context)[0]['sequence_number']

        return super(message_received, self).create(cr, uid, vals, context=context)

    def unfold_package(self, cr, uid, package, context=None):
        last_seq = False

        for data in package:
            # prevent duplicates if previous message_received_by_sync_id has failed
            if not self.search_exist(cr, uid, [('sync_id', '=', data['sync_id'])], context=context):
                self.create(cr, uid, {
                    'identifier' : data['id'],
                    'remote_call' : data['call'],
                    'arguments' : data['args'],
                    'sequence' : data['sequence'],
                    'source' : data['source'],
                    'sync_id': data['sync_id']}, context=context)
            last_seq = data['sequence']

        if last_seq:
            entity_obj = self.pool.get('sync.client.entity')
            entity = entity_obj.get_entity(cr, uid, context=context)
            entity_obj.write(cr, uid, entity.id, {'message_last' :data['sequence']}, context=context)

    def get_model_and_method(self, remote_call):
        remote_call = remote_call.strip()
        call_list = remote_call.split('.')
        return '.'.join(call_list[:-1]), call_list[-1]

    def get_arg(self, args):
        res = []
        for arg in eval(args):
            if isinstance(arg, dict):
                res.append(dict_to_obj(arg))
            else:
                res.append(arg)
        return res

    def manual_execute(self, cr, uid, ids, context=None):
        try:
            self.execute(cr, uid, ids, context=context)
        except:
            raise
        finally:
            self.write(cr, uid, ids, {'manually_ran': True}, context=context)
        return True

    def manual_set_as_run(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'run': True, 'log': 'Set manually to run without execution', 'manually_set_run_date': fields.datetime.now(), 'editable': False}, context=context)
        return True

    def manual_set_total_run(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'partial_run': False, 'manually_set_total_run_date': fields.datetime.now()}, context=context)
        return True

    def execute(self, cr, uid, ids=None, context=None):
        # scope the context of message executions and loggers
        context = dict((context or {}),
                       sync_message_execution=True,
                       sale_purchase_logger={})
        context['lang'] = 'en_US'

        if ids is None:
            ids = self.search(cr, uid, [('run','=',False)], order='rule_sequence, id', context=context)

        if not ids: return 0

        execution_date = fields.datetime.now()
        error = None
        for message in self.browse(cr, uid, ids, context=context):
            #UTP-682: double check to make sure if the message has been executed, then skip it
            if message.run:
                continue
            cr.commit()
            try:
                model, method = self.get_model_and_method(message.remote_call)
                arg = self.get_arg(message.arguments)
                try:
                    fn = getattr(self.pool.get(model), method)
                    new_ctx = context.copy()
                    new_ctx.update({'identifier': message.identifier})
                    res = fn(cr, uid, message.source, *arg, context=new_ctx)
                except RunWithoutException as e:
                    self.write(cr, uid, message.id, {
                        'execution_date' : execution_date,
                        'run' : True,
                        'log' : "%s\nSet as run without exec by system" % e.message,
                        'manually_set_run_date': fields.datetime.now(),
                        'editable': False
                    }, context=context)
                except BaseException as e:
                    error = e # Keep this message for the exception below
                    self._logger.exception("Message execution %d failed!" % message.id)
                    cr.rollback()
                    if isinstance(e, osv.except_osv):
                        error_msg = e.value
                    else:
                        error_msg = e
                    msg_data = {
                        'execution_date' : execution_date,
                        'run' : False,
                        'log' : e.__class__.__name__+": "+tools.ustr(error_msg)+"\n\n--\n"+tools.ustr(traceback.format_exc()),
                    }
                    if isinstance(e, SyncException):
                        msg_data['target_object'] = e.target_object
                        msg_data['target_id'] = e.target_id
                        msg_data['line_number'] = e.line_number


                    self.write(cr, uid, message.id, msg_data, context=context)
                else:
                    self.write(cr, uid, message.id, {
                        'execution_date' : execution_date,
                        'run' : True,
                        'log' : tools.ustr(res),
                        'partial_run': new_ctx.get('partial_sync_run', False),
                    }, context=context)
            except BaseException as e1:
                ### This should never be reachable, but nobody knows!
                self._logger.exception("Message execution %d failed!" % message.id)

                cr.execute("ROLLBACK")
                if error == None:
                    # if the error did not set in the previous round, then use the current exception
                    error = e1

                if isinstance(error, osv.except_osv):
                    error_msg = error.value
                else:
                    error_msg = error
                self.write(cr, uid, message.id, {
                    'execution_date' : execution_date,
                    'run' : False,
                    'log' : error.__class__.__name__+": "+tools.ustr(error_msg)+"\n\n--\n"+tools.ustr(traceback.format_exc()),
                }, context=context)

        return len(ids)


message_received()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

