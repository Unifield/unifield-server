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

from osv import osv, fields
from tools.translate import _
import time

class account_invoice_refund(osv.osv_memory):
    _name = 'account.invoice.refund'
    _inherit = 'account.invoice.refund'

    def _get_journal(self, cr, uid, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        # @@@override@account.wizard.account_invoice_refund.py
        obj_journal = self.pool.get('account.journal')
        obj_inv = self.pool.get('account.invoice')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if context is None:
            context = {}
        args = [('type', '=', 'sale_refund')]
        doc_to_refund_id = context.get('active_ids') and context['active_ids'][0]
        if doc_to_refund_id:
            source_type = obj_inv.read(cr, uid, doc_to_refund_id, ['type'], context=context)['type']
            if source_type in ('in_invoice', 'in_refund'):
                args = [('type', '=', 'purchase_refund')]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        journal = obj_journal.search(cr, uid, args, order='id', limit=1, context=context)
        return journal and journal[0] or False

    def _get_document_date(self, cr, uid, context=None):
        active_ids = context.get('active_ids', [])
        if active_ids:
            invoice_module = self.pool.get('account.invoice')
            doc_date = invoice_module.read(cr, uid, active_ids[0], ['document_date'],
                                           context=context)['document_date']
            return doc_date
        return time.strftime('%Y-%m-%d')

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        jtype = 'sale_refund'
        if context.get('journal_type'):
            jtype = isinstance(context['journal_type'], list) and context['journal_type'][0] or context['journal_type']
        if jtype in ('sale', 'sale_refund'):
            jtype = 'sale_refund'
        else:
            jtype = 'purchase_refund'
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        for field in res['fields']:
            if field == 'journal_id' and user.company_id.instance_id:
                journal_domain = [('type', '=', jtype), ('is_current_instance', '=', True)]
                journal_select = journal_obj._name_search(cr, uid, '', journal_domain, context=context, limit=None, name_get_uid=1)
                res['fields'][field]['selection'] = journal_select
                res['fields'][field]['domain'] = journal_domain
        return res

    _columns = {
        'date': fields.date('Posting date'),
        'document_date': fields.date('Document Date', required=True),
    }

    _defaults = {
        'document_date': _get_document_date,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        #UTP-961: refund DI: only refund option is available
        'filter_refund': 'refund',
        'journal_id': _get_journal,  # US-193
    }

    def onchange_date(self, cr, uid, ids, date, context=None):
        res = {}
        # Some verifications
        if not context:
            context = {}
        if date:
            res.update({'value': {'document_date' : date}})
        return res

    def _hook_fields_for_modify_refund(self, cr, uid, *args):
        """
        Add analytic_distribution_id field in result
        """
        res = super(account_invoice_refund, self)._hook_fields_for_modify_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        return res

    def _hook_fields_m2o_for_modify_refund(self, cr, uid, *args):
        """
        Add analytic_distribution_id field in result
        """
        res = super(account_invoice_refund, self)._hook_fields_m2o_for_modify_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        return res

    def _hook_create_refund(self, cr, uid, inv_ids, date, period, description, journal_id, form, context=None):
        """
        Permits to adapt refund creation
        """
        if form.get('document_date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               form['document_date'], date)
            return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, form['document_date'], context=context)
        else:
            return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, context=context)

    def _hook_create_invoice(self, cr, uid, data, form, *args):
        """
        Permits to adapt invoice creation
        """
        if form.get('document_date', False) and form.get('date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               form['document_date'], form['date'])
            data.update({'document_date': form['document_date']})
        return super(account_invoice_refund, self)._hook_create_invoice(cr, uid, data, form)

    def _hook_get_period_from_date(self, cr, uid, invoice_id, date=False, period=False):
        """
        Get period regarding given date
        """
        res = super(account_invoice_refund, self)._hook_get_period_from_date(cr, uid, invoice_id, date, period)
        if date:
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, date)
            if period_ids and isinstance(period_ids, list):
                res = period_ids[0]
        return res

    def compute_refund(self, cr, uid, ids, mode='refund', context=None):
        if mode == 'modify' or mode == 'cancel':
            invoice_obj = self.pool.get('account.invoice')
            inv_ids = context.get('active_ids', [])
            invoices = invoice_obj.browse(cr, uid, inv_ids, context=context)
            for invoice in invoices:
                if invoice.imported_state == 'partial':
                    raise osv.except_osv(_('Error !'), _('You can not refund-modify nor refund-cancel an invoice partially imported in a register.'))

        return super(account_invoice_refund, self).compute_refund(cr, uid, ids, mode=mode, context=context)



account_invoice_refund()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
