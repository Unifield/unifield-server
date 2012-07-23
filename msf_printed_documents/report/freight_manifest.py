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

class freight_manifest(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(freight_manifest, self).__init__(cr, uid, name, context=context)
        self.parcetot = 0
        self.kgtot = 0.0
        self.voltot = 0.0
        self.valtot = 0.0
        self.localcontext.update({
            'time': time,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getEtd': self.getEtd,
            'getEta': self.getEta,
            'getTransport': self.getTransport,
            'getDataRef': self.getDataRef,
            'getDataPpl': self.getDataPpl,
            'getDataDescr': self.getDataDescr,
            'getDataKg': self.getDataKg,
            'getDataParce': self.getDataParce,
            'getDataM3': self.getDataM3,
            'getDataValue': self.getDataValue,
            'getDataKC': self.getDataKC,
            'getDataDG': self.getDataDG,
            'getDataNP': self.getDataNP,
            'getTotParce': self.getTotParce,
            'getTotM3': self.getTotM3,
            'getTotValue': self.getTotValue,
            'getTotKg': self.getTotKg,
            'getFonCur': self.getFonCur,
        })

    def getFonCur(self,ligne):
        return ligne.currency_id and ligne.currency_id.name or False

    def getTotM3(self):
        return self.voltot and self.voltot or '0.0'

    def getTotValue(self):
        return self.valtot and self.valtot or '0.0'

    def getTotParce(self):
        return self.parcetot

    def getTotKg(self):
        return self.kgtot

    def get_lines(self, o): 
        return o[0].pack_family_memory_ids

    def getEtd(self, o):
        return time.strftime('%d/%m/%y',time.strptime(o.date_of_departure,'%Y-%m-%d'))

    def getEta(self, o):
        return time.strftime('%d/%m/%y',time.strptime(o.planned_date_of_arrival,'%Y-%m-%d'))

    def getTransport(self, o):
        sta = self.get_selection(o, 'transport_type')
        return sta

    def get_selection(self, o, field):
        sel = self.pool.get(o._name).fields_get(self.cr, self.uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(self.cr, self.uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(self.cr, self.uid, tr_ids, ['value'])[0]['value']
        else:
            return res

    def getDataRef(self, ligne):
        return ligne and ligne.sale_order_id and ligne.sale_order_id.name or False

    def getDataPpl(self, ligne):
        return ligne and ligne.ppl_id and ligne.ppl_id.name or False

    def getDataDescr(self, ligne):
        #return ligne.description and ligne.description or 'Pas de description'
        return False        

    def getDataKg(self, ligne):
        self.kgtot += ligne.total_weight
        return ligne and ligne.total_weight or '0.0'

    def getDataParce(self, ligne):
        self.parcetot += ligne.num_of_packs
        return ligne and ligne.num_of_packs or '0'

    def getDataM3(self, ligne):
        #self.voltot += ligne.total_volume
        #return ligne.total_volume and ligne.total_volume or 0.0
        return '0.0'

    def getDataValue(self, ligne):
        self.valtot += ligne.total_amount
        return ligne.total_amount and ligne.total_amount or '0.0'

    def getDataKC(self, ligne):
        for x in ligne.move_lines:
            if x.kc_check:
                return 'X'
        return ''

    def getDataDG(self, ligne):
        for x in ligne.move_lines:
            if x.dg_check:
                return 'X'
        return ''

    def getDataNP(self, ligne):
        for x in ligne.move_lines:
            if x.np_check:
                return 'X'
        return ''

report_sxw.report_sxw('report.msf.freight_manifest', 'shipment', 'addons/msf_printed_documents/report/freight_manifest.rml', parser=freight_manifest, header=False,)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

