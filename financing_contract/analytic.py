#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from osv import fields
from tools.translate import _

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
            force_no_order=False, context=None, count=False):
        donor_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        if context is None:
            context = {}
        if 'search_financing_contract' in context and context['search_financing_contract']:
            if 'reporting_line_id' in context and context['reporting_line_id']:
                donor_line = donor_line_obj.browse(cr, uid, context['reporting_line_id'], context=context)
                if donor_line.analytic_domain:
                    args += donor_line.analytic_domain
                else:
                    # Line without domain (consumption, overhead)
                    raise osv.except_osv(_('No Analytic Domain !'),_("This line does not have an analytic domain!"))
                    
        return super(account_analytic_line, self).search(cr, uid, args, offset,
                limit, order, force_no_order=force_no_order, context=context,
                count=count)

    def _get_fake(self, cr, uid, ids, *a, **b):
        if isinstance(ids, (int, long)):
            ids = [ids]
        return {}.fromkeys(ids, False)

    def _search_contract_open(self, cr, uid, obj, name, args, context):
        if not len(args):
            return []

        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Warning'), _('Filter contract_open is not implemented with those arguments.'))

        cr.execute('''select distinct fpline.funding_pool_id 
                from financing_contract_funding_pool_line fpline
                left join financing_contract_contract contract on contract.format_id = fpline.contract_id
                where contract.state in ('soft_closed', 'hard_closed') ''')
        ids = [x[0] for x in cr.fetchall()]
        return [('account_id', 'not in', ids)]

    _columns = {
        'contract_open': fields.function(_get_fake, type='boolean', method=True, string='Exclude closed contract', fnct_search=_search_contract_open, help="Field used only to search lines."),
    }
account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
