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
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
