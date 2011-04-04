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

def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context={}):
    """
    Get "Third Parties" following other fields
    """
    res = {}
    for st_line in self.browse(cr, uid, ids, context=context):
        if st_line.employee_id:
            res[st_line.id] = 'hr.employee,%s' % st_line.employee_id.id
        elif st_line.register_id:
            res[st_line.id] = 'account.bank.statement,%s' % st_line.register_id.id
        elif st_line.partner_id:
            res[st_line.id] = 'res.partner,%s' % st_line.partner_id.id
        else:
            res[st_line.id] = None
    return res

def _set_third_parties(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context={}):
    """
    Set some fields in function of "Third Parties" field
    """
    if name and value:
        fields = value.split(",")
        element = fields[0]
        sql = "UPDATE %s SET " % self._table
        if element == 'hr.employee':
            obj = 'employee_id'
        elif element == 'account.bank.statement':
            obj = 'register_id'
        elif element == 'res.partner':
            obj = 'partner_id'
        if obj:
            sql += "%s = %s " % (obj, fields[1])
            sql += "WHERE id = %s" % id
            cr.execute(sql)
    return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
