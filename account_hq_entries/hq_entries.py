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
from osv import fields

class hq_entries_validation_wizard(osv.osv_memory):
    _name = 'hq.entries.validation.wizard'

    def validate(self, cr, uid, ids, context={}):
        """
        Validate all given lines (in context)
        """
        # Some verifications
        if not context or not context.get('active_ids', False):
            return False
        active_ids = context.get('active_ids')
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        # Tag active_ids as user validated
        for line in self.pool.get('account.move.line').browse(cr, uid, active_ids, context=context):
            if not line.user_validated:
                self.pool.get('account.move.line').write(cr, uid, [line.id], {'user_validated': True}, context=context)
        action_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'action_hq_entries_tree')
        res = self.pool.get('ir.actions.act_window').read(cr, uid, action_id[1], [], context=context)
        res['target'] = 'crush'
        return res

hq_entries_validation_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
