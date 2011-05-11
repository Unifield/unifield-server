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

class res_currency_functional(osv.osv):
    _inherit = 'res.currency'
    
    def _current_k_currency(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        if 'date' in context:
            date = context['date']
        else:
            date = time.strftime('%Y-%m-%d')
        date = date or time.strftime('%Y-%m-%d')
        for id in ids:
            cr.execute("SELECT id, k_currency FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(id, date))
            if cr.rowcount:
                kid, k_currency = cr.fetchall()[0]
                res[id] = k_currency
            else:
                res[id] = 1
        return res
    
    _columns = {
        'currency_name': fields.char('Currency Name', size=64, required=True),
        'current_k_currency': fields.function(_current_k_currency, method=True, string='Current K-Currency')
    }

    _defaults = {
        'accuracy': 4, 
    }
    
    def _get_conversion_rate(self, cr, uid, from_currency, to_currency, context=None):
        conversion_rate = super(res_currency_functional, self)._get_conversion_rate(cr, uid, from_currency, to_currency, context)
        # we add the k-currency
        conversion_rate /= from_currency.current_k_currency 
        conversion_rate *= to_currency.current_k_currency
        return conversion_rate
    
res_currency_functional()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
