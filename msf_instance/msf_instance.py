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
    
    def _get_current_instance_level(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        res = dict.fromkeys(ids, False)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id and user.company_id.instance_id:
            for id in ids:
                res[id] = user.company_id.instance_id.level
        return res
    
    def _get_top_cost_center(self, cr, uid, ids, fields, arg, context=None):
        """
        Search for top cost center from the given instance.
        """
        # Some checks
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Default values
        res = dict.fromkeys(ids, False)
        # Search top cost center
        for instance in self.read(cr, uid, ids, ['target_cost_center_ids', 'level'], context=context):
            target_cc_ids = instance.get('target_cost_center_ids', False)
            if target_cc_ids:
                for target in self.pool.get('account.target.costcenter').read(cr, uid, target_cc_ids, ['is_top_cost_center', 'cost_center_id']):
                    if target.get('is_top_cost_center', False):
                        res[instance.get('id')] = target.get('cost_center_id', [False])[0]
                        break
            elif instance.get('level', '') == 'section':
                parent_cost_centers = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), ('parent_id', '=', '')], context=context)
                if len(parent_cost_centers) > 0:
                    res[instance.get('id')] = parent_cost_centers[0]
        return res
    
    def _get_po_fo_cost_center(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        res = dict.fromkeys(ids, False)
        for instance in self.browse(cr, uid, ids, context=context):
            if instance.target_cost_center_ids:
                for target in instance.target_cost_center_ids:
                    if target.is_po_fo_cost_center:
                        res[instance.id] = target.cost_center_id.id
                        break
            elif instance.level == 'section':
                parent_cost_centers = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), ('parent_id', '=', '')], context=context)
                if len(parent_cost_centers) > 0:
                    res[instance.id] = parent_cost_centers[0]
        return res
    
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
        'target_cost_center_ids': fields.one2many('account.target.costcenter', 'instance_id', 'Target Cost Centers'),
        'state': fields.selection([('draft', 'Draft'),
                                   ('active', 'Active'),
                                   ('inactive', 'Inactive')], 'State', required=True),
        'move_prefix': fields.char('Account move prefix', size=5, required=True),
        'reconcile_prefix': fields.char('Reconcilation prefix', size=5, required=True),
        'current_instance_level': fields.function(_get_current_instance_level, method=True, store=False, string="Current Instance Level", type="char", readonly="True"),
        'top_cost_center_id': fields.function(_get_top_cost_center, method=True, store=False, string="Top cost centre for budget consolidation", type="many2one", relation="account.analytic.account", readonly="True"),
        'po_fo_cost_center_id': fields.function(_get_po_fo_cost_center, method=True, store=False, string="Cost centre picked for PO/FO reference", type="many2one", relation="account.analytic.account", readonly="True"),
        'instance_identifier': fields.char('Instance identifier', size=64, readonly=1),
    }
    
    _defaults = {
        'state': 'draft',
        'current_instance_level': 'section', # UTP-941 set the default value to section, otherwise all fields in the new form are readonly
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
        # Check if lines are imported from coordo; if now, create those
        res_id = osv.osv.create(self, cr, uid, vals, context=context)
        if 'parent_id' in vals and 'level' in vals and vals['level'] == 'project':
            parent_instance = self.browse(cr, uid, vals['parent_id'], context=context)
            instance = self.browse(cr, uid, res_id, context=context)
            if len(parent_instance.target_cost_center_ids) != len(instance.target_cost_center_ids):
                # delete existing cost center lines
                old_target_line_ids = [x.id for x in instance.target_cost_center_ids]
                self.unlink(cr, uid, old_target_line_ids, context=context)
                # copy existing lines for project
                for line_to_copy in parent_instance.target_cost_center_ids:
                    self.pool.get('account.target.costcenter').create(cr, uid, {'instance_id': instance.id,
                                                                                'cost_center_id': line_to_copy.cost_center_id.id,
                                                                                'is_target': False,
                                                                                'parent_id': line_to_copy.id}, context=context)
        return res_id
        

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

    def get_child_ids(self, cr, uid, instance_ids=None, children_ids_list=None, context=None):
        """
        Search for all the children ids of the instance_ids parameter
        Get the current instance id if no instance_ids is given
        """
        if context is None:
            context = {}
        if instance_ids is None:
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            if user.company_id and user.company_id.instance_id:
                instance_ids = [user.company_id.instance_id.id]
        current_children = self.search(cr, uid, [('parent_id', 'in',
                                                  tuple(instance_ids))])
        if children_ids_list is None:
            children_ids_list = []
        if not current_children:
            return children_ids_list
        children_ids_list.extend(current_children)
        self.get_child_ids(cr, uid, current_children, children_ids_list,
                           context)
        return children_ids_list

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            txt = rs.code
            res += [(rs.id, txt)]
            context['level'] = rs.level
        
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
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Override the tree view to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(msf_instance, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        
        if user.company_id and user.company_id.instance_id:
            current_instance_level = user.company_id.instance_id.current_instance_level
            
            if current_instance_level != 'section':
                if 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_duplicate_button="1"')
                    res['arch'] = res['arch'].replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_delete_button="1"')
                    res['arch'] = res['arch'].replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_new_button="1" noteditable="1" notselectable="0"')
                    
                if 'target_cost_center_ids' in res['fields']:
                    arch = res['fields']['target_cost_center_ids']['views']['tree']['arch']
                    if 'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON' in arch:
                        res['fields']['target_cost_center_ids']['views']['tree']['arch'] = arch.replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON', 'noteditable="1" hide_delete_button="1')
            else:
                if res['type'] == 'form' and 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                if 'target_cost_center_ids' in res['fields']:
                    arch = res['fields']['target_cost_center_ids']['views']['tree']['arch']
                    if 'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON' in arch:
                        res['fields']['target_cost_center_ids']['views']['tree']['arch'] = arch.replace('PROP_INSTANCE_HIDE_BUTTON', '0')
                    
        return res
    
    
msf_instance()

class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def get_browse_user_instance(self, cr, uid, context=None):
        current_user = self.browse(cr, uid, uid, context=context)
        return current_user and current_user.company_id and current_user.company_id.instance_id or False
res_users()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
