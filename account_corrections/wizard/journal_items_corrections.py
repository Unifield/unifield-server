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

class journal_items_corrections_lines(osv.osv_memory):
    _name = 'wizard.journal.items.corrections.lines'
    _description = 'Journal items corrections lines'

    _columns = {
        'move_line_id': fields.many2one('account.move.line', string="Account move line", readonly=True, required=True),
        'wizard_id': fields.many2one('wizard.journal.items.corrections', string="wizard"),
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'move_id': fields.many2one('account.move', string="Entry sequence", readonly=True),
        'ref': fields.char(string="Reference", size=254, readonly=True),
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True),
        'date': fields.date('Posting date', readonly=True),
        # FIXME: add partner_type
        'debit': fields.float('Func. Out', readonly=True),
        'credit': fields.float('Func. In', readonly=True),
        'currency_id': fields.many2one('res.currency', string="Func. currency", readonly=True),
#        FIXME: add this field: 'analytic_distribution_id'
    }

journal_items_corrections_lines()

class journal_items_corrections(osv.osv_memory):
    _name = 'wizard.journal.items.corrections'
    _description = 'Journal items corrections wizard'

    _columns = {
        'date': fields.date(string="Correction date"),
        'move_line_id': fields.many2one('account.move.line', string="Move Line", required=True, readonly=True),
        'to_be_corrected_ids': fields.one2many('wizard.journal.items.corrections.lines', 'wizard_id', string='', help='Line to be corrected'),
    }

    def create(self, cr, uid, vals, context={}):
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
                'debit': move_line.debit,
                'credit': move_line.credit,
                'period_id': move_line.period_id.id,
                'currency_id': move_line.functional_currency_id.id,
#                FIXME: add this line: 'analytic_distribution_id': move_line.analytic_distribution_id,
            }
            self.pool.get('wizard.journal.items.corrections.lines').create(cr, uid, corrected_line_vals, context=context)
        return res

    def action_reverse(self, cr, uid, ids, context={}):
        """
        Do a reverse from the given line
        """
        return True

    def action_confirm(self, cr, uid, ids, context={}):
        """
        Do a correction from the given line
        """
        return True

journal_items_corrections()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
