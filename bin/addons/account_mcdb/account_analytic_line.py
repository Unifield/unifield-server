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
from tools.translate import _
from base import currency_date


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def _get_output(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get an amount regarding currency in context (from 'output' and 'output_currency_id' values)
        """
        if context is None:
            context = {}
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return nothing if no 'output_currency_id' in context
        if not context or not context.get('output_currency_id', False):
            for o_id in ids:
                res[o_id] = {'output_currency': False, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        # Retrieve currency
        currency_id = context.get('output_currency_id')
        currency_obj = self.pool.get('res.currency')
        rate = currency_obj.read(cr, uid, currency_id, ['rate'], context=context).get('rate', False)
        # Do calculation
        if not rate:
            for out_id in ids:
                res[out_id] = {'output_currency': currency_id, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            return res
        aal_fields = ['document_date', 'date', 'source_date', 'currency_id', 'amount_currency']
        for aal in self.browse(cr, uid, ids, fields_to_fetch=aal_fields, context=context):
            res[aal.id] = {'output_currency': False, 'output_amount': 0.0, 'output_amount_debit': 0.0, 'output_amount_credit': 0.0}
            # output_amount field
            # Update with date
            curr_date = currency_date.get_date(self, cr, aal.document_date, aal.date, source_date=aal.source_date)
            context.update({'currency_date': curr_date or strftime('%Y-%m-%d')})
            mnt = self.pool.get('res.currency').compute(cr, uid, aal.currency_id.id, currency_id, aal.amount_currency,
                                                        round=True, context=context)
            res[aal.id]['output_amount'] = mnt or 0.0
            if mnt < 0.0:
                res[aal.id]['output_amount_debit'] = 0.0
                res[aal.id]['output_amount_credit'] = abs(mnt) or 0.0
            else:
                res[aal.id]['output_amount_debit'] = abs(mnt) or 0.0
                res[aal.id]['output_amount_credit'] = 0.0
            # or output_currency field
            res[aal.id]['output_currency'] = currency_id
        return res

    def _get_cheque_number(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for self_br in self.browse(cr, uid, ids, context=context):
            res[self_br.id] = self_br.move_id and \
                self_br.move_id.cheque_number or ''
        return res

    def _search_cheque_number(self, cr, uid, ids, name, args, context=None):
        if not len(args):
            return []
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != 'ilike':
            # g/l selector / analytical selector default operator not found
            msg = _("Operator %s not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        if not args[0][2]:
            return []

        m_ids = self.pool.get('account.move.line').search(cr, uid,
                                                          [('cheque_number', 'ilike', args[0][2])], context=context)
        return [('move_id', 'in', m_ids)] if m_ids else [('id', 'in', [])]

    def _get_hq_system_acc(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        mapping_obj = self.pool.get('account.export.mapping')
        for aal in self.browse(cr, uid, ids, fields_to_fetch=['general_account_id'], context=context):
            mapping_id = mapping_obj.search(cr, uid, [('account_id', '=', aal.general_account_id.id)], context=context)
            if not mapping_id:
                return res
            else:
                mapping = mapping_obj.browse(cr, uid, mapping_id[0], fields_to_fetch=['mapping_value'], context=context)
                res[aal.id] = {'hq_system_account': mapping and mapping.mapping_value or False}
        return res


    _columns = {
        'output_amount': fields.function(_get_output, string="Output amount", type='float', method=True, store=False, multi="analytic_output_currency"),
        'output_amount_debit': fields.function(_get_output, string="Output debit", type='float', method=True, store=False, multi="analytic_output_currency"),
        'output_amount_credit': fields.function(_get_output, string="Output credit", type='float', method=True, store=False, multi="analytic_output_currency"),
        'output_currency': fields.function(_get_output, string="Output curr.", type='many2one', relation='res.currency', method=True, store=False,
                                           multi="analytic_output_currency"),
        'cheque_number': fields.function(_get_cheque_number, type='char',
                                         method=True, string='Cheque Number',
                                         fnct_search=_search_cheque_number),  # BKLG-7: move cheque
        'hq_system_account': fields.function(_get_hq_system_acc, type='char', store=True,
                                            method=True, string='HQ System Account', size=16),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Remove output_amount and output_currency field if context doesn't have 'output_currency_id'
        """
        # Some verifications
        view = super(account_analytic_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'tree' and (not context or not context.get('output_currency_id', False)):
            tree = etree.fromstring(view['arch'])
            for element in ['output_currency', 'output_amount']:
                element_fields = tree.xpath('/tree/field[@name="' + element + '"]')
                for field in element_fields:
                    tree.remove(field)
            view['arch'] = etree.tostring(tree)

        if view_type == 'tree' and \
                context.get('selector_display_cheque_number', False):
            # BKLG-7: cheque_number used in analytic selector: display it
            view['fields']['cheque_number'] = {
                'function': '_get_cheque_number',
                'fnct_search': '_search_cheque_number',
                'type': 'char',
                'string': 'Cheque Number',
            }

            tree = etree.fromstring(view['arch'])

            cheque_number_node = etree.Element('field', attrib={
                'name': 'cheque_number',
            })
            # insert it after entry sequence
            es_node = tree.find('.//field[@name="entry_sequence"]')
            tree.insert(es_node.getparent().index(es_node) + 1,
                        cheque_number_node)

            view['arch'] = etree.tostring(tree)
        return view

    def copy(self, cr, uid, id, default=None, context=None):
        """
        """
        if default is None:
            default = {}
        default.update({
            'output_currency': False,
            'output_amount': 0.0,
            'exported': False,
        })
        return super(account_analytic_line, self).copy(cr, uid, id, default, context=context)

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
