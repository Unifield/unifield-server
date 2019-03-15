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
import decimal_precision as dp

class account_analytic_line_compute_currency(osv.osv):
    _inherit = "account.analytic.line"
    
    def update_amounts(self, cr, uid, ids, context=None):
        """
        Update analytic line amount with debit and credit if move_id exists, otherwise use amount_currency to do change
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for analytic_line in self.browse(cr, uid, ids):
            amount = None
            if analytic_line.amount_currency and analytic_line.currency_id:
                context.update({'date': analytic_line.source_date or analytic_line.document_date})
                company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                amount = self.pool.get('res.currency').compute(cr, uid, analytic_line.currency_id.id, company_currency, 
                    analytic_line.amount_currency,round=False, context=context)
            if amount:
                cr.execute('update account_analytic_line set amount=%s where id=%s', (amount, analytic_line.id))
        return True
    
account_analytic_line_compute_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
