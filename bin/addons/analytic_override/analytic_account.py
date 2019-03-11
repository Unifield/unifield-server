# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 MSF, TeMPO Consulting.
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
from datetime import datetime
from datetime import date
import decimal_precision as dp
from dateutil.relativedelta import relativedelta
from tools.translate import _
from lxml import etree

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        '''
        If date out of date_start/date of given analytic account, then account is inactive.
        The comparison could be done via a date given in context.
        '''
        res = {}
        cmp_date = date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for a in self.browse(cr, uid, ids):
            res[a.id] = True
            if a.date_start > cmp_date:
                res[a.id] = False
            if a.date and a.date <= cmp_date:
                res[a.id] = False
        return res

    def _search_filter_active(self, cr, uid, ids, name, args, context=None):
        """
        UTP-410: Add the search on active/inactive CC
        """
        arg = []
        cmp_date = date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for x in args:
            if x[0] == 'filter_active' and x[2] == True:
                arg.append(('date_start', '<=', cmp_date))
                arg.append('|')
                arg.append(('date', '>', cmp_date))
                arg.append(('date', '=', False))
            elif x[0] == 'filter_active' and x[2] == False:
                arg.append('|')
                arg.append(('date_start', '>', cmp_date))
                arg.append(('date', '<=', cmp_date))
        return arg

    def _get_fake(self, cr, uid, ids, *a, **b):
        return {}.fromkeys(ids, False)

    def _compute_level_tree(self, cr, uid, ids, child_ids, res, field_names, context=None):
        """
        Change balance value using output_currency_id currency in context (if exists)
        """
        # some checks
        if not context:
            context = {}
        res = super(analytic_account, self)._compute_level_tree(cr, uid, ids, child_ids, res, field_names, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        if context.get('output_currency_id', False):
            for res_id in res:
                if res[res_id].get('balance', False):
                    new_balance = self.pool.get('res.currency').compute(cr, uid, context.get('output_currency_id'), company_currency, res[res_id].get('balance'), context=context)
                    res[res_id].update({'balance': new_balance,})
        return res

    # @@@override analytic.analytic
    def _debit_credit_bal_qtty(self, cr, uid, ids, name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        # use different criteria regarding analytic account category!
        account_type = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {}
            for field in name:
                res[line.id].update({field: False})
            if line.category:
                if not line.category in account_type:
                    account_type[line.category] = []
                account_type[line.category].append(line.id)
        for cat in account_type:
            default_field = 'account_id'
            if cat == 'DEST':
                default_field = 'destination_id'
            elif cat == 'OC':
                default_field = 'cost_center_id'
            child_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', account_type[cat])]))
            for i in child_ids:
                res[i] =  {}
                for n in name:
                    res[i][n] = 0.0

            #if not child_ids:
            #    return res

            where_date = ''
            where_clause_args = [tuple(child_ids)]
            if context.get('from_date', False):
                where_date += " AND l.date >= %s"
                where_clause_args  += [context['from_date']]
            if context.get('to_date', False):
                where_date += " AND l.date <= %s"
                where_clause_args += [context['to_date']]
            if context.get('instance_ids', False):
                instance_ids = context.get('instance_ids')
                if isinstance(instance_ids, (int, long)):
                    instance_ids = [instance_ids]
                if len(instance_ids) == 1:
                    where_date += " AND l.instance_id = %s"
                else:
                    where_date += " AND l.instance_id in %s"
                where_clause_args.append(tuple(instance_ids))
            # UF-1713: Add currency arg
            if context.get('currency_id', False):
                where_date += " AND l.currency_id = %s"
                where_clause_args += [context['currency_id']]
            cr.execute("""
                  SELECT a.id,
                         sum(
                             CASE WHEN l.amount > 0
                             THEN l.amount
                             ELSE 0.0
                             END
                              ) as debit,
                         sum(
                             CASE WHEN l.amount < 0
                             THEN -l.amount
                             ELSE 0.0
                             END
                              ) as credit,
                         COALESCE(SUM(l.amount),0) AS balance,
                         COALESCE(SUM(l.unit_amount),0) AS quantity
                  FROM account_analytic_account a
                      LEFT JOIN account_analytic_line l ON (a.id = l.""" + default_field  + """)
                  WHERE a.id IN %s
                  """ + where_date + """
                  GROUP BY a.id""", where_clause_args) # ignore_sql_check
            for ac_id, debit, credit, balance, quantity in cr.fetchall():
                res[ac_id] = {'debit': debit, 'credit': credit, 'balance': balance, 'quantity': quantity}
            tmp_res = self._compute_level_tree(cr, uid, ids, child_ids, res, name, context)
            res.update(tmp_res)
        return res

    def _get_parent_of(self, cr, uid, ids, limit=10, context=None):
        """
        Get all parents from the given accounts.
        To avoid problem of recursion, set a limit from 1 to 10.
        """
        # Some checks
        if context is None:
            context = {}
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        if limit < 1 or limit > 10:
            raise osv.except_osv(_('Error'), _("You're only allowed to use a limit between 1 and 10."))
        # Prepare some values
        account_ids = list(ids)
        sql = """
            SELECT parent_id
            FROM account_analytic_account
            WHERE id IN %s
            AND parent_id IS NOT NULL
            GROUP BY parent_id"""
        cr.execute(sql, (tuple(ids),))
        if not cr.rowcount:
            return account_ids
        parent_ids = [x[0] for x in cr.fetchall()]
        account_ids += parent_ids
        stop = 1
        while parent_ids:
            # Stop the search if we reach limit
            if stop >= limit:
                break
            stop += 1
            cr.execute(sql, (tuple(parent_ids),))
            if not cr.rowcount:
                parent_ids = False
            tmp_res = cr.fetchall()
            tmp_ids = [x[0] for x in tmp_res]
            if None in tmp_ids:
                parent_ids = False
            else:
                parent_ids = list(tmp_ids)
                account_ids += tmp_ids
        return account_ids

    _columns = {
        'name': fields.char('Name', size=128, required=True, translate=1),
        'code': fields.char('Code', size=24),
        'type': fields.selection([('view','View'), ('normal','Normal')], 'Type', help='If you select the View Type, it means you won\'t allow to create journal entries using that account.'),
        'date_start': fields.date('Active from', required=True),
        'date': fields.date('Inactive from', select=True),
        'category': fields.selection([('OC','Cost Center'),
                                      ('FUNDING','Funding Pool'),
                                      ('FREE1','Free 1'),
                                      ('FREE2','Free 2'),
                                      ('DEST', 'Destination')], 'Category', select=1),
        'cost_center_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_cost_centers', 'funding_pool_id', 'cost_center_id', string='Cost Centers', domain="[('type', '!=', 'view'), ('category', '=', 'OC')]"),
        'for_fx_gain_loss': fields.boolean(string="For FX gain/loss", help="Is this account for default FX gain/loss?"),
        'tuple_destination_summary': fields.one2many('account.destination.summary', 'funding_pool_id', 'Destination by accounts'),
        'filter_active': fields.function(_get_active, fnct_search=_search_filter_active, type="boolean", method=True, store=False, string="Show only active analytic accounts",),
        'intermission_restricted': fields.function(_get_fake, type="boolean", method=True, store=False, string="Domain to restrict intermission cc"),
        'balance': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Balance', digits_compute=dp.get_precision('Account'), multi='debit_credit_bal_qtty'),
    }

    _defaults ={
        'date_start': lambda *a: (datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d'),
        'for_fx_gain_loss': lambda *a: False,
    }

    def _check_code_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for account in self.read(cr, uid, ids, ['category', 'code'], context=context):
            bad_ids = self.search(cr, uid,
                                  [('category', '=', account.get('category', '')),
                                   ('code', '=ilike', account.get('code', ''))],
                                  order='NO_ORDER', limit=2)
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_gain_loss_account_unicity(self, cr, uid, ids, context=None):
        """
        Check that no more account is "for_fx_gain_loss" available.
        """
        if not context:
            context = {}
        search_ids = self.search(cr, uid, [('for_fx_gain_loss', '=', True)],
                                 order='NO_ORDER', limit=2)
        if search_ids and len(search_ids) > 1:
            return False
        return True

    def _check_gain_loss_account_type(self, cr, uid, ids, context=None):
        """
        Check account type for fx_gain_loss_account: should be Normal type and Cost Center category
        """
        if not context:
            context = {}
        for account in self.browse(cr, uid, ids, context=context):
            if account.for_fx_gain_loss == True and (account.type != 'normal' or account.category != 'OC'):
                return False
        return True

    def _check_default_destination(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            return True
        cr.execute('''select a.code, a.name, d.name from
            '''+self._table+''' d
            left join account_account a on a.default_destination_id = d.id
            left join account_destination_link l on l.destination_id = d.id and l.account_id = a.id and l.disabled='f'
            where a.default_destination_id is not null and l.destination_id is null and d.id in %s ''', (tuple(ids),) # not_a_user_entry
                   )
        error = []
        for x in cr.fetchall():
            error.append(_('"%s" is the default destination for the G/L account "%s %s", you can\'t remove it.')%(x[2], x[0], x[1]))
        if error:
            raise osv.except_osv(_('Warning !'), "\n".join(error))
        return True

    _constraints = [
        (_check_code_unicity, 'You cannot have the same code between analytic accounts in the same category!', ['code', 'category']),
        (_check_gain_loss_account_unicity, 'You can only have one account used for FX gain/loss!', ['for_fx_gain_loss']),
        (_check_gain_loss_account_type, 'You have to use a Normal account type and Cost Center category for FX gain/loss!', ['for_fx_gain_loss']),
        (_check_default_destination, "You can't delete an account which has this destination as default", []),
    ]

    def on_change_category(self, cr, uid, a_id, category):
        if not category:
            return {}
        res = {'value': {}, 'domain': {}}
        parent = self.search(cr, uid, [('category', '=', category), ('parent_id', '=', False)])[0]
        res['value']['parent_id'] = parent
        res['domain']['parent_id'] = [('category', '=', category), ('type', '=', 'view')]
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
            context = {}
        view = super(analytic_account, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        try:
            oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        except ValueError:
            oc_id = 0
        if view_type=='form':
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath('/form/field[@name="cost_center_ids"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('id', 'child_of', [%s])]" % oc_id)
            view['arch'] = etree.tostring(tree)
        return view

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if context is None:
            context={}
        if context.get('hide_inactive', False):
            args.append(('filter_active', '=', True))
        if context.get('current_model') == 'project.project':
            cr.execute("select analytic_account_id from project_project")
            project_ids = [x[0] for x in cr.fetchall()]
            return self.name_get(cr, uid, project_ids, context=context)
        if operator == '=':
            account = self.search(cr, uid, [('code', '=', name)]+args, limit=limit, context=context)
            if account:
                return self.name_get(cr, uid, account, context=context)
        account = self.search(cr, uid, ['|', ('code', 'ilike', '%%%s%%' % name), ('name', 'ilike', '%%%s%%' % name)]+args, limit=limit, context=context)
        return self.name_get(cr, uid, account, context=context)

    def name_get(self, cr, uid, ids, context=None):
        """
        Get name for analytic account with analytic account code.
        Example: For an account OC/Project/Mission, we have something like this:
          MIS-001 (OC-015/PROJ-859)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        res = []
        # Browse all accounts
        for account in self.browse(cr, uid, ids, context=context):
            res.append((account.id, account.code))
        return res

    def set_funding_pool_parent(self, cr, uid, vals):
        if 'category' in vals and \
           'code' in vals and \
                vals['category'] == 'FUNDING' and \
                vals['code'] != 'FUNDING':
            # for all accounts except the parent one
            funding_pool_parent = self.search(cr, uid, [('category', '=', 'FUNDING'), ('parent_id', '=', False)])[0]
            vals['parent_id'] = funding_pool_parent

    def remove_inappropriate_links(self, vals, context=None):
        '''
        Remove relations that are incoherent regarding the category selected. For instance an account with
        category "Funding Pool" can have associated cost centers, whereas a "Destination" shouldn't.
        (That would happen if the category is modified after that the relations have been created).
        :return: corrected vals
        '''
        if context is None:
            context = {}
        if 'category' in vals:
            if vals['category'] != 'DEST':
                vals['destination_ids'] = [(6, 0, [])]
            if vals['category'] != 'FUNDING':
                vals['tuple_destination_account_ids'] = [(6, 0, [])]
                vals['cost_center_ids'] = [(6, 0, [])]
        return vals

    def _check_date(self, vals):
        if 'date' in vals and vals['date'] is not False \
                and 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date
            raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        """
        Don't copy translations when duplicating an analytic account, i.e. we will have "name (copy)" in all languages
        """
        return True

    def copy(self, cr, uid, a_id, default=None, context=None, done_list=[], local=False):
        if context is None:
            context = {}
        account = self.browse(cr, uid, a_id, context=context)
        if not default:
            default = {}
        default = default.copy()
        name = '%s(copy)' % account['name'] or ''
        code = '%s(copy)' % account['code'] or ''
        default['name'] = name
        default['code'] = code
        default['child_ids'] = [] # do not copy the child_ids
        default['tuple_destination_summary'] = []
        default['line_ids'] = []
        return super(analytic_account, self).copy(cr, uid, a_id, default, context=context)

    def _check_name_unicity(self, cr, uid, ids, context=None):
        """
        Raises an error if the name chosen is already used by an analytic account of the same category
        """
        if context is None:
            context = {}
        lang_obj = self.pool.get('res.lang')
        # no check at sync time (note that there may be some accounts with duplicated names created before US-5224)
        if not context.get('sync_update_execution', False):
            if isinstance(ids, (int, long)):
                ids = [ids]
            lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True), ('active', '=', True)], context=context)
            for analytic_acc in self.read(cr, uid, ids, ['category', 'name'], context=context):
                dom = [('category', '=', analytic_acc.get('category', '')),
                       ('name', '=ilike', analytic_acc.get('name', '')),
                       ('id', '!=', analytic_acc.get('id'))]
                duplicate = 0
                # check the potential duplicates in all languages
                if lang_ids:
                    for lang in lang_obj.browse(cr, uid, lang_ids, fields_to_fetch=['code'], context=context):
                        if self.search_exist(cr, uid, dom, context={'lang': lang.code}):
                            duplicate += 1
                elif self.search_exist(cr, uid, dom, context=context):
                    duplicate += 1
                if duplicate > 0:
                    ir_trans = self.pool.get('ir.translation')
                    trans_ids = ir_trans.search(cr, uid, [('res_id', 'in', ids), ('name', '=', 'account.analytic.account,name')], context=context)
                    if trans_ids:
                        ir_trans.clear_transid(cr, uid, trans_ids, context=context)
                    raise osv.except_osv(_('Warning !'), _('You cannot have the same name between analytic accounts in the same category!'))
        return True

    def _check_existing_entries(self, cr, uid, analytic_account_id, context=None):
        """
        Checks if some AJI booked on the analytic_account_id are outside the account activation time interval.
        For FP and Free accounts: check is done on Doc Date. If AJI are found an error is raised to prevent Saving the account.
        For other accounts: check is done on Posting Date. If AJI are found only a message is displayed on top of the page.
        """
        if context is None:
            context = {}
        aal_obj = self.pool.get('account.analytic.line')
        if analytic_account_id:
            analytic_acc_fields = ['date_start', 'date', 'code']
            analytic_acc = self.browse(cr, uid, analytic_account_id, fields_to_fetch=analytic_acc_fields, context=context)
            aal_dom_fp_free = [('account_id', '=', analytic_account_id),
                               '|', ('document_date', '<', analytic_acc.date_start), ('document_date', '>=', analytic_acc.date)]
            if aal_obj.search_exist(cr, uid, aal_dom_fp_free, context=context):
                raise osv.except_osv(_('Error'), _('At least one Analytic Journal Item using the Analytic Account %s '
                                                   'has a Document Date outside the activation dates selected.') % (analytic_acc.code))
            if not context.get('sync_update_execution'):
                aal_dom_cc_dest = ['|', ('cost_center_id', '=', analytic_account_id),  ('destination_id', '=', analytic_account_id),
                                   '|', ('date', '<', analytic_acc.date_start), ('date', '>=', analytic_acc.date)]
                if aal_obj.search_exist(cr, uid, aal_dom_cc_dest, context=context):
                    self.log(cr, uid, analytic_account_id, _('At least one Analytic Journal Item using the Analytic Account %s '
                                                             'has a Posting Date outside the activation dates selected.') % (analytic_acc.code))

    def create(self, cr, uid, vals, context=None):
        """
        Some verifications before analytic account creation
        """
        if context is None:
            context = {}
        # Check that instance_id is filled in for FP
        if context.get('from_web', False) or context.get('from_import_menu', False):
            self.check_fp(cr, uid, vals, to_update=True, context=context)
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)
        # for auto instance creation, fx gain has been stored, need HQ sync + instance sync to get CC
        if context.get('sync_update_execution') and vals.get('code') and vals.get('category') == 'OC':
            param = self.pool.get('ir.config_parameter')
            init_cc_fx_gain = param.get_param(cr, 1, 'INIT_CC_FX_GAIN')
            if init_cc_fx_gain and vals.get('code') == init_cc_fx_gain:
                vals['for_fx_gain_loss'] = True
                param.set_param(cr, 1, 'INIT_CC_FX_GAIN', '')
        ids = super(analytic_account, self).create(cr, uid, vals, context=context)
        self._check_name_unicity(cr, uid, ids, context=context)
        return ids

    def write(self, cr, uid, ids, vals, context=None):
        """
        Some verifications before analytic account write
        """
        if not ids:
            return True
        if context is None:
            context = {}
        # US-166: Ids needs to always be a list
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)
        res = super(analytic_account, self).write(cr, uid, ids, vals, context=context)
        if context.get('from_web', False) or context.get('from_import_menu', False):
            cat_instance = self.read(cr, uid, ids, ['category', 'instance_id'], context=context)[0]
            if cat_instance:
                self.check_fp(cr, uid, cat_instance, context=context)
        self._check_name_unicity(cr, uid, ids, context=context)
        for analytic_acc_id in ids:
            self._check_existing_entries(cr, uid, analytic_acc_id, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete some analytic account is forbidden!
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_accounts = []
        # Search OC CC
        try:
            oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        except ValueError:
            oc_id = 0
        analytic_accounts.append(oc_id)
        # Search Funding Pool
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_funding_pool')[1]
        except ValueError:
            fp_id = 0
        analytic_accounts.append(fp_id)
        # Search Free 1
        try:
            f1_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_1')[1]
        except ValueError:
            f1_id = 0
        analytic_accounts.append(f1_id)
        # Search Free 2
        try:
            f2_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_2')[1]
        except ValueError:
            f2_id = 0
        analytic_accounts.append(f2_id)
        # Search MSF Private Fund
        try:
            msf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_id = 0
        analytic_accounts.append(msf_id)
        # Accounts verification
        for i in ids:
            if i in analytic_accounts:
                raise osv.except_osv(_('Error'), _('You cannot delete this Analytic Account!'))
        return super(analytic_account, self).unlink(cr, uid, ids, context=context)

    def get_analytic_line(self, cr, uid, ids, context=None):
        """
        Return analytic lines list linked to the given analytic accounts
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        default_field = 'account_id'
        for aaa in self.browse(cr, uid, ids):
            if aaa.category == 'OC':
                default_field = 'cost_center_id'
            elif aaa.category == 'DEST':
                default_field = 'destination_id'
        # Prepare some values
        domain = [(default_field, 'child_of', ids)]
        context.update({default_field: context.get('active_id')})
        return {
            'name': _('Analytic Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def button_cc_clear(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'cost_center_ids':[(6, 0, [])]}, context=context)
        return True

    def button_dest_clear(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'tuple_destination_account_ids':[(6, 0, [])]}, context=context)
        return True

analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
