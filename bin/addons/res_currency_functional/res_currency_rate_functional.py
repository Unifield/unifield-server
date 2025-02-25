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
from tools.translate import _
from base import currency_date


class res_currency_rate_functional(osv.osv):
    _inherit = "res.currency.rate"

    _columns = {
        'rate': fields.float('Rate', digits=(12,6), required=True,
                             help='The rate of the currency to the functional currency'),
    }

    def _get_date_type(self, cr, selected_date):
        """
        Returns the date field used for functional amount computation in this OC (always posting date if < 2020)
        """
        date_type = 'date'
        if selected_date >= currency_date.BEGINNING:
            date_type = currency_date.get_date_type(self, cr) == 'posting' and 'date' or 'document_date'
        return date_type

    def refresh_move_lines(self, cr, uid, ids, date=None, currency=None):
        move_line_obj = self.pool.get('account.move.line')
        if currency is None:
            currency_obj = self.read(cr, uid, ids, ['currency_id'])[0]
            currency = currency_obj['currency_id'][0]
        move_line_search_params = [('currency_id', '=', currency), ('is_revaluated_ok', '=', False)]
        if date is not None:
            date_type = self._get_date_type(cr, date)
            move_line_search_params.append((date_type, '>=', date))

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
        if isinstance(ids, int):
            ids = [ids]
        # Engagement lines object
        eng_obj = self.pool.get('account.analytic.line')
        # Search all engagement journal lines that don't come from a move and which date is superior to the rate
        search_params = [('move_id', '=', '')]
        if currency:
            search_params.append(('currency_id', '=', currency))
        if date:
            date_type = self._get_date_type(cr, date)
            search_params.append('|')
            search_params.append(('source_date', '>=', date))
            search_params.append('&')  # UFTP-361 in case source_date no set
            search_params.append(('source_date', '=', False))
            search_params.append((date_type, '>=', date))
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
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        old_rates = {}
        for rate_id in ids:
            old_rates[rate_id] = {}
            rate = self.read(cr, uid, rate_id, ['rate', 'name'], context=context)
            old_rates[rate_id]['rate'] = rate['rate']
            old_rates[rate_id]['date'] = rate['name']
        res = super(res_currency_rate_functional, self).write(cr, uid, ids, vals, context)
        if 'name' in vals or 'rate' in vals:
            for r_id in ids:
                date_changed = 'name' in vals and vals['name'] != old_rates[r_id]['date']
                # check if the rate has changed (rates in Unifield have an accuracy of 6 digits after the comma)
                rate_changed = 'rate' in vals and abs(vals['rate'] - old_rates[r_id]['rate']) > 10**-7
                if date_changed or rate_changed:
                    date_for_recompute = vals.get('name') or old_rates[r_id]['date']
                    if date_changed:
                        # use the earliest date for the re-computation
                        date_for_recompute = old_rates[r_id]['date'] < vals['name'] and old_rates[r_id]['date'] or vals['name']
                    self.refresh_move_lines(cr, uid, [r_id], date=date_for_recompute)
                    # Also update analytic move lines that don't come from a move (engagement journal lines)
                    rate = self.browse(cr, uid, r_id, fields_to_fetch=['currency_id'], context=context)
                    currency_id = rate.currency_id and rate.currency_id.id or False
                    self.refresh_analytic_lines(cr, uid, [r_id], date=date_for_recompute, currency=currency_id, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        This method is used to re-compute all account move lines when a currency is modified.
        """
        res = True
        period_obj = self.pool.get('account.period')
        if context is None:
            context = {}
        for currency in self.read(cr, uid, ids, ['currency_id', 'name'], context=context):
            period_ids = period_obj.get_period_from_date(cr, uid, currency['name'], context=context)
            if period_ids:
                period = period_obj.read(cr, uid, period_ids[0], ['state', 'name'], context=context)
                if period['state'] != 'created':
                    raise osv.except_osv(_('Error'),
                                         _("You can't delete this FX rate as the period \"%s\" isn't in Draft state.") % period['name'])
            res = res & super(res_currency_rate_functional, self).unlink(cr, uid, ids, context)
            if currency['currency_id']:
                currency_id = currency['currency_id'][0]
                self.refresh_move_lines(cr, uid, ids, currency=currency_id)
        return res

res_currency_rate_functional()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
