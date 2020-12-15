# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2020 TeMPO Consulting, MSF. All Rights Reserved
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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class fo_follow_up_finance(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        self.start_date = False
        self.end_date = False
        self.partner_ids = []
        self.order_id = False
        super(fo_follow_up_finance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLang': self._get_lang,
        })

    def _get_lang(self):
        return self.localcontext.get('lang', 'en_MF')


SpreadsheetReport('report.fo.follow.up.finance', 'fo.follow.up.finance.wizard',
                  'addons/finance/report/fo_follow_up_finance_xls.mako', parser=fo_follow_up_finance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
