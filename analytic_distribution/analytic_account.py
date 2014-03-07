# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

import datetime
from dateutil.relativedelta import relativedelta
from osv import fields, osv
from tools.translate import _
from lxml import etree
from tools.misc import flatten
from destination_tools import many2many_sorted, many2many_notlazy
import decimal_precision as dp

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        '''
        If date out of date_start/date of given analytic account, then account is inactive.
        The comparison could be done via a date given in context.
        '''
        res = {}
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
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
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
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

    def _search_closed_by_a_fp(self, cr, uid, ids, name, args, context=None):
        """
        UTP-423: Do not display analytic accounts linked to a soft/hard closed contract.
        """
        res = [('id', 'not in', [])]
        if args and args[0] and len(args[0]) == 3:
            if args[0][1] != '=':
                raise osv.except_osv(_('Error'), _('Operator not supported yet!'))
            # Search all fp_ids from soft_closed contract
            sql="""SELECT a.id
                FROM account_analytic_account a, financing_contract_contract fcc, financing_contract_funding_pool_line fcfl
                WHERE fcfl.contract_id = fcc.id
                AND fcfl.funding_pool_id = a.id
                AND fcc.state in ('soft_closed', 'hard_closed');"""
            cr.execute(sql)
            sql_res = cr.fetchall()
            if sql_res:
                aa_ids = self.is_blocked_by_a_contract(cr, uid, [x and x[0] for x in sql_res])
                if aa_ids:
                    if isinstance(aa_ids, (int, long)):
                        aa_ids = [aa_ids]
                    res = [('id', 'not in', aa_ids)]
        return res

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
                where_clause_args += tuple(instance_ids)
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
                  GROUP BY a.id""", where_clause_args)
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
        'destination_ids': many2many_notlazy('account.account', 'account_destination_link', 'destination_id', 'account_id', 'Accounts'),
        'tuple_destination_account_ids': many2many_sorted('account.destination.link', 'funding_pool_associated_destinations', 'funding_pool_id', 'tuple_id', "Account/Destination"),
        'tuple_destination_summary': fields.one2many('account.destination.summary', 'funding_pool_id', 'Destination by accounts'),
        'filter_active': fields.function(_get_active, fnct_search=_search_filter_active, type="boolean", method=True, store=False, string="Show only active analytic accounts",),
        'hide_closed_fp': fields.function(_get_active, fnct_search=_search_closed_by_a_fp, type="boolean", method=True, store=False, string="Linked to a soft/hard closed contract?"),
        'intermission_restricted': fields.function(_get_fake, type="boolean", method=True, store=False, string="Domain to restrict intermission cc"),
        'balance': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Balance', digits_compute=dp.get_precision('Account'), multi='debit_credit_bal_qtty'),
    }

    _defaults ={
        'date_start': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d'),
        'for_fx_gain_loss': lambda *a: False,
    }

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for account in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('category', '=', account.category),('|'),('name', '=ilike', account.name),('code', '=ilike', account.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_gain_loss_account_unicity(self, cr, uid, ids, context=None):
        """
        Check that no more account is "for_fx_gain_loss" available.
        """
        if not context:
            context = {}
        search_ids = self.search(cr, uid, [('for_fx_gain_loss', '=', True)])
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
            left join account_destination_link l on l.destination_id = d.id and l.account_id = a.id
            where a.default_destination_id is not null and l.destination_id is null and d.id in %s ''', (tuple(ids),)
        )
        error = []
        for x in cr.fetchall():
            error.append(_('"%s" is the default destination for the G/L account "%s %s", you can\'t remove it.')%(x[2], x[0], x[1]))
        if error:
            raise osv.except_osv(_('Warning !'), "\n".join(error))
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between analytic accounts in the same category!', ['code', 'name', 'category']),
        (_check_gain_loss_account_unicity, 'You can only have one account used for FX gain/loss!', ['for_fx_gain_loss']),
        (_check_gain_loss_account_type, 'You have to use a Normal account type and Cost Center category for FX gain/loss!', ['for_fx_gain_loss']),
        (_check_default_destination, "You can't delete an account which has this destination as default", []),
    ]

    def copy(self, cr, uid, a_id, default=None, context=None, done_list=[], local=False):
        account = self.browse(cr, uid, a_id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (account['code'] or '') + '(copy)'
        default['name'] = (account['name'] or '') + '(copy)'
        default['tuple_destination_summary'] = []
        # code is deleted in copy method in addons
        new_id = super(analytic_account, self).copy(cr, uid, a_id, default, context=context)
        self.write(cr, uid, new_id, {'code': '%s(copy)' % (account['code'] or '')})
        return new_id

    def set_funding_pool_parent(self, cr, uid, vals):
        if 'category' in vals and \
           'code' in vals and \
            vals['category'] == 'FUNDING' and \
            vals['code'] != 'FUNDING':
            # for all accounts except the parent one
            funding_pool_parent = self.search(cr, uid, [('category', '=', 'FUNDING'), ('parent_id', '=', False)])[0]
            vals['parent_id'] = funding_pool_parent

    def _check_date(self, vals, context=None):
        if context is None:
            context = {}
        if 'date' in vals and vals['date'] is not False:
            if vals['date'] <= datetime.date.today().strftime('%Y-%m-%d') and not context.get('sync_update_execution', False):
                # validate the date (must be > today)
                raise osv.except_osv(_('Warning !'), _('You cannot set an inactivity date lower than tomorrow!'))
            elif 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))

    def create(self, cr, uid, vals, context=None):
        """
        Some verifications before analytic account creation
        """
        self._check_date(vals, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Some verifications before analytic account write
        """
        self._check_date(vals, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        FIXME: this method do others things that not have been documented. Please complete here what method do.
        """
        if not context:
            context = {}
        if context and 'search_by_ids' in context and context['search_by_ids']:
            args2 = args[-1][2]
            del args[-1]
            ids = []
            for arg in args2:
                ids.append(arg[1])
            args.append(('id', 'in', ids))
        # UF-1713: Active/inactive functionnality was missing.
        if context and 'filter_inactive' in context and context['filter_inactive']:
            args.append(('filter_active', '=', context['filter_inactive']))
        # Tuple Account/Destination search
        for i, arg in enumerate(args):
            if arg[0] and arg[0] == 'tuple_destination':
                fp_ids = []
                destination_ids = self.pool.get('account.destination.link').search(cr, uid, [('account_id', '=', arg[2][0]), ('destination_id', '=', arg[2][1])])
                for adl in self.pool.get('account.destination.link').read(cr, uid, destination_ids, ['funding_pool_ids']):
                    fp_ids.append(adl.get('funding_pool_ids'))
                fp_ids = flatten(fp_ids)
                args[i] = ('id', 'in', fp_ids)
        res = super(analytic_account, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
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

    def on_change_category(self, cr, uid, a_id, category):
        if not category:
            return {}
        res = {'value': {}, 'domain': {}}
        parent = self.search(cr, uid, [('category', '=', category), ('parent_id', '=', False)])[0]
        res['value']['parent_id'] = parent
        res['domain']['parent_id'] = [('category', '=', category), ('type', '=', 'view')]
        return res

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
#            data = []
#            acc = account
#            while acc:
#                data.insert(0, acc.code)
#                acc = acc.parent_id
#            data = ' / '.join(data[1:-1])
#            display = "%s" % (account.code)
#            if len(data) and len(data) > 0:
#                display = "%s (%s)" % (account.code, data)
#            res.append((account.id, display))
            res.append((account.id, account.code))
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

    def is_blocked_by_a_contract(self, cr, uid, ids):
        """
        Return ids (analytic accounts) that are blocked by a contract (just FP1)
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = []
        for aa in self.browse(cr, uid, ids):
            # Only check funding pool accounts
            if aa.category != 'FUNDING':
                continue
            link_ids = self.pool.get('financing.contract.funding.pool.line').search(cr, uid, [('funding_pool_id', '=', aa.id)])
            format_ids = []
            for link in self.pool.get('financing.contract.funding.pool.line').browse(cr, uid, link_ids):
                if link.contract_id:
                    format_ids.append(link.contract_id.id)
            contract_ids = self.pool.get('financing.contract.contract').search(cr, uid, [('format_id', 'in', format_ids)])
            for contract in self.pool.get('financing.contract.contract').browse(cr, uid, contract_ids):
                if contract.state in ['soft_closed', 'hard_closed']:
                    res.append(aa.id)
        return res

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
