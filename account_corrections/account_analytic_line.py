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

    _columns = {
        'is_corrigible': fields.related('move_id', 'is_corrigible', string='Is correctible?', type="boolean", readonly=True),
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

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
