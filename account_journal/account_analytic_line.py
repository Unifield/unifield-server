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

from osv import osv
from osv import fields

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def _get_amount_currency(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Get amount currency.
        Get amount currency given in move attached to analytic line or default stored amount if no move_id exists.
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        for aal in self.browse(cr, uid, ids, context=context):
            if aal.move_id:
                res[aal.id] = aal.move_id.amount_currency
            else:
                sql = "SELECT amount_currency FROM %s WHERE id = %s" % (self._table, aal.id)
                cr.execute(sql)
                sql_result = cr.fetchone()
                res[aal.id] = sql_result and sql_result[0] or None
        return res

    def _set_amount_currency(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context={}):
        """
        Set amount currency if no move_id in value
        """
        if name and value:
            sql = "UPDATE %s SET %s = %s WHERE id = %s" % (self._table, name, value, id)
            cr.execute(sql)
        return True

    _columns = {
        'reversal_origin': fields.many2one('account.analytic.line', string="Reversal origin", readonly=True, help="Line that have been reversed."),
        'invoice_line_id': fields.many2one('account.invoice.line', string="Invoice line", readonly=True, help="Invoice line from which this line is linked."),
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'amount_currency': fields.function(_get_amount_currency, fnct_inv=_set_amount_currency, method=True, store=True, string="Amount currency", type="float", readonly="True", help="")
    }

    def copy(self, cr, uid, id, defaults, context={}):
        """
        Update amount_currency from previous element
        """
        amt = self.read(cr, uid, id, ['amount_currency'], context=context).get('amount_currency', False)
        res = super(account_analytic_line, self).copy(cr, uid, id, defaults, context=context)
        self.write(cr, uid, [res], {'amount_currency': amt}, context=context)
        return res

account_analytic_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
