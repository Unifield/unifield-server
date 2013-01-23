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
from osv import fields

class res_currency_rate(osv.osv):
    _name = 'res.currency.rate'
    _inherit = 'res.currency.rate'

    def _check_rate_unicity(self, cr, uid, ids, context=None):
        """
        Check that no rate exists on the same currency with the same date
        """
        if not context:
            context = {}
        for rate in self.browse(cr, uid, ids):
            rate_ids = self.search(cr, uid, [('name', '=', rate.name), ('currency_id', '=', rate.currency_id.id)])
            if rate_ids and len(rate_ids) > 1:
                raise osv.except_osv('Error', 'You can not have more than one rate valid for a currency on a given date.')
                return False
        return True

    _constraints = [
        (_check_rate_unicity, "Only one rate per date is accorded.", ['currency_id', 'name']),
    ]

res_currency_rate()

class res_currency(osv.osv):
    _name = 'res.currency'
    _inherit = 'res.currency'

    def _check_unicity(self, cr, uid, ids, context=None):
        """
        Check that no currency have the same code, the same name and the same currency_table_id.
        Check is non case-sensitive.
        """
        if not context:
            context = {}
        for c in self.browse(cr, uid, ids):
            sql = """SELECT id, name
            FROM res_currency
            WHERE (name ilike %s)
            AND (currency_name ilike %s)
            AND (active in ('t', 'f'))"""
            if c.currency_table_id:
                sql += """\nAND currency_table_id = %s""" % c.currency_table_id.id
            cr.execute(sql, (('%' + c.name + '%'), ('%' + c.currency_name + '%')))
            bad_ids = cr.fetchall()
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, "Another currency have the same code and name.", ['currency_name', 'name']),
    ]

res_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
