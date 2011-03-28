# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
import decimal_precision as dp

class account_move_line_compute_currency(osv.osv):
    _inherit = "account.move.line"
    
    def refresh_rate(self, cr, uid, ids):
        for move_line in self.browse(cr, uid, ids):
            cur_obj = self.pool.get('res.currency')
            account_obj = self.pool.get('account.account')
            account = account_obj.browse(cr, uid, move_line.account_id.id)
            ctx = {}
            if move_line.date:
                ctx['date'] = move_line.date
            if move_line.debit_currency != 0.0 or move_line.credit_currency != 0.0:
                # Booking currency used for debit/credit;
                # they are converted to the functional currency
                debit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                    move_line.functional_currency_id.id, move_line.debit_currency, round=False, context=ctx)
                credit_computed = cur_obj.compute(cr, uid, move_line.currency_id.id,
                    move_line.functional_currency_id.id, move_line.credit_currency, round=False, context=ctx)
                cr.execute('update account_move_line set debit=%s, credit=%s where id=%s', (debit_computed, credit_computed, move_line.id))
    

    def create(self, cr, uid, vals, context={}):
        res_id = super(account_move_line_compute_currency, self).create(cr, uid, vals, context)
        self.refresh_rate(cr, uid, [res_id])
        return res_id
    
    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        res = super(account_move_line_compute_currency, self).write(cr, uid, ids, vals, context, check, update_check)
        self.refresh_rate(cr, uid, ids)
        return res
    
    _columns = {
        'debit_currency': fields.float('Booking Out', digits_compute=dp.get_precision('Account')),
        'credit_currency': fields.float('Booking In', digits_compute=dp.get_precision('Account')),
        'functional_currency_id': fields.related('account_id', 'company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False),
    }
    
    _defaults = {
        'debit_currency': 0.0,
        'credit_currency': 0.0,
    }
    
account_move_line_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
