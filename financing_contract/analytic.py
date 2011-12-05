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
import tools
from tools.translate import _

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context={}, count=False):
        donor_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        if context is None:
            context = {}
        if 'search_financing_contract' in context and context['search_financing_contract']:
            if 'active_id' in context:
                donor_line = donor_line_obj.browse(cr, uid, context['active_id'], context=context)
                if donor_line.analytic_domain:
                    args += donor_line.analytic_domain
                else:
                    # Line without domain (consumption, overhead)
                    raise osv.except_osv(_('No Analytic Domain !'),_("This line does not have an analytic domain!"))
                    
        return super(account_analytic_line, self).search(cr, uid, args, offset, limit, order, context=context, count=count)

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
