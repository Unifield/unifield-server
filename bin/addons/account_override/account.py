#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from account_override import ACCOUNT_RESTRICTED_AREA
from tools.translate import _
from time import strftime
import datetime
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc

class account_account(osv.osv):
    '''
        To create a activity period, 2 new fields are created, and are NOT linked to the
        'active' field, since the behaviors are too different.
    '''
    _name = "account.account"
    _inherit = "account.account"
    _trace = True

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        '''
        If date out of date_start/date of given account, then account is inactive.
        The comparison could be done via a date given in context.
        '''
        res = {}
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for a in self.browse(cr, uid, ids, fields_to_fetch=['activation_date', 'inactivation_date']):
            res[a.id] = True
            if a.activation_date > cmp_date:
                res[a.id] = False
            if a.inactivation_date and a.inactivation_date <= cmp_date:
                res[a.id] = False
        return res

    def _search_filter_active(self, cr, uid, ids, name, args, context=None):
        """
        Add the search on active/inactive account
        """
        arg = []
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for x in args:
            if x[0] == 'filter_active' and x[2] == True:
                arg.append('&')
                arg.append(('activation_date', '<=', cmp_date))
                arg.append('|')
                arg.append(('inactivation_date', '>', cmp_date))
                arg.append(('inactivation_date', '=', False))
            elif x[0] == 'filter_active' and x[2] == False:
                arg.append('|')
                arg.append(('activation_date', '>', cmp_date))
                arg.append(('inactivation_date', '<=', cmp_date))
        return arg

    def __compute(self, cr, uid, ids, field_names, arg=None, context=None,
                  query='', query_params=()):
        """ compute the balance, debit and/or credit for the provided
        account ids
        Arguments:
        `ids`: account ids
        `field_names`: the fields to compute (a list of any of
                       'balance', 'debit' and 'credit')
        `arg`: unused fields.function stuff
        `query`: additional query filter (as a string)
        `query_params`: parameters for the provided query string
                        (__compute will handle their escaping) as a
                        tuple
        """
        mapping = {
            'balance': "COALESCE(SUM(l.debit),0) " \
                       "- COALESCE(SUM(l.credit), 0) as balance",
            'debit': "COALESCE(SUM(l.debit), 0) as debit",
            'credit': "COALESCE(SUM(l.credit), 0) as credit"
        }
        #get all the necessary accounts
        children_and_consolidated = self._get_children_and_consol(cr, uid, ids,
                                                                  context=context)
        #compute for each account the balance/debit/credit from the move lines
        accounts = {}
        sums = {}
        query_params = []
        # Add some query/query_params regarding context
        link = " "
        if context.get('currency_id', False):
            if query:
                link = " AND "
            query += link + 'currency_id = %s'
            query_params.append(tuple([context.get('currency_id')]))
        link = " "
        if context.get('instance_ids', False):
            if query:
                link = " AND "
            instance_ids = context.get('instance_ids')
            if isinstance(instance_ids, (int, long)):
                instance_ids = [instance_ids]
            if len(instance_ids) == 1:
                query += link + 'l.instance_id = %s'
            else:
                query += link + 'l.instance_id in %s'
            query_params.append(tuple(instance_ids))
        # Do normal process
        if children_and_consolidated:
            aml_query = self.pool.get('account.move.line')._query_get(cr, uid, context=context)

            wheres = [""]
            if query.strip():
                wheres.append(query.strip())
            if aml_query.strip():
                wheres.append(aml_query.strip())
            filters = " AND ".join(wheres)
            # target_move from chart of account wizard
            filters = filters.replace("AND l.state <> 'draft'", '')
            prefilters = " "
            possible_states = [x[0] for x in self.pool.get('account.move')._columns['state'].selection]
            if context.get('move_state', False) and context['move_state'] in possible_states:
                prefilters += "AND l.move_id = m.id AND m.state = '%s'" % context.get('move_state')
            else:
                prefilters += "AND l.move_id = m.id AND m.state in ('posted', 'draft')"
            # Notifications
            self.logger.notifyChannel('account_override.'+self._name, netsvc.LOG_DEBUG,
                                      'Filters: %s'%filters)
            # IN might not work ideally in case there are too many
            # children_and_consolidated, in that case join on a
            # values() e.g.:
            # SELECT l.account_id as id FROM account_move_line l
            # INNER JOIN (VALUES (id1), (id2), (id3), ...) AS tmp (id)
            # ON l.account_id = tmp.id
            # or make _get_children_and_consol return a query and join on that
            request = """SELECT l.account_id as id, %s
                       FROM account_move_line l, account_move m
                       WHERE l.account_id IN %%s %s
                       GROUP BY l.account_id""" % (', '.join(map(mapping.__getitem__, field_names)), prefilters + filters)  # not_a_user_entry
            params = [tuple(children_and_consolidated)]
            if query_params:
                for qp in query_params:
                    params.append(qp)
            cr.execute(request, params)
            self.logger.notifyChannel('account_override.'+self._name, netsvc.LOG_DEBUG,
                                      'Status: %s'%cr.statusmessage)

            for res in cr.dictfetchall():
                accounts[res['id']] = res

            # consolidate accounts with direct children
            children_and_consolidated.reverse()
            brs = list(self.browse(cr, uid, children_and_consolidated, context=context))
            currency_obj = self.pool.get('res.currency')
            display_only_checked_account = context.get('display_only_checked_account', False)
            while brs:
                current = brs[0]
                brs.pop(0)
                for fn in field_names:
                    sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)
                    for child in current.child_id:
                        # in context of report, if the current account is not
                        # displayed, it should no impact the total amount
                        if display_only_checked_account and not child.display_in_reports:
                            continue
                        if child.company_id.currency_id.id == current.company_id.currency_id.id:
                            sums[current.id][fn] += sums[child.id][fn]
                        else:
                            sums[current.id][fn] += currency_obj.compute(cr, uid, child.company_id.currency_id.id, current.company_id.currency_id.id, sums[child.id][fn], context=context)
        res = {}
        null_result = dict((fn, 0.0) for fn in field_names)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        for i in ids:
            res[i] = sums.get(i, null_result)
            # If output_currency_id in context, we change computation
            for f_name in ('debit', 'credit', 'balance'):
                if context.get('output_currency_id', False) and res[i].get(f_name, False):
                    new_amount = currency_obj.compute(cr, uid, context.get('output_currency_id'), company_currency, res[i].get(f_name), context=context)
                    res[i][f_name] = new_amount
        return res

    def _get_restricted_area(self, cr, uid, ids, field_name, args, context=None):
        """
        FAKE METHOD
        """
        # Check
        if context is None:
            context = {}
        res = {}
        for account_id in ids:
            res[account_id] = True
        return res

    def _search_restricted_area(self, cr, uid, ids, name, args, context=None):
        """
        Search the right domain to apply to this account filter.
        For this, it uses the "ACCOUNT_RESTRICTED_AREA" variable in which we list all well-known cases.
        The key args is "restricted_area", the param is like "register_lines".
        In ACCOUNT_RESTRICTED_AREA, we use the param as key. It so return the domain to apply.
        If no domain, return an empty domain.
        """
        # Check
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] == 'restricted_area' and x[2]:
                if x[2] in ACCOUNT_RESTRICTED_AREA:
                    for subdomain in ACCOUNT_RESTRICTED_AREA[x[2]]:
                        arg.append(subdomain)
            elif x[0] != 'restricted_area':
                arg.append(x)
            else:
                raise osv.except_osv(_('Error'), _('Operation not implemented!'))

        context_ivo = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'intermission' and \
            context.get('is_intermission', False) and context.get('intermission_type', False) == 'out'
        context_ivi = context.get('type', False) == 'in_invoice' and context.get('journal_type', False) == 'intermission' and \
            context.get('is_intermission', False) and context.get('intermission_type', False) == 'in'
        context_stv = context.get('type', False) == 'out_invoice' and context.get('journal_type', False) == 'sale' and \
            not context.get('is_debit_note', False)

        if args == [('restricted_area', '=', 'invoice_lines')]:
            # LINES of Stock Transfer Vouchers:
            # restrict to Expense/Income/Receivable accounts
            if context_stv or context.get('check_line_stv'):
                arg.append(('user_type_code', 'in', ['expense', 'income', 'receivables']))
        elif args == [('restricted_area', '=', 'intermission_header')]:
            if context_ivo or context.get('check_header_ivo'):
                # HEADER of Intermission Voucher OUT:
                # restrict to 'is_intermission_counterpart', or Regular/Cash or Income, or Receivable/Receivables or Cash,
                # or Payable/Payables (for refund UC)
                # + prevent from using donation accounts
                arg = [
                    ('type_for_register', 'not in', ['donation', 'advance', 'transfer', 'transfer_same']),
                    '|', '|', '|', ('is_intermission_counterpart', '=', True),
                    '&', ('type', '=', 'other'), ('user_type_code', 'in', ['cash', 'income']),
                    '&', ('type', '=', 'receivable'), ('user_type_code', 'in', ['receivables', 'cash']),
                    '&', ('user_type_code', '=', 'payables'), ('type', '=', 'payable')
                ]
            elif context_ivi or context.get('check_header_ivi'):
                # HEADER of Intermission Voucher IN:
                # restrict to 'is_intermission_counterpart' or Regular/Cash or Regular/Income or Payable/Payables
                # or Receivable/Receivables or Cash (for refund UC)
                # + prevent from using donation accounts
                arg = [
                    ('type_for_register', 'not in', ['donation', 'advance', 'transfer', 'transfer_same']),
                    '|', '|', '|', ('is_intermission_counterpart', '=', True),
                    '&', ('type', '=', 'other'), ('user_type_code', 'in', ['cash', 'income']),
                    '&', ('user_type_code', '=', 'payables'), ('type', '=', 'payable'),
                    '&', ('type', '=', 'receivable'), ('user_type_code', 'in', ['receivables', 'cash']),
                ]
        return arg

    def _get_fake_cash_domain(self, cr, uid, ids, field_name, arg, context=None):
        """
        Fake method for domain
        """
        if context is None:
            context = {}
        res = {}
        for cd_id in ids:
            res[cd_id] = True
        return res

    def _search_cash_domain(self, cr, uid, ids, field_names, args, context=None):
        """
        Return a given domain (defined in ACCOUNT_RESTRICTED_AREA variable)
        """
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] and x[1] == '=' and x[2]:
                if x[2] in ['cash', 'bank', 'cheque']:
                    arg.append(('restricted_area', '=', 'journals'))
            else:
                raise osv.except_osv(_('Error'), _('Operation not implemented!'))
        return arg

    def _get_is_specific_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        If this account is the same as default intermission counterpart OR rebilling intersection account, then return True. Otherwise return nothing.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        account = False
        if field_names == 'is_intermission_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
        elif field_names == 'is_intersection_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.import_invoice_default_account
        specific_account_id = account and account.id or False

        for account_id in ids:
            res[account_id] = False
        if specific_account_id in ids:
            res[specific_account_id] = True
        return res

    def _search_is_specific_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        Return the intermission counterpart OR the rebilling intersection account ID.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        arg = []
        account = False
        if field_names == 'is_intermission_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
        elif field_names == 'is_intersection_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.import_invoice_default_account
        specific_account_id = account and account.id or False

        for x in args:
            if x[0] == field_names and x[2] is True:
                if specific_account_id:
                    arg.append(('id', '=', specific_account_id))
            elif x[0] == field_names and x[2] is False:
                if specific_account_id:
                    arg.append(('id', '!=', specific_account_id))
            elif x[0] != field_names:
                arg.append(x)
            else:
                raise osv.except_osv(_('Error'), _('Filter on field %s not implemented! %s') % (field_names, x,))
        return arg

    def _get_inactivated_for_dest(self, cr, uid, ids, field_name, args, context=None):
        '''
        Is this account inactive for the destination given in context
        '''
        ret = {}
        for id in ids:
            ret[id] = False
        if context and context.get('destination_id'):
            link_obj = self.pool.get('account.destination.link')
            inactive_link_ids = link_obj.search(cr, uid, [('disabled', '=', True), ('destination_id', '=', context.get('destination_id')),
                                                          ('account_id', 'in', ids)], context=context)
            if inactive_link_ids:
                for link in link_obj.read(cr, uid, inactive_link_ids, ['account_id'], context=context):
                    ret[link['account_id'][0]] = True
        return ret

    def _get_selected_in_fp(self, cr, uid, account_ids, name=False, args=False, context=None):
        """
        Returns True for the G/L accounts already selected in the Funding Pool:
        they will be displayed in grey in the list and won't be re-selectable.
        """
        if context is None:
            context = {}
        if isinstance(account_ids, (int, long)):
            account_ids = [account_ids]
        selected = []
        acc = context.get('accounts_selected')
        if acc and isinstance(acc, list) and len(acc) == 1 and len(acc[0]) == 3:
            selected = acc[0][2]
        res = {}
        for account_id in account_ids:
            res[account_id] = account_id in selected
        return res

    def _get_false(self, cr, uid, ids, *a, **b):
        """
        Returns False for all ids
        """
        return {}.fromkeys(ids, False)

    def _search_selectable_in_contract(self, cr, uid, ids, field_name, arg, context=None):
        """
        Returns a domain with the G/L accounts selectable in the contract in context.
        The accounts must appear either in the G/L accounts or in the Account/Destination combinations linked to the
        Funding Pools selected in the contract.
        """
        if context is None:
            context = {}
        acc_ids = set()
        if context.get('contract_id'):
            cr.execute('''
                select
                    distinct(rel.account_id)
                from
                    financing_contract_funding_pool_line fpl,
                    financing_contract_contract contract,
                    account_analytic_account fp,
                    fp_account_rel rel
                where
                    contract.id = %s and
                    fpl.contract_id = contract.format_id and
                    fp.id = fpl.funding_pool_id and
                    fp.select_accounts_only = 't' and
                    rel.fp_id = fp.id
                ''', (context['contract_id'], ))
            acc_ids.update([x[0] for x in cr.fetchall()])

            cr.execute('''
                select
                    distinct(lnk.account_id)
                from
                    financing_contract_funding_pool_line fpl,
                    financing_contract_contract contract,
                    account_analytic_account fp,
                    account_destination_link lnk,
                    funding_pool_associated_destinations rel
                where
                    contract.id = %s and
                    fpl.contract_id = contract.format_id and
                    fp.id = fpl.funding_pool_id and
                    fp.select_accounts_only = 'f' and
                    rel.funding_pool_id = fp.id and
                    rel.tuple_id = lnk.id
                ''', (context['contract_id'], ))
            acc_ids.update([x[0] for x in cr.fetchall()])

        return [('id', 'in', list(acc_ids))]

    def _get_selected_in_contract(self, cr, uid, account_ids, name=False, args=False, context=None):
        """
        Returns True for the G/L accounts already selected in the contract or donor in context:
        they will be displayed in grey in the list and won't be re-selectable.

        As soon as an account has been selected in either G/L accounts only, acc/dest combinaisons, or quadruplets,
        it is seen as already used.
        """
        if context is None:
            context = {}
        if isinstance(account_ids, (int, long)):
            account_ids = [account_ids]
        res = {}
        selected = {}
        current_obj = current_id = False
        if context.get('contract_id'):
            current_obj = self.pool.get('financing.contract.contract')
            current_id = context['contract_id']
        elif context.get('donor_id'):
            current_obj = self.pool.get('financing.contract.donor')
            current_id = context['donor_id']
        if current_obj and current_id:
            active_id = context.get('active_id', False)
            for line in current_obj.browse(cr, uid, current_id, fields_to_fetch=['actual_line_ids'], context=context).actual_line_ids:
                if not active_id or line.id != active_id:  # skip the current reporting line
                    for account_destination in line.account_destination_ids:
                        selected[account_destination.account_id.id] = True
                    for account_quadruplet in line.account_quadruplet_ids:
                        selected[account_quadruplet.account_id.id] = True
                    for account in line.reporting_account_ids:
                        selected[account.id] = True
        for account_id in account_ids:
            res[account_id] = account_id in selected
        return res

    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True, translate=True),
        'activation_date': fields.date('Active from', required=True),
        'inactivation_date': fields.date('Inactive from'),
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Internal Transfer'), ('transfer_same','Internal Transfer (same currency)'),
                                               ('advance', 'Operational Advance'), ('payroll', 'Third party required - Payroll'), ('down_payment', 'Down payment'), ('donation', 'Donation'), ('disregard_rec', 'Reconciliation - Disregard 3rd party')], string="Type for specific treatment", required=True,
                                              help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register
            when he add a new register line.
            You can also make an account to accept reconciliation even if the 3RD party is not the same.
            """),
        'shrink_entries_for_hq': fields.boolean("Shrink entries for HQ export", help="Check this attribute if you want to consolidate entries on this account before they are exported to the HQ system."),
        'filter_active': fields.function(_get_active, fnct_search=_search_filter_active, type="boolean", method=True, store=False, string="Show only active accounts",),
        'restricted_area': fields.function(_get_restricted_area, fnct_search=_search_restricted_area, type='boolean', method=True, string="Is this account allowed?"),
        'cash_domain': fields.function(_get_fake_cash_domain, fnct_search=_search_cash_domain, method=True, type='boolean', string="Domain used to search account in journals", help="This is only to change domain in journal's creation."),
        'balance': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Balance', multi='balance'),
        'debit': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Debit', multi='balance'),
        'credit': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Credit', multi='balance'),
        'is_intermission_counterpart': fields.function(_get_is_specific_counterpart, fnct_search=_search_is_specific_counterpart, method=True, type='boolean', string='Is the intermission counterpart account?'),
        'is_intersection_counterpart': fields.function(_get_is_specific_counterpart, fnct_search=_search_is_specific_counterpart, method=True, type='boolean', string='Is the intersection counterpart account?'),
        'display_in_reports': fields.boolean("Display in P&L and B/S reports",
                                             help="Uncheck this attribute if you want an account not to appear"
                                             " in the 'Profit And Loss' and 'Balance Sheet' reports. This is "
                                             "feasible only on level 1 accounts. When an account is "
                                             "check/unchecked the behaviour will apply for all his children."),
        # US-672/1
        'has_partner_type_internal': fields.boolean('Internal'),
        'has_partner_type_section': fields.boolean('Inter-section'),
        'has_partner_type_external': fields.boolean('External'),
        'has_partner_type_esc': fields.boolean('ESC'),
        'has_partner_type_intermission': fields.boolean('Intermission'),
        'has_partner_type_local': fields.boolean('Employee Local'),  # NAT employee
        'has_partner_type_ex': fields.boolean('Employee Expat'),  # Expat
        'has_partner_type_book': fields.boolean('Journal'),  # transfer journal
        'has_partner_type_empty': fields.boolean('Empty'),  # US-1307 empty

        'inactivated_for_dest': fields.function(_get_inactivated_for_dest, method=True, type='boolean', string='Is inactive for destination given in context'),

        'selected_in_fp': fields.function(_get_selected_in_fp, string='Selected in Funding Pool', method=True, store=False, type='boolean'),
        # G/L acc. which CAN BE selected in the Financing Contract:
        'selectable_in_contract': fields.function(_get_false, string='Selectable in Contract', method=True, store=False,
                                                  type='boolean', fnct_search=_search_selectable_in_contract),
        # G/L acc. which ARE currently selected in the Financing Contract or Donor:
        'selected_in_contract': fields.function(_get_selected_in_contract, string='Selected in Contract or Donor', method=True,
                                                store=False, type='boolean'),
    }

    _defaults = {
        # US-8607 : set default activation_date to first day of current month
        'activation_date': lambda *a: (datetime.datetime.today().replace(day=1)).strftime('%Y-%m-%d'),
        'type_for_register': lambda *a: 'none',
        'shrink_entries_for_hq': lambda *a: True,
        'display_in_reports': lambda *a: True,
        # US-672/1: allow all partner types by default:
        # => master data retro-compat before ticket
        'has_partner_type_internal': True,
        'has_partner_type_section': True,
        'has_partner_type_external': True,
        'has_partner_type_esc': True,
        'has_partner_type_intermission': True,
        'has_partner_type_local': True,
        'has_partner_type_ex': True,
        'has_partner_type_book': True,
        'has_partner_type_empty': True,
    }

    # UTP-493: Add a dash between code and account name
    def name_get(self, cr, uid, ids, context=None):
        """
        Use "-" instead of " " between name and code for account's default name
        """
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'code'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['code']:
                if context.get('account_only_code'):
                    name = record['code']
                else:
                    name = record['code'] + ' - '+name
            res.append((record['id'], name))
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
            FROM account_account
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

    def _check_date(self, vals):
        if 'inactivation_date' in vals and vals['inactivation_date'] is not False \
                and 'activation_date' in vals and not vals['activation_date'] < vals['inactivation_date']:
                # validate that activation date
            raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))

    def _check_allowed_partner_type(self, vals):
        '''
        Check that at least one partner type has been allowed. If not, raise a warning.
        '''
        if 'has_partner_type_internal' in vals and not vals['has_partner_type_internal'] and \
                'has_partner_type_external' in vals and not vals['has_partner_type_external'] and \
                'has_partner_type_esc' in vals and not vals['has_partner_type_esc'] and \
                'has_partner_type_local' in vals and not vals['has_partner_type_local'] and \
                'has_partner_type_ex' in vals and not vals['has_partner_type_ex'] and \
                'has_partner_type_empty' in vals and not vals['has_partner_type_empty'] and \
                'has_partner_type_book' in vals and not vals['has_partner_type_book'] and \
                'has_partner_type_intermission' in vals and not vals['has_partner_type_intermission'] and \
                'has_partner_type_section' in vals and not vals['has_partner_type_section']:
            raise osv.except_osv(_('Warning !'), _('At least one Allowed Partner type must be selected.'))

    def _check_reconcile_status(self, cr, uid, account_id, context=None):
        """
        Prevents an account:
        - from being set as reconcilable if it is included in the yearly move to 0
        - from NOT being set as reconcilable if it is included in revaluation (except for liquidity accounts)
        """
        if context is None:
            context = {}
        if account_id:
            account_fields = ['reconcile', 'include_in_yearly_move', 'currency_revaluation', 'type']
            account = self.browse(cr, uid, account_id, fields_to_fetch=account_fields, context=context)
            reconcile = account.reconcile
            include_in_yearly_move = account.include_in_yearly_move
            currency_revaluation = account.currency_revaluation
            is_liquidity = account.type == 'liquidity'
            if reconcile and include_in_yearly_move:
                raise osv.except_osv(_('Warning !'),
                                     _("An account can't be both reconcilable and included in the yearly move to 0."))
            elif not reconcile and currency_revaluation and not is_liquidity:
                raise osv.except_osv(_('Warning !'),
                                     _('An account set as "Included in revaluation" must be set as "Reconcile".'))

    def _set_prevent_multi_curr_rec(self, vals):
        """
        Updates vals to set prevent_multi_curr_rec to False when "reconcile" is False.
        Cf: when "reconcile" is unticked, prevent_multi_curr_rec is in readonly so its value (False in that case) is ignored
        """
        if 'reconcile' in vals and not vals['reconcile'] and 'prevent_multi_curr_rec' not in vals:
            vals['prevent_multi_curr_rec'] = False

    def _check_existing_entries(self, cr, uid, account_id, context=None):
        """
        Displays a message visible on top of the page in case some JI booked on the account_id have a posting date
        outside the account activation time interval
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        if account_id and not context.get('sync_update_execution'):
            account_fields = ['activation_date', 'inactivation_date', 'code', 'name']
            account = self.browse(cr, uid, account_id, fields_to_fetch=account_fields, context=context)
            aml_dom = [('account_id', '=', account_id), '|', ('date', '<', account.activation_date), ('date', '>=', account.inactivation_date)]
            if aml_obj.search_exist(cr, uid, aml_dom, context=context):
                self.log(cr, uid, account_id, _('At least one Journal Item using the Account "%s - %s" has a Posting Date '
                                                'outside the activation dates selected.') % (account.code, account.name))

    def create(self, cr, uid, vals, context=None):
        self._set_prevent_multi_curr_rec(vals)  # update vals
        self._check_date(vals)
        self._check_allowed_partner_type(vals)
        account_id = super(account_account, self).create(cr, uid, vals, context=context)
        self._check_reconcile_status(cr, uid, account_id, context=context)
        return account_id

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        self._set_prevent_multi_curr_rec(vals)  # update vals
        self._check_date(vals)
        self._check_allowed_partner_type(vals)
        # remove user_type from vals if it hasn't been modified to avoid the recomputation on JI Account Type (due to store feature)
        res = True
        for acc in self.browse(cr, uid, ids, fields_to_fetch=['user_type'], context=context):
            newvals = vals.copy()
            if newvals.get('user_type') and newvals['user_type'] == acc.user_type.id:
                del newvals['user_type']
            res = res and super(account_account, self).write(cr, uid, [acc.id], newvals, context=context)
        for account_id in ids:
            self._check_reconcile_status(cr, uid, account_id, context=context)
            self._check_existing_entries(cr, uid, account_id, context=context)
        return res

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Filtering regarding context
        """
        if not context:
            context = {}
        if context.get('filter_inactive_accounts'):
            args_append = args.append
            args_append(('activation_date', '<=', datetime.date.today().strftime('%Y-%m-%d')))
            args_append('|')
            args_append(('inactivation_date', '>', datetime.date.today().strftime('%Y-%m-%d')))
            args_append(('inactivation_date', '=', False))
        return super(account_account, self).search(cr, uid, args, offset,
                                                   limit, order, context=context, count=count)

    def _get_allowed_partner_field(self, cr, uid, partner_type=False, partner_txt=False, employee_id=False,
                                   transfer_journal_id=False, partner_id=False, from_vals=False, context=None):
        '''
        Get the "Allowed Partner type" field to check (for the model account.account)
        :return: a String containing the field to check (for instance "has_partner_type_intermission"), or False
        '''
        if 'allowed_partner_field' in context:
            allowed_partner_field = context['allowed_partner_field']
        else:
            allowed_partner_field = False
            should_have_field_suffix = False
            if not partner_type and not partner_txt and not employee_id and not transfer_journal_id and not partner_id:
                # empty partner
                should_have_field_suffix = 'empty'
            else:
                # existing partner
                emp_obj = self.pool.get('hr.employee')
                partner_obj = self.pool.get('res.partner')
                journal_obj = self.pool.get('account.journal')
                if partner_type:
                    pt_model, pt_id = tuple(partner_type.split(',')) if from_vals \
                        else (partner_type._name, partner_type.id, )
                    if from_vals:
                        pt_id = int(pt_id)
                    employee_id = transfer_journal_id = partner_id = False
                    if pt_model == 'hr.employee':
                        employee_id = pt_id
                    elif pt_model == 'account.journal':
                        transfer_journal_id = pt_id
                    elif pt_model == 'res.partner':
                        partner_id = pt_id
                elif partner_txt:
                    employee_ids = emp_obj.search(cr, uid, [('name', '=', partner_txt)], limit=1, context=context)
                    if employee_ids:
                        employee_id = employee_ids[0]
                    else:
                        partner_ids = partner_obj.search(cr, uid, [('name', '=', partner_txt), ('active', 'in', ['t', 'f'])],
                                                         limit=1, context=context)
                        if partner_ids:
                            partner_id = partner_ids[0]
                        else:
                            transfer_journal_ids = journal_obj.search(cr, uid, [('code', '=', partner_txt)], limit=1, context=context)
                            if transfer_journal_ids:
                                transfer_journal_id = transfer_journal_ids[0]
                if employee_id:
                    tp_rec = emp_obj.browse(cr, uid, employee_id, fields_to_fetch=['employee_type'], context=context)
                    # note: allowed for employees with no type
                    should_have_field_suffix = tp_rec.employee_type or False
                elif transfer_journal_id:
                    should_have_field_suffix = 'book'
                elif partner_id:
                    tp_rec = partner_obj.browse(cr, uid, partner_id, fields_to_fetch=['partner_type'], context=context)
                    should_have_field_suffix = tp_rec.partner_type or False
            if should_have_field_suffix:
                allowed_partner_field = 'has_partner_type_%s' % (should_have_field_suffix,)
            # store the returned value in context in order not to do the same check several times
            context.update({'allowed_partner_field': allowed_partner_field})
        return allowed_partner_field

    def _display_account_partner_compatibility_error(self, cr, uid, not_compatible_ids,
                                                     context=None, type_for_specific_treatment=False):
        """
        Raises an error with the list of the accounts which are incompatible with the partner used
        """
        if context is None:
            context = {}
        error_msg = ''
        acc_obj = self.pool.get('account.account')
        if not_compatible_ids:
            errors = [_('following accounts are not compatible with partner:')]
            for acc in acc_obj.browse(cr, uid, not_compatible_ids, fields_to_fetch=['code', 'name'], context=context):
                errors.append(_('%s - %s') % (acc.code, acc.name))
                error_msg = "\n- ".join(errors)
                if type_for_specific_treatment:
                    error_msg += '%s%s' % ('\n\n', _('Please check the Type for specific treatment of the accounts used.'))
            raise osv.except_osv(_('Error'), error_msg)

    def check_type_for_specific_treatment(self, cr, uid, account_ids, partner_id=False, employee_id=False,
                                          journal_id=False, partner_txt=False, currency_id=False, context=None):
        """
        Checks if the Third parties and accounts in parameter are compatible regarding the "Type for specific treatment"
        of the accounts (raises an error if not).
        Note that the currency_id is the one of the entry to be checked and is used ONLY for the checks on
        transfer journals (if a currency is given).
        """
        if isinstance(account_ids, (int, long)):
            account_ids = [account_ids]
        if context is None:
            context = {}
        acc_obj = self.pool.get('account.account')
        employee_obj = self.pool.get('hr.employee')
        partner_obj = self.pool.get('res.partner')
        journal_obj = self.pool.get('account.journal')
        not_compatible_ids = []
        for acc_id in acc_obj.browse(cr, uid, account_ids, fields_to_fetch=['type_for_register'], context=context):
            # get the right Third Party if a partner_txt only has been given
            if partner_txt and not partner_id and not employee_id and not journal_id:
                employee_ids = employee_obj.search(cr, uid, [('name', '=', partner_txt)], limit=1, context=context)
                if employee_ids:
                    employee_id = employee_ids[0]
                else:
                    partner_ids = partner_obj.search(cr, uid, [('name', '=', partner_txt), ('active', 'in', ['t', 'f'])],
                                                     limit=1, context=context)
                    if partner_ids:
                        partner_id = partner_ids[0]
                    else:
                        journal_ids = journal_obj.search(cr, uid, [('code', '=', partner_txt)], limit=1, context=context)
                        if journal_ids:
                            journal_id = journal_ids[0]
                # if there is a partner_txt but no related Third Party found:
                # ignore the check if "ignore_non_existing_tp" is in context (e.g. when validating HQ entries)
                if not partner_id and not employee_id and not journal_id and context.get('ignore_non_existing_tp', False):
                    continue
            acc_type = acc_id.type_for_register
            advance_not_ok = acc_type == 'advance' and (not employee_id or journal_id or partner_id)
            dp_not_ok = acc_type == 'down_payment' and (not partner_id or journal_id or employee_id)
            payroll_not_ok = acc_type == 'payroll' and ((not partner_id and not employee_id) or journal_id)
            transfer_not_ok = acc_type in ['transfer', 'transfer_same'] and (not journal_id or partner_id or employee_id)
            if currency_id and journal_id and not transfer_not_ok:
                # check the journal type and currency
                journal = journal_obj.browse(cr, uid, journal_id, fields_to_fetch=['type', 'currency'], context=context)
                is_liquidity = journal and journal.type in ['cash', 'bank', 'cheque'] and journal.currency
                if acc_type == 'transfer_same' and (not is_liquidity or journal.currency.id != currency_id):
                    transfer_not_ok = True
                elif acc_type == 'transfer' and (not is_liquidity or journal.currency.id == currency_id):
                    transfer_not_ok = True
            if advance_not_ok or dp_not_ok or payroll_not_ok or transfer_not_ok:
                not_compatible_ids.append(acc_id.id)
        if not_compatible_ids:
            self._display_account_partner_compatibility_error(cr, uid, not_compatible_ids, context, type_for_specific_treatment=True)

    def is_allowed_for_thirdparty(self, cr, uid, ids, partner_type=False, partner_txt=False, employee_id=False,
                                  transfer_journal_id=False, partner_id=False, from_vals=False, raise_it=False, context=None):
        """
        US-672/2 is allowed regarding to thirdparty
        partner_type then partner_txt fields prevails on
        employee_id/transfer_journal_id/partner_id
        :type partner_type: 'model_name,id' if from_vals
            else object with model in obj._name and id in obj.id
        :type partner_type: object/str
        :param from_vals: True if values are from 'vals'
        :param raise_it: True to raise not compatible accounts
        :return: {id: True/False, }
        :rtype: dict
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        res = {}
        fields_to_fetch = ['type_for_register', 'has_partner_type_internal', 'has_partner_type_external', 'has_partner_type_esc',
                           'has_partner_type_local', 'has_partner_type_ex', 'has_partner_type_empty', 'has_partner_type_book',
                           'has_partner_type_intermission', 'has_partner_type_section']
        # browse the accounts and check if the third party is compatible
        for r in self.browse(cr, uid, ids, fields_to_fetch=fields_to_fetch, context=context):
            # US-1307 If the account has a "Type for specific Treatment": bypass the check on "Allowed Partner type"
            type_for_specific_treatment = hasattr(r, 'type_for_register') and getattr(r, 'type_for_register') != 'none' or False
            if type_for_specific_treatment:
                res[r.id] = True
            else:
                allowed_partner_field = self._get_allowed_partner_field(cr, uid, partner_type, partner_txt, employee_id,
                                                                        transfer_journal_id, partner_id, from_vals, context)
                if not allowed_partner_field:
                    res[r.id] = True  # allowed with no specific field (e.g. don't block validation of HQ entries with non-existing 3d Party)
                else:
                    res[r.id] = hasattr(r, allowed_partner_field) and getattr(r, allowed_partner_field) or False
        # once the checks are done, remove allowed_partner_field from context so as not to reuse it for another record
        if 'allowed_partner_field' in context:
            del context['allowed_partner_field']
        if raise_it:
            not_compatible_ids = [ id for id in res if not res[id] ]
            if not_compatible_ids:
                self._display_account_partner_compatibility_error(cr, uid, not_compatible_ids, context)
        return res

    def activate_destination(self, cr, uid, ids, context=None):
        if not context or not context.get('destination_id'):
            raise osv.except_osv(_('Error'), _('Activate destination: missing account in context'))

        link = self.pool.get('account.destination.link')
        link_ids = link.search(cr, uid,
                               [('account_id', 'in', ids), ('destination_id', '=', context.get('destination_id')), ('disabled', '=', True)],
                               context=context)
        if link_ids:
            link.write(cr, uid, link_ids, {'disabled': False}, context=context)
        return True

account_account()


class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    # @@@override account>account.py>account_journal>create_sequence
    def create_sequence(self, cr, uid, vals, context=None):
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = vals['name']
        code = vals['code'].lower()

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': '',
            'padding': 4,
            'number_increment': 1
        }
        return seq_pool.create(cr, uid, seq)

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _search_instance_filter(self, cr, uid, obj, name, args, context=None):
        # journals instance filter: let all default journals,
        # except specific cases
        res = False
        if not args:
            return res
        if len(args) != 1 or len(args[0]) != 3 or \
                args[0][0] != 'instance_filter' or args[0][1] != '=':
            raise osv.except_osv(_('Error'), 'invalid arguments')

        is_manual_view = context and context.get('from_manual_entry', False)
        if is_manual_view:
            self_instance = self.pool.get('res.users').browse(cr, uid, [uid],
                                                              context=context)[0].company_id.instance_id
            if self_instance:
                if self_instance.level:
                    if self_instance.level == 'coordo':
                        # BKLG-19/7: forbid creation of MANUAL journal entries
                        # from COORDO on a PROJECT journal
                        msf_instance_obj = self.pool.get('msf.instance')
                        forbid_instance_ids = msf_instance_obj.search(cr, uid,
                                                                      [('level', '=', 'project')], context=context)
                        if forbid_instance_ids:
                            return [('instance_id', 'not in', forbid_instance_ids)]
                    elif self_instance.level == 'project':
                        # US-896: project should only see project journals
                        # (coordo register journals sync down to project for
                        #  example)
                        return [('is_current_instance', '=', True)]
        return res

    _columns = {
        # BKLG-19/7: journals instance filter
        'instance_filter': fields.function(
            _get_fake, fnct_search=_search_instance_filter,
            method=True, type='boolean', string='Instance filter'
        ),
    }

account_journal()

class account_move(osv.osv):
    _inherit = 'account.move'

    def _journal_type_get(self, cr, uid, context=None):
        """
        Get journal types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context)

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True, select=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id',
                                               string="Statement lines", help="This field give all statement lines linked to this move."),
        'ref': fields.char('Reference', size=64, readonly=True, states={'draft':[('readonly',False)]}),
        'status': fields.selection([('sys', 'system'), ('manu', 'manual')], string="Status", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True,
                                     states={'posted':[('readonly',True)]},
                                     domain="[('state', '=', 'draft')]", hide_default_menu=True),
        'journal_id': fields.many2one('account.journal', 'Journal',
                                      required=True, states={'posted':[('readonly',True)]},
                                      domain="[('type', 'not in', "
                                             " ['accrual', 'hq', 'inkind', 'cur_adj', 'system', 'extra', 'correction', 'correction_hq', 'revaluation']),"
                                             "('code', '!=', 'ISI'), "
                                             "('is_active', '=', True), "
                                             "('instance_filter', '=', True)]",
                                      hide_default_menu=True),
        'document_date': fields.date('Document Date', size=255, required=True, help="Used for manual journal entries"),
        'journal_type': fields.related('journal_id', 'type', type='selection', selection=_journal_type_get, string="Journal Type", \
                                       help="This indicates which Journal Type is attached to this Journal Entry", write_relate=False),
        'sequence_id': fields.many2one('ir.sequence', string='Lines Sequence', ondelete='cascade',
                                       help="This field contains the information related to the numbering of the lines of this journal entry."),
        'manual_name': fields.char('Description', size=64, required=True),
        'imported': fields.boolean('Imported', help="Is this Journal Entry imported?", required=False, readonly=True),
        'register_line_id': fields.many2one('account.bank.statement.line', required=False, readonly=True),
        'posted_sync_sequence': fields.integer('Seq. number of sync update that posted the move', readonly=True, internal=True),
    }

    _defaults = {
        'status': lambda self, cr, uid, c: c.get('from_web_menu', False) and 'manu' or 'sys',
        'document_date': lambda *a: False,
        'date': lambda *a: False,
        'period_id': lambda *a: '',
        'manual_name': lambda *a: '',
        'imported': lambda *a: False,
    }

    def _check_document_date(self, cr, uid, ids, context=None):
        """
        Check that document's date is done BEFORE posting date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                self.pool.get('finance.tools').check_document_date(cr, uid,
                                                                   m.document_date, m.date, context=context)
        return True

    def _check_date_in_period(self, cr, uid, ids, context=None):
        """
        Check that date is inside defined period
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.date and m.period_id and m.period_id.date_start and m.date >= m.period_id.date_start and m.period_id.date_stop and m.date <= m.period_id.date_stop:
                    continue
                raise osv.except_osv(_('Error'), _('Posting date should be include in defined Period%s.') % (m.period_id and ': ' + m.period_id.name or '',))
        return True

    def _hook_check_move_line(self, cr, uid, move_line, context=None):
        """
        Check date on move line. Should be the same as Journal Entry (account.move)
        """
        if not context:
            context = {}
        res = super(account_move, self)._hook_check_move_line(cr, uid, move_line, context=context)
        if not move_line:
            return res
        if move_line.date != move_line.move_id.date:
            raise osv.except_osv(_('Error'), _("Journal item does not have same posting date (%s) as journal entry (%s).") % (move_line.date, move_line.move_id.date))
        return res

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new journal entry
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Journal Items L' # For Journal Items Lines
        code = 'account.move'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def _check_inactive_journal(self, cr, uid, new_journal_id, am_ids=None, context=None):
        """
        The goal of this method is to never end up with an inactive journal, either in a new JE or as new journal in existing JEs (am_ids).
        """
        if context is None:
            context = {}
        new_journal = new_journal_id and self.pool.get('account.journal').read(cr, uid, new_journal_id, ['is_active', 'code'], context=context)
        if new_journal and not new_journal['is_active']:
            if not am_ids:  # new JE to be created
                raise osv.except_osv(_('Warning'), _('The journal %s is inactive.') % new_journal['code'])
            else:  # existing JE
                if isinstance(am_ids, (int, long)):
                    am_ids = [am_ids]
                for am in self.read(cr, uid, am_ids, ['journal_id', 'name'], context=context):
                    if new_journal['id'] != am['journal_id'][0]:  # display an error only if the journal has changed
                        raise osv.except_osv(_('Warning'), _('Journal Entry %s: the journal %s is inactive.') %
                                             (am['name'], new_journal['code']))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Change move line's sequence (name) by using instance move prefix.
        Add default document date and posting date if none.
        """
        if not context:
            context = {}
        # Change the name for (instance_id.move_prefix) + (journal_id.code) + sequence number
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'])
        # Add default date and document date if none
        if not vals.get('date', False):
            vals.update({'date': self.pool.get('account.period').get_date_in_period(cr, uid, strftime('%Y-%m-%d'), vals.get('period_id'))})
        if not vals.get('document_date', False):
            vals.update({'document_date': vals.get('date')})
        if 'from_web_menu' in context:
            vals.update({'status': 'manu'})
            # Update context in order journal item could retrieve this @creation
            if 'document_date' in vals:
                context['document_date'] = vals.get('document_date')
            if 'date' in vals:
                context['date'] = vals.get('date')
            # UTFTP-262: Make manual_name mandatory
            if 'manual_name' not in vals or not vals.get('manual_name', False) or vals.get('manual_name') == '':
                raise osv.except_osv(_('Error'), _('Description is mandatory!'))
            if journal.type == 'system':
                raise osv.except_osv(_('Warning'), _('You can not record a Journal Entry on a system journal'))

        if context.get('seqnums',False):
            # utp913 - reuse sequence numbers if in the context
            vals['name'] = context['seqnums'][journal.id]
        else:
            # Create sequence for move lines
            if vals.get('period_id'):
                # use the period selected in the form if any
                period_ids = [vals['period_id']]
            else:
                period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, vals.get('date'))
                if not period_ids:
                    raise osv.except_osv(_('Warning'), _('No period found for creating sequence on the given date: %s') %
                                         (vals.get('date') or '',))
            period = self.pool.get('account.period').browse(cr, uid, period_ids)[0]
            # UF-2479: If the period is not open yet, raise exception for the move
            # US-2563: do not raise in case of duplicate
            if not context.get('copy', False) and period and (period.state == 'created' or \
                                                              (context.get('from_web_menu') and period.state != 'draft')):  # don't save manual JE in a non-open period
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open! No Journal Entry is created') % (period.name,))

            # Context is very important to fetch the RIGHT sequence linked to the fiscalyear!
            sequence_number = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id, context={'fiscalyear_id': period.fiscalyear_id.id})
            if instance and journal and sequence_number and ('name' not in vals or vals['name'] == '/'):
                if not instance.move_prefix:
                    raise osv.except_osv(_('Warning'), _('No move prefix found for this instance! Please configure it on Company view.'))
                vals['name'] = "%s-%s-%s" % (instance.move_prefix, journal.code, sequence_number)

        # Create a sequence for this new journal entry
        res_seq = self.create_sequence(cr, uid, vals, context)
        vals.update({'sequence_id': res_seq,})
        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['manual_name', 'ref'], replace=['manual_name'])
        self._check_inactive_journal(cr, uid, vals.get('journal_id'), context=context)
        # Default behaviour (create)
        res = super(account_move, self).create(cr, uid, vals, context=context)
        self._check_document_date(cr, uid, res, context)
        self._check_date_in_period(cr, uid, res, context)
        return res

    def name_get(self, cursor, user, ids, context=None):
        # Override default name_get (since it displays "*12" names for unposted entries)
        return super(osv.osv, self).name_get(cursor, user, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check that we can write on this if we come from web menu or synchronisation.
        """
        if not ids:
            return True
        def check_update_sequence(rec, new_journal_id, new_period_id):
            """
            returns new sequence move vals (sequence_id, name) or None
            :rtype : dict/None
            """
            if m.state != 'draft':
                return None

            period_obj = self.pool.get('account.period')
            period_rec = False
            do_update = False

            # journal or FY has changed ?
            if new_journal_id and m.journal_id.id != new_journal_id:
                do_update = True
            if new_period_id and m.period_id.id != new_period_id:
                period_rec = period_obj.browse(cr, uid, new_period_id)
                do_update = do_update or period_rec.fiscalyear_id.id \
                    != m.period_id.fiscalyear_id.id  # FY changed
            if not do_update:
                return None

            # get instance and journal/period
            instance_rec = self.pool.get('res.users').browse(cr, uid, uid,
                                                             context).company_id.instance_id
            if not instance_rec.move_prefix:
                raise osv.except_osv(_('Warning'),
                                     _('No move prefix found for this instance!' \
                                       ' Please configure it on Company view.'))
            journal_rec = self.pool.get('account.journal').browse(cr, uid,
                                                                  new_journal_id or m.journal_id.id)
            period_rec = period_rec or m.period_id
            if period_rec.state == 'created':
                raise osv.except_osv(_('Error !'),
                                     _("Period '%s' is not open!' \
                     ' No Journal Entry is updated") % (period_rec.name, ))

            # get new sequence number and return related vals
            sequence_number = self.pool.get('ir.sequence').get_id(
                cr, uid, journal_rec.sequence_id.id,
                context={ 'fiscalyear_id': period_rec.fiscalyear_id.id })
            if instance_rec and journal_rec and sequence_number:
                return {
                    'sequence_id': journal_rec.sequence_id.id,
                    'name': "%s-%s-%s" % (instance_rec.move_prefix,
                                          journal_rec.code, sequence_number, ),
                }
            return None

        if context is None:
            context = {}
        new_sequence_vals_by_move_id = {}

        if context.get('from_web_menu', False) or context.get('sync_update_execution', False):
            # by default, from synchro, we just need to update period_id and journal_id
            fields = ['journal_id', 'period_id']
            # from web menu, we also update document_date and date
            if context.get('from_web_menu', False):
                fields += ['document_date', 'date']
            for m in self.browse(cr, uid, ids):
                if context.get('sync_update_session') and vals.get('state') == 'posted' and m.state == 'draft':
                    vals['posted_sync_sequence'] = context['sync_update_session']
                if context.get('from_web_menu', False):
                    if m.status == 'sys':
                        raise osv.except_osv(_('Warning'), _('You cannot edit a Journal Entry created by the system.'))
                    if m.journal_id.type == 'system':
                        raise osv.except_osv(_('Warning'), _('You can not edit a Journal Entry on a system journal'))

                if context.get('from_web_menu', False) \
                        and not context.get('sync_update_execution', False):
                    # US-932: journal or FY changed ?
                    # typical UC: manual JE from UI: journal/period changed
                    # after a duplicate.
                    # check sequence and update it if needed. (we do not update
                    # it during on_change() to prevent sequence jumps)
                    new_seq = check_update_sequence(m,
                                                    vals.get('journal_id', False),
                                                    vals.get('period_id', False))
                    if new_seq:
                        new_sequence_vals_by_move_id[m.id] = new_seq

                # Update context in order journal item could retrieve this @creation
                # Also update some other fields
                ml_vals = {}
                for el in fields:
                    if el in vals:
                        context[el] = vals.get(el)
                        ml_vals.update({el: vals.get(el)})

                # Update document date AND date at the same time
                if ml_vals:
                    ml_id_list  = [ml.id for ml in m.line_id]
                    self.pool.get('account.move.line').write(cr, uid,
                                                             ml_id_list, ml_vals, context, False, False)

        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['manual_name', 'ref'], replace=['manual_name'])
        self._check_inactive_journal(cr, uid, vals.get('journal_id'), am_ids=ids, context=context)
        res = super(account_move, self).write(cr, uid, ids, vals,
                                              context=context)
        if new_sequence_vals_by_move_id:
            for id in new_sequence_vals_by_move_id:
                osv.osv.write(self, cr, uid, id,
                              new_sequence_vals_by_move_id[id], context=context)  # US-932

        self._check_document_date(cr, uid, ids, context)
        self._check_date_in_period(cr, uid, ids, context)
        return res

    def post(self, cr, uid, ids, context=None):
        """
        Add document date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # If invoice in context, we come from self.action_move_create from invoice.py. So at invoice validation step.
        if context.get('invoice', False):
            inv_info = self.pool.get('account.invoice').read(cr, uid, context.get('invoice') and context.get('invoice').id, ['document_date'])
            if inv_info.get('document_date', False):
                self.write(cr, uid, ids, {'document_date': inv_info.get('document_date')})
        res = super(account_move, self).post(cr, uid, ids, context)
        return res

    def button_validate(self, cr, button_uid, ids, context=None):
        """
        Check that user can approve the move by searching 'from_web_menu' in context. If present and set to True and move is manually created, so User have right to do this.
        """
        if not context:
            context = {}
        uid = hasattr(button_uid, 'realUid') and button_uid.realUid or button_uid
        for i in ids:
            ml_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', '=', i)])
            if not ml_ids:
                raise osv.except_osv(_('Warning'), _('No line found. Please add some lines before Journal Entry validation!'))
            elif len(ml_ids) < 2:
                raise osv.except_osv(_('Warning'), _('The entry must have at least two lines.'))
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'sys' and not context.get('from_recurring_entries'):
                    raise osv.except_osv(_('Warning'), _("You can't approve a Journal Entry that comes from the system!"))
                # UFTP-105: Do not permit to validate a journal entry on a period that is not open
                if m.period_id and m.period_id.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('You cannot post entries in a non-opened period: %s') % (m.period_id.name))
                if m.journal_id.type in ('correction', 'correction_hq'):
                    raise osv.except_osv(_('Warning'), _('The journal %s is forbidden in manual entries.') % (m.journal_id.code))
                prev_currency_id = False
                for ml in m.line_id:
                    # Check that the currency and type of the (journal) third party is correct
                    # in case of an "Internal Transfer" account
                    type_for_reg = ml.account_id.type_for_register
                    curr_aml = ml.currency_id
                    partner_journal = ml.transfer_journal_id
                    is_liquidity = partner_journal and partner_journal.type in ['cash', 'bank', 'cheque'] and partner_journal.currency
                    if type_for_reg == 'transfer_same' and (not is_liquidity or partner_journal.currency.id != curr_aml.id):
                        raise osv.except_osv(_('Warning'),
                                             _('Account: %s - %s. The Third Party must be a liquidity journal with the same '
                                               'currency as the booking one.') % (ml.account_id.code, ml.account_id.name))
                    elif type_for_reg == 'transfer' and (not is_liquidity or partner_journal.currency.id == curr_aml.id):
                        raise osv.except_osv(_('Warning'),
                                             _('Account: %s - %s. The Third Party must be a liquidity journal with a currency '
                                               'different from the booking one.') % (ml.account_id.code, ml.account_id.name))
                    if is_liquidity and m.journal_id and m.journal_id.id == partner_journal.id:
                        raise osv.except_osv(_('Warning'),
                                             _('Account: %s - %s. The journal used for the internal transfer must be different from the '
                                               'Journal Entry Journal.') % (ml.account_id.code, ml.account_id.name))
                    # Only Donation accounts are allowed with an ODX journal
                    if m.journal_id.type == 'extra' and type_for_reg != 'donation':
                        raise osv.except_osv(_('Warning'), _('The account %s - %s is not compatible with the '
                                                             'journal %s.') % (ml.account_id.code, ml.account_id.name, m.journal_id.code))
                    # Only Internal transfers are allowed with liquidity journals in manual JE
                    if m.journal_id.type in ('bank', 'cash', 'cheque') and type_for_reg not in ('transfer', 'transfer_same'):
                        raise osv.except_osv(_('Warning'), _('The account %s - %s is not allowed.\n'
                                                             'Only internal transfers (in the same currency or not) '
                                                             'are allowed in manual journal entries on a liquidity journal.') %
                                             (ml.account_id.code, ml.account_id.name))
                    if not prev_currency_id:
                        prev_currency_id = curr_aml.id
                        continue
                    if curr_aml.id != prev_currency_id:
                        raise osv.except_osv(_('Warning'), _('You cannot have two different currencies for the same Journal Entry!'))
        return super(account_move, self).button_validate(cr, uid, ids, context=context)

    def update_line_description(self, cr, uid, ids, context=None):
        """
        Updates the description of the JIs with the one of the JE
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        for m in self.browse(cr, uid, ids, fields_to_fetch=['manual_name', 'line_id'], context=context):
            if m.manual_name and m.line_id:
                aml_obj.write(cr, uid, [ml.id for ml in m.line_id], {'name': m.manual_name}, context=context)
        return True

    def copy(self, cr, uid, a_id, default=None, context=None):
        """
        Copy a manual journal entry
        """
        if not context:
            context = {}
        if default is None:
            default = {}

        setup_obj = self.pool.get('unifield.setup.configuration')

        context.update({'omit_analytic_distribution': False})
        je = self.browse(cr, uid, [a_id], context=context)[0]

        if je.status == 'sys' or (je.journal_id and je.journal_id.type == 'migration'):
            raise osv.except_osv(_('Error'), _("You can only duplicate manual journal entries."))

        if not je.journal_id.is_active:
            raise osv.except_osv(_('Error'), _("The journal %s is inactive.") % je.journal_id.code)

        if context.get('from_button') and je.period_id and je.period_id.state != 'draft':
            # copy from web
            period_obj = self.pool.get('account.period')
            new_period = period_obj.search(cr, uid, [('date_start', '>', je.date), ('state', '=', 'draft'), ('special', '=', False)], order='date_start,number', limit=1, context=context)
            if not new_period:
                raise osv.except_osv(_('Error'), _("No open period found"))
            period_id = new_period[0]
            date_start = period_obj.read(cr, uid, period_id, ['date_start'], context=context)['date_start']
            date_start_dt = datetime.datetime.strptime(date_start, '%Y-%m-%d')
            post_date = (datetime.datetime.strptime(je.date, '%Y-%m-%d') + relativedelta(month=date_start_dt.month,year=date_start_dt.year)).strftime('%Y-%m-%d')
            # doc. date is the original one except if doc and posting dates would be in different FY:
            # if this is forbidden in the configuration, the doc. date will be 'FY-01-01'
            if datetime.datetime.strptime(je.document_date, '%Y-%m-%d').year != date_start_dt.year and \
                    not setup_obj.get_config(cr, uid).previous_fy_dates_allowed:
                doc_date = '%s-01-01' % date_start_dt.year
            else:
                doc_date = je.document_date
        else:
            period_id = je.period_id and je.period_id.id or False
            post_date = je.date
            doc_date = je.document_date

        vals = {
            'line_id': [],
            'state': 'draft',
            'document_date': doc_date,
            'date': post_date,
            'period_id': period_id,
            'name': '',
        }
        res = super(account_move, self).copy(cr, uid, a_id, vals, context=context)
        for line in je.line_id:
            line_default = {
                'analytic_lines': [],
                'move_id': res,
                'document_date': doc_date,
                'date': post_date,
                'period_id': period_id,
                'reconcile_id': False,
                'reconcile_partial_id': False,
                'reconcile_txt': False,
            }
            self.pool.get('account.move.line').copy(cr, uid, line.id,
                                                    line_default, context)
        self.validate(cr, uid, [res], context=context)
        return res

    def onchange_journal_id(self, cr, uid, ids, journal_id=False, context=None):
        """
        Change some fields when journal is changed.
        """
        res = {}
        if not context:
            context = {}
        return res

    def onchange_period_id(self, cr, uid, ids, period_id=False, date=False, context=None):
        """
        Check that given period is open.
        """
        res = {}
        if not context:
            context = {}
        if period_id:
            data = self.pool.get('account.period').read(cr, uid, period_id, ['state', 'date_start', 'date_stop'])
            if data.get('state', False) != 'draft':
                raise osv.except_osv(_('Error'), _('Period is not open!'))
        return res

    def button_delete(self, cr, uid, ids, context=None):
        """
        Delete manual and unposted journal entries if we come from web menu
        """
        if not context:
            context = {}
        to_delete = []
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'manu' and m.state == 'draft':
                    to_delete.append(m.id)
        user_id = hasattr(uid, 'realUid') and uid.realUid or uid
        # First delete move lines to avoid "check=True" problem on account_move_line item
        if to_delete:
            context.update({'move_ids_to_delete': to_delete})
            ml_ids = self.pool.get('account.move.line').search(cr, user_id, [('move_id', 'in', to_delete)])
            if ml_ids:
                if isinstance(ml_ids, (int, long)):
                    ml_ids = [ml_ids]
                self.pool.get('account.move.line').unlink(cr, user_id, ml_ids, context, check=False)
        self.unlink(cr, user_id, to_delete, context, check=False)
        return True

    def get_valid_but_unbalanced(self, cr, uid, context=None):
        cr.execute("""select l.move_id, sum(l.debit-l.credit) from account_move_line l,
            account_move m,
            account_journal j
            where
                l.move_id = m.id and
                l.state='valid' and
                m.journal_id = j.id and
                j.type != 'system'
            group by l.move_id
            having abs(sum(l.debit-l.credit)) > 0.00001
        """)
        return [x[0] for x in cr.fetchall()]


account_move()

class account_move_reconcile(osv.osv):
    _inherit = 'account.move.reconcile'

    def get_name(self, cr, uid, context=None):
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        sequence_number = self.pool.get('ir.sequence').get(cr, uid, 'account.move.reconcile')
        if instance and sequence_number:
            return instance.reconcile_prefix + "-" + sequence_number
        else:
            return ''

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True, select=1),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id',
                                               string="Statement lines", help="This field give all statement lines linked to this move."),
    }
    _defaults = {
        'name': lambda self,cr,uid,ctx={}: self.get_name(cr, uid, ctx),
    }

account_move_reconcile()

class account_account_type(osv.osv):
    _name = 'account.account.type'
    _inherit = 'account.account.type'

    _columns = {
        'not_correctible': fields.boolean(string="Prevent entries to be correctible on this account type.")
    }

    _defaults = {
        'not_correctible': lambda *a: False,
    }

account_account_type()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
