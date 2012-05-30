#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from decimal_precision import get_precision
from time import strftime
from lxml import etree
from tools.translate import _

class hr_payroll(osv.osv):
    _name = 'hr.payroll.msf'
    _description = 'Payroll'

    def _get_analytic_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - all other case are "invalid"
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Search MSF Private Fund element, because it's valid with all accounts
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
            'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        # Browse all given lines to check analytic distribution validity
        ## TO CHECK:
        # A/ if CC = dummy CC
        # B/ if FP = MSF Private FUND
        # C/ (account/DEST) in FP except B
        # D/ CC in FP except when B
        # E/ DEST in list of available DEST in ACCOUNT
        ## CASES where FP is filled in (or not) and/or DEST is filled in (or not).
        ## CC is mandatory, so always available:
        # 1/ no FP, no DEST => Distro = valid
        # 2/ FP, no DEST => Check D except B
        # 3/ no FP, DEST => Check E
        # 4/ FP, DEST => Check C, D except B, E
        ## 
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = 'valid' # by default
            #### SOME CASE WHERE DISTRO IS OK
            # if account is not expense, so it's valid
            if line.account_id and line.account_id.user_type_code and line.account_id.user_type_code != 'expense':
                continue
            # if just a cost center, it's also valid! (CASE 1/)
            if not line.funding_pool_id and not line.destination_id:
                continue
            # if FP is MSF Private Fund and no destination_id, then all is OK.
            if line.funding_pool_id and line.funding_pool_id.id == fp_id and not line.destination_id:
                continue
            #### END OF CASES
            if line.funding_pool_id and not line.destination_id: # CASE 2/
                # D Check, except B check
                if line.cost_center_id.id not in [x.id for x in line.funding_pool_id.cost_center_ids] and line.funding_pool_id.id != fp_id:
                    res[line.id] = 'invalid'
                    continue
            elif not line.funding_pool_id and line.destination_id: # CASE 3/
                # E Check
                account = self.pool.get('account.account').browse(cr, uid, line.account_id.id)
                if line.destination_id.id not in [x.id for x in account.destination_ids]:
                    res[line.id] = 'invalid'
                    continue
            else: # CASE 4/
                # C Check, except B
                if (line.account_id.id, line.destination_id.id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in line.funding_pool_id.tuple_destination_account_ids] and line.funding_pool_id.id != fp_id:
                    res[line.id] = 'invalid'
                    continue
                # D Check, except B check
                if line.cost_center_id.id not in [x.id for x in line.funding_pool_id.cost_center_ids] and line.funding_pool_id.id != fp_id:
                    res[line.id] = 'invalid'
                    continue
                # E Check
                account = self.pool.get('account.account').browse(cr, uid, line.account_id.id)
                if line.destination_id.id not in [x.id for x in account.destination_ids]:
                    res[line.id] = 'invalid'
                    continue
        return res

    def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get "Third Parties" following other fields
        """
        res = {}
        for line in self.browse(cr, uid, ids):
            if line.employee_id:
                res[line.id] = {'third_parties': 'hr.employee,%s' % line.employee_id.id}
                res[line.id] = 'hr.employee,%s' % line.employee_id.id
            elif line.journal_id:
                res[line.id] = 'account.journal,%s' % line.transfer_journal_id.id
            elif line.partner_id:
                res[line.id] = 'res.partner,%s' % line.partner_id.id
            else:
                res[line.id] = False
        return res

    def _get_employee_identification_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get employee identification number if employee id is given
        """
        res = {}
        for line in self.browse(cr, uid, ids):
            res[line.id] = ''
            if line.employee_id:
                res[line.id] = line.employee_id.identification_id
        return res

    _columns = {
        'date': fields.date(string='Date', required=True, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", required=True, readonly=True),
        'period_id': fields.many2one('account.period', string="Period", required=True, readonly=True),
        'employee_id': fields.many2one('hr.employee', string="Employee", readonly=True),
        'partner_id': fields.many2one('res.partner', string="Partner", readonly=True),
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True),
        'employee_id_number': fields.function(_get_employee_identification_id, method=True, type='char', size=255, string='Employee ID', readonly=True),
        'name': fields.char(string='Description', size=255, readonly=True),
        'ref': fields.char(string='Reference', size=255, readonly=True),
        'amount': fields.float(string='Amount', digits_compute=get_precision('Account'), readonly=True),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True, readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('valid', 'Validated')], string="State", required=True, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'analytic_state': fields.function(_get_analytic_state, type='selection', method=True, readonly=True, string="Distribution State",
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], help="Give analytic distribution state"),
        'partner_type': fields.function(_get_third_parties, type='reference', method=True, string="Third Parties", readonly=True,
            selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')]),
        'field': fields.char(string='Field', readonly=True, size=255, help="Field this line come from in Homère."),
    }

    _order = 'employee_id, date desc'

    _defaults = {
        'date': lambda *a: strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change funding pool domain in order to include MSF Private fund
        """
        if not context:
            context = {}
        view = super(hr_payroll, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type in ['tree', 'form']:
            form = etree.fromstring(view['arch'])
            data_obj = self.pool.get('ir.model.data')
            try:
                oc_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
            except ValueError:
                oc_id = 0
            # Change OC field
            fields = form.xpath('//field[@name="cost_center_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
            # Change FP field
            try:
                fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            fp_fields = form.xpath('//field[@name="funding_pool_id"]')
            for field in fp_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', '&', ('cost_center_ids', '=', cost_center_id), '&', ('tuple_destination_account_ids.account_id', '=', account_id), ('tuple_destination_account_ids.destination_id', '=', destination_id), ('id', '=', %s)]" % fp_id)
            # Change Destination field
            dest_fields = form.xpath('//field[@name="destination_id"]')
            for field in dest_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST'), ('destination_ids', '=', account_id)]")
            # Apply changes
            view['arch'] = etree.tostring(form)
        return view

    def create(self, cr, uid, vals, context=None):
        """
        Raise an error if creation don't become from an import or a YAML.
        Add default analytic distribution for those that doesn't have anyone.
        """
        if not context:
            context = {}
        if not context.get('from', False) and not context.get('from') in ['yaml', 'csv_import']:
            raise osv.except_osv(_('Error'), _('You are not able to create payroll entries.'))
        if not vals.get('cost_center_id', False):
            try:
                dummy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1]
            except:
                dummy_id = 0
            if dummy_id:
                vals.update({'cost_center_id': dummy_id,})
        if not vals.get('funding_pool_id', False):
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            if fp_id:
                vals.update({'funding_pool_id': fp_id,})
        return super(osv.osv, self).create(cr, uid, vals, context)

hr_payroll()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
