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

class register_creation_lines(osv.osv_memory):
    _name = 'wizard.register.creation.lines'
    _description = 'Registers to be created'

    _columns = {
        'period_id': fields.many2one('account.period', string='Period', required=True, readonly=True),
        'currency_id': fields.many2one("res.currency", string="Currency", required=True, readonly=True),
        'register_type': fields.selection([('cash', 'Cash Register'), ('bank', 'Bank Register'), ('cheque', 'Cheque Register')], string="Type"),
        'to_create': fields.boolean("Create it?", help="Tick the box if this register have to be created."),
        'prev_reg_id': fields.many2one('account.bank.statement', string="Previous register", required=False, readonly=True),
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

    def previous_register_id(self, cr, uid, period_id, currency_id, register_type, context={}):
        """
        Give the previous register id regarding some criteria:
         - period_id: the period of current register
         - currency_id: currency of the current register
         - register_type: type of register
         - fiscalyear_id: current fiscalyear
        """
        # TIP - Use this postgresql query to verify current registers:
        # select s.id, s.state, s.journal_id, j.type, s.period_id, s.name, c.name 
        # from account_bank_statement as s, account_journal as j, res_currency as c 
        # where s.journal_id = j.id and j.currency = c.id;

        # Prepare some values
        p_obj = self.pool.get('account.period')
        j_obj = self.pool.get('account.journal')
        st_obj = self.pool.get('account.bank.statement')
        # Search period and previous one
        period = p_obj.browse(cr, uid, [period_id], context=context)[0]
        first_period_id = p_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id)], order='date_start', limit=1, context=context)[0]
        previous_period_ids = p_obj.search(cr, uid, [('date_start', '<', period.date_start), ('fiscalyear_id', '=', period.fiscalyear_id.id)], 
            order='date_start desc', limit=1, context=context)
        if period_id == first_period_id: 
            # if the current period is the first period of fiscalyear we have to search the last period of previous fiscalyear
            previous_fiscalyear = self.pool.get('account.fiscalyear').search(cr, uid, [('date_start', '<', period.fiscalyear_id.date_start)], 
                limit=1, order="date_start desc", context=context)
            if not previous_fiscalyear:
                raise osv.except_osv(_('Error'), 
                    _('No previous fiscalyear found. Is your period the first one of a fiscalyear that have no previous fiscalyear ?'))
            previous_period_ids = p_obj.search(cr, uid, [('fiscalyear_id', '=', previous_fiscalyear[0])], 
                limit=1, order='date_stop desc, name desc') # this work only for msf because of the last period name which is "Period 13", "Period 14" 
                # and "Period 15"
        # Search journal_ids that have the type we search
        journal_ids = j_obj.search(cr, uid, [('currency', '=', currency_id), ('type', '=', register_type)], context=context)
        previous_reg_ids = st_obj.search(cr, uid, [('journal_id', 'in', journal_ids), ('period_id', '=', previous_period_ids[0])], context=context)
        if len(previous_reg_ids) != 1:
            return False
        return previous_reg_ids[0]

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
                    prev_reg_id = self.previous_register_id(cr, uid, period_id, currency_id, reg_type, context=context)
                    reg_to_create_obj.create(cr, uid, {'period_id': period_id, 'currency_id': currency_id, 'register_type': reg_type, 
                        'prev_reg_id': prev_reg_id,'wizard_id': wizard.id}, context=context)
        
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
                    })
                    # FIXME: search old caracteristics from previous register
                else:
                    # Search journals that have same currency and type
                    j_ids = j_obj.search(cr, uid, [('currency', '=', new_reg.currency_id.id), ('type', '=', new_reg.register_type)], context=context)
                    reg_vals.update({
                        'journal_id': j_ids[0],
                    })
                    # FIXME: what about old caracteristics ?
                # Create the register
                reg_id = self.pool.get('account.bank.statement').create(cr, uid, reg_vals, context=context)
                if reg_id:
                    registers.append(reg_id)
        return { 'type': 'ir.actions.act_window_close', 'register_ids': registers}

register_creation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
