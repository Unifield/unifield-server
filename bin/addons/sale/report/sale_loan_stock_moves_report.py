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

    def _get_move_obj(self, cr, uid, obj_obj, move):
        '''
        Return the move's order type object
        '''
        obj = False
        acronym_type = False

        for split_origin in move.origin.split(":"):
            if obj_obj == self.pool.get('sale.order'):
                acronym_type = 'FO'
            elif obj_obj == self.pool.get('purchase.order'):
                acronym_type = 'PO'

            if acronym_type and acronym_type in split_origin:
                obj_name = str(split_origin)
                if '-' in obj_name.split('/')[-1]:
                    obj_name = obj_name.rsplit('-', 1)[0]
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
# TODO: we must search on counterpart if filter is used on wizard
        for move in report.sm_ids:
            sm_list.append(self.pool.get('stock.move').browse(self.cr, self.uid, move))

        sm_list = sorted(sm_list, key=lambda sm: (sm['product_id']['default_code'], sm['origin'].split(":")[-1], sm['create_date']))
        move_by_fo_po_prod = {}
        keys_order = []
        for index, move in enumerate(sm_list, start=0):
            if self._is_qty_out(move):
                qty = -1 * self._get_qty(move)
            else:
                qty = self._get_qty(move)

            dom = []
            status = 'Open'
            if move.purchase_line_id:
                if move.purchase_line_id.order_id.loan_id:
                    ids = [move.purchase_line_id.order_id.loan_id.id]
                elif move.purchase_line_id.order_id.origin[-2:] in ['-1', '-2', '-3']:
                    ids = so_obj.search(self.cr, self.uid, [('name', '=', move.purchase_line_id.order_id.origin)])
                    if not ids:
                        ids = so_obj.search(self.cr, self.uid, [('name', '=', move.purchase_line_id.order_id.origin[-2:])])
                else:
                    dom = [move.purchase_line_id.order_id.origin]
                    ids = so_obj.search(self.cr, self.uid, [('name', '=', move.purchase_line_id.origin)])
                    if not ids:
                        dom = ['%s-%s' % (move.purchase_line_id.order_id.origin, i) for i in [1, 2, 3]]
                        ids = so_obj.search(self.cr, self.uid, [('name', 'in', dom)])
                if ids:
                    po_found = po_obj.browse(self.cr, self.uid, move.purchase_line_id.order_id.id)
                    so_found = so_obj.browse(self.cr, self.uid, ids[0])
#TODO: PO/FO split
                    if so_found and so_found.state == po_found.state == 'done':
                        status = 'Closed'
            elif move.sale_line_id:
                if move.sale_line_id.order_id.loan_id:
                    ids = [move.sale_line_id.order_id.loan_id.id]
                elif move.sale_line_id.order_id.name[-2:] in ['-1', '-2', '-3']:
                    ids = po_obj.search(self.cr, self.uid, [('origin', '=', move.sale_line_id.order_id.name)])
                    if not ids:
                        ids = po_obj.search(self.cr, self.uid, [('origin', '=', move.sale_line_id.order_id.name[0:-2])])
                else:
                    ids = po_obj.search(self.cr, self.uid, [('origin', '=', move.sale_line_id.order_id.name)])
                if ids:
                    so_found = so_obj.browse(self.cr, self.uid, move.sale_line_id.order_id.id)
                    po_found = po_obj.browse(self.cr, self.uid, ids[0])
#TODO: PO/FO split
                    if po_found and so_found.state == po_found.state == 'done':
                        status = 'Closed'

            if status != 'Closed' or not report.remove_completed:
                setattr(move, 'status', status)
                setattr(move, 'balance', 0)
#TODO: if not found
                key = (so_found.id, po_found.id, move.product_id.id)
                if key not in move_by_fo_po_prod:
                    keys_order.append(key)
                    move_by_fo_po_prod[key] =  {'balance': 0, 'moves': []}
                move_by_fo_po_prod[key]['balance'] += qty
                move_by_fo_po_prod[key]['moves'].append(move)


        for key in keys_order:
            result += move_by_fo_po_prod[key]['moves']
            result[-1].balance = move_by_fo_po_prod[key]['balance']


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
            res = name.rsplit('_', 1)[0]

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
