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
from datetime import *
import ir
import pooler
import time
import tools
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

class msf_budget(osv.osv):
    _name = 'msf.budget'
    _inherit = 'msf.budget'
    _trace = True

msf_budget()

class financing_contract_contract(osv.osv):
    _name = 'financing.contract.contract'
    _inherit = 'financing.contract.contract'
    _trace = True

financing_contract_contract()

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
        "log_create": fields.boolean("Log Creates",help="Select this if you want to keep track of creation on any record of the object of this rule"),
        "log_action": fields.boolean("Log Action",help="Select this if you want to keep track of actions on the object of this rule"),
        "log_workflow": fields.boolean("Log Workflow",help="Select this if you want to keep track of workflow on any record of the object of this rule"),
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

    _sql_constraints = [
        ('model_uniq', 'unique (object_id)', """There is a rule defined on this object\n You can not define other on the same!""")
    ]
    __functions = {}

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
        #start Loop
        for thisrule in self.browse(cr, uid, ids):
            obj = self.pool.get(thisrule.object_id.model)
            if not obj:
                raise osv.except_osv(
                        _('WARNING: audittrail is not part of the pool'),
                        _('Change audittrail depends -- Setting rule as DRAFT'))
                self.write(cr, uid, [thisrule.id], {"state": "draft"})
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_audittrail', 'view_audittrail_log_line_search')
            val = {
                 "name": 'View Log',
                 "res_model": 'audittrail.log.line',
                 "src_model": thisrule.object_id.model,
                 "search_view_id": search_view_id and search_view_id[1] or False,
                 "domain": "[('object_id','=', " + str(thisrule.object_id.id) + "), ('res_id', '=', active_id)]"

            }
            action_id = obj_action.create(cr, uid, val)
            self.write(cr, uid, [thisrule.id], {"state": "subscribed", "action_id": action_id})
            keyword = 'client_action_relate'
            value = 'ir.actions.act_window,' + str(action_id)
            obj_model.ir_set(cr, uid, 'action', keyword, 'View_log_' + thisrule.object_id.model, [thisrule.object_id.model], value, replace=True, isobject=True, xml_id=False)
            #End Loop
        
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
        value=''
        #start Loop
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
        #End Loop
        
        return True

audittrail_rule()


class audittrail_log_line(osv.osv):
    """
    Audittrail Log Line.
    """
    _name = 'audittrail.log.line'
    _description = "Log Line"
    _order = 'timestamp asc'

    def _get_name_line(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the value of the field set in the rule
        '''
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            if not line.rule_id or not line.fct_res_id or not line.fct_object_id:
                res[line.id] = False
            else:
                field = line.rule_id.name_get_field_id.name
                res_id = line.fct_res_id
                object_id = self.pool.get(line.fct_object_id.model)
                try:
                    res[line.id] = object_id.read(cr, uid, res_id, [field], context=context)[field]
                except TypeError:
                    res[line.id] = False

        return res

    ####
    # TODO : To validate
    ####
    def _search_name_line(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all lines corresponding to the args
        '''
        ids = []

        if not context:
            return []

        for arg in args:
            if not arg[2]:
                return []
            if arg[0] == 'sub_obj_name' and arg[1] == 'ilike' and arg[2]:
                line_ids = self.browse(cr, uid, context.get('active_ids'), context=context)
                for line in line_ids:
                    if line.rule_id and line.fct_res_id and line.fct_object_id:
                        field = line.rule_id.name_get_field_id.name
                        res_id = line.fct_res_id
                        object_id = self.pool.get(line.fct_object_id.model)
                        if str(object_id.read(cr, uid, res_id, [field], context=context)[field]) == arg[2]:
                            ids.append(line.id)
                
                return [('id', 'in', ids)]

        return []
    
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
                self.write(cr, uid, [line.id], {'old_value_text': res[line.id]['old_value_fct'],})
            elif not line.new_value_text:
                self.write(cr, uid, [line.id], {'new_value_text': res[line.id]['new_value_fct'],})
        
        return res

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
          'sub_obj_name': fields.char(size=64, string='Order line'),
#          'sub_obj_name': fields.function(fnct=_get_name_line, fnct_search=_search_name_line, method=True, type='char', string='Order line', store=False),
          # These 3 fields allows the computation of the name of the subobject (sub_obj_name)
          'rule_id': fields.many2one('audittrail.rule', string='Rule'),
          'fct_res_id': fields.integer(string='Res. Id'),
          'fct_object_id': fields.many2one('ir.model', string='Fct. Object'),
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Display the name of the resource on the tree view
        '''
        res = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # TODO: Waiting OEB-86 
#        if view_type == 'tree' and context.get('active_ids') and context.get('active_model'):
#            element_name = self.pool.get(context.get('active_model')).name_get(cr, uid, context.get('active_ids'), context=context)[0][1]
#            xml_view = etree.fromstring(res['arch'])
#            for element in xml_view.iter("tree"):
#                element.set('string', element_name)
#            res['arch'] = etree.tostring(xml_view)
        return res

audittrail_log_line()


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
    if field_name in('__last_update','id'):
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
                if len(values) and relation_model_pool:
                    relation_model_object = relation_model_pool.read(cr, uid, int(values[0]), [relation_model_pool._rec_name])
                    res = relation_model_object[relation_model_pool._rec_name]
            return res

        elif field['ttype'] in ('many2many','one2many'):
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
                date_format = self.pool.get('date.tools').get_date_format(cr, uid, context=context)
                res = datetime.strptime(values, '%Y-%m-%d %H:%M:%S')
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
                res_tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name),('src', 'in', [values])])
                if res_tr_ids:
                    res = self.pool.get('ir.translation').read(cr, uid, res_tr_ids, ['value'])[0]['value']
            return res

    return values

def create_log_line(self, cr, uid, model, lines=[]):
    """
    Creates lines for changed fields with its old and new values

    @param cr: the current row, from the database cursor,
    @param uid: the current user’s ID for security checks,
    @param model: Object who's values are being changed
    @param lines: List of values for line is to be created
    """
    pool = pooler.get_pool(cr.dbname)
    obj_pool = pool.get(model.model)
    model_pool = pool.get('ir.model')
    field_pool = pool.get('ir.model.fields')
    log_line_pool = pool.get('audittrail.log.line')
    #start Loop
    for line in lines:
        if line['name'] in('__last_update','id'):
            continue
        if obj_pool._inherits:
            inherits_ids = model_pool.search(cr, uid, [('model', '=', obj_pool._inherits.keys()[0])])
            field_ids = field_pool.search(cr, uid, [('name', '=', line['name']), ('model_id', 'in', (model.id, inherits_ids[0]))])
        else:
            field_ids = field_pool.search(cr, uid, [('name', '=', line['name']), ('model_id', '=', model.id)])
        field_id = field_ids and field_ids[0] or False

        if field_id:
            field = field_pool.read(cr, uid, field_id)

        # Get the values
        old_value = line.get('old_value')
        new_value = line.get('new_value')
        method = line.get('method')

        if old_value == new_value and method not in ('create', 'unlink'):
            continue
        
        res_id = line.get('res_id')
        name = line.get('name', '')
        object_id = line.get('object_id')
        user_id = line.get('user_id')
        timestamp = line.get('timestamp', time.strftime('%Y-%m-%d %H:%M:%S'))
        log = line.get('log')
        field_description = line.get('field_description', '')
        sub_obj_name = line.get('sub_obj_name', '')
        rule_id = line.get('rule_id')
        fct_res_id = line.get('fct_res_id')
        fct_object_id = line.get('fct_object_id')

        if res_id:
            # Get the log number
            seq_object_id = object_id
            seq_res_id = res_id
            fct_object = self.pool.get('ir.model').browse(cr, uid, seq_object_id)
            log_sequence = self.pool.get('audittrail.log.sequence').search(cr, uid, [('model', '=', fct_object.model), ('res_id', '=', seq_res_id)])
            if log_sequence:
                log_seq = self.pool.get('audittrail.log.sequence').browse(cr, uid, log_sequence[0]).sequence
                log = log_seq.get_id(test='id')
            else:
                # Create a new sequence
                seq_pool = self.pool.get('ir.sequence')
                seq_typ_pool = self.pool.get('ir.sequence.type')
                types = {
                    'name': fct_object.name,
                    'code': fct_object.model,
                }
                seq_typ_pool.create(cr, uid, types)
                seq = {
                    'name': fct_object.name,
                    'code': fct_object.model,
                    'prefix': '',
                    'padding': 1,
                }
                seq_id = seq_pool.create(cr, uid, seq)
                self.pool.get('audittrail.log.sequence').create(cr, uid, {'model': fct_object.model, 'res_id': seq_res_id, 'sequence': seq_id})
                log = self.pool.get('ir.sequence').browse(cr, uid, seq_id).get_id(test='id')


        if field_id:
            field_description = field['field_description']

#            if field['ttype'] == 'many2one':
#                if type(old_value) == tuple:
#                    old_value = old_value[0]
#                if type(new_value) == tuple:
#                    new_value = new_value[0]


        vals = {
                "field_id": field_id,
                "old_value": old_value,
                "new_value": new_value,
                "field_description": field_description,
                "res_id": res_id,
                "name": name,
                "object_id": object_id,
                "user_id": user_id,
                "method": method,
                "timestamp": timestamp,
                "log": log,
                "rule_id": rule_id,
                "fct_res_id": fct_res_id,
                "fct_object_id": fct_object_id,
                "sub_obj_name": sub_obj_name,
                }
        log_line_pool.create(cr, uid, vals)
    #End Loop
    return True

def _get_domain_fields(self, domain=[]):
    '''
    Returns fields to read from the domain
    '''    
    ret_f = []
    for d in domain:
        ret_f.append(d[0])
       
    return ret_f

def _check_domain(self, cr, uid, vals=[], domain=[], model=False, res_id=False):
    '''
    Check if the values check with the domain
    '''
    res = True
    for d in tuple(domain):
        assert d[1] in ('=', '!=', 'in', 'not in'), _("'%s' Not comprehensive operator... Please use only '=', '!=', 'in' and 'not in' operators" %(d[1]))
        
        if d[0] not in vals and model and res_id:
            obj = self.pool.get(model.model).read(cr, uid, res_id, [d[0]])
            vals[d[0]] = obj[d[0]]
        
        if d[1] == '=' and vals[d[0]] != d[2]:
            res = False
        elif d[1] == '!=' and vals[d[0]] == d[2]:
            res = False
        elif d[1] == 'in' and vals[d[0]] not in d[2]:
            res = False
        elif d[1] == 'not in' and vals[d[0]] in d[2]:
            res = False
            
    return res


def log_fct(self, cr, uid, model, method, fct_src, fields_to_trace=None, rule_id=False, parent_field_id=False, name_get_field='name', domain='[]', *args, **kwargs):
    """
    Logging function: This function is performs logging oprations according to method
    @param cr: the current database
    @param uid: the current user’s ID for security checks,
    @param model: Object who's values are being changed
    @param method: method to log: create, read, write, unlink
    @param fct_src: execute method of Object proxy

    @return: Returns result as per method of Object proxy
    """
    if not fields_to_trace:
        fields_to_trace = []
    uid_orig = uid
    uid = 1
    pool = pooler.get_pool(cr.dbname)
    resource_pool = pool.get(model)
    model_pool = pool.get('ir.model')

    model_ids = model_pool.search(cr, uid, [('model', '=', model)])
    model_id = model_ids and model_ids[0] or False
    assert model_id, _("'%s' Model does not exist...") %(model,)
    model = model_pool.browse(cr, uid, model_id)
    domain = eval(domain)
    fields_to_read = ['id']

    if method in ('create'):
        res_id = fct_src(self, *args, **kwargs)
        
        # If the object doesn't match with the domain
        if domain and not _check_domain(self, cr, uid, args[2], domain, model, res_id):
            return res_id
        
        model_id = model.id
        model_name = model.name
        # If we are on the children object, escalate to the parent log
        if parent_field_id:
            parent_field = pool.get('ir.model.fields').browse(cr, uid, parent_field_id)
            model_id = model_pool.search(cr, uid, [('model', '=', parent_field.relation)])
            if not model_id or not args[2].get(parent_field.name, False):
                return res_id
            else:
                model_id = model_id[0]
            model_name = parent_field.model_id.name
            resource = resource_pool.read(cr, uid, res_id, [parent_field.name, name_get_field or 'name'])
            res_id2 = resource[parent_field.name][0]
        else:
            resource = resource_pool.read(cr, uid, res_id, ['id'])
            res_id2 = resource['id']
        
        vals = {
                "name": '%s' %model.name,
                "method": method,
                "object_id": model_id,
                "user_id": uid_orig,
                "res_id": res_id2,
                "field_description": model.name,
        }

        # Add the name of the created sub-object
        if parent_field_id:
            vals.update({'sub_obj_name': resource[name_get_field or 'name'],
                         'rule_id': rule_id,
                         'fct_object_id': model.id,
                         'fct_res_id': res_id})

        if 'id' in resource:
            del resource['id']

        # We create only one line on creation (not one line by field)
        create_log_line(self, cr, uid, model, [vals])

        return res_id

    elif method in ('unlink'):
        res_ids = []
        if isinstance(args[2], (int, long)):
            res_ids = [args[2]]
        else:
            res_ids = list(args[2])
        model_name = model.name
        model_id = model.id
        old_values = {}
        fields_to_read = [name_get_field, 'name']
        fields_to_read.extend(_get_domain_fields(self, domain))
        
        if parent_field_id:
            parent_field = pool.get('ir.model.fields').browse(cr, uid, parent_field_id)
            model_id = model_pool.search(cr, uid, [('model', '=', parent_field.relation)])
            # If the parent object is not a valid object
            if not model_id:
                return fct_src(self, *args, **kwargs)
            else:
                model_id = model_id[0]
            model_name = parent_field.model_id.name
        
        for res_id in res_ids:
            old_values[res_id] = resource_pool.read(cr, uid, res_id, fields_to_read)
            # If the object doesn't match with the domain
            if domain and not _check_domain(self, cr, uid, old_values[res_id], domain):
                res_ids.pop(res_ids.index(res_id))
                
            vals = {
                "name": "%s" %model_name,
                "method": method,
                "object_id": model_id,
                "user_id": uid_orig,
                "field_description": model_name,
            }

            if not parent_field_id:
                vals.update({'res_id': res_id})
            else:
                res_id = resource_pool.read(cr, uid, res_id, [parent_field.name])[parent_field.name][0]
                vals = {
                        "name": "%s" %model_name,
                        "method": method,
                        "object_id": model_id,
                        "user_id": uid_orig,
                        "res_id": res_id,
                        "field_description": model_name,
                        }

            # We create only one line when deleting a record
            create_log_line(self, cr, uid, model, [vals])
        res = fct_src(self, *args, **kwargs)
        return res
    else: 
        res_ids = []
        res = True
        if args:
            if isinstance(args[2], (long, int)):
                res_ids = [args[2]]
            else:
                res_ids = list(args[2])
            old_values = {}
            fields = []
            if len(args)>3 and type(args[3]) == dict:
                fields.extend(list(set(args[3]) & set(fields_to_trace)))
                
        model_id = model.id
        if parent_field_id:
            parent_field = pool.get('ir.model.fields').browse(cr, uid, parent_field_id)
            model_id = model_pool.search(cr, uid, [('model', '=', parent_field.relation)])
            # If the parent object is not a valid object
            if not model_id:
                return res
            else:
                model_id = model_id[0]
                
            if parent_field.name not in fields:
                fields.append(parent_field.name)
            
        fields.extend(_get_domain_fields(self, domain))
        # Remove double entries
        fields = list(set(fields))
        if name_get_field not in fields:
            fields.append(name_get_field)

        # Get old values
        if res_ids:
            for resource in resource_pool.read(cr, uid, res_ids, fields):
                if parent_field_id and not args[3].get(parent_field.name, resource[parent_field.name]):
                    continue
                if domain and not _check_domain(self, cr, uid, resource, domain):
                    res_ids.pop(res_ids.index(resource['id']))
                    continue
                
                resource_id = resource['id']
                if 'id' in resource:
                    del resource['id']
                    
                old_value = resource.copy()
#                for field in resource.keys():
#                    old_value = resource.copy()
                
                old_values[resource_id] = {'value': old_value}

        # Run the method on object
        res = fct_src(self, *args, **kwargs)

        # Get new values
        if res_ids:
            for resource in resource_pool.read(cr, uid, res_ids, fields):
                if parent_field_id and not args[3].get(parent_field.name, resource[parent_field.name]):
                    continue
                res_id = resource['id']
                res_id2 = parent_field_id and resource[parent_field.name][0] or res_id
                if 'id' in resource:
                    del resource['id']

                vals = {
                    "method": method,
                    "object_id": model_id,
                    "user_id": uid_orig,
                    "res_id": res_id2,
                }
                if 'name' in resource:
                    vals.update({'name': resource['name']})

                # Add the name of the created sub-object
                if parent_field_id:
                    vals.update({'sub_obj_name': resource[name_get_field],
                                 'rule_id': rule_id,
                                 'fct_object_id': model.id,
                                 'fct_res_id': res_id})

                lines = []
                for field in resource.keys():
                    line = vals.copy()
                    line.update({
                          'name': field,
                          'new_value': resource[field],
                          'old_value': old_values[res_id]['value'][field],
                          })
                    lines.append(line)

                create_log_line(self, cr, uid, model, lines)
        return res
    return True


#########################################################################
#                                                                       #
# OVERRIDE OSV METHODS (only create, write and unlink for the moment)   #
#                                                                       #
#########################################################################

_old_create = osv.osv.create
_old_write = orm.orm.write
_old_unlink = osv.osv.unlink

def _audittrail_osv_method(self, old_method, method_name, cr, *args, **kwargs):
    """ General wrapper for osv methods """
    # If the object is not marked as traced object, just return the normal method
    if not self._trace:
        return old_method(self, *args, **kwargs)

    # If the object is traceable
    uid_orig = args[1]
    model = self._name
    pool = pooler.get_pool(cr.dbname)
    model_pool = pool.get('ir.model')
    rule_pool = pool.get('audittrail.rule')

    def my_fct(cr, uid, model, method, *args, **kwargs):
        rule = False
        model_ids = model_pool.search(cr, uid, [('model', '=', model)])
        model_id = model_ids and model_ids[0] or False

        if not model_id:
            return old_method(self, *args, **kwargs)

        if 'audittrail.rule' in pool.obj_list():
            rule = True

        if not rule:
            return old_method(self, *args, **kwargs)

        rule_ids = rule_pool.search(cr, uid, [('object_id', '=', model_id)])
        if not rule_ids:
            return old_method(self, *args, **kwargs)

        for thisrule in rule_pool.browse(cr, uid, rule_ids):
            fields_to_trace = []
            for field in thisrule.field_ids:
                fields_to_trace.append(field.name)
            if getattr(thisrule, 'log_' + method_name):
                return log_fct(self, cr, uid_orig, model, method, old_method, fields_to_trace, thisrule.id, thisrule.parent_field_id.id, thisrule.name_get_field_id.name, thisrule.domain_filter, *args, **kwargs)
            return old_method(*args, **kwargs)
    res = my_fct(cr, uid_orig, model, method_name, *args, **kwargs)
    return res


def _audittrail_create(self, *args, **kwargs):
    """ Wrapper to trace the osv.create method """
    return _audittrail_osv_method(self, _old_create, 'create', args[0], *args, **kwargs)

def _audittrail_write(self, *args, **kwargs):
    """ Wrapper to trace the osv.write method """
    return _audittrail_osv_method(self, _old_write, 'write', args[0], *args, **kwargs)

def _audittrail_unlink(self, *args, **kwargs):
    """ Wrapper to trace the osv.unlink method """
    return _audittrail_osv_method(self, _old_unlink, 'unlink', args[0], *args, **kwargs)

osv.osv.create = _audittrail_create
orm.orm.write = _audittrail_write
osv.osv.unlink = _audittrail_unlink

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
