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

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def _is_aji_corrigible(self, cr, uid, ids, name, args, context=None):
        '''
        Returns True for all AJI corrigible
        '''
        if context is None:
            context = {}
        res = {}

        allow_extra = self.pool.get('res.company').extra_period_config(cr) == 'other'

        for aml in self.browse(cr, uid, ids, context=context):
            res[aml.id] = True
            # note that AJIs linked to JIs on inactive journals are still correctable (US-7563).
            if aml.is_reallocated or aml.is_reversal or aml.journal_type == 'engagement' or \
                    (not allow_extra and aml.real_period_id and aml.real_period_id.special) or \
                    aml.real_period_id and aml.real_period_id.number in (0, 16) or \
                    not aml.move_id or not aml.move_id.is_corrigible:
                res[aml.id] = False
        return res

    _columns = {
        'is_corrigible': fields.function(_is_aji_corrigible, method=True, string='Is corrigible?', type='boolean', readonly=True, store=False),
        'last_corrected_id': fields.many2one('account.analytic.line', string="Last corrected entry", readonly=True, select=1),
    }

    def button_corrections(self, cr, uid, ids, context=None):
        """
        Launch accounting correction wizard to do reverse or correction on selected analytic line.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        upstream_line_ids = []
        downstream_line_ids = []
        # Browse all given lines
        for aml in self.browse(cr, uid, ids, context=context):
            # Get upstream move lines
            line = aml
            new_upstream_line_ids = []
            while line:
                # Add line to result
                new_upstream_line_ids.append(line.id)
                # Add reversal line to result
                new_upstream_line_ids += self.search(cr, uid, [('reversal_origin', '=', line.id), ('is_reversal', '=', True)], context=context)
                line = line.last_corrected_id
            # Get downstream move lines
            sline_ids = [aml.id] + new_upstream_line_ids # Add upstream_line_ids because if more than one correction for a given line. Cf. UTP760 with split lines
            upstream_line_ids += new_upstream_line_ids
            while sline_ids:
                sline_ids = self.search(cr, uid, [('last_corrected_id', 'in', sline_ids)], context=context)
                if sline_ids:
                    # Add line to result
                    downstream_line_ids += sline_ids
                    # Add reversal line to result
                    downstream_line_ids += self.search(cr, uid, [('reversal_origin', 'in', sline_ids), ('is_reversal', '=', True)], context=context)
        return  list(set(upstream_line_ids + downstream_line_ids))

    def button_open_analytic_corrections(self, cr, uid, ids, context=None):
        """
        Open a wizard that contains all analytic lines linked to this one.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, int):
            ids = [ids]

        # Search ids to be open
        domain_ids = self.get_corrections_history(cr, uid, ids, context=context)
        # Create domain
        domain = [('id', 'in', domain_ids)]
        # Update context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
            'display_fp': True,
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
