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
import tools
from tools.translate import _

class account_move_line(osv.osv):
    _inherit = 'account.move.line'

    def _display_analytic_button(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The journal entry state is draft (unposted)
         - The account is an expense account
        """
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = True
            # False if journal entry is posted
            if ml.move_id.state == 'posted':
                res[ml.id] = False
            # False if account not an expense account
            if ml.account_id.user_type.code not in ['expense']:
                res[ml.id] = False
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the move line, then "valid"
         - if no distribution, take a tour of move distribution, if compatible, then "valid"
         - if no distribution on move line and move, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id, line.move_id and line.move_id.analytic_distribution_id and line.move_id.analytic_distribution_id.id or False, line.account_id.id)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If move have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = True
            if ml.analytic_distribution_id:
                res[ml.id] = False
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for ml in self.browse(cr, uid, ids):
            res[ml.id] = ''
            from_header = ''
            if ml.have_analytic_distribution_from_header:
                from_header = ' (from header)'
            res[ml.id] = ml.analytic_distribution_state.capitalize() + from_header
            if ml.account_id and ml.account_id.user_type and ml.account_id.user_type.code != 'expense':
                res[ml.id] = ''
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'display_analytic_button': fields.function(_display_analytic_button, method=True, string='Display analytic button?', type='boolean', readonly=True, 
            help="This informs system that we can display or not an analytic button", store=False),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection', 
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], 
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
         'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', 
            string='Header Distrib.?'),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30, 
            string="Distribution", 
            help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
  }

    def create_analytic_lines(self, cr, uid, ids, context=None):
        """
        Create analytic lines on expense accounts that have an analytical distribution.
        """
        # Some verifications
        if not context:
            context = {}
        acc_ana_line_obj = self.pool.get('account.analytic.line')
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for obj_line in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            amount = obj_line.debit_currency - obj_line.credit_currency
            if obj_line.analytic_distribution_id and obj_line.account_id.user_type_code == 'expense':
                ana_state = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, obj_line.analytic_distribution_id.id, {}, obj_line.account_id.id)
                if ana_state == 'invalid':
                    raise osv.except_osv(_('Warning'), _('Invalid analytic distribution.'))
                if not obj_line.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('Warning'),_("No Analytic Journal! You have to define an analytic journal on the '%s' journal!") % (obj_line.journal_id.name, ))
                distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, obj_line.analytic_distribution_id.id, context=context)
                # create lines
                for distrib_lines in [distrib_obj.funding_pool_lines, distrib_obj.free_1_lines, distrib_obj.free_2_lines]:
                    for distrib_line in distrib_lines:
                        context.update({'date': obj_line.source_date or obj_line.date})
                        anal_amount = distrib_line.percentage*amount/100
                        line_vals = {
                                     'name': obj_line.name,
                                     'date': obj_line.date,
                                     'ref': obj_line.ref,
                                     'journal_id': obj_line.journal_id.analytic_journal_id.id,
                                     'amount': -1 * self.pool.get('res.currency').compute(cr, uid, obj_line.currency_id.id, company_currency, 
                                        anal_amount, round=False, context=context),
                                     'amount_currency': -1 * anal_amount,
                                     'account_id': distrib_line.analytic_id.id,
                                     'general_account_id': obj_line.account_id.id,
                                     'move_id': obj_line.id,
                                     'distribution_id': distrib_obj.id,
                                     'user_id': uid,
                                     'currency_id': obj_line.currency_id.id,
                                     'distrib_line_id': '%s,%s'%(distrib_line._name, distrib_line.id),
                                     'document_date': obj_line.document_date,
                        }
                        # Update values if we come from a funding pool
                        if distrib_line._name == 'funding.pool.distribution.line':
                            destination_id = distrib_line.destination_id and distrib_line.destination_id.id or False
                            line_vals.update({'cost_center_id': distrib_line.cost_center_id and distrib_line.cost_center_id.id or False,
                                'destination_id': destination_id,})
                        # Update value if we come from a write-off
                        if obj_line.is_write_off:
                            line_vals.update({'from_write_off': True,})
                        # Add source_date value for account_move_line that are a correction of another account_move_line
                        if obj_line.corrected_line_id and obj_line.source_date:
                            line_vals.update({'source_date': obj_line.source_date})
                        self.pool.get('account.analytic.line').create(cr, uid, line_vals, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete analytic lines before unlink move lines
        """
        # Search analytic lines
        ana_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', 'in', ids)])
        self.pool.get('account.analytic.line').unlink(cr, uid, ana_ids)
        return super(account_move_line, self).unlink(cr, uid, ids)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an move line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No journal item given. Please save your line before.'))
        # Prepare some values
        ml = self.browse(cr, uid, ids[0], context=context)
        distrib_id = False
        amount = ml.debit_currency - ml.credit_currency
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = ml.currency_id and ml.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = ml and ml.analytic_distribution_id and ml.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'move_line_id': ml.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': ml.account_id and ml.account_id.id or False,
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
                'name': 'Analytic distribution',
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
