# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import tools
from tools.translate import _

class account_bank_statement(osv.osv):
    _inherit = "account.bank.statement"
    _name = "account.bank.statement"

    def button_confirm_bank(self, cr, uid, ids, context=None):
        super(account_bank_statement,self).button_confirm_bank(cr, uid, ids, context=context)
        for st in self.browse(cr, uid, ids, context=context):
            for st_line in st.line_ids:
                if not st_line.analytics_id:
                    raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution on the '%s' statement line!") % (st_line))
        return True
    
account_bank_statement()

class account_bank_statement_line(osv.osv):
    _inherit = "account.bank.statement.line"
    _name = "account.bank.statement.line"
    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }
    
    def create_move_from_st_line(self, cr, uid, st_line_id, company_currency_id, st_line_number, context=None):
        account_move_line_pool = self.pool.get('account.move.line')
        account_bank_statement_line_pool = self.pool.get('account.bank.statement.line')
        st_line = account_bank_statement_line_pool.browse(cr, uid, st_line_id, context=context)
        result = super(account_bank_statement_line,self).create_move_from_st_line(cr, uid, st_line_id, company_currency_id, st_line_number, context=context)
        move = st_line.move_ids and st_line.move_ids[0] or False
        if move:
            for line in move.line_id:
                account_move_line_pool.write(cr, uid, [line.id], {'analytic_distribution_id': st_line.analytic_distribution_id.id}, context=context)
        return result
    
    def button_analytic_distribution(self, cr, uid, ids, context={}):
        # we get the analytical distribution object linked to this line
        distrib_id = False
        statement_line_obj = self.browse(cr, uid, ids[0], context=context)
        amount = statement_line_obj.amount * -1 or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = statement_line_obj.statement_id.journal_id.currency and statement_line_obj.statement_id.journal_id.currency.id or company_currency
        if statement_line_obj.analytic_distribution_id:
            distrib_id = statement_line_obj.analytic_distribution_id.id
        else:
            distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
            newvals={'analytic_distribution_id': distrib_id}
            super(account_bank_statement_line, self).write(cr, uid, ids, newvals, context=context)
        wiz_obj = self.pool.get('wizard.costcenter.distribution')
        wiz_id = wiz_obj.create(cr, uid, {'total_amount': amount, 'distribution_id': distrib_id, 'currency_id': currency}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.costcenter.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_ids': {'cost_center': wiz_id}
               }
        }
        
    def write(self, cr, uid, ids, vals, context=None):
        if 'amount_in' in vals or 'amount_out' in vals:
            #new amount, we remove the distribution
            lines = self.browse(cr, uid, ids, context=context)
            for line in lines:
                self.pool.get('analytic.distribution').unlink(cr, uid, line.analytic_distribution_id.id, context=context)
        return super(account_bank_statement_line, self).write(cr, uid, ids, vals, context=context)
    
account_bank_statement_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
