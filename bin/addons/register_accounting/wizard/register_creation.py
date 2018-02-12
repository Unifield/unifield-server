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
from ..register_tools import previous_register_instance_id
from ..register_tools import open_register_view
from ..register_tools import previous_period_id

class register_creation_lines(osv.osv_memory):
    _name = 'wizard.register.creation.lines'
    _description = 'Registers to be created'

    def _get_previous_register_id(self, cr, uid, ids, field_name, arg, context=None):
        """
        Give the previous register for each element
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for el in self.browse(cr, uid, ids, context=context):
            prev_reg_id = previous_register_id(self, cr, uid, el.period_id.id, el.journal_id.id)
            res[el.id] = prev_reg_id
        return res

    def _get_previous_register_instance_id(self, cr, uid, ids, field_name, arg, context=None):
        """
        Give the previous register instance for each element
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for el in self.browse(cr, uid, ids, context=context):
            prev_instance_id = previous_register_instance_id(self, cr, uid, el.period_id.id, el.journal_id.id)
            res[el.id] = prev_instance_id
        return res

    _columns = {
        'period_id': fields.many2one('account.period', string='Period', required=True, domain=[('state','=','draft')], readonly=True),
        'currency_id': fields.many2one("res.currency", string="Currency", required=True, readonly=True),
        'journal_id': fields.many2one('account.journal', string="Journal", required=True, readonly=True),
        'register_type': fields.selection([('cash', 'Cash Register'), ('bank', 'Bank Statement'), ('cheque', 'Cheque Register')], string="Type", readonly=True),
        'prev_reg_id':  fields.function(_get_previous_register_id, method=True, type="many2one", relation="account.bank.statement",
                                        required=False, readonly=True, string="Previous register", store=False),
        'wizard_id': fields.many2one("wizard.register.creation", string="Wizard"),
        'prev_instance_id': fields.function(_get_previous_register_instance_id, method=True, type="many2one", relation="msf.instance",
                                            required=False, readonly=True, string="Instance", store=False),
    }

register_creation_lines()

class register_creation(osv.osv_memory):
    _name = 'wizard.register.creation'
    _description = 'Register creation wizard'

    _columns = {
        'period_id': fields.many2one("account.period", string="Period", required=True, readonly=False),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance', required=True, readonly=False),
        'new_register_ids': fields.one2many("wizard.register.creation.lines", 'wizard_id', string="", required=True, readonly=False),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open')], string="State",
                                  help="Permits to display Create Register button and list of registers to be created when state is open.")
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

    def button_clear(self, cr, uid, ids, context=None):
        """
        Clear the list of registers to create
        """
        if not context:
            context = {}
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

    def button_confirm_period(self, cr, uid, ids, context=None):
        """
        Update new_register_ids field by put in all register that could be created soon.
        """
        # Some verification
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.period_id:
            raise osv.except_osv(_('Error'), _('No period filled in.'))

        # Prepare some values
        abs_obj = self.pool.get('account.bank.statement')
        reg_to_create_obj = self.pool.get('wizard.register.creation.lines')
        period_id = wizard.period_id.id
        instance_id = wizard.instance_id.id
        prev_period_id = previous_period_id(self, cr, uid, period_id, context=context)
        reg_type = ['bank', 'cheque', 'cash']

        for rtype in reg_type:
            # Search all register from previous period
            abs_ids = abs_obj.search(cr, uid, [('journal_id.type', '=', rtype), ('period_id', '=', prev_period_id),('instance_id','=', instance_id)], context=context)
            if isinstance(abs_ids, (int, long)):
                abs_ids = [abs_ids]
            # Browse all registers in order to filter those which doesn't have an active currency
            for register in abs_obj.browse(cr, uid, abs_ids, context=context):
                if register.journal_id and register.journal_id.currency and register.journal_id.currency.active:
                    currency_id = register.journal_id.currency.id
                    journal_id = register.journal_id and register.journal_id.id or False
                    # verify that this register is not present in our wizard
                    if not reg_to_create_obj.search(cr, uid, [('period_id', '=', period_id), ('journal_id', '=', journal_id),
                                                              ('wizard_id', '=', wizard.id)], context=context) and not abs_obj.search(cr, uid, [('period_id', '=', period_id),
                                                                                                                                                ('journal_id', '=', journal_id)]):
                        vals = {
                            'period_id': period_id,
                            'currency_id': currency_id,
                            'journal_id': journal_id,
                            'register_type': rtype,
                            'wizard_id': wizard.id,
                        }
                        reg_id = reg_to_create_obj.create(cr, uid, vals, context=context)
                        reg_to_create_obj.browse(cr, uid, [reg_id], context=context)[0]

        # Delete lines that have no previous_register_id or whose previous register is in Draft state
        line_to_create_ids = reg_to_create_obj.search(cr, uid, [('wizard_id', '=', wizard.id)], context=context)
        for line in reg_to_create_obj.browse(cr, uid, line_to_create_ids, context=context):
            if not line.prev_reg_id or line.prev_reg_id.state == 'draft':
                reg_to_create_obj.unlink(cr, uid, [line.id], context=context)

        # Verify that there is some lines to treat
        remaining_lines = reg_to_create_obj.search(cr, uid, [('wizard_id', '=', wizard.id)], context=context)
        if not len(remaining_lines):
            raise osv.except_osv(_('Warning'), _('No register to create. Please verify that previous period have some registers.'))
        else:
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

    def button_create_registers(self, cr, uid, ids, context=None):
        """
        Create all selected registers.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.new_register_ids:
            raise osv.except_osv(_('Error'), _('There is no lines to create! Please choose another period.'))
        registers =  []
        curr_time = strftime('%Y-%m-%d')
        abs_obj = self.pool.get('account.bank.statement')
        wiz_register_lines_obj = self.pool.get('wizard.register.creation.lines')
        for new_reg in wizard.new_register_ids:
            # Shared values
            reg_vals = {
                'date': curr_time,
                'period_id': new_reg.period_id.id,
            }
            prev_reg = new_reg.prev_reg_id
            if prev_reg:
                reg_vals.update({
                    'journal_id': prev_reg.journal_id.id,
                    'prev_reg_id': prev_reg.id,
                    'name': prev_reg.name,
                })

            # Create the register
            reg_id = abs_obj.create(cr, uid, reg_vals, context=context)
            if reg_id:
                registers.append(reg_id)
                wiz_register_lines_obj.unlink(cr, uid, [new_reg.id], context=context)
        if registers:
            abs_obj.log(cr, uid, registers[0], '%s register(s) created for period %s' % (len(registers), wizard.period_id.name))
            return open_register_view(self, cr, uid, registers[0])
        raise osv.except_osv(_('Warning'), _('No registers created!'))

register_creation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
