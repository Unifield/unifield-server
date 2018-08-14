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

class report_reception(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_reception, self).__init__(cr, uid, name, context=context)
        self.item = 0
        self.localcontext.update({
            'time': time,
            'getState': self.getState,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getDateCreation': self.getDateCreation,
            'getNbItem': self.getNbItem,
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
            'getQtyPO': self.getQtyPO,
            'getQtyIS': self.getQtyIS,
            'getWarning': self.getWarning,
            'getOriginRef': self.getOriginRef,
            'getBatch': self.getBatch,
            'getExpDate': self.getExpDate,
            'getActualReceiptDate': self.getActualReceiptDate,
            'getQtyBO': self.getQtyBO,
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
            warn += 'You are about to receive'
        if kc_flag :
            tab.append('heat sensitive')
        if dg_flag :
            tab.append('dangerous')
        if len(tab) > 0 :
            if len(tab) ==1:
                warn += ' ' + tab[0]
            elif len(tab) == 2:
                warn += ' ' + tab[0] + ' and ' + tab[1]
            elif len(tab) == 3:
                warn += ' ' + tab[0] + ', ' + tab[1] + ' and ' +  tab[2]
        if warn:
            warn += ' goods products, please refer to the appropriate procedures'
        return warn

    def getQtyPO(self,line):
        # line amount from the PO, always the same on all INs for a given PO
        val = line.product_qty
        return "{0:.2f}".format(val)

    def getQtyBO(self,line,o):
        # Back Order amount = PO amount - all receipts

        # get PO qty
        initial_qty = line.product_qty
        # get received qty (current and previous INs)
        cr, uid = self.cr, self.uid
        val = 0.00
        stock_move_obj = self.pool.get('stock.move')
        closed_move_ids = stock_move_obj.search(cr, uid, [('purchase_line_id','=',line.purchase_line_id.id),('state','=','done'),('type','=','in')])
        if closed_move_ids:
            stock_moves = stock_move_obj.browse(cr, uid, closed_move_ids)
            if stock_moves:
                for move in stock_moves:
                    val = val + move.product_qty

        qtyBO = initial_qty - val
        if qtyBO <= 0:
            qtyBO = 0

        return "{0:.2f}".format(qtyBO)

    def getQtyIS(self, line, o):
        # Amount received in this IN only
        # REF-96: Don't count the shipped available IN

        if line.state in ('cancel') or o.state in ('cancel'):
            return '0' # US_275 Return 0 for cancel lines
        elif o.state in ('assigned', 'shipped'):
            val = 0
        else:
            val = line.product_qty

        if val == 0:
            return ' ' # display blank instead 0
        return "{0:.2f}".format(val)


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

    def getNbItem(self, ):
        self.item += 1
        return self.item

    def getDateCreation(self, o):
        return time.strftime('%d-%b-%Y', time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))

    def getBatch(self, line):
        return line.prodlot_id.name

    def getExpDate(self, line):
        return time.strftime('%d/%m/%Y', time.strptime(line.prodlot_id.life_date,'%Y-%m-%d'))


    def getActualReceiptDate(self,o):
        if o.state != 'done':
            actual_receipt_date = ''
        elif not o.move_lines:
            ard = time.strptime(o.date, '%Y-%m-%d %H:%M:%S')
            actual_receipt_date = time.strftime('%d/%m/%Y', ard)
        else:
            ard_min = time.strptime(o.move_lines[0].date, '%Y-%m-%d %H:%M:%S')
            for move in o.move_lines:
                move_ard = time.strptime(move.date, '%Y-%m-%d %H:%M:%S')
                if move_ard < ard_min:
                    ard_min = move_ard
            actual_receipt_date = time.strftime('%d/%m/%Y', ard_min)
        return actual_receipt_date

    def get_lines(self, o):
        return o.move_lines

report_sxw.report_sxw('report.msf.report_reception_in', 'stock.picking', 'addons/msf_printed_documents/report/report_reception.rml', parser=report_reception, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
