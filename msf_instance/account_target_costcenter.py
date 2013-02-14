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
    
    def _get_target_set(self, cr, uid, ids, field_names=None, arg=None, context=None):
        res = {}
        if context is None:
            context = {}
            
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = False
            if not line.is_target and line.cost_center_id and line.cost_center_id.id:
                set_target_lines = self.search(cr, uid, [('cost_center_id', '=', line.cost_center_id.id),
                                                         ('is_target', '=', 'True')], context=context)
                if len(set_target_lines) > 0:
                    res[line.id] = True
                    
        return res
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance', required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC')], required=True),
        'is_target': fields.boolean('Is target'),
        'is_target_set': fields.function(_get_target_set, method=True, store=False, string="Is Target set?", type="boolean", readonly="True"),
        'parent_id': fields.many2one('account.target.costcenter', 'Parent'),
        'child_ids': fields.one2many('account.target.costcenter', 'parent_id', 'Children'),
    }
    
    _defaults = {
        'is_target': False,
        'parent_id': False,
    }
    
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
        if isinstance(ids, (int, long)):
            ids = [ids]
        # delete lines in instance's children
        lines_to_delete_ids = self.search(cr, uid, [('parent_id', 'in', ids)], context=context)
        if len(lines_to_delete_ids) > 0:
            self.unlink(cr, uid, lines_to_delete_ids, context=context)
        return super(account_target_costcenter, self).unlink(cr, uid, ids, context)
    
account_target_costcenter()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
