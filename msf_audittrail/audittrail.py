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

from osv import fields, osv, orm
from osv.osv import osv_pool, object_proxy
from osv.orm import orm_template
from tools.translate import _
from lxml import etree
from datetime import datetime
import ir
import pooler
import time
import tools
import logging
from tools.safe_eval import safe_eval as eval


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    _trace = True

purchase_order()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'
    _trace = True

purchase_order_line()


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    _trace = True

sale_order()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    _trace = True

product_product()


class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'
    _trace = True

product_template()


class product_supplier(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    _trace = True

product_supplier()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'
    _trace = True

sale_order_line()


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
    _trace = True

stock_picking()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'
    _trace = True

    # [utp-360]: I rename the 'date' to 'Actual Receipt Date' because before it was 'Date'
    _columns = {
        'date': fields.datetime('Actual Receipt Date', required=True, select=True, help="Move date: scheduled date until move is done, then date of actual move processing", readonly=True),
    }

stock_move()


class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'
    _trace = True

account_invoice()


class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'
    _trace = True

account_invoice_line()


class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'
    _trace = True

account_bank_statement()


class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = 'account.bank.statement.line'
    _trace = True

    def _get_partner_type2(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get "Third Parties" audittrail version
        (audittrail does not process field function reference for now)
        """
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for st_line in self.browse(cr, uid, ids, context=context):
            if st_line.employee_id:
                res[st_line.id] = st_line.employee_id.name
            elif st_line.transfer_journal_id:
                res[st_line.id] = st_line.transfer_journal_id.name
            elif st_line.partner_id:
                res[st_line.id] = st_line.partner_id.name
            else:
                res[st_line.id] = False
        return res

    _columns = {
        'partner_type2': fields.function(_get_partner_type2, method=True, string="Third Parties"),
    }

    _defaults = {
        'name': lambda *a: '',
    }

account_bank_statement_line()

class account_cashbox_line(osv.osv):
    _name = 'account.cashbox.line'
    _inherit = 'account.cashbox.line'
    _trace = True

account_cashbox_line()

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'
    _trace = True

account_analytic_account()


class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'
    _trace = True

account_period()


class ir_module(osv.osv):
    _inherit = 'ir.module.module'

    def update_translations(self, cr, uid, ids, filter_lang=None, context=None):
        '''
        Override the lang install to apply the translation on Track changes ir.actions
        '''
        res = super(ir_module, self).update_translations(cr, uid, ids, filter_lang=None, context=context)

        msf_profile_id = self.search(cr, uid, [('name', '=', 'msf_profile')], context=context)

        if not msf_profile_id or msf_profile_id[0] not in ids:
            return res

        tr_obj = self.pool.get('ir.translation')
        act_obj = self.pool.get('ir.actions.act_window')
        src = 'Track changes'
        if not filter_lang:
            pool = pooler.get_pool(cr.dbname)
            lang_obj = pool.get('res.lang')
            lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True)])
            filter_lang = [lang.code for lang in lang_obj.browse(cr, uid, lang_ids)]
        elif not isinstance(filter_lang, (list, tuple)):
            filter_lang = [filter_lang]

        for lang in filter_lang:
            trans_ids = tr_obj.search(cr, uid, [('lang', '=', lang),
                                                ('xml_id', '=', 'action_audittrail_view_log'),
                                                ('module', '=', 'msf_audittrail')], context=context)
            if trans_ids:
                logger = logging.getLogger('i18n')
                logger.info('module msf_profile: loading translation for \'Track changes\' ir.actions.act_window for language %s', lang)
                trans = tr_obj.browse(cr, uid, trans_ids[0], context=context).value
                # Search all actions to rename
                act_ids = act_obj.search(cr, uid, [('name', '=', src)], context=context)
                for act in act_ids:
                    exist = tr_obj.search(cr, uid, [('lang', '=', lang),
                                                    ('type', '=', 'model'),
                                                    ('src', '=', src),
                                                    ('name', '=', 'ir.actions.act_window,name'),
                                                    ('value', '=', trans),
                                                    ('res_id', '=', act)], context=context)
                    if not exist:
                        tr_obj.create(cr, uid, {'lang': lang,
                                                'src': src,
                                                'name': 'ir.actions.act_window,name',
                                                'type': 'model',
                                                'value': trans,
                                                'res_id': act}, context=context)

        return res

ir_module()


class audittrail_log_sequence(osv.osv):
    _name = 'audittrail.log.sequence'
    _rec_name = 'model'
    _columns = {
        'model': fields.char(size=64, string='Model'),
        'res_id': fields.integer(string='Res Id'),
        'sequence': fields.many2one('ir.sequence', 'Logs Sequence', required=True, ondelete='cascade'),
    }

audittrail_log_sequence()


class audittrail_rule(osv.osv):
    """
    For Auddittrail Rule
    """
    _name = 'audittrail.rule'
    _description = "Audittrail Rule"
    _columns = {
        "name": fields.char("Rule Name", size=32, required=True),
        "object_id": fields.many2one('ir.model', 'Object', required=True, help="Select object for which you want to generate log."),
        "log_read": fields.boolean("Log Reads", help="Select this if you want to keep track of read/open on any record of the object of this rule"),
        "log_write": fields.boolean("Log Writes", help="Select this if you want to keep track of modification on any record of the object of this rule"),
        "log_unlink": fields.boolean("Log Deletes", help="Select this if you want to keep track of deletion on any record of the object of this rule"),
        "log_create": fields.boolean("Log Creates", help="Select this if you want to keep track of creation on any record of the object of this rule"),
        "log_action": fields.boolean("Log Action", help="Select this if you want to keep track of actions on the object of this rule"),
        "log_workflow": fields.boolean("Log Workflow", help="Select this if you want to keep track of workflow on any record of the object of this rule"),
        "domain_filter": fields.char(size=128, string="Domain", help="Python expression !"),
        "state": fields.selection((("draft", "Draft"),
                                   ("subscribed", "Subscribed")),
                                   "State", required=True),
        "action_id": fields.many2one('ir.actions.act_window', "Action ID"),
        "field_ids": fields.many2many('ir.model.fields', 'audit_rule_field_rel', 'rule_id', 'field_id', string='Fields'),
        "parent_field_id": fields.many2one('ir.model.fields', string='Parent fields'),
        "name_get_field_id": fields.many2one('ir.model.fields', string='Displayed field value'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'log_create': lambda *a: 1,
        'log_unlink': lambda *a: 1,
        'log_write': lambda *a: 1,
        'domain_filter': [],
    }

    def _check_domain_filter(self, cr, uid, ids, context=None):
        """
        Check that if you select cross docking, you do not have an other location than cross docking
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        for rule in self.browse(cr, uid, ids, context=context):
            domain = eval(rule.domain_filter)
            for d in tuple(domain):
                if len(d[0].split('.')) > 2:
                    return False

        return True


    _sql_constraints = [
        ('rule_name_uniq', 'unique(name)', """The AuditTrail rule name must be unique!""")
    ]

    _constraints = [
        (_check_domain_filter, 'The domain shouldn\'t contain a right element in condition with more than 2 elements.', ['domain_filter']),
    ]

    __functions = {}


    def write(self, cr, uid, ids, value, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for rule in self.browse(cr, uid, ids):
            self.get_functionnal_fields.clear_cache(cr.dbname, objname=rule.object_id.model, ids=[rule.id])
            for method in ['read', 'create', 'write', 'unlink']:
                field_name = 'log_' + method
                if getattr(rule, field_name):
                    self.to_trace.clear_cache(cr.dbname, model=rule.object_id.model, method=method)
        return super(audittrail_rule, self).write(cr, uid, ids, value, context=context)


    def subscribe(self, cr, uid, ids, *args):
        """
        Subscribe Rule for auditing changes on object and apply shortcut for logs on that object.
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Auddittrail Rule’s IDs.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        obj_action = self.pool.get('ir.actions.act_window')
        obj_model = self.pool.get('ir.model.data')

        for thisrule in self.browse(cr, uid, ids):
            obj = self.pool.get(thisrule.object_id.model)
            if not obj:
                raise osv.except_osv(
                        _('WARNING: audittrail is not part of the pool'),
                        _('Change audittrail depends -- Setting rule as DRAFT'))

            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_audittrail', 'view_audittrail_log_line_search')
            val = {
                 "name": _('Track changes'),
                 "res_model": 'audittrail.log.line',
                 "src_model": thisrule.object_id.model,
                 "search_view_id": search_view_id and search_view_id[1] or False,
                 "domain": "[('object_id','=', " + str(thisrule.object_id.id) + "), ('res_id', '=', active_id)]"
            }
            if thisrule.object_id.model == 'account.bank.statement.line':
                # for register line we allow to select many lines in track changes view
                val['domain'] = "[('object_id','=', " + str(thisrule.object_id.id) + "), ('res_id', 'in', active_ids)]"

            action_id = obj_action.create(cr, uid, val)
            self.write(cr, uid, [thisrule.id], {"state": "subscribed", "action_id": action_id})
            keyword = 'client_action_relate'
            value = 'ir.actions.act_window,' + str(action_id)
            obj_model.ir_set(cr, uid, 'action', keyword, 'View_log_' + thisrule.object_id.model, [thisrule.object_id.model], value, replace=True, isobject=True, xml_id=False)
            # End Loop

        # Check if an export model already exist for audittrail.rule
        export_ids = self.pool.get('ir.exports').search(cr, uid, [('name', '=', 'Log Lines'), ('resource', '=', 'audittrail.log.line')])
        if not export_ids:
            export_id = self.pool.get('ir.exports').create(cr, uid, {'name': 'Log Lines',
                                                                     'resource': 'audittrail.log.line'})
            fields = ['log', 'timestamp', 'sub_obj_name', 'method', 'field_description', 'old_value', 'new_value', 'user_id']
            for f in fields:
                self.pool.get('ir.exports.line').create(cr, uid, {'name': f, 'export_id': export_id})

        return True

    def unsubscribe(self, cr, uid, ids, *args):
        """
        Unsubscribe Auditing Rule on object
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Auddittrail Rule’s IDs.
        @return: True
        """
        obj_action = self.pool.get('ir.actions.act_window')
        val_obj = self.pool.get('ir.values')
        value = ''
        # start Loop
        for thisrule in self.browse(cr, uid, ids):
            if thisrule.id in self.__functions:
                for function in self.__functions[thisrule.id]:
                    setattr(function[0], function[1], function[2])
            w_id = obj_action.search(cr, uid, [('name', '=', 'View Log'), ('res_model', '=', 'audittrail.log.line'), ('src_model', '=', thisrule.object_id.model)])
            if w_id:
                obj_action.unlink(cr, uid, w_id)
                value = "ir.actions.act_window" + ',' + str(w_id[0])
            val_id = val_obj.search(cr, uid, [('model', '=', thisrule.object_id.model), ('value', '=', value)])
            if val_id:
                ir.ir_del(cr, uid, val_id[0])
            self.write(cr, uid, [thisrule.id], {"state": "draft"})
        # End Loop

        return True

    @tools.cache(skiparg=3)
    def get_functionnal_fields(self, cr, uid, objname, ids):
        # no context to not disturb caching
        fields_obj = self.pool.get('ir.model.fields')
        fields_ids = fields_obj.search(cr, uid, [('audittrail_rule_ids', 'in', ids)])
        if fields_ids:
            ret = []
            obj = self.pool.get(objname)
            for field in fields_obj.read(cr, uid, fields_ids, ['name']):
                col = obj._all_columns[field['name']].column
                if col._properties and not col._classic_write:
                    ret.append(field['name'])
            return ret
        return []

    @tools.cache(skiparg=3)
    def to_trace(self, cr, uid, model, method):
        obj = self.pool.get(model)
        if not obj or not obj._trace:
            return False

        log_field = 'log_' + method
        return self.search(cr, 1, [('object_id.model', '=', model), (log_field, '=', True), ('state', '=', 'subscribed')])


    def audit_log(self, cr, uid, ids, obj, objids, method, previous_value=None, current=None, context=None):
        uid_orig = hasattr(uid, 'realUid') and uid.realUid or uid
        uid = 1
        log_line_obj = self.pool.get('audittrail.log.line')

        if isinstance(objids, (int, long)):
            obj_ids = [objids]
            previous = [previous_value]
        else:
            obj_ids = objids[:]
            previous = previous_value

        for rule in self.browse(cr, uid, ids, context=context):
            if not obj_ids:
                # if a previous rule has been applied, stop the log
                # i.e: if multiple rules a set for a an object, only the 1st is applied
                return True
            domain = []
            if rule.domain_filter:
                domain = eval(rule.domain_filter)
            if domain:
                new_dom = ['&', ('id', 'in', obj_ids)] + domain
                res_ids = obj.search(cr, uid, new_dom)
                if not res_ids:
                    continue

                # test next rule on res_ids exluded by the rule domain
                obj_ids = [x for x in obj_ids if x not in res_ids]
            else:
                res_ids = obj_ids[:]
                obj_ids = []

            model_name_tolog = rule.object_id.model
            parent_field = False
            if rule.parent_field_id:
                parent_field_display = rule.name_get_field_id.name
                parent_field = rule.parent_field_id.name
                model_name_tolog = rule.parent_field_id.relation
                model_parent_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name_tolog)])[0]

            if method in ('write', 'create'):
                original_fields = current.values()[0].keys()
                fields_to_trace = {}

                for field in rule.field_ids:
                    if field.name in original_fields or field.is_function:
                        fields_to_trace[field.name] = field

                if method != 'create' and not fields_to_trace:
                    # no changes written in field to trace
                    continue

            new_values_computed = {}
            if parent_field:
                new_values_computed = dict((x['id'], x) for x in obj.read(cr, uid, res_ids, [parent_field, parent_field_display], context=context))


            for res_id in res_ids:
                parent_field_id = False
                if parent_field:
                    parent_field_id = new_values_computed[res_id][parent_field][0]

                vals = {
                    'name': rule.object_id.name,
                    'method': method,
                    'object_id': rule.object_id.id,
                    'user_id': uid_orig,
                    'res_id': parent_field_id or res_id,
                }

                # Add the name of the created sub-object
                if parent_field_id:
                    # get the parent model_id
                    vals.update({
                        'sub_obj_name': new_values_computed[res_id][parent_field_display],
                        'rule_id': rule.id,
                        'fct_object_id': rule.object_id.id,
                        'object_id': model_parent_id,
                        'fct_res_id': res_id
                    })
                if method == 'unlink':
                    vals.update({
                        'field_description': get_field_description(rule.object_id),
                        'log': self.get_sequence(cr, uid, model_name_tolog, vals['res_id'], context=context),
                    })
                    log_line_obj.create(cr, uid, vals)

                elif method in ('write', 'create'):
                    if method == 'create':
                        vals.update({
                            'log': self.get_sequence(cr, uid, model_name_tolog, vals['res_id'], context=context),
                            'field_description': get_field_description(rule.object_id),
                        })
                        log_line_obj.create(cr, uid, vals)
                    if method == 'write':
                        previous_values = dict((x['id'], x) for x in previous)
                        record = previous_values[res_id]
                    else:
                        record = {}

                    for field in fields_to_trace.keys():
                        old_value = record.get(field, False)
                        new_value = current[res_id].get(field, False)
                        if old_value != new_value:
                            if fields_to_trace[field].ttype == 'datetime' and old_value and new_value and old_value[:10] == new_value[:10]:
                                continue
                            line = vals.copy()
                            description = fields_to_trace[field].field_description
                            # UTP-360
                            if description == 'Pricelist':
                                description = 'Currency'
                            line.update({
                              'field_id': fields_to_trace[field].id,
                              'field_description': description,
                              'log': self.get_sequence(cr, uid, model_name_tolog, vals['res_id'], context=context),
                              'name': field,
                              'new_value': new_value,
                              'old_value': old_value,
                            })
                            log_line_obj.create(cr, uid, line)

    def get_sequence(self, cr, uid, obj_name, res_id, context=None):
        log_seq_obj = self.pool.get('audittrail.log.sequence')
        log_sequence = log_seq_obj.search(cr, uid, [('model', '=', obj_name), ('res_id', '=', res_id)])
        if log_sequence:
            log_seq = log_seq_obj.browse(cr, uid, log_sequence[0]).sequence
            log = log_seq.get_id(code_or_id='id')
        else:
            # Create a new sequence
            seq_pool = self.pool.get('ir.sequence')
            seq_typ_pool = self.pool.get('ir.sequence.type')
            code_name = ('at_%s' % obj_name)[0:32]
            types = {
                'name': 'at_%s' % obj_name,
                'code': code_name,
            }
            seq_typ_pool.create(cr, uid, types)
            seq = {
                'name': 'at_%s' % obj_name,
                'code': code_name,
                'prefix': '',
                'padding': 1,
            }
            seq_id = seq_pool.create(cr, uid, seq)
            log_seq_obj.create(cr, uid, {'model': obj_name, 'res_id': res_id, 'sequence': seq_id})
            log = seq_pool.browse(cr, uid, seq_id).get_id(code_or_id='id')
        return log

audittrail_rule()


class audittrail_log_line(osv.osv):
    """
    Audittrail Log Line.
    """
    _name = 'audittrail.log.line'
    _description = "Log Line"
    _order = 'timestamp asc'

    def _get_values(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return the value of the field according to his type
        '''
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'old_value_fct': False, 'new_value_fct': False}
            if not line.old_value_text:
                res[line.id]['old_value_fct'] = get_value_text(self, cr, uid, line.field_id.id, False, line.old_value, line.fct_object_id or line.object_id, context=context)
            else:
                res[line.id]['old_value_fct'] = line.old_value_text
            if not line.new_value_text:
                res[line.id]['new_value_fct'] = get_value_text(self, cr, uid, line.field_id.id, False, line.new_value, line.fct_object_id or line.object_id, context=context)
            else:
                res[line.id]['new_value_fct'] = line.new_value_text

            if not line.old_value_text and not line.new_value_text:
                self.write(cr, uid, [line.id], {'old_value_text': res[line.id]['old_value_fct'], 'new_value_text': res[line.id]['new_value_fct']})
            elif not line.old_value_text:
                self.write(cr, uid, [line.id], {'old_value_text': res[line.id]['old_value_fct'], })
            elif not line.new_value_text:
                self.write(cr, uid, [line.id], {'new_value_text': res[line.id]['new_value_fct'], })

        return res

    def _get_field_name(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return the name of the field in the user language
        '''
        tr_obj = self.pool.get('ir.translation')

        res = {}
        lang = self.pool.get('res.users').browse(cr, uid, uid, context=context).context_lang

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = False

            # Translation of field name
            if line.field_id:
                field_name = '%s,%s' % (line.object_id.model, line.field_id.name)
                tr_ids = tr_obj.search(cr, uid, [('name', '=', field_name),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'field'),
                                                 ('src', '=', line.field_id.field_description)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], context=context).value

            # Translation of one2many object if any
            if not res[line.id] and line.fct_object_id:
                field_name = '%s,%s' % (line.fct_object_id.model, line.field_id.name)
                tr_ids = tr_obj.search(cr, uid, [('name', '=', field_name),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'field'),
                                                 ('src', '=', line.field_id.field_description)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], context=context).value

            # Translation of main object
            if not res[line.id] and (line.object_id or line.fct_object_id):
                tr_ids = tr_obj.search(cr, uid, [('name', '=', 'ir.model,name'),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'model'),
                                                 ('src', '=', line.name)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], context=context).value

            # No translation
            if not res[line.id]:
                res[line.id] = line.field_description

        return res

    def _src_field_name(self, cr, uid, obj, name, args, context=None):
        '''
        Search field description with the user lang
        '''
        tr_obj = self.pool.get('ir.translation')

        res = []
        lang = self.pool.get('res.users').browse(cr, uid, uid, context=context).context_lang

        for arg in args:
            if arg[0] == 'trans_field_description':
                tr_fields = tr_obj.search(cr, uid, [('lang', '=', lang),
                                                    ('type', 'in', ['field', 'model']),
                                                    ('value', arg[1], arg[2])], context=context)

                field_names = []
                for f in tr_obj.browse(cr, uid, tr_fields, context=context):
                    field_names.append(f.src)

                res = [('field_description', 'in', field_names)]

        return res

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
               context={}, count=False):

        search_ids = super(audittrail_log_line, self).search(cr, uid, args, offset=0,
                                                             limit=None, order=order,
                                                             context=context, count=count)
        id_model_obj = self.pool.get('ir.model')
        model_id = context['active_model']
        current_obj = self.pool.get(model_id)
        inherit = False
        for obj_class in current_obj._inherits:
            inherit = True
            args_inherit = [('model', '=', obj_class)]
            obj_inherit = id_model_obj.search(cr, uid, args_inherit, context=context)
            new_args = [('object_id', '=', obj_inherit[0]),
                        ('res_id', '=', context['active_id'])]
            ids = super(audittrail_log_line, self).search(cr, uid, new_args, offset=0,
                                                          limit=None, order=order,
                                                          context=context, count=count)
            search_ids = search_ids + ids

        if inherit and not isinstance(search_ids, (int, long)):
            args_final = [('id', 'in', search_ids)]
            search_ids = super(audittrail_log_line, self).search(cr, uid, args_final, offset=offset,
                                                                 limit=limit, order=order,
                                                                 context=context, count=count)
        return search_ids


    _columns = {
          'name': fields.char(size=256, string='Description', required=True),
          'object_id': fields.many2one('ir.model', string='Object'),
          'user_id': fields.many2one('res.users', string='User'),
          'method': fields.selection([('create', 'Creation'), ('write', 'Modification'), ('unlink', 'Deletion')], string='Method'),
          'timestamp': fields.datetime(string='Date'),
          'res_id': fields.integer(string='Resource Id'),
          'field_id': fields.many2one('ir.model.fields', 'Fields'),
          'log': fields.integer("Log ID"),
          'old_value_fct': fields.function(_get_values, method=True, string='Old Value Fct', type='char', store=False, multi='values'),
          'new_value_fct': fields.function(_get_values, method=True, string='New Value Fct', type='char', store=False, multi='values'),
          'old_value_text': fields.char(size=256, string='Old Value'),
          'new_value_text': fields.char(size=256, string='New Value'),
          'old_value': fields.text("Old Value"),
          'new_value': fields.text("New Value"),
          'field_description': fields.char('Field Description', size=64),
          'trans_field_description': fields.function(_get_field_name, fnct_search=_src_field_name, method=True, type='char', size=64, string='Field Description', store=False),
          'sub_obj_name': fields.char(size=64, string='Order line'),
          # These 3 fields allows the computation of the name of the subobject (sub_obj_name)
          'rule_id': fields.many2one('audittrail.rule', string='Rule'),
          'fct_res_id': fields.integer(string='Res. Id'),
          'fct_object_id': fields.many2one('ir.model', string='Fct. Object'),
        }

    _defaults = {
        'timestamp': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    def _get_report_name(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        self_info = self.browse(cr, uid, ids[0], context)
        name = self_info.object_id.name or ''
        if self_info.res_id and self_info.object_id.model:
            obj = self.pool.get(self_info.object_id.model)
            if obj:
                name_get = obj.name_get(cr, uid, [self_info.res_id])
                if name_get and name_get[0]:
                    name = name_get[0][1].replace('/', '_')
        return "LL_%s_%s" % (name, time.strftime('%Y%m%d'))

audittrail_log_line()

class ir_model_fields(osv.osv):
    _name = 'ir.model.fields'
    _inherit = 'ir.model.fields'
    _columns = {
        'audittrail_rule_ids': fields.many2many('audittrail.rule', 'audit_rule_field_rel', 'field_id', 'rule_id', string='Audit rules'),
    }
ir_model_fields()

def get_value_text(self, cr, uid, field_id, field_name, values, model, context=None):
    """
    Gets textual values for the fields
    e.g.: For field of type many2one it gives its name value instead of id

    @param cr: the current row, from the database cursor,
    @param uid: the current user’s ID for security checks,
    @param field_name: List of fields for text values
    @param values: Values for field to be converted into textual values
    @return: values: List of textual values for given fields
    """
    if not context:
        context = {}
    if field_name in('__last_update', 'id'):
        return values
    pool = pooler.get_pool(cr.dbname)
    field_pool = pool.get('ir.model.fields')
    model_pool = pool.get('ir.model')
    if not field_id:
        obj_pool = pool.get(model.model)
        # If the field is not in the current object,
        # search if it's in an inherited object
        if obj_pool._inherits:
            inherits_ids = model_pool.search(cr, uid, [('model', '=', obj_pool._inherits.keys()[0])])
            field_ids = field_pool.search(cr, uid, [('name', '=', field_name), ('model_id', 'in', (model.id, inherits_ids[0]))])
        else:
            field_ids = field_pool.search(cr, uid, [('name', '=', field_name), ('model_id', '=', model.id)])
        field_id = field_ids and field_ids[0] or False

    if field_id:
        field = field_pool.read(cr, uid, field_id)
        relation_model = field['relation']
        relation_model_pool = relation_model and pool.get(relation_model) or False

        if field['ttype'] == 'many2one':
            res = False
            if values and values != '()':
                values = values[1:-1].split(',')
                if len(values) and values[0] != '' and relation_model_pool:
                    # int() failed if value '167L'
                    relation_model_object = relation_model_pool.read(cr, uid, long(values[0]), [relation_model_pool._rec_name])
                    res = relation_model_object[relation_model_pool._rec_name]
            return res

        elif field['ttype'] in ('many2many', 'one2many'):
            res = []
            if values and values != '[]':
                values = values[1:-1].split(',')
                for v in values:
                    relation_model_object = relation_model_pool.read(cr, uid, int(v), [relation_model_pool._rec_name])
                    res.append(relation_model_object[relation_model_pool._rec_name])
            return res
        elif field['ttype'] == 'date':
            res = False
            if values:
                date_format = self.pool.get('date.tools').get_date_format(cr, uid, context=context)
                res = datetime.strptime(values, '%Y-%m-%d')
                res = datetime.strftime(res, date_format)
            return res
        elif field['ttype'] == 'datetime':
            res = False
            if values:
                # Display only the date on log line (Comment the next line and uncomment the next one if you want display the time)
                date_format = self.pool.get('date.tools').get_date_format(cr, uid, context=context)
                try:
                    res = datetime.strptime(values, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    res = datetime.strptime(values, '%Y-%m-%d %H:%M:%S.%f')
                finally:
                    res = datetime.strftime(res, date_format)
            return res
        elif field['ttype'] == 'selection':
            res = False
            if values:
                fct_object = model_pool.browse(cr, uid, model.id, context=context).model
                sel = self.pool.get(fct_object).fields_get(cr, uid, [field['name']])
                res = dict(sel[field['name']]['selection']).get(values)
                name = '%s,%s' % (fct_object, field['name'])
                # Search translation
                res_tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name), ('src', 'in', [values])])
                if res_tr_ids:
                    res = self.pool.get('ir.translation').read(cr, uid, res_tr_ids, ['value'])[0]['value']
            return res

    return values

def get_field_description(model):
    """
    Redefine the field_description for sale order and sale order line
    """
    if model.model == 'stock.picking':
        return 'Incoming Shipment'
    return model.name

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
