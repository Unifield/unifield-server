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

    def _get_analytic_state(self, cr, uid, ids, name, args, context={}):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - if no distribution on the line, then "none"
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
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = 'invalid'
            if line.cost_center_id and line.funding_pool_id:
                if line.funding_pool_id.id == fp_id:
                    res[line.id] = 'valid'
                    continue
                if line.account_id.id in [x.id for x in line.funding_pool_id.account_ids] and line.cost_center_id.id in [x.id for x in line.funding_pool_id.cost_center_ids]:
                    res[line.id] = 'valid'
                    continue
            elif line.cost_center_id and not line.funding_pool_id:
                res[line.id] = 'valid'
                continue
            else:
                res[line.id] = 'none'
        return res

    def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context={}):
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

    def _get_employee_identification_id(self, cr, uid, ids, field_name=None, arg=None, context={}):
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
        'analytic_state': fields.function(_get_analytic_state, type='selection', method=True, readonly=True, string="Distribution State",
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], help="Give analytic distribution state"),
        'partner_type': fields.function(_get_third_parties, type='reference', method=True, string="Third Parties", readonly=True,
            selection=[('res.partner', 'Partner'), ('account.journal', 'Journal'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')]),
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
        if view_type == 'tree':
            form = etree.fromstring(view['arch'])
            data_obj = self.pool.get('ir.model.data')
            try:
                oc_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
            except ValueError:
                oc_id = 0
            # Change OC field
            fields = form.xpath('/tree//field[@name="cost_center_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
            # Change FP field
            try:
                fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            fp_fields = form.xpath('/tree//field[@name="funding_pool_id"]')
            for field in fp_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), '|', '&', ('cost_center_ids', '=', cost_center_id), ('account_ids', '=', account_id), ('id', '=', %s)]" % fp_id)
            view['arch'] = etree.tostring(form)
        return view

    def create(self, cr, uid, vals, context={}):
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
            except:
                fp_id = 0
            if fp_id:
                vals.update({'funding_pool_id': fp_id,})
        return super(osv.osv, self).create(cr, uid, vals, context)

hr_payroll()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
