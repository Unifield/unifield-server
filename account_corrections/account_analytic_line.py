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
from tools.misc import flatten

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    _columns = {
        'is_corrigible': fields.related('move_id', 'is_corrigible', string='Is correctible?', type="boolean", readonly=True),
        'last_corrected_id': fields.many2one('account.analytic.line', string="Last corrected entry", readonly=True),
    }

    def button_corrections(self, cr, uid, ids, context=None):
        """
        Launch accounting correction wizard to do reverse or correction on selected analytic line.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Retrieve some values
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        al = self.browse(cr, uid, ids[0])
        if not al.move_id:
            raise osv.except_osv(_('Warning'), _('No link to a journal item found!'))
        if not al.move_id.is_corrigible:
            raise osv.except_osv(_('Error'), _('The journal item linked to this analytic line is not correctible!'))
        # Create wizard
        wizard = wiz_obj.create(cr, uid, {'move_line_id': al.move_id.id}, context=context)
        # Change wizard state in order to change date requirement on wizard
        wiz_obj.write(cr, uid, [wizard], {'state': 'open'}, context=context)
        # Update context
        context.update({
            'active_id': al.move_id.id,
            'active_ids': [al.move_id.id],
        })
        # Change context if account special type is "donation"
        if al.move_id.account_id and al.move_id.account_id.type_for_register and al.move_id.account_id.type_for_register == 'donation':
            wiz_obj.write(cr, uid, [wizard], {'from_donation': True}, context=context)
        # Update context to inform wizard we come from a correction wizard
        context.update({'from_correction': True,})
        return {
            'name': _("Accounting Corrections Wizard (from Analytic Journal Items)"),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.journal.items.corrections',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wizard],
            'context': context,
        }

    def get_corrections_history(self, cr, uid, ids, context=None):
        """
        Give for each line their history by using "move_id and reversal_origin" field to browse lines
        Return something like that: 
            {id1: [line_id, another_line_id], id2: [a_line_id, other_line_id]}
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        move_obj = self.pool.get('account.move')
        # Browse all given lines
        for aml in self.browse(cr, uid, ids, context=context):
            upstream_line_ids = []
            downstream_line_ids = []
            # Get upstream move lines
            line = aml
            while line != None:
                if line:
                    # Add line to result
                    upstream_line_ids.append(line.id)
                    # Add reversal line to result
                    reversal_ids = self.search(cr, uid, [('reversal_origin', '=', line.id), ('is_reversal', '=', True)], context=context)
                    if reversal_ids:
                        upstream_line_ids.append(reversal_ids)
                if line.last_corrected_id:
                    line = line.last_corrected_id
                else:
                    line = None
            # Get downstream move lines
            sline_ids = [aml.id]
            while sline_ids != None:
                operator = 'in'
                if len(sline_ids) == 1:
                    operator = '='
                search_ids = self.search(cr, uid, [('last_corrected_id', operator, sline_ids)], context=context)
                if search_ids:
                    # Add line to result
                    downstream_line_ids.append(search_ids)
                    # Add reversal line to result
                    for dl in self.browse(cr, uid, search_ids, context=context):
                        reversal_ids = self.search(cr, uid, [('reversal_origin', '=', dl.id), ('is_reversal', '=', True)], context=context)
                        downstream_line_ids.append(reversal_ids)
                    sline_ids = search_ids
                else:
                    sline_ids = None
            # Add search result to res
            res[str(aml.id)] = list(set(flatten(upstream_line_ids) + flatten(downstream_line_ids))) # downstream_line_ids needs to be simplify with flatten
        return res

    def button_open_analytic_corrections(self, cr, uid, ids, context=None):
        """
        Open a wizard that contains all analytic lines linked to this one.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain_ids = []
        # Search ids to be open
        res_ids = self.get_corrections_history(cr, uid, ids, context=context)
        # For each ids, add elements to the domain
        for el in res_ids:
            domain_ids.append(res_ids[el])
        # If no result, just display selected ids
        if not domain_ids:
            domain_ids = ids
        # Create domain
        domain = [('id', 'in', flatten(domain_ids))]
        # Update context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Display the result
        return {
            'name': "History Analytic Line",
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'target': 'new',
            'view_type': 'form',
            'view_mode': 'tree',
            'context': context,
            'domain': domain,
        }
        return True

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
