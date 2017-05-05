#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

class res_currency_rate(osv.osv):
    _name = 'res.currency.rate'
    _inherit = 'res.currency.rate'

    _sql_constraints = [
        ('rate_unique', 'unique(name, currency_id)', "Only one rate per date is accorded."),
    ]

res_currency_rate()

class res_currency(osv.osv):
    _name = 'res.currency'
    _inherit = 'res.currency'

    def _check_unicity_currency_name(self, cr, uid, ids, context=None):
        """
        Check that no currency have the same name and the same currency_table_id.
        Check is non case-sensitive.
        """
        if not context:
            context = {}
        for c in self.browse(cr, uid, ids):
            if not c.currency_name:
                continue
            sql = """SELECT id, name
            FROM res_currency
            WHERE currency_name ilike %s"""
            if c.currency_table_id:
                sql += """\nAND currency_table_id in %s"""
                cr.execute(sql, (c.currency_name, tuple([c.currency_table_id.id])))
            else:
                sql += """\nAND currency_table_id is Null"""
                cr.execute(sql, (c.currency_name,))
            bad_ids = cr.fetchall()
            if bad_ids and len(bad_ids) > 1:
                return False
        return True

    def _check_unicity_name(self, cr, uid, ids, context=None):
        """
        Check that no currency is the same and have the same currency_table_id.
        Check is non case-sensitive.
        """
        if not context:
            context = {}
        for c in self.browse(cr, uid, ids):
            if not c.name:
                continue
            sql = """SELECT id, name
            FROM res_currency
            WHERE name ilike %s"""
            if c.currency_table_id:
                sql += """\nAND currency_table_id in %s"""
                cr.execute(sql, (c.name, tuple([c.currency_table_id.id])))
            else:
                sql += """\nAND currency_table_id is Null"""
                cr.execute(sql, (c.name,))
            bad_ids = cr.fetchall()
            if bad_ids and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity_currency_name, "Another currency have the same name.", ['currency_name']),
        (_check_unicity_name, "Same currency exists", ['name']),
    ]

res_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
