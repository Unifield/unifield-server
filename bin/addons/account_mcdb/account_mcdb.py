#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
from tools.translate import _
from tools import flatten
from lxml import etree
from datetime import datetime


class account_mcdb(osv.osv):
    _name = 'account.mcdb'
    _inherit = 'finance.query.method'
    _rec_name = 'description'

    _columns = {
        'description': fields.char("Query name", required=False, readonly=False, size=255),
        'journal_ids': fields.many2many(obj='account.journal', rel='account_journal_mcdb', id1='mcdb_id', id2='journal_id', string="Journal Code", domain="[('code', '!=', 'IB')]"),  # exclude year closing initial balance journal
        'instance_ids': fields.many2many('msf.instance', 'instance_mcdb', 'mcdb_id', 'instance_id', string="Proprietary instances"),
        'top_prop_instance_ids': fields.many2many('msf.instance', 'instance_top_mcdb', 'mcdb_id', 'instance_id', string="Top Proprietary instances"),
        'analytic_journal_ids': fields.many2many(obj='account.analytic.journal', rel='account_analytic_journal_mcdb', id1='mcdb_id', id2='analytic_journal_id', string="Analytic journal code"),
        'abs_id': fields.many2one('account.bank.statement', string="Register name"), # Change into many2many ?
        'posting_date_from': fields.date('First posting date'),
        'posting_date_to': fields.date('Ending posting date'),
        'document_date_from': fields.date('First document date'),
        'document_date_to': fields.date('Ending document date'),
        'document_code': fields.char(string='Sequence number', size=255),
        'include_related_entries': fields.boolean('Related entries', help='Entries related to the Sequence numbers set'),
        'document_state': fields.selection([('posted', 'Posted'), ('draft', 'Unposted')], string="Entry Status"),
        'period_ids': fields.many2many(obj='account.period', rel="account_period_mcdb", id1="mcdb_id", id2="period_id", string="Accounting Period"),
        'fiscalyear_id': fields.many2one('account.fiscalyear', string='Fiscal Year'),
        'account_ids': fields.many2many(obj='account.account', rel='account_account_mcdb', id1='mcdb_id', id2='account_id', string="Account Code"),
        'partner_id': fields.many2one('res.partner', string="Partner"),  # not used since US-3427
        'partner_ids': fields.many2many(obj='res.partner', rel='partner_mcdb', id1='mcdb_id', id2='partner_id',
                                        string='Partners', order_by='name, id', display_inactive=True),
        'employee_id': fields.many2one('hr.employee', string="Employee"),  # not used since US-3427
        'employee_ids': fields.many2many(obj='hr.employee', rel='employee_mcdb', id1='mcdb_id', id2='employee_id',
                                         string='Employees', order_by='employee_type, identification_id, id'),
        'transfer_journal_id': fields.many2one('account.journal', string="Journal",
                                               domain="[('code', '!=', 'IB')]"),  # exclude year closing initial balance journal / not used since US-3427
        'transfer_journal_ids': fields.many2many(obj='account.journal', rel='transfer_journal_mcdb', id1='mcdb_id', id2='journal_id',
                                                 string='Journals', domain="[('type', 'in', ['cash', 'bank', 'cheque'])]",
                                                 order_by='instance_id, code, id'),
        'reconciled': fields.selection([('reconciled', 'Reconciled'), ('unreconciled', 'NOT reconciled')], string='Reconciled?'),
        'functional_currency_id': fields.many2one('res.currency', string="Functional currency", readonly=True),
        'amount_func_from': fields.float('Begin amount in functional currency'),
        'amount_func_to': fields.float('Ending amount in functional currency'),
        'booking_currency_id': fields.many2one('res.currency', string="Booking currency"),
        'amount_book_from': fields.float('Begin amount in booking currency'),
        'amount_book_to': fields.float('Ending amount in booking currency'),
        'currency_choice': fields.selection([('booking', 'Booking'), ('functional', 'Functional')], string="Currency type"),
        'currency_id': fields.many2one('res.currency', string="Currency"),
        'amount_from': fields.float('Begin amount in given currency type'),
        'amount_to': fields.float('Ending amount in given currency type'),
        'account_type_ids': fields.many2many(obj='account.account.type', rel='account_account_type_mcdb', id1='mcdb_id', id2='account_type_id',
                                             string="Account type"),
        'reconcile_id': fields.many2one('account.move.reconcile', string="Reconcile Reference"),
        'reconcile_date': fields.date("Reconciled at"),
        'open_items': fields.many2one('account.period', string='Open Items at', domain=[('state', '!=', 'created')]),
        'ref': fields.char(string='Reference', size=255),
        'name': fields.char(string='Description', size=255),
        'rev_account_ids': fields.boolean('Exclude account selection'),
        'model': fields.selection([('account.move.line', 'Journal Items'),
                                   ('account.analytic.line', 'Analytic Journal Items'),
                                   ('combined.line', 'Both Journal Items and Analytic Journal Items')], string="Type"),
        'display_in_output_currency': fields.many2one('res.currency', string='Display in output currency'),
        'fx_table_id': fields.many2one('res.currency.table', string="FX Table"),
        'analytic_account_cc_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_cc_mcdb", id1="mcdb_id", id2="analytic_account_id",
                                                    string="Cost Center"),
        'rev_analytic_account_cc_ids': fields.boolean('Exclude Cost Center selection'),
        'analytic_account_fp_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_fp_mcdb", id1="mcdb_id", id2="analytic_account_id",
                                                    string="Funding Pool"),
        'rev_analytic_account_fp_ids': fields.boolean('Exclude Funding Pool selection'),
        'analytic_account_f1_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_f1_mcdb", id1="mcdb_id", id2="analytic_account_id",
                                                    string="Free 1"),
        'rev_analytic_account_f1_ids': fields.boolean('Exclude free 1 selection'),
        'analytic_account_f2_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_f2_mcdb", id1="mcdb_id", id2="analytic_account_id",
                                                    string="Free 2"),
        'rev_analytic_account_f2_ids': fields.boolean('Exclude free 2 selection'),
        'reallocated': fields.selection([('reallocated', 'Reallocated'), ('unreallocated', 'NOT reallocated')], string='Reallocated?'),
        'reversed': fields.selection([('reversed', 'Reversed'), ('notreversed', 'NOT reversed')], string='Reversed?'),
        'rev_journal_ids': fields.boolean('Exclude journal selection'),
        'rev_period_ids': fields.boolean('Exclude period selection'),
        'rev_account_type_ids': fields.boolean('Exclude account type selection'),
        'rev_analytic_journal_ids': fields.boolean('Exclude analytic journal selection'),
        'rev_instance_ids': fields.boolean('Exclude instances selection'),
        'rev_top_prop_instance_ids': fields.boolean('Exclude top prop instances selection'),
        'rev_partner_ids': fields.boolean('Exclude partner selection'),
        'rev_employee_ids': fields.boolean('Exclude employee selection'),
        'rev_transfer_journal_ids': fields.boolean('Exclude journal selection'),  # Third Party Journal
        'excl_inactive_journal_ids': fields.boolean('Exclude inactive journals'),
        'inactive_at': fields.date('Journals Inactive at'),
        'analytic_axis': fields.selection([('fp', 'Funding Pool'), ('f1', 'Free 1'), ('f2', 'Free 2')], string='Display'),
        'rev_analytic_account_dest_ids': fields.boolean('Exclude Destination selection'),
        'analytic_account_dest_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_dest_mcdb", id1="mcdb_id", id2="analytic_account_id",
                                                      string="Destination"),
        'display_journal': fields.boolean('Display journals?'),
        'display_period': fields.boolean('Display periods?'),
        'display_instance': fields.boolean('Display instances?'),
        'display_top_prop_instance': fields.boolean('Display Top prop instances?'),
        'display_account': fields.boolean('Display accounts?'),
        'display_analytic_account': fields.boolean('Display analytic accounts?'),
        'display_type': fields.boolean('Display account types?'),
        'display_analytic_period': fields.boolean('Display analytic periods?'),
        'display_analytic_journal': fields.boolean('Display analytic journals?'),
        'display_funding_pool': fields.boolean('Display funding pools?'),
        'display_cost_center': fields.boolean('Display cost centers?'),
        'display_destination': fields.boolean('Display destinations?'),
        'display_free1': fields.boolean('Display Free 1?'),
        'display_free2': fields.boolean('Display Free 2?'),
        'display_partner': fields.boolean('Display Partners?'),
        'display_employee': fields.boolean('Display Employees?'),
        'display_transfer_journal': fields.boolean('Display Transfer Journals?'),
        'user': fields.many2one('res.users', "User"),
        'cheque_number': fields.char('Cheque Number', size=120),  # BKLG-7
        'partner_txt': fields.char('Third Party', size=120),  # BKLG-7
        'template': fields.many2one('account.mcdb', 'Template',
                                    domain=[('description', '!=', False), ('description', '!=', '')]),  # filter on model done in the view
        'copied_id': fields.many2one('account.mcdb', help='Id of the template loaded'),
        'template_name': fields.char('Template name', size=255),  # same size as the "Query name"
        'display_mcdb_load_button': fields.boolean('Display the Load button'),
        'create_date': fields.date('Creation Date', readonly=True),
        'write_date': fields.date('Last Edit Date', readonly=True),
        'write_uid': fields.many2one('res.users', "Last Editor", readonly=True),
    }

    _defaults = {
        'model': lambda self, cr, uid, c: c.get('from', 'account.move.line'),
        'functional_currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'currency_choice': lambda *a: 'booking',
        'analytic_axis': lambda *a: 'fp',
        'display_journal': lambda *a: False,
        'display_period': lambda *a: False,
        'display_instance': lambda *a: False,
        'display_top_prop_instance': lambda *a: False,
        'display_account': lambda *a: False,
        'display_analytic_account': lambda *a: False,
        'display_type': lambda *a: False,
        'display_analytic_period': lambda *a: False,
        'display_analytic_journal': lambda *a: False,
        'display_funding_pool': lambda *a: False,
        'display_cost_center': lambda *a: False,
        'display_destination': lambda *a: False,
        'user': lambda self, cr, uid, c: uid or False,
        'display_mcdb_load_button': lambda *a: True,
    }

    _order = 'user, description, id'

    def search(self, cr, uid, dom, *a, **b):
        """
        Ignores the filter on "Active Users" once a specific user has been selected
        """
        new_dom = []
        active_user_dom = []
        user_filter = False
        for x in dom:
            if x[0] == 'user.active':
                active_user_dom = x
            elif x[0] == 'user':
                user_filter = True
                new_dom.append(x)
            else:
                new_dom.append(x)
        if not user_filter and active_user_dom:
            new_dom.append(active_user_dom)

        return super(account_mcdb, self).search(cr, uid, new_dom, *a, **b)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if  context is None:
            context = {}
        view = super(account_mcdb, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if context.get('from_query') and view_type == 'form':
            form = etree.fromstring(view['arch'])
            fields = form.xpath('//group[@name="wizard_template"]')
            for field in fields:
                field.set('invisible', "1")
            fields = form.xpath('//group[@name="wizard_hq_query"]')
            for field in fields:
                field.set('invisible', "0")
            view['arch'] = etree.tostring(form)

        if context.get('from', '') != 'combined.line' and 'document_code' in view['fields']:
            view['fields']['document_code']['string'] = _('Sequence numbers')
            view['fields']['document_code']['help'] = _('You can set several sequences separated by a comma.')
        return view


    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['description','hq_template'], context=context)
        res = []
        for record in reads:
            name = record['description']
            if record['hq_template']:
                name = '%s (SYNC)' % (name,)

            res.append((record['id'], name))
        return res

    def onchange_currency_choice(self, cr, uid, ids, choice, func_curr=False, mnt_from=0.0, mnt_to=0.0, context=None):
        """
        Permit to give default company currency if 'functional' has been choosen.
        Delete all currency and amount fields (to not disturb normal mechanism)
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not choice:
            return {}
        # Prepare some values
        vals = {}
        # Reset fields
        for field in ['amount_book_from', 'amount_book_to', 'amount_func_from', 'amount_func_to', 'booking_currency_id']:
            vals[field] = 0.0
        # Fill in values
        if choice == 'functional':
            vals.update({'currency_id': func_curr or False})
        elif choice == 'booking':
            vals.update({'currency_id': False})
        # Update amounts 'from' and 'to'.
        update_from = self.onchange_amount(cr, uid, ids, choice, mnt_from, 'from', context=context)
        update_to = self.onchange_amount(cr, uid, ids, choice, mnt_to, 'to', context=context)
        if update_from:
            vals.update(update_from.get('value'))
        if update_to:
            vals.update(update_to.get('value'))
        return {'value': vals}

    def onchange_currency(self, cr, uid, ids, choice, currency, context=None):
        """
        Fill in right field regarding choice and currency
        """
        # Prepare some values
        vals = {}
        # Some verifications
        if not choice:
            return {}
        # Fill in field
        if choice == 'functional':
            vals['functional_currency_id'] = currency
        elif choice == 'booking':
            vals['booking_currency_id'] = currency
        return {'value': vals}

    def onchange_amount(self, cr, uid, ids, choice, amount, amount_type=None, context=None):
        """
        Fill in right amount field regarding choice
        """
        # Prepare some values
        vals = {}
        # Some verifications
        if not choice:
            return {}
        if not amount:
            amount = 0.0
        if choice == 'functional':
            if amount_type == 'from':
                vals['amount_func_from'] = amount
            elif amount_type == 'to':
                vals ['amount_func_to'] = amount
        elif choice == 'booking':
            if amount_type == 'from':
                vals['amount_book_from'] = amount
            elif amount_type == 'to':
                vals['amount_book_to'] = amount
        return {'value': vals}

    def onchange_fx_table(self, cr, uid, ids, fx_table_id, context=None):
        """
        Update output currency domain in order to show right currencies attached to given fx table
        """
        res = {}
        # Some verifications
        if not context:
            context = {}
        if fx_table_id:
            res.update({'value': {'display_in_output_currency' : False}})
        return res

    def onchange_analytic_axis(self, cr, uid, ids, analytic_axis, context=None):
        """
        Clean up Cost Center / Destination / Funding Pool / Free 1 and Free 2 frames
        """
        vals = {}
        if not analytic_axis:
            return {}
        vals.update({'analytic_account_fp_ids': False, 'analytic_account_cc_ids': False, 'analytic_account_dest_ids': False, 'analytic_account_f1_ids': False, 'analytic_account_f2_ids': False})
        return {'value': vals}

    def onchange_display_instance(self, cr, uid, ids, display_instance, display_top_prop_instance, context=None):
        if display_instance and display_top_prop_instance:
            warning = {
                'title': _('Warning'),
                'message': _('You cannot select \'Instances\' because \'Top prop Instances\' is already selected.')
            }
            value = {'display_instance': False}
            return {
                'warning': warning,
                'value': value
            }
        return {}

    def onchange_display_prop_instance(self, cr, uid, ids, display_instance, display_top_prop_instance, context=None):
        if display_instance and display_top_prop_instance:
            warning = {
                'title': _('Warning'),
                'message': _('You cannot select \'Top prop Instances\' because \'Instances\' is already selected.')
            }
            value = {'display_top_prop_instance': False}

            return {
                'warning': warning,
                'value': value
            }
        return {}

    def onchange_template(self, cr, uid, ids, context=None):
        """
        Whenever a new template is selected, display the "load" button
        (and don't display the other options for the template, such as "delete"...)
        """
        res = {}
        res['value'] = {'display_mcdb_load_button': True}
        return res

    def _get_domain(self, cr, uid, ids, context=None):
        """
        Returns the domain to use to get the selector results
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        domain = []
        wiz = self.browse(cr, uid, [ids[0]], context=context)[0]
        res_model = context.get('selector_model', False) or (wiz and wiz.model) or False
        journal_obj = self.pool.get('account.journal')
        if res_model:
            # Prepare domain values
            # First MANY2MANY fields
            m2m_fields = [
                ('period_ids', 'period_id'),
                ('analytic_account_fp_ids', 'account_id'),
                ('analytic_account_cc_ids', 'cost_center_id'),
                ('analytic_account_f1_ids', 'account_id'),
                ('analytic_account_f2_ids', 'account_id'),
                ('analytic_account_dest_ids', 'destination_id'),
                ('instance_ids', 'instance_id'),
                ('top_prop_instance_ids', 'instance_id'),
            ]
            # Journals
            if res_model == 'account.analytic.line':
                if context.get('from', '') == 'combined.line':
                    # for the AJIs in the Combined Journals Report: distinguish between G/L and Analytic Journals
                    m2m_fields.append(('journal_ids', 'gl_journal_id'))
                    m2m_fields.append(('analytic_journal_ids', 'analytic_journal_id'))
                else:
                    # for the other AJIs: only handle analytic journals
                    m2m_fields.append(('analytic_journal_ids', 'journal_id'))
            else:
                # for the JIs: only handle G/L journals
                m2m_fields.append(('journal_ids', 'journal_id'))
            if res_model == 'account.analytic.line':
                m2m_fields.append(('account_ids', 'general_account_id'))
                m2m_fields.append(('account_type_ids', 'general_account_id.user_type'))
            else:
                m2m_fields.append(('account_ids', 'account_id'))
                m2m_fields.append(('account_type_ids', 'account_id.user_type'))
                m2m_fields.append(('partner_ids', 'partner_id'))
                m2m_fields.append(('employee_ids', 'employee_id'))
                m2m_fields.append(('transfer_journal_ids', 'transfer_journal_id'))
            for m2m in m2m_fields:
                if getattr(wiz, m2m[0]):
                    value = False

                    # do not add domain if the block have not been selected
                    # (because they are using same field relation m2m)
                    if m2m[0] == 'instance_ids' and not wiz.display_instance:
                        continue
                    if m2m[0] == 'top_prop_instance_ids' and not wiz.display_top_prop_instance:
                        continue

                    operator = 'in'
                    # Special fields
                    # account_ids with reversal
                    if m2m[0] == 'account_ids' and wiz.rev_account_ids:
                        operator = 'not in'
                    # analytic_account_fp_ids with reversal
                    elif m2m[0] == 'analytic_account_fp_ids' and wiz.rev_analytic_account_fp_ids:
                        operator = 'not in'
                    # analytic_account_cc_ids with reversal
                    elif m2m[0] == 'analytic_account_cc_ids' and wiz.rev_analytic_account_cc_ids:
                        operator = 'not in'
                    # analytic_account_f1_ids with reversal
                    elif m2m[0] == 'analytic_account_f1_ids' and wiz.rev_analytic_account_f1_ids:
                        operator = 'not in'
                    # analytic_account_f2_ids with reversal
                    elif m2m[0] == 'analytic_account_f2_ids' and wiz.rev_analytic_account_f2_ids:
                        operator = 'not in'
                    # analytic_account_dest_ids with reversal
                    elif m2m[0] == 'analytic_account_dest_ids' and wiz.rev_analytic_account_dest_ids:
                        operator = 'not in'
                    # period_ids with reversal
                    elif m2m[0] == 'period_ids' and wiz.rev_period_ids:
                        operator = 'not in'
                    # journal_ids with reversal
                    elif m2m[0] == 'journal_ids' and wiz.rev_journal_ids:
                        operator = 'not in'
                    # exclude inactive journals
                    elif m2m[0] == 'journal_ids' and wiz.excl_inactive_journal_ids:
                        operator = 'not in'
                        inactiv_date = wiz.inactive_at or datetime.today().date()
                        inactive_journal_ids = journal_obj.search(cr, uid, [('is_active', '=', 'f'), ('inactivation_date', '<', inactiv_date)], context=context)
                        value = [x.id for x in getattr(wiz, m2m[0])] + inactive_journal_ids
                    # account_type_ids with reversal
                    elif m2m[0] == 'account_type_ids' and wiz.rev_account_type_ids:
                        operator = 'not in'
                    # analytic_journal_ids with reversal
                    elif m2m[0] == 'analytic_journal_ids' and wiz.rev_analytic_journal_ids:
                        operator = 'not in'
                    # instance_ids with reversal
                    elif m2m[0] == 'instance_ids' and wiz.rev_instance_ids:
                        operator = 'not in'
                    elif m2m[0] == 'top_prop_instance_ids' and wiz.rev_top_prop_instance_ids:
                        operator = 'not in'
                    # partner_ids with reversal
                    elif m2m[0] == 'partner_ids' and wiz.rev_partner_ids:
                        operator = 'not in'
                    # employee_ids with reversal
                    elif m2m[0] == 'employee_ids' and wiz.rev_employee_ids:
                        operator = 'not in'
                    # transfer_journal_ids with reversal
                    elif m2m[0] == 'transfer_journal_ids' and wiz.rev_transfer_journal_ids:
                        operator = 'not in'
                        # also exclude all non liquidity journals (so the right journals will be displayed in the PDF report header)
                        other_journal_ids = journal_obj.search(cr, uid, [('type', 'not in', ['cash', 'bank', 'cheque'])], order='NO_ORDER', context=context)
                        value = [x.id for x in getattr(wiz, m2m[0])] + other_journal_ids
                    # Search if a view account is given
                    if m2m[0] in ['account_ids', 'analytic_account_fp_ids', 'analytic_account_cc_ids', 'analytic_account_f1_ids', 'analytic_account_f2_ids']:
                        account_ids = []
                        account_obj = 'account.account'
                        if m2m[0] in ['analytic_account_fp_ids', 'analytic_account_cc_ids', 'analytic_account_f1_ids', 'analytic_account_f2_ids']:
                            account_obj = 'account.analytic.account'
                        for account in getattr(wiz, m2m[0]):
                            if account.type == 'view':
                                search_ids = self.pool.get(account_obj).search(cr, uid, [('id', 'child_of', [account.id])])
                                account_ids.append(search_ids)
                        if account_ids:
                            # Add default account_ids from wizard
                            account_ids.append([x.id for x in getattr(wiz, m2m[0])])
                            # Convert list in a readable list for openerp
                            account_ids = flatten(account_ids)
                            # Create domain and NEXT element (otherwise this give a bad domain)
                            domain.append((m2m[1], operator, tuple(account_ids)))
                            continue
                    if m2m[0] == 'top_prop_instance_ids':
                        instance_obj = self.pool.get('msf.instance')
                        child_list = instance_obj.get_child_ids(cr, uid, [x.id for x in getattr(wiz, m2m[0])])
                        id_list = child_list + [x.id for x in getattr(wiz, m2m[0])]
                        domain.append((m2m[1], operator, tuple(id_list)))
                    else:
                        value = value or tuple([x.id for x in getattr(wiz, m2m[0])])
                        domain.append((m2m[1], operator, value))
            # Then MANY2ONE fields
            for m2o in [('abs_id', 'statement_id'), ('booking_currency_id', 'currency_id'),
                        ('fiscalyear_id', 'fiscalyear_id')]:
                if getattr(wiz, m2o[0]):
                    domain.append((m2o[1], '=', getattr(wiz, m2o[0]).id))
            # Finally others fields
            # LOOKS LIKE fields
            for ll in [('ref', 'ref'), ('name', 'name'), ('cheque_number', 'cheque_number'), ('partner_txt', 'partner_txt')]:
                if getattr(wiz, ll[0]):
                    domain.append((ll[1], 'ilike', '%%%s%%' % getattr(wiz, ll[0])))
                    if ll[0] == 'cheque_number':
                        context['selector_display_cheque_number'] = True
            # DOCUMENT CODE fields
            if wiz.document_code and wiz.document_code != '':
                document_code = wiz.document_code
                document_code_field = 'move_id.name'
                # For G/L and Analytic Selectors: allow searching several (exact) Entry Sequences separated by a comma
                # For Combined Journals Report: allow only one Entry Seq. but partial search possible (ex: "FXA-1804")
                document_codes = []
                if res_model == 'account.analytic.line':
                    domain.append('|')
                    if context.get('from', '') == 'combined.line':
                        domain.append(('commitment_line_id.commit_id.name', 'ilike', document_code))
                        domain.append(('entry_sequence', 'ilike', document_code))
                    else:
                        document_codes = [i.strip() for i in document_code.split(',')]
                        domain.append(('commitment_line_id.commit_id.name', 'in', document_codes))
                        domain.append(('entry_sequence', 'in', document_codes))
                else:
                    if context.get('from', '') == 'combined.line':
                        domain.append((document_code_field, 'ilike', document_code))
                    else:
                        document_codes = [i.strip() for i in document_code.split(',')]
                        domain.append((document_code_field, 'in', document_codes))
                if document_codes and wiz.include_related_entries:
                    # note: the domain has no impact on the related entries to be displayed
                    context.update({'related_entries': document_codes})

            if wiz.document_state and wiz.document_state != '':
                domain.append(('move_id.state', '=', wiz.document_state))
            # DATE fields
            # first doc date, then posting date to get a consistent display in the header when the selection is exported
            doc_sup = ('document_date_from', 'document_date')
            if getattr(wiz, doc_sup[0]):
                domain.append((doc_sup[1], '>=', getattr(wiz, doc_sup[0])))
            doc_inf = ('document_date_to', 'document_date')
            if getattr(wiz, doc_inf[0]):
                domain.append((doc_inf[1], '<=', getattr(wiz, doc_inf[0])))
            post_sup = ('posting_date_from', 'date')
            if getattr(wiz, post_sup[0]):
                domain.append((post_sup[1], '>=', getattr(wiz, post_sup[0])))
            post_inf = ('posting_date_to', 'date')
            if getattr(wiz, post_inf[0]):
                domain.append((post_inf[1], '<=', getattr(wiz, post_inf[0])))
            # RECONCILE field
            if wiz.reconcile_id:
                # total or partial and override  reconciled status
                domain.append(('reconcile_total_partial_id', '=', wiz.reconcile_id.id))
            elif wiz.reconciled:
                # US-533: new search matrix
                # http://jira.unifield.org/browse/US-533?focusedCommentId=50218&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-50218
                # search always regarding FULL reconcile (is_reconciled do that)
                if wiz.reconciled == 'reconciled':
                    domain.append(('is_reconciled', '=', True))
                elif wiz.reconciled == 'unreconciled':
                    domain.append(('is_reconciled', '=', False))
            if wiz.reconcile_date:
                domain.append(('reconcile_date', '<=', wiz.reconcile_date))
            # note that for US-533 JI search is overrided in
            # account_reconcile/account_move_line.py

            # OPEN ITEMS field
            if res_model == 'account.move.line' and wiz.open_items:
                domain.append(('open_items', '=', wiz.open_items.id))

            # REALLOCATION field
            if wiz.reallocated:
                if wiz.reallocated == 'reallocated':
                    # entries corrected by the system (= not marked as corrected manually)
                    domain.append(('is_reallocated', '=', True))
                    domain.append('|')
                    domain.append(('move_id', '=', False))
                    domain.append(('move_id.is_manually_corrected', '=', False))
                elif wiz.reallocated == 'unreallocated':
                    domain.append('|')
                    domain.append(('is_reallocated', '=', False))
                    domain.append(('move_id.is_manually_corrected', '=', True))
            # REVERSED field
            if wiz.reversed:
                if wiz.reversed == 'reversed':
                    domain.append(('is_reversal', '=', True))
                elif wiz.reversed == 'notreversed':
                    domain.append(('is_reversal', '=', False))
            # ANALYTIC AXIS FIELD
            if res_model == 'account.analytic.line':
                if wiz.analytic_axis == 'fp':
                    context.update({'display_fp': True, 'categ': 'FUNDING'})
                    domain.append(('account_id.category', '=', 'FUNDING'))
                elif wiz.analytic_axis == 'f1':
                    context.update({'categ': 'FREE1'})
                    domain.append(('account_id.category', '=', 'FREE1'))
                elif wiz.analytic_axis == 'f2':
                    context.update({'categ': 'FREE2'})
                    domain.append(('account_id.category', '=', 'FREE2'))
                else:
                    raise osv.except_osv(_('Warning'), _('Display field is mandatory!'))
            ## SPECIAL fields
            #
            # AMOUNTS fields
            #
            # NB: Amount problem has been resolved as this
            #+ There is 4 possibilities for amounts:
            #+ 1/ NO amount given: nothing to do
            #+ 2/ amount FROM AND amount TO is given
            #+ 3/ amount FROM is filled in but NOT amount TO
            #+ 4/ amount TO is filled in but NOT amount FROM
            #+
            # NB: on US-650 we agree that the "From" value is always the smallest and the "To" value is the biggest,
            # no matter if amounts are positive or negative
            #+ For each case, here is what domain should be look like:
            #+ 1/ FROM is 0.0, TO is 0,0. Domain is []
            #+ 2/ FROM is 400, TO is 600. Domain is ['&', (balance, '>=', 400), ('balance', '<=', 600)]
            #+ 3/ FROM is 400, TO is 0.0. Domain is [('balance', '>=', 400)]
            #+ 4/ FROM is 0.0, TO is 600. Domain is [('balance', '<=', 600)]

            # prepare tuples that would be processed
            booking = ('amount_book_from', 'amount_book_to', 'amount_currency')
            functional = ('amount_func_from', 'amount_func_to', 'balance')
            for curr in [booking, functional]:
                # Prepare some values
                mnt_from = getattr(wiz, curr[0]) or False
                mnt_to = getattr(wiz, curr[1]) or False
                # display a warning when amount FROM > amount TO
                if mnt_from and mnt_to and mnt_from > mnt_to:
                    raise osv.except_osv(_('Warning'),
                                         _('In the amount selector (from-to), the "from" value must be the smallest one.'))
                field = curr[2]
                # specific behaviour for functional in analytic MCDB
                if field == 'balance' and res_model == 'account.analytic.line':
                    field = 'amount'
                # domain elements initialisation
                domain_elements = []
                if mnt_from and mnt_to:
                    if mnt_from == mnt_to:
                        domain_elements = [(field, '=', mnt_from)]
                    else:
                        domain_elements = ['&', (field, '>=', mnt_from), (field, '<=', mnt_to)]
                elif mnt_from:
                    domain_elements = [(field, '>=', mnt_from)]
                elif mnt_to:
                    domain_elements = [(field, '<=', mnt_to)]
                # Add elements to domain which would be use for filtering
                for el in domain_elements:
                    domain.append(el)
            if res_model == 'account.move.line':
                # US-1290: JI export search result always exclude IB entries
                domain = [ ('period_id.number', '>', 0), ] + domain
        return domain

    def button_validate(self, cr, uid, ids, context=None):
        """
        Validate current forms and give result
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        domain = self._get_domain(cr, uid, ids, context)
        wiz = self.browse(cr, uid, [ids[0]], context=context)[0]
        res_model = wiz and wiz.model or False
        if res_model:
            # Output currency display (with fx_table)
            if wiz.fx_table_id:
                context.update({'fx_table_id': wiz.fx_table_id.id, 'currency_table_id': wiz.fx_table_id.id})
            if wiz.display_in_output_currency:
                context.update({'output_currency_id': wiz.display_in_output_currency.id})
            # Return result in a search view
            view = 'account_move_line_mcdb_search_result'
            search_view = 'mcdb_view_account_move_line_filter'
            search_model = 'account_mcdb'
            name = _('Selector - G/L')
            if res_model == 'account.analytic.line':
                view = 'account_analytic_line_mcdb_search_result'
                search_view = 'view_account_analytic_line_filter'
                search_model = 'account'
                name = _('Selector - Analytic')
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_mcdb', view)
            view_id = view_id and view_id[1] or False
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, search_model, search_view)
            search_view_id = search_view_id and search_view_id[1] or False

            context['target_filename_prefix'] = name

            # add the related entries at the end if needed
            if res_model in ('account.move.line', 'account.analytic.line') and context.get('related_entries', []):
                entry_ids = self.pool.get(res_model).search(cr, uid, domain, order='NO_ORDER', context=context) or []
                related_entry_ids = self.pool.get(res_model).get_related_entry_ids(cr, uid, entry_seqs=context['related_entries'], context=context) or []
                domain = [('id', 'in', list(set(entry_ids + related_entry_ids)))]

            return {
                'name': name,
                'type': 'ir.actions.act_window',
                'res_model': res_model,
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'search_view_id': search_view_id,
                'domain': domain,
                'context': context,
                'keep_open': 1,
                'target': 'current',
            }
        return False

    def button_clear(self, cr, uid, ids, field=False, context=None):
        """
        Delete all fields from this object
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        res_id = ids[0]
        all_fields = True
        # Search model
        wiz = self.browse(cr, uid, res_id)
        res_model = wiz and wiz.model or False
        if field and field in (self._columns and self._columns.keys()):
            if self._columns[field]._type == 'many2many':
                # Don't clear all other fields
                all_fields = False
                # Clear this many2many field
                self.write(cr, uid, ids, {field: [(6,0,[])]}, context=context)
        # Clear all fields if necessary
        if all_fields:
            res_id = self.create(cr, uid, {'model': res_model}, context=context)
        return {}

    def _button_add(self, cr, uid, ids, obj=False, field=False, args=None, context=None):
        """
        Search all elements of an object (obj) regarding criteria (args). Then return wizard and complete given field (field).
        NB: We consider field is always a MANY2ONE field! (no sense to add all elements of another field...)
        """
        if args is None:
            args = []
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Do search
        if obj and field:
            # Search all elements
            element_ids = self.pool.get(obj).search(cr, uid, args)
            if element_ids:
                self.write(cr, uid, ids, {field: [(6, 0, element_ids)]})
        return {}

    def button_journal_clear(self, cr, uid, ids, context=None):
        """
        Delete journal_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'journal_ids' field
        return self.button_clear(cr, uid, ids, field='journal_ids', context=context)

    def button_journal_add(self, cr, uid, ids, context=None):
        """
        Add all journals in journal_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.journal'
        args = []
        field = 'journal_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_period_clear(self, cr, uid, ids, context=None):
        """
        Delete period_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'period_ids' field
        return self.button_clear(cr, uid, ids, field='period_ids', context=context)

    def button_period_add(self, cr, uid, ids, context=None):
        """
        Add all periods in period_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.period'
        args = []
        field = 'period_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_analytic_journal_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_journal_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_journal_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_journal_ids', context=context)

    def button_analytic_journal_add(self, cr, uid, ids, context=None):
        """
        Add all Analytic journals in analytic_journal_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.journal'
        args = []
        field = 'analytic_journal_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_account_clear(self, cr, uid, ids, context=None):
        """
        Delete account_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'account_ids' field
        return self.button_clear(cr, uid, ids, field='account_ids', context=context)

    def button_account_add(self, cr, uid, ids, context=None):
        """
        Add all Accounts in account_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.account'
        args = [('parent_id', '!=', False)]
        field = 'account_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_account_type_clear(self, cr, uid, ids, context=None):
        """
        Delete account_type_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'account_type_ids' field
        return self.button_clear(cr, uid, ids, field='account_type_ids', context=context)

    def button_account_type_add(self, cr, uid, ids, context=None):
        """
        Add all Account Type in account_type_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.account.type'
        args = []
        field = 'account_type_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_funding_pool_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_account_fp_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_account_fp_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_account_fp_ids', context=context)

    def button_funding_pool_add(self, cr, uid, ids, context=None):
        """
        Add all Funding Pool in analytic_account_fp_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.account'
        args = [('type', '!=', 'view'), ('category', '=', 'FUNDING')]
        field = 'analytic_account_fp_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_cost_center_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_account_cc_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_account_cc_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_account_cc_ids', context=context)

    def button_cost_center_add(self, cr, uid, ids, context=None):
        """
        Add all Cost Center in analytic_account_cc_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.account'
        args = [('type', '!=', 'view'), ('category', '=', 'OC')]
        field = 'analytic_account_cc_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_free_1_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_account_f1_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_account_f1_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_account_f1_ids', context=context)

    def button_free_1_add(self, cr, uid, ids, context=None):
        """
        Add all Free 1 in analytic_account_f1_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.account'
        args = [('type', '!=', 'view'), ('category', '=', 'FREE1')]
        field = 'analytic_account_f1_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_free_2_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_account_f2_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_account_f2_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_account_f2_ids', context=context)

    def button_free_2_add(self, cr, uid, ids, context=None):
        """
        Add all Free 2 in analytic_account_f2_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.account'
        args = [('type', '!=', 'view'), ('category', '=', 'FREE2')]
        field = 'analytic_account_f2_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_destination_clear(self, cr, uid, ids, context=None):
        """
        Delete analytic_account_dest_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return default behaviour with 'analytic_account_dest_ids' field
        return self.button_clear(cr, uid, ids, field='analytic_account_dest_ids', context=context)

    def button_destination_add(self, cr, uid, ids, context=None):
        """
        Add all Destination in analytic_account_dest_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'account.analytic.account'
        args = [('type', '!=', 'view'), ('category', '=', 'DEST')]
        field = 'analytic_account_dest_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_instance_clear(self, cr, uid, ids, context=None):
        """
        Delete instance_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.button_clear(cr, uid, ids, field='instance_ids', context=context)

    def button_prop_instance_clear(self, cr, uid, ids, context=None):
        """
        Delete top_prop_instance_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.button_clear(cr, uid, ids, field='top_prop_instance_ids', context=context)

    def button_prop_instance_add(self, cr, uid, ids, context=None):
        """
        Add all instances in top_prop_instance_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'msf.instance'
        args = [('level', '=', 'coordo')]
        field = 'top_prop_instance_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_instance_add(self, cr, uid, ids, context=None):
        """
        Add all instances in instance_ids field content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        obj = 'msf.instance'
        args = []
        field = 'instance_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_partner_add(self, cr, uid, ids, context=None):
        """
        Adds all Partners in partner_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj = 'res.partner'
        args = [('active', '=', 't')]
        field = 'partner_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_employee_add(self, cr, uid, ids, context=None):
        """
        Adds all Employees in employee_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj = 'hr.employee'
        args = [('active', '=', 't')]
        field = 'employee_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_transfer_journal_add(self, cr, uid, ids, context=None):
        """
        Adds all Transfer Journals in transfer_journal_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj = 'account.journal'
        args = [('type', 'in', ['cash', 'bank', 'cheque'])]
        field = 'transfer_journal_ids'
        return self._button_add(cr, uid, ids, obj, field, args, context=context)

    def button_partner_clear(self, cr, uid, ids, context=None):
        """
        Deletes partner_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.button_clear(cr, uid, ids, field='partner_ids', context=context)

    def button_employee_clear(self, cr, uid, ids, context=None):
        """
        Deletes employee_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.button_clear(cr, uid, ids, field='employee_ids', context=context)

    def button_transfer_journal_clear(self, cr, uid, ids, context=None):
        """
        Deletes transfer_journal_ids field content
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.button_clear(cr, uid, ids, field='transfer_journal_ids', context=context)

    def clean_up_search(self, cr, uid, ids, context=None):
        """
        Clean up objects that have no description.
        """
        if not context:
            context = {}
        cr.execute('''SELECT id FROM account_mcdb
        WHERE description is NULL AND
        create_date + interval '1' day < NOW();''')
        res = cr.fetchall()
        to_clean = [x[0] for x in res]
        self.unlink(cr, uid, to_clean)
        return True

    def _get_data_from_field(self, cr, uid, field, value, operator, context):
        """
        Depending on the field type, returns the value to take into account,
        and the new operator to use if the selection has been reversed: for ex. 'not in' or '!=' becomes ':'
        (NOT done for "simple" fields as fields.char because we can't "reversed" the selection in that case)
        Ex. for the value: for the domain ('ref', 'ilike', u'%RefTest%'): RefTest,
        for ('move_id.state', '=', u'draft'): 'Unposted',
        for ('is_reallocated', '=', '0): "False"
        for ('period_id', 'in', (2, 1)): Feb 2017, Jan 2017
        :param field: dict with all the data of the field
        :param value: ex: (2, 1)
        :param operator: ex: 'not in'...
        """
        if field and 'relation' not in field:
            # in case a list of values is used for a simple field, get the corresponding string
            if isinstance(value, list):
                value = ", ".join(["%s" % v for v in value])
        if field and field['type'] in ['char', 'text']:
            value = value.strip('%')  # remove the '%' added for ilike
        elif field and 'selection' in field:
            for f in field['selection']:
                if value == f[0]:  # key
                    value = f[1]  # value
                    break
        elif field and field['type'] == 'boolean':
            if operator == '!':
                value = value and _('False') or _('True')
                operator = ':'  # the selection has been reversed
            else:
                value = value and _('True') or _('False')
        elif field and 'relation' in field:
            if value is False:  # ex: ('reconcile_id', '=', False)
                if operator == '!=':
                    value = _('True')  # ex: ('employee_id', '!=', False)
                    operator = ':'  # the selection has been reversed
                else:
                    value = _('False')
            elif value is True:
                if operator == '!=':
                    value = _('False')
                    operator = ':'  # the selection has been reversed
                else:
                    value = _('True')
            else:
                rel_obj = self.pool.get(field['relation'])
                if isinstance(value, (int, long)):
                    value = [value]
                elif isinstance(value, tuple):
                    value = list(value)
                if rel_obj and isinstance(value, list):
                    if operator.lower() == 'not in':
                        # reverse the selection to display all the items not excluded
                        value = rel_obj.search(cr, uid, [('id', 'not in', value)], context=context)
                        operator = ':'  # the selection has been reversed
                    record_ids = rel_obj.browse(cr, uid, value, context=context)
                    values_list = []
                    for record in record_ids:
                        record_str = hasattr(record, 'code') and getattr(record, 'code') or \
                            hasattr(record, 'name') and getattr(record, 'name') or ''
                        values_list.append(record_str)
                    value = ', '.join(values_list)
        return value, operator

    def get_selection_from_domain(self, cr, uid, domain, model, context=None):
        """
        Returns a String corresponding to the domain in parameter:
        criteria separated with ";" and followed by ":" for the value.
        Adds "Related entries: True" if related_entries stored in context.
        """
        if context is None:
            context = {}
        dom_selections = []
        obj = self.pool.get(model)
        if obj:
            obj_data = obj.fields_get(cr, uid, '')  # data on all fields on aml or aal
            # map the composed filters with their corresponding titles
            composed_filters = {
                'account_id.user_type': _('Account types'),
                'general_account_id.user_type': _('Account types'),
                'move_id.state': _('Entry Status'),
                'account_id.category': _('Display'),
                'move_id.name': _('Sequence number'),
            }
            to_ignore = \
                ['&',  # always 'and' by default
                 '|',  # whenever there is a '|' in the domain, we keep only one field to determine the name in the header
                 'move_id.move_id.name', 'commitment_line_id.commit_id.name',  # only entry_sequence is kept
                 'move_id', 'move_id.is_manually_corrected',  # only is_reallocated is kept (in G/L Selector)
                 'period_id.number',  # the check on period number != 0 is not part of the user selection in the interface
                 'account_id.reconcile',  # only reconcile_id is kept (filter 'Unreconciled' in JI view)
                 ]
            if context.get('from', False) == 'account.move.line':
                to_ignore.remove('move_id')  # 'move_id' (Entry Sequence) should not be ignored if we come from the JI view
            for dom in domain:
                if dom[0] in to_ignore or len(dom) != 3:
                    continue
                # standard use case: simple fields
                title = value = ""
                operator = dom[1]
                if operator.lower() in ('in', '=', 'like', 'ilike'):
                    operator = ':'
                elif operator in ('>', '>='):
                    operator = " %s" % _("from:")
                elif operator in ('<', '<='):
                    operator = " %s" % _("to:")
                if '.' not in dom[0]:
                    field = obj_data[dom[0]]
                    title = _(field['string'])
                    value, operator = self._get_data_from_field(cr, uid, field, dom[2], operator, context)
                # composed filters
                elif dom[0] in composed_filters:
                    title = composed_filters[dom[0]]
                    # get the "second_obj" to use, for ex. for account_id.user_type => self.pool.get('account.account')
                    obj_name = dom[0].split('.')[0]
                    second_obj = 'relation' in obj_data[obj_name] and self.pool.get(obj_data[obj_name]['relation'])
                    if second_obj:
                        second_obj_data = second_obj.fields_get(cr, uid, '')  # data on all fields of the second obj
                        second_obj_field = second_obj_data[dom[0].split('.')[1]]
                        value, operator = self._get_data_from_field(cr, uid, second_obj_field, dom[2], operator, context)
                if title and operator and value:
                    dom_selections.append("%s%s %s" % (title, operator, value))
        if context.get('related_entries', []):
            related_entries_str = "%s: %s" % (_("Related entries"), _("True"))
            dom_selections.append(related_entries_str)
        return ' ; '.join(dom_selections)

    def export_pdf(self, cr, uid, ids, context=None):
        """
        Triggers the same export as from the "output.currency.for.export" wizard
        => gets data to use, puts it in a dict and passed it in param. of the wizard method as data_from_selector
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        aal_obj = self.pool.get('account.analytic.line')
        export_wizard_obj = self.pool.get('output.currency.for.export')
        domain = self._get_domain(cr, uid, ids, context)
        selector = self.browse(cr, uid, [ids[0]], fields_to_fetch=['model', 'display_in_output_currency'], context=context)[0]
        res_model = selector and selector.model or False
        header = self.get_selection_from_domain(cr, uid, domain, res_model, context=context)
        result_ids = []
        target_filename = 'selector'
        limit = 5000  # max for PDF + issue if a large number of entries is exported (cf US-661)
        if res_model == 'account.move.line':
            result_ids = aml_obj.search(cr, uid, domain, context=context, limit=limit)
            target_filename = 'GL Selector'
        elif res_model == 'account.analytic.line':
            result_ids = aal_obj.search(cr, uid, domain, context=context, limit=limit)
            target_filename = 'Analytic Selector'
        # add the related entries if needed
        if res_model in ('account.move.line', 'account.analytic.line') and context.get('related_entries', []):
            related_entry_ids = self.pool.get(res_model).get_related_entry_ids(cr, uid, entry_seqs=context['related_entries'], context=context) or []
            result_ids = list(set(result_ids + related_entry_ids))
        output_currency_id = False
        if selector.display_in_output_currency:
            output_currency_id = selector.display_in_output_currency.id
        data = {}
        data['ids'] = result_ids
        data['model'] = res_model
        data['export_format'] = 'pdf'
        data['output_currency_id'] = output_currency_id
        data['target_filename'] = target_filename
        data['header'] = header
        context['keep_open'] = 1
        a = export_wizard_obj.button_validate(cr, uid, result_ids, context=context, data_from_selector=data)
        a['datas']['keep_open'] = 1
        return a

    def load_mcdb_template(self, cr, buid, ids, context=None):
        """
        Loads a COPY of the template selected, without description (cf US-3030 the selector handled is overwritten when
        the user clicks on the Search button)
        """
        if context is None:
            context = {}
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        mcdb = ids and self.read(cr, uid, ids[0], ['template'], context=context)
        template_id = mcdb and mcdb['template'] and mcdb['template'][0]
        if not template_id:
            raise osv.except_osv(_('Error'), _('You have to choose a template to load.'))
        default_dict = {'description': '',
                        'copied_id': template_id,
                        'template': template_id,
                        'display_mcdb_load_button': False}
        copied_template_id = self.copy(cr, uid, template_id, default=default_dict, context=context)
        module = 'account_mcdb'
        if context.get('from', '') == 'account.analytic.line':
            view_name = 'account_mcdb_analytic_form'
        elif context.get('from', '') == 'combined.line':
            view_name = 'account_mcdb_combined_form'
        else:
            view_name = 'account_mcdb_form'
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view_name)
        view_id = view_id and view_id[1] or False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.mcdb',
            'view_type': 'form',
            'context': context,
            'res_id': copied_template_id,
            'view_mode': 'form,tree',  # to display the menu on the right
            'view_id': [view_id],
            'target': 'self',
        }

    def _format_data(self, data):
        """
        Formats the dictionary in parameter containing the data to use to create/write a selector:
        - removes the id, the values related to the template itself, and the user that shouldn't be modified
        - many2many fields: formats the values to make them look like [(6, 0, [1, 2])]
        - many2one fields: replaces the tuple looking like (1, u'FY 2018') by the related id
        """

        fields_to_del = [
            'id', 'copied_id', 'template', 'description',
            'template_name', 'user', 'display_mcdb_load_button',
            'write_uid', 'create_date', 'write_date'
        ]

        for f in fields_to_del:
            if f in data:
                del data[f]
        for i in data:
            if type(data[i]) == list:
                data[i] = [(6, 0, data[i])]
            elif type(data[i]) == tuple:
                data[i] = data[i][0]

    def edit_mcdb_template(self, cr, buid, ids, context=None):
        """
        Edits the values of the selector of which the loaded template is a copy (see load_mcdb_template method)
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        # get a dictionary containing ALL fields values of the selector
        data = ids and self.read(cr, uid, ids[0], context=context)
        copied_id = data and data['copied_id'] and data['copied_id'][0] or False
        if not copied_id:
            raise osv.except_osv(_('Error'), _('You have to load the template first.'))
        self._format_data(data)

        for field_to_clean in ('hq_template', 'synced'):
            if field_to_clean in data:
                del data[field_to_clean]

        return self.write(cr, uid, copied_id, data, context=context)

    def save_mcdb_template(self, cr, buid, ids, context=None):
        """
        Stores all the fields values under the template name chosen
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        # get a dictionary containing ALL fields values of the selector
        data = ids and self.read(cr, uid, ids[0], context=context)
        if data:
            template_name = data['template_name']
            if not template_name:
                raise osv.except_osv(_('Error'), _('You have to choose a template name.'))
            if self.search_exist(cr, uid, [('description', '=', template_name),
                                           ('user', '=', uid),
                                           ('model', '=', data.get('model', ''))], context=context):
                raise osv.except_osv(_('Error'), _('This template name already exists for the current user. Please choose another name.'))
            self._format_data(data)
            data.update({'description': template_name})  # store the name chosen as the "Query name"
            self.create(cr, uid, data, context=context)
        return True

    def delete_mcdb_template(self, cr, buid, ids, context=None):
        """
        Deletes the selector of which the loaded template is a copy (see load_mcdb_template method),
        and loads a new empty selector
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        # get the id of the template to delete
        data = ids and self.read(cr, uid, ids[0], ['copied_id'], context=context)
        copied_id = data and data['copied_id'] and data['copied_id'][0] or False
        if not copied_id:
            raise osv.except_osv(_('Error'), _('You have to choose a template to delete.'))
        self.unlink(cr, uid, copied_id, context=context)
        # create a new "empty" selector
        new_id = self.create(cr, uid, {'display_mcdb_load_button': True}, context=context)
        module = 'account_mcdb'
        if context.get('from', '') == 'account.analytic.line':
            view_name = 'account_mcdb_analytic_form'
        elif context.get('from', '') == 'combined.line':
            view_name = 'account_mcdb_combined_form'
        else:
            view_name = 'account_mcdb_form'
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view_name)
        view_id = view_id and view_id[1] or False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.mcdb',
            'view_type': 'form',
            'context': context,
            'res_id': new_id,
            'view_mode': 'form,tree',  # to display the menu on the right
            'view_id': [view_id],
            'target': 'self',
        }

    def combined_export(self, cr, uid, ids, format='pdf', context=None):
        """
        Generates the Combined Journals Report in 'pdf' or 'xls' format
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        bg_obj = self.pool.get('memory.background.report')
        if format == 'xls':
            report_name = 'combined.journals.report.xls'
        else:
            report_name = 'combined.journals.report.pdf'
        selector = self.read(cr, uid, ids[0], ['analytic_axis'], context=context)
        data = {
            'selector_id': ids[0],
            'analytic_axis': selector.get('analytic_axis', 'fp')
        }
        # make the report run in background
        background_id = bg_obj.create(cr, uid, {'file_name': 'Combined Journals Report',
                                                'report_name': report_name}, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2
        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': context,
        }

    def combined_export_xls(self, cr, uid, ids, context=None):
        """
        Generates the Combined Journals Report in Excel format
        """
        return self.combined_export(cr, uid, ids, format='xls', context=context)

    def combined_export_pdf(self, cr, uid, ids, context=None):
        """
        Generates the Combined Journals Report in PDF format
        """
        return self.combined_export(cr, uid, ids, format='pdf', context=context)


    def save_query(self, cr, buid, ids, context=None):
        """
        Save the values of the selector from HQ query
        """
        self.edit_mcdb_template(cr, buid, ids, context=context)
        return {'type': 'ir.actions.act_window_close', 'context': context}

account_mcdb()


class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        """
        For Search Views: in case "user_with_active_filter" is set in context, displays a Search View with a filter to
        select/de-select active users
        """
        if context is None:
            context = {}
        model_data_obj = self.pool.get('ir.model.data')
        if view_type == 'search' and context.get('user_with_active_filter'):
            view_id = model_data_obj.get_object_reference(cr, uid, 'account_mcdb', 'user_search_with_active_filter')
            view_id = view_id and view_id[1] or False
        res = super(res_users, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context,
                                                     toolbar=toolbar, submenu=submenu)
        return res


res_users()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
