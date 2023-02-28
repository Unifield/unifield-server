# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

import time
import datetime
from dateutil.relativedelta import relativedelta
from os.path import join as opj
from operator import itemgetter

from tools.translate import _
from osv import fields, osv
import netsvc
import tools

class account_installer(osv.osv_memory):
    _name = 'account.installer'
    _inherit = 'res.config.installer'

    def _get_default_accounts(self, cr, uid, context=None):
        accounts = [{'acc_name': 'Current', 'account_type': 'bank'},
                    {'acc_name': 'Deposit', 'account_type': 'bank'},
                    {'acc_name': 'Cash', 'account_type': 'cash'}]
        return accounts

    def _get_charts(self, cr, uid, context=None):
        modules = self.pool.get('ir.module.module')
        ids = modules.search(cr, uid, [('category_id', '=', 'Account Charts')], context=context)
        charts = list(
            sorted(((m.name, m.shortdesc)
                    for m in modules.browse(cr, uid, ids, context=context)),
                   key=itemgetter(1)))
        charts.insert(0, ('configurable', 'Generic Chart Of Account'))
        return charts

    _columns = {
        # Accounting
        'charts': fields.selection(_get_charts, 'Chart of Accounts',
                                   required=True,
                                   help="Installs localized accounting charts to match as closely as "
                                   "possible the accounting needs of your company based on your "
                                   "country."),
        'date_start': fields.date('Start Date', required=True),
        'date_stop': fields.date('End Date', required=True),
        'period': fields.selection([('month', 'Monthly'), ('3months','3 Monthly')], 'Periods', required=True),
        'bank_accounts_id': fields.one2many('account.bank.accounts.wizard', 'bank_account_id', 'Your Bank and Cash Accounts'),
        'sale_tax': fields.float('Sale Tax(%)'),
        'purchase_tax': fields.float('Purchase Tax(%)'),
        'company_id': fields.many2one('res.company', 'Company'),
    }

    def _default_company(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id and user.company_id.id or False

    def _get_default_charts(self, cr, uid, context=None):
        module_name = False
        company_id = self._default_company(cr, uid, context=context)
        company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
        address_id = self.pool.get('res.partner').address_get(cr, uid, [company.partner_id.id])
        if address_id['default']:
            address = self.pool.get('res.partner.address').browse(cr, uid, address_id['default'], context=context)
            code = address.country_id.code
            module_name = (code and 'l10n_' + code.lower()) or False
        if module_name:
            module_id = self.pool.get('ir.module.module').search(cr, uid, [('name', '=', module_name)], context=context)
            if module_id:
                return module_name
        return 'configurable'

    _defaults = {
        'date_start': lambda *a: time.strftime('%Y-01-01'),
        'date_stop': lambda *a: time.strftime('%Y-12-31'),
        'period': 'month',
        'sale_tax': 0.0,
        'purchase_tax': 0.0,
        'company_id': _default_company,
        'bank_accounts_id': _get_default_accounts,
        'charts': _get_default_charts
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(account_installer, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        configured_cmp = []
        unconfigured_cmp = []
        cmp_select = []
        company_ids = self.pool.get('res.company').search(cr, uid, [], context=context)
        #display in the widget selection of companies, only the companies that haven't been configured yet (but don't care about the demo chart of accounts)
        cr.execute("SELECT company_id FROM account_account WHERE active = 't' AND account_account.parent_id IS NULL AND name != %s", ("Chart For Automated Tests",))
        configured_cmp = [r[0] for r in cr.fetchall()]
        unconfigured_cmp = list(set(company_ids)-set(configured_cmp))
        for field in res['fields']:
            if field == 'company_id':
                res['fields'][field]['domain'] = [('id','in',unconfigured_cmp)]
                res['fields'][field]['selection'] = [('', '')]
                if unconfigured_cmp:
                    cmp_select = [(line.id, line.name) for line in self.pool.get('res.company').browse(cr, uid, unconfigured_cmp)]
                    res['fields'][field]['selection'] = cmp_select
        return res

    def on_change_tax(self, cr, uid, id, tax):
        return {'value': {'purchase_tax': tax}}

    def on_change_start_date(self, cr, uid, id, start_date=False):
        if start_date:
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end_date = (start_date + relativedelta(months=12)) - relativedelta(days=1)
            return {'value': {'date_stop': end_date.strftime('%Y-%m-%d')}}
        return {}

    def generate_configurable_chart(self, cr, uid, ids, context=None):
        obj_acc = self.pool.get('account.account')
        obj_journal = self.pool.get('account.journal')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        mod_obj = self.pool.get('ir.model.data')
        obj_sequence = self.pool.get('ir.sequence')
        property_obj = self.pool.get('ir.property')
        fields_obj = self.pool.get('ir.model.fields')

        record = self.browse(cr, uid, ids, context=context)[0]

        if context is None:
            context = {}
        company_id = self.browse(cr, uid, ids, context=context)[0].company_id
        seq_journal = True


        #deactivate the parent_store functionnality on account_account for rapidity purpose
        ctx = context and context.copy() or {}
        ctx['defer_parent_store_computation'] = True

        #reactivate the parent_store functionality on account_account
        obj_acc._parent_store_compute(cr)


        # Creating Journals Sales and Purchase
        vals_journal = {}
        data_id = mod_obj.search(cr, uid, [('model', '=', 'account.journal.view'), ('name', '=', 'account_sp_journal_view')], context=context)
        data = mod_obj.browse(cr, uid, data_id[0], context=context)
        view_id = data.res_id
        seq_id = obj_sequence.search(cr,uid,[('name', '=', 'Account Journal')], context=context)[0]

        if seq_journal:
            seq_sale = {
                'name': 'Sale Journal',
                'code': 'account.journal',
                'prefix': 'SAJ/%(year)s/',
                'padding': 3,
                'company_id': company_id.id
            }
            seq_id_sale = obj_sequence.create(cr, uid, seq_sale, context=context)
            seq_purchase = {
                'name': 'Purchase Journal',
                'code': 'account.journal',
                'prefix': 'EXJ/%(year)s/',
                'padding': 3,
                'company_id': company_id.id
            }
            seq_id_purchase = obj_sequence.create(cr, uid, seq_purchase, context=context)
            seq_refund_sale = {
                'name': 'Sales Refund Journal',
                'code': 'account.journal',
                'prefix': 'SCNJ/%(year)s/',
                'padding': 3,
                'company_id': company_id.id
            }
            seq_id_sale_refund = obj_sequence.create(cr, uid, seq_refund_sale, context=context)
            seq_refund_purchase = {
                'name': 'Purchase Refund Journal',
                'code': 'account.journal',
                'prefix': 'ECNJ/%(year)s/',
                'padding': 3,
                'company_id': company_id.id
            }
            seq_id_purchase_refund = obj_sequence.create(cr, uid, seq_refund_purchase, context=context)
        else:
            seq_id_sale = seq_id
            seq_id_purchase = seq_id
            seq_id_sale_refund = seq_id
            seq_id_purchase_refund = seq_id

        vals_journal['view_id'] = view_id

        #Sales Journal
        analitical_sale_ids = analytic_journal_obj.search(cr, uid, [('type','=','sale')], context=context)
        analitical_journal_sale = analitical_sale_ids and analitical_sale_ids[0] or False

        vals_journal.update({
            'name': _('Sales Journal'),
            'type': 'sale',
            'code': _('SAJ'),
            'sequence_id': seq_id_sale,
            'analytic_journal_id': analitical_journal_sale,
            'company_id': company_id.id
        })

        obj_journal.create(cr, uid, vals_journal, context=context)

        # Purchase Journal
        analitical_purchase_ids = analytic_journal_obj.search(cr, uid, [('type', '=', 'purchase')], context=context)
        analitical_journal_purchase = analitical_purchase_ids and analitical_purchase_ids[0] or False

        vals_journal.update({
            'name': _('Purchase Journal'),
            'type': 'purchase',
            'code': _('EXJ'),
            'sequence_id': seq_id_purchase,
            'analytic_journal_id': analitical_journal_purchase,
            'company_id': company_id.id
        })


        obj_journal.create(cr, uid, vals_journal, context=context)
        # Creating Journals Sales Refund and Purchase Refund
        vals_journal = {}
        data_id = mod_obj.search(cr, uid, [('model', '=', 'account.journal.view'), ('name', '=', 'account_sp_refund_journal_view')], context=context)
        data = mod_obj.browse(cr, uid, data_id[0], context=context)
        view_id = data.res_id

        #Sales Refund Journal
        vals_journal = {
            'view_id': view_id,
            'name': _('Sales Refund Journal'),
            'type': 'sale_refund',
            'refund_journal': True,
            'code': _('SCNJ'),
            'sequence_id': seq_id_sale_refund,
            'analytic_journal_id': analitical_journal_sale,
            'company_id': company_id.id
        }

        obj_journal.create(cr, uid, vals_journal, context=context)

        # Purchase Refund Journal
        vals_journal = {
            'view_id': view_id,
            'name': _('Purchase Refund Journal'),
            'type': 'purchase_refund',
            'refund_journal': True,
            'code': _('ECNJ'),
            'sequence_id': seq_id_purchase_refund,
            'analytic_journal_id': analitical_journal_purchase,
            'company_id': company_id.id
        }

        obj_journal.create(cr, uid, vals_journal, context=context)

        #create the properties
        todo_list = [
            ('property_account_expense_categ', 'product.category', 'account.account'),
            ('property_account_income_categ', 'product.category', 'account.account'),
            ('property_account_expense', 'product.template', 'account.account'),
            ('property_account_income', 'product.template', 'account.account'),
            ('property_reserve_and_surplus_account', 'res.company', 'account.account'),
        ]

        for record in todo_list:
            r = []
            r = property_obj.search(cr, uid, [('name', '=', record[0]), ('company_id', '=', company_id.id)], context=context)
            field = fields_obj.search(cr, uid, [('name', '=', record[0]), ('model', '=', record[1]), ('relation', '=', record[2])], context=context)
            vals = {
                'name': record[0],
                'company_id': company_id.id,
                'fields_id': field[0],
                'value': False,
            }
            if r:
                #the property exist: modify it
                property_obj.write(cr, uid, r, vals, context=context)
            else:
                #create the property
                property_obj.create(cr, uid, vals, context=context)


    def execute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        super(account_installer, self).execute(cr, uid, ids, context=context)
        fy_obj = self.pool.get('account.fiscalyear')
        obj_acc = self.pool.get('account.account')
        obj_tax_code = self.pool.get('account.tax.code')
        obj_tax = self.pool.get('account.tax')
        obj_product = self.pool.get('product.product')
        ir_values = self.pool.get('ir.values')
        record = self.browse(cr, uid, ids, context=context)[0]
        company_id = record.company_id

        if not company_id:
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            raise osv.except_osv(_('Warning'), _('It seems that there is no company selected or %s already has an accounting configuration. If you want to set the accounting configuration for any company other than the main one, please make sure that you belong to the group Usability/Extended View') % (user.company_id.name))

        for res in self.read(cr, uid, ids, context=context):
            if record.charts == 'configurable':
                fp = tools.file_open(opj('account', 'configurable_account_chart.xml'))
                tools.convert_xml_import(cr, 'account', fp, {}, 'init', True, None)
                fp.close()
                self.generate_configurable_chart(cr, uid, ids, context=context)
                s_tax = (res.get('sale_tax', 0.0))/100
                p_tax = (res.get('purchase_tax', 0.0))/100
                tax_val = {}
                default_tax = []

                pur_taxcode_parent_id = False
                pur_taxcode_paid_parent_id = False

                sale_taxcode_parent_id = False

                sale_taxcode_paid_parent_id = False

                if s_tax*100 > 0.0:
                    tax_account_ids = obj_acc.search(cr, uid, [('name', '=', 'Tax Received')], context=context)
                    sales_tax_account_id = tax_account_ids and tax_account_ids[0] or False
                    vals_tax_code = {
                        'name': 'TAX%s%%'%(s_tax*100),
                        'code': 'TAX%s%%'%(s_tax*100),
                        'company_id': company_id.id,
                        'sign': 1,
                        'parent_id': sale_taxcode_parent_id
                    }
                    new_tax_code = obj_tax_code.create(cr, uid, vals_tax_code, context=context)

                    vals_paid_tax_code = {
                        'name': 'TAX Received %s%%'%(s_tax*100),
                        'code': 'TAX Received %s%%'%(s_tax*100),
                        'company_id': company_id.id,
                        'sign': 1,
                        'parent_id': sale_taxcode_paid_parent_id
                    }
                    new_paid_tax_code = obj_tax_code.create(cr, uid, vals_paid_tax_code, context=context)

                    sales_tax = obj_tax.create(cr, uid,
                                               {'name': 'TAX %s%%'%(s_tax*100),
                                                'amount': s_tax,
                                                'base_code_id': new_tax_code,
                                                'tax_code_id': new_paid_tax_code,
                                                'type_tax_use': 'sale',
                                                'account_collected_id': sales_tax_account_id,
                                                'account_paid_id': sales_tax_account_id
                                                }, context=context)
                    default_account_ids = obj_acc.search(cr, uid, [('name', '=', 'Product Sales')], context=context)
                    if default_account_ids:
                        obj_acc.write(cr, uid, default_account_ids, {'tax_ids': [(6, 0, [sales_tax])]}, context=context)
                    tax_val.update({'taxes_id': [(6, 0, [sales_tax])]})
                    default_tax.append(('taxes_id', sales_tax))
                if p_tax*100 > 0.0:
                    tax_account_ids = obj_acc.search(cr, uid, [('name', '=', 'Tax Paid')], context=context)
                    purchase_tax_account_id = tax_account_ids and tax_account_ids[0] or False
                    vals_tax_code = {
                        'name': 'TAX%s%%'%(p_tax*100),
                        'code': 'TAX%s%%'%(p_tax*100),
                        'company_id': company_id.id,
                        'sign': 1,
                        'parent_id': pur_taxcode_parent_id
                    }
                    new_tax_code = obj_tax_code.create(cr, uid, vals_tax_code, context=context)
                    vals_paid_tax_code = {
                        'name': 'TAX Paid %s%%'%(p_tax*100),
                        'code': 'TAX Paid %s%%'%(p_tax*100),
                        'company_id': company_id.id,
                        'sign': 1,
                        'parent_id': pur_taxcode_paid_parent_id
                    }
                    new_paid_tax_code = obj_tax_code.create(cr, uid, vals_paid_tax_code, context=context)

                    purchase_tax = obj_tax.create(cr, uid,
                                                  {'name': 'TAX%s%%'%(p_tax*100),
                                                   'description': 'TAX%s%%'%(p_tax*100),
                                                   'amount': p_tax,
                                                   'base_code_id': new_tax_code,
                                                   'tax_code_id': new_paid_tax_code,
                                                   'type_tax_use': 'purchase',
                                                   'account_collected_id': purchase_tax_account_id,
                                                   'account_paid_id': purchase_tax_account_id
                                                   }, context=context)
                    default_account_ids = obj_acc.search(cr, uid, [('name', '=', 'Expenses')], context=context)
                    if default_account_ids:
                        obj_acc.write(cr, uid, default_account_ids, {'tax_ids': [(6, 0, [purchase_tax])]}, context=context)
                    tax_val.update({'supplier_taxes_id': [(6 ,0, [purchase_tax])]})
                    default_tax.append(('supplier_taxes_id', purchase_tax))
                if tax_val:
                    product_ids = obj_product.search(cr, uid, [], context=context)
                    for product in obj_product.browse(cr, uid, product_ids, context=context):
                        obj_product.write(cr, uid, product.id, tax_val, context=context)
                    for name, value in default_tax:
                        ir_values.set(cr, uid, key='default', key2=False, name=name, models =[('product.product', False)], value=[value])

            if 'date_start' in res and 'date_stop' in res:
                f_ids = fy_obj.search(cr, uid, [('date_start', '<=', res['date_start']), ('date_stop', '>=', res['date_stop']), ('company_id', '=', res['company_id'])], context=context)
                if not f_ids:
                    name = code = res['date_start'][:4]
                    if int(name) != int(res['date_stop'][:4]):
                        name = res['date_start'][:4] +'-'+ res['date_stop'][:4]
                        code = res['date_start'][2:4] +'-'+ res['date_stop'][2:4]
                    vals = {
                        'name': name,
                        'code': code,
                        'date_start': res['date_start'],
                        'date_stop': res['date_stop'],
                        'company_id': res['company_id']
                    }
                    fiscal_id = fy_obj.create(cr, uid, vals, context=context)
                    if res['period'] == 'month':
                        fy_obj.create_period(cr, uid, [fiscal_id])
                    elif res['period'] == '3months':
                        fy_obj.create_period3(cr, uid, [fiscal_id])


    def modules_to_install(self, cr, uid, ids, context=None):
        modules = super(account_installer, self).modules_to_install(
            cr, uid, ids, context=context)
        chart = self.read(cr, uid, ids, ['charts'],
                          context=context)[0]['charts']
        self.logger.notifyChannel(
            'installer', netsvc.LOG_DEBUG,
            'Installing chart of accounts %s'%chart)
        return modules | set([chart])

account_installer()

class account_bank_accounts_wizard(osv.osv_memory):
    _name='account.bank.accounts.wizard'

    _columns = {
        'acc_name': fields.char('Account Name.', size=64, required=True),
        'bank_account_id': fields.many2one('account.installer', 'Bank Account', required=True),
        'currency_id': fields.many2one('res.currency', 'Secondary Currency', help="Forces all moves for this account to have this secondary currency."),
        'account_type': fields.selection([('cash','Cash'), ('check','Check'), ('bank','Bank')], 'Account Type', size=32),
    }

account_bank_accounts_wizard()

class account_installer_modules(osv.osv_memory):
    _name = 'account.installer.modules'
    _inherit = 'res.config.installer'
    _columns = {
        'account_analytic_plans': fields.boolean('Multiple Analytic Plans',
                                                 help="Allows invoice lines to impact multiple analytic accounts "
                                                 "simultaneously."),
        'account_payment': fields.boolean('Suppliers Payment Management',
                                          help="Streamlines invoice payment and creates hooks to plug "
                                          "automated payment systems in."),
        'account_followup': fields.boolean('Followups Management',
                                           help="Helps you generate reminder letters for unpaid invoices, "
                                           "including multiple levels of reminding and customized "
                                           "per-partner policies."),
        'account_voucher': fields.boolean('Voucher Management',
                                          help="Account Voucher module includes all the basic requirements of "
                                          "Voucher Entries for Bank, Cash, Sales, Purchase, Expenses, Contra, etc... "),
        'account_anglo_saxon': fields.boolean('Anglo-Saxon Accounting',
                                              help="This module will support the Anglo-Saxons accounting methodology by "
                                              "changing the accounting logic with stock transactions."),
    }

    _defaults = {
        'account_voucher': True,
    }

account_installer_modules()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
