# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

import datetime
from dateutil.relativedelta import relativedelta
from osv import fields, osv

class account_period_create(osv.osv_memory):
    _name="account.period.create"

    _columns = {
        'fiscalyear': fields.selection([('current', 'Current FY'), ('next', 'Next FY')], 'Fiscal year', required=True)
    }

    _defaults = {
        'fiscalyear': 'current'
    }


    def account_period_create_periods(self, cr, uid, ids, context=None):
        if context is None:
            context = {}


        if context.get('force_open_year'):
            year = context['force_open_year']
        else:
            data = self.read(cr, uid, ids, [], context=context)[0]
            year = datetime.date.today().year
            if data['fiscalyear'] == 'next':
                year += 1

        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)

        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')

        ds = start_date
        while ds < end_date:
            de = ds + relativedelta(months=1, days=-1)

            if de > end_date:
                de = end_date

            fiscalyear_id = fiscalyear_obj.find(cr, uid, ds, exception=False, context=context)
            if not fiscalyear_id:
                fiscalyear_id = fiscalyear_obj.create(cr,uid, {
                    'name': 'FY %d' % (start_date.year),
                    'code': 'FY%d' % (start_date.year),
                    'date_start': ds,
                    'date_stop': end_date})

            if not period_obj.name_search(cr, uid, ds.strftime('%b %Y'), [('fiscalyear_id', '=', fiscalyear_id)]):
                period_obj.create(cr, uid, {
                    'name': ds.strftime('%b %Y'),
                    'code': ds.strftime('%b %Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fiscalyear_id,
                    'number': int(ds.strftime('%m')),
                })
            ds = ds + relativedelta(months=1)

        fiscalyear_id = fiscalyear_obj.find(cr, uid, start_date, exception=False, context=context)
        for period_nb in (13, 14, 15):
            if not period_obj.name_search(cr, uid, 'Period %d' % (period_nb),
                                          [('fiscalyear_id', '=', fiscalyear_id)], operator='ilike'):
                period_obj.create(cr, uid, {
                    'name': 'Period %d %d' % (period_nb, start_date.year),
                    'code': 'Period %d %d' % (period_nb, start_date.year),
                    'date_start': '%d-12-01' % (start_date.year),
                    'date_stop': '%d-12-31' % (start_date.year),
                    'fiscalyear_id': fiscalyear_id,
                    'special': True,
                    'number': period_nb,
                })
        periods_to_create=[16]
        if fiscalyear_obj.search_exist(cr, uid, [('date_start', '<', start_date)], context=context):
            periods_to_create.insert(0, 0)
        self.pool.get('account.year.end.closing').create_periods(cr, uid, fiscalyear_id, periods_to_create=periods_to_create, context=context)

        return {'type': 'ir.actions.act_window_close'}

account_period_create()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
