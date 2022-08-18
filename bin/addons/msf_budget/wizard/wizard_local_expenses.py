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


class wizard_local_expenses(osv.osv_memory):
    _name = "wizard.local.expenses"

    def _get_cc_id(self, cr, uid, c):
        cc = self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.top_cost_center_id
        if cc.name != 'OC':
            return cc.id
        return None

    _columns = {
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'start_period_id': fields.many2one('account.period', 'Period From'),
        'end_period_id': fields.many2one('account.period', 'Period To'),
        'breakdown': fields.selection([('month','By month'),
                                       ('year','Total figure')], 'Breakdown', select=1, required=True),
        'granularity': fields.selection([('all','By account'),
                                         ('parent','By parent account')], 'Granularity', select=1, required=True),
        'booking_currency_id': fields.many2one('res.currency', 'Booking currency'),
        'output_currency_id': fields.many2one('res.currency', 'Output currency', required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Centre', domain=[('category', '=', 'OC'), ('code', '!=', 'OC')], required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), False, c),
        'commitment': True,
        'breakdown': 'year',
        'granularity': 'parent',
        'output_currency_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'cost_center_id': _get_cc_id,
    }

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        data['form'].update({'breakdown': wizard.breakdown})
        data['form'].update({'granularity': wizard.granularity})
        data['form'].update({'output_currency_id': wizard.output_currency_id.id})
        data['form'].update({'cost_center_id': wizard.cost_center_id.id})
        data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        # Month stop for YTD
        month_start = 1
        month_stop = 12
        if wizard.start_period_id:
            data['form'].update({'start_period_id': wizard.start_period_id.id})
            period = self.pool.get('account.period').browse(cr, uid, wizard.start_period_id.id, context=context)
            month_start = datetime.datetime.strptime(period.date_start, '%Y-%m-%d').month
        if wizard.end_period_id:
            data['form'].update({'end_period_id': wizard.end_period_id.id})
            period = self.pool.get('account.period').browse(cr, uid, wizard.end_period_id.id, context=context)
            month_stop = datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').month
        data['form'].update({'month_start': month_start})
        data['form'].update({'month_stop': month_stop})
        if wizard.booking_currency_id:
            data['form'].update({'booking_currency_id': wizard.booking_currency_id.id})

        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        data['target_filename'] = '%s_%s_%s' % (_('Local Expenses'), instance and instance.code or '', datetime.datetime.now().strftime('%Y%m%d'))

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': 'local.expenses',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'local.expenses',
            'datas': data,
            'context': context,
        }

wizard_local_expenses()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4
