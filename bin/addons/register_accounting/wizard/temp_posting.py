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

    def action_confirm_temp_posting(self, cr, uid, ids, context=None, all_lines=False):
        """
        Temp post some statement lines
        """
        if context is None:
            context = {}
        absl_obj = self.pool.get('account.bank.statement.line')
        # note: active_ids must be in context also for Temp Post "ALL", or that would mean that there is no line to post in the reg. anyway
        if context.get('active_ids'):
            # Retrieve statement line ids
            st_line_ids = context.get('active_ids')
            if isinstance(st_line_ids, (int, long)):
                st_line_ids = [st_line_ids]
            if all_lines:  # get ALL the register lines to temp-post for this register
                reg_id = absl_obj.browse(cr, uid, st_line_ids[0], fields_to_fetch=['statement_id'], context=context).statement_id.id
                if reg_id == context.get('register_id'):  # out of security compare with the register_id in param.
                    st_line_ids = absl_obj.search(cr, uid,
                                                  [('statement_id', '=', reg_id), ('state', '=', 'draft')],
                                                  context=context)
                    if not st_line_ids:
                        # UC = lines have been temp-posted since the display of the temp-posting page
                        raise osv.except_osv(_('Warning'), _('There are no more lines to temp-post for this register. '
                                                             'Please refresh the page.'))
                else:
                    raise osv.except_osv(_('Warning'), _('Impossible to retrieve automatically the lines to temp-post for this register. '
                                                         'Please select them manually and click on "Temp Posting".'))
            # Prepare some values
            tochange = []
            # Browse statement lines
            for st_line in absl_obj.read(cr,uid, st_line_ids, ['statement_id', 'state']):
                # Verify that the line isn't in hard state
                if st_line.get('state', False) == 'draft':
                    tochange.append(st_line.get('id'))
            real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
            absl_obj.posting(cr, real_uid, tochange, 'temp', context=context)
            return open_register_view(self, cr, real_uid, st_line.get('statement_id')[0])
        elif all_lines:
            raise osv.except_osv(_('Warning'), _('There are no lines to temp-post for this register.'))
        else:
            raise osv.except_osv(_('Warning'), _('You have to select some lines before using this wizard.'))

    def temp_post_all(self, cr, uid, ids, context=None):
        self.action_confirm_temp_posting(cr, uid, ids, context=context, all_lines=True)


wizard_temp_posting()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
