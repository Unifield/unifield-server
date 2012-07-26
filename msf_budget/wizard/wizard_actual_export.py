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
from tools.translate import _

class wizard_actual_export(osv.osv_memory):
    _name = "wizard.actual.export"

    _columns = {
        'currency_table_id': fields.many2one('res.currency.table', 'Currency table'),
        'cost_center_ids': fields.many2many('account.analytic.account', 'actual_export_cost_centers', 'wizard_id', 'cost_center_id', 'Cost Centers', domain=[('category', '=', 'OC')]),
    }

    def button_create_report(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        if len(wizard.cost_center_ids) == 0:
            raise osv.except_osv(_('No Cost Center'),_("No cost center was selected for the report!"))
        else:
            data['form'].update({'cost_center_ids': [x.id for x in wizard.cost_center_ids]})
        if wizard.currency_table_id:
            data['form'].update({'currency_table_id': wizard.currency_table_id.id})

        return {'type': 'ir.actions.report.xml', 'report_name': 'msf.budget.actual', 'datas': data}
        

wizard_actual_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: