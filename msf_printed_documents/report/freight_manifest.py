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
        self.getadditional_items_kgtot = 0.0
        self.voltot = 0.0
        self.valtot = 0.0
        self.cur = False
        self.localcontext.update({
            'time': time,
            'enumerate': enumerate,
            'get_lines': self.get_lines,
            'getEtd': self.getEtd,
            'getEta': self.getEta,
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
            #addtional items
            'get_additional_items': self.get_additional_items,
            'getadditional_items_name': self.getadditional_items_name,
            'getadditional_items_qty': self.getadditional_items_qty,
            'getadditional_items_uom': self.getadditional_items_uom,
            'getadditional_items_comment': self.getadditional_items_comment,
            'getadditional_items_volume': self.getadditional_items_volume,
            'getadditional_items_weight': self.getadditional_items_weight,
            'getadditional_items_getTotKg': self.getadditional_items_getTotKg,
            'getallTotKg': self.getallTotKg,
        })

    def getFonCur(self,ligne):
        return self.cur

    def getTotM3(self):
        return self.voltot and self.voltot or '0.0'

    def getTotValue(self):
        return self.formatLang(self.valtot and self.valtot or 0.)

    def getTotParce(self):
        return self.parcetot and self.parcetot or '0.0'

    def getTotKg(self):
        return self.formatLang(self.kgtot and self.kgtot or 0.)

    def get_lines(self, o):
        return o[0].pack_family_memory_ids

    def getEtd(self, o):
        return time.strftime('%d/%m/%Y',time.strptime(o.date_of_departure,'%Y-%m-%d'))

    def getEta(self, o):
        return time.strftime('%d/%m/%Y',time.strptime(o.planned_date_of_arrival,'%Y-%m-%d'))

    def getDataRef(self, ligne):
        if ligne.currency_id:
            self.cur = ligne.currency_id.name
        return ligne and ligne.sale_order_id and ligne.sale_order_id.name or False

    def getDataPpl(self, ligne):
        return ligne and ligne.ppl_id and ligne.ppl_id.name or False

    def getDataDescr(self, ligne):
        return ligne and ligne.ppl_id and ligne.ppl_id.description_ppl or False

    def getDataKg(self, ligne):
        self.kgtot += ligne.total_weight
        return ligne and ligne.total_weight or '0.0'

    def getDataParce(self, ligne):
        self.parcetot += ligne.num_of_packs
        return ligne and ligne.num_of_packs or '0'

    def getDataM3(self, ligne):
        self.voltot += ligne.total_volume/1000.00
        return ligne and ligne.total_volume/1000.00 or '0.0'

    def getDataValue(self, ligne):
        self.valtot += ligne.total_amount
        return ligne and ligne.total_amount or '0.0'

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

    def get_additional_items(self, o):
        return o[0].additional_items_ids

    def getadditional_items_name(self, line):
        return line.name

    def getadditional_items_qty(self, line):
        return line.quantity

    def getadditional_items_uom(self, line):
        return line.uom.name

    def getadditional_items_comment(self, line):
        return line.comment

    def getadditional_items_volume(self, line):
        return line.volume / 1000.00

    def getadditional_items_weight(self, line):
        self.getadditional_items_kgtot += line.weight
        return line.weight

    def getadditional_items_getTotKg(self):
        return self.getadditional_items_kgtot and self.getadditional_items_kgtot or '0.0'

    def getallTotKg(self):
        return self.formatLang(self.getadditional_items_kgtot + self.kgtot or 0.)

report_sxw.report_sxw('report.msf.freight_manifest', 'shipment', 'addons/msf_printed_documents/report/freight_manifest.rml', parser=freight_manifest, header=False,)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
