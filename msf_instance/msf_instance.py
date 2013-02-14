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

class msf_instance(osv.osv):
    _name = 'msf.instance'
    
    _columns = {
        'level': fields.selection([('section', 'Section'),
                                   ('coordo', 'Coordo'),
                                   ('project', 'Project')], 'Level', required=True),
        'code': fields.char('Code', size=64, required=True),
        'mission': fields.char('Mission', size=64),
        'instance': fields.char('Instance', size=64),
        #'parent_id': fields.many2one('msf.instance', 'Parent', domain=[('level', '!=', 'project'), ('state', '=', 'active')]),
        'parent_id': fields.many2one('msf.instance', 'Parent', domain=[('level', '!=', 'project') ]),
        'child_ids': fields.one2many('msf.instance', 'parent_id', 'Children'),
        'name': fields.char('Name', size=64, required=True),
        'note': fields.char('Note', size=256),
        'top_budget_cost_center_id': fields.many2one('account.analytic.account', 'Top consolidated cost center'),
        'target_cost_center_ids': fields.one2many('account.target.costcenter', 'instance_id', 'Target Cost Centers'),
        'state': fields.selection([('draft', 'Draft'),
                                   ('active', 'Active'),
                                   ('inactive', 'Inactive')], 'State', required=True),
        'move_prefix': fields.char('Account move prefix', size=5, required=True),
        'reconcile_prefix': fields.char('Reconcilation prefix', size=2, required=True),
    }
    
    _defaults = {
        'state': 'draft',
    }

    def button_cost_center_wizard(self, cr, uid, ids, context=None):
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': "Add Cost Centers",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.add.cost.centers',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'context': context,
        }

    def create(self, cr, uid, vals, context=None):
        return osv.osv.create(self, cr, uid, vals, context=context)

    def _check_name_code_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('|'),
                                            ('name', '=ilike', instance.name),
                                            ('code', '=ilike', instance.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True
    
    def onchange_parent_id(self, cr, uid, ids, parent_id, level, context=None):
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if parent_id and level == 'project':
            parent_instance = self.browse(cr, uid, parent_id, context=context)
            for instance in self.browse(cr, uid, ids, context=context):
                # delete existing cost center lines
                old_target_line_ids = [x.id for x in instance.target_cost_center_ids]
                self.unlink(cr, uid, old_target_line_ids, context=context)
                # copy existing lines for project
                for line_to_copy in parent_instance.target_cost_center_ids:
                    self.pool.get('account.target.costcenter').create(cr, uid, {'instance_id': instance.id,
                                                                                'cost_center_id': line_to_copy.cost_center_id.id,
                                                                                'is_target': False,
                                                                                'parent_id': line_to_copy.id}, context=context)
        return True

    def _check_database_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('&'),
                                            ('instance', '!=', False),
                                            ('instance', '=', instance.instance)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True
    
    def _check_move_prefix_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('move_prefix', '=ilike', instance.move_prefix)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_reconcile_prefix_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('reconcile_prefix', '=ilike', instance.reconcile_prefix)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
         (_check_name_code_unicity, 'You cannot have the same code or name than an active instance!', ['code', 'name']),
         (_check_database_unicity, 'You cannot have the same database than an active instance!', ['instance']),
         (_check_move_prefix_unicity, 'You cannot have the same move prefix than an active instance!', ['move_prefix']),
         (_check_reconcile_prefix_unicity, 'You cannot have the same reconciliation prefix than an active instance!', ['reconcile_prefix']),
    ]
    
    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            txt = rs.code
            res += [(rs.id, txt)]
        return res

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        """
        Search Instance regarding their code and their name
        """
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, uid, [('code', 'ilike', name)]+ args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, uid, [('name', 'ilike', name)]+ args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context=context)

    def button_deactivate(self, cr, uid, ids, context=None):
        """
        Deactivate instance
        """
        self.write(cr, uid, ids, {'state': 'inactive'}, context=context)
        return True
    
msf_instance()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
