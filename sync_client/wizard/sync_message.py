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
import sync_data
from sync_client.ir_model_data import link_with_ir_model, dict_to_obj
pp = pprint.PrettyPrinter(indent=4)
import logging

from tools.safe_eval import safe_eval as eval


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

    def save(self, cr, uid, data_list, context=None):
        self._delete_old_rules(cr, uid, context)
        for data in data_list:
            model_name = data.get('model')
            model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name)], context=context)
            if not model_id:
                sync_data.log(self, cr, uid, "Model %s does not exist" % model_name, data=data, context=context)
                continue #we do not save this rule
            data['model'] = model_id[0]

            self.create(cr, uid, data, context=context)

    def _delete_old_rules(self, cr, uid, context=None):
        ids_to_unlink = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, ids_to_unlink, context=context)

    _order = 'sequence_number asc'
local_message_rule()


class message_to_send(osv.osv):
    _name = "sync.client.message_to_send"
    _rec_name = 'identifier'

    _columns = {

        'identifier' : fields.char('Identifier', size=128, readonly=True),
        'sent' : fields.boolean('Sent ?', readonly=True),
        'remote_call':fields.text('Method to call', required = True,readonly=True),
        'arguments':fields.text('Arguments of the method', required = True, readonly=True),
        'destination_name':fields.char('Destination Name', size=256, required = True, readonly=True),
        'sent_date' : fields.datetime('Sent Date', readonly=True),
    }


    """
        Creation from rule
    """
    def create_from_rule(self, cr, uid, rule, context=None):
        obj = self.pool.get(rule.model.model)
        domain = rule.domain and eval(rule.domain) or []
        obj_ids = sync_data.eval_poc_domain(obj, cr, uid, domain, context=context)
        dest = self.pool.get(rule.model.model).get_destination_name(cr, uid, obj_ids, rule.destination_name, context=context)
        args = {}
        for obj_id in obj_ids:
            arg = self.pool.get(rule.model.model).get_message_arguments(cr, uid, obj_id, rule, context=context)
            args[obj_id] = arg
        call = rule.remote_call
        identifiers = self._generate_message_uuid(cr, uid, obj, obj_ids, rule.server_id, context=context)
        for id in obj_ids:
            self.create_message(cr, uid, identifiers[id], call, args[id], dest[id], context)

    def _generate_message_uuid(self, cr, uid, model, ids, server_rule_id, context=None):
        res = {}
        for id in ids:
            model_data_id = link_with_ir_model(model, cr, uid, id, context=context)
            name = self.pool.get('ir.model.data').browse(cr, uid, model_data_id, context=context).name
            res[id] = name + "_" + str(server_rule_id)
        return res


    def create_message(self, cr, uid, identifier, remote_call, arguments, destination_name, context=None):
        data = {
                'identifier' : identifier,
                'remote_call': remote_call,
                'arguments': arguments,
                'destination_name': destination_name,
                'sent' : False,
        }
        res = self.search(cr, uid, [('identifier', '=', identifier)], context=context)
        if not res:
            self.create(cr, uid, data, context=context)
        #else:
            #sync_data.log(self, cr, uid, "Message %s already exist" % identifier, context=context)



    """
        Sending Part
    """
    def get_message_packet(self, cr, uid, max_size, context=None):
        ids = self.search(cr, uid, [('sent', '=', False)], context=context)
        if not ids:
            return False

        packet = []
        for data in self.browse(cr, uid, ids, context=context):
            res = {
                'id' : data.identifier,
                'call' : data.remote_call,
                'dest' : data.destination_name,
                'args' : data.arguments,
            }
            packet.append(res)
        return packet


    def packet_sent(self, cr, uid, packet, context=None):
        message_uuids = [data['id'] for data in packet]
        ids = self.search(cr, uid, [('identifier', 'in', message_uuids)], context=context)
        if ids:
            self.write(cr, uid, ids, {'sent' : True, 'sent_date' : datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, context=context)

    _order = 'id asc'

message_to_send()


class message_received(osv.osv):
    _name = "sync.client.message_received"
    _rec_name = 'identifier'
    __logger = logging.getLogger('sync.client')
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

    def unfold_package(self, cr, uid, package, context=None):
        for data in package:
            ids = self.search(cr, uid, [('identifier', '=', data['id'])], context=context)
            if ids:
                sync_data.log(self, cr, uid, 'Message %s already in the database' % data['id'])
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
        for arg  in eval(args):
            if isinstance(arg, dict):
                res.append(dict_to_obj(arg))
            else:
                res.append(arg)
        return res

    def execute(self, cr, uid, ids=False, context=None):
        if not ids:
            ids = self.search(cr, uid, [('run', '=', False)], context=context)
        if not ids: return True
        execution_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.write(cr, uid, ids, {'execution_date' : execution_date}, context=context)
        for message in self.browse(cr, uid, ids, context=context):
            cr.execute("SAVEPOINT exec_message")
            model, method = self.get_model_and_method(message.remote_call)
            arg = self.get_arg(message.arguments)
            try:
                fn = getattr(self.pool.get(model), method)
                res = fn(cr, uid, message.source, *arg)
                self.write(cr, uid, message.id, {'run' : True, 'log' : tools.ustr(res)}, context=context)
                cr.execute("RELEASE SAVEPOINT exec_message")
            except Exception, e:
                cr.execute("ROLLBACK TO SAVEPOINT exec_message")
                log = "Something go wrong with the call %s \n" % message.remote_call
                log += tools.ustr(e)
                self.__logger.error(log)
                self.write(cr, uid, message.id, {'run' : False, 'log' : log}, context=context)
        return True

    _order = 'id asc'

message_received()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

