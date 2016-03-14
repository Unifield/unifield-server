# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 TeMPO Consulting, MSF. All Rights Reserved
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

from report import report_sxw
from msf_supply_doc_export.msf_supply_doc_export import WebKitParser
from msf_supply_doc_export.msf_supply_doc_export import getIds


class parser_standard_price_track_changes_report_xls(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(parser_standard_price_track_changes_report_xls, self).__init__(
            cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getSPTC': self._get_sptc,
        })

    def _get_sptc(self, product_id):
        """
        Return the standard.price.track.changes related to the product_id
        :param product_id:
        :return: List of browse_record of standard.price.track.changes
        """
        sptc_obj = self.pool.get('standard.price.track.changes')
        sptc_ids = sptc_obj.search(self.cr, self.uid, [
            ('product_id', '=', product_id),
        ])
        return sptc_obj.browse(self.cr, self.uid, sptc_ids)


class standard_price_track_changes_report_xls(WebKitParser):
    """
    Parser to generate the Cost Price Track Changes Excel report for a
    specific product.
    """

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser,
                              header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(standard_price_track_changes_report_xls,
                     self).create_single_pdf(cr, uid, ids, data, report_xml,
                                             context=context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(standard_price_track_changes_report_xls, self).create(cr,
                                                                        uid,
                                                                        ids,
                                                                        data,
                                                                        context)
        return a[0], 'xls'

standard_price_track_changes_report_xls(
    'report.product.cost.track.changes.xls',
    'product.product',
    'addons/product_attributes/report/standard_price_track_changes.mako',
    parser=parser_standard_price_track_changes_report_xls)