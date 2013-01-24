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
        self.kc = False
        self.dg = False
        self.np = False
        self.localcontext.update({
            'time': time,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getDateCreation': self.getDateCreation,
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
            'getWarning': self.getWarning,
            'getOriginRef': self.getOriginRef,
            'get_selection': self.get_selection,
        })

    def getOriginRef(self,o):
        return o and o.purchase_id and o.purchase_id.origin or False

    def getWarning(self,):
        warn = ''
        tab = []
        if self.kc or self.dg or self.np:
            warn += 'You are about to receive'
        if self.kc :
            tab.append('heat')
        if self.np :
            tab.append('sensitive')
        if self.dg :
            tab.append('dangerous')
        if len(tab) > 0 :
            if len(tab) ==1:
                warn += ' ' + tab[0]
            elif len(tab) == 2:
                warn += ' ' + tab[0] + ' and ' + tab[1]
            elif len(tab) == 3:
                warn += ' ' + tab[0] + ', ' + tab[1] + ' and ' +  tab[2]
        if self.kc or self.dg or self.np:
            warn += ' goods products, please refer to the appropriate procedures'
        return warn

    def getQtyPO(self,line):
        if line.picking_id:
            for x in line.picking_id.move_lines:
                if x.line_number == line.line_number:
                    return x.product_qty
        return False

    def getQtyIS(self,line):
        return line.product_qty

    def getProject(self,o):
        return o and o.purchase_id and o.purchase_id.dest_address_id and o.purchase_id.dest_address_id.name or False

    def getDetail(self,o):
        return o and o.purchase_id and o.purchase_id.details or False

    def getCateg(self,o):
        sta = self.get_selection(o.purchase_id, 'categ')
        return sta

    def getPOref(self,o):
        return o and o.purchase_id and o.purchase_id.name or False

    def getERD(self,o):
        return time.strftime('%d/%m/%Y', time.strptime(o.min_date,'%Y-%m-%d %H:%M:%S'))

    def getPartnerCity(self,o):
        return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.city or False

    def getPartnerPhone(self,o):
        return o.purchase_id and o.purchase_id.partner_address_id and o.purchase_id.partner_address_id.phone or False

    def getPartnerName(self,o):
        return o.purchase_id and o.purchase_id.partner_id and o.purchase_id.partner_id.name or False

    def getPartnerAddress(self,o):
        temp = o.purchase_id and o.purchase_id.partner_address_id.name_get()
        if temp:
            return temp[0][1]

    def getWarehouse(self,o):
        return o.warehouse_id and o.warehouse_id.name or False

    def getTransportMode(self,o):
        sta = self.get_selection(o.purchase_id, 'transport_type')
        return sta

    def getPrio(self,o):
        sta = self.get_selection(o.purchase_id, 'priority')
        return sta

    def getConfirmedDeliveryDate(self,o):
        if o.purchase_id:
            return time.strftime('%d/%m/%Y', time.strptime( o.purchase_id.delivery_confirmed_date,'%Y-%m-%d'))
        return False

    def getTotItems(self,o):
        return len(o.move_lines)

    def check(self,line,opt):
        if opt == 'kc':
            if line.kc_check:
                self.kc = True
                return 'X'
            return ''
        elif opt == 'dg':
            if line.dg_check:
                self.dg = True
                return 'X'
            return ''
        elif opt == 'np':
            if line.np_check:
                self.np = True
                return 'X'
            return ''

    def getNbItem(self, ):
        self.item += 1
        return self.item

    def getDateCreation(self, o):
        return time.strftime('%d-%b-%Y', time.strptime(o.creation_date,'%Y-%m-%d %H:%M:%S'))


    def get_lines(self, o):
        return o.move_lines

    def get_selection(self, o, field):
        sel = self.pool.get(o._name).fields_get(self.cr, self.uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(self.cr, self.uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(self.cr, self.uid, tr_ids, ['value'])[0]['value']
        else:
            return res

report_sxw.report_sxw('report.msf.report_reception_in', 'stock.picking', 'addons/msf_printed_documents/report/report_reception.rml', parser=report_reception, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
