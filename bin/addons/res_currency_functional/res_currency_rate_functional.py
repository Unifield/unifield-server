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
        'rate': fields.float('Rate', digits=(12,6), required=True,
            help='The rate of the currency to the functional currency'),
    }

    def refresh_move_lines(self, cr, uid, ids, date=None, currency=None):
        cur_obj = self.pool.get('res.currency')
        account_obj = self.pool.get('account.account')
        move_line_obj = self.pool.get('account.move.line')
        if currency is None:
            currency_obj = self.read(cr, uid, ids, ['currency_id'])[0]
            currency = currency_obj['currency_id'][0]
        move_line_search_params = [('currency_id', '=', currency), ('is_revaluated_ok', '=', False)]
        if date is not None:
            move_line_search_params.append(('date', '>=', date))
        
        move_line_ids = move_line_obj.search(cr, uid, move_line_search_params)
        move_line_obj.update_amounts(cr, uid, move_line_ids)
        move_ids = []
        reconcile = set()
        for ml in move_line_obj.read(cr, uid, move_line_ids, ['move_id', 'reconcile_id']):
            if ml['reconcile_id']:
                reconcile.add(ml['reconcile_id'][0])
            if ml.get('move_id', False):
                move_ids.append(ml.get('move_id')[0])
        if move_ids:
            reconcile.update(self.pool.get('account.move').balance_move(cr, uid, list(set(move_ids))))
        if reconcile:
            move_line_obj.reconciliation_update(cr, uid, list(reconcile))
        return True

    def refresh_analytic_lines(self, cr, uid, ids, date=None, currency=None, context=None):
        """
        Refresh analytic lines that don't come from a move
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Engagement lines object
        eng_obj = self.pool.get('account.analytic.line')
        # Search all engagement journal lines that don't come from a move and which date is superior to the rate
        search_params = [('move_id', '=', '')]
        if currency:
            search_params.append(('currency_id', '=', currency))
        if date:
            search_params.append('|')
            search_params.append(('source_date', '>=', date))
            search_params.append('&')  # UFTP-361 in case source_date no set
            search_params.append(('source_date', '=', False))
            search_params.append(('date', '>=', date))
        eng_ids = eng_obj.search(cr, uid, search_params, context=context)
        if eng_ids:
            eng_obj.update_amounts(cr, uid, eng_ids, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        """
        This method is used to re-compute all account move lines when a currency is modified.
        """
        res_id = super(res_currency_rate_functional, self).create(cr, uid, vals, context)
        self.refresh_move_lines(cr, uid, [res_id], date=vals['name'])
        # Also update analytic move line that don't come from a move (engagement journal lines)
        currency_id = vals.get('currency_id', False)
        self.refresh_analytic_lines(cr, uid, [res_id], date=vals['name'], currency=currency_id, context=context)
        return res_id
    
    def write(self, cr, uid, ids, vals, context=None):
        """
        This method is used to re-compute all account move lines when a currency is modified.
        """
        res = super(res_currency_rate_functional, self).write(cr, uid, ids, vals, context)
        self.refresh_move_lines(cr, uid, ids, date=vals['name'])
        # Also update analytic move line that don't come from a move (engagement journal lines)
        for rate in self.browse(cr, uid, ids, context=context):
            currency_id = rate.currency_id and rate.currency_id.id or False
            self.refresh_analytic_lines(cr, uid, ids, date=vals['name'], currency=currency_id, context=context)
        return res
    
    def unlink(self, cr, uid, ids, context=None):
        """
        This method is used to re-compute all account move lines when a currency is modified.
        """
        res = True
        for currency in self.read(cr, uid, ids, ['currency_id']):
            res = res & super(res_currency_rate_functional, self).unlink(cr, uid, ids, context)
            if currency['currency_id']:
                currency_id = currency['currency_id'][0]
                self.refresh_move_lines(cr, uid, ids, currency=currency_id)
        return res

res_currency_rate_functional()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
