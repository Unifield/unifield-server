#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from osv import fields
from time import strftime
from lxml import etree

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def _get_output(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get an amount regarding currency in context (from 'output' and 'output_currency_id' values).
        NB: Pay attention to 'currency_table_id' field in context. It compute amounts regarding another rates.
        """
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Return nothing if no 'output_currency_id' in context
        if not context or not context.get('output_currency_id', False):
            for id in ids:
                res[id] = {'output_currency': False, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        # Retrieve currency
        currency_id = context.get('output_currency_id')
        currency_obj = self.pool.get('res.currency')
        rate = currency_obj.read(cr, uid, currency_id, ['rate'], context=context).get('rate', False)
        # Do calculation
        if not rate:
            for id in ids:
                res[id] = {'output_currency': currency_id, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = {'output_currency': False, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            # output_amount field
            # Update with date
            context.update({'date': ml.source_date or ml.date or strftime('%Y-%m-%d')})
            if ml.is_addendum_line:
                # UTP-896: addendum line expressed in functional currency, output ccy based on functional ccy vs booking ccy (balance vs amount_currency)
                # with ADDENDUM we dont use 'balance' field but debit - credit as balance as fix
                if currency_id != ml.currency_id.id:
                    # ouput ccy <> booking ccy
                    balance = ml.debit - ml.credit
                    mnt = self.pool.get('res.currency').compute(cr, uid, ml.functional_currency_id.id, currency_id, balance, round=True, context=context)
                else:
                    mnt = 0  # balance of addendum line with same ccy = 0
            else:
                mnt = self.pool.get('res.currency').compute(cr, uid, ml.currency_id.id, currency_id, ml.amount_currency, round=True, context=context)
            res[ml.id]['output_amount'] = mnt or 0.0
            if mnt < 0.0:
                res[ml.id]['output_amount_debit'] = 0.0
                res[ml.id]['output_amount_credit'] = abs(mnt) or 0.0
            else:
                res[ml.id]['output_amount_debit'] = abs(mnt) or 0.0
                res[ml.id]['output_amount_credit'] = 0.0
            # or output_currency field
            res[ml.id]['output_currency'] = currency_id
        return res

    _columns = {
        'output_amount': fields.function(_get_output, string="Output amount", type='float', method=True, store=False, multi="output_currency"),
        'output_amount_debit': fields.function(_get_output, string="Output debit", type='float', method=True, store=False, multi="output_currency"),
        'output_amount_credit': fields.function(_get_output, string="Output credit", type='float', method=True, store=False, multi="output_currency"),
        'output_currency': fields.function(_get_output, string="Output curr.", type='many2one', relation='res.currency', method=True, store=False, 
            multi="output_currency"),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Remove output_amount and output_currency field if context doesn't have 'output_currency_id'
        """
        # Some verifications
        if context is None:
            context = {}
        view = super(account_move_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'tree' and (not context or not context.get('output_currency_id', False)):
            tree = etree.fromstring(view['arch'])
            for element in ['output_currency', 'output_amount_debit', 'output_amount_credit']:
                element_fields = tree.xpath('/tree/field[@name="' + element + '"]')
                for field in element_fields:
                    tree.remove(field)
            view['arch'] = etree.tostring(tree)
        return view

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
