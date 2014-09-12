# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 MSF, TeMPO consulting
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
from osv import osv
from osv import fields

class monthly_budget_wizard(osv.osv_memory):
    _name = "monthly.budget.wizard"

    _columns = {
        'granularity': fields.selection([
            ('view','By parent account'),
            ('expense','By expense'),
            ('all','By expense and destination'),
        ], 'Granularity', select=1, required=True),
        'extension': fields.selection([('xls', 'XLS'), ('pdf', 'PDF')], 'Format', select=1, required=True),
    }

    _defaults = {
        'granularity': lambda *a: 'view',
        'format': lambda *a: 'xls',
    }

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Launch monthly budget generation using given granularity and given format.
        """
        report_name = 'msf.pdf.budget.monthly'
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.extension == 'xls':
            report_name = 'xls.budget.monthly'
        data = {}
        data['ids'] = context.get('active_ids', [])
        if 'active_id' in context:
            # add parameters
            data['form'] = {}
            data['form'].update({'granularity': wizard.granularity})
        if not 'context' in data:
            data['context']= {}
        data['context'].update(data['form'])

        return {'type': 'ir.actions.report.xml', 'report_name': report_name, 'datas': data, 'context': context}

monthly_budget_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
