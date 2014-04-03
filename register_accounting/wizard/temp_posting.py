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
from ..register_tools import open_register_view

class wizard_temp_posting(osv.osv_memory):
    _name = "wizard.temp.posting"

    def action_confirm_temp_posting(self, cr, uid, ids, context=None):
        """
        Temp post some statement lines
        """
        if context is None:
            context = {}
        if 'active_ids' in context:
            # Retrieve statement line ids
            st_line_ids = context.get('active_ids')
            if isinstance(st_line_ids, (int, long)):
                st_line_ids = [st_line_ids]
            # Prepare some values
            tochange = []
            absl_obj = self.pool.get('account.bank.statement.line')
            # Browse statement lines
            for st_line in absl_obj.read(cr,uid, st_line_ids, ['statement_id', 'state']):
                # Verify that the line isn't in hard state
                if st_line.get('state', False) == 'draft':
                    tochange.append(st_line.get('id'))
            absl_obj.posting(cr, uid, tochange, 'temp')
            return open_register_view(self, cr, uid, st_line.get('statement_id')[0])
        else:
            raise osv.except_osv(_('Warning'), _('You have to select some lines before using this wizard.'))

wizard_temp_posting()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
