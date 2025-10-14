#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from time import strftime
from tools.translate import _
from tools.misc import ustr
from tools.misc import _max_amount
from datetime import datetime
from msf_partner import PARTNER_TYPE
import re
import netsvc


import decimal_precision as dp


class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_invoice_report_name(self, cr, uid, ids, context=None):
        '''
        Returns the name of the invoice according to its type
        '''
        if isinstance(ids, list):
            ids = ids[0]

        inv = self.browse(cr, uid, ids, context=context)
        inv_name = inv.number or inv.name or 'No_description'
        prefix = 'STV_'

        if inv.doc_type == 'cr':
            prefix = 'CR_'
        elif inv.doc_type == 'sr':
            prefix = 'SR_'
        elif inv.doc_type == 'stv':
            prefix = 'STV_'
        elif inv.doc_type == 'dn':
            prefix = 'DN_'
        elif inv.doc_type == 'ivo':
            prefix = 'IVO_'
        elif inv.doc_type == 'si':
            prefix = 'SI_'
        elif inv.doc_type == 'ivi':
            prefix = 'IVI_'
        elif inv.doc_type == 'di':
            prefix = 'DI_'
        elif inv.doc_type == 'donation':
            prefix = 'DON_'
        elif inv.doc_type == 'str':
            prefix = 'STR_'
        elif inv.doc_type == 'isi':
            prefix = 'ISI_'
        elif inv.doc_type == 'isr':
            prefix = 'ISR_'
        return '%s%s' % (prefix, inv_name)

    def _get_journal(self, cr, uid, context=None):
        """
        Returns the journal to be used by default, depending on the doc type of the selected invoice
        """
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('inv_doc_type', '=', True), ('is_active', '=', True)], order='id', limit=1, context=context)
        return res and res[0] or False

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Returns False for all ids
        """
        res = {}
        for i in ids:
            res[i] = False
        return res

    def _search_ready_for_import_in_debit_note(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        account_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account and \
            self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account.id or False
        if not account_id:
            raise osv.except_osv(_('Error'), _('No default account for import invoice on Debit Note!'))
        dom1 = [
            ('account_id','=',account_id),
            ('reconciled','=',False),
            ('state', '=', 'open'),
            ('type', '=', 'out_invoice'),
            ('journal_id.type', 'not in', ['migration']),
        ]
        return dom1+[('is_debit_note', '=', False)]

    def _get_int_journal_for_current_instance(self, cr, uid, context=None):
        """
        Returns the id of the Intermission journal of the current instance if it exists, else returns False.
        """
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        int_journal_domain = [('type', '=', 'intermission'), ('is_current_instance', '=', True)]
        int_journal_id = journal_obj.search(cr, uid, int_journal_domain, order='id', limit=1, context=context)
        return int_journal_id and int_journal_id[0] or False

    def _get_fake_m2o_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get many2one field content
        """
        res = {}
        name = field_name.replace("fake_", '')
        for i in self.browse(cr, uid, ids):
            if context and context.get('is_intermission', False):
                res[i.id] = False
                if name == 'account_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.intermission_default_counterpart:
                        res[i.id] = user[0].company_id.intermission_default_counterpart.id
                elif name == 'journal_id':
                    int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                    if int_journal_id:
                        res[i.id] = int_journal_id
                elif name == 'currency_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.currency_id:
                        res[i.id] = user[0].company_id.currency_id.id
            else:
                res[i.id] = getattr(i, name, False) and getattr(getattr(i, name, False), 'id', False) or False
        return res

    def _get_have_donation_certificate(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        If this invoice have a stock picking in which there is a Certificate of Donation, return True. Otherwise return False.
        """
        res = {}
        for i in self.browse(cr, uid, ids):
            res[i.id] = False
            if i.picking_id:
                a_ids = self.pool.get('ir.attachment').search(cr, uid, [('res_model', '=', 'stock.picking'), ('res_id', '=', i.picking_id.id), ('description', '=', 'Certificate of Donation')])
                if a_ids:
                    res[i.id] = True
        return res

    def _get_virtual_fields(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get fields in order to transform them into 'virtual fields" (kind of field duplicity):
         - currency_id
         - account_id
         - supplier
        """
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = {'virtual_currency_id': inv.currency_id.id or False, 'virtual_account_id': inv.account_id.id or False,
                           'virtual_partner_id': inv.partner_id.id or False}
        return res

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _get_line_count(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns the number of lines for each selected invoice
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for inv in self.browse(cr, uid, ids, fields_to_fetch=['invoice_line'], context=context):
            res[inv.id] = len(inv.invoice_line)
        return res

    def _get_invoice_type_list(self, cr, uid, context=None):
        """
        Returns the list of possible types for the account.invoice document.
        """
        return [('dn', _('Debit Note')),
                ('donation', _('Donation')),
                ('ivi', _('Intermission Voucher IN')),
                ('ivo', _('Intermission Voucher OUT')),
                ('di', _('Direct Invoice')),
                ('si', _('Supplier Invoice')),
                ('sr', _('Supplier Refund')),
                ('stv', _('Stock Transfer Voucher')),
                ('cr', _('Customer Refund')),
                ('str', _('Stock Transfer Refund')),
                ('isi', _('Intersection Supplier Invoice')),
                ('isr', _('Intersection Supplier Refund')),
                ('unknown', _('Unknown')),
                ]

    _invoice_action_act_window = {
        'dn': 'account_override.action_debit_note',
        'donation': 'account_override.action_inkind_donation',
        'ivi': 'account_override.action_intermission_in',
        'ivo': 'account_override.action_intermission_out',
        'di': 'register_accounting.action_direct_invoice',
        'si': 'account.action_invoice_tree2',
        'sr': 'account.action_invoice_tree4',
        'stv': 'account.action_invoice_tree1',
        'cr': 'account.action_invoice_tree3',
        'str': 'account.action_str',
        'isi': 'account.action_isi',
        'isr': 'account.action_isr',
    }

    def _get_invoice_act_window(self, cr, uid, invoice_id, views_order=None, context=None):
        inv_doc_type = self.read(cr, uid, invoice_id, ['doc_type'], context=context)['doc_type']
        return self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, self._invoice_action_act_window[inv_doc_type], views_order=views_order, context=context)

    def _get_doc_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Returns a dict with key = id of the account.invoice, and value = doc type (see the list of types in _get_invoice_type_list).
        If a "real_doc_type" exists: it is used. Otherwise: the doc type is deduced from the other fields.
        """
        res = {}
        fields = ['real_doc_type', 'type', 'is_debit_note', 'is_inkind_donation', 'is_intermission', 'is_direct_invoice']
        for inv in self.browse(cr, uid, ids, fields_to_fetch=fields, context=context):
            inv_type = 'unknown'
            if inv.real_doc_type:  # str, isi, isr...
                inv_type = inv.real_doc_type
            elif inv.is_debit_note:
                if inv.type == 'out_invoice':
                    inv_type = 'dn'  # Debit Note
            elif inv.is_inkind_donation:
                if inv.type == 'in_invoice':
                    inv_type = 'donation'
            elif inv.is_intermission:
                if inv.type == 'in_invoice':
                    inv_type = 'ivi'  # Intermission Voucher In
                elif inv.type == 'out_invoice':
                    inv_type = 'ivo'  # Intermission Voucher Out
            elif inv.type == 'in_invoice':
                if inv.is_direct_invoice:
                    inv_type = 'di'  # Direct Invoice
                else:
                    inv_type = 'si'  # Supplier Invoice
            elif inv.type == 'in_refund':
                inv_type = 'sr'  # Supplier Refund
            elif inv.type == 'out_invoice':
                inv_type = 'stv'  # Stock Transfer Voucher
            elif inv.type == 'out_refund':
                inv_type = 'cr'  # Customer Refund
            res[inv.id] = inv_type
        return res

    def _get_dom_by_doc_type(self, doc_type):
        """
        Returns the domain matching with the doc type (see the list of types in _get_invoice_type_list).
        """
        if doc_type in ('str', 'isi', 'isr'):
            dom = [('real_doc_type', '=', doc_type)]
        elif doc_type == 'dn':  # Debit Note
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'out_invoice'),
                   ('is_debit_note', '!=', False), ('is_inkind_donation', '=', False)]
        elif doc_type == 'donation':
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'in_invoice'),
                   ('is_debit_note', '=', False), ('is_inkind_donation', '=', True)]
        elif doc_type == 'ivi':  # Intermission Voucher In
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'in_invoice'), ('is_debit_note', '=', False),
                   ('is_inkind_donation', '=', False), ('is_intermission', '=', True)]
        elif doc_type == 'ivo':  # Intermission Voucher Out
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'out_invoice'), ('is_debit_note', '=', False),
                   ('is_inkind_donation', '=', False), ('is_intermission', '=', True)]
        elif doc_type == 'di':  # Direct Invoice
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', ('real_doc_type', '=', False), ('type', '=', 'in_invoice'), ('is_direct_invoice', '!=', False)]
        elif doc_type == 'si':  # Supplier Invoice
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'in_invoice'), ('is_direct_invoice', '=', False),
                   ('is_inkind_donation', '=', False), ('is_debit_note', '=', False), ('is_intermission', '=', False)]
        elif doc_type == 'sr':  # Supplier Refund
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', ('real_doc_type', '=', False), ('type', '=', 'in_refund')]
        elif doc_type == 'stv':  # Stock Transfer Voucher
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', '&', '&', '&',
                   ('real_doc_type', '=', False), ('type', '=', 'out_invoice'), ('is_debit_note', '=', False),
                   ('is_inkind_donation', '=', False), ('is_intermission', '=', False)]
        elif doc_type == 'cr':  # Customer Refund
            dom = ['|',
                   ('real_doc_type', '=', doc_type),
                   '&', ('real_doc_type', '=', False), ('type', '=', 'out_refund')]
        else:  # "unknown" or any undefined type
            dom = [('id', '=', 0)]
        return dom

    def _search_doc_type(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain to get all invoices matching the selected doc types (see the list of types in _get_invoice_type_list).
        """
        if not args:
            return []
        dom = [('id', '=', 0)]
        if not args[0] or len(args[0]) < 3 or args[0][1] not in ('=', 'in'):
            raise osv.except_osv(_('Error'), _('Filter not implemented yet.'))
        if args[0][1] == '=' and args[0][2]:
            doc_type = args[0][2]
            dom = self._get_dom_by_doc_type(doc_type)
        if args[0][1] == 'in' and args[0][2] and isinstance(args[0][2], (list, tuple)):
            dom = []
            for i in range(len(args[0][2]) - 1):
                dom.append('|')
            for doc_type in args[0][2]:
                dom.extend(self._get_dom_by_doc_type(doc_type))
        return dom

    def _search_open_fy(self, cr, uid, obj, name, args, context):
        """
        Returns a domain with:
        - Draft Invoices: all
        - Cancelled Invoices: those without date or those with a date within an Open Fiscal Year
        - Other Invoices: those with a date within an Open Fiscal Year.

        Example of domain generated:
        dom = [
         '|', '|',
         ('state', '=', 'draft'),
         '&', ('state', '=', 'cancel'), ('date_invoice', '=', False),
         '&',
         '&', ('state', '!=', 'draft'), ('date_invoice', '!=', False),
         '|', '|',
         '&', ('date_invoice', '>=', '2020-01-01'), ('date_invoice', '<=', '2020-12-31'),
         '&', ('date_invoice', '>=', '2021-01-01'), ('date_invoice', '<=', '2021-12-31'),
         '&', ('date_invoice', '>=', '2022-01-01'), ('date_invoice', '<=', '2022-12-31'),
        ]
        """
        if not args:
            return []
        if args[0][1] != '=' or not args[0][2] or not args[0][2] is True:
            raise osv.except_osv(_('Error'), _('Filter not implemented yet.'))
        if context is None:
            context = {}
        fy_obj = self.pool.get('account.fiscalyear')
        open_fy_ids = fy_obj.search(cr, uid, [('state', '=', 'draft')], order='NO_ORDER', context=context)  # "draft" = "Open" in the interface
        if open_fy_ids:
            dom = [
                '|', '|',
                ('state', '=', 'draft'),
                '&', ('state', '=', 'cancel'), ('date_invoice', '=', False),
                '&',
                '&', ('state', '!=', 'draft'), ('date_invoice', '!=', False),
            ]
            for i in range(len(open_fy_ids) - 1):
                dom.append('|')
            for open_fy in fy_obj.browse(cr, uid, open_fy_ids, fields_to_fetch=['date_start', 'date_stop'], context=context):
                dom.append('&')
                dom.append(('date_invoice', '>=', open_fy.date_start))
                dom.append(('date_invoice', '<=', open_fy.date_stop))
        else:
            dom = ['|', ('state', '=', 'draft'), '&', ('state', '=', 'cancel'), ('date_invoice', '=', False)]
        return dom

    def _get_fiscalyear(self, cr, uid, ids, field_name=None, arg=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        fy_obj = self.pool.get('account.fiscalyear')
        for inv in self.browse(cr, uid, ids, fields_to_fetch=['date_invoice'], context=context):
            fy_id = fy_obj.search(cr, uid, [('date_start', '<=', inv.date_invoice), ('date_stop', '>=', inv.date_invoice)], context=context)[0]
            if fy_id:
                res[inv.id] = fy_id
        return res

    def _get_search_by_fiscalyear(self, cr, uid, obj=None, name=None, args=None, context=None):
        if not args:
            return []
        if not args[0] or len(args[0]) < 3 or args[0][1] != '=':
            raise osv.except_osv(_('Error'), _('Filter not implemented yet.'))
        if context is None:
            context = {}
        fy_obj = self.pool.get('account.fiscalyear')
        dom = []
        if args[0][1] == '=' and args[0][2]:
            fy_id = args[0][2]
            fy = fy_obj.browse(cr, uid, fy_id, fields_to_fetch=['date_start', 'date_stop'], context=context)
            dom = [('date_invoice', '>=', fy.date_start), ('date_invoice', '<=', fy.date_stop)]
        return dom

    def _get_customer_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Add the customer name information as it is on the PO source of the supplier invoice
        """
        res = {}
        for inv in self.browse(cr, uid, ids):
            res[inv.id] = False
            if inv.picking_id and inv.picking_id.purchase_id and inv.picking_id.purchase_id.dest_partner_names:
                res[inv.id] = inv.picking_id.purchase_id.dest_partner_names
        return res

    _columns = {
        'sequence_id': fields.many2one('ir.sequence', string='Lines Sequence', ondelete='cascade',
                                       help="This field contains the information related to the numbering of the lines of this order."),
        'date_invoice': fields.date('Posting Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                            'inv_close':[('readonly',True)], 'done':[('readonly',True)]}, select=True),
        'document_date': fields.date('Document Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
                                                              'inv_close':[('readonly',True)], 'done':[('readonly',True)]}, select=True),
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'is_inkind_donation': fields.boolean(string="Is an In-kind Donation?"),
        'is_intermission': fields.boolean(string="Is an Intermission Voucher?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean",
                                                          method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
        'partner_move_line': fields.one2many('account.move.line', 'invoice_partner_link', string="Partner move line", readonly=True),
        'fake_journal_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.journal", string="Journal", hide_default_menu=True, readonly="True"),
        'have_donation_certificate': fields.function(_get_have_donation_certificate, method=True, type='boolean', string="Have a Certificate of donation?"),
        'purchase_list': fields.boolean(string='Purchase List ?', help='Check this box if the invoice comes from a purchase list', readonly=True, states={'draft':[('readonly',False)]}),
        'virtual_currency_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Currency",
                                               type='many2one', relation="res.currency", readonly=True),
        'virtual_account_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Account",
                                              type='many2one', relation="account.account", readonly=True),
        'virtual_partner_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Supplier",
                                              type='many2one', relation="res.partner", readonly=True),
        'register_line_ids': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register Lines"),
        'is_direct_invoice': fields.boolean("Is direct invoice?", readonly=True),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False,
                                              states={'draft':[('readonly',False)]}),
        'register_posting_date': fields.date(string="Register posting date for Direct Invoice", required=False),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'st_lines': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register lines", readonly=True, help="Register lines that have a link to this invoice."),
        'is_merged_by_account': fields.boolean("Is merged by account (deprecated)"),
        'partner_type': fields.related('partner_id', 'partner_type', string='Partner Type', type='selection',
                                       selection=PARTNER_TYPE, readonly=True, store=False),
        'refunded_invoice_id': fields.many2one('account.invoice', string='Refunded Invoice', readonly=True,
                                               help='The refunded invoice which has generated this document'),  # 2 inv types for Refund Modify
        'line_count': fields.function(_get_line_count, string='Line count', method=True, type='integer', store=False),
        'real_doc_type': fields.selection(_get_invoice_type_list, 'Real Document Type', readonly=True),
        'doc_type': fields.function(_get_doc_type, method=True, type='selection', selection=_get_invoice_type_list,
                                    string='Document Type', store=False, fnct_search=_search_doc_type),
        'open_fy': fields.function(_get_fake, method=True, type='boolean', string='Open Fiscal Year', store=False,
                                   fnct_search=_search_open_fy),
        'fiscalyear_id': fields.function(_get_fiscalyear, fnct_search=_get_search_by_fiscalyear, type='many2one', obj='account.fiscalyear', method=True, store=False, string='Fiscal year', readonly=True),
        'customers': fields.function(_get_customer_id, method=True, type='char', size=1024, string='Customers', readonly=True, store=False),
    }

    _defaults = {
        'journal_id': _get_journal,
        'date_invoice': lambda *a: strftime('%Y-%m-%d'),
        'is_debit_note': lambda obj, cr, uid, c: c.get('is_debit_note', False),
        'is_inkind_donation': lambda obj, cr, uid, c: c.get('is_inkind_donation', False),
        'is_intermission': lambda obj, cr, uid, c: c.get('is_intermission', False),
        'is_direct_invoice': lambda *a: False,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'is_merged_by_account': lambda *a: False,
        # set a default value on doc type so that the restrictions on fields apply even before the form is saved
        'doc_type': lambda obj, cr, uid, c: c and c.get('doc_type') or False,
    }

    def import_data_web(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None,
                        display_all_errors=False, has_header=False):
        """
        Overrides the standard import_data_web method for account.invoice model:
        - based on the 3 values for "cost_center_id / destination_id / funding_pool_id", creates a new AD at 100% for
          each invoice line and add it to "datas"
        - removes these 3 values that won't be used in the SI line
        - adapts the "fields" list accordingly
        - converts the dates from the format '%d/%m/%Y' to the standard one '%Y-%m-%d' so the checks on dates are correctly made
        """
        if context is None:
            context = {}
        new_data = datas
        analytic_acc_obj = self.pool.get('account.analytic.account')
        account_obj = self.pool.get('account.account')
        analytic_distrib_obj = self.pool.get('analytic.distribution')
        cc_distrib_line_obj = self.pool.get('cost.center.distribution.line')
        fp_distrib_line_obj = self.pool.get('funding.pool.distribution.line')
        curr_obj = self.pool.get('res.currency')
        nb_ad_fields = 0
        if 'invoice_line/cost_center_id' in fields:
            nb_ad_fields += 1
        if 'invoice_line/destination_id' in fields:
            nb_ad_fields += 1
        if 'invoice_line/funding_pool_id' in fields:
            nb_ad_fields += 1
        if nb_ad_fields:
            if nb_ad_fields != 3:
                raise osv.except_osv(_('Error'),
                                     _('Either the Cost Center, the Destination, or the Funding Pool is missing.'))
            # note: CC, dest and FP indexes always exist at this step
            cc_index = fields.index('invoice_line/cost_center_id')
            dest_index = fields.index('invoice_line/destination_id')
            fp_index = fields.index('invoice_line/funding_pool_id')
            si_line_name_index = 'invoice_line/name' in fields and fields.index('invoice_line/name')
            si_journal_index = 'journal_id' in fields and fields.index('journal_id')
            curr_index = 'currency_id' in fields and fields.index('currency_id')
            account_index = 'invoice_line/account_id' in fields and fields.index('invoice_line/account_id')
            doc_date_index = 'document_date' in fields and fields.index('document_date')
            date_inv_index = 'date_invoice' in fields and fields.index('date_invoice')
            new_data = []
            curr = False
            for data in datas:
                cc_ids = []
                dest_ids = []
                fp_ids = []
                distrib_id = ''
                cc = len(data) > cc_index and data[cc_index].strip()
                dest = len(data) > dest_index and data[dest_index].strip()
                fp = len(data) > fp_index and data[fp_index].strip()
                # check if details for SI line are filled in (based on the required field "name")
                has_si_line = si_line_name_index is not False and len(data) > si_line_name_index and data[si_line_name_index].strip()
                # process AD only for SI lines where at least one AD field has been filled in
                # (otherwise no AD should be added to the line AND no error should be displayed)
                if has_si_line and (cc or dest or fp):  # at least one AD field has been filled in
                    if cc:
                        cc_dom = [('category', '=', 'OC'), ('type', '=', 'normal'), '|', ('code', '=ilike', cc), ('name', '=ilike', cc)]
                        cc_ids = analytic_acc_obj.search(cr, uid, cc_dom, order='id', limit=1, context=context)
                    if dest:
                        dest_dom = [('category', '=', 'DEST'), ('type', '=', 'normal'), '|', ('code', '=ilike', dest), ('name', '=ilike', dest)]
                        dest_ids = analytic_acc_obj.search(cr, uid, dest_dom, order='id', limit=1, context=context)
                    if fp:
                        fp_dom = [('category', '=', 'FUNDING'), ('type', '=', 'normal'), '|', ('code', '=ilike', fp), ('name', '=ilike', fp)]
                        fp_ids = analytic_acc_obj.search(cr, uid, fp_dom, order='id', limit=1, context=context)
                    if not cc_ids or not dest_ids or not fp_ids:
                        raise osv.except_osv(_('Error'), _('Either the Cost Center, the Destination, or the Funding Pool '
                                                           'was not found on the line %s.') % data)
                    else:
                        # create the Analytic Distribution
                        distrib_id = analytic_distrib_obj.create(cr, uid, {}, context=context)
                        # get the next currency to use IF NEED BE (cf for an SI with several lines the curr. is indicated on the first one only)
                        si_journal = si_journal_index is not False and len(data) > si_journal_index and data[si_journal_index].strip()
                        if si_journal:  # first line of the SI
                            curr = curr_index is not False and len(data) > curr_index and data[curr_index].strip()
                        curr_ids = []
                        if curr:  # must exist at least on the first imported line
                            curr_ids = curr_obj.search(cr, uid, [('name', '=ilike', curr)], limit=1, context=context)
                        if not curr_ids:
                            raise osv.except_osv(_('Error'),
                                                 _('The currency was not found for the line %s.') % data)
                        vals = {
                            'analytic_id': cc_ids[0],  # analytic_id = Cost Center for the CC distrib line
                            'percentage': 100.0,
                            'distribution_id': distrib_id,
                            'currency_id': curr_ids[0],
                            'destination_id': dest_ids[0],
                        }
                        cc_distrib_line_obj.create(cr, uid, vals, context=context)
                        vals.update({
                            'analytic_id': fp_ids[0],  # analytic_id = Funding Pool for the FP distrib line
                            'cost_center_id': cc_ids[0],
                        })
                        fp_distrib_line_obj.create(cr, uid, vals, context=context)
                        account_code = account_index is not False and len(data) > account_index and data[account_index].strip()
                        if account_code:
                            account_ids = account_obj.search(cr, uid, [('code', '=', account_code)], context=context, limit=1)
                            if not account_ids:
                                raise osv.except_osv(_('Error'), _('The account %s was not found on the line %s.') % (account_code, data))
                            parent_id = False  # no distrib. at header level
                            distrib_state = analytic_distrib_obj._get_distribution_state(cr, uid, distrib_id, parent_id,
                                                                                         account_ids[0], context=context)
                            if distrib_state == 'invalid':
                                raise osv.except_osv(_('Error'), _('The analytic distribution is invalid on the line %s.') % data)
                # create a new list with the new distrib id and without the old AD fields
                # to be done also if no AD to ensure the size of each data list is always the same
                i = 0
                new_sub_list = []
                for d in data:  # loop on each value of the file line
                    if i not in [cc_index, dest_index, fp_index]:
                        if doc_date_index is not False and date_inv_index is not False and i in [doc_date_index, date_inv_index]:
                            # format the date from '%d/%m/%Y' to '%Y-%m-%d' so the checks on dates are correctly made
                            raw_date = len(data) > i and data[i].strip()
                            try:
                                new_date = raw_date and datetime.strptime(raw_date, '%d/%m/%Y').strftime('%Y-%m-%d') or ''
                            except ValueError:
                                new_date = raw_date
                            new_sub_list.append(new_date)
                        else:
                            new_sub_list.append(d)
                    i += 1
                # add new field value
                new_sub_list.append(distrib_id)
                new_data.append(new_sub_list)

            # remove old field names from fields
            fields.remove('invoice_line/cost_center_id')
            fields.remove('invoice_line/destination_id')
            fields.remove('invoice_line/funding_pool_id')
            # add new field
            fields.append('invoice_line/analytic_distribution_id/.id')  # .id = id in the database

        return super(account_invoice, self).import_data_web(cr, uid, fields, new_data, mode=mode, current_module=current_module,
                                                            noupdate=noupdate, context=context, filename=filename,
                                                            display_all_errors=display_all_errors, has_header=has_header)

    def synch_auto_tick(self, cr, uid, res, partner_id, doc_type, from_supply):
        """
        Updates res for manual IVO and STV:
        - automatically ticks the Synchronized box if the selected partner is Intermission or Intersection
        - automatically unticks the Synchronized box if the selected partner has another type.
        """
        if partner_id and doc_type in ('ivo', 'stv') and not from_supply:
            partner_type = self.pool.get('res.partner').read(cr, uid, partner_id, ['partner_type'])['partner_type']
            if partner_type in ['intermission', 'section']:
                res['value']['synced'] = True
            else:
                res['value']['synced'] = False
        return True

    def onchange_partner_id(self, cr, uid, ids, ctype, partner_id, date_invoice=False, payment_term=False, partner_bank_id=False,
                            company_id=False, is_inkind_donation=False, is_intermission=False, is_debit_note=False, is_direct_invoice=False,
                            account_id=False, doc_type=None, from_supply=None):
        """
        Get default donation account for Donation invoices.
        Get default intermission account for Intermission Voucher IN/OUT invoices.
        Get default currency from partner if this one is linked to a pricelist.
        Ticket utp917 - added code to avoid currency cd change if a direct invoice
        """
        res = super(account_invoice, self).onchange_partner_id(cr, uid, ids, ctype, partner_id, date_invoice, payment_term, partner_bank_id, company_id)
        partner = False
        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if not from_supply and doc_type in ('di', 'si') and partner.state == 'phase_out':
                return {
                    'value': {'partner_id': False, 'invoice_address_id': False, 'address_invoice_id': False, 'account_id': False},
                    'warning': {'title': _('Error'), 'message': _('The selected Supplier is Phase Out, please select another Supplier')}
                }
        if is_inkind_donation and partner:
            account_id = partner and partner.donation_payable_account and partner.donation_payable_account.id or False
            res['value']['account_id'] = account_id
        if is_intermission and partner_id:
            if account_id:
                # if the account_id field is filled in: keep its value
                res['value']['account_id'] = account_id
            else:
                # else: use its default value
                intermission_default_account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
                account_id = intermission_default_account and intermission_default_account.id or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
                res['value']['account_id'] = account_id
        if partner and ctype:
            ai_direct_invoice = False
            if ids: #utp917
                ai = self.browse(cr, uid, ids)[0]
                ai_direct_invoice = ai.is_direct_invoice
            if partner:
                c_id = False
                if ctype in ['in_invoice', 'out_refund'] and partner.property_product_pricelist_purchase:
                    c_id = partner.property_product_pricelist_purchase.currency_id.id
                elif ctype in ['out_invoice', 'in_refund'] and partner.property_product_pricelist:
                    c_id = partner.property_product_pricelist.currency_id.id
                # UFTP-121: regarding UTP-917, we have to change currency when changing partner, but not for direct invoices
                if c_id and (not is_direct_invoice and not ai_direct_invoice):
                    if not res.get('value', False):
                        res['value'] = {'currency_id': c_id}
                    else:
                        res['value'].update({'currency_id': c_id})
        # UFTP-168: If debit note, set account to False value
        if is_debit_note:
            res['value'].update({'account_id': False})
        self.synch_auto_tick(cr, uid, res, partner_id, doc_type, from_supply)
        return res

    def _check_currency_active(self, cr, uid, ids, context=None):
        if not ids:
            return True

        if isinstance(ids, int):
            ids = [ids]

        cr.execute('''
            select 
                c.name 
            from
                account_invoice i, res_currency c
            where
                i.currency_id = c.id and
                c.active = 'f' and
                i.id in %s
        ''', (tuple(ids),))
        inactives = [x[0] for x in cr.fetchall()]
        if inactives:
            raise osv.except_osv(
                _('Error'),
                _('Currency %s is inactive. Activate or change the currency before validation.') % (','.join(inactives))
            )
        return True

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        if isinstance(ids, int):
            ids = [ids]
        for i in self.browse(cr, uid, ids):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               i.document_date, i.date_invoice)
        return True

    def _check_invoice_merged_lines(self, cr, uid, ids, context=None):
        """
        US-357:
            merge of lines by account break lines descriptions (required field)
            => before next workflow stage from draft (validate, split)
               check that user has entered description on each line
               (force user to enter a custom description)
        """
        for self_br in self.browse(cr, uid, ids, context=context):
            if self_br.is_merged_by_account:  # deprecated since US-9241
                if not all([ l.name for l in self_br.invoice_line ]):
                    raise osv.except_osv(
                        _('Error'),
                        _('Please enter a description in each merged line' \
                            ' before invoice validation')
                    )

    def check_po_link(self, cr, uid, ids, context=None):
        """
        Checks that the invoices aren't linked to any PO (because of the commitments).
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for inv in self.read(cr, uid, ids, ['purchase_ids', 'doc_type', 'state']):
            if inv.get('doc_type', '') in ('ivi', 'si', 'isi'):
                if inv.get('purchase_ids', False):
                    if inv['doc_type'] == 'ivi':
                        if inv.get('state', '') != 'draft':  # only draft IVIs can be deleted
                            raise osv.except_osv(_('Warning'),
                                                 _('Intermission Vouchers linked to a PO can be deleted only in Draft state.'))
                    elif inv['doc_type'] == 'isi':
                        raise osv.except_osv(_('Warning'),
                                             _('You cannot cancel or delete an Intersection Supplier Invoice linked to a PO.'))
                    else:
                        # US-1702 Do not allow at all the deletion of SI coming from PO
                        raise osv.except_osv(_('Warning'), _('You cannot cancel or delete a supplier invoice linked to a PO.'))
        return True

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        Fill in account and journal for intermission invoice
        """
        defaults = super(account_invoice, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if context and context.get('is_intermission', False):
            intermission_type = context.get('intermission_type', False)
            if intermission_type in ('in', 'out'):
                # UF-2270: manual intermission (in or out)
                if defaults is None:
                    defaults = {}
                user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                if user and user[0] and user[0].company_id:
                    # get 'intermission counter part' account
                    if user[0].company_id.intermission_default_counterpart:
                        defaults['account_id'] = user[0].company_id.intermission_default_counterpart.id
                    else:
                        raise osv.except_osv("Error","Company Intermission Counterpart Account must be set")
                # 'INT' intermission journal
                int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                if int_journal_id:
                    defaults['fake_journal_id'] = int_journal_id
                    defaults['journal_id'] = defaults['fake_journal_id']
        return defaults

    def copy_web(self, cr, uid, inv_id, default=None, context=None):
        """
        Blocks manual duplication of old SI/SR with an Intersection Partner (replaced by ISI/ISR since US-8585)
        """
        if context is None:
            context = {}
        context.update({'from_copy_web': True})
        inv = self.browse(cr, uid, inv_id, fields_to_fetch=['partner_id', 'doc_type'], context=context)
        if inv.partner_id.partner_type == 'section' and inv.doc_type in ('si', 'sr'):
            new_doc_type = inv.doc_type == 'si' and _("an Intersection Supplier Invoice") or _("an Intersection Supplier Refund")
            raise osv.except_osv(_('Warning'), _("This invoice can't be duplicated because it has an Intersection partner: "
                                                 "please create %s instead.") % new_doc_type)
        return super(account_invoice, self).copy_web(cr, uid, inv_id, default, context=context)

    def copy(self, cr, uid, inv_id, default=None, context=None):
        """
        Delete period_id from invoice.
        Check context for splitting invoice.
        Reset register_line_ids.
        """
        # Some checks
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'period_id': False,
            'purchase_ids': False,  # UFTP-24 do not copy linked POs
            'purchase_list': False,  # UFTP-24 do not copy linked: reset of potential purchase list flag (from a PO direct purchase)
            'partner_move_line': False,
            'imported_invoices': False,
        })
        inv = self.browse(cr, uid, inv_id, fields_to_fetch=['state', 'from_supply', 'journal_id'], context=context)
        if not inv.journal_id.is_active:
            raise osv.except_osv(_('Warning'), _("The journal %s is inactive.") % inv.journal_id.code)
        # Manual duplication should generate a "manual document not created through the supply workflow", so we don't keep
        # the link to FOs and Picking List, and we reset the Source Doc if the invoice copied relates to a Supply workflow
        if context.get('from_button', False):
            default.update({
                'order_ids': False,
                'picking_id': False,
            })
            if inv.state == 'cancel':
                raise osv.except_osv(_('Warning'), _("You can't duplicate a Cancelled invoice."))
            if not context.get('from_split') and inv.from_supply:
                default.update({'origin': ''})

        # Reset register_line_ids if not given in default
        if 'register_line_ids' not in default:
            default['register_line_ids'] = []
        # US-267: Reset st_lines if not given in default, otherwise a new line in Reg will be added
        if 'st_lines' not in default:
            default['st_lines'] = []
        # Default behaviour
        new_id = super(account_invoice, self).copy(cr, uid, inv_id, default, context)
        # Case where you split an invoice
        if 'from_split' in context:
            purchase_obj = self.pool.get('purchase.order')
            sale_obj = self.pool.get('sale.order')
            if purchase_obj:
                # attach new invoice to PO
                purchase_ids = purchase_obj.search(cr, uid, [('invoice_ids', 'in', [inv_id])], context=context)
                if purchase_ids:
                    purchase_obj.write(cr, uid, purchase_ids, {'invoice_ids': [(4, new_id)]}, context=context)
            if sale_obj:
                # attach new invoice to SO
                sale_ids = sale_obj.search(cr, uid, [('invoice_ids', 'in', [inv_id])], context=context)
                if sale_ids:
                    sale_obj.write(cr, uid, sale_ids, {'invoice_ids': [(4, new_id)]}, context=context)
        return new_id


    def is_set_ref_from_partner(self, cr, uid, vals, context=None):
        '''read some properties to determine if the invoice is a supplier
        invoice or supplier refund to be able to set the reference from partner.
        '''
        if context is None:
            context = {}

        is_supplier_invoice = vals.get('type') == 'in_invoice'\
            and not vals.get('is_direct_invoice')\
            and not vals.get('is_inkind_donation')\
            and not vals.get('is_debit_note')\
            and not vals.get('is_intermission')

        is_supplier_refund = vals.get('type') == 'in_refund'

        if is_supplier_invoice or is_supplier_refund:
            return True
        return False

    def create(self, cr, uid, vals, context=None):
        """
        """
        if not context:
            context = {}
        if 'document_date' in vals and 'date_invoice' in vals:
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               vals['document_date'], vals['date_invoice'], context=context)

        # Create a sequence for this new invoice
        res_seq = self.create_sequence(cr, uid, vals, context)
        vals.update({'sequence_id': res_seq,})

        # UTP-317 # Check that no inactive partner have been used to create this invoice (except for isi and ivi)
        if 'partner_id' in vals:
            partner_id = vals.get('partner_id')
            if isinstance(partner_id, (str)):
                partner_id = int(partner_id)
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.read(cr, uid, partner_id,
                                       ['active', 'name', 'ref'])
            if partner and not partner['active']:
                if not ('real_doc_type' in vals and vals['real_doc_type'] in ('isi', 'ivi') and
                        (context.get('sync_update_execution', False) or context.get('sync_message_execution', False))):
                    raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner and partner['name'] or '',))

            #US-1686: set supplier reference from partner
            if 'supplier_reference' not in vals\
                    and self.is_set_ref_from_partner(cr, uid, vals=vals,
                                                     context=context):
                vals['supplier_reference'] = partner['ref']

        if not vals.get('real_doc_type') and context.get('doc_type') and not context.get('from_refund_button'):
            vals.update({'real_doc_type': context['doc_type']})

        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name'])

        return super(account_invoice, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # US_286: Forbit possibility to add include price tax
        # in bottom left corner
        if 'tax_line' in vals:
            tax_obj = self.pool.get('account.tax')
            for tax_line in vals['tax_line']:
                if tax_line[2]:
                    if 'account_tax_id' in tax_line[2]:
                        args = [('price_include', '=', '1'),
                                ('id', '=', tax_line[2]['account_tax_id'])]
                        tax_ids = tax_obj.search(cr, uid, args, limit=1,
                                                 order='NO_ORDER', context=context)
                        if tax_ids:
                            raise osv.except_osv(_('Error'),
                                                 _('Tax included in price can not be tied to the whole invoice.'))

        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name'])
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete register line if this invoice is a Direct Invoice.
        Don't delete an invoice that is linked to a PO.
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Check register lines
        for inv in self.browse(cr, uid, ids):
            if inv.is_direct_invoice and inv.register_line_ids:
                if not context.get('from_register', False):
                    self.pool.get('account.bank.statement.line').unlink(cr, uid, [x.id for x in inv.register_line_ids], {'from_direct_invoice': True})
        # Check PO
        self.check_po_link(cr, uid, ids)
        return super(account_invoice, self).unlink(cr, uid, ids, context)

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new invoice
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Invoice L' # For Invoice Lines
        code = 'account.invoice'

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

    def log(self, cr, uid, inv_id, message, secondary=False, action_xmlid=False, context=None):
        """
        Updates the log message with the right document name + link it to the right action_act_window
        """
        if context is None:
            context = {}
        # update the message
        pattern = re.compile('^(Invoice)')
        doc_type = self.read(cr, uid, inv_id, ['doc_type'], context=context)['doc_type'] or ''
        action_xmlid = self._invoice_action_act_window.get(doc_type) or action_xmlid
        doc_name = dict(self.fields_get(cr, uid, context=context)['doc_type']['selection']).get(doc_type)
        if doc_name:
            m = re.match(pattern, message)
            if m and m.groups():
                message = re.sub(pattern, doc_name, message, 1)
        return super(account_invoice, self).log(cr, uid, inv_id, message, secondary, action_xmlid=action_xmlid, context=context)

    def _check_tax_allowed(self, cr, uid, ids, context=None):
        """
        Raises an error if a tax is used with an Intermission or Intersection partner
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        warning_msg = _('Taxes are forbidden with Intermission and Intersection partners.')
        for inv in self.browse(cr, uid, ids, fields_to_fetch=['partner_id', 'tax_line', 'invoice_line'], context=context):
            if inv.partner_id.partner_type in ('intermission', 'section'):
                if inv.tax_line:
                    raise osv.except_osv(_('Warning'), warning_msg)
                for inv_line in inv.invoice_line:
                    if inv_line.invoice_line_tax_id:
                        raise osv.except_osv(_('Warning'), warning_msg)

    def _check_sync_allowed(self, cr, uid, ids, context=None):
        """
        Raises an error if the doc is marked as Synced whereas the Partner is neither Intermission nor Intersection
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for inv in self.browse(cr, uid, ids, fields_to_fetch=['partner_id', 'synced'], context=context):
            if inv.partner_id.partner_type not in ('intermission', 'section') and inv.synced:
                raise osv.except_osv(_('Warning'), _('Synchronized invoices are allowed only with Intermission and Intersection partners.'))

    def invoice_open(self, cr, uid, ids, context=None):
        """
        No longer fills the date automatically, but requires it to be set
        """
        # Some verifications
        if context is None:
            context = {}
        self._check_currency_active(cr, uid, ids, context=context)
        self._check_active_product(cr, uid, ids, context=context)
        self._check_invoice_merged_lines(cr, uid, ids, context=context)
        self.check_accounts_for_partner(cr, uid, ids, context=context)
        self._check_tax_allowed(cr, uid, ids, context=context)
        self._check_sync_allowed(cr, uid, ids, context=context)

        # Prepare workflow object
        wf_service = netsvc.LocalService("workflow")
        for inv in self.browse(cr, uid, ids):
            values = {}
            curr_date = strftime('%Y-%m-%d')
            if context.get('from_button') and inv.real_doc_type in ('di', 'si') and inv.state == 'draft' and \
                    inv.partner_id and inv.partner_id.state == 'phase_out':
                raise osv.except_osv(_('Error'),
                                     _('The selected Supplier is Phase Out, please select another Supplier'))
            if inv.is_debit_note:
                for inv_line in inv.invoice_line:
                    if inv_line.partner_id != inv.partner_id:
                        raise osv.except_osv(_('Warning'),
                                             _('All the imported lines must have the same partner as the Debit Note.'))
            # the journal used for Intermission Vouchers must be the INT journal of the current instance
            is_iv = context and context.get('type') in ['in_invoice', 'out_invoice'] and not context.get('is_debit_note') \
                and not context.get('is_inkind_donation') and context.get('is_intermission')
            ignore_check_total = False
            if is_iv:
                int_journal_id = self._get_int_journal_for_current_instance(cr, uid, context)
                # update the IV if the INT journal exists but isn't used in the IV (= journal created after the IV creation)
                if int_journal_id:
                    if not inv.journal_id or inv.journal_id.id != int_journal_id:
                        self.write(cr, uid, inv.id, {'journal_id': int_journal_id}, context=context)
                else:
                    raise osv.except_osv(_('Warning'), _('No Intermission journal found for the current instance.'))
            if inv.doc_type in ('isi', 'ivi', 'isr'):
                ignore_check_total = True

            if not inv.date_invoice and not inv.document_date:
                values.update({'date': curr_date, 'document_date': curr_date, 'state': 'date'})
            elif not inv.date_invoice:
                values.update({'date': curr_date, 'document_date': inv.document_date, 'state': 'date'})
            elif not inv.document_date:
                values.update({'date': inv.date_invoice, 'document_date': curr_date, 'state': 'date'})
            if inv.type in ('in_invoice', 'in_refund') and not ignore_check_total and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding/2.0):
                state = values and 'both' or 'amount'
                values.update({'check_total': inv.check_total, 'amount_total': inv.amount_total, 'state': state})

            has_asset_line = self.pool.get('account.invoice.line').search_exists(cr, uid, [('invoice_id', '=', inv.id), ('is_asset', '=', True)], context=context)
            if values or has_asset_line:
                values['invoice_id'] = inv.id
                wiz_id = self.pool.get('wizard.invoice.date').create(cr, uid, values, context)
                return {
                    'name': "Missing Information",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.invoice.date',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': wiz_id,
                }

            wf_service.trg_validate(uid, 'account.invoice', inv.id, 'invoice_open', cr)

        return True

    def invoice_open2(self, cr, uid, ids, context=None):
        """
        Alias for invoice_open (used to handle different characteristics on both buttons)
        """
        return self.invoice_open(cr, uid, ids, context=context)

    def invoice_open_with_confirmation(self, cr, uid, ids, context=None):
        """
        Simply calls "invoice_open" (asking for confirmation is done at form level)
        """
        return self.invoice_open(cr, uid, ids, context=context)

    def invoice_open_with_sync_confirmation(self, cr, uid, ids, context=None):
        """
        Simply calls "invoice_open" (asking for confirmation is done at form level)
        """
        return self.invoice_open(cr, uid, ids, context=context)

    def action_reconcile_imported_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile each imported invoice with its attached invoice line
        """
        # some verifications
        if isinstance(ids, int):
            ids = [ids]
        # browse all given invoices
        for inv in self.browse(cr, uid, ids):
            for invl in inv.invoice_line:
                if not invl.import_invoice_id:
                    continue
                imported_invoice = invl.import_invoice_id
                # reconcile partner line from import invoice with this invoice line attached move line
                import_invoice_partner_move_lines = self.pool.get('account.move.line').search(cr, uid, [('invoice_partner_link', '=', imported_invoice.id)])
                invl_move_lines = [x.id or None for x in invl.move_lines]
                rec = self.pool.get('account.move.line').reconcile_partial(cr, uid, [import_invoice_partner_move_lines[0], invl_move_lines[0]], 'auto', context=context)
                if not rec:
                    return False
        return True

    def action_reconcile_direct_invoice(self, cr, uid, inv, context=None):
        """
        Reconcile move line if invoice is a Direct Invoice
        NB: In order to define that an invoice is a Direct Invoice, we need to have register_line_ids not null
        """
        # Verify that this invoice is linked to a register line and have a move
        if not inv:
            return False
        if inv.move_id and inv.register_line_ids:
            ml_obj = self.pool.get('account.move.line')
            # First search move line that becomes from invoice
            res_ml_ids = ml_obj.search(cr, uid, [
                ('move_id', '=', inv.move_id.id),
                ('account_id', '=', inv.account_id.id),
                ('invoice_line_id', '=', False),  # US-254: do not seek invoice line's JIs (if same account as header)
            ])
            if len(res_ml_ids) > 1:
                raise osv.except_osv(_('Error'), _('More than one journal items found for this invoice.'))
            invoice_move_line_id = res_ml_ids[0]
            # Then search move line that corresponds to the register line
            reg_line = inv.register_line_ids[0]
            reg_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', reg_line.move_ids[0].id), ('account_id', '=', reg_line.account_id.id)])
            if len(reg_ml_ids) > 1:
                raise osv.except_osv(_('Error'), _('More than one journal items found for this register line.'))
            register_move_line_id = reg_ml_ids[0]
            # Finally do reconciliation
            ml_obj.reconcile_partial(cr, uid, [invoice_move_line_id, register_move_line_id])
        return True

    def action_date_assign(self, cr, uid, ids, *args):
        """
        Check Document date.
        """
        # Prepare some values
        period_obj = self.pool.get('account.period')
        # Default behaviour to add date
        res = super(account_invoice, self).action_date_assign(cr, uid, ids, args)
        # Process invoices
        for i in self.browse(cr, uid, ids):
            if not i.date_invoice:
                self.write(cr, uid, i.id, {'date_invoice': strftime('%Y-%m-%d')})
                i = self.browse(cr, uid, i.id) # This permit to refresh the browse of this element
            if not i.document_date:
                raise osv.except_osv(_('Warning'), _('Document Date is a mandatory field for validation!'))
            # UFTP-105: Search period and raise an exeception if this one is not open
            period_ids = period_obj.get_period_from_date(cr, uid, i.date_invoice)
            if not period_ids:
                raise osv.except_osv(_('Error'), _('No period found for this posting date: %s') % (i.date_invoice))
            for period in period_obj.browse(cr, uid, period_ids):
                if period.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('You cannot validate this document in the given period: %s because it\'s not open. Change the date of the document or open the period.') % (period.name))
        # Posting date should not be done BEFORE document date
        self._check_document_date(cr, uid, ids)
        return res

    def _check_journal(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the journal used are not compatible
        """
        if context is None:
            context = {}
        journal = self.browse(cr, uid, inv_id, fields_to_fetch=['journal_id'], context=context).journal_id
        j_type = journal.type
        if inv_type is None:
            inv_type = self.read(cr, uid, inv_id, ['doc_type'])['doc_type']
        if inv_type in ('si', 'di', 'isi', 'isr') and j_type != 'purchase' or inv_type == 'sr' and j_type != 'purchase_refund' or \
            inv_type in ('ivi', 'ivo') and j_type != 'intermission' or inv_type in ('stv', 'str', 'dn') and j_type != 'sale' or \
                inv_type == 'cr' and j_type != 'sale_refund' or inv_type == 'donation' and j_type not in ('inkind', 'extra') or \
                inv_type in ('isi', 'isr') and journal.code != 'ISI' or inv_type not in ('isi', 'isr') and journal.code == 'ISI':
            raise osv.except_osv(_('Error'), _("The journal %s is not allowed for this document.") % journal.name)

    def _check_partner(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the partner used are not compatible
        """
        if context is None:
            context = {}
        partner = self.browse(cr, uid, inv_id, fields_to_fetch=['partner_id'], context=context).partner_id
        p_type = partner.partner_type
        if inv_type is None:
            inv_type = self.read(cr, uid, inv_id, ['doc_type'])['doc_type']
        # if a supplier/customer is expected for the doc: check that the partner used has the right flag
        # note: SI/SR on Intersection partners are blocked only at form level (the validation of old docs should still be possible)
        supplier_ko = inv_type in ('si', 'di', 'sr', 'ivi', 'donation', 'isi', 'isr') and not partner.supplier
        customer_ko = inv_type in ('ivo', 'stv', 'dn', 'cr', 'str') and not partner.customer
        if supplier_ko or customer_ko or inv_type in ('ivi', 'ivo') and p_type != 'intermission' or \
            inv_type in ('stv', 'str') and p_type not in ('section', 'external') or \
                inv_type == 'donation' and p_type not in ('esc', 'external', 'section') or \
                inv_type in ('isi', 'isr') and p_type != 'section':
            raise osv.except_osv(_('Error'), _("The partner %s is not allowed for this document.") % partner.name)

    def _check_header_account(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the account used are not compatible
        """
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        account = self.browse(cr, uid, inv_id, fields_to_fetch=['account_id'], context=context).account_id
        if inv_type is None:
            inv_type = self.read(cr, uid, inv_id, ['doc_type'])['doc_type']
        account_domain = []
        if inv_type in ('si', 'di', 'sr', 'isi', 'isr'):
            account_domain.append(('restricted_area', '=', 'in_invoice'))
        elif inv_type in ('stv', 'cr', 'str'):
            account_domain.append(('restricted_area', '=', 'out_invoice'))
        elif inv_type == 'dn':
            account_domain.append(('restricted_area', '=', 'out_invoice'))
            account_domain.append(('is_intersection_counterpart', '=', False))
        elif inv_type == 'donation':
            account_domain.append(('restricted_area', '=', 'donation_header'))
        elif inv_type == 'ivi':
            context.update(({'check_header_ivi': True, }))
            account_domain.append(('restricted_area', '=', 'intermission_header'))
        elif inv_type == 'ivo':
            context.update(({'check_header_ivo': True, }))
            account_domain.append(('restricted_area', '=', 'intermission_header'))
        account_domain.append(('id', '=', account.id))  # the account used in the account_invoice
        if not account_obj.search_exist(cr, uid, account_domain, context=context):
            raise osv.except_osv(_('Error'), _("The account %s - %s is not allowed for this document.") % (account.code, account.name))

    def _check_line_accounts(self, cr, uid, inv_id, inv_type=None, context=None):
        """
        Raises an error if the type of the account.invoice and the accounts used at line level are not compatible
        No check is done for Debit Notes where the creation of lines is only possible by importing existing finance docs
        """
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        inv_line_obj = self.pool.get('account.invoice.line')
        lines = inv_line_obj.search(cr, uid, [('invoice_id', '=', inv_id)], context=context, order='NO_ORDER')
        if inv_type is None:
            inv_type = self.read(cr, uid, inv_id, ['doc_type'])['doc_type']
        account_domain = []
        if inv_type in ('si', 'di', 'sr', 'cr', 'isi', 'isr', 'str'):
            account_domain.append(('restricted_area', '=', 'invoice_lines'))
        elif inv_type == 'stv':
            context.update(({'check_line_stv': True, }))
            account_domain.append(('restricted_area', '=', 'invoice_lines'))
        elif inv_type == 'donation':
            account_domain.append(('restricted_area', '=', 'donation_lines'))
        elif inv_type in ('ivi', 'ivo'):
            account_domain.append(('restricted_area', '=', 'intermission_lines'))
        for line in inv_line_obj.browse(cr, uid, lines, fields_to_fetch=['account_id'], context=context):
            acc = line.account_id
            if not account_obj.search_exist(cr, uid, account_domain + [('id', '=', acc.id)], context=context):
                raise osv.except_osv(_('Error'), _("The account %s - %s used at line level is not allowed.") % (acc.code, acc.name))

    def check_domain_restrictions(self, cr, uid, ids, context=None):
        """
        Check that the journal, partner and accounts used are compatible with the type of the document
        """
        if context is None:
            context = {}
        for inv_id in ids:
            inv_type = self.read(cr, uid, inv_id, ['doc_type'])['doc_type']
            self._check_journal(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_partner(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_header_account(cr, uid, inv_id, inv_type=inv_type, context=context)
            self._check_line_accounts(cr, uid, inv_id, inv_type=inv_type, context=context)

    def update_counterpart_inv_status(self, cr, uid, ids, context=None):
        """
        In case an IVO or STV, with an Intermission or Intersection partner and set as Synchronized, is being opened:
        set the Counterpart Invoice Status to Draft automatically
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        inv_fields = ['type', 'is_debit_note', 'synced', 'partner_type', 'counterpart_inv_status']
        for inv in self.browse(cr, uid, ids, fields_to_fetch=inv_fields, context=context):
            is_ivo_or_stv = inv.type == 'out_invoice' and not inv.is_debit_note
            if is_ivo_or_stv and inv.synced and inv.partner_type in ('intermission', 'section') and not inv.counterpart_inv_status:
                self.write(cr, uid, inv.id, {'counterpart_inv_status': 'draft'}, context=context)

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Give function to use when changing invoice to open state
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
        if not self.action_reconcile_imported_invoice(cr, uid, ids, context):
            return False
        self.check_domain_restrictions(cr, uid, ids, context)  # raises an error if one unauthorized element is used
        self.update_counterpart_inv_status(cr, uid, ids, context=context)
        for invoice in self.browse(cr, uid, ids, fields_to_fetch=['doc_type'], context=context):
            if invoice.doc_type == 'donation':
                self.write(cr, uid, invoice.id, {'state': 'done'}, context=context)
            else:
                self.write(cr, uid, invoice.id, {'state': 'open'}, context=context)
        return True


    def button_debit_note_import_invoice(self, cr, uid, ids, context=None):
        """
        Launch wizard that permits to import invoice on a debit note
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse all given invoices
        for inv in self.browse(cr, uid, ids):
            if inv.type != 'out_invoice' or inv.is_debit_note == False:
                raise osv.except_osv(_('Error'), _('You can only do import invoice on a Debit Note!'))
            w_id = self.pool.get('debit.note.import.invoice').create(cr, uid, {'invoice_id': inv.id, 'currency_id': inv.currency_id.id,
                                                                               'partner_id': inv.partner_id.id}, context=context)
            context.update({
                'active_id': inv.id,
                'active_ids': ids,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'debit.note.import.invoice',
                'name': 'Import invoice',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': w_id,
                'context': context,
                'target': 'new',
            }

    def button_split_invoice(self, cr, uid, ids, context=None):
        """
        Launch the split invoice wizard to split an invoice in two elements.
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, int):
            ids = [ids]
        self._check_invoice_merged_lines(cr, uid, ids, context=context)

        # Prepare some value
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        inv_lines_obj = self.pool.get('account.invoice.line')
        # Creating wizard
        wizard_id = self.pool.get('wizard.split.invoice').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        # Add invoices_lines into the wizard
        invoice_line_ids = self.pool.get('account.invoice.line').search(cr, uid, [('invoice_id', '=', ids[0])], context=context)
        # Some other verifications
        if not len(invoice_line_ids):
            raise osv.except_osv(_('Error'), _('No invoice line in this invoice or not enough elements'))
        for invl in inv_lines_obj.browse(cr, uid, invoice_line_ids, context=context):
            wiz_lines_obj.create(cr, uid, {'invoice_line_id': invl.id, 'product_id': invl.product_id.id, 'quantity': invl.quantity,
                                           'price_unit': invl.price_unit, 'description': invl.name, 'wizard_id': wizard_id}, context=context)
        # Return wizard
        if wizard_id:
            if context.get('from_stv'):
                wizard_title = _('Split Stock Transfer Voucher')
            elif context.get('is_intermission') and context.get('intermission_type', '') == 'out':
                wizard_title = _('Split Intermission Voucher OUT')
            elif context.get('is_inkind_donation'):
                wizard_title = _('Split Donation')
            else:
                wizard_title = _('Split Invoice')
            return {
                'name': wizard_title,
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.split.invoice',
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [wizard_id],
                'context':
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_id': wizard_id,
                }
            }
        return False

    def button_split_invoice2(self, cr, uid, ids, context=None):
        """
        Alias for button_split_invoice (used to handle different characteristics on both buttons)
        """
        return self.button_split_invoice(cr, uid, ids, context=context)

    def button_donation_certificate(self, cr, uid, ids, context=None):
        """
        Open a view containing a list of all donation certificates linked to the given invoice.
        """
        for inv in self.browse(cr, uid, ids):
            pick_id = inv.picking_id and inv.picking_id.id or ''
            domain = "[('res_model', '=', 'stock.picking'), ('res_id', '=', " + str(pick_id) + "), ('description', '=', 'Certificate of Donation')]"
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_attachment_tree_2')
            view_id = view_id and view_id[1] or False
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'view_attachment_search_2')
            search_view_id = search_view_id and search_view_id[1] or False
            return {
                'name': "Certificate of Donation",
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'search_view_id': search_view_id,
                'domain': domain,
                'context': context,
                'target': 'current',
            }
        return False

    def button_dummy_compute_total(self, cr, uid, ids, context=None):
        return True

    def check_accounts_for_partner(self, cr, uid, ids, context=None,
                                   header_obj=False, lines_field='invoice_line',
                                   line_level_partner_type=False):
        """
        :param header_obj: target model for header or self
        :param lines_field: lines o2m field
        :param line_level_partner_type: partner to check lines account with
            if true use partner_type for lines else use header partner
        :return:
        """
        header_obj = header_obj or self
        account_obj = self.pool.get('account.account')
        header_errors = []
        lines_errors = []

        for r in header_obj.browse(cr, uid, ids, context=context):
            partner_id = hasattr(r, 'partner_id') and r.partner_id \
                and r.partner_id.id or False

            # header check
            if hasattr(r, 'account_id') and r.account_id:
                if not account_obj.is_allowed_for_thirdparty(cr, uid,
                                                             [r.account_id.id], partner_id=partner_id,
                                                             context=context)[r.account_id.id]:
                    header_errors.append(
                        _('invoice header account and partner not compatible.'))

            # lines check
            if lines_field and hasattr(r, lines_field):
                if line_level_partner_type:
                    partner_id = False
                else:
                    partner_type = False
                line_index = 1
                for l in getattr(r, lines_field):
                    if l.account_id:
                        if line_level_partner_type:
                            # partner at line level
                            partner_type = l.partner_type
                        if not account_obj.is_allowed_for_thirdparty(cr,
                                                                     uid, [l.account_id.id],
                                                                     partner_type=partner_type or False,
                                                                     partner_id=partner_id or False,
                                                                     context=context)[l.account_id.id]:
                            num = hasattr(l, 'line_number') and l.line_number \
                                or line_index
                            if not lines_errors:
                                header_errors.append(
                                    _('following # lines with account/partner' \
                                        ' are not compatible:'))
                            lines_errors.append(_('#%d account %s - %s') % (num,
                                                                            l.account_id.code, l.account_id.name, ))
                    line_index += 1

        if header_errors or lines_errors:
            raise osv.except_osv(_('Error'),
                                 "\n".join(header_errors + lines_errors))

    def has_one_line_reconciled(self, cr, uid, account_inv_ids, context=None):
        """
        Returns True if one of the account.invoice docs whose ids are in parameter has a line which is fully reconciled
        (header, lines, taxes at header or line level)
        """
        if context is None:
            context = {}
        if isinstance(account_inv_ids, int):
            account_inv_ids = [account_inv_ids]
        aml_obj = self.pool.get('account.move.line')
        aml_ids = aml_obj.search(cr, uid, [('invoice', 'in', account_inv_ids)], order='NO_ORDER', context=context)
        if aml_obj.search_exist(cr, uid, [('id', 'in', aml_ids), ('reconcile_id', '!=', False)], context=context):
            return True
        return False

    def _get_ad(self, cr, uid, ids,  ad_obj, context=None):
        percentages, cc_codes, dest_codes, fp_codes = [], [], [], []
        for fp_line in ad_obj.funding_pool_lines:
            percentages.append(str(fp_line.percentage))
            cc_codes.append(fp_line.cost_center_id.code)
            dest_codes.append(fp_line.destination_id.code)
            fp_codes.append(fp_line.analytic_id.code)
        return [';'.join(percentages), ';'.join(cc_codes), ';'.join(dest_codes), ';'.join(fp_codes)]

    def export_invoice(self, cr, uid, ids, data, context=None):
        """
        Opens the Export Invoice report
        """
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.export_invoice',
            'datas': data,
        }

    def import_invoice(self, cr, uid, ids, data, context=None):
        """
        Opens the Import Invoice wizard
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_id = self.pool.get('account.invoice.import').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        return {
            'name': _('Import Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.import',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wiz_id],
        }

    def get_invoice_lines_follow_up(self, cr, uid, ids, context=None):
        """
        Prints the FO Follow-Up Finance report related to the IVO or STV selected
        """
        if context is None:
            context = {}
        follow_up_wizard = self.pool.get('fo.follow.up.finance.wizard')
        inv_ids = context.get('active_ids')
        if not inv_ids:
            raise osv.except_osv(_('Error'),
                                 _('Please select at least one record!'))
        if isinstance(inv_ids, int):
            inv_ids = [inv_ids]
        context.update({
            'selected_inv_ids': inv_ids,
            'is_intermission': self.browse(cr, uid, inv_ids[0], fields_to_fetch=['is_intermission']).is_intermission,
        })
        wiz_id = follow_up_wizard.create(cr, uid, {}, context=context)
        return follow_up_wizard.print_excel(cr, uid, [wiz_id], context=context)


account_invoice()


class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.product_id.id, obj.uos_id.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))
        return True

    _constraints = [(_uom_constraint, 'Constraint error on Uom', [])]

    def _have_been_corrected(self, cr, uid, ids, name, args, context=None):
        """
        Return True if ALL elements are OK:
         - a journal items is linked to this invoice line
         - the journal items is linked to an analytic line that have been reallocated
        """
        if context is None:
            context = {}
        res = {}

        def has_ana_reallocated(move):
            for ml in move.move_lines or []:
                for al in ml.analytic_lines or []:
                    if al.is_reallocated:
                        return True
            return False

        for il in self.browse(cr, uid, ids, context=context):
            res[il.id] = has_ana_reallocated(il)
        return res

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Give product code for each invoice line
        """
        res = {}
        for inv_line in self.browse(cr, uid, ids, context=context):
            res[inv_line.id] = ''
            if inv_line.product_id:
                res[inv_line.id] = inv_line.product_id.default_code

        return res
    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _get_fake_m2o(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Returns False for all ids
        """
        res = {}
        for i in ids:
            res[i] = False
        return res

    def _get_line_doc_type(self, cr, uid, context=None):
        """
        Gets the list of possible invoice types
        """
        return self.pool.get('account.invoice')._get_invoice_type_list(cr, uid, context=context)

    def _get_cc(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = {}
        for i in ids:
            res[i] = False
            cost_centers = ''
            line_ad = self.browse(cr, uid, i,fields_to_fetch=['analytic_distribution_id'], context=context)
            if line_ad and line_ad.analytic_distribution_id and line_ad.analytic_distribution_id.funding_pool_lines:
                cc = []
                for fp_line in line_ad.analytic_distribution_id.funding_pool_lines:
                    cc.append(fp_line.cost_center_id.code)
                cost_centers = ', '.join(cc)
            res[i] = cost_centers
        return res

    def _get_dest(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = {}
        for i in ids:
            res[i] = False
            destinations = ''
            line_ad = self.browse(cr, uid, i, fields_to_fetch=['analytic_distribution_id'], context=context)
            if line_ad and line_ad.analytic_distribution_id and line_ad.analytic_distribution_id.funding_pool_lines:
                dest = []
                for fp_line in line_ad.analytic_distribution_id.funding_pool_lines:
                    dest.append(fp_line.destination_id.code)
                destinations = ', '.join(dest)
            res[i] = destinations
        return res

    _columns = {
        'line_number': fields.integer(string='Line Number'),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Account Computation')),
        'import_invoice_id': fields.many2one('account.invoice', string="From an import invoice", readonly=True),
        'move_lines':fields.one2many('account.move.line', 'invoice_line_id', string="Journal Item", readonly=True),
        'is_corrected': fields.function(_have_been_corrected, method=True, string="Have been corrected?", type='boolean',
                                        readonly=True, help="This informs system if this item have been corrected in analytic lines. Criteria: the invoice line is linked to a journal items that have analytic item which is reallocated.",
                                        store=False),
        'product_code': fields.function(_get_product_code, method=True, store=False, string="Product Code", type='char'),
        'reference': fields.char(string="Reference", size=64),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'reversed_invoice_line_id': fields.many2one('account.invoice.line', string='Reversed Invoice Line',
                                                    help='Invoice line that has been reversed by this one through a '
                                                         '"refund cancel" or "refund modify"'),
        'cost_center_id': fields.function(_get_fake_m2o, method=True, type='many2one', store=False,
                                          states={'draft': [('readonly', False)]},  # see def detect_data in unifield-web/addons/openerp/controllers/impex.py
                                          relation="account.analytic.account", string='Cost Center',
                                          help="Field used for import only"),
        'destination_id': fields.function(_get_fake_m2o, method=True, type='many2one', store=False,
                                          relation="account.analytic.account", string='Destination',
                                          states={'draft': [('readonly', False)]},
                                          help="Field used for import only"),
        'funding_pool_id': fields.function(_get_fake_m2o, method=True, type='many2one', store=False,
                                           relation="account.analytic.account", string='Funding Pool',
                                           states={'draft': [('readonly', False)]},
                                           help="Field used for import only"),
        'cost_centers':fields.function(_get_cc, method=True, type='char', size=1024, string='Cost Centers', readonly=True),
        'destinations': fields.function(_get_dest, method=True, type='char', size=1024, string='Destinations', readonly=True),
        'from_supply': fields.related('invoice_id', 'from_supply', type='boolean', string='From Supply', readonly=True, store=False),
        'synced': fields.related('invoice_id', 'synced', type='boolean', string='Synchronized', readonly=True, store=False),
        # field "line_synced" created to be used in the views where the "synced" field at doc level is displayed
        # (avoids having 2 fields with the same name within the same view)
        'line_synced': fields.related('invoice_id', 'synced', type='boolean', string='Synchronized', readonly=True, store=False,
                                      help='Technical field, similar to "synced"'),
        'line_doc_type': fields.related('invoice_id', 'doc_type', type='selection', selection=_get_line_doc_type,
                                        string='Document Type', store=False, write_relate=False),
        'invoice_type': fields.related('invoice_id', 'type', string='Invoice Type', type='selection', readonly=True, store=False,
                                       selection=[('out_invoice', 'Customer Invoice'),
                                                  ('in_invoice', 'Supplier Invoice'),
                                                  ('out_refund', 'Customer Refund'),
                                                  ('in_refund', 'Supplier Refund')]),
        'merged_line': fields.boolean(string='Merged Line (deprecated)', help='Line generated by the merging of other lines', readonly=True),
        # - a CV line can be linked to several invoice lines ==> e.g. several partial deliveries, split of invoice lines
        # - an invoice line can be linked to several CV lines => e.g. merge invoice lines by account
        'cv_line_ids': fields.many2many('account.commitment.line', 'inv_line_cv_line_rel', 'inv_line_id', 'cv_line_id',
                                        string='Commitment Voucher Lines'),
        'allow_no_account': fields.boolean(string='Allow an empty account on the line', readonly=True),
    }

    _defaults = {
        'price_unit': lambda *a: 0.00,
        'is_corrected': lambda *a: False,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'merged_line': lambda *a: False,
        'allow_no_account': lambda *a: False,
    }

    _order = 'line_number'

    _sql_constraints = [
        ('ck_invl_account', "CHECK(account_id IS NOT NULL OR COALESCE(allow_no_account, 'f') = 't')",
         'The invoice lines must have an account.')
    ]

    def _check_on_invoice_line_big_amounts(self, cr, uid, ids, context=None):
        """
        Prevents booking amounts having more than 10 digits before the comma, i.e. amounts starting from 10 billions.
        The goal is to avoid losing precision, see e.g.: "%s" % 10000000000.01  # '10000000000.0'
        (and to avoid decimal.InvalidOperation due to huge amounts).
        This applies to all types of account.invoice.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        inv_line_fields = ['quantity', 'price_unit', 'discount', 'name']
        for inv_line in self.browse(cr, uid, ids, fields_to_fetch=inv_line_fields, context=context):
            # check amounts entered manually (cf. huge amounts could cause decimal.InvalidOperation), and the total to be used in JI
            qty = inv_line.quantity or 0.0
            pu = inv_line.price_unit or 0.0
            discount = inv_line.discount or 0.0
            subtotal = self._amount_line(cr, uid, [inv_line.id], 'price_subtotal', None, context)[inv_line.id]
            if _max_amount(qty)  or _max_amount(pu) or _max_amount(discount) or _max_amount(subtotal):
                raise osv.except_osv(_('Error'), _('Line "%s": one of the numbers entered is more than 10 digits with decimals or 12 digits without decimals.') % inv_line.name)

    def _check_automated_invoice(self, cr, uid, invoice_id, context=None):
        """
        Prevents the creation of manual inv. lines if the related invoice has been generated via Sync. or
        by a Supply workflow (for Intermission/Intersection partners)
        """
        if context is None:
            context = {}
        if self._name == 'wizard.account.invoice.line':
            # no check on Direct Invoice
            return True
        inv_obj = self.pool.get('account.invoice')
        if invoice_id:
            inv_fields = ['from_supply', 'synced', 'type', 'is_inkind_donation', 'partner_type']
            inv = inv_obj.browse(cr, uid, invoice_id, fields_to_fetch=inv_fields, context=context)
            if not inv.is_inkind_donation:  # never block manual line creation in Donations whatever the workflow and partner type
                ivi_or_isi_synced = inv.type == 'in_invoice' and inv.synced
                intermission_or_section_from_supply = inv.partner_type in ('intermission', 'section') and inv.from_supply
                from_split = context.get('from_split')
                if context.get('from_inv_form'):
                    if from_split and ivi_or_isi_synced:
                        raise osv.except_osv(_('Error'), _('This document has been generated via synchronization. '
                                                           'You can\'t split its lines.'))
                    elif not from_split and (ivi_or_isi_synced or intermission_or_section_from_supply):
                        raise osv.except_osv(_('Error'), _('This document has been generated via a Supply workflow or via synchronization. '
                                                           'You can\'t add lines manually.'))

    def _remove_spaces_name(self, cr, uid, vals, context=None):
        """
            remove spaces in name, except if the result is an empty string
        """
        if vals.get('name'):
            orig = vals['name']
            # ustr: all kind of spaces are removed in unicode
            vals['name'] = ustr(vals['name']).strip()
            if not vals['name']:
                vals['name'] = orig
                return True
        return False

    def raise_if_not_workflow(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        invoice_line_table = self._table
        if self._name == 'wizard.account.invoice.line':
            invoice_table = 'wizard_account_invoice'
        else:
            invoice_table = 'account_invoice'
        cr.execute('''
            select l.line_number
            from
                ''' + invoice_line_table + ''' l, ''' + invoice_table + ''' i
            where
                l.invoice_id = i.id and
                i.from_supply = 'f' and
                (i.type not in ('in_invoice', 'in_refund') or i.synced = 'f') and
                l.id in %s
            ''', (tuple(ids), ))  # not_a_user_entry
        line_error = ['%s'%(x[0] or '') for x in cr.fetchall()]
        if line_error:
            raise osv.except_osv(_('Error'), _('Invoice line #%s: The description contains only spaces.') % ', '.join(line_error))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Give a line_number to invoice line.
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        self._check_automated_invoice(cr, uid, vals.get('invoice_id'), context=context)
        # Create new number with invoice sequence
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            invoice = self.pool.get('account.invoice').browse(cr, uid, vals['invoice_id'], fields_to_fetch=['sequence_id'])
            if invoice and invoice.sequence_id:
                sequence = invoice.sequence_id
                line = sequence.get_id(code_or_id='id', context=context)
                vals.update({'line_number': line})
        empty_name = self._remove_spaces_name(cr, uid, vals, context=context)
        inv_line_id = super(account_invoice_line, self).create(cr, uid, vals, context)
        if empty_name:
            self.raise_if_not_workflow(cr, uid, [inv_line_id], context=context)

        self._check_on_invoice_line_big_amounts(cr, uid, inv_line_id, context=context)
        return inv_line_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Give a line_number in invoice_id in vals
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """

        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            for il in self.browse(cr, uid, ids):
                if not il.line_number and il.invoice_id.sequence_id:
                    sequence = il.invoice_id.sequence_id
                    il_number = sequence.get_id(code_or_id='id', context=context)
                    vals.update({'line_number': il_number})
        empty_name = self._remove_spaces_name(cr, uid, vals, context=context)
        res = super(account_invoice_line, self).write(cr, uid, ids, vals, context)
        if empty_name:
            self.raise_if_not_workflow(cr, uid, ids, context=context)
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.is_direct_invoice and invl.invoice_id.state == 'draft':
                amount = 0.0
                for l in invl.invoice_id.invoice_line:
                    amount += l.price_subtotal
                self.pool.get('account.invoice').write(cr, uid, [invl.invoice_id.id], {'check_total': amount}, context)
                self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in invl.invoice_id.register_line_ids], {'amount': -1 * amount}, context)
        self._check_on_invoice_line_big_amounts(cr, uid, ids, context=context)
        return res

    def copy(self, cr, uid, inv_id, default=None, context=None):
        """
        Check context to see if we come from a split. If yes, we create the link between invoice and PO/FO.
        """
        if not context:
            context = {}
        if not default:
            default = {}

        new_id = super(account_invoice_line, self).copy(cr, uid, inv_id, default, context)

        if 'from_split' in context:
            purchase_lines_obj = self.pool.get('purchase.order.line')
            sale_lines_obj = self.pool.get('sale.order.line')

            if purchase_lines_obj:
                purchase_line_ids = purchase_lines_obj.search(cr, uid,
                                                              [('invoice_lines', 'in', [inv_id])], order='NO_ORDER')
                if purchase_line_ids:
                    purchase_lines_obj.write(cr, uid, purchase_line_ids, {'invoice_lines': [(4, new_id)]})

            if sale_lines_obj:
                sale_lines_ids =  sale_lines_obj.search(cr, uid,
                                                        [('invoice_lines', 'in', [inv_id])], order='NO_ORDER')
                if sale_lines_ids:
                    sale_lines_obj.write(cr, uid,  sale_lines_ids, {'invoice_lines': [(4, new_id)]})

        return new_id

    def copy_data(self, cr, uid, invl_id, default=None, context=None):
        """
        Copy an invoice line without its move lines,
        without the link to a reversed invoice line,
        and without link to PO/FO/CV lines when the duplication is manual
        Reset the merged_line and allow_no_account tags.
        Prevent the manual duplication of invoices lines with no account.
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        # The only way to get invoice lines without account should be via synchro and not via duplication
        # (display a specific error message instead of the SQL error)
        if context.get('from_copy_web') and not self.read(cr, uid, invl_id, ['account_id'], context=context)['account_id']:
            raise osv.except_osv(_('Warning'), _("Duplication not allowed. Please set an account on all lines first."))
        default.update({'move_lines': False,
                        'reversed_invoice_line_id': False,
                        'merged_line': False,
                        'allow_no_account': False,
                        'is_asset': False,
                        })
        if self.read(cr, uid, invl_id, ['is_asset'], context=context)['is_asset']:
            line_data = self.browse(cr, uid, invl_id, fields_to_fetch=['product_id'], context=context)
            prod = line_data.product_id
            if prod:
                default['account_id'] = prod.property_account_expense and prod.property_account_expense.id or \
                    prod.categ_id and prod.categ_id.property_account_expense_categ and prod.categ_id.property_account_expense_categ.id or \
                    False
        # Manual duplication should generate a "manual document not created through the supply workflow"
        # so we don't keep the link to PO/FO/CV at line level
        if context.get('from_button') and not context.get('from_split'):
            default.update({
                'order_line_id': False,
                'sale_order_line_id': False,
                'sale_order_lines': False,
                'purchase_order_line_ids': [],
                'cv_line_ids': [(6, 0, [])],
            })
        return super(account_invoice_line, self).copy_data(cr, uid, invl_id, default, context)

    def unlink(self, cr, uid, ids, context=None):
        """
        - If invoice is a Direct Invoice and is in draft state:
            - compute total amount (check_total field)
            - write total to the register line
        - Raise error msg if the related inv. has been generated via Sync. or by a Supply workflow (for Intermission/Intersection partners)
          (for SI from Supply: deleting lines is allowed only for manual lines not having been merged (merging is deprecated since US-9241))
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Fetch all invoice_id to check
        direct_invoice_ids = []
        invoice_ids = []
        abst_obj = self.pool.get('account.bank.statement.line')
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.id not in invoice_ids:
                invoice = invl.invoice_id
                in_invoice = invoice.type == 'in_invoice' and not invoice.is_inkind_donation
                supp_inv = in_invoice and not invoice.is_intermission
                donation = invoice.is_inkind_donation
                from_split = context.get('from_split')
                from_supply = invoice.from_supply
                intermission_or_section = invoice.partner_type in ('intermission', 'section')
                check_line_per_line = from_supply and (supp_inv or donation) and not from_split
                if not check_line_per_line:
                    invoice_ids.append(invoice.id)  # check each invoice only once
                deletion_allowed = True
                if in_invoice and invoice.synced:
                    deletion_allowed = False
                elif from_supply and not from_split:  # allow deletion due to the "Split" feature (available in Draft)
                    if intermission_or_section and not donation:
                        deletion_allowed = False
                    elif (supp_inv or donation) and (invl.order_line_id or invl.merged_line):
                        deletion_allowed = False
                if not deletion_allowed:
                    # will be displayed when trying to delete lines manually or split invoices
                    if donation:
                        raise osv.except_osv(_('Error'),
                                             _("This donation has been generated via a Supply workflow. Existing lines can't be deleted."))
                    else:
                        raise osv.except_osv(_('Error'), _("This document has been generated via a Supply workflow or via synchronization. "
                                                           "Existing lines can't be deleted."))
                if invoice.is_direct_invoice and invoice.state == 'draft':
                    direct_invoice_ids.append(invoice.id)
                    # find account_bank_statement_lines and use this to delete the account_moves and associated records
                    absl_ids = abst_obj.search(cr, uid,
                                               [('invoice_id', '=', invoice.id)],
                                               order='NO_ORDER')
                    if absl_ids:
                        abst_obj.unlink_moves(cr, uid, absl_ids, context)
        # Normal behaviour
        res = super(account_invoice_line, self).unlink(cr, uid, ids, context)
        # See all direct invoice
        for inv in self.pool.get('account.invoice').browse(cr, uid, direct_invoice_ids):
            amount = 0.0
            for l in inv.invoice_line:
                amount += l.price_subtotal
            self.pool.get('account.invoice').write(cr, uid, [inv.id], {'check_total': amount}, context)
            self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in inv.register_line_ids], {'amount': -1 * amount}, context)
        return res

    def button_open_analytic_lines(self, cr, uid, ids, context=None):
        """
        Return analytic lines linked to this invoice line.
        First we takes all journal items that are linked to this invoice line.
        Then for all journal items, we take all analytic journal items.
        Finally we display the result for "button_open_analytic_corrections" of analytic lines
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        al_ids = []
        # Browse give invoice lines
        for il in self.browse(cr, uid, ids, context=context):
            if il.move_lines:
                for ml in il.move_lines:
                    if ml.analytic_lines:
                        al_ids += [x.id for x in ml.analytic_lines]
        return self.pool.get('account.analytic.line').button_open_analytic_corrections(cr, uid, al_ids, context=context)

    def onchange_donation_product(self, cr, uid, ids, product_id, qty, currency_id, context=None):
        res = {'value': {}}
        if product_id:
            p_info = self.pool.get('product.product').read(cr, uid, product_id, ['donation_expense_account', 'partner_ref', 'standard_price', 'categ_id'], context=context)
            if p_info['donation_expense_account']:
                res['value']['account_id'] = p_info['donation_expense_account'][0]
            elif p_info['categ_id']:
                categ = self.pool.get('product.category').read(cr, uid, p_info['categ_id'][0], ['donation_expense_account'])
                if categ['donation_expense_account']:
                    res['value']['account_id'] = categ['donation_expense_account'][0]
            if p_info['partner_ref']:
                res['value']['name'] = p_info['partner_ref']
            if p_info['standard_price']:
                std_price = p_info['standard_price']
                company_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
                if company_curr_id and company_curr_id != currency_id:
                    std_price = self.pool.get('res.currency').compute(cr, uid, company_curr_id, currency_id, std_price, context=context)
                res['value']['price_unit'] = std_price
                res['value']['price_subtotal'] = (qty or 0) * std_price
        return res

    def onchange_donation_qty_price(self, cr, uid, ids, qty, price_unit, context=None):
        return {'value': {'price_subtotal': (qty or 0) * (price_unit or 0)}}


account_invoice_line()


class res_partner(osv.osv):
    _description='Partner'
    _inherit = "res.partner"

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _get_search_by_invoice_type(self, cr, uid, obj, name, args,
                                    context=None):
        res = []
        if not len(args):
            return res
        if context is None:
            context = {}
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        if not args[0][2]:
            return res

        invoice_type = context.get('type', False)
        if invoice_type:
            if invoice_type in ('in_invoice', 'in_refund', ):
                # in invoices: only supplier partner
                res = [('supplier', '=', True)]
            elif invoice_type in ('out_invoice', 'out_refund', ):
                # out invoices: only customer partner
                res = [('customer', '=', True)]

        return res

    _columns = {
        'by_invoice_type': fields.function(_get_fake, type='boolean',
                                           fnct_search=_get_search_by_invoice_type, method=True),
    }

    def name_search(self, cr, uid, name='', args=None, operator='ilike',
                    context=None, limit=100):
        # BKLG-50: IN/OUT invoice/refund partner autocompletion filter
        # regarding supplier/customer
        if context is None:
            context = {}
        if args is None:
            args = []

        alternate_domain = False
        invoice_type = context.get('type', False)
        if invoice_type:
            if invoice_type in ('in_invoice', 'in_refund', ):
                alternate_domain = [('supplier', '=', True)]
            elif invoice_type in ('out_invoice', 'out_refund', ):
                alternate_domain = [('customer', '=', True)]
        if alternate_domain:
            args += alternate_domain

        return super(res_partner, self).name_search(cr, uid, name=name,
                                                    args=args, operator=operator, context=context, limit=limit)

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
