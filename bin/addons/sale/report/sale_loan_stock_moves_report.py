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
#loan
##############################################################################


import time

from datetime import datetime
from datetime import timedelta

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class sale_loan_stock_moves_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_loan_stock_moves_report_parser, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'time': time,
            'getMoves': self._get_moves,
            'isQtyOut': self._is_qty_out,
            'getQty': self._get_qty,
            'getInstance': self._get_instance,
        })

    def _is_qty_out(self, move):
        '''
        Check if the move is an in or an out
        '''
        out = False

        if (move.location_id.usage == 'internal') and (move.location_dest_id and move.location_dest_id.usage in ('customer', 'supplier')):
            out = True

        return out

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
        result = []
        sm_list = []
        for move in report.sm_ids:
            sm_list.append(self.pool.get('stock.move').browse(self.cr, self.uid, move))

        sm_list = sorted(sm_list, key=lambda sm: (sm['product_id']['default_code'], sm['origin'].split(":")[-1], sm['create_date']))
        tmp_list = []
        balance = 0
        for index, move in enumerate(sm_list, start=0):
            move.balance = balance
            if self._is_qty_out(move):
                balance -= self._get_qty(move)
            else:
                balance += self._get_qty(move)

            if move is sm_list[-1]:
                setattr(move, 'balance', balance)
                tmp_list.append(move)
                if balance == 0:
                    if not report.remove_completed:
                        for sm_obj in tmp_list:
                            sm_obj.state = 'Closed'
                            result.append(sm_obj)
                else:
                    for sm_obj in tmp_list:
                        sm_obj.state = 'Open'
                        result.append(sm_obj)
                tmp_list = []
                balance = 0
            else:
                if move.origin.split(":")[-1] not in sm_list[index+1].origin.split(":")[-1] and \
                            sm_list[index + 1].origin.split(":")[-1] not in move.origin.split(":")[-1]:
                    setattr(move, 'balance', balance)
                    tmp_list.append(move)
                    if balance == 0:
                        if not report.remove_completed:
                            for sm_obj in tmp_list:
                                sm_obj.state = 'Closed'
                                result.append(sm_obj)
                    else:
                        for sm_obj in tmp_list:
                            sm_obj.state = 'Open'
                            result.append(sm_obj)
                    tmp_list = []
                    balance = 0
                else:
                    if move.product_id.id != sm_list[index+1].product_id.id:
                        setattr(move, 'balance', balance)
                        tmp_list.append(move)
                        if balance == 0:
                            if not report.remove_completed:
                                for sm_obj in tmp_list:
                                    sm_obj.state = 'Closed'
                                    result.append(sm_obj)
                        else:
                            for sm_obj in tmp_list:
                                sm_obj.state = 'Open'
                                result.append(sm_obj)
                        tmp_list = []
                        balance = 0
                    else:
                        setattr(move, 'balance', 0)
                        tmp_list.append(move)

        return sorted(result, key=lambda sm: (sm['product_id']['default_code'], sm['origin'].split(":")[-1], sm['create_date']))

    def _get_instance(self):
        '''
        Return user's current instance
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.name

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
