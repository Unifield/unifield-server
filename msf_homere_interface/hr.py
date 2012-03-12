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

    _columns = {
        'date_from': fields.date(string='Active from'),
        'employee_type': fields.selection([('', ''), ('local', 'Local Staff'), ('ex', 'Expatriate employee')], string="Type", required=True),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'homere_codeterrain': fields.char(string='Homere field: codeterrain', size=20, readonly=True, required=False),
        'homere_id_staff': fields.integer(string='Homere field: id_staff', size=10, readonly=True, required=False),
        'homere_id_unique': fields.char(string='Homere field: id_unique', size=42, readonly=True, required=False),
        'gender': fields.selection([('male', 'Male'),('female', 'Female'), ('unknown', 'Unknown')], 'Gender'),
        'private_phone': fields.char(string='Private Phone', size=32),
    }

    _defaults = {
        'cost_center_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1] or False,
        'employee_type': lambda *a: 'ex',
        'homere_codeterrain': lambda *a: '',
        'homere_id_staff': lambda *a: 0.0,
        'homere_id_unique': lambda *a: '',
        'gender': lambda *a: 'unknown',
    }

    def create(self, cr, uid, vals, context={}):
        """
        Block creation for local staff if no 'from' in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'employee_type' in vals and vals.get('employee_type') == 'local':
            if not context.get('from', False) or context.get('from') not in ['yaml', 'import']:
                raise osv.except_osv(_('Error'), _('You are not allowed to create a local staff! Please use Import to create local staff.'))
        return super(hr_employee, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context={}):
        """
        Block write for local staff if no 'from' in context.
        Allow only analytic distribution changes (cost center, funding pool, free 1 and free 2)
        """
        # Some verifications
        if not context:
            context = {}
        if 'employee_type' in vals and vals.get('employee_type') == 'local':
            if not context.get('from', False) or context.get('from') not in ['yaml', 'import']:
                new_vals = {}
                for el in vals:
                    if el in ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id']:
                        new_vals.update({el: vals[el],})
                vals = new_vals
        return super(hr_employee, self).write(cr, uid, ids, vals, context)

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

hr_employee()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
