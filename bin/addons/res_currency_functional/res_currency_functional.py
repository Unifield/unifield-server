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

import time
from osv import fields, osv
from tools.translate import _
import tools

class res_currency_functional(osv.osv):
    _inherit = 'res.currency'

    def name_get(self, cr, uid, ids, context=None):
        # UF-886: Do not use the symbol provided by OpenERP, currency is only shown as abbr: USD and not USD($))
        return super(osv.osv, self).name_get(cr, uid, ids, context)
    
    def _verify_rate(self, cr, uid, ids, context=None):
        """
        Verify that a currency set to active has a non-zero rate.
        """
        for currency in self.browse(cr, uid, ids, context=context):
            if not currency.rate_ids and currency.active:
                return False
        return True

    # @@@override base>res>res_currency.py>_current_rate
    def _current_date_rate(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        if 'currency_date' in context:
            date = context['currency_date']
        else:
            date = time.strftime('%Y-%m-%d')
        date = date or time.strftime('%Y-%m-%d')
        for id in ids:
            cr.execute("SELECT currency_id, name, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(id, date))
            if cr.rowcount:
                id, curr_date, rate = cr.fetchall()[0]
                res[id] = {'date': curr_date, 'rate': rate}
            else:
                res[id] = {'date': False, 'rate': 0}
        return res


    _columns = {
        'currency_name': fields.char('Currency Name', size=64, required=True, translate=1),
        'rate': fields.function(_current_date_rate, method=True, string='Current Rate', digits=(12,6),
            help='The rate of the currency to the functional currency',  multi='_date_rate'),
        'date': fields.function(_current_date_rate, method=True, string='Validity From', type='date', multi='_date_rate'),
    }
    
    _constraints = [
        (_verify_rate, "No rate is set. Please set one before activating the currency. ", ['active', 'rate_ids']),
    ]
    
    _defaults = {
        'active': lambda *a: 0,
        'accuracy': 4, 
    }

res_currency_functional()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
