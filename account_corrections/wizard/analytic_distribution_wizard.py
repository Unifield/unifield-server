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
from tools.translate import _
import time
from collections import defaultdict
from tools.misc import flatten

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

    def _check_lines(self, cr, uid, distribution_line_id, wiz_line_id, type):
        """
        Check components compatibility
        """
        # Prepare some values
        wiz_line_types = {'cost.center': '', 'funding.pool': 'fp', 'free.1': 'f1', 'free.2': 'f2',}
        obj = '.'.join([type, 'distribution', 'line'])
        oline = self.pool.get(obj).browse(cr, uid, distribution_line_id)
        nline_type = '.'.join([wiz_line_types.get(type), 'lines'])
        nline_obj = '.'.join(['analytic.distribution.wizard', nline_type])
        nline = self.pool.get(nline_obj).browse(cr, uid, wiz_line_id)
        to_reverse = []
        to_override = defaultdict(list)
        period = nline.wizard_id and nline.wizard_id.move_line_id and nline.wizard_id.move_line_id.period_id or False
        if not period:
            raise osv.except_osv(_('Error'), _('No attached period to the correction wizard. Do you come from a correction wizard attached to a journal item?'))
        # Some cases
        if type == 'funding.pool':
            old_component = [oline.destination_id.id, oline.analytic_id.id, oline.cost_center_id.id, oline.percentage]
            new_component = [nline.destination_id.id, nline.analytic_id.id, nline.cost_center_id.id, nline.percentage]
            if old_component != new_component:
                # Don't do anything if the old FP account is on a soft/hard closed contract!
                if oline.analytic_id.id != nline.analytic_id.id:
                    check_fp = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [oline.analytic_id.id])
                    if check_fp and oline.analytic_id.id in check_fp:
                        return False, _("Old funding pool is on a soft/hard closed contract: %s") % (oline.analytic_id.code,), to_reverse, to_override
                    to_override[oline.id].append(('account_id', nline.analytic_id.id))
                # Override CC on open period, otherwise reverse line
                if oline.cost_center_id.id != nline.cost_center_id.id:
                    # if period is open, do an override, except if FP needs to reverse the line
                    if period.state != 'done' and oline.id not in to_reverse:
                        to_override[oline.id].append(('cost_center_id', nline.cost_center_id.id))
                    elif period.state == 'done':
                        to_reverse.append(oline.id)
                # Only reverse line if destination have changed
                if oline.destination_id.id != nline.destination_id.id:
                    if period.state != 'done' and oline.id not in to_reverse:
                        to_override[oline.id].append(('destination_id', nline.destination_id.id))
                    elif period.state == 'done':
                        to_reverse.append(oline.id)
                # Override line if percentage have changed
                if oline.percentage != nline.percentage and oline.id not in to_reverse:
                    to_override[oline.id].append(('percentage', nline.percentage))
                # Check that if old_component and new_component have changed we should find oline.id in to_reverse OR to_override
                if oline.id not in to_override and oline.id not in to_reverse:
                    raise osv.except_osv(_('Error'), _('Code error: A case have not been taken.'))
        else:
            old_component = [oline.analytic_id.id, oline.percentage]
            new_component = [nline.analytic_id.id, nline.percentage]
            if old_component != new_component:
                field_name = ''
                value = None
                if oline.analytic_id.id != nline.analytic_id.id:
                    field_name = 'account_id'
                    value = nline.analytic_id.id
                if oline.percentage != nline.percentage:
                    field_name = 'percentage'
                    value = nline.percentage
                if not value:
                    raise osv.except_osv(_('Error'), _('A value is missing.'))
                to_override[oline.id].append((field_name, value))
        # Delete lines that are in override if they are in to_reverse
        if oline.id in to_override and oline.id in to_reverse:
            del to_override[oline.id]
        return True, _("All is OK."), to_reverse, to_override

    def do_analytic_distribution_changes(self, cr, uid, wizard_id, distrib_id):
        """
        For each given wizard compare old (distrib_id) and new analytic distribution. Then adapt analytic lines.
        """
        # Prepare some values
        wiz_line_types = {'cost.center': '', 'funding.pool': 'fp', 'free.1': 'f1', 'free.2': 'f2',}
        wizard = self.browse(cr, uid, wizard_id)
        to_update  = [] # NEEDED for analytic lines to be updated with new analytic distribution after its creation
        # Fetch funding pool lines, free 1 lines and free 2 lines

        company_currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        current_date = time.strftime('%Y-%m-%d')
        ml = wizard.move_line_id

        orig_date = ml.source_date or ml.date
        # OK let's go on funding pool lines
        # Search old line and new lines
        old_line_ids = self.pool.get('funding.pool.distribution.line').search(cr, uid, [('distribution_id', '=', distrib_id)])
        wiz_line_ids = self.pool.get('analytic.distribution.wizard.fp.lines').search(cr, uid, [('wizard_id', '=', wizard_id), ('type', '=', 'funding.pool')])
        to_create = []
        to_override = []
        to_delete = []
        to_reverse = []
        old_line_ok = []
        period_closed = ml.period_id.state == 'done'

        for wiz_line in self.pool.get('analytic.distribution.wizard.fp.lines').browse(cr, uid, wiz_line_ids):
            if not wiz_line.distribution_line_id or wiz_line.distribution_line_id.id not in old_line_ids:
                # new distribution line
                #if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [wiz_line.analytic_id.id]):
                #    raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(wiz_line.analytic_id.code))
                to_create.append(wiz_line)
            else:
                old_line = self.pool.get('funding.pool.distribution.line').browse(cr, uid, wiz_line.distribution_line_id.id)
                # existing line, test modifications
                if old_line.analytic_id.id != wiz_line.analytic_id.id \
                    or old_line.percentage != wiz_line.percentage:
                    # FP account changed or % modified
                    if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [old_line.analytic_id.id]):
                        raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(old_line.analytic_id.code))

                if (old_line.cost_center_id.id != wiz_line.cost_center_id.id or
                        old_line.destination_id.id != wiz_line.destination_id.id or
                        old_line.percentage != wiz_line.percentage):
                    if period_closed:
                        to_reverse.append(wiz_line)
                    else:
                        to_override.append(wiz_line)
                elif old_line.analytic_id.id != wiz_line.analytic_id.id:
                    to_override.append(wiz_line)

                old_line_ok.append(old_line.id)

        for wiz_line in self.pool.get('funding.pool.distribution.line').browse(cr, uid, [x for x in old_line_ids if x not in old_line_ok]):
            # distribution line deleted by user
            if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [wiz_line.analytic_id.id]):
                raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(wiz_line.analytic_id.code))
            if period_closed:
                # reverse the line
                to_reverse_ids = self.pool.get('account.analytic.line').search(cr, uid, [('distrib_line_id', '=', wiz_line.id), ('line_type', '=', 'fp')])
                self.pool.get('account.analytic.line').unlink(cr, uid, to_reverse_ids)
                # delete the distribution line
                wiz_line.unlink()
            else:
                to_delete.append(wiz_line)
        print period_closed
        print 'to_create', to_create
        print 'to_over', to_override
        print 'to_delete', to_delete
        print 'to_reverse', to_reverse
        print 'old_line_ok', old_line_ok

        for line in to_create:
            # create the new distrib line
            new_distrib_line = self.pool.get('funding.pool.distribution.line').create(cr, uid, {
                    'analytic_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'percentage': line.percentage,
                    'destination_id': line.destination_id.id,
                    'distribution_id': distrib_id,
                    'currency_id': ml.currency_id.id,
                })
            # create the ana line
            self.pool.get('funding.pool.distribution.line').create_analytic_lines(cr, uid, [new_distrib_line], ml.id, date=wizard.date, source_date=orig_date)

        for line in to_delete:
            # delete distrib line
            self.pool.get('funding.pool.distribution.line').unlink(cr, uid, [line.id])
            # delete associated analytic line
            to_delete_ids = self.pool.get('account.analytic.line').search(cr, uid, [('distrib_line_id', '=', line.id), ('line_type', '=', 'fp')])
            self.pool.get('account.analytic.line').unlink(cr, uid, to_delete_ids)

        for line in to_reverse:
            # reverse the line
            to_reverse_ids = self.pool.get('account.analytic.line').search(cr, uid, [('distrib_line_id', '=', line.distribution_line_id.id), ('line_type', '=', 'fp'), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
            self.pool.get('account.analytic.line').reverse(cr, uid, to_reverse_ids)
            # Mark old lines as non reallocatable (ana_ids): why reverse() don't set this flag ?
            self.pool.get('account.analytic.line').write(cr, uid, to_reverse_ids, {'is_reallocated': True,})
            # update the distrib line
            name = False
            if to_reverse_ids:
                ana_line_obj = self.pool.get('account.analytic.line')
                name = ana_line_obj.join_without_redundancy(ana_line_obj.read(cr, uid, to_reverse_ids[0], ['name'])['name'], 'COR')
            self.pool.get('funding.pool.distribution.line').write(cr, uid, [line.distribution_line_id.id], {
                    'analytic_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'percentage': line.percentage,
                    'destination_id': line.destination_id.id,
                })
            # Create the new ana line
            self.pool.get('funding.pool.distribution.line').create_analytic_lines(cr, uid, line.distribution_line_id.id, ml.id, date=wizard.date, source_date=orig_date, name=name)

        for line in to_override:
            # update the ana line
            to_override_ids = self.pool.get('account.analytic.line').search(cr, uid, [('distrib_line_id', '=', line.distribution_line_id.id), ('line_type', '=', 'fp'), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
            ctx = {'date': orig_date}
            amount_cur = (ml.credit_currency - ml.debit_currency) * line.percentage / 100
            amount = self.pool.get('res.currency').compute(cr, uid, ml.currency_id.id, company_currency_id, amount_cur, round=False, context=ctx)
            self.pool.get('account.analytic.line').write(cr, uid, to_override_ids, {
                    'account_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'destination_id': line.destination_id.id,
                    'amount_currency': amount_cur,
                    'amount': amount,
                    'date': wizard.date,
                    'source_date': orig_date,
                })
            # update the distib line
            self.pool.get('funding.pool.distribution.line').write(cr, uid, [line.distribution_line_id.id], {
                    'analytic_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'percentage': line.percentage,
                    'destination_id': line.destination_id.id
                })

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

                # Account AND/OR Distribution have changed
                if account_changed:
                    # Create new distribution
                    new_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                    self.write(cr, uid, [wiz.id], {'distribution_id': new_distrib_id})
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'), distrib_id=new_distrib_id)
                # JUST Distribution have changed
                else:
                    # Check all lines to proceed to changes
                    self.do_analytic_distribution_changes(cr, uid, wiz.id, wiz.distribution_id.id)
                    return {'type': 'ir.actions.act_window_close'}
        # Get default method
        return super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
