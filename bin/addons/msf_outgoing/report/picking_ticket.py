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
import pooler
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
        self.product_uom = move.product_id.uom_id
        self.state = move.state
        self.comment = move.comment
        self.product_qty = 0.00
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
            'getWarningMessage': self.get_warning,
            'getStock': self.get_qty_available,
            'getNbItems': self.get_nb_items,
            'getLines': self.get_lines,
            'getShipper': self.get_shipper,
            'getPickingShipper': self.get_picking_shipper,
            'getConsignee': self.get_consignee,
            'get_pdf_title': self.get_pdf_title,
        })

    def get_pdf_title(self):
        if self.objects[0].is_subpick:
            return _('Picking Ticket')
        elif self.objects[0].subtype == 'ppl':
            return _('PPL')
        return _('Picking List')

    def get_consignee(self, picking):
        """
        Return values for consignee
        @param picking: browse_record of the picking.ticket
        @return: A dictionnary with consignee values
        """
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')
        cr = self.cr
        uid = self.uid
        res = {}

        if picking.partner_id2:
            consignee_partner = picking.partner_id2
            consignee_addr_id = partner_obj.address_get(cr, uid, consignee_partner.id)['default']
            consignee_addr = None

            addr = ''
            addr_street = ''
            addr_zip_city = ''
            if consignee_addr_id:
                consignee_addr = addr_obj.browse(cr, uid, consignee_addr_id)
                if consignee_addr.street:
                    addr += consignee_addr.street
                    addr += ' '
                    addr_street += consignee_addr.street + ' '
                if consignee_addr.street2:
                    addr += consignee_addr.street2
                    addr += ' '
                    addr_street += consignee_addr.street2
                if consignee_addr.zip:
                    addr += consignee_addr.zip
                    addr += ' '
                    addr_zip_city += consignee_addr.zip + ' '
                if consignee_addr.city:
                    addr += consignee_addr.city
                    addr += ' '
                    addr_zip_city += consignee_addr.city
                if consignee_addr.country_id:
                    addr += consignee_addr.country_id.name

            res.update({
                'consignee_name': consignee_partner.name,
                'consignee_contact': consignee_partner.partner_type == 'internal' and 'Supply responsible' or consignee_addr and consignee_addr.name or '',
                'consignee_address': addr,
                'consignee_phone': consignee_addr and consignee_addr.phone or '',
                'consignee_email': consignee_addr and consignee_addr.email or '',
                'consignee_addr_street': addr_street,
                'consignee_addr_zip_city': addr_zip_city,
            })

        return [res]

    def get_shipper(self):
        """
        Return the shipper value for the given field
        @param field: Name of the field to retrieve
        @return: The value of the shipper field
        """
        return [self.pool.get('shipment').default_get(self.cr, self.uid, [])]

    def get_picking_shipper(self):
        """
        The 'Shipper' fields must be filled automatically with the
        default address of the current instance
        """
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')

        instance_partner = user_obj.browse(self.cr, self.uid, self.uid).company_id.partner_id
        instance_addr_id = partner_obj.address_get(self.cr,self. uid, instance_partner.id)['default']
        instance_addr = addr_obj.browse(self.cr, self.uid, instance_addr_id)

        addr_street = ''
        addr_zip_city = ''
        if instance_addr.street:
            addr_street += instance_addr.street + ' '
        if instance_addr.street2:
            addr_street += instance_addr.street2
        if instance_addr.zip:
            addr_zip_city += instance_addr.zip + ' '
        if instance_addr.city:
            addr_zip_city += instance_addr.city + ' '
        if instance_addr.country_id:
            addr_zip_city += instance_addr.country_id.name

        return {
            'shipper_name': instance_partner.name,
            'shipper_contact': 'Supply responsible',
            'shipper_addr_street': addr_street,
            'shipper_addr_zip_city': addr_zip_city,
            'shipper_phone': instance_addr.phone,
            'shipper_email': instance_addr.email,
        }

    def get_lines(self, picking, is_pdf=True):
        """
        Returns the move lines. For move lines with a batch number/expiry date
        create a first line with the whole quantity of product in stock, then
        one line for each batch with the quantity of batch in stock.
        """
        res = []
        dict_res = {}
        pool = pooler.get_pool(self.cr.dbname)

        for m in picking.move_lines:
            dict_res.setdefault(m.line_number, [])
            if m.prodlot_id and not dict_res[m.line_number] and is_pdf:
                # First create a line without batch
                dict_res[m.line_number].append(BatchMoveLines(m))
            bm = BatchMoveLines(m)
            bm.composition_list_id = m.composition_list_id
            bm.product_uom = m.product_uom
            bm.product_qty = m.product_qty
            bm.prodlot_id = m.prodlot_id
            bm.kc_check = m.product_id and m.product_id.is_kc or False
            bm.dg_check = m.product_id and m.product_id.is_dg or False
            bm.np_check = m.product_id and m.product_id.is_cs or False
            bm.from_pack = m.from_pack
            bm.to_pack = m.to_pack
            bm.total_weight = m.product_qty * m.product_id.weight
            bm.total_vol = m.product_qty * m.product_id.volume * 1000
            bm.pack_type = m.pack_type
            if m.prodlot_id and dict_res[m.line_number]:
                bm.no_product = True
                dict_res[m.line_number][0].product_qty += pool.get('product.uom')._compute_qty(
                    self.cr, self.uid, bm.product_uom.id, bm.product_qty, bm.product_id.uom_id.id)
            dict_res[m.line_number].append(bm)

        for key in dict_res:
            for m in dict_res[key]:
                res.append(m)

        return res

    def get_nb_items(self, picking):
        """
        Returns the number of different line number. If a line is split
        with a different product, this line count for +1
        """
        res = 0
        dict_res = {}
        for m in picking.move_lines:
            dict_res.setdefault(m.line_number, {})
            if m.product_id.id not in dict_res[m.line_number]:
                dict_res[m.line_number][m.product_id.id] = 1

        for ln in list(dict_res.values()):
            for p in list(ln.values()):
                res += p

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
                kc = _('heat sensitive')
            if m.dg_check:
                dg = _('dangerous goods')
            if kc and dg:
                and_msg = _(' and ')
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
            if obj.subtype not in ('picking', 'ppl'):
                raise osv.except_osv(_('Warning !'), _('Picking Ticket is only available for Picking Ticket Objects!'))

        return super(picking_ticket, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw(
    'report.picking.ticket',
    'stock.picking',
    'addons/msf_outgoing/report/picking_ticket.rml',
    parser=picking_ticket,
    header=False,
)

report_sxw.report_sxw(
    'report.empty.picking.ticket',
    'stock.picking',
    'addons/msf_outgoing/report/empty_picking_ticket.rml',
    parser=picking_ticket,
    header=False,
)
