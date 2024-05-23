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
        for a in self.browse(cr, uid, ids, fields_to_fetch=['category', 'type', 'allow_all_cc', 'dest_cc_link_ids'], context=context):
            if a.category == 'DEST' and a.type != 'view' and not a.allow_all_cc and not a.dest_cc_link_ids:
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
                arg.append(('dest_cc_link_ids', '!=', False))
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
                arg.append(('type', '!=', 'view'))
                arg.append(('allow_all_cc', '=', False))
                arg.append(('dest_cc_link_ids', '=', False))
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
                if isinstance(instance_ids, int):
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
        if isinstance(ids, int):
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
                if operator != '=' or not isinstance(cc, int):
                    raise osv.except_osv(_('Error'), _('Filter not implemented on Destinations.'))
                if not cc:
                    # by default if no CC is selected display only the Destinations compatible with all CC
                    compatible_dest_ids = self.search(cr, uid, [('category', '=', 'DEST'),
                                                                ('type', '!=', 'view'),
                                                                ('allow_all_cc', '=', True)], context=context)
                else:
                    compatible_dest_sql = """
                        SELECT id
                        FROM account_analytic_account
                        WHERE category = 'DEST' AND type != 'view'
                        AND (allow_all_cc = 't' OR id IN (SELECT dest_id FROM dest_cc_link WHERE cc_id = %s));
                    """
                    cr.execute(compatible_dest_sql, (cc,))
                    compatible_dest_ids = [x[0] for x in cr.fetchall()]
                dom.append(('id', 'in', compatible_dest_ids))
        return dom

    def _search_fp_compatible_with_cc_ids(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with all funding pools compatible with the selected Cost Center
        E.g.: to get the FPs compatible with the CC 2, use the dom [('fp_compatible_with_cc_ids', '=', 2)]
        """
        dom = []
        if context is None:
            context = {}
        ir_model_data_obj = self.pool.get('ir.model.data')
        for arg in args:
            if arg[0] == 'fp_compatible_with_cc_ids':
                operator = arg[1]
                cc_id = arg[2]
                if operator != '=':
                    raise osv.except_osv(_('Error'), _('Filter not implemented on Funding Pools.'))
                cc = False
                if cc_id and isinstance(cc_id, int):
                    cc = self.browse(cr, uid, cc_id, fields_to_fetch=['category', 'type', 'cc_instance_ids'], context=context)
                    if cc.category != 'OC' or cc.type == 'view':
                        raise osv.except_osv(_('Error'), _('Filter only compatible with a normal-type Cost Center.'))
                compatible_fp_ids = []
                # The Funding Pool PF is compatible with every CC
                try:
                    pf_id = ir_model_data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                except ValueError:
                    pf_id = 0
                compatible_fp_ids.append(pf_id)
                if cc:
                    other_fp_ids = self.search(cr, uid, [('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('id', '!=', pf_id)],
                                               context=context)
                    cc_inst_ids = [inst.id for inst in cc.cc_instance_ids]
                    for fp in self.browse(cr, uid, other_fp_ids,
                                          fields_to_fetch=['allow_all_cc_with_fp', 'instance_id', 'cost_center_ids'],
                                          context=context):
                        if fp.allow_all_cc_with_fp and fp.instance_id and fp.instance_id.id in cc_inst_ids:
                            compatible = True
                        elif cc.id in [c.id for c in fp.cost_center_ids]:
                            compatible = True
                        else:
                            compatible = False
                        if compatible:
                            compatible_fp_ids.append(fp.id)
                dom.append(('id', 'in', compatible_fp_ids))
        return dom

    def _search_fp_compatible_with_acc_dest_ids(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with all funding pools compatible with the selected Account/Destination combination.
        It requires a tuple with (account, destination), e.g.: to get the FPs compatible with the G/L account 20 and the
        destination 30, use the dom [('fp_compatible_with_acc_dest_ids', '=', (20, 30))]
        """
        fp_ids = []
        if context is None:
            context = {}
        ir_model_data_obj = self.pool.get('ir.model.data')
        account_obj = self.pool.get('account.account')
        for arg in args:
            if arg[0] == 'fp_compatible_with_acc_dest_ids':
                operator = arg[1]
                if operator != '=':
                    raise osv.except_osv(_('Error'), _('Filter not implemented on Funding Pools.'))
                acc_dest = arg[2]
                acc_id = dest_id = False
                if acc_dest and isinstance(acc_dest, tuple) and len(acc_dest) == 2:
                    acc_id = acc_dest[0]
                    dest_id = acc_dest[1]
                # The Funding Pool PF is compatible with everything and must always be displayed
                try:
                    pf_id = ir_model_data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                except ValueError:
                    pf_id = 0
                fp_ids.append(pf_id)
                if acc_id and dest_id:
                    account_selected = account_obj.browse(cr, uid, acc_id, fields_to_fetch=['destination_ids'], context=context)
                    # search for compatible FPs only if the account and destination selected are compatible with one another
                    if dest_id in [d.id for d in account_selected.destination_ids]:
                        # note: when the link is made to G/L accounts only, all Destinations compatible with the acc. are allowed
                        cr.execute('''
                            SELECT fp.id
                            FROM
                                account_analytic_account fp
                                  LEFT JOIN fp_account_rel ON fp_account_rel.fp_id = fp.id
                                  LEFT JOIN funding_pool_associated_destinations ON funding_pool_associated_destinations.funding_pool_id = fp.id
                                  LEFT JOIN account_destination_link link ON link.id = funding_pool_associated_destinations.tuple_id
                            WHERE
                                fp.category = 'FUNDING' AND
                                fp.type != 'view' AND
                                fp.id != %(pf_id)s AND
                                (
                                    fp.select_accounts_only = 't' AND 
                                    fp_account_rel.account_id = %(acc_id)s
                                OR
                                    fp.select_accounts_only = 'f' AND 
                                    link.account_id = %(acc_id)s AND 
                                    link.destination_id = %(dest_id)s AND 
                                    link.disabled = 'f'
                                )
                        ''', {'pf_id': pf_id, 'acc_id': acc_id, 'dest_id': dest_id})
                        other_fp_ids = [x[0] for x in cr.fetchall()]
                        fp_ids.extend(other_fp_ids)
        return [('id', 'in', fp_ids)]

    def _get_cc_instance_ids(self, cr, uid, ids, fields, arg, context=None):
        """
        Computes the values for fields.function fields, retrieving:
        - the instances using the analytic account...
          ...as Top Cost Center => top_cc_instance_ids
          ...as Target Cost Center => is_target_cc_instance_ids
          ...as Cost centre picked for PO/FO reference => po_fo_cc_instance_ids
          (Note that those fields should theoretically always be linked to one single instance,
           but they are set as one2many in order to be consistent with the type of fields used in the related object.)
        - the Instances where the Cost Center is added to => cc_instance_ids
        - the related Missions => cc_missions
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        acc_target_cc_obj = self.pool.get('account.target.costcenter')
        for analytic_acc_id in ids:
            top_instance_ids = []
            target_instance_ids = []
            po_fo_instance_ids = []
            all_instance_ids = []
            missions = set()
            missions_str = ""
            top_prop_ids = set()
            target_cc_ids = acc_target_cc_obj.search(cr, uid, [('cost_center_id', '=', analytic_acc_id)], context=context)
            if target_cc_ids:
                field_list = ['instance_id', 'is_target', 'is_po_fo_cost_center', 'is_top_cost_center']
                for target_cc in acc_target_cc_obj.browse(cr, uid, target_cc_ids, fields_to_fetch=field_list, context=context):
                    instance = target_cc.instance_id
                    if instance:
                        if instance.level == 'project':
                            top_prop_ids.add(instance.parent_id.id)
                        elif instance.level == 'coordo':
                            top_prop_ids.add(instance.id)
                    all_instance_ids.append(instance.id)
                    if instance.mission:
                        missions.add(instance.mission)
                    if target_cc.is_top_cost_center:
                        top_instance_ids.append(instance.id)
                    if target_cc.is_target:
                        target_instance_ids.append(instance.id)
                    if target_cc.is_po_fo_cost_center:
                        po_fo_instance_ids.append(instance.id)
            if missions:
                missions_str = ", ".join(missions)
            res[analytic_acc_id] = {
                'top_cc_instance_ids': top_instance_ids,
                'is_target_cc_instance_ids': target_instance_ids,
                'po_fo_cc_instance_ids': po_fo_instance_ids,
                'cc_missions': missions_str,
                'cc_instance_ids': all_instance_ids,
                'top_prop_instance': list(top_prop_ids),
            }
        return res

    def _get_selected_in_dest(self, cr, uid, cc_ids, name=False, args=False, context=None):
        """
        Returns True for the Cost Centers already selected in the Destination:
        they will be displayed in grey in the list and won't be re-selectable.
        """
        if context is None:
            context = {}
        if isinstance(cc_ids, int):
            cc_ids = [cc_ids]
        selected = []
        dest_id = context.get('current_destination_id') or False
        if dest_id:
            dest = self.browse(cr, uid, dest_id, fields_to_fetch=['dest_cc_link_ids'], context=context)
            selected = [dest_cc_link.cc_id.id for dest_cc_link in dest.dest_cc_link_ids]
        res = {}
        for cc_id in cc_ids:
            res[cc_id] = cc_id in selected
        return res

    def _get_dest_cc_link_dates(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns a dict with key = id of the analytic account,
        and value = dict with dest_cc_link_active_from and dest_cc_link_inactive_from dates separated by commas (String).
        Note that the date format is the same in EN and FR, and that empty dates are not ignored.
        E.g.: '2021-03-02,2021-03-01,,2021-03-03,'

        This is used in Destination Import Tools, in particular for the Export of existing entries used as examples.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for a in self.browse(cr, uid, ids, fields_to_fetch=['category', 'dest_cc_link_ids'], context=context):
            active_date_list = []
            inactive_date_list = []
            if a.category == 'DEST':
                for cc_link in a.dest_cc_link_ids:
                    active_date_str = "%s" % (cc_link.active_from or "")
                    active_date_list.append(active_date_str)
                    inactive_date_str = "%s" % (cc_link.inactive_from or "")
                    inactive_date_list.append(inactive_date_str)
            res[a.id] = {
                'dest_cc_link_active_from': ",".join(active_date_list),
                'dest_cc_link_inactive_from': ",".join(inactive_date_list),
            }
        return res

    def _get_has_ajis(self, cr, uid, ids, field_name, arg, context=None):
        """
        Returns a dict with key = the id of the account_analytic_account,
        and value = True if at least one AJI use that analytic account, or False otherwise.
        """
        res = {}
        if not ids:
            return res
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        aal_obj = self.pool.get('account.analytic.line')
        for aac_id in ids:
            res[aac_id] = aal_obj.search_exist(cr, uid, ['|', '|', ('account_id', '=', aac_id), ('destination_id', '=', aac_id), ('cost_center_id', '=', aac_id)], context=context) or False
        return res

    _columns = {
        'name': fields.char('Name', size=128, required=True),
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
        'dest_cc_link_ids': fields.one2many('dest.cc.link', 'dest_id', string="Cost Centers", required=False),
        'dest_cc_link_active_from': fields.function(_get_dest_cc_link_dates, method=True, type='char',
                                                    store=False, readonly=True,
                                                    string='Activation Combination Dest / CC from',
                                                    help="Technical field used for Import Tools only",
                                                    multi="dest_cc_link_dates"),
        'dest_cc_link_inactive_from': fields.function(_get_dest_cc_link_dates, method=True, type='char',
                                                      store=False, readonly=True,
                                                      string='Inactivation Combination Dest / CC from',
                                                      help="Technical field used for Import Tools only",
                                                      multi="dest_cc_link_dates"),
        'allow_all_cc': fields.boolean(string="Allow all Cost Centers"),  # for the Destinations
        'allow_all_cc_with_fp': fields.boolean(string="Allow all Cost Centers"),  # for the Funding Pools
        'dest_compatible_with_cc_ids': fields.function(_get_fake, method=True, store=False,
                                                       string='Destinations compatible with the Cost Center',
                                                       type='many2many', relation='account.analytic.account',
                                                       fnct_search=_search_dest_compatible_with_cc_ids),
        'dest_without_cc': fields.function(_get_dest_without_cc, type='boolean', method=True, store=False,
                                           string="Destination allowing no Cost Center",),
        'fp_compatible_with_cc_ids': fields.function(_get_fake, method=True, store=False,
                                                     string='Funding Pools compatible with the Cost Center',
                                                     type='many2many', relation='account.analytic.account',
                                                     fnct_search=_search_fp_compatible_with_cc_ids),
        'fp_compatible_with_acc_dest_ids': fields.function(_get_fake, method=True, store=False,
                                                           string='Funding Pools compatible with the Account/Destination combination',
                                                           type='many2many', relation='account.analytic.account',
                                                           fnct_search=_search_fp_compatible_with_acc_dest_ids),
        'top_cc_instance_ids': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                               string="Instance having the CC as Top CC",
                                               type="one2many", relation="msf.instance", multi="cc_instances"),
        'is_target_cc_instance_ids': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                                     string="Instance having the CC as Target CC",
                                                     type="one2many", relation="msf.instance", multi="cc_instances"),
        'po_fo_cc_instance_ids': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                                 string="Instance having the CC as CC picked for PO/FO ref",
                                                 type="one2many", relation="msf.instance", multi="cc_instances"),
        'cc_missions': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                       string="Missions where the CC is added to",
                                       type='char', multi="cc_instances"),
        'cc_instance_ids': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                           string="Instances where the CC is added to",
                                           type="one2many", relation="msf.instance", multi="cc_instances"),
        'top_prop_instance': fields.function(_get_cc_instance_ids, method=True, store=False, readonly=True,
                                             string="Top Proprietary Instance", type="one2many", relation="msf.instance",
                                             multi="cc_instances"),
        'select_accounts_only': fields.boolean(string="Select Accounts Only"),
        'fp_account_ids': fields.many2many('account.account', 'fp_account_rel', 'fp_id', 'account_id', string='G/L Accounts',
                                           domain="[('type', '!=', 'view'), ('is_analytic_addicted', '=', True), ('active', '=', 't')]",
                                           help="G/L accounts linked to the Funding Pool", order_by='code'),
        'selected_in_dest': fields.function(_get_selected_in_dest, string='Selected in Destination', method=True,
                                            type='boolean', store=False),
        'has_ajis': fields.function(_get_has_ajis, type='boolean', method=True, string='Has Analytic Journal Items', store=False),
    }

    _defaults ={
        # US-8607 : set default date_start to first day of current month
        'date_start': lambda *a: (datetime.today().replace(day=1)).strftime('%Y-%m-%d'),
        'for_fx_gain_loss': lambda *a: False,
        'allow_all_cc': lambda *a: False,
        'allow_all_cc_with_fp': lambda *a: False,
        'select_accounts_only': lambda *a: False,
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
        if isinstance(ids, int):
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

    def on_change_allow_all_cc(self, cr, uid, ids, allow_all_cc, cc_ids, acc_type='destination', field_name='allow_all_cc',
                               m2m=False, context=None):
        """
        If the user tries to tick the box "Allow all Cost Centers" whereas CC are selected,
        informs him that he has to remove the CC first
        (acc_type = name of the Analytic Account Type to which the CC are linked, displayed in the warning msg)
        """
        res = {}
        if allow_all_cc:
            if m2m:
                cc_filled_in = cc_ids and cc_ids[0][2] or False  # e.g. [(6, 0, [1, 2])]
            else:
                cc_filled_in = cc_ids or False
            if cc_filled_in:
                # NOTE: the msg is stored in a variable on purpose, otherwise the ".po" translation files would wrongly contain Python code
                msg = 'Please remove the Cost Centers linked to the %s before ticking this box.' % acc_type.title()
                warning = {
                    'title': _('Warning!'),
                    'message': _(msg)
                }
                res['warning'] = warning
                res['value'] = {field_name: False, }
        return res

    def on_change_allow_all_cc_with_fp(self, cr, uid, ids, allow_all_cc_with_fp, cost_center_ids, context=None):
        return self.on_change_allow_all_cc(cr, uid, ids, allow_all_cc_with_fp, cost_center_ids, acc_type='funding pool',
                                           field_name='allow_all_cc_with_fp', m2m=True, context=context)

    def on_change_cc_ids(self, cr, uid, ids, cc_ids, field_name='allow_all_cc', m2m=False, context=None):
        """
        If at least a CC is selected, unticks the box "Allow all Cost Centers"
        """
        res = {}
        if m2m:
            cc_filled_in = cc_ids and cc_ids[0][2] or False  # e.g. [(6, 0, [1, 2])]
        else:
            cc_filled_in = cc_ids or False
        if cc_filled_in:
            res['value'] = {field_name: False, }
        return res

    def on_change_cc_with_fp(self, cr, uid, ids, cost_center_ids, context=None):
        return self.on_change_cc_ids(cr, uid, ids, cost_center_ids, field_name='allow_all_cc_with_fp', m2m=True, context=context)

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
            view['arch'] = etree.tostring(tree, encoding='unicode')
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
        if isinstance(ids, int):
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
        """
        Removes relations that are inconsistent regarding the category selected. For instance an account with the
        category "Funding Pool" can have associated cost centers, whereas a "Cost Center" shouldn't.
        (That would happen if the category is modified after that the relations have been created).
        :return: corrected vals
        """
        if context is None:
            context = {}
        if 'category' in vals:
            if vals['category'] != 'DEST':
                vals['destination_ids'] = [(6, 0, [])]
                vals['dest_cc_ids'] = [(6, 0, [])]
                vals['dest_cc_link_ids'] = []  # related dest.cc.links (if any) are deleted in _clean_dest_cc_link
                vals['allow_all_cc'] = False  # default value
            if vals['category'] != 'FUNDING':
                vals['tuple_destination_account_ids'] = [(6, 0, [])]
                vals['cost_center_ids'] = [(6, 0, [])]
                vals['allow_all_cc_with_fp'] = False  # default value
                vals['select_accounts_only'] = False
                vals['fp_account_ids'] = [(6, 0, [])]
            # Funding Pools: either "Account/Destination combinations" or "G/L accounts only" must be stored
            if vals['category'] == 'FUNDING' and 'select_accounts_only' in vals:
                if vals['select_accounts_only']:
                    vals['tuple_destination_account_ids'] = [(6, 0, [])]
                else:
                    vals['fp_account_ids'] = [(6, 0, [])]
        return vals

    def _check_data(self, vals, context=None):
        if context is None:
            context = {}
        if 'date' in vals and vals['date'] is not False \
                and 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date
            raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))
        if 'code' in vals and vals['code'] is not False and ';' in vals['code']:
            # to prevent issues in the draft FO/PO AD import
            raise osv.except_osv(_('Warning !'), _('The Code can not contain a semicolon (;)'))

    def _check_sub_cc(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'category' in vals and vals['category'] == 'OC' and 'parent_id' in vals and vals['parent_id']:
            msg = ''
            parent = self.browse(cr, uid, vals['parent_id'], fields_to_fetch=['date_start', 'date', 'code'], context=context)
            if parent.code == 'OC':  # If parent CC is OC, no need to check
                return True
            if parent.date and parent.date < datetime.today().strftime('%Y-%m-%d'):
                raise osv.except_osv(_('Warning !'), _('The parent CC %s is not active, you can not create a child to this parent') % parent.code)
            if ('date' in vals and vals['date'] and parent.date and vals['date'] > parent.date) or parent.date and ('date' not in vals or ('date' in vals and vals['date'] == False)):
                msg += _('The sub-costcenter validity date is greater than the parent cost center validity date!') + "\n"
            if 'date_start' in vals and vals['date_start'] and parent.date_start and vals['date_start'] < parent.date_start:
                msg += _('The sub-costcenter activation date is lower than the parent cost center activation date!') + "\n"

            if msg:
                raise osv.except_osv(_('Warning !'), msg)


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
        default['dest_cc_link_ids'] = []
        return super(analytic_account, self).copy(cr, uid, a_id, default, context=context)

    def _check_name_unicity(self, cr, uid, ids, context=None):
        """
        Raises an error if the name chosen is already used by an analytic account of the same category
        """
        if context is None:
            context = {}
        # no check at sync time (note that there may be some accounts with duplicated names created before US-5224)
        if not context.get('sync_update_execution', False):
            if isinstance(ids, int):
                ids = [ids]
            for analytic_acc in self.read(cr, uid, ids, ['category', 'name'], context=context):
                dom = [('category', '=', analytic_acc.get('category', '')),
                       ('name', '=ilike', analytic_acc.get('name', '')),
                       ('id', '!=', analytic_acc.get('id'))]
                if self.search_exist(cr, uid, dom, context=context):
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

    def _clean_dest_cc_link(self, cr, uid, ids, vals, context=None):
        """
        In case Dest CC Links are reset in an analytic account: deletes the related existing Dest CC Links if any.
        Probable UC: Dest CC Links selected on a destination, then account changed to another category.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if 'dest_cc_link_ids' in vals and not vals['dest_cc_link_ids']:
            dcl_ids = []
            for analytic_acc in self.browse(cr, uid, ids, fields_to_fetch=['dest_cc_link_ids'], context=context):
                dcl_ids.extend([dcl.id for dcl in analytic_acc.dest_cc_link_ids])
            if dcl_ids:
                self.pool.get('dest.cc.link').unlink(cr, uid, dcl_ids, context=context)
        return True

    def _dest_cc_ids_must_be_updated(self, vals, context):
        """
        Returns True if dest_cc_ids in vals must be changed to dest_cc_link_ids (the goal of this method is to ensure
        that the same condition is used everywhere and that the UC where all CC are removed is taken into account)
        """
        if context and vals and context.get('sync_update_execution') and vals.get('dest_cc_ids') and vals['dest_cc_ids'][0][2] is not None:
            return True
        return False

    def _update_synched_dest_cc_ids(self, cr, uid, dest_ids, vals, context):
        """
        For synch made before or while US-7295 was released: changes the dest_cc_ids into dest_cc_link_ids
        """
        if self._dest_cc_ids_must_be_updated(vals, context):
            dest_cc_link_obj = self.pool.get('dest.cc.link')
            if isinstance(dest_ids, int):
                dest_ids = [dest_ids]
            for dest_id in dest_ids:
                dest = self.browse(cr, uid, dest_id, fields_to_fetch=['dest_cc_link_ids'], context=context)
                # note: after US-7295 patch script no instance has any dest_cc_ids, all CC links are necessarily dest.cc.link
                current_cc_ids = [dest_cc_link.cc_id.id for dest_cc_link in dest.dest_cc_link_ids]
                new_cc_ids = vals['dest_cc_ids'][0][2] or []  # take into account the UC where all CC are removed
                # delete the CC to be deleted
                cc_to_be_deleted = [c for c in current_cc_ids if c not in new_cc_ids]
                if cc_to_be_deleted:
                    dcl_to_be_deleted = dest_cc_link_obj.search(cr, uid, [('dest_id', '=', dest_id), ('cc_id', 'in', cc_to_be_deleted)],
                                                                order='NO_ORDER', context=context)
                    dest_cc_link_obj.unlink(cr, uid, dcl_to_be_deleted, context=context)
                # create the CC to be created
                dcl_created = []
                out_of_sync_ctx = context.copy()
                del out_of_sync_ctx['sync_update_execution']  # removed in order for the sdrefs to be created
                for cc_id in [c for c in new_cc_ids if c not in current_cc_ids]:
                    new_dcl_id = dest_cc_link_obj.create(cr, uid, {'dest_id': dest_id, 'cc_id': cc_id}, context=out_of_sync_ctx)
                    dcl_created.append(new_dcl_id)
                if dcl_created:
                    # prevents the sync of the links created, which are used at migration time only and will be deleted
                    # (see the US-7295 patch script). Note: sync direction is DOWN so this code is never executed in HQ.
                    cr.execute("""
                               UPDATE ir_model_data 
                               SET touched ='[]', last_modification = '1980-01-01 00:00:00'
                               WHERE module='sd' 
                               AND model='dest.cc.link' 
                               AND res_id IN %s
                    """, (tuple(dcl_created),))
            del vals['dest_cc_ids']
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Some verifications before analytic account creation
        """
        if context is None:
            context = {}
        # Check that instance_id is filled in for FP
        if context.get('from_web', False) or context.get('from_import_menu', False):
            self.check_fp(cr, uid, vals, to_update=True, context=context)
        self._check_data(vals, context=context)
        self._check_sub_cc(cr, uid, vals=vals, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)
        vals_copy = vals.copy()
        if self._dest_cc_ids_must_be_updated(vals, context):
            del vals['dest_cc_ids']  # replaced by dest_cc_link_ids in _update_synched_dest_cc_ids (called after create as it uses the new id)
        # for auto instance creation, fx gain has been stored, need HQ sync + instance sync to get CC
        if context.get('sync_update_execution') and vals.get('code') and vals.get('category') == 'OC':
            param = self.pool.get('ir.config_parameter')
            init_cc_fx_gain = param.get_param(cr, 1, 'INIT_CC_FX_GAIN')
            if init_cc_fx_gain and vals.get('code') == init_cc_fx_gain:
                vals['for_fx_gain_loss'] = True
                param.set_param(cr, 1, 'INIT_CC_FX_GAIN', '')
        if vals.get('code', False):
            vals['code'] = vals['code'].strip()
        if vals.get('name', False):
            vals['name'] = vals['name'].strip()
        analytic_acc_id = super(analytic_account, self).create(cr, uid, vals, context=context)
        self._check_name_unicity(cr, uid, analytic_acc_id, context=context)
        self._clean_dest_cc_link(cr, uid, analytic_acc_id, vals, context=context)
        self._update_synched_dest_cc_ids(cr, uid, analytic_acc_id, vals_copy, context)
        return analytic_acc_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Some verifications before analytic account write
        """
        if not ids:
            return True
        if context is None:
            context = {}
        # US-166: Ids needs to always be a list
        if isinstance(ids, int):
            ids = [ids]
        self._check_data(vals, context=context)
        self.set_funding_pool_parent(cr, uid, vals)
        vals = self.remove_inappropriate_links(vals, context=context)
        self._update_synched_dest_cc_ids(cr, uid, ids, vals, context)
        if vals.get('code', False):
            vals['code'] = vals['code'].strip()
        if vals.get('name', False):
            vals['name'] = vals['name'].strip()
        res = super(analytic_account, self).write(cr, uid, ids, vals, context=context)
        self._clean_dest_cc_link(cr, uid, ids, vals, context=context)
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

    def get_analytic_line(self, cr, uid, ids, context=None):
        """
        Return analytic lines list linked to the given analytic accounts
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
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

    def get_cc_linked_to_fp(self, cr, uid, fp_id, context=None):
        """
        Returns a browse record list of all Cost Centers compatible with the Funding Pool in parameter:
        - if "Allow all Cost Centers" is ticked: all CC linked to the prop. instance of the FP
        - else all CC selected in the FP form.

        Note: this method matches with what has been selected in the Cost centers tab of the FP form.
              It returns an empty list for PF.
        """
        if context is None:
            context = {}
        cc_list = []
        fp = self.browse(cr, uid, fp_id,
                         fields_to_fetch=['category', 'allow_all_cc_with_fp', 'instance_id', 'cost_center_ids'],
                         context=context)
        if fp.category == 'FUNDING':
            if fp.allow_all_cc_with_fp and fp.instance_id:
                # inactive CC are included on purpose, to match with selectable CC in FP form
                for cc_id in self.search(cr, uid, [('category', '=', 'OC'), ('type', '!=', 'view')], order='code', context=context):
                    cc = self.browse(cr, uid, cc_id, context=context)
                    if fp.instance_id.id in [inst.id for inst in cc.cc_instance_ids]:
                        cc_list.append(cc)
            else:
                cc_list = fp.cost_center_ids or []
        return cc_list

    def get_acc_dest_linked_to_fp(self, cr, uid, fp_id, context=None):
        """
        Returns a tuple of all combinations of (account_id, destination_id) compatible with the FP in parameter:
        - if "Select Accounts Only" is ticked: the accounts selected and the Destinations compatible with them
        - else the Account/Destination combinations selected.

        Note: this method matches with what has been selected in the Accounts/Destinations tab of the FP form.
              It returns an empty list for PF.
        """
        if context is None:
            context = {}
        combinations = []
        fp = self.browse(cr, uid, fp_id,
                         fields_to_fetch=['category', 'select_accounts_only', 'fp_account_ids', 'tuple_destination_account_ids'],
                         context=context)
        if fp.category == 'FUNDING':
            if fp.select_accounts_only:
                for account in fp.fp_account_ids:
                    for dest in account.destination_ids:
                        combinations.append((account.id, dest.id))
            else:
                combinations = [(t.account_id.id, t.destination_id.id) for t in fp.tuple_destination_account_ids if not t.disabled]
        return combinations

    def button_cc_clear(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'cost_center_ids':[(6, 0, [])]}, context=context)
        return True

    def button_dest_cc_clear(self, cr, uid, ids, context=None):
        """
        Removes all Dest / CC combinations selected in the Cost Centers tab of the Destination form
        """
        if context is None:
            context = {}
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        for dest in self.browse(cr, uid, ids, fields_to_fetch=['dest_cc_link_ids'], context=context):
            dest_cc_link_ids = [dcl.id for dcl in dest.dest_cc_link_ids]
            if dest_cc_link_ids:
                dest_cc_link_obj.unlink(cr, uid, dest_cc_link_ids, context=context)
        return True

    def button_dest_clear(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'tuple_destination_account_ids':[(6, 0, [])]}, context=context)
        return True

    def button_fp_account_clear(self, cr, uid, ids, context=None):
        """
        Removes all G/L accounts selected in the Funding Pool view
        """
        self.write(cr, uid, ids, {'fp_account_ids': [(6, 0, [])]}, context=context)
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

    def open_multiple_cc_selection_wizard(self, cr, uid, ids, context=None):
        """
        Creates and displays a Multiple CC Selection Wizard linked to the current Destination
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        multiple_cc_wiz_obj = self.pool.get('multiple.cc.selection.wizard')
        if ids:
            dest_id = ids[0]
            # ensure that the dest. is in context even outside edition mode
            context.update({
                'current_destination_id': dest_id,
            })
            multiple_cc_wiz_id = multiple_cc_wiz_obj.create(cr, uid, {'dest_id': dest_id}, context=context)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'multiple.cc.selection.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [multiple_cc_wiz_id],
                'context': context,
            }
        return True


analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
