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
import datetime
from mx.DateTime import *

class wizard_csv_report(osv.osv_memory):

    _name = "wizard.csv.report"

    def _get_contract_header(self, cr, uid, contract, context=None):
        if context is None:
            context = {}
        if 'reporting_type' in context:

            # default 'out' currency to contract (reporting) currency
            out_currency_name = contract.reporting_currency.name
            out_currency_amount = contract.grant_amount

            if 'out_currency' in context:
                curr_id = context.get('out_currency')
                currency_id = self.pool.get('res.currency').browse(cr, uid, curr_id, context=None)
                out_currency_name = currency_id.name

                # get amount in selected currency
                out_currency_amount = self.pool.get('res.currency').compute(cr,
                                                           uid,
                                                           contract.reporting_currency.id,
                                                           currency_id.id,
                                                           out_currency_amount or 0.0,
                                                           round=True,
                                                           context=context)

            # Dictionary for selection

            # get Cost Center codes of the given contract
            costcenter_codes = ""
            for cc in contract.cost_center_ids:
                costcenter_codes = cc.code + ", " + costcenter_codes
            if costcenter_codes:
                costcenter_codes = costcenter_codes[:-2]

            reporting_type_selection = dict(self.pool.get('financing.contract.format')._columns['reporting_type'].selection)
            return [['FINANCIAL REPORT for financing contract'],
                    ['Report printing date::', datetime.datetime.now().strftime("%d-%b-%Y %H:%M")],
                    [''],
                    ['Donor:', contract.donor_id.name],
                    ['Financing contract name:', contract.name],
                    ['Financing contract code:', contract.code],
                    ['Grant amount:', out_currency_amount],
                    ['Reporting currency:', out_currency_name],
                    ['Eligible from:', contract.eligibility_from_date],
                    ['to:', contract.eligibility_to_date],
                    ['Reporting type:', reporting_type_selection[context.get('reporting_type')]],
                    ['Cost centers:', costcenter_codes]]
        else:
            return []

    def _get_contract_footer(self, cr, uid, contract, context=None):
        # Dictionary for selection
        if context is None:
            context = {}
        contract_state_selection = dict(self.pool.get('financing.contract.contract')._columns['state'].selection)

        return [['Open date:', contract.open_date and contract.open_date or None],
                ['Soft-closed date:', contract.soft_closed_date and contract.soft_closed_date or None],
                ['Hard-closed date:', contract.hard_closed_date and contract.hard_closed_date or None],
                ['State:', contract_state_selection[contract.state]]]

    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def _create_csv(self, data):
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(map(self._enc,line))
        out = buffer.getvalue()
        buffer.close()
        return (out, 'csv')

wizard_csv_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
