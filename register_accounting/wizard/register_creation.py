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
from time import strftime
from ..register_tools import previous_register_id

class register_creation_lines(osv.osv_memory):
    _name = 'wizard.register.creation.lines'
    _description = 'Registers to be created'

    def _get_previous_register_id(self, cr, uid, ids, field_name, arg, context={}):
        """
        Give the previous register for each element
        """
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for el in self.browse(cr, uid, ids, context=context):
            prev_reg_id = previous_register_id(self, cr, uid, el.period_id.id, el.currency_id.id, el.register_type)
            res[el.id] = prev_reg_id
        return res

    _columns = {
        'period_id': fields.many2one('account.period', string='Period', required=True, readonly=True),
        'currency_id': fields.many2one("res.currency", string="Currency", required=True, readonly=True),
        'register_type': fields.selection([('cash', 'Cash Register'), ('bank', 'Bank Register'), ('cheque', 'Cheque Register')], string="Type", readonly=True),
        'to_create': fields.boolean("Create it?", help="Tick the box if this register have to be created."),
        'prev_reg_id':  fields.function(_get_previous_register_id, method=True, type="many2one", relation="account.bank.statement", 
            required=False, readonly=True, string="Previous register", store=False),
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
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open')], string="State", 
            help="Permits to display Create Register button and list of registers to be created when state is open.")
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def button_clear(self, cr, uid, ids, context={}):
        """
        Clear the list of registers to create
        """
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        lines_obj = self.pool.get('wizard.register.creation.lines')
        lines_ids = lines_obj.search(cr, uid, [], context=context)
        lines_obj.unlink(cr, uid, lines_ids)
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)
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
                journal_ids = self.pool.get('account.journal').search(cr, uid, [('currency', '=', currency_id), ('type', '=', reg_type)], 
                    context=context)
                if isinstance(journal_ids, (int, long)):
                    journal_ids = [journal_ids]
                current_register_ids = abs_obj.search(cr, uid, [('currency', '=', currency_id), 
                    ('period_id', '=', period_id), ('journal_id', 'in', journal_ids)], context=context)
                if not current_register_ids:
                    vals = {
                        'period_id': period_id,
                        'currency_id': currency_id,
                        'register_type': reg_type,
                        'wizard_id': wizard.id,
                    }
                    reg_id = reg_to_create_obj.create(cr, uid, vals, context=context)
                    reg = reg_to_create_obj.browse(cr, uid, [reg_id], context=context)[0]
                    if reg_id and not reg.prev_reg_id:
                        reg_to_create_obj.write(cr, uid, [reg_id], {'to_create': False,}, context=context)
        
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
        registers =  []
        curr_time = strftime('%Y-%m-%d')
        j_obj = self.pool.get('account.journal')
        wiz_register_lines_obj = self.pool.get('wizard.register.creation.lines')
        for new_reg in wizard.new_register_ids:
            if new_reg.to_create:
                # Shared values
                reg_vals = {
                    'date': curr_time,
                    'period_id': new_reg.period_id.id,
                }
                if new_reg.prev_reg_id:
                    reg_vals.update({
                        'journal_id': new_reg.prev_reg_id.journal_id.id,
                        'prev_reg_id': new_reg.prev_reg_id.id,
                    })
                    # FIXME: search old caracteristics from previous register
                # Create the register
                reg_id = self.pool.get('account.bank.statement').create(cr, uid, reg_vals, context=context)
                if reg_id:
                    registers.append(reg_id)
                    wiz_register_lines_obj.unlink(cr, uid, [new_reg.id], context=context)
        # Refresh wizard to display changes
        return {
         'type': 'ir.actions.act_window',
         'res_model': 'wizard.register.creation',
         'view_type': 'form',
         'view_mode': 'form',
         'res_id': ids[0],
         'context': context,
         'target': 'new',
         'register_ids': registers,
        }

register_creation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
