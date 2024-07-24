#!/usr/bin/env python
# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from decimal_precision import get_precision
from time import strftime
from lxml import etree
from tools.translate import _
from tools.analytic import get_analytic_state


class hr_payroll(osv.osv):
    _name = 'hr.payroll.msf'
    _description = 'Payroll'


    def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get "Third Parties" following other fields
        """
        res = {}
        for line in self.browse(cr, uid, ids):
            if line.employee_id:
                res[line.id] = {'third_parties': 'hr.employee,%s' % line.employee_id.id}
                res[line.id] = 'hr.employee,%s' % line.employee_id.id
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

    def _get_trigger_state_ana(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        fp = [-1]
        cc = [-1]
        dest = [-1]
        for ana_account in self.read(cr, uid, ids, ['category']):
            if ana_account['category'] == 'OC':
                cc.append(ana_account['id'])
            elif ana_account['category'] == 'DEST':
                dest.append(ana_account['id'])
            elif ana_account['category'] == 'FUNDING':
                fp.append(ana_account['id'])
        if len(fp) > 1 or len(cc) > 1 or len(dest) > 1:
            return self.pool.get('hr.payroll.msf').search(cr, uid,
                                                          [('state', '=', 'draft'),
                                                           '|', '|',
                                                           ('funding_pool_id', 'in', fp),
                                                           ('cost_center_id', 'in', cc),
                                                           ('destination_id', 'in', dest)],
                                                          order='NO_ORDER')
        return []

    def _get_trigger_state_account(self, cr, uid, ids, context=None):
        pay_obj = self.pool.get('hr.payroll.msf')
        return pay_obj.search(cr, uid, [('state', '=', 'draft'), ('account_id', 'in', ids)])

    def _get_trigger_state_dest_link(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        to_update = []
        pay_obj = self.pool.get('hr.payroll.msf')
        for dest_link in self.read(cr, uid, ids, ['account_id', 'destination_id', 'funding_pool_ids']):
            to_update += pay_obj.search(cr, uid, [
                ('state', '=', 'draft'),
                ('account_id', '=', dest_link['account_id'][0]),
                ('destination_id', '=', dest_link['destination_id'][0]),
                ('funding_pool_id', 'in', dest_link['funding_pool_ids'])
            ])
        return to_update

    def _get_trigger_state_dest_cc_link(self, cr, uid, ids, context=None):
        """
        Returns the list of Payroll Entries for which the AD state should be re-computed
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        cc_ids = []
        dest_ids = []
        payroll_obj = self.pool.get('hr.payroll.msf')
        for dest_cc_link in self.browse(cr, uid, ids, context=context):
            cc_ids.append(dest_cc_link.cc_id.id)
            dest_ids.append(dest_cc_link.dest_id.id)
        payroll_ids = payroll_obj.search(cr, uid, [('state', '=', 'draft'),
                                                   '|',
                                                   ('cost_center_id', 'in', cc_ids),
                                                   ('destination_id', 'in', dest_ids)], order='NO_ORDER', context=context)
        return payroll_ids

    def _has_third_party(self, cr, uid, ids, name, arg, context=None):
        """
        Returns True if the Payroll entry is linked to either an Employee or a Supplier
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for p in self.browse(cr, uid, ids, fields_to_fetch=['employee_id', 'partner_id'], context=context):
            res[p.id] = False
            if p.employee_id or p.partner_id:
                res[p.id] = True
        return res

    _columns = {
        'date': fields.date(string='Date', required=True, readonly=True),
        'document_date': fields.date(string='Document Date', required=True, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", required=True, readonly=True),
        'period_id': fields.many2one('account.period', string="Period", required=True, readonly=True),
        'employee_id': fields.many2one('hr.employee', string="Employee", readonly=True, ondelete="restrict"),
        'partner_id': fields.many2one('res.partner', string="Partner", readonly=True, ondelete="restrict"),
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True, ondelete="restrict"),
        'employee_id_number': fields.function(_get_employee_identification_id, method=True, type='char', size=255, string='Employee ID', readonly=True),
        'name': fields.char(string='Description', size=255, readonly=True),
        'ref': fields.char(string='Reference', size=255, readonly=True),
        'amount': fields.float(string='Amount', digits_compute=get_precision('Account'), readonly=True),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True, readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('valid', 'Validated')], string="State", required=True, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=False, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'funding_pool_id': fields.many2one('account.analytic.account', string="Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free1_id': fields.many2one('account.analytic.account', string="Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free2_id': fields.many2one('account.analytic.account', string="Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'analytic_state': fields.function(get_analytic_state, type='selection', method=True, readonly=True, string="Distribution State",
                                          selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], help="Give analytic distribution state",
                                          store={
                                              'hr.payroll.msf': (lambda self, cr, uid, ids, c=None: ids, ['account_id', 'cost_center_id', 'funding_pool_id', 'destination_id'], 10),
                                              'account.account': (_get_trigger_state_account, ['user_type_code', 'destination_ids'], 20),
                                              'account.analytic.account': (_get_trigger_state_ana, ['date', 'date_start', 'allow_all_cc',
                                                                                                    'allow_all_cc_with_fp',
                                                                                                    'cost_center_ids', 'select_accounts_only',
                                                                                                    'fp_account_ids',
                                                                                                    'tuple_destination_account_ids'],
                                                                           20),
                                              'account.destination.link': (_get_trigger_state_dest_link, ['account_id', 'destination_id'], 30),
                                              'dest.cc.link': (_get_trigger_state_dest_cc_link,
                                                               ['cc_id', 'dest_id', 'active_from', 'inactive_from'], 40),
                                          }
                                          ),
        'partner_type': fields.function(_get_third_parties, type='reference', method=True, string="Third Parties", readonly=True,
                                        selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee')]),
        'field': fields.char(string='Field', readonly=True, size=255, help="Field this line come from in Homère."),
        'has_third_party': fields.function(_has_third_party, method=True, type='boolean', string='Has a Third Party', store=True, readonly=True),
    }

    _order = 'has_third_party, employee_id, date desc'

    _defaults = {
        'date': lambda *a: strftime('%Y-%m-%d'),
        'document_date': lambda *a: strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Adapts domain for AD fields
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
                field.set('domain', "[('category', '=', 'OC'), ('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
            # Change FP field
            fp_fields = form.xpath('//field[@name="funding_pool_id"]')
            for field in fp_fields:
                field.set('domain', "[('category', '=', 'FUNDING'), ('type', '!=', 'view'), "
                                    "('fp_compatible_with_cc_ids', '=', cost_center_id), "
                                    "('fp_compatible_with_acc_dest_ids', '=', (account_id, destination_id))]")
            # Change Destination field
            dest_fields = form.xpath('//field[@name="destination_id"]')
            for field in dest_fields:
                field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST'), ('destination_ids', '=', account_id)]")
            # Apply changes
            view['arch'] = etree.tostring(form, encoding='unicode')
        return view

    def onchange_destination(self, cr, uid, ids, destination_id=False, funding_pool_id=False, account_id=False):
        return self.pool.get('analytic.distribution').\
            onchange_ad_destination(cr, uid, ids, destination_id=destination_id, funding_pool_id=funding_pool_id, account_id=account_id)

    def create(self, cr, uid, vals, context=None):
        """
        Raise an error if creation don't become from an import or a YAML.
        Add default analytic distribution for those that doesn't have anyone.
        """
        if not context:
            context = {}
        if not context.get('from', False) and not context.get('from') in ['yaml', 'csv_import']:
            raise osv.except_osv(_('Error'), _('You are not able to create payroll entries.'))
        if not vals.get('funding_pool_id', False):
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            if fp_id:
                vals.update({'funding_pool_id': fp_id,})
        return super(osv.osv, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        In the B/S lines change the values of partner_id and employee_id according to the value of the partner_type field
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if context.get('payroll_bs_lines'):
            if 'partner_type' in vals:
                employee_id = False
                partner_id = False
                if vals['partner_type']:
                    p_model, p_id = tuple(vals['partner_type'].split(','))
                    if p_model == 'hr.employee' and p_id:
                        employee_id = p_id
                    elif p_model == 'res.partner' and p_id:
                        partner_id = p_id
                vals.update({'employee_id': employee_id, 'partner_id': partner_id})
        return super(hr_payroll, self).write(cr, uid, ids, vals, context=context)

    def move_to_payroll_bs_lines(self, cr, uid, ids, context=None):
        """
        Checks the AD on the Payroll expense lines and returns a view with the Payroll B/S lines
        """
        if context is None:
            context = {}
        ir_model_obj = self.pool.get('ir.model.data')
        payroll_obj = self.pool.get('hr.payroll.msf')
        line_ids = payroll_obj.search(cr, uid, [('state', '=', 'draft')], order='NO_ORDER', context=context)
        for line in payroll_obj.browse(cr, uid, line_ids, fields_to_fetch=['account_id', 'analytic_state'], context=context):
            if line.account_id.is_analytic_addicted and line.analytic_state != 'valid':
                raise osv.except_osv(_('Warning'), _('Some lines have analytic distribution problems!'))
        view_id = ir_model_obj.get_object_reference(cr, uid, 'msf_homere_interface', 'view_payroll_bs_lines_tree')
        view_id = view_id and view_id[1] or False
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'msf_homere_interface', 'view_hr_payroll_msf_bs_filter')
        search_view_id = search_view_id and search_view_id[1] or False
        domain = [('state', '=', 'draft'), ('account_id.is_analytic_addicted', '=', False)]
        context.update({'payroll_bs_lines': True})
        return {
            'name': _('Payroll B/S lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.msf',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': [search_view_id],
            'context': context,
            'domain': domain,
            'target': 'self',  # don't open a new tab
        }

hr_payroll()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
