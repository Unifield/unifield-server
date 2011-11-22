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

class account_mcdb(osv.osv_memory):
    _name = 'account.mcdb'

    _columns = {
        'journal_id': fields.many2one('account.journal', string="Journal Code"),
        'abs_id': fields.many2one('account.bank.statement', string="Register Code"), # Change into many2many ?
        'company_id': fields.many2one('res.company', string="Proprietary instance"),
        'posting_date': fields.date('Posting date'),
        'document_date': fields.date('Document date'),
        'period_id': fields.many2one('account.period', string="Accounting Period"),
        'account_ids': fields.many2many(obj='account.account', rel='account_account_mcdb', id1='mcdb_id', id2='account_id', string="Account Code"),
        'partner_id': fields.many2one('res.partner', string="Partner"),
        'employee_id': fields.many2one('hr.employee', string="Employee"),
        'register_id': fields.many2one('account.bank.statement', string="Register"),
        'reconciled': fields.selection([('reconciled', 'Reconciled'), ('unreconciled', 'NOT reconciled')], string='Reconciliation'),
        'booking_currency_id': fields.many2one('res.currency', string="Booking currency"),
        'amount_func_from': fields.float('Amount'),
        'amount_func_to': fields.float('to'),
        'amount_book_from': fields.float('Amount'),
        'amount_book_to': fields.float('to'),
        'account_type_ids': fields.many2many(obj='account.account.type', rel='account_account_type_mcdb', id1='mcdb_id', id2='account_type_id', string="Account type"),
        'reconcile_id': fields.many2one('account.move.reconcile', string="Reconcile Reference"),
        'ref': fields.char(string='Reference', size=255),
        'name': fields.char(string='Description', size=255),
        'model': fields.selection([('account.move.line', 'Journal Items'), ('account.analytic.line', 'Analytic Journal Items')], string="Type")
    }

    _defaults = {
        'model': lambda *a: 'account.move.line'
    }

    def button_validate(self, cr, uid, ids, context={}):
        """
        Validate current forms and give result
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain = []
        wiz = self.browse(cr, uid, [ids[0]], context=context)[0]
        res_model = wiz and wiz.model or False
        if res_model:
            # Prepare domain values
            # First many2many fields
            for m2m in [('account_ids', 'account_id'), ('account_type_ids', 'account_id.user_type')]:
                if getattr(wiz, m2m[0]):
                    domain.append((m2m[1], 'in', tuple([x.id for x in getattr(wiz, m2m[0])])))
            # Then many2one fields
            for m2o in [('journal_id', 'journal_id'), ('abs_id', 'statement_id'), ('company_id', 'company_id'), ('period_id', 'period_id'), 
                ('partner_id', 'partner_id'), ('employee_id', 'employee_id'), ('register_id', 'register_id'), ('booking_currency_id', 'currency_id'), 
                ('reconcile_id', 'reconcile_id')]:
                if getattr(wiz, m2o[0]):
                    domain.append((m2o[1], '=', getattr(wiz, m2o[0]).id))
            return {
                'name': _('Multi-criteria data browser result'),
                'type': 'ir.actions.act_window',
                'res_model': res_model,
                'view_type': 'form',
                'view_mode': 'tree',
                'view_id': False,
                'domain': domain,
                'context': context,
                'target': 'current',
            }
        return False

account_mcdb()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
