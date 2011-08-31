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

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'corrected': fields.boolean(string="Corrected", readonly=True, help="If true, this line has been corrected by an accounting correction wizard"),
        'corrected_line_id': fields.many2one('account.move.line', string="Corrected Line", readonly=True, help="Line that have been corrected by this line."),
    }

    _defaults = {
        'corrected': lambda *a: False,
    }

    def copy(self, cr, uid, id, defaults={}, context={}):
        """
        Copy a move line
        """
        defaults.update({
            'state': 'draft',
        })
        return super(account_move_line, self).copy(cr, uid, id, defaults, context=context)

    def button_do_accounting_corrections(self, cr, uid, ids, context={}):
        """
        Launch accounting correction wizard to do reverse or correction on selected move line.
        """
        # Verification
        if not context:
            context={}
        # Retrieve some values
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        # Create wizard
        wizard = wiz_obj.create(cr, uid, {'move_line_id': ids[0]}, context=context)
        # Change wizard state in order to change date requirement on wizard
        wiz_obj.write(cr, uid, [wizard], {'state': 'open'}, context=context)
        return {
            'name': "Accounting Corrections Wizard",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.journal.items.corrections',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wizard],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
            }
        }

    def button_open_corrections(self, cr, uid, ids, context={}):
        """
        Open all corrections linked to the given one
        """
        return True

    def correct_account(self, cr, uid, ids, date=None, new_account_id=None, context={}):
        """
        Correct given account_move_line by only changin account
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%d-%m')
        if not new_account_id:
            raise osv.except_osv(_('Error'), _('No new account_id given!'))
        # Prepare some values
        move_obj = self.pool.get('account.move')
        aml_obj = self.pool.get('account.move.line')
        j_obj = self.pool.get('account.journal')
        # Search correction journal
        j_corr_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        if not j_corr_ids:
            raise osv.except_osv(_('Error'), ('No correction journal found!'))
        # Search attached period
        period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], 
            context=context, limit=1, order='date_start, name')
        # Browse all given move line for correct them
        for ml in self.browse(cr, uid, ids, context=context):
            # Create a new move
            move_id = move_obj.create(cr, uid,{'journal_id': j_corr_ids[0], 'period_id': period_ids[0], 'date': date}, context=context)
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': date,
                'journal_id': j_corr_ids[0],
                'period_id': period_ids[0],
            }
            # Copy the line
            rev_line_id = aml_obj.copy(cr, uid, ml.id, vals, context=context)
            correction_line_id = aml_obj.copy(cr, uid, ml.id, vals, context=context)
            # Do the reverse
            name = 'REV' + ' ' + ml.name
            amt = -1 * ml.amount_currency
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'corrected_line_id': ml.id,
                'account_id': ml.account_id.id,
            })
            aml_obj.write(cr, uid, [rev_line_id], vals, context=context)
            # Do the correction line
            name = 'COR' + ' ' + ml.name
            aml_obj.write(cr, uid, [correction_line_id], {'name': name, 'journal_id': j_corr_ids[0], 'corrected_line_id': ml.id,
                'account_id': new_account_id,}, context=context)
            # Inform old line that it have been corrected
            aml_obj.write(cr, uid, [ml.id], {'corrected': True}, context=context)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
        return True

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
