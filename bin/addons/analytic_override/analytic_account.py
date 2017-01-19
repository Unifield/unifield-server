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

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for account in self.read(cr, uid, ids, ['category', 'name', 'code'], context=context):
            bad_ids = self.search(cr, uid, [('category', '=',
                                             account.get('category', '')), ('|'), ('name', '=ilike',
                                                                                   account.get('name', '')), ('code', '=ilike',
                                                                                                              account.get('code', ''))], order='NO_ORDER', limit=2)
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

    def _fp_line_on_account(self, cr, uid, distrib, account_ids, context=None):
        """
        Return True if one of the "funding.pool.distribution.line" related to the distribution in parameter uses
        one of the accounts in parameter
        """
        if context is None:
            context = {}
        fp_line_obj = self.pool.get('funding.pool.distribution.line')
        fp_line_ids = distrib and fp_line_obj.search(cr, uid, [('distribution_id', '=', distrib.id)], order='NO_ORDER',
                                                     context=context)
        for fp in fp_line_obj.browse(cr, uid, fp_line_ids, context=context,
                                     fields_to_fetch=['destination_id', 'cost_center_id', 'analytic_id']):
            if fp.destination_id.id in account_ids or fp.cost_center_id.id in account_ids or \
                    (fp.analytic_id and fp.analytic_id.id in account_ids):
                return True
        return False

    def _free1_line_on_account(self, cr, uid, distrib, account_ids, context=None):
        """
        Return True if one of the "free.1.distribution.line" related to the distribution in parameter uses
        one of the accounts in parameter
        """
        if context is None:
            context = {}
        free1_obj = self.pool.get('free.1.distribution.line')
        free1_line_ids = distrib and free1_obj.search(cr, uid, [('distribution_id', '=', distrib.id)], order='NO_ORDER',
                                                      context=context)
        for free1 in free1_obj.browse(cr, uid, free1_line_ids, context=context, fields_to_fetch=['analytic_id']):
            if free1.analytic_id and free1.analytic_id.id in account_ids:
                return True
        return False

    def _free2_line_on_account(self, cr, uid, distrib, account_ids, context=None):
        """
        Return True if one of the "free.2.distribution.line" related to the distribution in parameter uses
        one of the accounts in parameter
        """
        if context is None:
            context = {}
        free2_obj = self.pool.get('free.2.distribution.line')
        free2_line_ids = distrib and free2_obj.search(cr, uid, [('distribution_id', '=', distrib.id)], order='NO_ORDER',
                                                      context=context)
        for free2 in free2_obj.browse(cr, uid, free2_line_ids, context=context, fields_to_fetch=['analytic_id']):
            if free2.analytic_id and free2.analytic_id.id in account_ids:
                return True
        return False

    def _invoice_line_on_account(self, cr, uid, account_invoice, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used for one of the "account.invoice" (SI, SR...) lines
        """
        if context is None:
            context = {}
        for inv_line in account_invoice.invoice_line:
            distrib_line = inv_line.analytic_distribution_id or False
            if distrib_line and (self._fp_line_on_account(cr, uid, distrib_line, account_ids, context) or
                                 self._free1_line_on_account(cr, uid, distrib_line, account_ids, context) or
                                 self._free2_line_on_account(cr, uid, distrib_line, account_ids, context)):
                return True
        return False

    def _commitment_voucher_line_on_account(self, cr, uid, comm_voucher, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used for one of the Account Commitment Voucher lines
        """
        if context is None:
            context = {}
        for comm_voucher_line in comm_voucher.line_ids:
            distrib_line = comm_voucher_line.analytic_distribution_id or False
            if distrib_line and self._fp_line_on_account(cr, uid, distrib_line, account_ids, context):
                return True
        return False

    def _po_line_on_account(self, cr, uid, po, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used for one of the PO lines
        """
        if context is None:
            context = {}
        for po_line in po.order_line:
            distrib_line = po_line.analytic_distribution_id or False
            if distrib_line and self._fp_line_on_account(cr, uid, distrib_line, account_ids, context):
                return True
        return False

    def _fo_line_on_account(self, cr, uid, fo, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used for one of the FO lines
        """
        if context is None:
            context = {}
        for fo_line in fo.order_line:
            distrib_line = fo_line.analytic_distribution_id or False
            if distrib_line and self._fp_line_on_account(cr, uid, distrib_line, account_ids, context):
                return True
        return False

    def _regline_on_account(self, cr, uid, regline, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used in the register line
        """
        if context is None:
            context = {}
        distrib_line = regline.analytic_distribution_id or False
        if distrib_line and (self._fp_line_on_account(cr, uid, distrib_line, account_ids, context) or
                             self._free1_line_on_account(cr, uid, distrib_line, account_ids, context) or
                             self._free2_line_on_account(cr, uid, distrib_line, account_ids, context)):
            return True
        return False

    def _accrual_line_on_account(self, cr, uid, acc_line, account_ids, context=None):
        """
        Return True if one of the analytic accounts is used in the accrual line
        """
        if context is None:
            context = {}
        distrib_line = acc_line.analytic_distribution_id or False
        if distrib_line and (self._fp_line_on_account(cr, uid, distrib_line, account_ids, context) or
                             self._free1_line_on_account(cr, uid, distrib_line, account_ids, context) or
                             self._free2_line_on_account(cr, uid, distrib_line, account_ids, context)):
            return True
        return False

    def _check_date(self, cr, uid, vals, account_ids=None, context=None):
        if context is None:
            context = {}
        aji_obj = self.pool.get('account.analytic.line')
        inv_obj = self.pool.get('account.invoice')
        comm_voucher_obj = self.pool.get('account.commitment')
        po_obj = self.pool.get('purchase.order')
        fo_obj = self.pool.get('sale.order')
        regline_obj = self.pool.get('account.bank.statement.line')
        accrual_line_obj = self.pool.get('msf.accrual.line')
        hq_entry_obj = self.pool.get('hq.entries')
        payroll_obj = self.pool.get('hr.payroll.msf')
        if 'date' in vals and vals['date'] is not False:
            if 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))
            elif not context.get('sync_update_execution', False) and account_ids is not None:
                # if the account already exists, check that there is no unposted AJI using it and
                # having a posting date >= selected inactivation date
                aji_ko = aji_obj.search_exist(cr, uid, ['&', '&', ('move_state', '=', 'draft'),
                                                        ('date', '>=', vals['date']),
                                                        '|', '|',
                                                        ('account_id', 'in', account_ids),
                                                        ('cost_center_id', 'in', account_ids),
                                                        ('destination_id', 'in', account_ids)], context=context)
                if aji_ko:
                    raise osv.except_osv(_('Warning !'),
                                         _('At least one unposted Analytic Journal Item using this account has a posting date '
                                           'greater than or equal to the selected inactivation date.'))
                # check that there is no draft "account.invoice" doc (SI, SR...) using the account and having
                # a posting date >= selected inactivation date
                doc_error = osv.except_osv(_('Warning !'), _('At least one document in draft state using this account has a date '
                                                             'greater than or equal to the selected inactivation date.'))
                inv_ids = inv_obj.search(cr, uid, [('date_invoice', '>=', vals['date']),
                                                   ('state', '=', 'draft')], order='NO_ORDER', context=context)
                acc_inv_ko = False
                for inv in inv_obj.browse(cr, uid, inv_ids, fields_to_fetch=['analytic_distribution_id', 'invoice_line'], context=context):
                    distrib = inv.analytic_distribution_id or False
                    # check that the analytic account is not used in the AD at account.invoice header level
                    if distrib and (self._fp_line_on_account(cr, uid, distrib, account_ids, context) or \
                       self._free1_line_on_account(cr, uid, distrib, account_ids, context) or \
                       self._free2_line_on_account(cr, uid, distrib, account_ids, context)):
                        acc_inv_ko = True
                        break
                    # check that the analytic account is not used in the AD at account.invoice Line level
                    if self._invoice_line_on_account(cr, uid, inv, account_ids, context):
                        acc_inv_ko = True
                        break
                if acc_inv_ko:
                    raise doc_error
                # check that there is no draft "Account Commitment Voucher" using the account and having
                # a date >= selected inactivation date
                comm_voucher_ids = comm_voucher_obj.search(cr, uid, [('date', '>=', vals['date']), ('state', '=', 'draft')],
                                                           order='NO_ORDER', context=context)
                comm_voucher_ko = False
                for comm_voucher in comm_voucher_obj.browse(cr, uid, comm_voucher_ids, context=context,
                                                            fields_to_fetch=['analytic_distribution_id', 'line_ids']):
                    comm_voucher_distrib = comm_voucher.analytic_distribution_id or False
                    # check that the analytic account is not used in the AD at Commitment Voucher header level
                    if comm_voucher_distrib and self._fp_line_on_account(cr, uid, comm_voucher_distrib, account_ids, context):
                        comm_voucher_ko = True
                        break
                    # check that the analytic account is not used in the AD at Commitment Voucher Line level
                    if self._commitment_voucher_line_on_account(cr, uid, comm_voucher, account_ids, context):
                        comm_voucher_ko = True
                        break
                if comm_voucher_ko:
                    raise doc_error
                # check that there is no draft PO using the account and having a delivery requested date >= selected inactivation date
                po_ids = po_obj.search(cr, uid, [('delivery_requested_date', '>=', vals['date']), ('state', '=', 'draft')],
                                                  order='NO_ORDER', context=context)
                po_ko = False
                for po in po_obj.browse(cr, uid, po_ids, context=context,
                                        fields_to_fetch=['analytic_distribution_id', 'order_line']):
                    po_distrib = po.analytic_distribution_id or False
                    # check that the analytic account is not used in the AD at PO header level
                    if po_distrib and self._fp_line_on_account(cr, uid, po_distrib, account_ids,  context):
                        po_ko = True
                        break
                    # check that the analytic account is not used in the AD at PO Line level
                    if self._po_line_on_account(cr, uid, po, account_ids, context):
                        po_ko = True
                        break
                if po_ko:
                    raise doc_error
                # check that there is no draft FO using the account and having a delivery requested date >= selected inactivation date
                fo_ids = fo_obj.search(cr, uid, [('delivery_requested_date', '>=', vals['date']), ('state', '=', 'draft')],
                                       order='NO_ORDER', context=context)
                fo_ko = False
                for fo in fo_obj.browse(cr, uid, fo_ids, context=context,
                                        fields_to_fetch=['analytic_distribution_id', 'order_line']):
                    fo_distrib = fo.analytic_distribution_id or False
                    # check that the analytic account is not used in the AD at FO header level
                    if fo_distrib and self._fp_line_on_account(cr, uid, fo_distrib, account_ids, context):
                        fo_ko = True
                        break
                    # check that the analytic account is not used in the AD at FO Line level
                    if self._fo_line_on_account(cr, uid, fo, account_ids, context):
                        fo_ko = True
                        break
                if fo_ko:
                    raise doc_error
                # check that there is no register line using the account, being draft or temp posted, and having a
                # posting date >= selected inactivation date
                regline_ids = regline_obj.search(cr, uid, [('date', '>=', vals['date']), ('state', 'in', ('draft', 'temp'))],
                                                 order='NO_ORDER', context=context)
                regline_ko = False
                for regline in regline_obj.browse(cr, uid, regline_ids, fields_to_fetch=['analytic_distribution_id'], context=context):
                    if self._regline_on_account(cr, uid, regline, account_ids, context):
                        regline_ko = True
                        break
                if regline_ko:
                    raise osv.except_osv(_('Warning !'),
                                         _('At least one draft or temp posted register line using this account has a '
                                           'posting date greater than or equal to the selected inactivation date.'))
                # check that there is no accrual line using the account, being draft or partially posted, and having a
                # posting date >= selected inactivation date
                acc_line_ids = accrual_line_obj.search(cr, uid,
                                                       [('date', '>=', vals['date']), ('state', 'in', ('draft', 'partially_posted'))],
                                                       order='NO_ORDER', context=context)
                acc_line_ko = False
                for acc_line in accrual_line_obj.browse(cr, uid, acc_line_ids, fields_to_fetch=['analytic_distribution_id'], context=context):
                    if self._accrual_line_on_account(cr, uid, acc_line, account_ids, context):
                        acc_line_ko = True
                        break
                if acc_line_ko:
                    raise osv.except_osv(_('Warning !'),
                                         _('At least one draft or partially posted accrual line using this account has '
                                           'a date greater than or equal to the selected inactivation date.'))
                # check that there is no HQ entry using the account, not being validated, and having a
                # posting date >= selected inactivation date
                hq_entry_ko = hq_entry_obj.search_exist(cr, uid, ['&', '&', ('user_validated', '=', False),
                                                        ('date', '>=', vals['date']),
                                                        '|', '|', '|', '|',
                                                        ('analytic_id', 'in', account_ids),
                                                        ('cost_center_id', 'in', account_ids),
                                                        ('destination_id', 'in', account_ids),
                                                        ('free_1_id', 'in', account_ids),
                                                        ('free_2_id', 'in', account_ids)], context=context)
                if hq_entry_ko:
                    raise osv.except_osv(_('Warning !'),
                                         _('At least one HQ entry (not validated) using this account has a posting '
                                           'date greater than or equal to the selected inactivation date.'))
                # check that there is no draft payroll entry using the account and having a date >= selected inactivation date
                payroll_ko = payroll_obj.search_exist(cr, uid, ['&', '&', ('state', '=', 'draft'),
                                                                ('date', '>=', vals['date']),
                                                                '|', '|', '|', '|',
                                                                ('funding_pool_id', 'in', account_ids),
                                                                ('cost_center_id', 'in', account_ids),
                                                                ('destination_id', 'in', account_ids),
                                                                ('free1_id', 'in', account_ids),
                                                                ('free2_id', 'in', account_ids)], context=context)
                if payroll_ko:
                    raise osv.except_osv(_('Warning !'),
                                         _('At least one draft payroll entry using this account has a date '
                                           'greater than or equal to the selected inactivation date.'))

    def copy(self, cr, uid, a_id, default=None, context=None, done_list=[], local=False):
        account = self.browse(cr, uid, a_id, context=context)
        if not default:
            default = {}
        default = default.copy()
        name = '%s(copy)' % account['name'] or ''
        default['code'] = (account['code'] or '') + '(copy)'
        default['name'] = name
        default['tuple_destination_summary'] = []
        # code is deleted in copy method in addons
        new_id = super(analytic_account, self).copy(cr, uid, a_id, default, context=context)
        # UFTP-83: Add name + context (very important) in order the translation to not display wrong element. This is because context is missing (wrong language)
        self.write(cr, uid, new_id, {'name': name,'code': '%s(copy)' % (account['code'] or '')}, context=context)
        trans_obj = self.pool.get('ir.translation')
        trans_ids = trans_obj.search(cr, uid, [('name', '=',
                                                'account.analytic.account,name'), ('res_id', '=', new_id),],
                                     order='NO_ORDER')
        trans_obj.unlink(cr, uid, trans_ids)
        return new_id

    def create(self, cr, uid, vals, context=None):
        """
        Some verifications before analytic account creation
        """
        self._check_date(cr, uid, vals, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)
        return super(analytic_account, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Some verifications before analytic account write
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_date(cr, uid, vals, account_ids=ids, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)

        ###### US-113: I have moved the block that sql updates on the name causing the problem of sync (touched not update). The block is now moved to after the write

        # US-399: First read the value from the database, and check if vals contains any of these values, use them for unicity check 
        new_values = self.read(cr, uid, ids, ['category', 'name', 'code'], context=context)[0]
        if vals.get('name', False):
            new_values['name'] = vals.get('name') 
        if vals.get('category', False):
            new_values['category'] = vals.get('category') 
        if vals.get('code', False):
            new_values['code'] = vals.get('code') 

        ######################################################
        # US-399: Now perform the check unicity manually!
        bad_ids = self.search(cr, uid, [('category', '=',
                                         new_values.get('category', '')), ('|'), ('name', '=ilike',
                                                                                  new_values.get('name', '')), ('code', '=ilike',
                                                                                                                new_values.get('code', ''))], order='NO_ORDER', limit=2)
        if len(bad_ids) and len(bad_ids) > 1:
            raise osv.except_osv(_('Warning !'), _('You cannot have the same code or name between analytic accounts in the same category!'))
        ######################################################

        res = super(analytic_account, self).write(cr, uid, ids, vals, context=context)
        # UFTP-83: Error after duplication, the _constraints is not called with right params. So the _check_unicity gets wrong.
        if vals.get('name', False):
            cr.execute('UPDATE account_analytic_account SET name = %s WHERE id IN %s', (vals.get('name'), tuple(ids)))
        # UFTP-83: Use name as SRC value for translations (to be done after WRITE())
        if vals.get('name', False):
            trans_obj = self.pool.get('ir.translation')
            trans_ids = trans_obj.search(cr, uid, [('name', '=',
                                                    'account.analytic.account,name'), ('res_id', 'in', ids)],
                                         order='NO_ORDER')
            if trans_ids:
                cr.execute('UPDATE ir_translation SET src = %s WHERE id IN %s', (vals.get('name'), tuple(trans_ids)))
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
