#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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
from .register_tools import _populate_third_party_name


class account_move(osv.osv):
    _name = "account.move"
    _inherit = "account.move"

    def _get_third_parties_from_move_line(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Give the third parties of the given account.move.
        If all move lines content the same third parties, then return this third parties.
        If a partner_id field is filled in, then comparing both.
        """
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = False
            prev = None
            for move_line in move.line_id:
                if prev is None:
                    prev = move_line.third_parties
                elif prev != move_line.third_parties:
                    prev = False
                    break
            if prev:
                res[move.id] = "%s,%s"%(prev._table_name, prev.id)
        return res

    _columns = {
        'partner_type': fields.function(_get_third_parties_from_move_line, string="Third Parties", selection=[('hr.employee', 'Employee'),
                                                                                                              ('res.partner', 'Partner'), ('account.journal', 'Journal')], size=128, readonly="1", type="reference", method=True),
        'transfer_journal_id': fields.many2one("account.journal", "Journal", ondelete="restrict"),
        'employee_id': fields.many2one("hr.employee", "Employee", ondelete="restrict"),
        'partner_id2': fields.many2one("res.partner", "Partner", ondelete="restrict"),
    }

account_move()

class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        elif isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        to_modify = []
        name = vals.get('name', False)
        new_name = {}
        if name:
            for id in ids:
                oldemp = self.browse(cr, uid, id, fields_to_fetch=['name', 'section_code'], context=context)
                if name != oldemp.name:
                    to_modify.append(id)
                    section_code = vals.get('section_code', oldemp.section_code)
                    if section_code:
                        name = '%s %s' % (section_code, name)
                    new_name[id] = name

                    # BKLG-80: Populate changes to account.move.line and account.analytic when the name got updated

        res = super(hr_employee, self).write(cr, uid, ids, vals, context)
        for id in to_modify:
            _populate_third_party_name(self, cr, uid, id, 'employee_id', new_name[id], context)

        return res

hr_employee()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}

        to_modify = []
        name = vals.get('name', False)
        if name:
            for id in ids:
                oldname = self.browse(cr, uid, id, context=context).name
                if name != oldname:
                    to_modify.append(id)
                    # BKLG-80: Populate changes to account.move.line and account.analytic when the name got updated
        res = super(res_partner, self).write(cr, uid, ids, vals, context)
        for id in to_modify:
            _populate_third_party_name(self, cr, uid, id, 'partner_id', name, context)
        return res

res_partner()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
