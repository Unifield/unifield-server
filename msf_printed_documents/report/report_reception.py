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
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getDateCreation': self.getDateCreation,
            'getDateFrom': self.getDateFrom,
            'getDateTo': self.getDateTo,
            'getNbItem': self.getNbItem,
            'check': self.check,
            'getTotItems': self.getTotItems,
            'getTransportMode': self.getTransportMode,
            'getPrio': self.getPrio,
            'getConfirmedDeliveryDate': self.getConfirmedDeliveryDate,
            'getWarehouse': self.getWarehouse,
            'getPartnerName': self.getPartnerName,
            'getPartnerAddress': self.getPartnerAddress,
            'getPartnerCity': self.getPartnerCity,
            'getPartnerPhone': self.getPartnerPhone,
            'getERD': self.getERD,
            'getPOref': self.getPOref,
            'getCateg': self.getCateg,
            'getDetail': self.getDetail,
            'getProject': self.getProject,
            'getQtyPO': self.getQtyPO,
            'getQtyIS': self.getQtyIS,
        })

    def getQtyPO(self,o):
        return 5

    def getQtyIS(self,o):
        return 5

    def getProject(self,o):
        return o and o.purchase_id and o.purchase_id.dest_address_id and o.purchase_id.dest_address_id.name or False

    def getDetail(self,o):
        return o and o.purchase_id and o.purchase_id.details or False

    def getCateg(self,o):
        return o and o.purchase_id and o.purchase_id.categ or False

    def getPOref(self,o):
        return o and o.purchase_id and o.purchase_id.name or False

    def getERD(self,o):
        return time.strftime('%d-%m-%Y', time.strptime(o.min_date,'%Y-%m-%d %H:%M:%S'))

    def getPartnerCity(self,o):
        return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.city or False

    def getPartnerPhone(self,o):
        return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.phone or False

    def getPartnerName(self,o):
        return o.purchase_id and o.purchase_id.partner_id and o.purchase_id.partner_id.name or False

    def getPartnerAddress(self,o):
        return o and o.purchase_id and o.purchase_id.partner_address_id

    def getWarehouse(self,o):
        return o.warehouse_id and o.warehouse_id.name or False

    def getTransportMode(self,o):
        return o.purchase_id and o.purchase_id.transport_type or False

    def getPrio(self,o):
        if o.purchase_id:
            return o.purchase_id.priority == 'normal' and 'Normal' or o.purchase_id.priority == 'emergency' and 'Emergency' or o.purchase_id.priority

    def getConfirmedDeliveryDate(self,o):
        if o.purchase_id:
            return time.strftime('%d/%m/%y', time.strptime( o.purchase_id.delivery_confirmed_date,'%Y-%m-%d'))
        return False

    def getTotItems(self,o):
        return len(o.move_lines)

    def check(self,line,opt):
        if opt == 'kc':    
            return line.kc_check and 'X' or ' '
        elif opt == 'dg':
            return line.dg_check and 'X' or ' '
        elif opt == 'np':
            return line.np_check and 'X' or ' '

    def getNbItem(self, ):
        self.item += 1
        return self.item

    def getDateCreation(self, o):
        return time.strftime('%d-%b-%y', time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))

    def getDateFrom(self, o):
        return time.strftime('%d-%b-%y', time.strptime(o.period_from,'%Y-%m-%d'))

    def getDateTo(self, o):
        return time.strftime('%d-%b-%y', time.strptime(o.period_to,'%Y-%m-%d'))

    def get_lines(self, o):
        return o.move_lines

report_sxw.report_sxw('report.msf.report_reception_in', 'stock.picking', 'addons/msf_printed_documents/report/report_reception.rml', parser=report_reception, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
