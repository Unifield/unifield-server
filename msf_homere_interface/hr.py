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
from lxml import etree
from tools.translate import _

class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'

    _order = 'name_resource'

    _columns = {
        'employee_type': fields.selection([('', ''), ('local', 'Local Staff'), ('ex', 'Expatriate employee')], string="Type", required=True),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=False, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'homere_codeterrain': fields.char(string='Homere field: codeterrain', size=20, readonly=True, required=False),
        'homere_id_staff': fields.integer(string='Homere field: id_staff', size=10, readonly=True, required=False),
        'homere_id_unique': fields.char(string='Homere field: id_unique', size=42, readonly=True, required=False),
        'gender': fields.selection([('male', 'Male'),('female', 'Female'), ('unknown', 'Unknown')], 'Gender'),
        'private_phone': fields.char(string='Private Phone', size=32),
        'name_resource': fields.related('resource_id', 'name', string="Name", type='char', size=128, store=True),
    }

    _defaults = {
        'employee_type': lambda *a: 'ex',
        'homere_codeterrain': lambda *a: '',
        'homere_id_staff': lambda *a: 0.0,
        'homere_id_unique': lambda *a: '',
        'gender': lambda *a: 'unknown',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Block creation for local staff if no 'from' in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'employee_type' in vals and vals.get('employee_type') == 'local':
            # Raise an error if employee is created manually
            if not context.get('from', False) or context.get('from') not in ['yaml', 'import']:
                raise osv.except_osv(_('Error'), _('You are not allowed to create a local staff! Please use Import to create local staff.'))
            # Raise an error if no cost_center
            if not vals.get('cost_center_id', False):
                raise osv.except_osv(_('Warning'), _('You have to complete Cost Center field before employee creation!'))
        return super(hr_employee, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Block write for local staff if no 'from' in context.
        Allow only analytic distribution changes (cost center, funding pool, free 1 and free 2)
        """
        # Some verifications
        if not context:
            context = {}
        local = False
        ex = False
        allowed = False
        if vals.get('employee_type', False):
            if vals.get('employee_type') == 'local':
                local = True
            elif vals.get('employee_type') == 'ex':
                ex = True
        if context.get('from', False) and context.get('from') in ['yaml', 'import']:
            allowed = True
        # Do not change any field except analytic distribution (if not allowed)
        if not allowed:
            new_vals = {}
            for el in vals:
                if el in ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id']:
                    new_vals.update({el: vals[el],})
            vals = new_vals
        # Raise an error if attempt to change local into expat and expat into local
        for emp in self.browse(cr, uid, ids):
            if emp.employee_type == 'ex' and local and not allowed:
                raise osv.except_osv(_('Error'), _('You are not allowed to change an expatriate to local staff!'))
            if emp.employee_type == 'local' and ex and not allowed:
                raise osv.except_osv(_('Error'), _('You are not allowed to change a local staff to expatriate!'))
            if local or emp.employee_type == 'local':
                if (not emp.cost_center_id and not vals.get('cost_center_id', False)) or (vals.get('cost_center_id') is False):
                    cc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1] or False
                    if not cc_id:
                        raise osv.except_osv(_('Warning'), _('You should give a Cost Center (CC) for local staff! "%s" have no CC!') % (emp.name,))
                    vals.update({'cost_center_id': cc_id})
        return super(hr_employee, self).write(cr, uid, ids, vals, context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete local staff is not allowed except if 'unlink' is in context and its value is 'auto'
        """
        # Some verification
        if not context:
            context = {}
        delete_local_staff = False
        if context.get('unlink', False) and context.get('unlink') == 'auto':
            delete_local_staff = True
        # Browse all employee
        for emp in self.browse(cr, uid, ids):
            if emp.employee_type == 'local' and not delete_local_staff:
                raise osv.except_osv(_('Warning'), _('You are not allowed to delete local staff manually!'))
        return super(hr_employee, self).unlink(cr, uid, ids, context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change funding pool domain in order to include MSF Private fund
        """
        if not context:
            context = {}
        view = super(hr_employee, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        form = etree.fromstring(view['arch'])
        data_obj = self.pool.get('ir.model.data')
        try:
            oc_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        except ValueError:
            oc_id = 0
        # Change OC field
        fields = form.xpath('/' + view_type + '//field[@name="cost_center_id"]')
        for field in fields:
            field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
        # Change FP field
        try:
            fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        fp_fields = form.xpath('/'  + view_type + '//field[@name="funding_pool_id"]')
        for field in fp_fields:
            field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), '|', ('cost_center_ids', '=', cost_center_id), ('id', '=', %s)]" % fp_id)
        view['arch'] = etree.tostring(form)
        return view

    def onchange_cc(self, cr, uid, ids, cost_center_id=False, funding_pool_id=False):
        """
        Update FP or CC regarding both.
        """
        # Prepare some values
        vals = {}
        if not cost_center_id or not funding_pool_id:
            return {}
        if cost_center_id and funding_pool_id:
            fp = self.pool.get('account.analytic.account').browse(cr, uid, funding_pool_id)
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            # Exception for MSF Private Fund
            if funding_pool_id == fp_id:
                return {}
            if cost_center_id not in [x.id for x in fp.cost_center_ids]:
                vals.update({'funding_pool_id': False})
        return {'value': vals}

hr_employee()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
