#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from time import strftime
from tools.translate import _

class hr_payroll_validation(osv.osv):
    _name = 'hr.payroll.validation'
    _description = 'Payroll entries validation wizard'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Verify that all lines have an analytic distribution
        """
        if not context:
            context = {}
        res = super(hr_payroll_validation, self).fields_view_get(cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False)
        # Verification
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft')])
        for line in self.pool.get('hr.payroll.msf').browse(cr, uid, line_ids):
            if line.account_id and line.account_id.user_type.code == 'expense' and line.analytic_state != 'valid':
                raise osv.except_osv(_('Warning'), _('Some lines have no analytic distribution!'))
        return res

    def button_validate(self, cr, uid, ids, context={}):
        """
        Validate ALL draft payroll entries
        """
        # Some verifications
        if not context:
            context = {}
        # Retrieve some values
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft')])
        if not line_ids:
            raise osv.except_osv(_('Warning'), _('No draft line found!'))
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hr')])
        if not journal_ids:
            raise osv.except_osv(_('Warning'), _('No HR journal found!'))
        journal_id = journal_ids[0]
        current_date = strftime('%Y-%m-%d')
        one_line_data = self.pool.get('hr.payroll.msf').read(cr, uid, line_ids[0], ['period_id'])
        period_id = one_line_data.get('period_id', False) and one_line_data.get('period_id')[0] or False
        if not period_id:
            raise osv.except_osv(_('Error'), _('Unknown period'))
        try:
            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_fp_id = 0
        # Create a move
        move_vals= {
            'journal_id': journal_id,
            'period_id': period_id,
            'date': self.pool.get('account.period').get_date_in_period(cr, uid, current_date, period_id) or False,
            'name': 'Salaries',
        }
        move_id = self.pool.get('account.move').create(cr, uid, move_vals, context=context)
        # Create lines into this move
        for line in self.pool.get('hr.payroll.msf').browse(cr, uid, line_ids):
            # fetch amounts
            amount = line.amount or 0.0
            debit = credit = 0.0
            if amount < 0.0:
                credit = abs(amount)
            else:
                debit = amount
            # create new distribution (only for expense accounts)
            distrib_id = False
            if line.cost_center_id:
                cc_id = line.cost_center_id and line.cost_center_id.id or False
                fp_id = line.funding_pool_id and line.funding_pool_id.id or False
                f1_id = line.free1_id and line.free1_id.id or False
                f2_id = line.free2_id and line.free2_id.id or False
                if not line.funding_pool_id:
                    fp_id = msf_fp_id
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                if distrib_id:
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': line.currency_id and line.currency_id.id or False,
                        'percentage': 100.0,
                        'date': line.date or current_date,
                        'source_date': line.date or current_date,
                    }
                    common_vals.update({'analytic_id': cc_id,})
                    cc_res = self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': fp_id, 'cost_center_id': cc_id,})
                    fp_res = self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    del common_vals['cost_center_id']
                    if f1_id:
                        common_vals.update({'analytic_id': f1_id,})
                        self.pool.get('free.1.distribution.line').create(cr, uid, common_vals)
                    if f2_id:
                        common_vals.update({'analytic_id': f2_id})
                        self.pool.get('free.2.distribution.line').create(cr, uid, common_vals)
            # create move line values
            line_vals = {
                'move_id': move_id,
                'name': line.name,
                'date': line.date,
                'ref': line.ref,
                'partner_id': line.partner_id and line.partner_id.id or False,
                'account_id': line.account_id and line.account_id.id or False,
                'debit': debit,
                'credit': credit,
                'journal_id': journal_id,
                'period_id': line.period_id and line.period_id.id or period_id,
                'currency_id': line.currency_id and line.currency_id.id or False,
                'analytic_distribution_id': distrib_id or False,
            }
            # create move line
            self.pool.get('account.move.line').create(cr, uid, line_vals)
        self.pool.get('account.move').post(cr, uid, [move_id])
        # Update payroll lines status
        self.pool.get('hr.payroll.msf').write(cr, uid, line_ids, {'state': 'valid'})
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hr_payroll_validation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
