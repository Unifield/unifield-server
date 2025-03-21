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
from tools.translate import _


class account_move_compute_currency(osv.osv):
    _inherit = "account.move"

    def _book_amount_compute(self, cr, uid, ids, name, args, context=None):
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

    def _search_currency(self, cr, uid, obj, name, args, context=None):
        """
        Search move in which lines have the given currency
        """
        # Prepare some elements
        newargs = []
        if not context:
            context = {}
        if not args:
            return newargs
        sql_base = """
        SELECT ml.id FROM account_move ml, account_move_line aml
        WHERE aml.move_id = ml.id
        AND aml.currency_id"""
        for arg in args:
            if args[0] and args[0][1] and args[0][1] in ['in', '='] and args[0][2]:
                # create SQL request
                sql = sql_base + ' in %s\nGROUP BY ml.id'  # not_a_user_entry
                second = args[0][2]
                # execute it and fetch result
                if isinstance(second, int):
                    second = [second]
                cr.execute(sql, (tuple(second),))
                res = cr.fetchall()
                newargs.append(('id', 'in', [x and x[0] for x in res]))
            else:
                raise osv.except_osv(_('Error'), _('Operator not supported.'))
        return newargs

    def onchange_journal_id(self, cr, uid, ids, journal_id=False, context=None):
        """
        Change currency_id regarding journal.
        If journal have a currency, set manual_currency_id to the journal's currency and change field to readonly.
        If journal doesn't have any currency: No changes on currency.

        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = super(account_move_compute_currency, self).onchange_journal_id(cr, uid, ids, journal_id, context)
        if 'value' not in res:
            res['value'] = {}
        if not journal_id:
            res['value'].update({'block_manual_currency_id': False,})
            return res
        j = self.pool.get('account.journal').read(cr, uid, journal_id, ['currency'])
        if j and j.get('currency', False):
            res['value'].update({'manual_currency_id': j.get('currency'), 'block_manual_currency_id': True,})
        else:
            res['value'].update({'block_manual_currency_id': False,})
        return res

    _columns = {
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Functional Currency", store=False, write_relate=False),
        'currency_id': fields.function(_get_currency, method=True, type="many2one", relation="res.currency", string='Book. Currency', help="The optional other currency if it is a multi-currency entry."),
        'manual_currency_id': fields.many2one('res.currency', "Book. Currency",
                                              hide_default_menu=True),
        'book_amount': fields.function(_book_amount_compute, method=True, string='Book Amount', digits_compute=dp.get_precision('Account'), type='float'),
        'block_manual_currency_id': fields.boolean("Block manual currency field", help="Block manual currency field if journal have a currency."),
    }

    _defaults = {
        'manual_currency_id': lambda *a: False,
        'block_manual_currency_id': lambda *a: False,
    }

    def _sub_sort_by_xmlid(self, cr, uid, sorted_line_ids):
        aml_obj = self.pool.get('account.move.line')
        if sorted_line_ids[1].debit == sorted_line_ids[2].debit and sorted_line_ids[1].credit == sorted_line_ids[2].credit:
            # if the 2nd-biggest amount is the same on several lines sort the lines by xmlid
            # so on each instance the rounding is done on the same line
            debit = sorted_line_ids[1].debit
            credit = sorted_line_ids[1].credit
            to_sort = {sorted_line_ids[1].id: sorted_line_ids[1]}

            for line in sorted_line_ids[2:]:
                if line.debit == debit and line.credit == credit:
                    to_sort[line.id] = line
                else:
                    break

            max_sdref = ''
            max_id = 0

            for id, sdref in list(aml_obj.get_sd_ref(cr, uid, list(to_sort.keys())).items()):
                if sdref > max_sdref:
                    max_id = id
                    max_sdref = sdref
            return to_sort[max_id]

        return sorted_line_ids[1]

    def balance_move(self, cr, uid, ids, context=None):
        """
        Balance move
        """
        if not context:
            context = {}
        reconcile = {}
        for move in self.browse(cr, uid, ids, context):
            amount = 0
            amount_currency = 0
            sorted_line_ids = move.line_id
            sorted_line_ids.sort(key=lambda x: abs(x.debit - x.credit), reverse=True)
            all_line_zero_func = True
            for line in sorted_line_ids:
                amount += line.debit - line.credit
                if all_line_zero_func:
                    # because of high fx rate, funct. amount could be 0 on all lines, we must not consider this case as func balanced
                    all_line_zero_func = abs(line.debit - line.credit) < 10**-4
                amount_currency += line.amount_currency

            if move.period_id and not move.period_id.is_system \
                    and len(sorted_line_ids) > 2:
                if abs(amount) > 10 ** -4 and abs(amount_currency) < 10 ** -4:
                    # The move is book. balanced, but there is a difference in the converted amounts;
                    # the second-biggest move line is modified accordingly
                    line_to_be_balanced = self._sub_sort_by_xmlid(cr, uid, sorted_line_ids)
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
                    if line_to_be_balanced.reconcile_id:
                        reconcile[line_to_be_balanced.reconcile_id.id] = 1
        return list(reconcile.keys())

    def validate(self, cr, uid, ids, context=None):
        """
        Balance move before its validation
        """
        self.balance_move(cr, uid, ids, context=context)
        return super(account_move_compute_currency, self).validate(cr, uid, ids, context)

    def create(self, cr, uid, vals, context=None):
        """
        Add currency if none for manual entry
        """
        if not context:
            context = {}
        if not 'manual_currency_id' in vals or not vals.get('manual_currency_id'):
            if 'journal_id' in vals:
                j = self.pool.get('account.journal').read(cr, uid, vals.get('journal_id'), ['currency'])
                if j and j.get('currency', False):
                    vals.update({'manual_currency_id': j.get('currency')[0]})
        return super(account_move_compute_currency, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Change manual currency regarding journal
        """
        if not ids:
            return True
        if not context:
            context = {}
        res = []
        for m in self.read(cr, uid, ids, ['journal_id', 'status', 'line_id']):
            j_id = m.get('journal_id', False) and m.get('journal_id')[0] or False
            if 'journal_id' in vals:
                j_id = vals.get('journal_id')
            journal = self.pool.get('account.journal').read(cr, uid, j_id, ['currency'])
            if journal and journal.get('currency', False):
                vals.update({'manual_currency_id': journal.get('currency')[0], 'block_manual_currency_id': True,})
            tmp_res = super(account_move_compute_currency, self).write(cr, uid, [m.get('id')], vals, context)
            res.append(tmp_res)
        return res

account_move_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
