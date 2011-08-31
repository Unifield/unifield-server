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

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'corrected': fields.boolean(string="Corrected", readonly=True, help="If true, this line has been corrected by an accounting correction wizard"),
    }

    _defaults = {
        'corrected': lambda *a: False,
    }

    def button_do_accounting_corrections(self, cr, uid, ids, context={}):
        """
        Launch accounting correction wizard to do reverse or correction on selected move line.
        """
        # Verification
        if not context:
            context={}
        # Retrieve some values
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        # Create wizard
        wizard = wiz_obj.create(cr, uid, {'move_line_id': ids[0]}, context=context)
        # Change wizard state in order to change date requirement on wizard
        wiz_obj.write(cr, uid, [wizard], {'state': 'open'}, context=context)
        return {
            'name': "Accounting Corrections Wizard",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.journal.items.corrections',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wizard],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
            }
        }

    def button_open_corrections(self, cr, uid, ids, context={}):
        """
        Open all corrections linked to the given one
        """
        return True

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
