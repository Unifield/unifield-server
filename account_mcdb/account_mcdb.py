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
        'journal_ids': fields.many2many(obj='account.journal', rel='account_journal_mcdb', id1='mcdb_id', id2='journal_id', string="Journal Code"),
        'abs_id': fields.many2one('account.bank.statement', string="Register Code"), # Change into many2many ?
        'company_id': fields.many2one('res.company', string="Proprietary instance"),
        'posting_date_from': fields.date('First posting date'),
        'posting_date_to': fields.date('Ending posting date'),
        'document_date_from': fields.date('First document date'),
        'document_date_to': fields.date('Ending document date'),
        'period_ids': fields.many2many(obj='account.period', rel="account_period_mcdb", id1="mcdb_id", id2="period_id", string="Accounting Period"),
        'account_ids': fields.many2many(obj='account.account', rel='account_account_mcdb', id1='mcdb_id', id2='account_id', string="Account Code"),
        'partner_id': fields.many2one('res.partner', string="Partner"),
        'employee_id': fields.many2one('hr.employee', string="Employee"),
        'register_id': fields.many2one('account.bank.statement', string="Register"),
        'reconciled': fields.selection([('reconciled', 'Reconciled'), ('unreconciled', 'NOT reconciled')], string='Reconciled?'),
        'functional_currency_id': fields.many2one('res.currency', string="Functional currency", readonly=True),
        'amount_func_from': fields.float('Begin amount in functional currency'),
        'amount_func_to': fields.float('Ending amount in functional currency'),
        'booking_currency_id': fields.many2one('res.currency', string="Booking currency"),
        'amount_book_from': fields.float('Begin amount in booking currency'),
        'amount_book_to': fields.float('Ending amount in booking currency'),
        'output_currency_id': fields.many2one('res.currency', string="Output currency", readonly=True),
        'amount_out_from': fields.float('Begin amount in output currency', readonly=True),
        'amount_out_to': fields.float('Ending amount in output currency', readonly=True),
        'currency_choice': fields.selection([('booking', 'Booking'), ('functional', 'Functional'), ('output', 'Output')], string="Currency type"),
        'currency_id': fields.many2one('res.currency', string="Currency"),
        'amount_from': fields.float('Begin amount in given currency type'),
        'amount_to': fields.float('Ending amount in given currency type'),
        'account_type_ids': fields.many2many(obj='account.account.type', rel='account_account_type_mcdb', id1='mcdb_id', id2='account_type_id', 
            string="Account type"),
        'reconcile_id': fields.many2one('account.move.reconcile', string="Reconcile Reference"),
        'ref': fields.char(string='Reference', size=255),
        'name': fields.char(string='Description', size=255),
        'rev_account_ids': fields.boolean('Reverse account(s) selection'),
        'model': fields.selection([('account.move.line', 'Journal Items'), ('account.analytic.line', 'Analytic Journal Items')], string="Type"),
        'display_in_output_currency': fields.many2one('res.currency', string='Display in output currency'),
        'fx_table_id': fields.many2one('res.currency.table', string="FX Table"),
        'analytic_account_ids': fields.many2many(obj='account.analytic.account', rel="account_analytic_mcdb", id1="mcdb_id", id2="analytic_account_id", 
            string="Analytic Account"),
    }

    _defaults = {
        'model': lambda self, cr, uid, c: c.get('from', 'account.move.line'),
        'functional_currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'currency_choice': lambda *a: 'booking',
    }

    def onchange_currency_choice(self, cr, uid, ids, choice, currency=False, func_curr=False, book_curr=False, mnt_func_from=0.0, mnt_func_to=0.0, mnt_book_from=0.0, mnt_book_to=0.0, context={}):
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
        for field in ['amount_book_from', 'amount_book_to', 'amount_func_from', 'amount_func_to', 'booking_currency_id', 'output_currency_id']:
            vals[field] = False
        # Fill in values
        if choice == 'functional':
            vals['currency_id'] = func_curr or False
        elif choice == 'booking':
            vals['currency_id'] = False
        elif choice == 'output':
            vals['output_currency_id'] = False
        return {'value': vals}

    def onchange_currency(self, cr, uid, ids, choice, currency, context={}):
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
        elif choice == 'output':
            vals['output_currency_id'] = currency
        return {'value': vals}

    def onchange_amount(self, cr, uid, ids, choice, amount, amount_type=None, context={}):
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
        elif choice == 'output':
            if amount_type == 'from':
                vals['amount_out_from'] = amount
            elif amount_type == 'to':
                vals['amount_out_to'] = amount
        return {'value': vals}

    def onchange_fx_table(self, cr, uid, ids, fx_table_id, context={}):
        """
        Update output currency domain in order to show right currencies attached to given fx table
        """
        res = {}
        # Some verifications
        if not context:
            context = {}
        if fx_table_id:
            res.update({'domain': {'display_in_output_currency': [('currency_table_id', '=', fx_table_id), ('active', 'in', ['True', 'False'])]}, 
                'value': {'display_in_output_currency' : False}})
        return res

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
            for m2m in [('account_ids', 'account_id'), ('account_type_ids', 'account_id.user_type'), ('period_ids', 'period_id'), 
                ('journal_ids', 'journal_id'), ('analytic_account_ids', 'account_id')]:
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
                            # Create domain and NEXT element (otherwise this give a bad domain)
                            domain.append((m2m[1], operator, tuple(account_ids)))
                            continue
                    domain.append((m2m[1], operator, tuple([x.id for x in getattr(wiz, m2m[0])])))
            # Then MANY2ONE fields
            for m2o in [('abs_id', 'statement_id'), ('company_id', 'company_id'), ('partner_id', 'partner_id'), ('employee_id', 'employee_id'), 
                ('register_id', 'register_id'), ('booking_currency_id', 'currency_id'), ('reconcile_id', 'reconcile_id')]:
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
            for curr in [booking, functional]: #FIXME:add functional when possible
                # Prepare some values
                mnt_from = getattr(wiz, curr[0]) or False
                mnt_to = getattr(wiz, curr[1]) or False
                field = curr[2]
                abs_from = abs(mnt_from)
                min_from = -1 * abs_from
                abs_to = abs(mnt_to)
                min_to = -1 * abs_to
                # domain elements initialisation
                domain_elements = []
                if mnt_from and mnt_to:
                    domain_elements = ['|', '&', (field, '>=', min_to), (field, '<=', min_from), '&', (field, '>=', abs_from), (field, '<=', abs_to)]
                elif mnt_from:
                    domain_elements = ['|', (field, '<=', min_from), (field, '>=', abs_from)]
                elif mnt_to:
                    domain_elements = ['&', (field, '>=', min_to), (field, '<=', abs_to)]
                # Add elements to domain which would be use for filtering
                for el in domain_elements:
                    domain.append(el)
            # Output currency display (with fx_table)
            if wiz.fx_table_id:
                context.update({'fx_table_id': wiz.fx_table_id.id, 'currency_table_id': wiz.fx_table_id.id})
            if wiz.display_in_output_currency:
                context.update({'output_currency_id': wiz.display_in_output_currency.id})
            # Return result in a search view
            view = 'account_move_line_mcdb_search_result'
            search_view = 'mcdb_view_account_move_line_filter'
            name = _('Journal Items MCDB result')
            if res_model == 'account.analytic.line':
                view = 'account_analytic_line_mcdb_search_result'
                search_view = 'mcdb_view_account_analytic_line_filter'
                name = _('Analytic Journal Items MCDB result')
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_mcdb', view)
            view_id = view_id and view_id[1] or False
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_mcdb', search_view)
            search_view_id = search_view_id and search_view_id[1] or False
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
        # Update context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Search view_id
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_mcdb', 'account_mcdb_form')
        view_id = view_id and view_id[1] or False
        return {
            'name': _('Multi-Criteria Data Browser'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.mcdb',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'context': context,
            'target': 'crush',
        }

account_mcdb()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
