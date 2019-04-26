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
from tools.translate import _

class hr_payroll_deletion(osv.osv):
    _name = 'hr.payroll.deletion'
    _description = 'Payroll entries deletion wizard'

    def button_validate(self, cr, uid, ids, context=None):
        """
        Delete ALL draft payroll entries
        """
        # Some verifications
        if not context:
            context = {}
        # Retrieve some values
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft')])
        if not line_ids:
            raise osv.except_osv(_('Warning'), _('No draft line found!'))
        self.pool.get('hr.payroll.msf').unlink(cr, uid, line_ids)
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hr_payroll_deletion()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
