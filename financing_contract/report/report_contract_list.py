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
import locale
import pooler

class report_contract_list(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_contract_list, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'locale': locale,
            'get_contract_list': self.get_contract_list,
        })
        return

    def get_contract_list(self):
        result = []
        
        contract_obj = self.pool.get('financing.contract.contract')
        reporting_types = dict(self.pool.get('financing.contract.format')._columns['reporting_type'].selection)
        
        # get all contracts
        contract_ids = contract_obj.search(self.cr, self.uid, [], context={})
        contracts = contract_obj.browse(self.cr, self.uid, contract_ids, context={})
        
        for contract in contracts:
            earmarked_funding_pools = ""
            total_project_funding_pools = ""
            cost_centers = ""
            for funding_pool_line in contract.funding_pool_ids:
                total_project_funding_pools += funding_pool_line.funding_pool_id.code
                total_project_funding_pools += ", "
                if funding_pool_line.funded:
                    earmarked_funding_pools += funding_pool_line.funding_pool_id.code
                    earmarked_funding_pools += ", "
            for cost_center in contract.cost_center_ids:
                cost_centers += cost_center.code
                cost_centers += ", "
                    
            values = {'code': contract.code,
                      'name': contract.name,
                      'donor_grant_reference': contract.donor_grant_reference,
                      'hq_grant_reference': contract.hq_grant_reference,
                      'cost_centers': cost_centers[:-2],
                      'eligibility_from_date': contract.eligibility_from_date,
                      'eligibility_to_date': contract.eligibility_to_date,
                      'grant_amount': contract.grant_amount,
                      'reporting_currency': contract.reporting_currency.name,
                      'reporting_type': reporting_types[contract.reporting_type],
                      'earmarked_funding_pools': earmarked_funding_pools[:-2],
                      'total_project_funding_pools': total_project_funding_pools[:-2]}
            result.append(values)
        return result
        
report_sxw.report_sxw('report.financing.contract.list', 'financing.contract.contract', 'addons/financing_contract/report/contract_list.rml', parser=report_contract_list, header=False)
