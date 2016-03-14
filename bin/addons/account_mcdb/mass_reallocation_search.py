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
        # Only process first id
        account = self.pool.get('account.analytic.account').browse(cr, uid, ids, context=context)[0]
        if account.category != 'FUNDING':
            raise osv.except_osv(_('Error'), _('This action only works for Funding Pool accounts!'))
        # Take all elements to create a domain
        search = []
        if account.date_start:
            search.append(('document_date', '>=', account.date_start))
        if account.date:
            search.append(('document_date', '<=', account.date))
        # Search default MSF Private Fund analytic account
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        if account.id != fp_id:
            if account.tuple_destination_account_ids:
                search.append(('is_fp_compat_with', '=', account.id))
            else:
                # trick to avoid problem with FP that have NO destination link. So we need to search a "False" Destination.
                search.append(('destination_id', '=', 0))
            if account.cost_center_ids:
                search.append(('cost_center_id', 'in', [x.id for x in account.cost_center_ids]))
            else:
                # trick to avoid problem with FP that have NO CC.
                search.append(('cost_center_id', '=', 0))
        for criterium in [('account_id', '!=', account.id), ('journal_id.type', '!=', 'engagement'), ('is_reallocated', '=', False), ('is_reversal', '=', False)]:
            search.append(criterium)
        search.append(('contract_open','=', True))
        search.append(('move_state', '!=', 'draft'))
        
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
