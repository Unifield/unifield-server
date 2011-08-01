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
from operator import itemgetter
from register_tools import _get_third_parties
from register_tools import _set_third_parties

class account_move_line(osv.osv):
    _name = "account.move.line"
    _inherit = "account.move.line"

    _columns = {
        'register_id': fields.many2one("account.account", "Register"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
            multi="third_parties_key"),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'third_parties': fields.function(_get_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')], 
            help="To use for python code when registering", multi="third_parties_key"),
        'supplier_invoice_ref': fields.related('invoice', 'name', type='char', size=64, string="Supplier inv.ref.", store=False),
        'from_import_invoice': fields.boolean('Come from an Import Invoices wizard'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have those from account_statement_from_invoice_lines (in case where account_statement_from_invoice is used)
        """
        if context is None:
            context = {}
        if 'from' in context:
            if context.get('from') == 'wizard_import_invoice':
                view_name = 'invoice_from_registers_tree'
                if view_type == 'search':
                    view_name = 'invoice_from_registers_search'
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', view_name)
                if view:
                    view_id = view[1]
        result = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return result

    def onchange_account_id(self, cr, uid, ids, account_id=False, third_party=False):
        """
        Update some values and do this if a partner_id is given
        """
        # @@@override account.account_move_line.onchange_account_id
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        fiscal_pos_obj = self.pool.get('account.fiscal.position')
        val = {}
        if isinstance(account_id, (list, tuple)):
            account_id = account_id[0]

        # Add partner_id variable in order to the function to works
        partner_id = False
        if third_party:
            third_vals = third_party.split(",")
            if third_vals[0] == "res.partner":
                partner_id = third_vals[1]
        # end of add
        if account_id:
            res = account_obj.browse(cr, uid, account_id)
            tax_ids = res.tax_ids
            if tax_ids and partner_id:
                part = partner_obj.browse(cr, uid, partner_id)
                tax_id = fiscal_pos_obj.map_tax(cr, uid, part and part.property_account_position or False, tax_ids)[0]
            else:
                tax_id = tax_ids and tax_ids[0].id or False
            val['account_tax_id'] = tax_id
        # @@@end

        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner')]
        third_required = False
        third_selection = 'res.partner,0'
        domain = {'partner_type': []}
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            account = acc_obj.browse(cr, uid, [account_id])[0]
            acc_type = account.type_for_register
            # if the account is a payable account, then we change the domain
            if acc_type == 'partner':
                if account.type == "payable":
                    domain = {'partner_type': [('property_account_payable', '=', account_id)]}
                elif account.type == "receivable":
                    domain = {'partner_type': [('property_account_receivable', '=', account_id)]}

            if acc_type == 'transfer':
                third_type = [('account.bank.statement', 'Register')]
                third_required = True
                third_selection = 'account.bank.statement,0'
                domain = {'partner_type': [('state', '=', 'open')]}
            elif acc_type == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
        val.update({'partner_type_mandatory': third_required, 'partner_type': {'options': third_type, 'selection': third_selection}})
        return {'value': val, 'domain': domain}

    def onchange_partner_type(self, cr, uid, ids, partner_type=None, credit=None, debit=None, context={}):
        """
        Give the right account_id according partner_type and third parties choosed
        """
        ## TO BE FIXED listgrid.py
        if isinstance(partner_type, dict):
            partner_type = partner_type.get('selection')
        return self.pool.get('account.bank.statement.line').onchange_partner_type(cr, uid, ids, partner_type, credit, debit, context=context)

account_move_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
