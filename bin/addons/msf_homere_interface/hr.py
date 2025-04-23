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
from msf_field_access_rights.osv_override import _get_instance_level
import time

class hr_payment_method(osv.osv):
    _name = 'hr.payment.method'
    _description = 'Payment Method'
    _columns = {
        'name': fields.char(size=128, string='Name', required=True, select=1),
    }

    _order = 'name'

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'The payment method name must be unique.')
    ]

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(hr_payment_method, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            if _get_instance_level(self, cr, uid) == 'hq':
                root = etree.fromstring(result['arch'])
                root.set('editable', 'top')
                root.set('hide_new_button', '0')
                root.set('hide_edit_button', '0')
                root.set('hide_delete_button', '0')
                result['arch'] = etree.tostring(root, encoding='unicode')
        return result

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if 'name' in vals and not context.get('sync_update_execution'):
            existing_ids = self.search(cr, uid, [('id', 'in', ids), ('name', '!=', vals['name'])])
            if existing_ids and self.pool.get('hr.employee').search(cr, uid, [('active', 'in', ['t', 'f']), ('payment_method_id', 'in', existing_ids)]):
                raise osv.except_osv(_('Error'), _("You can't change a payment method used at least in one employee"))

        return super(hr_payment_method, self).write(cr, uid, ids, vals, context=context)
hr_payment_method()


class hr_employee(osv.osv):
    _name = 'hr.employee'
    _inherit = 'hr.employee'
    _rec_name = 'name_resource'

    _order = 'name_resource'

    def _get_allow_edition(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        For given ids get True or False regarding payroll system configuration (activated or not).
        If payroll_ok is True, so don't permit Local employee edition.
        Otherwise permit user to edit them.
        """
        if not context:
            context = {}
        res = {}
        allowed = False
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup and not setup.payroll_ok:
            allowed = True
        for e in ids:
            res[e] = allowed
        return res

    def _get_ex_allow_edition(self, cr, uid, ids, field_name=None, arg=None,
                              context=None):
        """
        US-94 do not allow to modify an already set identification id for expat
        """
        res = {}
        if not ids:
            return res

        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for self_br in self.browse(cr, uid, ids, context=context):
            can_edit = True
            if self_br.employee_type == 'ex' and self_br.identification_id:
                can_edit = False
            res[self_br.id] = can_edit
        return res

    def onchange_type(self, cr, uid, ids, e_type=None, context=None):
        """
        Update allow_edition field when changing employee_type
        """
        res = {}
        if not context:
            context = {}
        if not e_type:
            return res
        elif e_type == 'local':
            if not 'value' in res:
                res['value'] = {}
            allowed = False
            setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
            if setup and not setup.payroll_ok:
                allowed = True
            res['value'].update({'allow_edition': allowed,})
        return res

    _columns = {
        'employee_type': fields.selection([('', ''), ('local', 'Local Staff'), ('ex', 'Expatriate employee')], string="Type", required=True, select=1),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=False, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'homere_codeterrain': fields.char(string='Homere field: codeterrain', size=20, readonly=True, required=False),
        'homere_id_staff': fields.integer(string='Homere field: id_staff', size=10, readonly=True, required=False, select=1),
        'homere_id_unique': fields.char(string='Homere field: id_unique', size=42, readonly=True, required=False, select=1),
        'homere_uuid_key': fields.char(string='Homere UUID', size=64, readonly=True, required=False, select=1),
        'gender': fields.selection([('male', 'Male'),('female', 'Female'), ('unknown', 'Unknown')], 'Gender'),
        'private_phone': fields.char(string='Private Phone', size=32),
        'name_resource': fields.related('resource_id', 'name', string="Name", type='char', size=128, store=True, write_relate=False),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'allow_edition': fields.function(_get_allow_edition, method=True, type='boolean', store=False, string="Allow local employee edition?", readonly=True),
        'photo': fields.binary('Photo', readonly=True),
        'ex_allow_edition': fields.function(_get_ex_allow_edition, method=True, type='boolean', store=False, string="Allow expat employee edition?", readonly=True),
        'payment_method_id': fields.many2one('hr.payment.method', string='Payment Method', required=False, ondelete='restrict'),
        'bank_name': fields.char('Bank Name', size=256, required=False),
        'bank_account_number': fields.char('Bank Account Number', size=128, required=False),
        'instance_creator': fields.char('Instance creator of the employee', size=64, readonly=1),
        'expat_creation_date': fields.date('Creation Date', readonly=1),
        'former_identification_id': fields.char('Former ID', size=32, readonly=1, help='Used for the OCP migration', select=1),
        'workday_identification_id': fields.char('Workday ID', size=32, readonly=1, help='Used for the OCP migration', select=1),
    }

    _defaults = {
        'employee_type': lambda *a: 'ex',
        'homere_codeterrain': lambda *a: '',
        'homere_id_staff': lambda *a: 0.0,
        'homere_id_unique': lambda *a: '',
        'gender': lambda *a: 'unknown',
        'ex_allow_edition': lambda *a: True,
        'expat_creation_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def _set_sync_update_as_run(self, cr, uid, data, sdref, context=None):
        if not data.get('identification_id') or not data.get('name'):
            return False

        employee_name = data['name'].strip()
        employee_id = data['identification_id']
        existing_id = self.find_sd_ref(cr, uid, sdref)
        if not existing_id:
            # never run, but exists with the same id and name => ignore
            if self.search_exist(cr, uid, [('identification_id', '=', employee_id), ('name', '=', employee_name)]):
                return True

        else:
            same_ids = self.search(cr, uid, [('identification_id', '=', employee_id), ('name', '=', employee_name)])
            if same_ids and existing_id not in same_ids:
                # Run on the instance but has a different Employee ID (identification_id) than on the one run on the instance
                return True

        return False



    def _check_unicity(self, cr, uid, ids, context=None):
        """
        Check that identification_id is not used yet.
        """
        # Some verifications
        if not context:
            context = {}
        # Search if no one use this identification_id
        for e in self.browse(cr, uid, ids):
            if e.identification_id:
                same = self.search(cr, uid, [('identification_id', '=', e.identification_id)])
                if same and len(same) > 1:
                    same_data = self.read(cr, uid, same, ['name'])
                    names = [e.name]
                    for employee in same_data:
                        employee_name = employee.get('name', False)
                        if employee_name and employee_name not in names:
                            names.append(employee_name)
                    raise osv.except_osv(_('Error'), _('Several employees have the same Identification No "%s": %s') %
                                         (e.identification_id, ' ; '.join(names)))
                    return False
        return True

    _constraints = [
        (_check_unicity, "Another employee has the same Identification No.", ['identification_id']),
    ]

    def _check_employee_cc_compatibility(self, cr, uid, employee_id, context=None):
        """
        Raises an error in case the employee "Destination and Cost Center" or "Funding Pool and Cost Center" are not compatible.
        """
        if context is None:
            context = {}
        ad_obj = self.pool.get('analytic.distribution')
        employee_fields = ['destination_id', 'cost_center_id', 'funding_pool_id', 'name_resource']
        employee = self.browse(cr, uid, employee_id, fields_to_fetch=employee_fields, context=context)
        emp_dest = employee.destination_id
        emp_cc = employee.cost_center_id
        emp_fp = employee.funding_pool_id
        if emp_dest and emp_cc:
            if not ad_obj.check_dest_cc_compatibility(cr, uid, emp_dest.id, emp_cc.id, context=context):
                raise osv.except_osv(_('Error'), _('Employee %s: the Cost Center %s is not compatible with the Destination %s.') %
                                     (employee.name_resource, emp_cc.code or '', emp_dest.code or ''))
        if emp_fp and emp_cc:
            if not ad_obj.check_fp_cc_compatibility(cr, uid, emp_fp.id, emp_cc.id, context=context):
                raise osv.except_osv(_('Error'), _('Employee %s: the Cost Center %s is not compatible with the Funding Pool %s.') %
                                     (employee.name_resource, emp_cc.code or '', emp_fp.code or ''))

    def create(self, cr, uid, vals, context=None):
        """
        Block creation for local staff if no 'from' in context
        Remove space in the beginning and end of employee name
        """
        # Some verifications
        if not context:
            context = {}
        if not context.get('sync_update_execution') and not vals.get('instance_creator'):
            c = self.pool.get('res.users').browse(cr, uid, uid).company_id
            instance_code = c and c.instance_id and c.instance_id.code

            if instance_code:
                vals['instance_creator'] = instance_code

        if vals.get('name'):
            vals['name'] = vals['name'].strip()
        if vals.get('identification_id', False) and vals.get('employee_type', False) == 'ex':
            vals['identification_id'] = vals['identification_id'].strip()
        if vals.get('job_name', False):
            vals['job_name'] = vals['job_name'].strip()
        if vals.get('employee_type') == 'local':
            vals['section_code'] = False
        allow_edition = False
        if 'employee_type' in vals and vals.get('employee_type') == 'local':
            # Search Payroll functionnality preference (activated or not)
            # If payroll_ok is False, then we permit user to create local employees
            setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
            if setup and not setup.payroll_ok:
                allow_edition = True
            # Raise an error if employee is created manually
            if (not context.get('from', False) or context.get('from') not in ['yaml', 'import']) and not context.get('sync_update_execution', False) and not allow_edition:
                raise osv.except_osv(_('Error'), _('You are not allowed to create a local staff! Please use Import to create local staff.'))
        if vals.get('job_id', False):
            job_obj = self.pool.get('hr.job')
            job = job_obj.browse(cr, uid, vals['job_id'], fields_to_fetch=['name'])
            vals['job_name'] = job and job.name
        employee_id = super(hr_employee, self).create(cr, uid, vals, context)
        self._check_employee_cc_compatibility(cr, uid, employee_id, context=context)
        return employee_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Block write for local staff if no 'from' in context.
        Allow only analytic distribution changes (cost center, funding pool, free 1 and free 2)
        Remove space in the beginning and end of employee name
        """
        if not ids:
            return True
        elif isinstance(ids, int):
            ids = [ids]
        # Some verifications
        if not context:
            context = {}

        if 'instance_creator' in vals:
            del(vals['instance_creator'])

        # Prepare some values
        local = False
        ex = False
        allowed = False
        res = []
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup and not setup.payroll_ok:
            allowed = True
        # Prepare some variable for process
        if vals.get('name'):
            vals['name'] = vals['name'].strip()
        if vals.get('job_name', False):
            vals['job_name'] = vals['job_name'].strip()
        if vals.get('identification_id', False) and vals.get('employee_type', False) == 'ex':
            vals['identification_id'] = vals['identification_id'].strip()
        if vals.get('employee_type', False):
            if vals.get('employee_type') == 'local':
                local = True
                vals['section_code'] = False
            elif vals.get('employee_type') == 'ex':
                ex = True
        if (context.get('from', False) and context.get('from') in ['yaml', 'import']) or context.get('sync_update_execution', False):
            allowed = True
            if vals.get('job_id', False):
                job_obj = self.pool.get('hr.job')
                job = job_obj.browse(cr, uid, vals['job_id'], fields_to_fetch=['name'])
                vals['job_name'] = job and job.name
        # Browse all employees
        for emp in self.browse(cr, uid, ids):
            new_vals = dict(vals)
            # Raise an error if attempt to change local into expat and expat into local
            if emp.employee_type == 'ex' and local and not allowed:
                raise osv.except_osv(_('Error'), _('You are not allowed to change an expatriate to local staff!'))
            if emp.employee_type == 'local' and ex and not allowed:
                raise osv.except_osv(_('Error'), _('You are not allowed to change a local staff to expatriate!'))
            # Do some modifications for local employees
            if local or emp.employee_type == 'local':
                # Do not change any field except analytic distribution (if not allowed)
                for el in vals:
                    if el in ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id']:
                        new_vals.update({el: vals[el]})
            # Write changes
            employee_id = super(hr_employee, self).write(cr, uid, emp.id, new_vals, context)
            if employee_id:
                res.append(employee_id)
            updated_emp = self.browse(cr, uid, emp.id, fields_to_fetch=['active'], context=context)
            if updated_emp and updated_emp.active:
                self._check_employee_cc_compatibility(cr, uid, emp.id, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete local staff is not allowed except if:
        - 'unlink' is in context and its value is 'auto'
        - Payroll functionnality have been DESactivated
        """
        # Some verification
        if not context:
            context = {}
        delete_local_staff = False
        allowed = False
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup and not setup.payroll_ok:
            allowed = True
        if (context.get('unlink', False) and context.get('unlink') == 'auto') or allowed:
            delete_local_staff = True
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if not setup_id.payroll_ok:
            delete_local_staff = True
        # Browse all employee
        for emp in self.browse(cr, uid, ids):
            if emp.employee_type == 'local' and (not delete_local_staff or not allowed):
                raise osv.except_osv(_('Warning'), _('You are not allowed to delete local staff manually!'))
        return super(hr_employee, self).unlink(cr, uid, ids, context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Adapts domain for AD fields
        """
        if not context:
            context = {}
        view = super(hr_employee, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if self.pool.get('res.company')._get_instance_oc(cr, uid) == 'ocp':
            found = False
            view_xml = etree.fromstring(view['arch'])
            for field in view_xml.xpath('//field[@name="section_code"]'):
                found = True
                field.set('invisible', "0")
            if found:
                view['arch'] = etree.tostring(view_xml, encoding='unicode')

        if view_type in ['form', 'tree']:
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
            # Change DEST field
            dest_fields = form.xpath('/' + view_type + '//field[@name="destination_id"]')
            for dest_field in dest_fields:
                dest_field.set('domain', "[('category', '=', 'DEST'), ('type', '!=', 'view'), "
                                         "('dest_compatible_with_cc_ids', '=', cost_center_id)]")
            # Change FP field
            fp_fields = form.xpath('/' + view_type + '//field[@name="funding_pool_id"]')
            for field in fp_fields:
                field.set('domain', "[('category', '=', 'FUNDING'), ('type', '!=', 'view'), "
                                    "('fp_compatible_with_cc_ids', '=', cost_center_id)]")
            view['arch'] = etree.tostring(form, encoding='unicode')
        return view

    def onchange_cc(self, cr, uid, ids, cost_center_id=False, funding_pool_id=False):
        return self.pool.get('analytic.distribution').\
            onchange_ad_cost_center(cr, uid, ids, cost_center_id=cost_center_id, funding_pool_id=funding_pool_id)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):

        if not args:
            args = []
        if context is None:
            context = {}
        # US_262: add disrupt in search
        # If disrupt is not define don't block inactive
        disrupt = False
        if context.get('disrupt_inactive', True):
            disrupt = True

        if not disrupt:
            if ('active', '=', False) not in args \
               and ('active', '=', True) not in args:
                args += [('active', '=', True)]
        return super(hr_employee, self).search(cr, uid, args, offset=offset,
                                               limit=limit, order=order,
                                               context=context, count=count)

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if context is None:
            context={}
        # UTP-441: only see active employee execept if args also contains a search on 'active' field
        disrupt = False
        if context.get('disrupt_inactive', False) and context.get('disrupt_inactive') == True:
            disrupt = True
        if not disrupt:
            if not ('active', '=', False) or not ('active', '=', True) in args:
                args += [('active', '=', True)]

        return super(hr_employee, self).name_search(cr, uid, name, args, operator, context, limit)

    def auto_import(self, cr, uid, file_to_import, context=None):
        import base64
        import os
        processed = []
        rejected = []
        headers = []

        import_obj = self.pool.get('hr.expat.employee.import')
        import_id = import_obj.create(cr, uid, {
            'file': base64.b64encode(open(file_to_import, 'rb').read()),
            'filename': os.path.split(file_to_import)[1],
        })
        processed, rejected, headers = import_obj.button_validate(cr, uid, [import_id], auto_import=True)
        return processed, rejected, headers

    def update_exported_fields(self, cr, uid, fields):
        res = super(hr_employee, self).update_exported_fields(cr, uid, fields)
        if res:
            res += [
                ['company_id', _('Company')],
                ['instance_creator', _('Instance creator of the employee')]
            ]
        return res

hr_employee()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
