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
import decimal_precision as dp

class account_move_compute_currency(osv.osv):
    _inherit = "account.move"
    
    def _book_amount_compute(self, cr, uid, ids, name, args, context, where =''):
        """
        On the same model of the function defined in account>account.py,
        we compute the booking amount
        """
        if not ids: return {}
        cr.execute( """SELECT move_id, SUM(debit_currency) 
                    FROM account_move_line 
                    WHERE move_id IN %s 
                    GROUP BY move_id""", (tuple(ids),))
        result = dict(cr.fetchall())
        for id in ids:
            result.setdefault(id, 0.0)
        return result
    
    def _get_currency(self, cr, uid, ids, fields, arg, context=None):
        """
        get booking currency: we look at the currency_id of the first line
        """
        if not context:
            context = {}
        res = {}
        for move in self.pool.get('account.move').browse(cr, uid, ids, context=context):
            res[move.id] = {}
            if move.line_id:
                line = move.line_id[0]
                if line.currency_id:
                    res[move.id] = line.currency_id.id
                else:
                    res[move.id] = False
        return res
    
    _columns = {
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False),
        'currency_id': fields.function(_get_currency, method=True, type="many2one", relation="res.currency", string='Book. Currency', help="The optional other currency if it is a multi-currency entry."),
        'book_amount': fields.function(_book_amount_compute, method=True, string='Book Amount', digits_compute=dp.get_precision('Account'), type='float'),
    }
    
    def validate(self, cr, uid, ids, context=None):
        for move in self.browse(cr, uid, ids, context):
            amount = 0
            amount_currency = 0
            sorted_line_ids = move.line_id
            sorted_line_ids.sort(key=lambda x: abs(x.debit - x.credit), reverse=True)
            for line in sorted_line_ids:
                amount += line.debit - line.credit
                amount_currency += line.amount_currency
            
            if len(sorted_line_ids) >= 2:
                if abs(amount_currency) > 10 ** -4 and abs(amount) < 10 ** -4:
                    # The move is balanced, but there is a difference in the converted amounts;
                    # the second-biggest move line is modified accordingly
                    line_to_be_balanced = sorted_line_ids[1]
                    amount_currency = line_to_be_balanced.amount_currency - amount_currency
                    debit_currency = 0.0
                    credit_currency = 0.0
                    if amount_currency > 0:
                        debit_currency = amount_currency
                    else:
                        credit_currency = -amount_currency
                    # write() is not called to avoid a loop and a refresh of the rates
                    cr.execute('update account_move_line set amount_currency=%s, \
                                                             debit_currency=%s, \
                                                             credit_currency=%s where id=%s',
                              (amount_currency, debit_currency, credit_currency, line_to_be_balanced.id))
                elif abs(amount) > 10 ** -4 and abs(amount_currency) < 10 ** -4:
                    # The move is balanced, but there is a difference in the converted amounts;
                    # the second-biggest move line is modified accordingly
                    line_to_be_balanced = sorted_line_ids[1]
                    amount = line_to_be_balanced.debit - line_to_be_balanced.credit - amount
                    debit = 0.0
                    credit = 0.0
                    if amount > 0:
                        debit = amount
                    else:
                        credit = -amount
                    # write() is not called to avoid a loop and a refresh of the rates
                    cr.execute('update account_move_line set debit=%s, \
                                                             credit=%s where id=%s',
                              (debit, credit, line_to_be_balanced.id))
        return super(account_move_compute_currency, self).validate(cr, uid, ids, context)
        
    
account_move_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
