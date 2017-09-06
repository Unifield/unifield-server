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
            'getFirstSplitOnUnderscore': self._get_first_split_on_underscore,
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

    def _get_move_obj(self, cr, uid, obj_obj, move):
        '''
        Return the move's order type object
        '''
        obj_id = False
        obj = False
        acronym_type = False

        for split_origin in move.origin.split(":"):
            if obj_obj == self.pool.get('sale.order'):
                acronym_type = 'FO'
            elif obj_obj == self.pool.get('purchase.order'):
                acronym_type = 'PO'

            if acronym_type and acronym_type in split_origin:
                obj_name = str(split_origin.split("-")[0])
                obj_id = obj_obj.search(cr, uid, [('name', 'like', obj_name + '-')])
                if not obj_id:
                    obj_id = obj_obj.search(cr, uid, [('name', 'like', obj_name)])

            if obj_id:
                obj = obj_obj.browse(cr, uid, obj_id[0])
                break

        return obj

    def _get_moves(self, report):
        '''
        Return the moves for the report and set their qty balance
        '''
        so_obj = self.pool.get('sale.order')
        po_obj = self.pool.get('purchase.order')
        result = []
        sm_list = []
        for move in report.sm_ids:
            sm_list.append(self.pool.get('stock.move').browse(self.cr, self.uid, move))

        sm_list = sorted(sm_list, key=lambda sm: (sm['product_id']['default_code'], sm['origin'].split(":")[-1], sm['create_date']))
        balance = 0
        # dict used to check if the loan flow is done
        dict_check_done = {}
        for index, move in enumerate(sm_list, start=0):
            move.balance = balance
            if self._is_qty_out(move):
                balance -= self._get_qty(move)
            else:
                balance += self._get_qty(move)

            # check if the flow exists in the dict
            move.status = 'Open'
            move_ref = str(move.origin.split(":")[-1].split("/")[-1].split("-")[0])
            if not dict_check_done.get(move_ref, []):
                if 'FO' in move.origin and 'PO' in move.origin:
                    so_found = self._get_move_obj(self.cr, self.uid, so_obj, move)
                    so_state = so_found.state if so_found else 'none'
                    po_found = self._get_move_obj(self.cr, self.uid, po_obj, move)
                    po_state = po_found.state if po_found else 'none'
                    if so_state == 'done' and po_state == 'done':
                        dict_check_done[move_ref] = 'Closed'
                    else:
                        dict_check_done[move_ref] = 'Open'
                elif 'FO' in move.origin and 'PO' not in move.origin:
                    so_found = self._get_move_obj(self.cr, self.uid, so_obj, move)
                    so_state = so_found.state if so_found else 'none'
                    po_ids = po_obj.search(self.cr, self.uid, [('origin', '=', so_found.name)])
                    if len(po_ids) > 0:
                        po_found = po_obj.browse(self.cr, self.uid, po_ids[0])
                        po_state = po_found.state if po_found else 'none'
                        if so_state == 'done' and po_state == 'done':
                            dict_check_done[move_ref] = 'Closed'
                        else:
                            dict_check_done[move_ref] = 'Open'
                    else:
                        dict_check_done[move_ref] = 'Open'
                elif 'FO' not in move.origin and 'PO' in move.origin:
                    po_found = self._get_move_obj(self.cr, self.uid, po_obj, move)
                    po_state = po_found.state if po_found else 'none'
                    so_ids = so_obj.search(self.cr, self.uid, [('name', '=', po_found.origin)])
                    if len(so_ids) > 0:
                        so_found = po_obj.browse(self.cr, self.uid, so_ids[0])
                        so_state = so_found.state if so_found else 'none'
                        if so_state == 'done' and po_state == 'done':
                            dict_check_done[move_ref] = 'Closed'
                        else:
                            dict_check_done[move_ref] = 'Open'
                    else:
                        dict_check_done[move_ref] = 'Open'
            # set the state according to the flow status
            setattr(move, 'status', dict_check_done[move_ref])

            # if the move is the last in the list
            if move is sm_list[-1]:
                setattr(move, 'balance', balance)
                # remove closed flows
                if report.remove_completed:
                    if move.status == 'Open':
                        result.append(move)
                else:
                    result.append(move)
                balance = 0
            else:
                # if the move's origin is different than the next one
                if move.origin.split(":")[-1] not in sm_list[index+1].origin.split(":")[-1] and \
                        sm_list[index + 1].origin.split(":")[-1] not in move.origin.split(":")[-1]:
                    setattr(move, 'balance', balance)
                    # remove closed flows
                    if report.remove_completed:
                        if move.status == 'Open':
                            result.append(move)
                    else:
                        result.append(move)
                    balance = 0
                else:
                    # if the move's product is different than the next one
                    if move.product_id.id != sm_list[index+1].product_id.id:
                        setattr(move, 'balance', balance)
                        # remove closed flows
                        if report.remove_completed:
                            if move.status == 'Open':
                                result.append(move)
                        else:
                            result.append(move)
                        balance = 0
                    else:
                        setattr(move, 'balance', 0)
                        # remove closed flows
                        if report.remove_completed:
                            if move.status == 'Open':
                                result.append(move)
                        else:
                            result.append(move)

        return result

    def _get_instance(self):
        '''
        Return user's current instance
        '''
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.name

    def _get_first_split_on_underscore(self, name):
        '''
        Return the first data from a table with the string split to '_'
        '''
        res = name
        if res:
            res = name.split('_')[0]

        return res

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
