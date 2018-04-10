#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
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

class hq_entries_unsplit(osv.osv_memory):
    _name = 'hq.entries.unsplit'
    _description = 'HQ entry unsplit wizard'

    _columns = {
        'line_ids': fields.many2many('hq.entries', 'hq_entries_unsplit_rel', 'wizard_id', 'line_id', "Selected lines", help="Lines previously selected by the user", readonly=True),
        'process_ids': fields.many2many('hq.entries', 'hq_entries_unsplit_process_rel', 'wizard_id', 'line_id', "Valid lines", help="Lines that would be processed", readonly=True),
    }

    def create(self, cr, uid, vals, context=None):
        # BKLG-77: check transation at wiz creation (done by hq.entries model)
        line_ids = context and context.get('active_ids', []) or []
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        self.pool.get('hq.entries').check_hq_entry_transaction(cr, uid,
            line_ids, self._name, context=context)
        return super(hq_entries_unsplit, self).create(cr, uid, vals,
            context=context)

    def button_validate(self, cr, uid, ids, context=None):
        """
        Unsplit lines from process_ids field in all given wizards
        """
        # Some checks
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        hq_obj = self.pool.get('hq.entries')
        for wiz in self.browse(cr, uid, ids, context=context):
            # Sort lines by type to:
            # - delete split ones
            # - change original one to "normal" one (HQ Entry)
            split_ids = []
            original_ids = []
            for line in wiz.process_ids:
                if line.is_original:
                    original_ids.append(line.id)
                    continue
                if line.is_split and line.original_id:
                    split_ids.append(line.id)
                    continue
            # Process
            context.update({'from': 'code'}) # "from: code" is to avoid unlink problems
            hq_obj.unlink(cr, uid, split_ids, context=context)
            hq_obj.write(cr, uid, original_ids, {'is_original': False, 'split_ids': False}, context=context)
        return {'type' : 'ir.actions.act_window_close',}

hq_entries_unsplit()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
