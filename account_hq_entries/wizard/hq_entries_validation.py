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
from tools.translate import _

class hq_entries_validation(osv.osv_memory):
    _name = 'hq.entries.validation'
    _description = 'HQ entries validation'

    _columns = {
        'txt': fields.char("Text", size=128, readonly="1"),
    }

    def _get_hq_entries_number(self, cr, uid, active_ids, context=None):
        """
        Return number of HQ Entries to validate regarding the fact that some HQ Entry could be original entries and have some split lines.
        """
        res = 0
        if not active_ids:
            return res
        ids = set()
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        for hq in self.pool.get('hq.entries').browse(cr, uid, active_ids):
            ids.add(hq.id)
            if hq.is_original:
                for line in hq.split_ids:
                    ids.add(line.id)
            if hq.is_split:
                ids.add(hq.original_id.id)
                for line in hq.original_id.split_ids:
                    ids.add(line.id)
        if ids:
            res = len(ids)
        return res

    def _get_txt(self, cr, uid, context=None):
        if not context:
            context = {}
        ids = context.get('active_ids', [])
        if self.pool.get('hq.entries').search(cr, uid, [('id', 'in', ids), ('user_validated', '=', True)]):
            raise osv.except_osv(_('Error'), _('You cannot validate HQ Entries already validated !'))
        number = self._get_hq_entries_number(cr, uid, context.get('active_ids', False), context=context)
        return _('Are you sure you want to post %d HQ entries ?') % (number or 0,)


    def button_validate(self, cr, uid, ids, context):
        return self.pool.get('hq.entries.validation.wizard').validate(cr, uid, ids, context)

    _defaults = {
        'txt': _get_txt,
    }
hq_entries_validation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
