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
            line_ids = []
            res[move.id] = False
            move_line_obj = self.pool.get('account.move.line')
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

    def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get third party regarding some fields:
        - register_id
        - transfer_journal_id
        - partner_id
        - employee_id
        """
        res = {}
        for move in self.browse(cr, uid, ids):
            res[move.id] = False
            if move.partner_id2:
                res[move.id] = "%s,%s" % ('res.partner', move.partner_id2.id)
            elif move.transfer_journal_id:
                res[move.id] = "%s,%s" % ('account.journal', move.transfer_journal_id.id)
            elif move.register_id:
                res[move.id] = "%s,%s" % ('account.bank.statement', move.register_id.id)
            elif move.employee_id:
                res[move.id] = "%s,%s" % ('hr.employee', move.employee_id.id)
        return res

    def _set_third_parties(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context=None):
        """
        Set some fields in function of "Third Parties" field
        """
        if name and value:
            fields = value.split(",")
            element = fields[0]
            sql = "UPDATE %s SET " % self._table
            obj = False
            if element == 'hr.employee':
                obj = 'employee_id'
                other = ', register_id = Null, partner_id2 = Null, transfer_journal_id = Null '
            elif element == 'account.bank.statement':
                obj = 'register_id'
                other = ', employee_id = Null, partner_id2 = Null, transfer_journal_id = Null '
            elif element == 'res.partner':
                obj = 'partner_id2'
                other = ', employee_id = Null, register_id = Null, transfer_journal_id = Null '
            elif element == 'account.journal':
                obj = 'transfer_journal_id'
                other = ', employee_id = Null, register_id = Null, partner_id2 = Null '
            if obj:
                sql += "%s = %s " % (obj, fields[1])
                sql += other
                sql += "WHERE id = %s" % id
                cr.execute(sql)
        # Delete values for Third Parties if no value given
        elif name == 'set_partner_type' and not value:
            cr.execute("UPDATE %s SET employee_id = Null, register_id = Null, partner_id2 = Null, transfer_journal_id = Null WHERE id = %s" % (self._table, id))
        return True

    _columns = {
        'partner_type': fields.function(_get_third_parties_from_move_line, string="Third Parties", selection=[('account.bank.statement', 'Register'), ('hr.employee', 'Employee'), 
            ('res.partner', 'Partner'), ('account.journal', 'Journal')], size=128, readonly="1", type="reference", method=True),
        'set_partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee'), 
            ('account.bank.statement', 'Register')]),
        'register_id': fields.many2one("account.bank.statement", "Register"),
        'transfer_journal_id': fields.many2one("account.journal", "Journal"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'partner_id2': fields.many2one("res.partner", "Partner"),
    }

account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
