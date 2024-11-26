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
from base import currency_date


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    # UTP-936: Extract the method to calculate the output here, so that it can be used at other places, for example:
    # account_mcdb/report/account_mcdb_export.py, which is used to generate csv reports
    def calculate_output(self, cr, uid, currency_id, ml, round, context):
        currency_obj = self.pool.get('res.currency')
        func_amount = ml.amount_currency
        original_currency = ml.currency_id.id
        if ml.journal_id.type in ['cur_adj','revaluation']:
            # UF-2296: in case of Current Adjustmeent Journal (MT)
            # if output ccy == fonctional ccy we must return functional amount
            # explanation: export search result account_mcdb/report/account_mcdb_export.py
            # uses 'output_currency_id' for amount computing even if no output ccy
            return_func_amount = False
            if currency_id == ml.functional_currency_id.id:
                return_func_amount = True
            #UTP-936: In case of MT journal, the conversion is from functional currency to output currency
            if ml.debit:
                func_amount = ml.debit
            elif ml.credit:
                func_amount = -ml.credit
            if return_func_amount:  # UF-2296
                return func_amount
            original_currency = ml.functional_currency_id.id
        # Perform the conversion from original currency to selected currency
        return currency_obj.compute(cr, uid, original_currency, currency_id, func_amount, round=round, context=context)

    def _get_output(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get an amount regarding currency in context (from 'output' and 'output_currency_id' values).
        NB: Pay attention to 'currency_table_id' field in context. It compute amounts regarding another rates.
        """
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        # Return nothing if no 'output_currency_id' in context
        if not context or not context.get('output_currency_id', False):
            for o_id in ids:
                res[o_id] = {'output_currency': False, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        # Retrieve currency
        company_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency_id = context.get('output_currency_id')
        currency_obj = self.pool.get('res.currency')
        rate = currency_obj.read(cr, uid, currency_id, ['rate'], context=context).get('rate', False)
        # Do calculation
        if not rate:
            for out_id in ids:
                res[out_id] = {'output_currency': currency_id, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = {'output_currency': currency_id, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            # output_amount field
            # Update with date
            if context.get('currency_table_id'):
                context['currency_date'] =  strftime('%Y-%m-%d')
            else:
                curr_date = currency_date.get_date(self, cr, ml.document_date, ml.date, source_date=ml.source_date)
                context.update({'currency_date': curr_date or strftime('%Y-%m-%d')})
            # Now call the common method to calculate the output values
            if currency_id == company_currency_id and not context.get('currency_table_id', False):
                res[ml.id].update({'output_amount': ml.debit - ml.credit, 'output_amount_debit': ml.debit, 'output_amount_credit': ml.credit})
            else:
                amount = self.calculate_output(cr, uid, currency_id, ml, round=True, context=context)
                res[ml.id]['output_amount'] = amount or 0.0
                if amount < 0.0:
                    res[ml.id]['output_amount_debit'] = 0.0
                    res[ml.id]['output_amount_credit'] = abs(amount) or 0.0
                else:
                    res[ml.id]['output_amount_debit'] = abs(amount) or 0.0
                    res[ml.id]['output_amount_credit'] = 0.0
                    # or output_currency field
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
            view['arch'] = etree.tostring(tree, encoding='unicode')

        if view_type == 'tree' and \
                context.get('selector_display_cheque_number', False):
            # BKLG-7: cheque_number used in G/L selector: display it
            view['fields']['cheque_number'] = {
                'type': 'char',
                'string': 'Cheque Number',
            }

            tree = etree.fromstring(view['arch'])

            cheque_number_node = etree.Element('field', attrib={
                'name': 'cheque_number',
            })
            # insert it after entry sequence
            es_node = tree.find('.//field[@name="move_id"]')
            tree.insert(es_node.getparent().index(es_node) + 1,
                        cheque_number_node)

            view['arch'] = etree.tostring(tree, encoding='unicode')
        if view_type == 'search':
            # filter on Cheque Number must appear only when searching for the lines to add in the Import Cheque wizard
            if context.get('from') != 'wizard_import_cheque':
                tree = etree.fromstring(view['arch'])
                element_fields = tree.xpath('.//field[@name="cheque_number"]')
                for el in element_fields:
                    el.getparent().remove(el)
                view['arch'] = etree.tostring(tree, encoding='unicode')
        self.pool.get('account.export.mapping').update_view_with_mapping_field(cr, uid, view_type, view, context=context)
        return view

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
