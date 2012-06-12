#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from tools.translate import _

class mass_reallocation_search(osv.osv_memory):
    _name = 'mass.reallocation.search'
    _description = 'Mass Reallocation Search'

    def get_filled_mcdb(self, cr, uid, ids, context=None):
        """
        Give a pre-populated MCDB search form
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        valid_ids = []
        # Only process first id
        account = self.pool.get('account.analytic.account').browse(cr, uid, ids, context=context)[0]
        if account.category != 'FUNDING':
            raise osv.except_osv(_('Error'), _('This action only works for Funding Pool accounts!'))
        # Take all elements to create a domain
        search = []
        if account.date_start:
            search.append(('date', '>=', account.date_start))
        if account.date:
            search.append(('date', '<=', account.date))
        if account.tuple_destination_account_ids:
            account_ids = [x.account_id and x.account_id.id for x in account.tuple_destination_account_ids]
            destination_ids = [x.destination_id and x.destination_id.id for x in account.tuple_destination_account_ids]
            if account_ids:
                account_ids = list(set(account_ids))
            if destination_ids:
                destination_ids = list(set(destination_ids))
            search.append(('general_account_id', 'in', account_ids))
            search.append(('destination_id', 'in', destination_ids))
        if account.cost_center_ids:
            search.append(('cost_center_id', 'in', [x.id for x in account.cost_center_ids]))
        for criterium in [('account_id', '!=', account.id), ('journal_id.type', '!=', 'engagement'), ('is_reallocated', '=', False), ('is_reversal', '=', False)]:
            search.append(criterium)
        search.append(('contract_open','=', True))
        #search_ids = self.pool.get('account.analytic.line').search(cr, uid, search, context=context)
        #non_valid_ids = []
        ## Browse all analytic line to verify contract state
        #for aline in self.pool.get('account.analytic.line').browse(cr, uid, search_ids, context=context):
        #    contract_ids = self.pool.get('financing.contract.contract').search(cr, uid, [('funding_pool_ids', '=', aline.account_id.id)], context=context)
        #    valid = True
        #    for contract in self.pool.get('financing.contract.contract').browse(cr, uid, contract_ids, context=context):
        #        if contract.state in ['soft_closed', 'hard_closed']:
        #            valid = False
        #    if not valid:
        #        non_valid_ids.append(aline.id)
        ## Delete ids that doesn't correspond to a valid line
        #valid_ids = [x for x in search_ids if x not in non_valid_ids]
        #operator = 'in'
        #if len(valid_ids) == 1:
        #    operator = '='
        #domain = [('id', 'in', valid_ids)]
        
        # Update context for Mass reallocation
        context['analytic_account_from'] = ids[0]
        # and for column
        context.update({'display_fp': True})
        return {
            'name': 'Mass reallocation search for' + ' ' + account.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': search,
            'target': 'current',
        }

mass_reallocation_search()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
