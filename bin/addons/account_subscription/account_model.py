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
from tools.translate import _

class account_model_line(osv.osv):
    _name = "account.model.line"
    _inherit = "account.model.line"

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the invoice line, then "valid"
         - if no distribution, take a tour of invoice distribution, if compatible, then "valid"
         - if no distribution on invoice line and invoice, then "none"
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
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id, line.model_id.analytic_distribution_id.id, line.account_id.id)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If model has an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for model in self.browse(cr, uid, ids, context=context):
            res[model.id] = True
            if model.analytic_distribution_id:
                res[model.id] = False
        return res

    def _get_is_allocatable(self, cr, uid, ids, name, arg, context=None):
        """
        If analytic-a-holic account, then this account is allocatable.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for model_line in self.browse(cr, uid, ids):
            res[model_line.id] = True
            if model_line.account_id and not model_line.account_id.is_analytic_addicted:
                res[model_line.id] = False
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for model_line in self.browse(cr, uid, ids):
            res[model_line.id] = ''
            if not model_line.is_allocatable:
                continue
            from_header = ''
            if model_line.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            ana_distri_state = self.pool.get('ir.model.fields').get_browse_selection(cr, uid, model_line, 'analytic_distribution_state', context)
            res[model_line.id] = "%s%s" % (ana_distri_state, from_header)
        return res

    def _get_exp_in_line_state(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context=context):
            if line.account_id.user_type.code in ('expense', 'income'):
                if line.have_analytic_distribution_from_header \
                    and not line.model_id.analytic_distribution_id:
                    # line has no AD
                    res[line.id] = 'no_header'
                else:
                    # get line AD state
                    res[line.id] = line.analytic_distribution_state
            else:
                res[line.id] = 'no_exp_in'
        return res

    _columns = {
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')],
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean',
            string='Header Distrib.?'),
        'is_allocatable': fields.function(_get_is_allocatable, method=True, type='boolean', string="Is allocatable?", readonly=True, store=False),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30,
            string="Distribution",
            help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
        'sequence': fields.integer('Sequence', readonly=True, help="The sequence field is used to order the resources from lower sequences to higher ones"),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'exp_in_ad_state': fields.function(_get_exp_in_line_state, method=True, type='selection',
             selection=[('no_exp_in', 'Not expense/income'), ('no_header', 'No header'), ('valid', 'Valid'), ('invalid', 'Invalid')],
             string='Expense/income line status'),  # UFTP-103
    }

    _defaults = {
        'have_analytic_distribution_from_header': lambda *a: True,
        'is_allocatable': lambda *a: True,
        'analytic_distribution_state_recap': lambda *a: '',
    }

    def create(self, cr, uid, vals, context=None):
        model = self.pool.get('account.model').browse(cr, uid, vals['model_id'], context=context)
        # just add the next line
        vals['sequence'] = len(model.lines_id) + 1
        return super(account_model_line, self).create(cr, uid, vals, context=context)

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
        amount = abs(model_line.debit - model_line.credit)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = model_line.model_id and  model_line.model_id.currency_id and  model_line.model_id.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = model_line.analytic_distribution_id and model_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'model_line_id': model_line.id,
            'currency_id': currency or False,
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
                'name': _('Analytic distribution'),
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new model line
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Copy analytic distribution
        model_line = self.browse(cr, uid, [id], context=context)[0]
        if model_line.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, model_line.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_model_line, self).copy_data(cr, uid, id, default, context)

account_model_line()

class account_model(osv.osv):
    _name = "account.model"
    _inherit = "account.model"

    def _has_any_bad_ad_line_exp_in(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for model in self.browse(cr, uid, ids, context=context):
            res[model.id] = False
            for line in model.lines_id:
                if line.exp_in_ad_state and line.exp_in_ad_state in ('no_header', 'invalid'):
                    res[model.id] = True
                    break
        return res

    _columns = {
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'has_any_bad_ad_line_exp_in': fields.function(_has_any_bad_ad_line_exp_in,
             method=True, type='boolean',
             string='Has bad analytic distribution on expense/income lines',
             help='There is lines with expense or income accounts with invalid analytic distribution or using header AD that is not defined or not compatible.'),  # UFTP-103
    }

    _defaults = {
        'currency_id': lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id,
        'has_any_bad_ad_line_exp_in': False,
    }

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
        # UFTP-105: Check that period is open. Otherwise raise an error
        period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
        if not period or period.state != 'draft':
            raise osv.except_osv(_('Warning'), _('This period should be in open state: %s') % (period.name))

        for model in self.browse(cr, uid, ids, context=context):
            try:
                entry['name'] = model.name%{'year':time.strftime('%Y'), 'month':time.strftime('%m'), 'date':time.strftime('%Y-%m')}
            except (KeyError, TypeError, ValueError):
                '''
                Examples of: KeyError => model of the month %(montht)s
                             TypeError => model of the %(month)s/ % (year)s
                             ValueError => model of the month %month)s / model of the month % (month)s
                '''
                raise osv.except_osv(_('Error'), _('Please check the name of the Recurring Model used: %s\n'
                                                   'Only the keys %%(year)s / %%(month)s / %%(date)s can be used '
                                                   'and must be written without spaces.') % model.name)
            except Exception:
                raise osv.except_osv(_('Error'), _('The name of the Recurring Model used is incorrect: %s\n'
                                                   'You can find a list of the formatted strings usable on the Recurring Model form.') % model.name)
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
                if line.account_id.is_analytic_addicted:
                    if line.analytic_distribution_state == 'invalid':
                        raise osv.except_osv(_('Invalid Analytic Distribution !'),_("Please define a valid analytic distribution for the recurring model '%s'!") % (line.name))
                    if not model.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (model.journal_id.name,))
                    if line.analytic_distribution_id:
                        new_distribution_id = ana_obj.copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
                        val.update({'analytic_distribution_id': new_distribution_id})
                    elif model.analytic_distribution_id:
                        new_distribution_id = ana_obj.copy(cr, uid, model.analytic_distribution_id.id, {}, context=context)
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
                    'debit_currency': line.debit, # UF-1535: set this value as the booking currency, and not functional currency
                    'credit_currency': line.credit, # UF-1535: set this value as the booking currency, and not functional currency
                    'account_id': line.account_id.id,
                    'move_id': move_id,
                    'partner_id': line.partner_id.id,
                    'date': context.get('date',time.strftime('%Y-%m-%d')),
                    'document_date': context.get('date',time.strftime('%Y-%m-%d')),
                    'date_maturity': date_maturity,
                    'currency_id': model.currency_id.id,
                    'is_recurring': True,
                })
                c = context.copy()
                c.update({'journal_id': model.journal_id.id,'period_id': period_id})
                account_move_line_obj.create(cr, uid, val, context=c)

        return move_ids

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a model
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        model = self.browse(cr, uid, ids[0], context=context)
        amount = 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = model.currency_id and model.currency_id.id or company_currency
        for line in model.lines_id:
            amount += (line.debit - line.credit)
        amount = abs(amount)
        # Get analytic_distribution_id
        distrib_id = model.analytic_distribution_id and model.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'model_id': model.id,
            'currency_id': currency or False,
            'state': 'dispatch',
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
                'name': _('Global analytic distribution'),
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all recurring lines.
        To do this, just delete the analytic_distribution id link on each recurring line.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        recurring_obj = self.pool.get(self._name + '.line')
        # Search recurring lines
        to_reset = recurring_obj.search(cr, uid, [('model_id', 'in', ids)])
        recurring_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

account_model()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
