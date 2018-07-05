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

class wizard_financing_currency_export(osv.osv_memory):
    _name = "wizard.financing.currency.export"

    _columns = {
        'out_currency': fields.many2one('res.currency', 'Currency'),
    }

    def _get_reporting_currency(self, cr, uid, context=None):
        if context is None:
            context = {}
        ids = context.get('active_ids', [])
        if ids:
            contract_obj = self.pool.get('financing.contract.contract')
            contract = contract_obj.browse(cr, uid, ids, context=context)[0]

            if contract:
                return contract.reporting_currency.id
        return False

    _defaults = {
        'out_currency': _get_reporting_currency,
    }

    def button_create_budget(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        if wizard.out_currency:
            data['out_currency'] = wizard.out_currency.id

        return {'type': 'ir.actions.report.xml', 'report_name': 'financing.interactive', 'datas': data}


    def button_create_budget_2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        bg_obj = self.pool.get('memory.background.report')
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        if wizard.out_currency:
            data['out_currency'] = wizard.out_currency.id

        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)

        data['target_filename'] = 'Interactive Report_%s_%s' % (instance and instance.code or '', time.strftime('%Y%m%d'))

        # make the report run in background
        report_name = 'financing.interactive.2'
        background_id = bg_obj.create(cr, uid,
                                      {'file_name': data['target_filename'],
                                       'report_name': report_name,
                                       },
                                      context=context)
        context['background_id'] = background_id
        context['background_time'] = 2
        data['context'] = context

        return {'type': 'ir.actions.report.xml', 'report_name': report_name, 'datas': data, 'context': context}

wizard_financing_currency_export()
