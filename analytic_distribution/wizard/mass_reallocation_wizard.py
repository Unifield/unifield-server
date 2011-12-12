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

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True, readonly=True),
        'error_ids': fields.many2many('account.analytic.line', 'mass_reallocation_error_rel', 'wizard_id', 'analytic_line_id', string="Errors", readonly=True),
        'supported_ids': fields.many2many('account.analytic.line', 'mass_reallocation_supported_rel', 'wizard_id', 'analytic_line_id', string="Supported", readonly=True),
        'process_ids': fields.many2many('account.analytic.line', 'mass_reallocation_process_rel', 'wizard_id', 'analytic_line_id', string="To process", readonly=True),
    }

    def button_validate(self, cr, uid, ids, context={}):
        """
        Launch mass reallocation on "supported_ids".
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            # If no supporteds_ids, raise an error
            if not wiz.supported_ids:
                raise osv.except_osv(_('Error'), _('No lines to be processed.'))
            # Prepare some values
            account_id = wiz.account_id and wiz.account_id.id
            # Sort by distribution
            lines = defaultdict(list)
            for line in wiz.supported_ids:
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
            # Don't process lines that are not from choosen category. For an example it's useless to treat line that have a funding pool if we choose a cost center account.
            # Nevertheless line that have a funding pool line could be indirectally be modified by a change of cost center.
            search_ns_ids = self.pool.get('account.analytic.line').search(cr, uid, [('id', 'in', to_process), 
                ('account_id.category', '!=', wiz.account_id.category)], context=context)
            if search_ns_ids:
                non_supported_ids.extend(search_ns_ids)
            # Search line that have same account as given account_id (useless to treat a line that already have the given account)
            same_account_ids = self.pool.get('account.analytic.line').search(cr, uid, [('id', 'in', to_process), 
                ('account_id', '=', account_id)], context=context)
            if same_account_ids:
                non_supported_ids.extend(same_account_ids)
            # Delete non_supported element from to_process and write them to tmp_process_ids
            tmp_to_process = [x for x in to_process if x not in non_supported_ids]
            if tmp_to_process:
                valid_ids = self.pool.get('account.analytic.line').check_analytic_account(cr, uid, tmp_to_process, account_id, context=context)
                process_ids.extend(valid_ids)
                error_ids.extend([x for x in tmp_to_process if x not in valid_ids])
        print "RESULT: ERR, %s NS, %s PROC, %s" % (error_ids, non_supported_ids, process_ids)
        vals = {'account_id': account_id,}
        # Display of elements. Non supported should be inserted into some one. If process_ids not null, then include them into.
        if error_ids and not process_ids:
            vals.update({'error_ids': [(6, 0, error_ids + non_supported_ids)]})
        elif error_ids:
            vals.update({'error_ids': [(6, 0, error_ids)]})
        if non_supported_ids and process_ids:
            vals.update({'process_ids': [(6, 0, non_supported_ids + process_ids)], 'supported_ids': [(6, 0, process_ids)]})
        elif process_ids:
            vals.update({'process_ids': [(6, 0, process_ids)], 'supported_ids': [(6, 0, process_ids)]})
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
