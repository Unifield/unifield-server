# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from report import report_sxw
import csv
import StringIO

class report_budget_criteria(report_sxw.report_sxw):
    _name = 'report.budget.criteria'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def create(self, cr, uid, ids, data, context=None):
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data['form']:
            writer.writerow(line)
        out = buffer.getvalue()    
        buffer.close()
        return (out, 'csv')
    
report_budget_criteria('report.msf.budget.criteria', 'msf.budget', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: