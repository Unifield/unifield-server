# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
from osv import fields, osv
import locale
from tools.translate import _

class wizard_expense_report(osv.osv_memory):
    
    _name = "wizard.expense.report"
    _inherit = "wizard.csv.report"
        
    def _get_expenses_data(self, cr, uid, contract_id, reporting_type, context=None):
        res = {}
        contract_obj = self.pool.get('financing.contract.contract')
        # Context updated with wizard's value
        context.update({'reporting_type': reporting_type})
        
        contract = contract_obj.browse(cr, uid, contract_id, context=context)
        
        # check for the contract type; if it's not supposed to be displayed, return an error
        if contract.reporting_type != 'all' and contract.reporting_type != reporting_type:
            raise osv.except_osv(_('Warning !'), _("This report does not apply to the reporting type selected."))
        
        header_data = self._get_contract_header(cr, uid, contract, context=context)
        footer_data = self._get_contract_footer(cr, uid, contract, context=context)
        
        # Report lines with analytic lines for each one
        analytic_data = [['Date',
                          'Analytic Journal',
                          'Reference',
                          'Description',
                          'General Account',
                          'Destination',
                          'Cost Center',
                          'Funding Pool',
                          'Booking Amount',
                          'Booking Currency',
                          'Reporting Amount',
                          'Reporting Currency',
                          'Invoice Line']]
        contract_domain = contract_obj.get_contract_domain(cr,
                                                           uid,
                                                           contract,
                                                           reporting_type=reporting_type,
                                                           context=context)
        # get lines
        analytic_line_obj = self.pool.get('account.analytic.line')
        analytic_lines = analytic_line_obj.search(cr, uid, contract_domain ,context=context)
        amount_sum = 0.0
        amount_currency_sum = 0.0
        currency_table = None
        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
            date_context = {'currency_date': analytic_line.document_date,
                            'currency_table_id': contract.currency_table_id and contract.currency_table_id.id or None}
            amount = self.pool.get('res.currency').compute(cr,
                                                           uid,
                                                           analytic_line.currency_id.id,
                                                           contract.reporting_currency.id, 
                                                           analytic_line.amount_currency or 0.0,
                                                           round=True,
                                                           context=date_context)
            amount_currency = analytic_line.amount_currency
            amount_sum += amount
            amount_currency_sum += amount_currency
            
            # Localized to add comma separators for thousands
            formatted_amount = locale.format("%.2f", amount, grouping=True)
            formatted_amount_currency = locale.format("%.2f", amount_currency, grouping=True)
            
            analytic_data.append([analytic_line.date,
                                  analytic_line.journal_id.name,
                                  analytic_line.ref or '',
                                  analytic_line.name,
                                  analytic_line.general_account_id.code + ' ' + analytic_line.general_account_id.name,
                                  analytic_line.destination_id and analytic_line.destination_id.name,
                                  analytic_line.cost_center_id.name,
                                  analytic_line.account_id.name,
                                  formatted_amount,
                                  contract.reporting_currency.name,
                                  formatted_amount_currency,
                                  analytic_line.currency_id.name,
                                  analytic_line.move_id and analytic_line.move_id.invoice_line_id and analytic_line.move_id.invoice_line_id.name or ''])
            
        # Localized to add comma separators for thousands
        formatted_amount_sum = locale.format("%.2f", amount_sum, grouping=True)
        formatted_amount_currency_sum = locale.format("%.2f", amount_currency_sum, grouping=True)
        
        analytic_data.append(['','','','','','','','',formatted_amount_sum,'', formatted_amount_currency_sum])
        
        data = header_data + [[]] + analytic_data + [[]] + footer_data
        
        return data
    
wizard_expense_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
