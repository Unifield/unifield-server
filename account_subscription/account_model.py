#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools.translate import _

class account_model_line(osv.osv):
    _name = "account.model.line"
    _inherit = "account.model.line"
    
    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'account_user_type_code': fields.related('account_id', 'user_type_code', type="char", string="Account User Type Code", store=False)
    }
    
    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No model line given. Please save your model line before.'))
        model_line = self.browse(cr, uid, ids[0], context=context)
        distrib_id = False
        amount = abs(model_line.debit - model_line.credit)
        currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        # Get analytic distribution id from this line
        distrib_id = model_line.analytic_distribution_id and model_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'model_line_id': model_line.id,
            'currency_id': currency,
            'state': 'dispatch',
            'account_id': model_line.account_id.id,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }
    
account_model_line()

class account_model(osv.osv):
    _name = "account.model"
    _inherit = "account.model"
    
    # @@@override@account.account_model.generate()
    def generate(self, cr, uid, ids, datas={}, context=None):
        move_ids = []
        entry = {}
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        pt_obj = self.pool.get('account.payment.term')
        ana_obj = self.pool.get('analytic.distribution')

        if context is None:
            context = {}

        if datas.get('date', False):
            context.update({'date': datas['date']})

        period_id = self.pool.get('account.period').find(cr, uid, dt=context.get('date', False))
        if not period_id:
            raise osv.except_osv(_('No period found !'), _('Unable to find a valid period !'))
        period_id = period_id[0]

        for model in self.browse(cr, uid, ids, context=context):
            entry['name'] = model.name%{'year':time.strftime('%Y'), 'month':time.strftime('%m'), 'date':time.strftime('%Y-%m')}
            move_id = account_move_obj.create(cr, uid, {
                'ref': entry['name'],
                'period_id': period_id,
                'journal_id': model.journal_id.id,
                'date': context.get('date',time.strftime('%Y-%m-%d'))
            })
            move_ids.append(move_id)
            for line in model.lines_id:
                val = {
                    'move_id': move_id,
                    'journal_id': model.journal_id.id,
                    'period_id': period_id,
                }
                if line.account_id.user_type_code == 'expense':
                    if not line.analytic_distribution_id:
                        raise osv.except_osv(_('No Analytic Distribution !'),_("You have to define an analytic distribution on the '%s' line!") % (line.name))
                    if not model.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (model.journal_id.name,))
                    new_distribution_id = ana_obj.copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
                    val.update({'analytic_distribution_id': new_distribution_id})
                    
                date_maturity = time.strftime('%Y-%m-%d')
                if line.date_maturity == 'partner':
                    if not line.partner_id:
                        raise osv.except_osv(_('Error !'), _("Maturity date of entry line generated by model line '%s' of model '%s' is based on partner payment term!" \
                                                                "\nPlease define partner on it!")%(line.name, model.name))
                    if line.partner_id.property_payment_term:
                        payment_term_id = line.partner_id.property_payment_term.id
                        pterm_list = pt_obj.compute(cr, uid, payment_term_id, value=1, date_ref=date_maturity)
                        if pterm_list:
                            pterm_list = [l[0] for l in pterm_list]
                            pterm_list.sort()
                            date_maturity = pterm_list[-1]

                val.update({
                    'name': line.name,
                    'quantity': line.quantity,
                    'debit': line.debit,
                    'credit': line.credit,
                    'account_id': line.account_id.id,
                    'move_id': move_id,
                    'partner_id': line.partner_id.id,
                    'date': context.get('date',time.strftime('%Y-%m-%d')),
                    'date_maturity': date_maturity
                })
                c = context.copy()
                c.update({'journal_id': model.journal_id.id,'period_id': period_id})
                account_move_line_obj.create(cr, uid, val, context=c)

        return move_ids

account_model()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
