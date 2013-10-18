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

import logging
from sync_common import sync_log

from tools.safe_eval import safe_eval as eval

class dict_to_obj(object):
    def __init__(self, values):
        assert isinstance(values, dict), "Must be a dictionary"
        self.values = values
        for k, v in values.items():
            if isinstance(v, dict):
                v = dict_to_obj(v)
            elif hasattr(v, '__iter__'):
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
        'model' : fields.many2one('ir.model','Model', readonly=True),
        'domain' : fields.text('Domain', required=False, readonly=True),
        'sequence_number' : fields.integer('Sequence', readonly=True),
        'remote_call': fields.text('Method to call', required=True),
        'arguments': fields.text('Arguments of the method', required=True),
        'destination_name': fields.char('Fields to extract destination', size=256, required=True),
    }

    _logger = logging.getLogger('sync.client')

    def save(self, cr, uid, data_list, context=None):
        self._delete_old_rules(cr, uid, context)
        for data in data_list:
            model_name = data.get('model')
            model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name)], context=context)
            if not model_id:
                sync_log(self, "Model %s does not exist" % model_name, data=data)
                continue #we do not save this rule
            data['model'] = model_id[0]

            self.create(cr, uid, data, context=context)

    def _delete_old_rules(self, cr, uid, context=None):
        ids_to_unlink = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, ids_to_unlink, context=context)

    def get_rule_by_sequence(self, cr, uid, sequence_number, context=None):
        rules = self.search(cr, uid, [('sequence_number', '=', sequence_number)], context=context)
        if rules:
            return self.browse(cr, uid, rules, context=context)[0]
        return False

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
    }
    
    _defaults = {
        'generate_message' : True,
    }


    """
        Creation from rule
    """
    def create_from_rule(self, cr, uid, rule, context=None):
        domain = rule.domain and eval(rule.domain) or []
        context = dict(context or {})
        context['active_test'] = False
        obj_ids = self.pool.get(rule.model.model).search_ext(cr, uid, domain, context=context)
        dest = self.pool.get(rule.model.model).get_destination_name(cr, uid, obj_ids, rule.destination_name, context=context)
        args = {}
        for obj_id in obj_ids:
            arg = self.pool.get(rule.model.model).get_message_arguments(cr, uid, obj_id, rule, context=context)
            args[obj_id] = arg
        call = rule.remote_call
        identifiers = self._generate_message_uuid(cr, uid, rule.model.model, obj_ids, rule.server_id, context=context)
        for id in obj_ids:
            for destination in (dest[id] if hasattr(dest[id], '__iter__') else [dest[id]]):
                self.create_message(cr, uid, identifiers[id], call, args[id], dest[id], context)
        return len(obj_ids)

    def _generate_message_uuid(self, cr, uid, model, ids, server_rule_id, context=None):
        return dict( (id, "%s_%s" % (name, server_rule_id)) \
                     for id, name in self.pool.get(model).get_sd_ref(cr, uid, ids, context=context).items() )

    def create_message(self, cr, uid, identifier, remote_call, arguments, destination_name, context=None):
        data = {
                'identifier' : identifier,
                'remote_call': remote_call,
                'arguments': arguments,
                'destination_name': destination_name,
                'sent' : False,
                'generate_message' : False,
        }
        ids = self.search(cr, uid, [('identifier', '=', identifier)], context=context)
        if not ids:
            ids = [self.create(cr, uid, data, context=context)]
        return ids[0]
        #else:
            #sync_log(self, "Message %s already exist" % identifier)

    # SP-135: Manually generate a message if there is a modification on the relevant object
    def modify_manual_message(self, cr, uid, existing_message_id, identifier, remote_call, arguments, destination_name, context=None):
        data = {
                'identifier' : identifier,
                'remote_call': remote_call,
                'arguments': arguments,
                'generate_message': True,   # set this message as generated by the system, it will not cause the resume synch event
                'destination_name': destination_name,
                'sent' : False,
        }
        self.write(cr, uid, existing_message_id, data, context=context)

    """
        Sending Part
    """
    def get_message_packet(self, cr, uid, max_size, context=None):
        packet = []

        for message in self.browse(cr, uid,
                self.search(cr, uid, [('sent', '=', False)],
                    limit=max_size, order='id asc', context=context),
                context=context):
            packet.append({
                'id' : message.identifier,
                'call' : message.remote_call,
                'dest' : message.destination_name,
                'args' : message.arguments,
            })
            
        return packet


    def packet_sent(self, cr, uid, packet, context=None):
        message_uuids = [data['id'] for data in packet]
        ids = self.search(cr, uid, [('identifier', 'in', message_uuids)], context=context)
        if ids:
            self.write(cr, uid, ids, {'sent' : True, 'sent_date' : fields.datetime.now()}, context=context)

    _order = 'create_date desc, id desc'

message_to_send()


class message_received(osv.osv):
    _name = "sync.client.message_received"
    _rec_name = 'identifier'
    _columns = {
        'identifier' : fields.char('Identifier', size=128, readonly=True),
        'sequence': fields.integer('Sequence', readonly = True),
        'remote_call':fields.text('Method to call', required = True),
        'arguments':fields.text('Arguments of the method', required = True),
        'source':fields.char('Source Name', size=256, required = True, readonly=True),
        'run' : fields.boolean("Run", readonly=True),
        'log' : fields.text("Execution Messages",readonly=True),
        'execution_date' :fields.datetime('Execution Date', readonly=True),
        'create_date' :fields.datetime('Receive Date', readonly=True),
        'editable' : fields.boolean("Set editable"),
    }

    _logger = logging.getLogger('sync.client')

    def unfold_package(self, cr, uid, package, context=None):
        for data in package:
            ids = self.search(cr, uid, [('identifier', '=', data['id'])], context=context)
            if ids:
                sync_log(self, 'Message %s already in the database' % data['id'])
                # SP-135/UF-1617: Write the message if there is modification, and set the "run" to false to be executed next time
                self.write(cr, uid, ids, {
                    'identifier' : data['id'],
                    'remote_call' : data['call'],
                    'arguments' : data['args'],
                    'sequence' : data['sequence'],
                    'run' : False, # SP-135: set the message to become not run, so it will be rerun if there is a modif from server
                    'source' : data['source'] }, context=context)
                continue
            self.create(cr, uid, {
                'identifier' : data['id'],
                'remote_call' : data['call'],
                'arguments' : data['args'],
                'sequence' : data['sequence'],
                'source' : data['source'] }, context=context)
            
            entity_obj = self.pool.get( "sync.client.entity")
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

    def execute(self, cr, uid, ids=None, context=None):
        # scope the context of message executions and loggers
        context = dict((context or {}),
            sync_message_execution=True,
            sale_purchase_logger={})

        # get all ids if not specified
        if ids is None:
            ids = self.search(cr, uid, [('run', '=', False)],
                order='id asc', context=context)
        if not ids: return 0

        execution_date = fields.datetime.now()
        for message in self.browse(cr, uid, ids, context=context):
            if message.run: #UTP-682: double check to make sure if the message has been executed, then skip it
                continue

            cr.execute("SAVEPOINT exec_message")
            model, method = self.get_model_and_method(message.remote_call)
            arg = self.get_arg(message.arguments)
            try:
                fn = getattr(self.pool.get(model), method)
                res = fn(cr, uid, message.source, *arg, context=context)
            except BaseException, e:
                self._logger.exception("Message execution %d failed!" % message.id)
                cr.execute("ROLLBACK TO SAVEPOINT exec_message")
                self.write(cr, uid, message.id, {
                    'execution_date' : execution_date,
                    'run' : False,
                    'log' : e.__class__.__name__+": "+tools.ustr(e),
                }, context=context)
            else:
                cr.execute("RELEASE SAVEPOINT exec_message")
                self.write(cr, uid, message.id, {
                    'execution_date' : execution_date,
                    'run' : True,
                    'log' : tools.ustr(res),
                }, context=context)

        return len(ids)

    _order = 'create_date desc, id desc'

message_received()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

