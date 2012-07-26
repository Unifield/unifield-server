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
from tools.translate import _
from time import strftime
from register_accounting.register_tools import _get_third_parties, _set_third_parties
from lxml import etree

class journal_items_corrections_lines(osv.osv_memory):
    _name = 'wizard.journal.items.corrections.lines'
    _description = 'Journal items corrections lines'

    _columns = {
        'move_line_id': fields.many2one('account.move.line', string="Account move line", readonly=True, required=True),
        'wizard_id': fields.many2one('wizard.journal.items.corrections', string="wizard"),
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'move_id': fields.many2one('account.move', string="Entry sequence", readonly=True),
        'ref': fields.char(string="Reference", size=254, readonly=True),
        'journal_id': fields.many2one('account.journal', string="Journal Code", readonly=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True),
        'date': fields.date('Posting date', readonly=True),
        # Third Parties Fields - BEGIN
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'register_id': fields.many2one("account.bank.statement", "Register"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
#        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
#            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
#            multi="third_parties_key"),
#        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
#        'third_parties': fields.function(_get_third_parties, type='reference', method=True, 
#            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
#            help="To use for python code when registering", multi="third_parties_key"),
        # Third Parties fields - END
        'debit_currency': fields.float('Book. Debit', readonly=True),
        'credit_currency': fields.float('Book. Credit', readonly=True),
        'currency_id': fields.many2one('res.currency', string="Book. Curr.", readonly=True),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic Distribution", readonly=True),
    }

    _defaults = {
        'from_donation': lambda *a: False,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change account_id domain if account is donation expense
        """
        if not context:
            context = {}
        view = super(journal_items_corrections_lines, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if context and context.get('from_donation_account', False):
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath('//field[@name="account_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('type_for_register', '=', 'donation')]")
            view['arch'] = etree.tostring(tree)
        return view

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Open an analytic distribution wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Add context in order to know we come from a correction wizard
        this_line = self.browse(cr, uid, ids[0], context=context)
        wiz = this_line.wizard_id
        context.update({'from': 'wizard.journal.items.corrections', 'wiz_id': wiz.id or False})
        # Get distribution
        distrib_id = False
        if wiz and wiz.move_line_id and wiz.move_line_id.analytic_distribution_id:
            distrib_id = wiz.move_line_id.analytic_distribution_id.id or False
        if not distrib_id:
            distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
            self.pool.get('account.move.line').write(cr, uid, wiz.move_line_id.id, {'analytic_distribution_id': distrib_id})
        # Prepare values
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wiz.move_line_id.currency_id and wiz.move_line_id.currency_id.id or company_currency
        amount = wiz.move_line_id.amount_currency and wiz.move_line_id.amount_currency or 0.0
        vals = {
            'total_amount': amount,
            'move_line_id': wiz.move_line_id and wiz.move_line_id.id,
            'currency_id': currency or False,
            'old_account_id': wiz.move_line_id and wiz.move_line_id.account_id and wiz.move_line_id.account_id.id or False,
            'distribution_id': distrib_id,
            'state': 'dispatch', # Be very careful, if this state is not applied when creating wizard => no lines displayed
            'date': wiz.date or strftime('%Y-%m-%d'),
            'account_id': this_line.account_id and this_line.account_id.id or False,
        }
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Change wizard state to 'correction' in order to display mandatory fields
        wiz_obj.write(cr, uid, [wiz_id], {'state': 'correction'}, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'name': 'Analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

journal_items_corrections_lines()

class journal_items_corrections(osv.osv_memory):
    _name = 'wizard.journal.items.corrections'
    _description = 'Journal items corrections wizard'

    _columns = {
        'date': fields.date(string="Correction date", states={'open':[('required', True)]}),
        'move_line_id': fields.many2one('account.move.line', string="Move Line", required=True, readonly=True),
        'to_be_corrected_ids': fields.one2many('wizard.journal.items.corrections.lines', 'wizard_id', string='', help='Line to be corrected'),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open')], string="state"),
        'from_donation': fields.boolean('From Donation account?'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def onchange_date(self, cr, uid, ids, date, context=None):
        """
        Write date on this wizard.
        NB: this is essentially for analytic distribution correction wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            return False
        return self.write(cr, uid, ids, {'date': date}, context=context)

    def create(self, cr, uid, vals, context=None):
        """
        Fill in all elements in our wizard with given move_line_id field
        """
        # Verifications
        if not context:
            context = {}
        # Normal mechanism
        res = super(journal_items_corrections, self).create(cr, uid, vals, context=context)
        # Process given move line to complete wizard
        if 'move_line_id' in vals:
            move_line_id = vals.get('move_line_id')
            move_line = self.pool.get('account.move.line').browse(cr, uid, [move_line_id])[0]
            corrected_line_vals = {
                'wizard_id': res,
                'move_line_id': move_line.id,
                'account_id': move_line.account_id.id,
                'move_id': move_line.move_id.id,
                'ref': move_line.ref,
                'journal_id': move_line.journal_id.id,
                'date': move_line.date,
                'debit_currency': move_line.debit_currency,
                'credit_currency': move_line.credit_currency,
                'period_id': move_line.period_id.id,
                'currency_id': move_line.currency_id.id,
                'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                'employee_id': move_line.employee_id and move_line.employee_id.id or None,
                'register_id': move_line.register_id and move_line.register_id.id or None,
#                'partner_type_mandatory': move_line.partner_type_mandatory or None,
                'analytic_distribution_id': move_line.analytic_distribution_id and move_line.analytic_distribution_id.id or None,
            }
            self.pool.get('wizard.journal.items.corrections.lines').create(cr, uid, corrected_line_vals, context=context)
        return res

    def compare_lines(self, cr, uid, old_line_id=None, new_line_id=None, context=None):
        """
        Compare an account move line to a wizard journal items corrections lines regarding 3 fields:
         - account_id (1)
         - partner_type (partner_id, employee_id or register_id) (2)
         - analytic_distribution_id (4)
        Then return the sum.
        """
        # Verifications
        if not context:
            context = {}
        if not old_line_id or not new_line_id:
            raise osv.except_osv(_('Error'), _('An ID is missing!'))
        # Prepare some values
        res = 0
        # Lines
        old_line = self.pool.get('account.move.line').browse(cr, uid, [old_line_id], context=context)[0]
        new_line = self.pool.get('wizard.journal.items.corrections.lines').browse(cr, uid, [new_line_id], context=context)[0]
        # Fields
        old_account = old_line.account_id and old_line.account_id.id or False
        new_account = new_line.account_id and new_line.account_id.id or False
        old_partner = old_line.partner_id and old_line.partner_id.id or False
        new_partner = new_line.partner_id and new_line.partner_id.id or False
        old_distrib = old_line.analytic_distribution_id and old_line.analytic_distribution_id.id or False
        new_distrib = new_line.analytic_distribution_id and new_line.analytic_distribution_id.id or False
        if cmp(old_account, new_account):
            res += 1
        if cmp(old_partner, new_partner): # FIXME !!!!! or cmp(old_line.employee_id, new_line.employee_id) or 
            # cmp(old_line.register_id, new_line.register_id):
            res += 2
        if cmp(old_distrib, new_distrib):
            res += 4
        return res

    def action_reverse(self, cr, uid, ids, context=None):
        """
        Do a reverse from the lines attached to this wizard
        NB: The reverse is done on the first correction journal found (type = 'correction')
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Verify that date is superior to line's date
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.move_line_id and wiz.move_line_id.date:
                if not wiz.date >= wiz.move_line_id.date:
                    raise osv.except_osv(_('Warning'), _('Please insert a correction date from the entry date onwards.'))
        # Retrieve values
        wizard = self.browse(cr, uid, ids[0], context=context)
        aml_obj = self.pool.get('account.move.line')
        # Do reverse
        res, move_ids = aml_obj.reverse_move(cr, uid, [wizard.move_line_id.id], wizard.date, context=context)
        return {'type': 'ir.actions.act_window_close', 'success_move_line_ids': res}

    def action_confirm(self, cr, uid, ids, context=None, distrib_id=False):
        """
        Do a correction from the given line
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Verify that date is superior to line's date
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.move_line_id and wiz.move_line_id.date:
                if not wiz.date >= wiz.move_line_id.date:
                    raise osv.except_osv(_('Warning'), _('Please insert a correction date from the entry date onwards.'))
        # Retrieve values
        wizard = self.browse(cr, uid, ids[0], context=context)
        wiz_line_obj = self.pool.get('wizard.journal.items.corrections.lines')
        aml_obj = self.pool.get('account.move.line')
        # Fetch old line
        old_line = wizard.move_line_id
        # Verify what have changed between old line and new one
        new_lines = wizard.to_be_corrected_ids
        # compare lines
        comparison = self.compare_lines(cr, uid, old_line.id, new_lines[0].id, context=context)
        # Result
        res = [] # no result yet
        # Correct account
        if comparison == 1:
#            if not old_line.statement_id:
#                raise osv.except_osv(_('Error'), _('Account correction is only possible on move line that come from a register!'))
            res = aml_obj.correct_account(cr, uid, [old_line.id], wizard.date, new_lines[0].account_id.id, distrib_id, context=context)
            if not res:
                raise osv.except_osv(_('Error'), _('No account changed!'))
        # Correct third parties
        elif comparison == 2:
            if not old_line.statement_id:
                res = aml_obj.correct_partner_id(cr, uid, [old_line.id], wizard.date, new_lines[0].partner_id.id, context=context)
                if not res:
                    raise osv.except_osv(_('Error'), 
                        _('No partner changed! Verify that the Journal Entries attached to this line was not modify previously.'))
#        elif old_line.partner_id and old_line.partner_id.id != new_lines[0].partner_id.id:
#            raise osv.except_osv('Information', 'Entering third parties change')
        elif comparison == 4:
            raise osv.except_osv('Warning', 'Do analytic distribution reallocation here!')
        elif comparison in [3, 5, 7]:
            raise osv.except_osv(_('Error'), _("You're just allowed to change ONE field amoungst Account, Third Party or Analytical Distribution"))
        else:
            raise osv.except_osv(_('Warning'), _('No modifications seen!'))
        return {'type': 'ir.actions.act_window_close', 'success_move_line_ids': res}

journal_items_corrections()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
