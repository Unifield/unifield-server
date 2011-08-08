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

class register_creation_lines(osv.osv_memory):
    _name = 'wizard.register.creation.lines'
    _description = 'Registers to be created'

    _columns = {
        'register_id': fields.many2one("account.bank.statement", string="Register", required=True, readonly=True),
        'currency_id': fields.many2one("res.currency", string="Currency", required=True, readonly=True),
        'register_type': fields.selection([('cash', 'Cash Register'), ('bank', 'Bank Register'), ('cheque', 'Cheque Register')], string="Type"),
        'to_create': fields.boolean("Create it?", help="Tick the box if this register have to be created."),
        'wizard_id': fields.many2one("wizard.register.creation", string="Wizard"),
    }

register_creation_lines()

class register_creation(osv.osv_memory):
    _name = 'wizard.register.creation'
    _description = 'Register creation wizard'

    _columns = {
        'period_id': fields.many2one("account.period", string="Period", required=True, readonly=False),
        'new_register_ids': fields.one2many("wizard.register.creation.lines", 'wizard_id', string="", required=True, readonly=False),
        'state': fields.selection([(), ()], string="State", help="Permits to display Create Register button and list of registers to be created when state is open.")
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def button_confirm_period(self, cr, uid, ids, context={}):
        """
        Update new_register_ids field by put in all register that could be created soon.
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.period_id:
            raise osv.except_osv(_('Error'), _('No period filled in.'))
        self.write(cr, uid, ids, {'state': 'open'}, context=context)
        # Refresh wizard to display changes
        return {
         'type': 'ir.actions.act_window',
         'res_model': 'wizard.register.creation',
         'view_type': 'form',
         'view_mode': 'form',
         'res_id': ids[0],
         'context': context,
         'target': 'new',
        }

register_creation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
