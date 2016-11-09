# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class report_cheque_inventory(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_cheque_inventory, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLines': self.getLines,
        })
        return

    def getLines(self, statement):
        """
        Return list of lines from given register and previous ones that are not reconciled
        """
        # Prepare some values
        res = []
        absl_obj = self.pool.get('account.bank.statement.line')
        # Fetch all previous registers linked to this one
        prev_reg_ids = [statement.id]
        if statement.prev_reg_id:
            prev_reg_ids.append(statement.prev_reg_id.id)
            prev_reg_id = statement.prev_reg_id
            while prev_reg_id != False:
                prev_reg_id = prev_reg_id.prev_reg_id or False
                if prev_reg_id:
                    prev_reg_ids.append(prev_reg_id.id)
        absl_ids = absl_obj.search(self.cr, self.uid, [('statement_id', 'in', prev_reg_ids), ('reconciled', '=', False)])
        if absl_ids:
            res = absl_obj.browse(self.cr, self.uid, absl_ids)
        return res

SpreadsheetReport('report.cheque.inventory.2','account.bank.statement','addons/register_accounting/report/cheque_inventory_xls.mako', parser=report_cheque_inventory)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
