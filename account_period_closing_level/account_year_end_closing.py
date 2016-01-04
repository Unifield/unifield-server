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

from osv import osv
from tools.translate import _
import calendar


class account_year_end_closing(osv.osv_memory):
    _name="account.year.end.closing"
    _auto=False

    # valid special period numbers and their month
    _period_month_map = { 0: 1, 16: 12, }


    def create_periods(self, cr, uid, fy_id, periods_to_create=[0, 16, ],
        context=None):
        """
        create closing special periods 0/16 for given FY
        :param fy_id: fy id to create periods in
        """
        period_numbers = [ pn for pn in periods_to_create \
            if pn in self._period_month_map.keys() ]
        fy_rec = self.pool.get('account.fiscalyear').browse(cr, uid, fy_id,
            context=context)
        fy_year = fy_rec.date_start[:4]
        period_year_month = (fy_year, self._period_month_map[pn], )

        for pn in period_numbers:
            code = "Period %d" % (pn, )
            vals = {
                'name': code,
                'code': code,
                'number': pn,
                'special': True,
                'date_start': '%s-%02d-01' % period_year_month,
                'date_stop': '%s-%02d-31' % period_year_month,
                'fiscalyear_id': fy_id,
                'state': 'created',
            }

            self.pool.get('account.period').create(cr, uid, vals,
                context=context)

account_year_end_closing()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
