#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

class hr_payroll_analytic_reallocation(osv.osv_memory):
    _name = 'hr.payroll.analytic.reallocation'
    _description = 'Payroll analytic reallocation wizard'

    _columns = {
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
    }

    def button_validate(self, cr, uid ,ids, context={}):
        """
        Give all lines the given analytic distribution
        """
        if not context:
            raise osv.except_osv(_('Error'), _('Unknown error'))
        line_ids = context.get('active_ids', [])
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0])
        vals = {}
        for el in ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id']:
            obj = getattr(wiz, el, None)
            if obj:
                vals.update({el: getattr(obj, 'id', None)})
        self.pool.get('hr.payroll.msf').write(cr, uid, line_ids, vals)
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hr_payroll_analytic_reallocation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
