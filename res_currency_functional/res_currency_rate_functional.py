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

from osv import fields, osv

class res_currency_rate_functional(osv.osv):
    _inherit = "res.currency.rate"
    
    _columns = {
        'k_currency': fields.selection([(1,'1'),(1000,'1000'),(1000000,'1000000')],'K-currency', required=True),
    }

    _defaults = {
        'k_currency': 1,
    }
    
    def refresh_move_lines(self, cr, uid, ids, date=None, currency=None):
        cur_obj = self.pool.get('res.currency')
        account_obj = self.pool.get('account.account')
        move_line_obj = self.pool.get('account.move.line')
        if currency is None:
            currency_obj = self.read(cr, uid, ids, ['currency_id'])[0]
            currency = currency_obj['currency_id'][0]
        move_line_search_params = [('currency_id', '=', currency)]
        if date is not None:
            move_line_search_params.append(('date', '>=', date))
        
        move_line_ids = move_line_obj.search(cr, uid, move_line_search_params)
        move_line_obj.update_amounts(cr, uid, move_line_ids)
    
    def create(self, cr, uid, vals, context=None):
        # This method is used to re-compute all account move lines
        # when a currency is modified
        res_id = super(res_currency_rate_functional, self).create(cr, uid, vals, context)
        self.refresh_move_lines(cr, uid, [res_id], date=vals['name'])
        return res_id
    
    def write(self, cr, uid, ids, vals, context=None):
        # This method is used to re-compute all account move lines
        # when a currency is modified
        res = super(res_currency_rate_functional, self).write(cr, uid, ids, vals, context)
        self.refresh_move_lines(cr, uid, ids, date=vals['name'])
        return res
    
    def unlink(self, cr, uid, ids, context=None):
        # This method is used to re-compute all account move lines
        # when a currency is modified
        res = True
        for currency in self.read(cr, uid, ids, ['currency_id']):
            currency_id = currency['currency_id'][0]
            res = res & super(res_currency_rate_functional, self).unlink(cr, uid, ids, context)
            self.refresh_move_lines(cr, uid, ids, currency=currency_id)
        return res
    

res_currency_rate_functional()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
