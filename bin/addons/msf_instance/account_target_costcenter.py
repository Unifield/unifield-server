# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv

class account_target_costcenter(osv.osv):
    _name = 'account.target.costcenter'
    _rec_name = 'cost_center_id'
    _trace = True

    def _get_cost_center_code(self, cr, uid, ids, name, args, context=None):
        """
        Returns a dict with key = target Cost Center id, and value = related Cost Center code.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for target_cc in self.browse(cr, uid, ids, fields_to_fetch=['cost_center_id'], context=context):
            res[target_cc.id] = target_cc.cost_center_id.code or ''
        return res

    def _get_target_cc_to_update(self, cr, uid, analytic_acc_ids, context=None):
        """
        Returns the list of target CC for which the CC code should be updated.
        """
        if context is None:
            context = {}
        if isinstance(analytic_acc_ids, int):
            analytic_acc_ids = [analytic_acc_ids]
        return self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', 'in', analytic_acc_ids)],
                                                                 order='NO_ORDER', context=context)

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance', required=True, select=1),
        'cost_center_id': fields.many2one('account.analytic.account', 'Code', domain=[('category', '=', 'OC')], required=True, select=1),
        'cost_center_code': fields.function(_get_cost_center_code, method=True, string="Code", type='char', size=24, readonly=True,
                                            store={
                                                'account.analytic.account': (_get_target_cc_to_update, ['code'], 10),
                                                'account.target.costcenter': (lambda self, cr, uid, ids, c=None: ids, ['cost_center_id'], 20),
                                            }),
        'cost_center_name': fields.related('cost_center_id', 'name', string="Name", readonly=True, type="text"),
        'cost_center_status': fields.related('cost_center_id', 'filter_active', string="Is_Active", readonly=True, type="boolean"),
        'is_target': fields.boolean('Is target', select=1),
        'is_top_cost_center': fields.boolean('Top cost centre for budget consolidation'),
        'is_po_fo_cost_center': fields.boolean('Cost centre picked for PO/FO reference'),
        'parent_id': fields.many2one('account.target.costcenter', 'Parent'),
        'child_ids': fields.one2many('account.target.costcenter', 'parent_id', 'Children'),
    }

    _defaults = {
        'is_target': False,
        'is_top_cost_center': False,
        'is_po_fo_cost_center': False,
        'parent_id': False,
    }

    def _check_target(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('cost_center_id', '=', line.cost_center_id.id),('is_target', '=', True)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_top_cost_center(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('cost_center_id', '=', line.cost_center_id.id),('is_top_cost_center', '=', True)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_top_cost_center_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('instance_id', '=', line.instance_id.id),('is_top_cost_center', '=', True)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_po_fo_cost_center(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('cost_center_id', '=', line.cost_center_id.id),('is_po_fo_cost_center', '=', True)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_po_fo_cost_center_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('instance_id', '=', line.instance_id.id),('is_po_fo_cost_center', '=', True)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_target, 'This cost centre is already defined as target in another proprietary instance.', ['is_target', 'cost_center_id', 'instance_id']),
        (_check_top_cost_center, 'This cost centre is already defined as the budget consolidation in another proprietary instance.', ['is_top_cost_center', 'cost_center_id', 'instance_id']),
        (_check_top_cost_center_unicity, 'Another cost centre is already defined as the budget consolidation in this proprietary instance.', ['is_top_cost_center', 'cost_center_id', 'instance_id']),
        (_check_po_fo_cost_center, 'This cost centre is already defined as the PO/FO reference in another proprietary instance.', ['is_po_fo_cost_center', 'cost_center_id', 'instance_id']),
        (_check_po_fo_cost_center_unicity, 'Another cost centre is already defined as the PO/FO reference in this proprietary instance.', ['is_po_fo_cost_center', 'cost_center_id', 'instance_id']),
    ]

    def create(self, cr, uid, vals, context={}):
        res_id = super(account_target_costcenter, self).create(cr, uid, vals, context=context)
        # create lines in instance's children
        if 'instance_id' in vals:
            instance = self.pool.get('msf.instance').browse(cr, uid, vals['instance_id'], context=context)
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
            if instance and instance.child_ids and current_instance.level == 'section':
                for child in instance.child_ids:
                    self.create(cr, uid, {'instance_id': child.id,
                                          'cost_center_id': vals['cost_center_id'],
                                          'is_target': False,
                                          'parent_id': res_id})
        return res_id

    def unlink(self, cr, uid, ids, context={}):
        if isinstance(ids, int):
            ids = [ids]
        # delete lines in instance's children
        lines_to_delete_ids = self.search(cr, uid, [('parent_id', 'in', ids)], context=context)
        if len(lines_to_delete_ids) > 0:
            self.unlink(cr, uid, lines_to_delete_ids, context=context)
        return super(account_target_costcenter, self).unlink(cr, uid, ids, context)

account_target_costcenter()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
