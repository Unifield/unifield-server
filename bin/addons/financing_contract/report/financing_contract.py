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

import locale

from report import report_sxw

class contract(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(contract, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'locale': locale,
            'process': self.process,
            'get_totals': self.get_totals,
        })
        return


    def get_totals(self, reporting_lines):
        result = [0, 0]
        # Parse each budget line

        for line in reporting_lines:
            if line.line_type != 'view':
                result[0] += line.allocated_budget
                result[1] += line.project_budget
        return result

    def process(self, reporting_lines):
        def add_account_list_block_item(account_str, data_list, data_list_index):
            if len(data_list[data_list_index]) + len(account_str) > account_list_block_size:
                data_list.append('')
                data_list_index += 1

            if data_list[data_list_index]:
                data_list[data_list_index] += ', '
            data_list[data_list_index] += account_str
            return data_list_index

        register_states = dict(self.pool.get('financing.contract.format.line')._columns['line_type'].selection)
        result = []
        # US-678 cut account list in para blocks (rml crashes with oversized para)
        account_list_block_size = 4096

        # Parse each contract line
        for line in reporting_lines:
            account_list = ['']
            account_list_index = 0

            account_invalid_list = ['']
            account_invalid_index = 0
            if line.account_quadruplet_ids:
                # Case of quadruplet
                for quad in line.account_quadruplet_ids:
                    if not quad.disabled:
                        account_list_index = add_account_list_block_item(
                            " ".join([str(quad.account_destination_name),
                                      str(quad.funding_pool_id.code),
                                      str(quad.cost_center_id.code)]),
                            account_list, account_list_index)
                    else:
                        account_invalid_index = add_account_list_block_item(
                            " ".join([str(quad.account_destination_name),
                                      str(quad.funding_pool_id.code),
                                      str(quad.cost_center_id.code)]),
                            account_invalid_list, account_invalid_index)

            elif line.reporting_account_ids:
                # G/L Accounts Only selected
                for account in line.reporting_account_ids:
                    account_list_index = add_account_list_block_item(str(account.code), account_list, account_list_index)
            else:
                # Case where we have some destination_ids
                for account_destination in line.account_destination_ids:
                    account_list_index = add_account_list_block_item(
                        str(account_destination.account_id.code) \
                        + " " + str(account_destination.destination_id.code),
                        account_list, account_list_index)

            values = {
                'code': line.code,
                'name': line.name,
                'allocated_budget': line.allocated_budget,
                'project_budget': line.project_budget,
                'line_type': register_states[line.line_type],
                'account_list': account_list,
                'account_invalid_list': account_invalid_list
            }
            result.append(values)

        return result


report_sxw.report_sxw('report.financing.contract', 'financing.contract.contract', 'addons/financing_contract/report/financing_contract.rml', parser=contract)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

