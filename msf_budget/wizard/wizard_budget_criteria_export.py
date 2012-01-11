# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv, fields
import datetime

class wizard_budget_criteria_export(osv.osv_memory):
    _name = "wizard.budget.criteria.export"

    _columns = {
        'currency_table_id': fields.many2one('res.currency.table', 'Currency table'),
        'period_id': fields.many2one('account.period', 'Year-to-date'),
        'commitment': fields.boolean('Commitments'),
        'breakdown': fields.selection([('month','By month'),
                                       ('year','Total figure')], 'Breakdown', select=1, required=True),
        'granularity': fields.selection([('all','By budget line'),
                                         ('parent','By parent budget line')], 'Granularity', select=1, required=True),
    }
    
    _defaults = {
        'commitment': True,
        'breakdown': 'year',
        'granularity': 'all',
    }
    
    def _get_budget_header(self, cr, uid, budget, wizard, context={}):
        # Dictionary for selection
        breakdown_selection = dict(self._columns['breakdown'].selection)
        granularity_selection = dict(self._columns['granularity'].selection)
        result =  [['Budget name:', budget.name],
                   ['Budget code:', budget.code],
                   ['Fiscal year:', budget.fiscalyear_id.name],
                   ['Cost center:', budget.cost_center_id.name],
                   ['Decision moment:', budget.decision_moment],
                   ['Version:', budget.version],
                   ['Commitments:', wizard.commitment and 'Included' or 'Excluded'],
                   ['Breakdown:', breakdown_selection[wizard.breakdown]],
                   ['Granularity:', granularity_selection[wizard.granularity]]]
        if wizard.currency_table_id:
            result.append(['Currency table:', wizard.currency_table_id.name])
        if wizard.period_id:
            result.append(['Year-to-date:', wizard.period_id.name])
        return result
    
    def _get_budget_lines(self, cr, uid, budget, wizard, context={}):
        result = []
        # Column header
        month_stop = 12
        header = ['Account']
        # check if month detail is needed
        if wizard.breakdown and wizard.breakdown == 'month':
            month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
            if wizard.period_id:
                period = self.pool.get('account.period').browse(cr, uid, wizard.period_id.id, context=context)
                month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
            for month in range(month_stop):
                header.append(month_list[month] + ' (Budget)')
                header.append(month_list[month] + ' (Actual)')
        header += ['Total (Budget)', 'Total (Actual)']
        result.append(header)
        # Update the context for later
        context.update({'commitment': wizard.commitment})
        if wizard.currency_table_id:
            context.update({'currency_table_id': wizard.currency_table_id.id})
        if wizard.period_id:
            context.update({'period_id': wizard.period_id.id})
        # Retrieve lines
        for budget_line in budget.budget_line_ids:
            if budget_line.line_type == 'view' or wizard.granularity == 'all':
                line = [budget_line.account_id.code]
                if wizard.breakdown and wizard.breakdown == 'month':
                    # Calculate amounts for each month
                    for month in range(month_stop):
                        context.update({'for_month': month + 1})
                        amounts = self.pool.get('msf.budget.line')._get_amounts(cr, uid, [budget_line.id], context=context)[budget_line.id]
                        line += [amounts['budget_amount'], amounts['actual_amount']]
                    del context['for_month']
                total_amounts = self.pool.get('msf.budget.line')._get_amounts(cr, uid, [budget_line.id], context=context)[budget_line.id]
                line += [total_amounts['budget_amount'], total_amounts['actual_amount']]
                result.append(line)
        return result

    def button_create_budget(self, cr, uid, ids, context=None):
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        if 'active_id' in context:
            wizard = self.browse(cr, uid, ids[0], context=context)
            budget = self.pool.get('msf.budget').browse(cr, uid, context['active_id'], context=context)
            header_data = self._get_budget_header(cr, uid, budget, wizard, context)
            budget_line_data = self._get_budget_lines(cr, uid, budget, wizard, context)
            data['form'] = header_data + [['']] + budget_line_data

        return {'type': 'ir.actions.report.xml', 'report_name': 'msf.budget.criteria', 'datas': data}
        

wizard_budget_criteria_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: