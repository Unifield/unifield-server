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

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        summary_obj = self.pool.get('msf.budget.summary')
        if context is None:
            context = {}
        if 'search_budget' in context and context['search_budget']:
            if 'summary_id' in context and context['summary_id']:
                domain = summary_obj._get_analytic_domain(cr, uid, context['summary_id'], context=context)
                if domain:
                    args += domain
                else:
                    # Line without domain (consumption, overhead)
                    raise osv.except_osv(_('No Analytic Domain !'),_("This budget does not have an analytic domain!"))
                    
        return super(account_analytic_line, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
