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
from tools.translate import _
from collections import defaultdict

class mass_reallocation_verification_wizard(osv.osv_memory):
    _name = 'mass.reallocation.verification.wizard'
    _description = 'Mass Reallocation Verification Wizard'

    def _get_total(self, cr, uid, ids, field_name, arg, context={}):
        """
        Get total of lines for given field_name
        """
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        # browse elements
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = {'nb_error': len(wiz.error_ids), 'nb_process': len(wiz.process_ids), 'nb_other': len(wiz.other_ids)}
        return res

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True, readonly=True),
        'error_ids': fields.many2many('account.analytic.line', 'mass_reallocation_error_rel', 'wizard_id', 'analytic_line_id', string="Errors", readonly=True),
        'other_ids': fields.many2many('account.analytic.line', 'mass_reallocation_non_supported_rel', 'wizard_id', 'analytic_line_id', string="Non supported", readonly=True),
        'process_ids': fields.many2many('account.analytic.line', 'mass_reallocation_process_rel', 'wizard_id', 'analytic_line_id', string="Allocatable", readonly=True),
        'nb_error': fields.function(_get_total, string="Lines in error", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_process': fields.function(_get_total, string="Allocatable lines", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_other': fields.function(_get_total, string="Excluded lines", type='integer', method=True, store=False, multi="mass_reallocation_check"),
    }

    def button_validate(self, cr, uid, ids, context={}):
        """
        Launch mass reallocation on "process_ids".
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            # If no supporteds_ids, raise an error
            if not wiz.process_ids:
                raise osv.except_osv(_('Error'), _('No lines to be processed.'))
            # Prepare some values
            account_id = wiz.account_id and wiz.account_id.id
            # Sort by distribution
            lines = defaultdict(list)
            for line in wiz.process_ids:
                lines[line.distribution_id.id].append(line)
            # Process each distribution
            for distrib_id in lines:
                for line in lines[distrib_id]:
                    # Update distribution
                    self.pool.get('analytic.distribution').update_distribution_line_account(cr, uid, [distrib_id], [line.account_id.id], account_id, context=context)
                    # Then update analytic line
                    self.pool.get('account.analytic.line').update_account(cr, uid, [x.id for x in lines[distrib_id]], account_id, context=context)
        return {'type': 'ir.actions.act_window_close'}

mass_reallocation_verification_wizard()

class mass_reallocation_wizard(osv.osv_memory):
    _name = 'mass.reallocation.wizard'
    _description = 'Mass Reallocation Wizard'

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True),
        'line_ids': fields.many2many('account.analytic.line', 'mass_reallocation_rel', 'wizard_id', 'analytic_line_id', 
            string="Analytic Journal Items", required=True),
        'state': fields.selection([('normal', 'Normal'), ('blocked', 'Blocked')], string="State", readonly=True),
    }

    _default = {
        'state': lambda *a: 'normal',
    }

    def default_get(self, cr, uid, fields=[], context={}):
        """
        Fetch context active_ids to populate line_ids wizard field
        """
        # Some verifications
        if not context:
            context = {}
        # Default behaviour
        res = super(mass_reallocation_wizard, self).default_get(cr, uid, fields, context=context)
        # Populate line_ids field
        if context.get('active_ids', False) and context.get('active_model', False) == 'account.analytic.line':
            res['line_ids'] = context.get('active_ids')
        return res

    def button_validate(self, cr, uid, ids, context={}):
        """
        Launch mass reallocation process
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        error_ids = []
        non_supported_ids = []
        process_ids = []
        # Browse given wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            to_process = [x.id for x in wiz.line_ids] or []
            account_id = wiz.account_id.id
            # Don't process lines:
            # - that are not from choosen category. For an example it's useless to treat line that have a funding pool if we choose a cost center account.
            # Nevertheless line that have a funding pool line could be indirectally be modified by a change of cost center.
            # - that have same account
            # - that are commitment lines
            # - that have been reallocated
            # - that have been reversed
            # - that come from an engagement journal
            search_ns_ids = self.pool.get('account.analytic.line').search(cr, uid, [('id', 'in', to_process), 
                '|', '|', '|', '|', '|', ('account_id.category', '!=', wiz.account_id.category), ('account_id', '=', account_id),
                ('commitment_line_id', '!=', False), ('is_reallocated', '=', True), ('is_reversal', '=', True), ('journal_id.type', '=', 'engagement')], 
                context=context)
            if search_ns_ids:
                non_supported_ids.extend(search_ns_ids)
            # Delete non_supported element from to_process and write them to tmp_process_ids
            tmp_to_process = [x for x in to_process if x not in non_supported_ids]
            if tmp_to_process:
                valid_ids = self.pool.get('account.analytic.line').check_analytic_account(cr, uid, tmp_to_process, account_id, context=context)
                process_ids.extend(valid_ids)
                error_ids.extend([x for x in tmp_to_process if x not in valid_ids])
        vals = {'account_id': account_id,}
        # Display of elements
        if error_ids:
            vals.update({'error_ids': [(6, 0, error_ids)]})
        if non_supported_ids:
            vals.update({'other_ids': [(6, 0, non_supported_ids)]})
        if process_ids:
            vals.update({'process_ids': [(6, 0, process_ids)]})
        verif_id = self.pool.get('mass.reallocation.verification.wizard').create(cr, uid, vals, context=context)
        # Create Mass Reallocation Verification Wizard
        return {
                'name': "Verification Result",
                'type': 'ir.actions.act_window',
                'res_model': 'mass.reallocation.verification.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [verif_id],
                'context': context,
        }

mass_reallocation_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
