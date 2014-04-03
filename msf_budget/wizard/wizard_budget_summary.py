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

class wizard_budget_summary_export(osv.osv_memory):
    _name = "wizard.budget.summary.export"

    _columns = {
        'granularity': fields.selection([
            ('all','By expense and destination'),
            ('expense','By expense'),
            ('view','By parent account')
        ], 'Granularity', select=1, required=True),
    }

    _defaults = {
        'granularity': lambda *a: 'all',
    }

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Launch budget summary generation using given granularity.
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        if 'active_id' in context:
            # add parameters
            data['form'] = {}
            data['form'].update({'granularity': wizard.granularity})
        if not 'context' in data:
            data['context']= {}
        data['context'].update(data['form'])

        return {'type': 'ir.actions.report.xml', 'report_name': 'msf.pdf.budget.summary', 'datas': data, 'context': context}

wizard_budget_summary_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
