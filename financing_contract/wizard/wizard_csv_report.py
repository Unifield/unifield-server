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
from osv import fields, osv
import csv
import StringIO
from tools.translate import _

class wizard_csv_report(osv.osv_memory):
    
    _name = "wizard.csv.report"
    
    # Method to add formatting to csv values
    def _split_thousands(string):
        if len(string) <= 3:
            return string
        else:
            return _split_thousands(string[:-3]) + "," + string[-3:]
    
    def _get_contract_header(self, cr, uid, contract, context={}):
        if 'reporting_type' in context:
            # Dictionary for selection
            reporting_type_selection = dict(self.pool.get('financing.contract.format')._columns['reporting_type'].selection)
            return [['Financing contract name:', contract.name],
                    ['Financing contract code:', contract.code],
                    ['Donor:', contract.donor_id.name],
                    ['Eligible from:', contract.eligibility_from_date, 'to:', contract.eligibility_to_date],
                    ['Reporting type:', reporting_type_selection[context.get('reporting_type')]]]
        else:
            return []
    
    def _get_contract_footer(self, cr, uid, contract, context={}):
        # Dictionary for selection
        contract_state_selection = dict(self.pool.get('financing.contract.contract')._columns['state'].selection)
        
        return [['Open date:', contract.open_date and contract.open_date or None],
                ['Soft-closed date:', contract.soft_closed_date and contract.soft_closed_date or None],
                ['Hard-closed date:', contract.hard_closed_date and contract.hard_closed_date or None],
                ['State:', contract_state_selection[contract.state]]]
        
    def _create_csv(self, data):
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(line)
        out = buffer.getvalue()    
        buffer.close()
        return (out, 'csv')

wizard_csv_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
