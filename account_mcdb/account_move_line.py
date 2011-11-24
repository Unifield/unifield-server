#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from time import strftime

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def _get_output(self, cr, uid, ids, field_name, arg, context={}):
        """
        Get an amount regarding currency in context (from 'output' and 'output_currency_id' values)
        """
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Return nothing if no 'output_currency_id' in context
        if not context or not context.get('output_currency_id', False):
            for id in ids:
                res[id] = 0.0
            return res
        # Retrieve currency
        currency_id = context.get('output_currency_id')
        # Do calculation
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = 0.0
            # output_amount field
            if field_name == 'output_amount':
                # Update with date
                context.update({'date': ml.source_date or ml.date or strftime('%Y-%m-%d')})
                mnt = self.pool.get('res.currency').compute(cr, uid, currency_id, ml.currency_id.id, ml.amount_currency, round=True, context=context)
                res[ml.id] = mnt or 0.0
            # or output_currency field
            elif field_name == 'output_currency':
                res[ml.id] = currency_id
        return res

    _columns = {
        'output_amount': fields.function(_get_output, string="Output amount", type='float', method=True, store=False),
        'output_currency': fields.function(_get_output, string="Output curr.", type='many2one', relation='res.currency', method=True, store=False),
    }

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
