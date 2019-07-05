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
import pooler
from tools.translate import _


class parser_report_product_labels(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_report_product_labels, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getData': self.get_data,
        })

    def get_data(self, rep_object):
        '''
        Search if the report is from Batch, Product or Stock Card view and send back data.
        Batch: BN and ED
        Product: No BN or ED
        Stock Card: Add BN and ED if the product needs Batch management
        '''
        data = {}
        if rep_object:
            if rep_object[0]._table_name == 'stock.production.lot':
                data.update({
                    'product_code': rep_object[0].product_id.default_code,
                    'product_desc': rep_object[0].product_id.name,
                    'prodlot': rep_object[0].name,
                    'exp_date': rep_object[0].life_date,
                })
            elif rep_object[0]._table_name == 'product.product':
                data.update({
                    'product_code': rep_object[0].default_code,
                    'product_desc': rep_object[0].name,
                    'prodlot': False,
                    'exp_date': False,
                })
            elif rep_object[0]._table_name == 'stock.card.wizard':
                data.update({
                    'product_code': rep_object[0].product_id.default_code,
                    'product_desc': rep_object[0].product_id.name,
                    'prodlot': rep_object[0].prodlot_id and rep_object[0].prodlot_id.name or False,
                    'exp_date': rep_object[0].prodlot_id and rep_object[0].prodlot_id.life_date or False,
                })
            else:
                raise osv.except_osv(_('Error'), _("You can only generate Product Labels in the Product's, Stock Card's or Batch number's Action menu"))
        else:
            raise osv.except_osv(_('Error'), _('No document has been selected'))

        self.datas['rep_data'] = data

        return ''


report_sxw.report_sxw(
    'report.product_labels_batch',
    'stock.production.lot',
    'addons/msf_printed_documents/report/report_product_labels.rml',
    parser=parser_report_product_labels,
    header=False
)

report_sxw.report_sxw(
    'report.product_labels_product',
    'product.product',
    'addons/msf_printed_documents/report/report_product_labels.rml',
    parser=parser_report_product_labels,
    header=False
)

report_sxw.report_sxw(
    'report.product_labels_stock_card',
    'stock.card.wizard',
    'addons/msf_printed_documents/report/report_product_labels.rml',
    parser=parser_report_product_labels,
    header=False
)
