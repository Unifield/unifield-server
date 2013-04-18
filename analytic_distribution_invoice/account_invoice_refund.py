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
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if context is None:
            context = {}
        args = [('type', '=', 'sale_refund')]
        if context.get('type', False):
            if context['type'] in ('in_invoice', 'in_refund'):
                args = [('type', '=', 'purchase_refund')]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        journal = obj_journal.search(cr, uid, [('type', '=', 'purchase_refund')])
        return journal and journal[0] or False

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        journal_obj = self.pool.get('account.journal')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        type = context.get('journal_type', 'sale_refund')
        if type in ('sale', 'sale_refund'):
            type = 'sale_refund'
        else:
            type = 'purchase_refund'
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        for field in res['fields']:
            if field == 'journal_id' and user.company_id.instance_id:
                journal_select = journal_obj._name_search(cr, uid, '', [('type', '=', type),('is_current_instance','=',True)], context=context, limit=None, name_get_uid=1)
                res['fields'][field]['selection'] = journal_select
        return res
    
    _columns = {
        'date': fields.date('Posting date'),
        'document_date': fields.date('Document Date', required=True),
    }
    
    _defaults = {
        'document_date': lambda *a: time.strftime('%Y-%m-%d'),
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

    def _hook_create_refund(self, cr, uid, inv_ids, date, period, description, journal_id, form):
        """
        Permits to adapt refund creation
        """
        if form.get('document_date', False):
            if date < form['document_date']:
                raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
            return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, form['document_date'])
        else:
            return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id)

    def _hook_create_invoice(self, cr, uid, data, form, *args):
        """
        Permits to adapt invoice creation
        """
        if form.get('document_date', False) and form.get('date', False):
            if form['date'] < form['document_date']:
                raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
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

account_invoice_refund()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
