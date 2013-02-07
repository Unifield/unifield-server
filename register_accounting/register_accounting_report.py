# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

# !!! each time you create a new report the "name" in the xml file should be on the form "report.sale.order_xls" but WITHOUT "report" at the beginning)
# so in that case, only name="sale.order_xls" in the xml

from osv import osv
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport



SpreadsheetReport('report.open.advances.2','account.bank.statement','addons/register_accounting/report/open_advances_xls.mako')

