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
            res[l.id] = ''
            if l.move_id:
                if l.move_id.partner_type and l.move_id.partner_type.name:
                    res[l.id] = l.move_id.partner_type.name or ''
            elif l.commitment_line_id and l.commitment_line_id.commit_id and l.commitment_line_id.commit_id.partner_id and l.commitment_line_id.commit_id.partner_id.name:
                res[l.id] = l.commitment_line_id.commit_id.partner_id.name or ''
            elif l.imported_commitment:
                res[l.id] = l.imported_partner_txt
        return res

    _columns = {
        'partner_txt': fields.function(_get_partner, method=True, string="Third Party", readonly=True, type="text", store=True),
        'imported_partner_txt': fields.text("Imported Third Party"),
    }

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
