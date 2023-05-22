# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from osv import osv
from tools.translate import _


class report_reception(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_reception, self).__init__(cr, uid, name, context=context)
        self.item = 0
        self.localcontext.update({
            'time': time,
            'getState': self.getState,
            'enumerate': enumerate,
            'get_lines_by_packing': self.get_lines_by_packing,
            'getDateCreation': self.getDateCreation,
            'check': self.check,
            'getTotItems': self.getTotItems,
            'getConfirmedDeliveryDate': self.getConfirmedDeliveryDate,
            'getWarehouse': self.getWarehouse,
            'getPartnerName': self.getPartnerName,
            'getPartnerAddress': self.getPartnerAddress,
            'getPartnerCity': self.getPartnerCity,
            'getPartnerPhone': self.getPartnerPhone,
            'getERD': self.getERD,
            'getPOref': self.getPOref,
            'getDetail': self.getDetail,
            'getProject': self.getProject,
            'getQtyIS': self.getQtyIS,
            'getWarning': self.getWarning,
            'getOriginRef': self.getOriginRef,
            'getBatch': self.getBatch,
            'getExpDate': self.getExpDate,
            'getActualReceiptDate': self.getActualReceiptDate,
            'getQtyBO': self.getQtyBO,
            'getFromScratchQty': self.getFromScratchQty,
        })

    def getState(self, o):
        return o.state

    def getOriginRef(self,o):
        return o and o.purchase_id and o.purchase_id.origin or False

    def getWarning(self, o):
        # UTP-756: Check the option right here on move lines of this stock picking, remove the check in self.check because it's too late!
        lines = o.move_lines
        kc_flag = False
        dg_flag = False
        for line in lines:
            if line.kc_check:
                kc_flag = True
            if line.dg_check:
                dg_flag = True

        warn = ''
        tab = []
        if kc_flag or dg_flag:
            warn += _('You are about to receive')
        if kc_flag :
            tab.append(_(' heat sensitive'))
        if dg_flag :
            tab.append(_(' dangerous'))
        if len(tab) > 0 :
            if len(tab) == 1:
                warn += tab[0]
            elif len(tab) == 2:
                warn += tab[0] + _(' and') + tab[1]
            elif len(tab) == 3:
                warn += tab[0] + ', ' + tab[1] + _(' and') + tab[2]
        if warn:
            warn += _(' goods products, please refer to the appropriate procedures')
        return warn

    def getQtyBO(self, line):
        '''
        Get the remaining qty to receive, comparing the sum of the qty of all done IN moves linked to the PO line, to
        the confirmed qty of the linked PO line
        '''
        bo_qty = line.state != 'done' and line.product_qty or 0
        if line.purchase_line_id:
            self.cr.execute("""SELECT SUM(product_qty) FROM stock_move WHERE purchase_line_id = %s AND state = 'done'
                AND type = 'in'""", (line.purchase_line_id.id,))
            sum_data = self.cr.fetchone()
            bo_qty = line.purchase_line_id.product_qty - (sum_data and sum_data[0] or 0)

        return bo_qty >= 0 and bo_qty or 0

    def getQtyIS(self, line, o, rounding):
        # Amount received in this IN only
        # REF-96: Don't count the shipped available IN

        val = 0
        if line.state == 'done':
            val = line.product_qty
        elif line.state == 'cancel' or o.state == 'cancel':
            return '0'  # US_275 Return 0 for cancel lines

        if val == 0:
            return ' '  # display blank instead 0
        return self.formatFloatDigitsToUom(val, rounding)

    def getQtyFromINs(self, qties, line_number, incoming, backorder_search):
        '''
        Recursive method to get the needed qties from an IN and all those linked to it
        '''
        if 'confirmed' not in qties or 'backorder' not in qties:
            raise osv.except_osv(_('Error'), _('Please ensure that the list "qties" has "confirmed" and "backorder"'))

        for move in incoming.move_lines:
            if move.line_number == line_number:
                qties['confirmed'] += move.product_qty
                if move.state not in ['done', 'cancel']:
                    qties['backorder'] += move.product_qty

        new_incoming = False
        if backorder_search:
            pick_obj = self.pool.get('stock.picking')
            backorder_ids = pick_obj.search(self.cr, self.uid, [('backorder_id', '=', incoming.id)], context=self.localcontext)
            if backorder_ids:
                new_incoming = pick_obj.browse(self.cr, self.uid, backorder_ids[0], context=self.localcontext)
        else:
            new_incoming = incoming.backorder_id

        if new_incoming:
            qties = self.getQtyFromINs(qties, line_number, new_incoming, backorder_search)

        return qties

    def getFromScratchQty(self, line):
        '''
        Get the total confirmed and backorder qty for this line using backorder_id data
        '''
        pick_obj = self.pool.get('stock.picking')
        qties = {
            'confirmed': line.product_qty,
            'backorder': line.state not in ['done', 'cancel'] and line.product_qty or 0.00,
        }

        # Get qties from processed INs
        if line.picking_id.backorder_id:
            qties = self.getQtyFromINs(qties, line.line_number, line.picking_id.backorder_id, False)
        # Get qties from backorders
        backorder_ids = pick_obj.search(self.cr, self.uid, [('backorder_id', '=', line.picking_id.id)], context=self.localcontext)
        if backorder_ids:
            qties = self.getQtyFromINs(qties, line.line_number, pick_obj.browse(self.cr, self.uid, backorder_ids[0],
                                                                                context=self.localcontext), True)

        return qties

    def getProject(self,o):
        return o and o.purchase_id and o.purchase_id.dest_address_id and o.purchase_id.dest_address_id.name or False

    def getDetail(self,o):
        return o and o.purchase_id and o.purchase_id.details or False

    def getPOref(self,o):
        return o and o.purchase_id and o.purchase_id.name or False

    def getERD(self,o):
        return time.strftime('%d/%m/%Y', time.strptime(o.min_date,'%Y-%m-%d %H:%M:%S'))

    def getPartnerCity(self,o):
        if o.purchase_id:
            return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.city or False
        elif o.partner_id and len(o.partner_id.address):
            return o.partner_id.address[0].city
        else:
            return False

    def getPartnerPhone(self,o):
        if o.purchase_id:
            return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.phone or False
        elif o.partner_id and len(o.partner_id.address):
            return o.partner_id.address[0].phone
        else:
            return False

    def getPartnerName(self,o):
        if o.purchase_id:
            return o.purchase_id and o.purchase_id.partner_id and o.purchase_id.partner_id.name or False
        if o.partner_id:
            return o.partner_id.name
        if o.ext_cu:
            return o.ext_cu.name

        return False

    def getPartnerAddress(self,o):
        if o.purchase_id:
            temp = o.purchase_id and o.purchase_id.partner_address_id.name_get()
        elif o.partner_id and len(o.partner_id.address):
            temp = o.partner_id.address[0].name_get()
        if temp:
            return temp[0][1]

    def getWarehouse(self,o):
        return o.warehouse_id and o.warehouse_id.name or False

    def getConfirmedDeliveryDate(self,o):
        if o.purchase_id:
            return time.strftime('%d/%m/%Y', time.strptime( o.purchase_id.delivery_confirmed_date,'%Y-%m-%d'))
        return False

    def getTotItems(self,o):
        return len(o.move_lines)

    def check(self,line,opt):
        options = {
            'kc': 'kc_check',
            'dg': 'dg_check',
            'np': 'np_check',
            'bm': 'lot_check',
            'ed': 'exp_check',
        }

        if opt in options and hasattr(line, options[opt]) and getattr(line, options[opt]) is True:
            return 'X'
        elif opt in options and hasattr(line, options[opt]):
            return getattr(line, options[opt])

        return ' '

    def getDateCreation(self, o):
        return time.strftime('%d-%b-%Y', time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))

    def getBatch(self, line):
        return line.prodlot_id.name

    def getExpDate(self, line):
        return time.strftime('%d/%m/%Y', time.strptime(line.prodlot_id.life_date,'%Y-%m-%d'))

    def getActualReceiptDate(self, o):
        if o.state != 'done':
            actual_receipt_date = ''
        else:
            actual_receipt_date = time.strftime('%d/%m/%Y', time.strptime(o.date_done, '%Y-%m-%d %H:%M:%S'))
        return actual_receipt_date

    def get_lines_by_packing(self, o):
        pack_info = {}
        for line in o.move_lines:
            pack_info.setdefault(line.pack_info_id or False, []).append(line)

        return sorted(pack_info.items(), key=lambda x: x[0] and (x[0].ppl_name, x[0].packing_list, x[0].parcel_from))


report_sxw.report_sxw('report.msf.report_reception_in', 'stock.picking', 'addons/msf_printed_documents/report/report_reception.rml', parser=report_reception, header=False)
