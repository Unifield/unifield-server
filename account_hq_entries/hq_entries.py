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

class hq_entries_validation_wizard(osv.osv_memory):
    _name = 'hq.entries.validation.wizard'

    def create_move(self, cr, uid, ids):
        """
        Create a move with given hq entries lines
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = False
        if ids:
            # prepare some values
            current_date = strftime('%Y-%m-%d')
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hq')])
            if not journal_ids:
                raise osv.except_osv(_('Warning'), _('No HQ journal found!'))
            journal_id = journal_ids[0]
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, current_date)
            if not period_ids:
                raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (current_date,))
            if len(period_ids) > 1:
                raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % (current_date,))
            period_id = period_ids[0]
            # create move
            move_id = self.pool.get('account.move').create(cr, uid, {
                'date': current_date,
                'journal_id': journal_id,
                'period_id': period_id,
            })
            total_amount = 0
            for line in self.pool.get('hq.entries').read(cr, uid, ids, ['account_id', 'period_id', 'analytic_id', 'cost_center_id', 'date', 
                'free_1_id', 'free_2_id', 'currency_id', 'name']):
                # create new distribution (only for expense accounts)
                distrib_id = False
                cc_id = line.get('cost_center_id', False) and line.get('cost_center_id')[0] or False
                fp_id = line.get('analytic_id', False) and line.get('analytic_id')[0] or False
                f1_id = line.get('free1_id', False) and line.get('free1_id')[0] or False
                f2_id = line.get('free2_id', False) and line.get('free2_id')[0] or False
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                if distrib_id:
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': line.get('currency_id', False) and line.get('currency_id')[0] or False,
                        'percentage': 100.0,
                        'date': line.get('date', False) or current_date,
                        'source_date': line.get('date', False) or current_date,
                    }
                    common_vals.update({'analytic_id': cc_id,})
                    cc_res = self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': fp_id, 'cost_center_id': cc_id,})
                    fp_res = self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    del common_vals['cost_center_id']
                    if f1_id:
                        common_vals.update({'analytic_id': f1_id,})
                        self.pool.get('free.1.distribution.line').create(cr, uid, common_vals)
                    if f2_id:
                        common_vals.update({'analytic_id': f2_id})
                        self.pool.get('free.2.distribution.line').create(cr, uid, common_vals)
                vals = {
                    'account_id': line.get('account_id', False) and line.get('account_id')[0] or False,
                    'period_id': line.get('period_id', False) and line.get('period_id')[0] or False,
                    'journal_id': journal_id,
                    'date': line.get('date'),
                    'move_id': move_id,
                    'analytic_distribution_id': distrib_id,
                    'name': line.get('name', ''),
                }
                self.pool.get('account.move.line').create(cr, uid, vals, context={}, check=False)
                # total_amount += line.get('amount')
            # FIXME: write an account move line with total_amount
            # Post move
            post = self.pool.get('account.move').post(cr, uid, [move_id])
            if post:
                res = True
        return res

    def validate(self, cr, uid, ids, context={}):
        """
        Validate all given lines (in context)
        """
        # Some verifications
        if not context or not context.get('active_ids', False):
            return False
        active_ids = context.get('active_ids')
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        # Tag active_ids as user validated
        to_write = []
        for line in self.pool.get('hq.entries').browse(cr, uid, active_ids, context=context):
            if not line.user_validated:
                if line.account_id.id != line.account_id_first_value.id or line.cost_center_id.id != line.cost_center_id_first_value.id \
                    or line.analytic_id.id != line.analytic_id_first_value.id:
                    self.create_move(cr, uid, line.id)
                    self.pool.get('hq.entries').write(cr, uid, [line.id], {'user_validated': True}, context=context)
                    continue
                to_write.append(line.id)
        # Write lines and validate them
        write = self.create_move(cr, uid, to_write)
        if write:
            self.pool.get('hq.entries').write(cr, uid, to_write, {'user_validated': True}, context=context)
        # Return HQ Entries Tree View in current view
        action_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'action_hq_entries_tree')
        res = self.pool.get('ir.actions.act_window').read(cr, uid, action_id[1], [], context=context)
        res['target'] = 'crush'
        return res

hq_entries_validation_wizard()

class hq_entries(osv.osv):
    _name = 'hq.entries'
    _description = 'HQ Entries'

    _columns = {
        'account_id': fields.many2one('account.account', "Account", required=True),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", required=True),
        'analytic_id': fields.many2one('account.analytic.account', "Funding Pool", required=True),
        'free_1_id': fields.many2one('account.analytic.account', "Free 1"),
        'free_2_id': fields.many2one('account.analytic.account', "Free 2"),
        'user_validated': fields.boolean("User validated?", help="Is this line validated by a user in a OpenERP field instance?", readonly=True),
        'date': fields.date("Posting Date", readonly=True),
        'partner_id': fields.many2one("res.partner", "Third Party", readonly=True),
        'period_id': fields.many2one("account.period", "Period", readonly=True),
        'name': fields.char('Description', size=255, readonly=True),
        'currency_id': fields.many2one('res.currency', "Book. Currency", required=True, readonly=True),
        'amount': fields.float('Amount', readonly=True),
        'account_id_first_value': fields.many2one('account.account', "Account @import", required=True, readonly=True),
        'cost_center_id_first_value': fields.many2one('account.analytic.account', "Cost Center @import", required=True, readonly=True),
        'analytic_id_first_value': fields.many2one('account.analytic.account', "Funding Pool @import", required=True, readonly=True),
    }

    _defaults = {
        'user_validated': lambda *a: False,
        'amount': lambda *a: 0.0,
    }

hq_entries()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
