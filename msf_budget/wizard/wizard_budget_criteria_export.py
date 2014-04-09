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
import time

class wizard_budget_criteria_export(osv.osv_memory):
    _name = "wizard.budget.criteria.export"

    _columns = {
        'currency_table_id': fields.many2one('res.currency.table', 'Currency table'),
        'period_id': fields.many2one('account.period', 'Year-to-date'),
        'commitment': fields.boolean('Commitments'),
        'breakdown': fields.selection([
            ('month','By month'),
            ('year','Total figure')
        ], 'Breakdown', select=1, required=True),
        'granularity': fields.selection([
            ('all','By expense and destination'),
            ('expense','By expense'),
            ('view','By parent account')
        ], 'Granularity', select=1, required=True),
    }

    _defaults = {
        'commitment': lambda *a: True,
        'breakdown': lambda *a: 'year',
        'granularity': lambda *a: 'all',
        'period_id': lambda *a: False,
    }

    def button_create_budget_2(self, cr, uid, ids, context=None):
        """
        Take all criteria from wizard to the report.
        Pay attention to have these criteria in context to display right lines:
          - period_id
          - currency_table_id
          - granularity
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        if 'active_id' in context:
            # add parameters
            data['form'] = {}
            data['form'].update({'commitment': wizard.commitment})
            data['form'].update({'breakdown': wizard.breakdown})
            data['form'].update({'granularity': wizard.granularity})
            budget_code = self.pool.get('msf.budget').read(cr, uid, context['active_id'], ['code'])
            data['target_filename'] = 'Budget vs. Actual_%s_%s' % (budget_code['code'] or '', time.strftime('%Y%m%d'))
            if wizard.currency_table_id:
                data['form'].update({'currency_table_id': wizard.currency_table_id.id})
            if wizard.period_id:
                data['form'].update({'period_id': wizard.period_id.id})
        if not 'context' in data:
            data['context']= {}
        data['context'].update(data['form'])

        return {'type': 'ir.actions.report.xml', 'report_name': 'budget.criteria.2', 'datas': data}

wizard_budget_criteria_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
