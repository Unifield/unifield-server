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

from osv import fields, osv
from tools.translate import _
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


class product_category(osv.osv):
    _name = 'product.category'
    _inherit = 'product.category'
    _trace = True

product_category()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    _trace = True

res_partner()


class res_partner_address(osv.osv):
    _name = 'res.partner.address'
    _inherit = 'res.partner.address'
    _trace = True

res_partner_address()


class product_supplier(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    _trace = True

    def add_audit_line(self, cr, uid, name, object_id, res_id, fct_object_id,
                       fct_res_id, sub_obj_name, field_description,
                       trans_field_description, new_value, old_value, context=None):

        audit_line_obj = self.pool.get('audittrail.log.line')
        audit_seq_obj = self.pool.get('audittrail.log.sequence')
        log = 1

        domain = [
            ('model', '=', 'product.template'),
            ('res_id', '=', res_id),
        ]
        field_id = False
        log_sequence = audit_seq_obj.search(cr, uid, domain)
        if log_sequence:
            log_seq = audit_seq_obj.browse(cr, uid, log_sequence[0]).sequence
            log = log_seq.get_id(code_or_id='id')

        user_id = uid
        if name == 'seller_ids':
            field_id = self.pool.get('ir.model.fields').search(cr, uid, [('model', '=', 'product.template'), ('name', '=', 'seller_ids')], limit=1, context=context)
            if field_id:
                field_id = field_id[0]
            if context.get('real_user'):
                user_id = context['real_user']
        vals = {
            'user_id': user_id,
            'method': 'write',
            'name': name,
            'object_id': object_id,
            'res_id': res_id,
            'fct_object_id': fct_object_id,
            'fct_res_id': fct_res_id,
            'field_id': field_id or False,
            'sub_obj_name': sub_obj_name,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'field_description': field_description,
            'trans_field_description': trans_field_description,
            'new_value': new_value,
            'new_value_text': new_value,
            'new_value_fct': new_value,
            'old_value': old_value,
            'old_value_text': old_value,
            'old_value_fct': old_value,
            'log': log,
        }
        audit_line_obj.create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        ir_model = self.pool.get('ir.model')
        model_name = self._name
        product_model_name = 'product.template'

        object_id = ir_model.search(cr, uid, [('model', '=', product_model_name)], context=context)[0]
        fct_object_id = ir_model.search(cr, uid, [('model', '=', model_name)], context=context)[0]

        suppliers = self.browse(cr, uid, ids, context=context)
        for supplier in suppliers:
            if vals.get('sequence') and vals['sequence'] != supplier.sequence:
                self.add_audit_line(cr, uid, 'sequence', object_id,
                                    supplier.product_id.id, fct_object_id,
                                    supplier.id, supplier.name.name, 'Supplier sequence',
                                    'Supplier sequence', vals['sequence'],
                                    supplier.sequence, context=context)

        res = super(product_supplier, self).write(cr, uid, ids, vals, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Create an audit log lines when create a new supplierinfo
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        ir_model = self.pool.get('ir.model')
        prod_model = self.pool.get('product.template')
        product_model_name = 'product.template'

        object_id = ir_model.search(cr, uid, [('model', '=', product_model_name)], context=context)[0]

        for supplierinfo in self.browse(cr, uid, ids, context=context):
            old_seller = []
            seller_ids = supplierinfo.product_id.seller_ids
            for seller in seller_ids:
                old_seller.append((seller.sequence, seller.name.name))

            res = super(product_supplier, self).unlink(cr, uid, [supplierinfo.id], context=context)

            product_brw = self.pool.get('product.template').browse(cr, uid, supplierinfo.product_id.id, context=context)
            new_seller = []
            for seller in product_brw.seller_ids:
                new_seller.append((seller.sequence, seller.name.name))

            self.add_audit_line(cr, uid, 'seller_ids', object_id,
                                product_brw.id, False, False,
                                False, prod_model._columns['seller_ids'].string,
                                False, new_seller, old_seller, context=context)

        return res

    def create(self, cr, uid, vals, context=None):
        """
        Create an audit log lines when create a new supplierinfo
        """
        ir_model = self.pool.get('ir.model')
        prod_model = self.pool.get('product.template')
        product_model_name = 'product.template'

        object_id = ir_model.search(cr, uid, [('model', '=', product_model_name)], context=context)[0]

        old_seller = []
        if vals.get('product_id', None):
            seller_ids = prod_model.browse(cr, uid, vals.get('product_id'), context=context).seller_ids
            for seller in seller_ids:
                old_seller.append((seller.sequence, seller.name.name))

        res = super(product_supplier, self).create(cr, uid, vals, context=context)

        new_seller = list(old_seller)
        seller = self.browse(cr, uid, res, context=context)
        new_seller.append((seller.sequence, seller.name.name))

        self.add_audit_line(cr, uid, 'seller_ids', object_id,
                            vals.get('product_id'), False, False,
                            False, prod_model._columns['seller_ids'].string,
                            False, new_seller, old_seller, context=context)

        return res

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
        if isinstance(ids, int):
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

#UF-1358: Track changes also for account move and account move line
class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'
    _trace = True

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    _trace = True

account_move_line()


class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'
    _trace = True

hr_employee()


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
                                                    ('res_id', '=', act)],
                                          limit=1, order='NO_ORDER', context=context)
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
        'model': fields.char(size=64, string='Model', select=1),
        'res_id': fields.integer(string='Res Id', select=1),
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
        "field_other_id": fields.many2one('ir.model.fields', string='Displayed other field value'),
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
        if isinstance(ids, int):
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
        if not ids:
            return True
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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
            view_ids = []
            if thisrule.object_id.model == 'account.bank.statement.line' or thisrule.object_id.model == 'account.move.line':
                # for register line we allow to select many lines in track changes view
                # it is required to use fct_object_id and fct_res_id instead
                # of object_id and res_id because account.bank.statement.line are sub object of
                # register and track changes are created this way.
                val['domain'] = "[('fct_object_id','=', %d), ('fct_res_id', 'in', active_ids)]" % (thisrule.object_id.id, )

            elif thisrule.object_id.model == 'stock.move':
                # disable Track changes link
                view_ids.append(obj_model.get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1])

            elif thisrule.object_id.model == 'stock.picking':
                # TC only on IN, OUT
                view_ids.append(obj_model.get_object_reference(cr, uid, 'stock', 'view_picking_in_tree')[1])
                view_ids.append(obj_model.get_object_reference(cr, uid, 'stock', 'view_picking_in_form')[1])
                view_ids.append(obj_model.get_object_reference(cr, uid, 'stock', 'view_picking_out_tree')[1])
                view_ids.append(obj_model.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')[1])
                view_ids.append(obj_model.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_tree')[1])
                view_ids.append(obj_model.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1])

            # search if the view does not already exists
            search_domain = [('name', '=', val['name']),
                             ('res_model', '=', val['res_model']),
                             ('src_model', '=', val['src_model'])]
            action_search = obj_action.search(cr, uid, search_domain)
            if action_search:
                if len(action_search) > 1:
                    logger = logging.getLogger('audittrail')
                    logger.warn('There is already %s ir.actions.act_window matching the domain %r, the first one will be updated' % (len(action_search), search_domain))
                action_id = action_search[0]
            else:
                action_id = obj_action.create(cr, uid, val)
            self.write(cr, uid, [thisrule.id], {"state": "subscribed", "action_id": action_id})
            keyword = 'client_action_relate'
            value = 'ir.actions.act_window,' + str(action_id)
            obj_model.ir_set(cr, uid, 'action', keyword, 'View_log_' + thisrule.object_id.model, [thisrule.object_id.model], value, replace=True, isobject=True, xml_id=False, view_ids=view_ids)
            cr.execute('update ir_values set sequence = 99999 where model=%s and key=\'action\' and name=%s', (thisrule.object_id.model, 'View_log_' + thisrule.object_id.model))
            # End Loop

        # Check if an export model already exist for audittrail.rule
        export_ids = self.pool.get('ir.exports').search(cr, uid, [('name', '=',
                                                                   'Log Lines'), ('resource', '=', 'audittrail.log.line')], limit=1,
                                                        order='NO_ORDER')
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
        if context is None:
            context = {}
        uid_orig = hasattr(uid, 'realUid') and uid.realUid or uid
        uid = 1
        log_line_obj = self.pool.get('audittrail.log.line')

        if isinstance(objids, int):
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
                res_ids = obj.search(cr, uid, new_dom, order='NO_ORDER')
                if not res_ids:
                    continue

                # test next rule on res_ids exluded by the rule domain
                obj_ids = [x for x in obj_ids if x not in res_ids]
            else:
                res_ids = obj_ids[:]
                obj_ids = []

            model_name_tolog = rule.object_id.model
            model_id_tolog = rule.object_id.id
            parent_field = False
            inherits = False
            if rule.parent_field_id:
                parent_field_display = rule.name_get_field_id.name
                parent_field = rule.parent_field_id.name
                model_name_tolog = rule.parent_field_id.relation
                model_parent_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name_tolog)])[0]

            if model_name_tolog in ('product.product', 'hr.employee'):
                inherits = self.pool.get(model_name_tolog)._inherits
                if inherits:
                    model_name_tolog = list(inherits.keys())[-1]
                    model_id_tolog = self.pool.get('ir.model').search(cr, uid, [('model', '=', model_name_tolog)])[0]

            if method in ('write', 'create'):
                original_fields = list(current.values())[0].keys()
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
                if parent_field and new_values_computed[res_id][parent_field]:
                    parent_field_id = new_values_computed[res_id][parent_field][0]

                inherit_field_id = False
                if inherits:
                    inherits_field = list(inherits.values())[-1]
                    inherit_field_ids = self.pool.get(rule.object_id.model).read(cr, uid, res_id, [inherits_field])[inherits_field]
                    if inherit_field_ids:
                        inherit_field_id = inherit_field_ids[0]

                vals = {
                    'name': rule.object_id.name,
                    'method': method,
                    'object_id': model_id_tolog,
                    'user_id': uid_orig,
                    'res_id': parent_field_id or inherit_field_id or res_id,
                }

                if rule.field_other_id:
                    vals.update({
                        'other_column': self.pool.get(rule.object_id.model).read(cr, uid,
                                                                                 res_id, [rule.field_other_id.name])[rule.field_other_id.name]
                    }
                    )

                # Add the name of the created sub-object
                if parent_field_id:
                    # get the parent model_id
                    vals.update({
                        'sub_obj_name': new_values_computed[res_id][parent_field_display],
                        'rule_id': rule.id,
                        'fct_object_id': model_id_tolog,
                        'object_id': model_parent_id,
                        'fct_res_id': inherit_field_id or res_id,
                    })
                if method == 'unlink':
                    vals.update({
                        'field_description': get_field_description(rule.object_id),
                        'log': self.get_sequence(cr, uid, model_name_tolog, vals['res_id'], context=context),
                    })
                    log_line_obj.create(cr, uid, vals)

                elif method in ('write', 'create'):
                    if method == 'create' and rule.object_id.model != 'stock.picking':
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

                    for field in list(fields_to_trace.keys()):
                        old_value = record.get(field, False)
                        new_value = current[res_id].get(field, False)

                        # Don't trace two times the translatable fields
                        if fields_to_trace[field].translate:
                            tr_domain  = [
                                ('name', '=', '%s,%s' % (rule.object_id.model, field)),
                                ('res_id', '=', res_id),
                                ('type', '=', 'model'),
                            ]
                            if context.get('lang'):
                                tr_domain.append(('lang', '=', context.get('lang', 'en_US')),)
                            if new_value:
                                tr_domain.append(('value', '=', new_value))
                            tr_ids = self.pool.get('ir.translation').search(cr, uid, tr_domain)
                            if not new_value and tr_ids:
                                old_value = self.pool.get('ir.translation').read(cr, uid, tr_ids[0], ['value'])['value']

                            if context.get('translate_fields') and not tr_ids:
                                continue

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

        context['translate_fields'] = True

    def get_sequence(self, cr, uid, obj_name, res_id, context=None):
        log_seq_obj = self.pool.get('audittrail.log.sequence')
        log_sequence = log_seq_obj.search(cr, uid, [('model', '=', obj_name), ('res_id', '=', res_id)])
        if log_sequence:
            log_seq = log_seq_obj.browse(cr, uid, log_sequence[0], fields_to_fetch=['sequence']).sequence
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
            log = seq_pool.get_id(cr, uid, seq_id, code_or_id='id')
        return log

audittrail_rule()


class audittrail_log_line(osv.osv):
    """
    Audittrail Log Line.
    """
    _name = 'audittrail.log.line'
    _description = "Log Line"
    _order = 'timestamp desc, log desc'

    def _auto_init(self, cr, context=None):
        super(audittrail_log_line, self)._auto_init(cr, context)
        if not cr.index_exists('audittrail_log_line', 'audittrail_log_line_object_id_res_id_idx'):
            cr.execute('CREATE INDEX audittrail_log_line_object_id_res_id_idx ON audittrail_log_line (object_id, res_id)')
        if not cr.index_exists('audittrail_log_line', 'audittrail_log_line_fct_object_id_fct_res_id_idx'):
            cr.execute('CREATE INDEX audittrail_log_line_fct_object_id_fct_res_id_idx ON audittrail_log_line (fct_object_id, fct_res_id)')


    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change the tracking view depending on the model_object
        """
        if context is None:
            context = {}
        if context.get('active_model') in ('account.bank.statement', 'account.bank.statement.line'):
            # Register Track Changes
            dataobj = self.pool.get('ir.model.data')
            if view_type == 'tree':
                dummy, view_id = dataobj.get_object_reference(cr, 1, 'register_accounting', 'view_audittrail_log_line_other_column_tree')
            elif view_type == 'search':
                dummy, view_id = dataobj.get_object_reference(cr, 1, 'register_accounting', 'view_audittrail_log_line_register_search')
        elif view_type == 'tree' and\
                context.get('active_model') in\
                ('account.move', 'account.move.line'):
            dataobj = self.pool.get('ir.model.data')
            dummy, view_id = dataobj.get_object_reference(cr, 1, 'account', 'view_audittrail_log_line_account_move_tree')
        view = super(audittrail_log_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return view

    def create(self, cr, uid, vals, context=None):
        """
        get text values at create step because in some cases the text values
        will not be available (when a object link to this one is deleted, then
        the delete track log cannot get the text value cause the object is
        deleted)
        """
        line_id = super(audittrail_log_line, self).create(cr, uid, vals, context=context)
        self._get_values(cr, uid, line_id, None, None, context=context)
        return line_id

    def _get_values(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return the value of the field according to his type
        '''
        res = {}
        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'old_value_fct': False, 'new_value_fct': False}
            obj_to_log = line.fct_object_id or line.object_id

            # translate value of fields.selection
            to_compute = line.field_id.name in ('state_to_display', 'state', 'state_hidden_sale_order', 'rfq_state', 'rfq_line_state')\
                         and obj_to_log.model in ('sale.order', 'sale.order.line', 'purchase.order', 'purchase.order.line')
            if line.method == 'create':
                res[line.id]['old_value_fct'] = False
            elif to_compute or not line.old_value_text:
                res[line.id]['old_value_fct'] = get_value_text(self, cr, uid, line.field_id.id, False, line.old_value, obj_to_log, context=context)
            else:
                res[line.id]['old_value_fct'] = line.old_value_text

            if to_compute or not line.new_value_text:
                res[line.id]['new_value_fct'] = get_value_text(self, cr, uid, line.field_id.id, False, line.new_value, obj_to_log, context=context)
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

        for line in self.browse(cr, uid, ids, fields_to_fetch=['field_id', 'object_id', 'fct_object_id', 'res_id', 'name', 'field_description'], context=context):
            res[line.id] = False
            # Translation of field name
            if line.field_id:
                field_name = ['%s,%s' % (line.object_id.model, line.field_id.name)]
                if line.object_id.model == 'product.template':
                    field_name.append('product.product,%s' % (line.field_id.name))
                tr_ids = tr_obj.search(cr, uid, [('name', 'in', field_name),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'field'),
                                                 ('src', '=', line.field_id.field_description)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], fields_to_fetch=['value'], context=context).value

            # Translation of one2many object if any
            if not res[line.id] and line.fct_object_id:
                field_name = '%s,%s' % (line.fct_object_id.model, line.field_id.name)
                tr_ids = tr_obj.search(cr, uid, [('name', '=', field_name),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'field'),
                                                 ('src', '=', line.field_id.field_description)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], fields_to_fetch=['value'], context=context).value

            # Translation of main object
            if not res[line.id] and (line.object_id or line.fct_object_id):
                tr_ids = tr_obj.search(cr, uid, [('name', '=', 'ir.model,name'),
                                                 ('lang', '=', lang),
                                                 ('type', '=', 'model'),
                                                 ('src', '=', line.name)], context=context)
                if tr_ids:
                    res[line.id] = tr_obj.browse(cr, uid, tr_ids[0], fields_to_fetch=['value'], context=context).value

            # No translation
            if not res[line.id]:
                res[line.id] = _(line.field_description)

            # rename 'Field Order' to 'Order' in case of IR
            if line.object_id.model == 'sale.order':
                so = self.pool.get('sale.order').browse(cr, uid, line.res_id, fields_to_fetch=['procurement_request'], context=context)
                if so.procurement_request:
                    if res[line.id].find('Commande de Terrain') != -1:
                            res[line.id] = res[line.id].replace('Commande de Terrain', 'Commande')
                    elif res[line.id].find('Field Order') != -1:
                        res[line.id] = res[line.id].replace('Field Order', 'Order')

            # rename 'Purchase Order' to 'Request for Quotation' in case of RfQ
            if line.object_id.model == 'purchase.order':
                po = self.pool.get('purchase.order').browse(cr, uid, line.res_id, fields_to_fetch=['rfq_ok'], context=context)
                if po.rfq_ok:
                    if res[line.id].find('Bon de Commande') != -1:
                        res[line.id] = res[line.id].replace('Bon de Commande', 'Demande de Devis')
                    elif res[line.id].find('Purchase Order') != -1:
                        res[line.id] = res[line.id].replace('Purchase Order', 'Request for Quotation')

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

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}

        if context.get('active_model') and context.get('active_id'):
            id_model_obj = self.pool.get('ir.model')
            current_obj = self.pool.get(context['active_model'])
            add_obj = []
            num = 0
            for obj_class in current_obj._inherits:
                # get inherits object and inherits id
                obj_inherit = id_model_obj.search(cr, uid, [('model', '=', obj_class)], context=context)

                inherit_field = current_obj._inherits[obj_class]
                rel_obj = current_obj.read(cr, uid, [context['active_id']], [inherit_field], context=context)[0]
                if rel_obj[inherit_field]:
                    add_obj += ['&', ('object_id', '=', obj_inherit[0]), ('res_id', '=', rel_obj[inherit_field][0])]
                    num += 1

            if add_obj:
                # build the new domain
                new_args = []
                target_model = id_model_obj.search(cr, uid, [('model', '=', context['active_model'])], context=context)
                current_filter = ['&', ('res_id', '=', context['active_id']), ('object_id', '=', target_model[0])]
                for arg in args:
                    if arg[0] == 'object_id':
                        new_args += ['|' * num] + current_filter + add_obj
                    elif arg[0] == 'res_id':
                        pass
                    else:
                        new_args += [arg]
                args = new_args


        return super(audittrail_log_line, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

    _columns = {
        'name': fields.char(size=256, string='Description', required=True, readonly=1),
        'object_id': fields.many2one('ir.model', string='Object', readonly=1),
        'user_id': fields.many2one('res.users', string='User', readonly=1),
        'method': fields.selection([('create', 'Creation'), ('write', 'Modification'), ('unlink', 'Deletion')], string='Method', readonly=1),
        'timestamp': fields.datetime(string='Date', readonly=1),
        'res_id': fields.integer(string='Resource Id', readonly=1),
        'field_id': fields.many2one('ir.model.fields', 'Fields', readonly=1),
        'log': fields.integer("Log ID", readonly=1),
        'old_value_fct': fields.function(_get_values, method=True, string='Old Value Fct', type='char', store=False, multi='values'),
        'new_value_fct': fields.function(_get_values, method=True, string='New Value Fct', type='char', store=False, multi='values'),
        'old_value_text': fields.char(size=1024, string='Old Value', readonly=1),
        'new_value_text': fields.char(size=1024, string='New Value', readonly=1),
        'old_value': fields.text("Old Value", readonly=1),
        'new_value': fields.text("New Value", readonly=1),
        'field_description': fields.char('Field Description', size=64, readonly=1),
        'trans_field_description': fields.function(_get_field_name, fnct_search=_src_field_name, method=True, type='char', size=64, string='Field Description', store=False),
        'other_column': fields.char(size=64, string='Sequence', select=1, readonly=1),
        'sub_obj_name': fields.char(size=64, string='Order line', readonly=1),
        # These 3 fields allows the computation of the name of the subobject (sub_obj_name)
        'rule_id': fields.many2one('audittrail.rule', string='Rule', readonly=1),
        'fct_res_id': fields.integer(string='Res. Id', readonly=1),
        'fct_object_id': fields.many2one('ir.model', string='Fct. Object', readonly=1),
    }

    _defaults = {
        'timestamp': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    def _get_report_name(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
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
            inherits_ids = model_pool.search(cr, uid, [('model', '=', list(obj_pool._inherits.keys())[0])])
            field_ids = field_pool.search(cr, uid, [('name', '=', field_name), ('model_id', 'in', (model.id, inherits_ids[0]))])
        else:
            field_ids = field_pool.search(cr, uid, [('name', '=', field_name), ('model_id', '=', model.id)])
        field_id = field_ids and field_ids[0] or False

    if field_id:
        field = field_pool.read(cr, uid, field_id, ['relation', 'ttype', 'name'])
        relation_model = field['relation']
        relation_model_pool = relation_model and pool.get(relation_model) or False

        if field['ttype'] == 'boolean':
            if values in ('True', 't', '1', 1, True):
                res = _('True')
            else:
                res = _('False')
            return res

        elif field['ttype'] == 'many2one':
            res = False
            if values and values != '()':
                values = values[1:-1].split(',')
                if len(values) and values[0] != '' and relation_model_pool:
                    # int() failed if value '167L'
                    res = relation_model_pool.name_get(cr, uid,
                                                       [int(values[0])], context={'from_track_changes': True})[0][1]
            return res

        elif field['ttype'] in ('many2many', 'one2many'):
            res = []
            if values and values != '[]':
                values = values[1:-1].split(',')
                values = [int(v) for v in values]
                res = [x[1] for x in relation_model_pool.name_get(cr, uid, values)]
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
                fct_object = model_pool.browse(cr, uid, model.id, fields_to_fetch=['model'], context=context).model
                sel = self.pool.get(fct_object).fields_get(cr, uid, [field['name']], context=context)
                if field['name'] in sel:
                    res = dict(sel[field['name']]['selection']).get(values)
                    if not res:  # if values is not found as key in selection
                        res = values
                else:
                    res = values
            return res
        elif field['ttype'] == 'float':
            try:
                if values and float(values) >= tools.misc._max_fin_amount_digts:
                    return '%.2f' % float(values)
            except:
                pass

    return values

def get_field_description(model):
    """
    Redefine the field_description for sale order and sale order line
    """
    if model.model == 'stock.picking':
        return 'Incoming Shipment'
    return model.name

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
