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
from ..register_tools import _get_date_in_period
from time import strftime


class wizard_import_cheque_lines(osv.osv_memory):
    """
    Content all lines that have been imported from a cheque register.
    """
    _name = 'wizard.import.cheque.lines'
    _description = 'Cheque register lines'
    _columns = {
        'partner_id': fields.many2one('res.partner', string='Partner', readonly=True),
        'ref': fields.char('Ref.', size=64, readonly=True),
        'number': fields.char('Number', size=64, readonly=True),
        'supplier_ref': fields.char('Supplier Inv. Ref.', size=64, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", readonly=True),
        'date_maturity': fields.date('Due Date', readonly=True),
        'date': fields.date('Posting Date', readonly=False, required=True),
        'document_date': fields.date('Document Date', readonly=False, required=True),
        'amount_to_pay': fields.integer('Amount to pay', readonly=True),
        'amount_currency': fields.integer('Amount currency', readonly=True),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True),
        'line_id': fields.many2one('account.move.line', string="Invoice", required=True),
        'wizard_id': fields.many2one('wizard.import.cheque', string='wizard'),
        'cheque_number': fields.char(string="Cheque Number", size=120, readonly=True),
        'partner_txt': fields.char('Third Party', size=255, readonly=True),
        'employee_id': fields.many2one('hr.employee', string="Employee", readonly=True),
        'transfer_journal_id': fields.many2one('account.journal', string="Transfer Journal", readonly=True),
    }

wizard_import_cheque_lines()

class wizard_import_cheque(osv.osv_memory):
    """
    Wizard to select some cheque register lines in order to import them into a bank statement.
    """
    _name = 'wizard.import.cheque'
    _description = 'Import cheque register from a bank statement'
    _columns = {
        'line_ids': fields.many2many('account.move.line', 'imported_cheque', 'wizard_id', 'move_line_id', string="Imported Cheques"),
        'imported_lines_ids': fields.one2many('wizard.import.cheque.lines', 'wizard_id', string=''),
        'statement_id': fields.many2one('account.bank.statement', string='Register', required=True, help="Register that we come from."),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True, help="Help to filter cheque regarding currency."),
        'period_id': fields.many2one('account.period', string="Period", required=True, help="Useful for filtering account move line that are in the same period"),
        'state': fields.selection( (('draft', 'Draft'), ('open', 'Open')), string="State", required=True),
        'date': fields.date('Posting Date', required=False),
        'document_date': fields.date('Document Date', required=False),
        'journal_id': fields.many2one('account.journal', string="Cheque journal to use", required=True, help="The journal the wizard will use to display lines to import"),
        'is_imported': fields.boolean("is wizard already imported"),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'is_imported': False,
    }

    def action_import(self, cr, uid, ids, context=None):
        """
        Import some cheque statement line into wizard.import.cheque.lines before process.
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.line_ids:
            raise osv.except_osv(_('Error'), _('No entries ! Please select some entries then click on Import button.'))

        imported_lines = [x.line_id.id for x in wizard.imported_lines_ids]
        new_lines = []
        date = wizard.date or None
        document_date = wizard.document_date or None
        for line in wizard.line_ids:

            if line.id not in imported_lines:
                if not date:
                    date = line.date
                vals = {
                    'line_id': line.id or None,
                    'partner_id': line.partner_id.id or None,
                    'ref': line.ref or None,
                    'number': line.invoice.number or None,
                    'cheque_number': line.cheque_number or None,
                    'supplier_ref': line.invoice.name or None,
                    'account_id': line.account_id.id or None,
                    'date_maturity': line.date_maturity or None,
                    'date': _get_date_in_period(self, cr, uid, date, wizard.period_id.id, context=context),
                    'amount_to_pay': line.amount_to_pay or None,
                    'amount_currency': line.amount_currency or None,
                    'currency_id': line.currency_id.id or None,
                    'wizard_id': wizard.id or None,
                    'document_date': document_date or None,
                    'partner_txt': line.partner_txt or None,
                    'employee_id': line.employee_id and line.employee_id.id or None,
                    'transfer_journal_id': line.transfer_journal_id and line.transfer_journal_id.id or None,
                }
                new_lines.append((0, 0, vals))
        # Add lines to the imported_lines, flush them from the first tree and change state of the wizard
        self.write(cr, uid, ids, {'state': 'open', 'line_ids': [(6, 0, [])], 'imported_lines_ids': new_lines, 'date': '', 'document_date': '',}, context=context)
        # Refresh wizard to display changes
        return {
            'type': 'ir.actions.act_window',
         'res_model': 'wizard.import.cheque',
         'view_type': 'form',
         'view_mode': 'form',
         'res_id': ids[0],
         'context': context,
         'target': 'new',
        }

    def action_confirm(self, cr, uid, ids, context=None):
        """
        Import some cheque statement lines into the bank statement and temp post them.
        """
        # Some verifications
        if not ids:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        absl_obj = self.pool.get('account.bank.statement.line')
        curr_date = strftime('%Y-%m-%d')

        # US-212: If multi-click on import button, we import only the first
        if wizard.is_imported:
            return {}
        self.write(cr, uid, ids, {'is_imported': True}, context=context)

        # Process lines
        absl_lines = []
        for imported_line in wizard.imported_lines_ids:
            line = imported_line.line_id
            if absl_obj.search_exist(cr, uid, [('from_import_cheque_id', '=', line.id)], context=context):
                raise osv.except_osv(_('Warning'), _('The Cheque %s has already been imported.') % line.cheque_number or line.name or line.ref or '')
            total = line.amount_currency
            if not imported_line.document_date:
                raise osv.except_osv(_('Warning'), _('Please add a Document Date on imported lines.'))

            vals = {
                'name': 'Imported Cheque: ' + (line.cheque_number or line.name or line.ref or ''),
                'ref': line.ref,
                'date': _get_date_in_period(self, cr, uid, imported_line.date or curr_date, wizard.period_id.id, context=context),
                'document_date': imported_line.document_date,
                'statement_id': wizard.statement_id.id,
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id,
                'employee_id': line.employee_id and line.employee_id.id or None,
                'transfer_journal_id': line.transfer_journal_id and line.transfer_journal_id.id or None,
                'amount': total,
                'from_import_cheque_id': line.id,
            }
            # create the register line
            absl_id = absl_obj.create(cr, uid, vals, context=context)
            absl_lines.append(absl_id)
            # post the register line
            absl_obj.posting(cr, uid, [absl_id], 'temp', context=context)

        if not len(absl_lines):
            raise osv.except_osv(_('Warning'), _('No line created!'))
        return { 'type': 'ir.actions.act_window_close', 'st_line_ids': absl_lines, 'o2m_refresh': 'line_ids'}

wizard_import_cheque()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
