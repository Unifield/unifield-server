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

    def _get_dest_without_cc(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns a dict with key = id of the analytic account,
        and value = True if the analytic account is a Destination of normal type allowing no Cost Center, False otherwise
        """
        if context is None:
            context = {}
        res = {}
        for a in self.browse(cr, uid, ids, fields_to_fetch=['category', 'type', 'allow_all_cc', 'dest_cc_ids'], context=context):
            if a.category == 'DEST' and a.type == 'normal' and not a.allow_all_cc and not a.dest_cc_ids:
                res[a.id] = True
            else:
                res[a.id] = False
        return res

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        """
        If date out of date_start/date of given analytic account, then account is inactive.
        The comparison could be done via a date given in context.

        A normal-type destination allowing no CC is also seen as inactive whatever its activation dates
        Exception when coming from a Supply workflow: PO/FO validation should not be blocked for that reason.
        """
        res = {}
        if context is None:
            context = {}
        cmp_date = date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for a in self.browse(cr, uid, ids):
            res[a.id] = True
            if a.date_start > cmp_date:
                res[a.id] = False
            elif a.date and a.date <= cmp_date:
                res[a.id] = False
            elif not context.get('from_supply_wkf') and a.dest_without_cc:
                res[a.id] = False
        return res

    def _search_filter_active(self, cr, uid, ids, name, args, context=None):
        """
        Analytic accounts are seen as active if the date in context (or today's date) is included within the active date range.
        In case of Destination with normal Type: it must additionally allows at least one Cost Center.
        """
        arg = []
        cmp_date = date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for x in args:
            # filter: active
            if x[0] == 'filter_active' and x[2] is True:
                arg.append('&')
                arg.append('&')
                arg.append(('date_start', '<=', cmp_date))
                arg.append('|')
                arg.append(('date', '>', cmp_date))
                arg.append(('date', '=', False))
                arg.append('|')
                arg.append('|')
                arg.append('|')
                arg.append(('category', '!=', 'DEST'))
                arg.append(('type', '=', 'view'))
                arg.append(('allow_all_cc', '=', True))
                arg.append(('dest_cc_ids', '!=', False))
            # filter: inactive
            elif x[0] == 'filter_active' and x[2] is False:
                arg.append('|')
                arg.append('|')
                arg.append(('date_start', '>', cmp_date))
                arg.append(('date', '<=', cmp_date))
                arg.append('&')
                arg.append('&')
                arg.append('&')
                arg.append(('category', '=', 'DEST'))
                arg.append(('type', '=', 'normal'))
                arg.append(('allow_all_cc', '=', False))
                arg.append(('dest_cc_ids', '=', False))
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

    def _is_pf(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns True if the Analytic Account is the default Funding Pool "MSF Private Funds"
        """
        res = {}
        ir_model_obj = self.pool.get('ir.model.data')
        # get the id of PF
        try:
            pf_id = ir_model_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            pf_id = 0
        for analytic_acc_id in ids:
            res[analytic_acc_id] = analytic_acc_id == pf_id
        return res

    def _search_dest_compatible_with_cc_ids(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with all destinations compatible with the selected Cost Center
        Ex: to get the dest. compatible with the CC 2, use the dom [('dest_compatible_with_cc_ids', '=', 2)]
        """
        dom = []
        if context is None:
            context = {}
        for arg in args:
            if arg[0] == 'dest_compatible_with_cc_ids':
                operator = arg[1]
                cc = arg[2]
                if operator != '=' or not isinstance(cc, (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter not implemented on Destinations.'))
                all_dest_ids = self.search(cr, uid, [('category', '=', 'DEST')], context=context)
                compatible_dest_ids = []
                for dest in self.browse(cr, uid, all_dest_ids, fields_to_fetch=['allow_all_cc', 'dest_cc_ids'], context=context):
                    if dest.allow_all_cc or (cc and cc in [c.id for c in dest.dest_cc_ids]):
                        compatible_dest_ids.append(dest.id)
                dom.append(('id', 'in', compatible_dest_ids))
        return dom

    def _get_top_cc_instance_ids(self, cr, uid, ids, fields, arg, context=None):
        """
        Returns a dict. with key = id of the analytic account, and value = id of the instances using it as Top Cost Center
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        instance_obj = self.pool.get('msf.instance')
        for analytic_acc_id in ids:
            res[analytic_acc_id] = instance_obj.search(cr, uid, [('top_cost_center_id', '=', analytic_acc_id)], context=context)
        return res

    def _get_is_target_instance_ids(self, cr, uid, ids, fields, arg, context=None):
        """
        Returns a dict. with key = id of the analytic account, and value = id of the instances using it as Target Cost Center
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        acc_target_cc_obj = self.pool.get('account.target.costcenter')
        for analytic_acc_id in ids:
            instance_ids = []
            target_cc_ids = acc_target_cc_obj.search(cr, uid,
                                                     [('cost_center_id', '=', analytic_acc_id), ('is_target', '=', True)],
                                                     context=context)
            if target_cc_ids:
                for target_cc in acc_target_cc_obj.browse(cr, uid, target_cc_ids, fields_to_fetch=['instance_id'], context=context):
                    instance_ids.append(target_cc.instance_id.id)
            res[analytic_acc_id] = instance_ids
        return res

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
        'is_pf': fields.function(_is_pf, method=True, type='boolean', string='Is the default Funding Pool "PF"', store=False),
        'dest_cc_ids': fields.many2many('account.analytic.account', 'destination_cost_center_rel',
                                        'destination_id', 'cost_center_id', string='Cost Centers',
                                        domain="[('type', '!=', 'view'), ('category', '=', 'OC')]"),
        'allow_all_cc': fields.boolean(string="Allow all Cost Centers"),
        'dest_compatible_with_cc_ids': fields.function(_get_fake, method=True, store=False,
                                                       string='Destinations compatible with the Cost Center',
                                                       type='many2many', relation='account.analytic.account',
                                                       fnct_search=_search_dest_compatible_with_cc_ids),
        'dest_without_cc': fields.function(_get_dest_without_cc, type='boolean', method=True, store=False,
                                           string="Destination allowing no Cost Center",),
        # note: the following 3 fields should theoretically always return one instance, but they are set as one2many in
        # order to be consistent with the type of fields used in the related object
        'top_cc_instance_ids': fields.function(_get_top_cc_instance_ids, method=True, store=False, readonly=True,
                                               string="Instances having the CC as Top CC",
                                               type="one2many", relation="msf.instance"),
        'is_target_instance_ids': fields.function(_get_is_target_instance_ids, method=True, store=False, readonly=True,
                                                  string="Instances having the CC as Target CC",
                                                  type="one2many", relation="msf.instance"),
    }

    _defaults ={
        'date_start': lambda *a: (datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d'),
        'for_fx_gain_loss': lambda *a: False,
        'allow_all_cc': lambda *a: False,
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

    def on_change_allow_all_cc(self, cr, uid, ids, allow_all_cc, dest_cc_ids, context=None):
        """
        If the user tries to tick the box "Allow all Cost Centers" whereas CC are selected,
        informs him that he has to remove the CC first
        """
        res = {}
        if allow_all_cc and dest_cc_ids and dest_cc_ids[0][2]:  # e.g. [(6, 0, [1, 2])]
            warning = {
                'title': _('Warning!'),
                'message': _('Please remove the Cost Centers linked to the Destination before ticking this box.')
            }
            res['warning'] = warning
            res['value'] = {'allow_all_cc': False, }
        return res

    def on_change_dest_cc_ids(self, cr, uid, ids, dest_cc_ids, context=None):
        """
        If at least a CC is selected, unticks the box "Allow all Cost Centers"
        """
        res = {}
        if dest_cc_ids and dest_cc_ids[0][2]:  # e.g. [(6, 0, [1, 2])]
            res['value'] = {'allow_all_cc': False, }
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
                vals['dest_cc_ids'] = [(6, 0, [])]
                vals['allow_all_cc'] = False  # default value
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
        default['dest_cc_ids'] = []
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
                aal_dom_cc_dest = ['|', ('cost_center_id', '=', analytic_account_id), ('destination_id', '=', analytic_account_id),
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
        self.check_access_rule(cr, uid, ids, 'write', context=context)
        if context.get('from_web', False) or context.get('from_import_menu', False):
            cat_instance = self.read(cr, uid, ids, ['category', 'instance_id', 'is_pf'], context=context)[0]
            if cat_instance:
                self.check_fp(cr, uid, cat_instance, context=context)
        self._check_name_unicity(cr, uid, ids, context=context)
        if not context.get('sync_update_execution'):
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

    def button_dest_cc_clear(self, cr, uid, ids, context=None):
        """
        Removes all Cost Centers selected in the Destination view
        """
        self.write(cr, uid, ids, {'dest_cc_ids': [(6, 0, [])]}, context=context)
        return True

    def button_dest_clear(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'tuple_destination_account_ids':[(6, 0, [])]}, context=context)
        return True

    def get_destinations_by_accounts(self, cr, uid, ids, context=None):
        """
        Returns a view with the Destinations by accounts (for the FP selected if any, otherwise for all the FP)
        """
        if context is None:
            context = {}
        ir_model_obj = self.pool.get('ir.model.data')
        active_ids = context.get('active_ids', [])
        if active_ids:
            analytic_acc_category = self.browse(cr, uid, active_ids[0], fields_to_fetch=['category'], context=context).category or ''
            if analytic_acc_category == 'FUNDING':
                context.update({'search_default_funding_pool_id': active_ids[0]})
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'analytic_distribution', 'view_account_destination_summary_search')
        search_view_id = search_view_id and search_view_id[1] or False
        return {
            'name': _('Destinations by accounts'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.destination.summary',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'search_view_id': [search_view_id],
            'context': context,
            'target': 'current',
        }

    def is_account_active(self, analytic_acc_br, date_to_check):
        """
        Returns True if the analytic account is active at the date selected, else returns False.
        """
        if date_to_check < analytic_acc_br.date_start or (analytic_acc_br.date and date_to_check >= analytic_acc_br.date):
            return False
        return True


analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
