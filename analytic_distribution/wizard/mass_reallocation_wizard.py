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

class mass_reallocation_verification_wizard(osv.osv_memory):
    _name = 'mass.reallocation.verification.wizard'
    _description = 'Mass Reallocation Verification Wizard'

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True, readonly=True),
        'error_ids': fields.many2many('account.analytic.line', 'mass_reallocation_error_rel', 'wizard_id', 'analytic_line_id', string="Errors", readonly=True),
        'non_supported_ids': fields.many2many('account.analytic.line', 'mass_reallocation_non_supported_rel', 'wizard_id', 'analytic_line_id', string="Non supported", readonly=True),
        'process_ids': fields.many2many('account.analytic.line', 'mass_reallocation_process_rel', 'wizard_id', 'analytic_line_id', string="To process", readonly=True),
    }

    def button_validate(self, cr, uid, ids, context={}):
        pass

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
            search_ns_ids = self.pool.get('account.analytic.line').search(cr, uid, [('id', 'in', to_process), 
                ('account_id.category', '!=', wiz.account_id.category)], context=context)
            if search_ns_ids:
                non_supported_ids.extend(search_ns_ids)
            # Delete non_supported element from to_process and write them to tmp_process_ids
            tmp_to_process = [x for x in to_process if x not in non_supported_ids]
            if tmp_to_process:
                valid_ids = self.pool.get('account.analytic.line').distribution_is_valid_with_account(cr, uid, tmp_to_process, account_id, context=context)
                process_ids.extend(valid_ids)
                error_ids.extend([x for x in tmp_to_process if x not in valid_ids])
#            if account_type == 'OC':
#                
#            elif account_type == 'FUNDING':
#                pass
#            else:
#                pass
        print "RESULT: %s %s %s" % (error_ids, non_supported_ids, process_ids)
        vals = {'account_id': account_id,}
        if error_ids:
            vals.update({'error_ids': [(6, 0, error_ids)]})
        if non_supported_ids:
            vals.update({'non_supported_ids': [(6, 0, non_supported_ids)]})
        if process_ids:
            vals.update({'process_ids': [(6, 0, process_ids)]})
        verif_id = self.pool.get('mass.reallocation.verification.wizard').create(cr, uid, vals, context=context)
        # Create Mass Reallocation Verification Wizard
        return {
                'name': "Mass Reallocation Wizard Verification Result",
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
