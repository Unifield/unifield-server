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
from tools.translate import _
import logging

class account_period(osv.osv):
    _name = "account.period"
    _inherit = "account.period"
    
    # To avoid issues with existing OpenERP code (account move line for example),
    # the state are:
    #  - 'created' for Draft
    #  - 'draft' for Open
    #  - 'done' for HQ-Closed
    def _get_state(self, cursor, user_id, context=None):
        return (('created','Draft'), \
                ('draft', 'Open'), \
                ('field-closed', 'Field-Closed'), \
                ('mission-closed', 'Mission-Closed'), \
                ('done', 'HQ-Closed'))
    
    def action_set_state(self, cr, uid, ids, context):
        """
        Change period state
        """
        
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # Prepare some elements
        reg_obj = self.pool.get('account.bank.statement')
        sub_obj = self.pool.get('account.subscription.line')
        curr_obj = self.pool.get('res.currency')
        curr_rate_obj = self.pool.get('res.currency.rate')
        inv_obj = self.pool.get('account.invoice')
        
        # Do verifications for draft periods
        for period in self.browse(cr, uid, ids, context=context):
            if period.state == 'draft':
                # first verify that all existent registers for this period are closed
                reg_ids = reg_obj.search(cr, uid, [('period_id', '=', period.id)], context=context)
                for register in reg_obj.browse(cr, uid, reg_ids, context=context):
                    if register.state not in ['confirm']:
                        raise osv.except_osv(_('Warning'), _("The register '%s' is not closed. Please close it before closing period" % register.name))
                # check if subscriptions lines were not created for this period
                sub_ids = sub_obj.search(cr, uid, [('date', '<', period.date_stop), ('move_id', '=', False)], context=context)
                if len(sub_ids) > 0:
                    raise osv.except_osv(_('Warning'), _("Recurring entries were not created for period '%s'. Please create them before closing period" % period.name))
                # then verify that all currencies have a fx rate in this period
                # retrieve currencies for this period (in account_move_lines)
                sql = """SELECT DISTINCT currency_id
                FROM account_move_line
                WHERE period_id = %s""" % period.id
                cr.execute(sql)
                res = [x[0] for x in cr.fetchall()]
                comp_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
                # for each currency do a verification about fx rate
                for id in res:
                    # search for company currency_id if ID is None
                    if id == None or id == comp_curr_id:
                        continue
                    rate_ids = curr_rate_obj.search(cr, uid, [('currency_id', '=', id), ('name', '>=', period.date_start), 
                        ('name', '<=', period.date_stop)], context=context)
                    # if no rate found
                    if not rate_ids:
                        curr_name = curr_obj.read(cr, uid, id, ['name']).get('name', False)
                        raise osv.except_osv(_('Warning'), _("No FX rate found for currency '%s'") % curr_name)
## This block could be reused later
#                # finally check supplier invoice for this period and display those of them that have due date to contened in this period
#                inv_ids = inv_obj.search(cr, uid, [('state', 'in', ['draft', 'open']), ('period_id', '=', period.id), 
#                    ('type', 'in', ['in_invoice', 'in_refund'])], context=context)
#                inv_to_display = []
#                for inv in inv_obj.browse(cr, uid, inv_ids, context=context):
#                    if not inv.date_due or inv.date_due <= period.date_stop:
#                        inv_to_display.append(inv.id)
#                if inv_to_display:
#                    raise osv.except_osv(_('Warning'), _('Some invoices are not paid and have an overdue date. Please verify this with \
#"Open overdue invoice" button and fix the problem.'))
                
                # Display a wizard to inform user all kind of verifications he have to verify in order to close period
                return {
                    'name': "Period closing confirmation wizard",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.confirm.closing.period',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'context':
                    {
                        'active_id': ids[0],
                        'active_ids': ids,
                        'period_id': period.id,
                    }
                }
                
        
        # check if unposted move lines are linked to this period
        move_line_obj = self.pool.get('account.move.line')
        move_lines = move_line_obj.search(cr, uid, [('period_id', 'in', ids)])
        for move_line in move_line_obj.browse(cr, uid, move_lines):
            if move_line.state != 'valid':
                raise osv.except_osv(_('Error !'), _('You cannot close a period containing unbalanced move lines!'))
            

        
        # otherwise, change the period's and journal period's states
        if context['state']:
            state = context['state']
            if state == 'done':
                journal_state = 'done'
            else:
                journal_state = 'draft'
            for id in ids:
                cr.execute('update account_journal_period set state=%s where period_id=%s', (journal_state, id))
                cr.execute('update account_period set state=%s where id=%s', (state, id))
        return True

    _columns = {
        'special': fields.boolean('Opening/Closing Period', size=12,
            help="These periods can overlap.", readonly=True),
        'state': fields.selection(_get_state, 'State', readonly=True,
            help='HQ opens a monthly period. After validation, it will be closed by the different levels.'),
        'number': fields.integer(string="Number for register creation", help="This number informs period's order. Should be between 1 and 15. If 16: have not been defined yet."),
    }

    _order = 'date_start, number'

    def create(self, cr, uid, vals, context={}):
        if not context:
            context = {}

        if context.get('update_mode') in ['init', 'update'] and 'state' not in vals:
            logging.getLogger('init').info('Loading default draft state for account.period')
            vals['state'] = 'draft'

        return super(account_period, self).create(cr, uid, vals, context=context)

    _defaults = {
        'state': lambda *a: 'created',
        'number': lambda *a: 16, # Because of 15 period in MSF, no period would use 16 number.
    }

    def button_overdue_invoice(self, cr, uid, ids, context={}):
        """
        Open a view that display overdue invoices for this period
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # Prepare some values
        inv_obj = self.pool.get('account.invoice')
        
        # Search invoices
        for period in self.browse(cr, uid, ids, context=context):
            inv_ids = inv_obj.search(cr, uid, [('state', 'in', ['draft', 'open']), ('period_id', '=', period.id), 
                ('type', 'in', ['in_invoice', 'in_refund'])], context=context)
            inv_to_display = []
            for inv in inv_obj.browse(cr, uid, inv_ids, context=context):
                if not inv.date_due or inv.date_due <= period.date_stop:
                    inv_to_display.append(inv.id)
            if inv_to_display:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_tree')
                view_id = view_id and view_id[1] or False
                domain = [('id', 'in', inv_to_display)]
                # this context cancel default context of account.action_account_period_tree given by account_period_closing_level_view.xml 
                #+ @line 81 in action_account_period_closing_level_tree
                context = {'search_default_draft': 0}
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.invoice',
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'view_id': [view_id],
                    'target': 'new',
                    'domain': domain,
                    'context': context,
                }

account_period()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
