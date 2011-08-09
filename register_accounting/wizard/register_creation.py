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

class register_creation_lines(osv.osv_memory):
    _name = 'wizard.register.creation.lines'
    _description = 'Registers to be created'

    _columns = {
        'currency_id': fields.many2one("res.currency", string="Currency", required=True, readonly=True),
        'register_type': fields.selection([('cash', 'Cash Register'), ('bank', 'Bank Register'), ('cheque', 'Cheque Register')], string="Type"),
        'to_create': fields.boolean("Create it?", help="Tick the box if this register have to be created."),
        'wizard_id': fields.many2one("wizard.register.creation", string="Wizard"),
    }

    _defaults = {
        'to_create': lambda *a: True,
    }

register_creation_lines()

class register_creation(osv.osv_memory):
    _name = 'wizard.register.creation'
    _description = 'Register creation wizard'

    _columns = {
        'period_id': fields.many2one("account.period", string="Period", required=True, readonly=False),
        'new_register_ids': fields.one2many("wizard.register.creation.lines", 'wizard_id', string="", required=True, readonly=False),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open')], string="State", help="Permits to display Create Register button and list of registers to be created when state is open.")
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def previous_register_id(self, cr, uid, period_id, currency_id, register_type, context={}):
        """
        Give the previous register id regarding some criteria:
         - period_id: the period of current register
         - currency_id: currency of the current register
         - register_type: type of register
         - fiscalyear_id: current fiscalyear
        """
        #FIXME : change content of this function
        # Take all journal from a type (journal_ids)
        # Take the previous period
        # Take all bank statement from this currencies and from these journal_ids and from the previous period
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('currency', '=', currency_id), ('type', '=', register_type)], context=context)
        print journal_ids
        return True

    def button_confirm_period(self, cr, uid, ids, context={}):
        """
        Update new_register_ids field by put in all register that could be created soon.
        """
        # Some verification
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.period_id:
            raise osv.except_osv(_('Error'), _('No period filled in.'))
        
        # Prepare some values
        abs_obj = self.pool.get('account.bank.statement')
        curr_obj = self.pool.get('res.currency')
        reg_to_create_obj = self.pool.get('wizard.register.creation.lines')
        period_id = wizard.period_id.id
        reg_type = ['bank', 'cheque', 'cash']
        
        # Search active currencies
        curr_ids = curr_obj.search(cr, uid, [('active', '=', True)], context=context)
        
        # For each currency, do a list of registers that should be created
        register_list = {}
        for curr_id in curr_ids:
            register_list[curr_id] = []
            for r_type in reg_type:
                register_list[curr_id].append(r_type)
        
        # Fill in wizard.register.creation.line
        for currency_id in register_list:
            for reg_type in register_list[currency_id]:
                # Search journals that are in the same type
                journal_ids = self.pool.get('account.journal').search(cr, uid, [('currency', '=', currency_id), ('type', '=', reg_type)])
                if isinstance(journal_ids, (int, long)):
                    journal_ids = [journal_ids]
                current_register_ids = abs_obj.search(cr, uid, [('currency', '=', currency_id), ('period_id', '=', period_id), ('journal_id', 'in', journal_ids)], context=context)
                if not current_register_ids:
                    reg_to_create_obj.create(cr, uid, {'currency_id': currency_id, 'register_type': reg_type, 'wizard_id': wizard.id}, context=context)
        
        # Change state to activate the "Create Registers" confirm button
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

    def button_create_registers(self, cr, uid, ids, context={}):
        """
        Create all selected registers.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context={}
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.new_register_ids:
            raise osv.except_osv(_('Error'), _('There is no lines to create! Please choose another period.'))
        for new_reg in wizard.new_register_ids:
            print new_reg.currency_id.id, new_reg.register_type
            print self.previous_register_id(cr, uid, wizard.period_id.id, new_reg.currency_id.id, new_reg.register_type, context=context)
        return True

register_creation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
