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
from osv import fields
from time import strftime
from tools.translate import _
import re
from lxml import etree as ET
from tools.misc import ustr

class hr_payroll_validation(osv.osv_memory):
    _name = 'hr.payroll.validation'
    _description = 'Payroll entries validation wizard'

    def check(self, cr, uid, context=None):
        # US-672/2 expenses lines account/partner compatible check pass
        if context is None:
            context = {}
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [
            ('state', '=', 'draft'),
            ('account_id.is_analytic_addicted', '=', True)
        ])
        if not line_ids:
            raise osv.except_osv(_('Warning'), _('No draft line found!'))

        warning_msg = ''
        account_obj = self.pool.get('account.account')
        account_partner_not_compat_log = []
        for line in self.pool.get('hr.payroll.msf').read(cr, uid, line_ids, [
            'name', 'ref', 'account_id',
                'partner_id', 'employee_id', ]):
            partner_id = line['partner_id'] and line['partner_id'][0] or False
            employee_id = line['employee_id'] and line['employee_id'][0] or False
            line['account_id'] and account_obj.check_type_for_specific_treatment(cr, uid, [line['account_id'][0]],
                                                                                 partner_id=partner_id, employee_id=employee_id,
                                                                                 context=context)
            if line['account_id'] \
                    and not account_obj.is_allowed_for_thirdparty(cr, uid,
                                                                  line['account_id'][0],
                                                                  employee_id=employee_id,
                                                                  partner_id=partner_id,
                                                                  context=context)[line['account_id'][0]]:
                partner = line['employee_id'] or line['partner_id']
                entry_msg = "%s - %s: %s / %s" % (
                    line['name'] or '', line['ref'] or '',
                    line['account_id'][1] or '',
                    partner and partner[1] or '')
                account_partner_not_compat_log.append(entry_msg)

        if account_partner_not_compat_log:
            account_partner_not_compat_log.insert(0,
                                                  _('Following entries have account/partner not compatible:'))
            warning_msg = "\n".join(account_partner_not_compat_log)
        if warning_msg:
            raise osv.except_osv(_('Warning'), warning_msg)

    def button_validate(self, cr, uid, ids, context=None):
        """
        Validate ALL draft payroll entries
        """
        # Some verifications
        if not context:
            context = {}
        acc_obj = self.pool.get('account.account')
        # Retrieve some values
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft')])
        if not line_ids:
            raise osv.except_osv(_('Warning'), _('No draft line found!'))
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hr'),
                                                                        ('is_current_instance', '=', True)])
        if not journal_ids:
            raise osv.except_osv(_('Warning'), _('No HR journal found!'))
        journal_id = journal_ids[0]
        current_date = strftime('%Y-%m-%d')
        one_line_data = self.pool.get('hr.payroll.msf').read(cr, uid, line_ids[0], ['period_id', 'field'])
        period_id = one_line_data.get('period_id', False) and one_line_data.get('period_id')[0] or False
        field = one_line_data.get('field', False) and one_line_data.get('field') or False
        if not period_id:
            raise osv.except_osv(_('Error'), _('Unknown period!'))
        if not field:
            raise osv.except_osv(_('Error'), _('No field found!'))
        # Search if this period have already been validated
        period_validated_ids = self.pool.get('hr.payroll.import.period').search(cr, uid, [('period_id', '=', period_id), ('field', '=', field)])
        if period_validated_ids:
            period_validated = self.pool.get('hr.payroll.import.period').browse(cr, uid, period_validated_ids[0])
            raise osv.except_osv(_('Error'), _('Payroll entries have already been validated for: %s in this period: "%s"!') % (field, period_validated.period_id.name,))

        # US-672 check counterpart entries account/thirdparty compat
        self.check(cr, uid, context=context)  # check expense lines
        account_partner_not_compat_log = []
        for line in self.pool.get('hr.payroll.msf').read(cr, uid, line_ids, [
                'name', 'ref', 'partner_id', 'account_id', 'amount', 'employee_id', ]):

            account_id = line.get('account_id', False) and line.get('account_id')[0] or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No account found!'))
            account = acc_obj.browse(cr, uid, account_id, context=context)
            if not account.is_analytic_addicted:
                partner_id = line['partner_id'] and line['partner_id'][0] or False
                employee_id = line['employee_id'] and line['employee_id'][0] or False
                acc_obj.check_type_for_specific_treatment(cr, uid, [account_id], partner_id=partner_id,
                                                          employee_id=employee_id, context=context)
                if not acc_obj.is_allowed_for_thirdparty(
                        cr, uid, [account_id],
                        partner_id=partner_id,
                        employee_id=employee_id,
                        context=context)[account_id]:
                    partner_txt = (line['partner_id'] and line['partner_id'][1]) or \
                                  (line['employee_id'] and line['employee_id'][1]) or ''
                    entry_msg = "%s - %s / %0.02f / %s / %s" % (
                        line['name'] or '',  line['ref'] or '',
                        round(line['amount'], 2),
                        line['account_id'][1], partner_txt, )
                    account_partner_not_compat_log.append(entry_msg)
        if account_partner_not_compat_log:
            account_partner_not_compat_log.insert(0,
                                                  _('Following counterpart entries have account/partner not compatible:'))
            raise osv.except_osv(_('Error'),  "\n".join(account_partner_not_compat_log))

        # Fetch default funding pool: MSF Private Fund
        try:
            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_fp_id = 0

        # Create a move (use one of the line to fetch the date)
        a_line_among_all = self.pool.get('hr.payroll.msf').read(cr, uid, line_ids[0], ['date'])
        move_date = a_line_among_all.get('date', False)
        if not move_date:
            raise osv.except_osv(_('Warning'), _('No posting date found for the journal entry. Please contact a developer.'))
        move_vals= {
            'journal_id': journal_id,
            'period_id': period_id,
            'date': self.pool.get('account.period').get_date_in_period(cr, uid, move_date, period_id) or False,
            'ref': 'Salaries' + ' ' + field,
        }
        move_id = self.pool.get('account.move').create(cr, uid, move_vals, context=context)

        # Create lines into this move
        for line in self.pool.get('hr.payroll.msf').read(cr, uid, line_ids, ['amount', 'cost_center_id', 'funding_pool_id', 'free1_id', 
                                                                             'free2_id', 'currency_id', 'date', 'name', 'ref', 'partner_id', 'employee_id', 'account_id', 'period_id',
                                                                             'destination_id']):
            line_vals = {}
            # fetch amounts
            amount = line.get('amount', 0.0)
            debit = credit = 0.0
            if amount < 0.0:
                credit = abs(amount)
            else:
                debit = amount
            # Note @JFB: this is a correction for UF-1356 that have been already done in another UF. This is the good one.
            # fetch account
            account_id = line.get('account_id', False) and line.get('account_id')[0] or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No account found!'))
            account = acc_obj.browse(cr, uid, account_id, fields_to_fetch=['is_analytic_addicted', 'default_destination_id'], context=context)
            # End of Note
            # create new distribution (only for analytic-a-holic accounts)
            distrib_id = False
            # Note @JFB: this is a correction for UF-1356 that have been already done in another UF. This is the good one.
            if account.is_analytic_addicted:
                # End of Note
                cc_id = line.get('cost_center_id', False) and line.get('cost_center_id')[0] or False
                fp_id = line.get('funding_pool_id', False) and line.get('funding_pool_id')[0] or False
                f1_id = line.get('free1_id', False) and line.get('free1_id')[0] or False
                f2_id = line.get('free2_id', False) and line.get('free2_id')[0] or False
                if not line.get('funding_pool_id', False):
                    fp_id = msf_fp_id
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                # Note @JFB: this is a correction for UF-1356 that have been already done in another UF. This is the good one.
                dest_id = line.get('destination_id', False) and line.get('destination_id')[0] or (account.default_destination_id and account.default_destination_id.id) or False
                # End of Note
                if distrib_id:
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': line.get('currency_id', False) and line.get('currency_id')[0] or False,
                        'percentage': 100.0,
                        'date': line.get('date', False) or current_date,
                        'source_date': line.get('date', False) or current_date,
                        # Note @JFB: this is a correction for UF-1356 that have been already done in another UF. This is the good one.
                        'destination_id': dest_id,
                        # End of Note
                    }
                    common_vals.update({'analytic_id': cc_id,})
                    self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': fp_id, 'cost_center_id': cc_id,})
                    self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    del common_vals['cost_center_id']
                    if f1_id:
                        common_vals.update({'analytic_id': f1_id,})
                        self.pool.get('free.1.distribution.line').create(cr, uid, common_vals)
                    if f2_id:
                        common_vals.update({'analytic_id': f2_id})
                        self.pool.get('free.2.distribution.line').create(cr, uid, common_vals)

            # UTP-1042: Specific partner's accounts are not needed.
            # create move line values
            line_vals = {
                'move_id': move_id,
                'name': line.get('name', ''),
                'date': line.get('date', ''),
                'document_date': line.get('date', ''),
                'reference': line.get('ref', ' '), # a backspace is mandatory for salary lines! Do not remove this backspace.
                'partner_id': line.get('partner_id', False) and line.get('partner_id')[0] or False,
                'employee_id': line.get('employee_id', False) and line.get('employee_id')[0] or False,
                # Note @JFB: this is a correction for UF-1356 that have been already done in another UF. This is the good one.
                'account_id': account_id,
                # End of Note
                'debit_currency': debit,
                'credit_currency': credit,
                'journal_id': journal_id,
                'period_id': line.get('period_id', False) and line.get('period_id')[0] or period_id,
                'currency_id': line.get('currency_id', False) and line.get('currency_id')[0] or False,
                'analytic_distribution_id': distrib_id or False,
            }
            # create move line
            self.pool.get('account.move.line').create(cr, uid, line_vals, check=False)
        self.pool.get('account.move').post(cr, uid, [move_id])
        # Update payroll lines status
        self.pool.get('hr.payroll.msf').write(cr, uid, line_ids, {'state': 'valid'})
        # Update Payroll import period table
        self.pool.get('hr.payroll.import.period').create(cr, uid, {'period_id': period_id, 'field': field,})
        # Display a confirmation wizard
        period = self.pool.get('account.period').browse(cr, uid, period_id, fields_to_fetch=['name'], context=context)
        context.update({'message': _('Payroll entries validation is successful for this period: %s and for that field: %s') % (period.name, field,)})
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False

        # This is to redirect to Payroll Tree View
        context.update({'from': 'payroll_import'})

        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'state': 'none'}, context=context)

        return {
            'name': 'Payroll Validation Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

hr_payroll_validation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
