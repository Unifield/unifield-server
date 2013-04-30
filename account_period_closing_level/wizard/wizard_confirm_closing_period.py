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
from tools.translate import _

class wizard_confirm_closing_period(osv.osv_memory):
    _name = 'wizard.confirm.closing.period'
    _description = 'Closing period confirmation wizard'

    def button_fx_rate(self, cr, uid, ids, context=None):
        """
        Open Currencies in a new tab
        """
        # Some checks
        if not context:
            context = {}
        # Default buttons
        context.update({'search_default_active': 1})
        return {
            'name': 'Curencies',
            'type': 'ir.actions.act_window',
            'res_model': 'res.currency',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('active', 'in', ['t', 'f'])],
        }

    def button_hr(self, cr, uid, ids, context=None):
        """
        Open all HR entries from given period
        """
        if not context:
            context = {}
        if not context.get('period_id', False):
            raise osv.except_osv(_('Error'), _('No period found in context. Please contact a system administrator.'))
        return {
            'name': 'HR entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('journal_id.type', '=', 'hr'), ('period_id', '=', context.get('period_id'))]
        }

    def button_accruals(self, cr, uid, ids, context=None):
        """
        Open all accruals from given period
        """
        if not context:
            context = {}
        if not context.get('period_id', False):
            raise osv.except_osv(_('Error'), _('No period found in context. Please contact a system administrator.'))
        return {
            'name': 'Accruals',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
            'domain': [('journal_id.type', '=', 'accrual'), ('period_id', '=', context.get('period_id'))]
        }

    def button_recurring(self, cr, uid, ids, context=None):
        """
        Open all recurring models
        """
        if not context:
            context = {}
        return {
            'name': 'Reccuring lines',
            'type': 'ir.actions.act_window',
            'res_model': 'account.model',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'context': context,
        }

    def button_open_invoices(self, cr, uid, ids, context=None):
        """
        Open all Supplier invoices in given period
        """
        if not context:
            context = {}
        if not context.get('period_id', False):
            raise osv.except_osv(_('Error'), _('No period found in context. Please contact a system administrator.'))
        period = self.pool.get('account.period').browse(cr, uid, [context.get('period_id')])[0]
        # Update context
        context.update({'type':'in_invoice', 'journal_type': 'purchase'})
        return {
            'name': 'Supplier Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'target': 'current',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'domain': [
                ('state', '=', 'draft'),
                ('type','=','in_invoice'),
                ('register_line_ids', '=', False),
                ('is_inkind_donation', '=', False),
                ('is_debit_note', "=", False),
                ('is_intermission', '=', False)
            ],
            'context': context,
        }

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Confirm that we close the period
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not 'period_id' in context:
            raise osv.except_osv(_('Error'), _('No period selected. Please do a closing period confirmation from a period!'))
        # Prepare some variables
        period_id = context.get('period_id')
        period_obj = self.pool.get('account.period')
        # All is ok ? Let's go closing the period!
        res = period_obj.write(cr, uid, [period_id], {'state':'field-closed'}, context=context)
        # Then close wizard
        if res:
            return { 'type': 'ir.actions.act_window_close', }
        raise osv.except_osv(_('Error'), _('An unknown error has occured on Period closing confirmation wizard. Please contact an administrator to solve this problem.'))

wizard_confirm_closing_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
