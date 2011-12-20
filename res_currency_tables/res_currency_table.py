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
from osv import fields, osv

class res_currency_table(osv.osv):
    _name = 'res.currency.table'

    _columns = {
        'name': fields.char('Currency table name', size=64, required=True),
        'code': fields.char('Currency table code', size=16, required=True),
        'currency_ids': fields.one2many('res.currency', 'currency_table_id', 'Currencies', domain=[('active', 'in', ['t','f'])]),
    }
    
    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        table_id = super(res_currency_table, self).create(cr, uid, vals, context=context)
        # Duplicate main currency list
        currency_obj = self.pool.get('res.currency')
        main_currency_ids = currency_obj.search(cr, uid, [('currency_table_id', '=', False)], context={'active_test': False})
        for currency in currency_obj.browse(cr, uid, main_currency_ids, context=context):
            currency_vals = {'name': currency.name,
                             'currency_name': currency.currency_name,
                             'symbol': currency.symbol,
                             'accuracy': currency.accuracy,
                             'rounding': currency.rounding,
                             'company_id': currency.company_id.id,
                             'date': currency.date,
                             'base': currency.base,
                             'currency_table_id': table_id,
                             'reference_currency_id': currency.id,
                             'active': False
                            }
            currency_id = currency_obj.create(cr, uid, currency_vals, context=context)
            if currency.name in ['EUR', 'CHF']:
                # EUR and CHF are default ones
                # create default rate
                date_rate = datetime.date(datetime.date.today().year, 1, 1)
                self.pool.get('res.currency.rate').create(cr, uid, {'name': date_rate.strftime('%Y-%m-%d'),
                                                                    'rate': 1,
                                                                    'currency_id': currency_id}, context=context)
                # Activate currency
                currency_obj.write(cr, uid, [currency_id], {'active': True}, context=context)
        return table_id
    
res_currency_table()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
    