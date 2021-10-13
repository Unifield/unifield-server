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
        obj_journal = self.pool.get('account.journal')
        obj_inv = self.pool.get('account.invoice')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if context is None:
            context = {}
        args = [('type', '=', 'sale_refund')]
        # in case of a DI refund from a register line use the dir_invoice_id in context
        doc_to_refund_id = context.get('dir_invoice_id', False) or (context.get('active_ids') and context['active_ids'][0])
        if doc_to_refund_id:
            source = obj_inv.read(cr, uid, doc_to_refund_id, ['type', 'is_intermission', 'doc_type', 'journal_id'], context=context)
            if source['doc_type'] == 'stv':
                if source['journal_id']:
                    # by default use the same journal for the refund
                    args = [('id', '=', source['journal_id'][0])]
                else:
                    args = [('type', '=', 'sale')]
            elif source['doc_type'] == 'isi':
                args = [('type', '=', 'purchase'), ('code', '=', 'ISI')]
            elif source['is_intermission']:
                args = [('type', '=', 'intermission')]
            elif source['type'] in ('in_invoice', 'in_refund'):
                args = [('type', '=', 'purchase_refund')]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        journal = obj_journal.search(cr, uid, args, order='id', limit=1, context=context)
        return journal and journal[0] or False

    def _get_document_date(self, cr, uid, context=None):
        if context is None:
            context = {}
        invoice_id = context.get('dir_invoice_id') or (context.get('active_ids') and context['active_ids'][0])
        if invoice_id:
            invoice_module = self.pool.get('account.invoice')
            doc_date = invoice_module.read(cr, uid, invoice_id, ['document_date'],
                                           context=context)['document_date']
            return doc_date
        return time.strftime('%Y-%m-%d')

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if context.get('doc_type', '') == 'stv':
            jtype = 'sale'
        elif context.get('doc_type', '') == 'isi':
            jtype = 'purchase'
        else:
            jtype = 'sale_refund'
            if context.get('journal_type'):
                jtype = isinstance(context['journal_type'], list) and context['journal_type'][0] or context['journal_type']
            if jtype in ('sale', 'sale_refund'):
                jtype = 'sale_refund'
            elif jtype != 'intermission':  # for IVO/IVI keep using the Interm. journal
                jtype = 'purchase_refund'
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        for field in res['fields']:
            if field == 'journal_id' and user.company_id.instance_id:
                journal_domain = [('type', '=', jtype), ('is_current_instance', '=', True)]
                if context.get('doc_type', '') == 'isi':
                    journal_domain.append(('code', '=', 'ISI'))
                journal_select = journal_obj._name_search(cr, uid, '', journal_domain, context=context, limit=None, name_get_uid=1)
                res['fields'][field]['selection'] = journal_select
                res['fields'][field]['domain'] = journal_domain
        return res

    _columns = {
        'date': fields.date('Posting date'),
        'document_date': fields.date('Document Date', required=True),
        'is_intermission': fields.boolean("Wizard opened from an Intermission Voucher", readonly=True),
        'is_stv': fields.boolean("Wizard opened from a Stock Transfer Voucher", readonly=True),
        'is_isi': fields.boolean("Wizard opened from an Intersection Supplier Invoice", readonly=True),
        'counterpart_inv_status': fields.char('Counterpart Invoice Status', size=24, readonly=True),
    }

    def _get_refund(self, cr, uid, context=None):
        """
        Returns the default value for the 'filter_refund' field depending on the context
        """
        if context is None:
            context = {}
        if context.get('is_intermission', False) or context.get('doc_type', '') == 'stv':
            return 'modify'
        return 'refund'  # note that only the "Refund" option is available in DI

    def _get_is_intermission(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from an Intermission Voucher
        """
        if context is None:
            context = {}
        return context.get('is_intermission', False)

    def _get_is_stv(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from a Stock Transfer Voucher
        """
        if context is None:
            context = {}
        return context.get('doc_type', '') == 'stv'

    def _get_is_isi(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from an Intersection Supplier Invoice
        """
        if context is None:
            context = {}
        return context.get('doc_type', '') == 'isi'

    def _get_counterpart_inv_status(self, cr, uid, context=None):
        """
        Returns the "Counterpart Invoice Status" of the invoice being refunded
        """
        if context is None:
            context = {}
        inv_obj = self.pool.get('account.invoice')
        status = ''
        if context.get('active_id'):
            status = inv_obj.read(cr, uid, context['active_id'], ['counterpart_inv_status'])['counterpart_inv_status'] or ''
        return status

    _defaults = {
        'document_date': _get_document_date,
        'filter_refund': _get_refund,
        'journal_id': _get_journal,  # US-193
        'is_intermission': _get_is_intermission,
        'is_stv': _get_is_stv,
        'is_isi': _get_is_isi,
        'counterpart_inv_status': _get_counterpart_inv_status,
    }

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

    def _hook_create_invoice(self, cr, uid, data, form, context=None):
        """
        Permits to adapt invoice creation
        """
        if form.get('document_date', False) and form.get('date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               form['document_date'], form['date'])
            data.update({'document_date': form['document_date']})
        return super(account_invoice_refund, self)._hook_create_invoice(cr, uid, data, form, context=context)

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
            inv_ids = context.get('dir_invoice_id') and [context['dir_invoice_id']] or context.get('active_ids', [])
            invoices = invoice_obj.browse(cr, uid, inv_ids, context=context)
            for invoice in invoices:
                if invoice.imported_state == 'partial':
                    raise osv.except_osv(_('Error !'), _('You can not refund-modify nor refund-cancel an invoice partially imported in a register.'))

        return super(account_invoice_refund, self).compute_refund(cr, uid, ids, mode=mode, context=context)



account_invoice_refund()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
