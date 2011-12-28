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
from tools.translate import _

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context={}, count=False):
        donor_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        if context is None:
            context = {}
        if 'search_financing_contract' in context and context['search_financing_contract']:
            if 'active_id' in context and \
               'reporting_type' in context:
                donor_line = donor_line_obj.browse(cr, uid, context['active_id'], context=context)
                # project domain
                if donor_line.computation_type not in ('children_sum', 'analytic_sum'):
                    raise osv.except_osv(_('Warning !'), _("The line selected has no analytic lines associated."))
                    return
                else:
                    # common domain part
                    date_domain = eval(donor_line.date_domain)
                    args += [date_domain[0],
                             date_domain[1],
                             donor_line_obj._get_account_domain(donor_line)]
                    if context['reporting_type'] == 'allocated':
                        # funding pool lines
                        args += [eval(donor_line.funding_pool_domain)]
                    else:
                        # total project lines
                        private_funds_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'PF')], context=context)
                        if private_funds_id:
                            args += [('account_id', '!=', private_funds_id),
                                     eval(donor_line.cost_center_domain)]
        
        return super(account_analytic_line, self).search(cr, uid, args, offset, limit, order, context=context, count=count)

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
