#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

class account_fiscalyear(osv.osv):
    _name = "account.fiscalyear"
    _inherit = "account.fiscalyear"

    def create_period(self,cr, uid, ids, context=None, interval=1):
        for fy in self.browse(cr, uid, ids, context=context):
            ds = datetime.datetime.strptime(fy.date_start, '%Y-%m-%d')
            i = 0
            while ds.strftime('%Y-%m-%d')<fy.date_stop:
                i += 1
                de = ds + relativedelta(months=interval, days=-1)

                if de.strftime('%Y-%m-%d')>fy.date_stop:
                    de = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')

                self.pool.get('account.period').create(cr, uid, {
                    'name': ds.strftime('%b %Y'),
                    'code': ds.strftime('%b %Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fy.id,
                    'special': False,
                    'number': i,
                })
                ds = ds + relativedelta(months=interval)
                 
            ds = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')
            for period_nb in (13, 14, 15):   
                self.pool.get('account.period').create(cr, uid, {
                    'name': 'Period %d' % (period_nb),
                    'code': 'Period %d' % (period_nb),
                    'date_start': '%d-12-01' % (ds.year),
                    'date_stop': '%d-12-31' % (ds.year),
                    'fiscalyear_id': fy.id,
                    'special': True,
                    'number': period_nb,
                })
        return True

account_fiscalyear()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
