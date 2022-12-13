# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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


import time

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class sale_loan_stock_moves_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_loan_stock_moves_report_parser, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.user_company = self._get_user_company()
        self.localcontext.update({
            'time': time,
            'getMoves': self._get_moves,
            'isQtyOut': self._is_qty_out,
            'getQty': self._get_qty,
            'getUserCompany': self._get_user_company,
            'getFirstSplitOnUnderscore': self._get_first_split_on_underscore,
            'computeCurrency': self._compute_currency,
        })

    def _is_qty_out(self, move):
        '''
        Check if the move is an in or an out
        '''

        if (move.location_id.usage == 'internal') and (move.location_dest_id and move.location_dest_id.usage in ('customer', 'supplier')):
            return True

        return False

    def _get_qty(self, move):
        '''
        Return the move's product quantity
        '''
        uom_obj = self.pool.get('product.uom')

        qty = uom_obj._compute_qty(self.cr, self.uid, move.product_uom.id,
                                   move.product_qty,
                                   move.product_id.uom_id.id)

        return qty

    def _get_moves(self, report):
        '''
        Return the moves for the report and set their qty balance
        '''
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        sm_list = []
        # TODO: we must search on counterpart if filter is used on wizard
        for move in report.sm_ids:
            sm_list.append(self.pool.get('stock.move').browse(self.cr, self.uid, move, context=self.localcontext))

        sm_list = sorted(sm_list, key=lambda sm: sm['create_date'])
        move_by_fo_po_prod = {}
        keys_order = []

        get_so_from_po_id = {}
        get_po_from_so_id = {}

        for move in sm_list:
            if self._is_qty_out(move):
                qty = -1 * self._get_qty(move)
            else:
                qty = self._get_qty(move)

            status = _('Open')
            if move.purchase_line_id:
                pol = move.purchase_line_id
                po_found = pol.order_id
                sol_found = False
                ids = []
                if pol.loan_line_id:
                    sol_found = pol.loan_line_id
                    if po_found.id not in get_so_from_po_id:
                        get_so_from_po_id[po_found.id] = sol_found.order_id
                else:
                    sol_found_ids = sol_obj.search(self.cr, self.uid, [('loan_line_id', '=', pol.id)])
                    if sol_found_ids:
                        sol_found = sol_obj.browse(self.cr, self.uid, sol_found_ids[0], fields_to_fetch=['state', 'order_id'])
                        if po_found.id not in get_so_from_po_id:
                            get_so_from_po_id[po_found.id] = sol_found.order_id
                    elif po_found.id not in get_so_from_po_id:
                        if po_found.loan_id:
                            ids = [po_found.loan_id.id]
                        elif po_found.origin:
                            if po_found.origin[-2:] in ['-1', '-2', '-3']:
                                ids = so_obj.search(self.cr, self.uid, [('name', '=', po_found.origin)])
                                if not ids:
                                    ids = so_obj.search(self.cr, self.uid, [('name', '=', po_found.origin[0:-2])])
                            else:
                                ids = so_obj.search(self.cr, self.uid, [('name', '=', po_found.origin)])
                                if not ids:
                                    dom = ['%s-%s' % (po_found.origin, i) for i in [1, 2, 3]]
                                    ids = so_obj.search(self.cr, self.uid, [('name', 'in', dom)])
                        if po_found.state == 'done' and not ids:
                            ids = so_obj.search(self.cr, self.uid, [('loan_id', '=', po_found.id)])
                        if ids:
                            so = so_obj.browse(self.cr, self.uid, ids[0])
                            if so.split_type_sale_order:
                                ids = so_obj.search(self.cr, self.uid, [('name', '=', '%s-2' % so.name)])
                                if ids:
                                    so = so_obj.browse(self.cr, self.uid, ids[0])
                            get_so_from_po_id[po_found.id] = so
                    if not sol_found and get_so_from_po_id.get(po_found.id, False):
                        pol_domain = [('order_id', '=', get_so_from_po_id[po_found.id].id),
                                      ('line_number', '=', pol.line_number), ('product_id', '=', pol.product_id.id)]
                        sol_found_ids = sol_obj.search(self.cr, self.uid, pol_domain)
                        if sol_found_ids:
                            sol_found = sol_obj.browse(self.cr, self.uid, sol_found_ids[0], fields_to_fetch=['state'])

                # Skip the line if reception and linked FO line are both cancelled or no FO line is found and the
                # PO line is cancelled
                if (sol_found and sol_found.state == pol.state == 'cancel') or \
                        (not sol_found and pol.state == 'cancel'):
                    continue
                so_found = get_so_from_po_id.get(po_found.id)
                if move.state == 'cancel' or pol.state == 'cancel':
                    status = _('Cancelled')
                elif sol_found:
                    if sol_found.state == pol.state == 'done':
                        status = _('Closed')
                    elif sol_found.state == 'cancel':
                        status = _('Cancelled')
                elif so_found:
                    if so_found.state == po_found.state == 'done':
                        status = _('Closed')
                    elif so_found.state == 'cancel':
                        status = _('Cancelled')
            elif move.sale_line_id:
                sol = move.sale_line_id
                so_found = sol.order_id
                pol_found = False
                if sol.loan_line_id:
                    pol_found = sol.loan_line_id
                    if so_found.id not in get_po_from_so_id:
                        get_po_from_so_id[so_found.id] = pol_found.order_id
                else:
                    pol_found_ids = pol_obj.search(self.cr, self.uid, [('loan_line_id', '=', sol.id)])
                    if pol_found_ids:
                        pol_found = pol_obj.browse(self.cr, self.uid, pol_found_ids[0], fields_to_fetch=['state', 'order_id'])
                        get_po_from_so_id[so_found.id] = pol_found.order_id
                    elif not pol_found_ids and so_found.id not in get_po_from_so_id:
                        if so_found.loan_id:
                            ids = [so_found.loan_id.id]
                        elif so_found.name[-2:] in ['-1', '-2', '-3']:
                            ids = po_obj.search(self.cr, self.uid, [('origin', '=', so_found.name)])
                            if not ids:
                                ids = po_obj.search(self.cr, self.uid, [('origin', '=', so_found.name[0:-2])])
                        else:
                            ids = po_obj.search(self.cr, self.uid, [('origin', '=', so_found.name)])
                        if ids:
                            po_found = po_obj.browse(self.cr, self.uid, ids[0])
                            if po_found.state == 'split':
                                ids = po_obj.search(self.cr, self.uid, [('name', '=', '%s-2' % po_found.name)])
                                po_found = po_obj.browse(self.cr, self.uid, ids[0])
                            get_po_from_so_id[so_found.id] = po_found
                    if not pol_found and get_po_from_so_id.get(so_found.id, False):
                        sol_domain = [('order_id', '=', get_po_from_so_id[so_found.id].id),
                                      ('line_number', '=', sol.line_number), ('product_id', '=', sol.product_id.id)]
                        pol_found_ids = sol_obj.search(self.cr, self.uid, sol_domain)
                        if pol_found_ids:
                            pol_found = sol_obj.browse(self.cr, self.uid, pol_found_ids[0], fields_to_fetch=['state'])

                # Skip the line if delivery line and linked PO line are both cancelled or no PO line is found and the
                # FO line is cancelled
                if (pol_found and pol_found.state == sol.state == 'cancel') or \
                        (not pol_found and sol.state == 'cancel'):
                    continue
                po_found = get_po_from_so_id.get(so_found.id)
                if move.state == 'cancel' or sol.state == 'cancel':
                    status = _('Cancelled')
                elif pol_found:
                    if sol.state == pol_found.state == 'done':
                        status = _('Closed')
                    elif pol_found.state == 'cancel':
                        status = _('Cancelled')
                elif po_found:
                    if po_found.state == so_found.state == 'done':
                        status = _('Closed')
                    elif po_found.state == 'cancel':
                        status = _('Cancelled')
            else:
                so_found = False
                po_found = False

            if status != _('Closed') or not report.remove_completed:
                setattr(move, 'status', status)
                setattr(move, 'balance', 0)

                key = (
                    so_found and so_found.id or 'NF%s' % (po_found and po_found.id or '',),
                    po_found and po_found.id or 'NF%s' % (so_found and so_found.id or '',),
                    move.product_id.id
                )
                if key not in move_by_fo_po_prod:
                    keys_order.append(key)
                    move_by_fo_po_prod[key] = {'balance': 0, 'moves': []}
                move_by_fo_po_prod[key]['balance'] += qty
                move_by_fo_po_prod[key]['moves'].append(move)

        result = []
        for key in keys_order:
            move_by_fo_po_prod[key]['moves'][-1].balance = move_by_fo_po_prod[key]['balance']
            result.append(move_by_fo_po_prod[key]['moves'])

        return result

    def _get_user_company(self):
        '''
        Return user's current company
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

    def _get_first_split_on_underscore(self, name):
        '''
        Return the first data from a table with the string split to '_'
        '''
        res = name
        if res:
            res = name.rsplit('_', 1)[0]

        return res

    def _compute_currency(self, move):
        '''
        Compute an amount of a given currency to the instance's currency
        '''
        currency_obj = self.pool.get('res.currency')

        if not move.price_currency_id:
            if move.price_unit is None:
                return round(move.product_id.standard_price, 2)
            if move.type == 'in':
                from_currency_id = move.partner_id.property_product_pricelist_purchase.currency_id.id
            else:
                from_currency_id = move.partner_id.property_product_pricelist.currency_id.id
        else:
            from_currency_id = move.price_currency_id.id

        context = {'currency_date': move.date}
        to_currency_id = self.user_company['currency_id'].id

        if from_currency_id == to_currency_id:
            return round(move.price_unit, 2)

        return round(currency_obj.compute(self.cr, self.uid, from_currency_id, to_currency_id, move.price_unit, round=False, context=context), 2)


class sale_loan_stock_moves_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(sale_loan_stock_moves_report_xls, self).__init__(name, table,
                                                               rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(sale_loan_stock_moves_report_xls, self).create(cr, uid, ids,
                                                                 data, context)
        return (a[0], 'xls')

sale_loan_stock_moves_report_xls(
    'report.sale.loan.stock.moves.report_xls',
    'sale.loan.stock.moves',
    'addons/sale/report/sale_loan_stock_moves_report_xls.mako',
    parser=sale_loan_stock_moves_report_parser,
    header=False)
