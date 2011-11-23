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

class account_mcdb(osv.osv_memory):
    _name = 'account.mcdb'

    _columns = {
        'journal_id': fields.many2one('account.journal', string="Journal Code"),
        'abs_id': fields.many2one('account.bank.statement', string="Register Code"), # Change into many2many ?
        'company_id': fields.many2one('res.company', string="Proprietary instance"),
        'posting_date_from': fields.date('First posting date'),
        'posting_date_to': fields.date('Ending posting date'),
        'document_date_from': fields.date('First document date', readonly=True),
        'document_date_to': fields.date('Ending document date', readonly=True),
        'period_id': fields.many2many(obj='account.period', rel="account_period_mcdb", id1="mcdb_id", id2="period_id", string="Accounting Period"),
        'account_ids': fields.many2many(obj='account.account', rel='account_account_mcdb', id1='mcdb_id', id2='account_id', string="Account Code"),
        'partner_id': fields.many2one('res.partner', string="Partner"),
        'employee_id': fields.many2one('hr.employee', string="Employee"),
        'register_id': fields.many2one('account.bank.statement', string="Register"),
        'reconciled': fields.selection([('reconciled', 'Reconciled'), ('unreconciled', 'NOT reconciled')], string='Reconciled?'),
        'functional_currency_id': fields.many2one('res.currency', string="Functional currency", readonly=True),
        'amount_func_from': fields.float('Begin amount in functional currency', readonly=True),
        'amount_func_to': fields.float('Ending amount in functional currency', readonly=True),
        'booking_currency_id': fields.many2one('res.currency', string="Booking currency"),
        'amount_book_from': fields.float('Begin amount in booking currency'),
        'amount_book_to': fields.float('Ending amount in booking currency'),
        'output_currency_id': fields.many2one('res.currency', string="Output currency", readonly=True),
        'amount_out_from': fields.float('Begin amount in output currency', readonly=True),
        'amount_out_to': fields.float('Ending amount in output currency', readonly=True),
        'account_type_ids': fields.many2many(obj='account.account.type', rel='account_account_type_mcdb', id1='mcdb_id', id2='account_type_id', string="Account type"),
        'reconcile_id': fields.many2one('account.move.reconcile', string="Reconcile Reference"),
        'ref': fields.char(string='Reference', size=255),
        'name': fields.char(string='Description', size=255),
        'rev_account_ids': fields.boolean('Reverse account selection'),
        'model': fields.selection([('account.move.line', 'Journal Items'), ('account.analytic.line', 'Analytic Journal Items')], string="Type")
    }

    _defaults = {
        'model': lambda *a: 'account.move.line',
        'functional_currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
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
            # First MANY2MANY fields
            for m2m in [('account_ids', 'account_id'), ('account_type_ids', 'account_id.user_type'), ('period_id', 'period_id')]:
                if getattr(wiz, m2m[0]):
                    operator = 'in'
                    # Special field : account_ids with reversal
                    if m2m[0] == 'account_ids' and wiz.rev_account_ids:
                        operator = 'not in'
                    # Search if a view account is given
                    if m2m[0] == 'account_ids':
                        account_ids = []
                        for account in getattr(wiz, m2m[0]):
                            if account.type == 'view':
                                search_ids = self.pool.get('account.account').search(cr, uid, [('id', 'child_of', [account.id])])
                                account_ids.append(search_ids)
                        if account_ids:
                            # Add default account_ids from wizard
                            account_ids.append([x.id for x in getattr(wiz, m2m[0])])
                            # Convert list in a readable list for openerp
                            account_ids = flatten(account_ids)
                            domain.append((m2m[1], operator, tuple(account_ids)))
                            continue
                    domain.append((m2m[1], operator, tuple([x.id for x in getattr(wiz, m2m[0])])))
            # Then MANY2ONE fields
            for m2o in [('journal_id', 'journal_id'), ('abs_id', 'statement_id'), ('company_id', 'company_id'), ('partner_id', 'partner_id'), 
                ('employee_id', 'employee_id'), ('register_id', 'register_id'), ('booking_currency_id', 'currency_id'), 
                ('reconcile_id', 'reconcile_id')]:
                if getattr(wiz, m2o[0]):
                    domain.append((m2o[1], '=', getattr(wiz, m2o[0]).id))
            # Finally others fields
            # LOOKS LIKE fields
            for ll in [('ref', 'ref'), ('name', 'name')]:
                if getattr(wiz, ll[0]):
                    domain.append((ll[1], 'ilike', '%%%s%%' % getattr(wiz, ll[0])))
            # DATE fields
            for sup in [('posting_date_from', 'date')]:
                if getattr(wiz, sup[0]):
                    domain.append((sup[1], '>=', getattr(wiz, sup[0])))
            for inf in [('posting_date_to', 'date')]:
                if getattr(wiz, inf[0]):
                    domain.append((inf[1], '<=', getattr(wiz, inf[0])))
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
            #+ For each case, here is what domain should be look like:
            #+ 1/ FROM is 0.0, TO is 0,0. Domain is []
            #+ 2/ FROM is 400, TO is 600. Domain is
            #+ ['|', '&', ('balance', '>=', -600), ('balance', '<=', -400), '&', ('balance', '>=', 400), ('balance', '<=', '600')]
            #+ 3/ FROM is 400, TO is 0.0. Domain is ['|', ('balance', '<=', -400), ('balance', '>=', 400)]
            #+ 4/ FROM is 0.0, TO is 600. Domain is ['&', ('balance', '>=', -600), ('balance', '<=', 600)]
            
            # prepare tuples that would be processed
            booking = ('amount_book_from', 'amount_book_to', 'amount_currency')
            functional = ('amount_func_from', 'amount_func_to', 'balance')
            for curr in [booking]: #FIXME:add functional when possible
                mnt_from = getattr(wiz, curr[0])
                mnt_to = getattr(wiz, curr[1])
                if mnt_from or mnt_to:
                    if mnt_from:
                        domain.append('|')
                    if mnt_to:
                        domain.append('&')
                        domain.append((curr[2], '>=', -1 * abs(mnt_to)))
                    if mnt_from:
                        domain.append((curr[2], '<=', -1 * abs(mnt_from)))
                    if mnt_from and mnt_to:
                        domain.append('&')
                    if mnt_from:
                        domain.append((curr[2], '>=', abs(mnt_from)))
                    if mnt_to:
                        domain.append((curr[2], '<=', abs(mnt_to)))
            # Return result in a search view
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

    def button_clear(self, cr, uid, ids, context={}):
        """
        Delete all fields from this object
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Search all fields
        vals = {}
        for el in self._columns:
            # exceptions (m2m or fields that shouldn't be deleted)
            if el.__str__() not in ['functional_currency_id', 'account_ids', 'account_type_ids']:
                vals.update({el.__str__(): False,})
        # Delete m2m links
        vals.update({'account_ids': [(6,0,[])], 'account_type_ids': [(6,0,[])]})
        self.write(cr, uid, ids, vals, context=context)
        return True

account_mcdb()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
