# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
from mx import DateTime

class import_cell_data(osv.osv_memory):
    '''
    Compute field from xml file
    '''
    _name = 'import.cell.data'

    def get_cell_data(self, cr, uid, ids, row, cell_nb, context=None):
        if context is None:
            context = {}
        cell_data = False
        try:
            line_content = row.cells
        except ValueError:
            line_content = row.cells
        if line_content and len(line_content) - 1 >= cell_nb and row.cells[cell_nb]:
            if row.cells[cell_nb].data or context.get('from_je_import', False):
                # at JE import store the exact value: 0.00 and False are handled differently
                cell_data = row.cells[cell_nb].data
        return cell_data

    def get_purchase_id(self, cr, uid, ids, row, cell_nb, line_num, error_list, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data and isinstance(cell_data, (str,)):
            purchase_name = cell_data.strip()
            purchase_ids = self.pool.get('purchase.order').search(cr, uid, [('name', '=', purchase_name)])
            if purchase_ids:
                return purchase_ids[0]
        return False


    def get_picking_id(self, cr, uid, ids, row, cell_nb, line_num, error_list, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data and isinstance(cell_data, (str,)):
            incoming_shipment_name = cell_data.strip()
            picking_ids = self.pool.get('stock.picking').search(cr, uid, [('name', '=', incoming_shipment_name)])
            if picking_ids:
                return picking_ids[0]
        return False

    def get_move_line_number(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data:
            if isinstance(cell_data, (int, long)):
                return cell_data
        return False

    def get_product_id(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data and isinstance(cell_data, (str,)):
            default_code = cell_data.strip()
            product_ids = self.pool.get('product.product').search(cr, uid, [('default_code', '=', default_code)])
            if product_ids:
                return product_ids[0]
        return False

    def get_product_qty(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data:
            if isinstance(cell_data, (float, int, long)):
                return cell_data
        return False

    def get_product_uom_id(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data and isinstance(cell_data, (str,)):
            product_uom_name = cell_data.strip()
            product_uom_ids = self.pool.get('product.uom').search(cr, uid, [('name', '=', product_uom_name)])
            if product_uom_ids:
                return product_uom_ids[0]
        return False

    def get_prodlot_name(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data and isinstance(cell_data, (str,)):
            return cell_data.strip()
        elif cell_data and isinstance(cell_data, (int,)):
            return cell_data
        return False

    def get_expired_date(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb)
        if cell_data:
            if row.cells[cell_nb].type == 'datetime':
                return cell_data.strftime('%Y-%m-%d')
            else:
                try:
                    expired_date = DateTime.strptime(cell_data,'%Y-%m-%d')
                    return str(expired_date)
                except ValueError:
                    try:
                        expired_date = DateTime.strptime(cell_data,'%Y/%m/%d')
                        return str(expired_date)
                    except ValueError:
                        try:
                            expired_date = DateTime.strptime(cell_data,'%d-%m-%Y')
                            return str(expired_date)
                        except ValueError:
                            try:
                                expired_date = DateTime.strptime(cell_data,'%d/%m/%Y')
                                return str(expired_date)
                            except ValueError:
                                try:
                                    expired_date = DateTime.strptime(cell_data,'%d-%b-%Y')
                                    return str(expired_date)
                                except ValueError:
                                    try:
                                        expired_date = DateTime.strptime(cell_data,'%d/%b/%Y')
                                        return str(expired_date)
                                    except ValueError:
                                        return False
        return False

    def get_line_values(self, cr, uid, ids, row, context=None):
        if context is None:
            context = {}
        list_of_values = []
        for cell_nb in range(len(row)):
            cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb, context=context)
            # cells filled with whitespace should behave the same as cells that are empty
            if isinstance(cell_data, basestring) and cell_data.isspace():
                cell_data = ''
            list_of_values.append(cell_data)
        return list_of_values

import_cell_data()
