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
import time

class analytic_distribution_wizard(osv.osv_memory):
    _inherit = 'analytic.distribution.wizard'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('draft', 'Draft'), ('cc', 'Cost Center only'), ('dispatch', 'All other elements'), ('done', 'Done'), 
            ('correction', 'Correction')], string="State", required=True, readonly=True),
        'old_account_id': fields.many2one('account.account', "New account given by correction wizard", readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def button_cancel(self, cr, uid, ids, context=None):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(analytic_distribution_wizard, self).button_cancel(cr, uid, ids, context=context)

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Change wizard state in order to use normal method
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change wizard state if current is 'correction'
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.state == 'correction':
                self.write(cr, uid, ids, {'state': 'dispatch'}, context=context)
            if 'from' in context and 'wiz_id' in context:
                # Update cost center lines
                if not self.update_cost_center_lines(cr, uid, wiz.id, context=context):
                    raise osv.except_osv(_('Error'), _('Cost center update failure.'))
                # Do some verifications before writing elements
                self.wizard_verifications(cr, uid, wiz.id, context=context)
                # Verify old account and new account
                account_changed = False
                new_account_id = wiz.account_id and wiz.account_id.id or False
                old_account_id = wiz.old_account_id and wiz.old_account_id.id or False
                if old_account_id != new_account_id:
                    account_changed = True
                # Compare new distribution with old one
                distrib_changed = False
                distrib_id = wiz.distribution_id and wiz.distribution_id.id or False
                for line_type in ['funding.pool', 'free.1', 'free.2']:
                    dbl = self.distrib_lines_to_list(cr, uid, distrib_id, line_type)
                    wizl = self.wizard_lines_to_list(cr, uid, wiz.id, line_type)
                    if not dbl == wizl:
                        distrib_changed = True
                        break
                # After checks, 3 CASES:
                ## 1/ Account AND Distribution have changed
                ## 2/ JUST account have changed
                ## 3/ JUST distribution have changed
                # So:
                ## 1 => Reverse G/L Account as expected and do a COR line. Do changes on analytic distribution and create new distribution then 
                #- linked it to new corrected line.
                ## 2 => Normal correction for G/L Account
                ## 3 => Verify analytic distribution and do changes regarding periods and contracts
                
                # Account AND Distribution have changed
                if account_changed and distrib_changed:
                    # Create new distribution
                    new_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                    self.write(cr, uid, [wiz.id], {'distribution_id': new_distrib_id})
                    for line_type in ['funding.pool', 'free.1', 'free.2']:
                        # Compare and write modifications done on analytic lines
                        type_res = self.compare_and_write_modifications(cr, uid, wiz.id, line_type, context=context)
                    # return account change behaviour with a new analytic distribution
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'), new_distrib_id)
                # JUST Account have changed
                elif account_changed and not distrib_changed:
                    # return normal behaviour with account change
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'))
                # JUST Distribution have changed
                else:
                    pass
        # Get default method
        return super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
