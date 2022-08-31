#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
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

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def _get_partner(self, cr, uid, ids, field_name, args, context=None):
        """
        Search 3RD party for analytic lines linked to a journal entry, otherwise attempt to search commitment partner
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        res = {}
        for l in self.browse(cr, uid, ids, context=context):
            # UTP-1182:
            if context.get('sync_update_execution', False):
                continue
            else:
                res[l.id] = False
            if l.move_id:
                if l.move_id.partner_type:
                    if l.move_id.partner_type._table_name != 'account.journal' and l.move_id.partner_type.name:
                        res[l.id] = l.move_id.partner_type.name or False
                    elif l.move_id.partner_type._table_name == 'account.journal' and l.move_id.partner_type.code:
                        res[l.id] = l.move_id.partner_type.code or False
                # UTP-1106: In case of HQ Entries, we don't have any "real 3RD party", but just a partner_txt. That's why we use it as it is!
                else:
                    res[l.id] = l.move_id.partner_txt or False
            elif l.commitment_line_id and l.commitment_line_id.commit_id and l.commitment_line_id.commit_id.partner_id and l.commitment_line_id.commit_id.partner_id.name:
                res[l.id] = l.commitment_line_id.commit_id.partner_id.name or False
            elif l.imported_commitment:
                res[l.id] = l.imported_partner_txt
        return res

    def _set_partner(self, cr, uid, ids, name, value, arg, context=None):
        """
        Set the partner_txt field if a value given
        """
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        sql = "UPDATE " + self._table + " SET partner_txt = %s WHERE id in %s"  # not_a_user_entry
        cr.execute(sql, (value or None, tuple(ids)))
        return True

    _columns = {
        'partner_txt': fields.function(_get_partner, fnct_inv=_set_partner, method=True, string="Third Party", readonly=True, type="text"),
        'imported_partner_txt': fields.text("Imported Third Party"),
    }

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
