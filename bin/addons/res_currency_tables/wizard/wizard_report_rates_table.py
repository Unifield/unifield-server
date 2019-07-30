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
from tools.translate import _


class wizard_report_rates_table(osv.osv_memory):
    _name = "wizard.report.rates.table"

    _columns = {
        'start_period_id': fields.many2one('account.period', 'Start period', required=True, domain=[('special','=',False)]),
        'end_period_id': fields.many2one('account.period', 'End period', required=True, domain=[('special','=',False)]),
        'export_all': fields.boolean('Export all currencies'),
    }

    _defaults = {
        'export_all': lambda *a: False,
    }

    def button_create_report(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['form'] = {}
        if 'active_model' in context \
                and context['active_model'] == 'res.currency.table' \
                and len(data['ids']) > 0:
            # add parameters
            data['form'].update({'currency_table_id': data['ids'][0]})
        else:
            data['form'].update({'currency_table_id': False})
        if wizard and wizard.start_period_id and wizard.end_period_id:
            if wizard.start_period_id.date_start > wizard.end_period_id.date_start:
                raise osv.except_osv(_('Warning'), _('You cannot select a start period starting after the end period!'))
            else:
                data['form'].update({'start_date': wizard.start_period_id.date_start})
                data['form'].update({'end_date': wizard.end_period_id.date_start})
        export_all = wizard and wizard.export_all or False
        data['form'].update({'export_all': export_all})
        return {'type': 'ir.actions.report.xml', 'report_name': 'msf.rates.table', 'datas': data}


wizard_report_rates_table()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
