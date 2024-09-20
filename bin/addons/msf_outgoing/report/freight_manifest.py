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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


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
            'getTotParce': self.getTotParce,
            'getTotM3': self.getTotM3,
            'getTotValue': self.getTotValue,
            'getTotKg': self.getTotKg,
            'getFonCur': self.getFonCur,
            'get_total': self.get_total,
            'get_group_lines': self.get_group_lines,
            'get_sum_additionnal': self.get_sum_additionnal,
        })

    def getFonCur(self):
        return self.cur

    def getTotM3(self):
        return self.voltot and round(self.voltot, 4) or 0.0

    def getTotValue(self):
        return self.valtot and self.valtot or 0.0

    def getTotParce(self):
        return self.parcetot and self.parcetot or 0

    def getTotKg(self):
        return self.kgtot and round(self.kgtot, 2) or 0.0

    # BKLG_84
    def get_group_lines(self, report_data):
        lines_output = []
        line_obj = {}

        for line in report_data.pack_family_memory_ids:
            if line.not_shipped:
                continue
            if line.currency_id:
                self.cur = line.currency_id.name
            self.parcetot += line.num_of_packs
            self.kgtot += line.total_weight
            self.voltot += line.total_volume/1000.00
            self.valtot += line.total_amount

            line_ref = line and line.sale_order_id and line.sale_order_id.name or False
            line_po_ref = line and line.sale_order_id and line.sale_order_id.client_order_ref or False
            line_pl = line and line.ppl_id and line.ppl_id.name or False
            if line.packing_list:
                line_pl = '%s (%s: %s)' % (line_pl, _('Supplier PL'), line.packing_list)

            kc = ""
            dg = ""
            np = ""
            for x in line.move_lines:
                if x.kc_check:
                    kc = x.kc_check
                if x.dg_check:
                    dg = x.dg_check
                if x.np_check:
                    np = x.np_check

            if line_ref not in line_obj:
                line_obj[line_ref] = {}

            if line_pl not in line_obj[line_ref]:
                line_obj[line_ref][line_pl] = {
                    'desc': '',
                    'po_ref': '',
                    'parcels': 0,
                    'kgs': 0,
                    'm3': 0,
                    'value': 0,
                    'kc': 0,
                    'dg': 0,
                    'np': 0
                }

            line_obj[line_ref][line_pl]['desc'] = line.description_ppl or ''
            line_obj[line_ref][line_pl]['po_ref'] = line_po_ref or ''
            line_obj[line_ref][line_pl]['parcels'] += line.num_of_packs or 0
            line_obj[line_ref][line_pl]['kgs'] += line.total_weight or 0.0
            line_obj[line_ref][line_pl]['m3'] += line.total_volume/1000.0 or 0.0
            line_obj[line_ref][line_pl]['value'] += line.total_amount or 0.0
            if kc != "":
                line_obj[line_ref][line_pl]['kc'] = kc
            if dg != "":
                line_obj[line_ref][line_pl]['dg'] = dg
            if np != "":
                line_obj[line_ref][line_pl]['np'] = np

        for ref in line_obj:
            for ppl in line_obj[ref]:
                current = {
                    'ref': ref,
                    'po_ref': line_obj[ref][ppl]['po_ref'],
                    'ppl': ppl,
                    'desc': line_obj[ref][ppl]['desc'],
                    'parcels': line_obj[ref][ppl]['parcels'],
                    'kgs': round(line_obj[ref][ppl]['kgs'], 2),
                    'm3': round(line_obj[ref][ppl]['m3'], 4),
                    'value': round(line_obj[ref][ppl]['value'], 2),
                    'kc': line_obj[ref][ppl]['kc'],
                    'dg': line_obj[ref][ppl]['dg'],
                    'np': line_obj[ref][ppl]['np']
                }
                lines_output.append(current)
        return lines_output

    def get_lines(self, o):
        return o[0].pack_family_memory_ids

    def getEtd(self, o):
        return time.strftime('%d/%m/%Y',time.strptime(o.date_of_departure,'%Y-%m-%d'))

    def getEta(self, o):
        return time.strftime('%d/%m/%Y',time.strptime(o.planned_date_of_arrival,'%Y-%m-%d'))

    def get_sum_additionnal(self, o):
        nb = sum([x.nb_parcels or 0 for x in o.additional_items_ids])
        self.parcetot += nb

        weigth = sum([x.weight or 0 for x in o.additional_items_ids])
        self.kgtot += weigth

        volume = sum([x.volume or 0 for x in o.additional_items_ids])/1000.0
        self.voltot += volume

        value = sum([x.value or 0 for x in o.additional_items_ids])
        self.valtot += value
        return [(nb, round(weigth, 2), round(volume, 4), round(value, 2), self.cur)]

    def get_total(self):
        return [(self.parcetot, round(self.kgtot, 2), round(self.voltot, 4), round(self.valtot, 2), self.cur)]


report_sxw.report_sxw('report.freight_manifest', 'shipment', 'addons/msf_outgoing/report/freight_manifest.rml', parser=freight_manifest)


class freight_manifest_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(freight_manifest_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(freight_manifest_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


freight_manifest_xls('report.freight_manifest_xls', 'shipment', 'msf_outgoing/report/freight_manifest_xls.mako', parser=freight_manifest)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
