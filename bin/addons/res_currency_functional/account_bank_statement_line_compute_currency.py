# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import fields, osv
from base import currency_date


class account_bank_statement_line_compute_currency(osv.osv):
    _inherit = "account.bank.statement.line"


    def _compute(self, cr, uid, ids, name, args, context):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for statement_line in self.browse(cr, uid, ids):
            ctx = {}
            curr_date = currency_date.get_date(self, cr, statement_line.document_date, statement_line.date)
            if curr_date:
                ctx['currency_date'] = curr_date
            try:
                res[statement_line.id] = {
                    'functional_in': cur_obj.compute(cr, uid, statement_line.currency_id.id,
                                                     statement_line.functional_currency_id.id, statement_line.amount_in, round=True, context=ctx),
                    'functional_out': cur_obj.compute(cr, uid, statement_line.currency_id.id,
                                                      statement_line.functional_currency_id.id, statement_line.amount_out, round=True, context=ctx),
                }
            except osv.except_osv:
                res[statement_line.id] = {
                    'functional_in': 0,
                    'functional_out': 0
                }
        return res

    _columns = {
        'currency_id': fields.related('statement_id', 'currency', type="many2one", relation="res.currency", string="Currency", store=False, write_relate=False),
        'functional_in': fields.function(_compute, method=True, store=False, type='float', string='Func. In', multi='amount_in, amount_out'),
        'functional_out': fields.function(_compute, method=True, store=False, type='float', string='Func. Out', multi='amount_in, amount_out'),
        'functional_currency_id': fields.related('company_id', 'currency_id', type="many2one", relation="res.currency", string="Func. Currency", store=False, write_relate=False),
    }

account_bank_statement_line_compute_currency()
