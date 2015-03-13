# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
from osv import osv
from tools.translate import _
from report import report_sxw


class BatchMoveLines(object):

    def __init__(self, move):
        self.move = move
        self.location_id = move.location_id
        self.product_id = move.product_id
        self.line_number = move.line_number
        self.sale_line_id = move.sale_line_id
        self.product_uom = None
        self.product_qty = None
        self.prodlot_id = None
        self.kc_check = False
        self.dg_check = False
        self.np_check = False
        self.no_product = False


class picking_ticket(report_sxw.rml_parse):
    """
    Parser for the picking ticket report
    """

    def __init__(self, cr, uid, name, context=None):
        """
        Set the localcontext on the parser

        :param cr: Cursor to the database
        :param uid: ID of the user that runs this method
        :param name: Name of the parser
        :param context: Context of the call
        """
        super(picking_ticket, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'self': self,
            'cr': cr,
            'uid': uid,
            'getWarningMessage': self.get_warning,
            'getStock': self.get_qty_available,
            'getLines': self.get_lines,
        })

    def get_lines(self, picking):
        """
        Returns the move lines. For move lines with a batch number/expiry date
        create a first line with the whole quantity of product in stock, then
        one line for each batch with the quantity of batch in stock.
        """
        res = []
        dict_res = {}

        for m in picking.move_lines:
            dict_res.setdefault(m.line_number, [])
            if m.prodlot_id and not dict_res[m.line_number]:
                # First create a line without batch
                dict_res[m.line_number].append(BatchMoveLines(m))
            bm = BatchMoveLines(m)
            bm.product_uom = m.product_uom
            bm.product_qty = m.product_qty
            bm.prodlot_id = m.prodlot_id
            bm.kc_check = m.kc_check
            bm.dg_check = m.dg_check
            bm.np_check = m.np_check
            if m.prodlot_id and dict_res[m.line_number]:
                bm.no_product = True
            dict_res[m.line_number].append(bm)

        for key in dict_res:
            for m in dict_res[key]:
                res.append(m)

        return res

    def get_warning(self, picking):
        """
        If the picking ticket contains heat sensitive, dangerous goods or both,
        return a message to be displayed on the picking ticket report.

        :param picking: A browse_record of stock.picking

        :return A message to be displayed on the report or False
        :rtype str or boolean
        """
        kc = ''
        dg = ''
        and_msg = ''

        for m in picking.move_lines:
            if m.kc_check:
                kc = 'heat sensitive'
            if m.dg_check:
                dg = 'dangerous goods'
            if kc and dg:
                and_msg = ' and '
                break

        if kc or dg:
            return _('You are about to pick %s%s%s products, please refer to the appropriate procedures') % (kc, and_msg, dg)

        return False

    def get_qty_available(self, move=False):
        """
        Return the available quantity of product in the source location of the move.
        I use this method because, by default, m.product_id.qty_available doesn't
        take care of the context.

        :param move: browse_record of a stock move

        :return The available stock for the product of the stock move in the
                source location of the stock move
        :rtype float
        """
        product_obj = self.pool.get('product.product')

        context = {}

        if not move:
            return 0.00

        if move.location_id:
            context = {
                'location': move.location_id.id,
                'location_id': move.location_id.id,
                'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
            }

        qty_available = product_obj.browse(
                self.cr,
                self.uid,
                move.product_id.id,
                context=context).qty_available

        return qty_available

    def set_context(self, objects, data, ids, report_type=None):
        """
        Override the set_context method of rml_parse to check if the object
        link to the report is a picking ticket.

        :param objects: List of browse_record used to generate the report
        :param data: Data of the report
        :param ids: List of ID of objects used to generate the report
        :param report_type: Type of the report

        :return Call the super() method
        """
        for obj in objects:
            if obj.subtype != 'picking':
                raise osv.except_osv(_('Warning !'), _('Picking Ticket is only available for Picking Ticket Objects!'))

        return super(picking_ticket, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw(
    'report.picking.ticket',
    'stock.picking',
    'addons/msf_outgoing/report/picking_ticket.rml',
    parser=picking_ticket,
    header=False,
)
