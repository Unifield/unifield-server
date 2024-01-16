# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class hr_department(osv.osv):
    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _dept_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _get_ids_to_update(self, cr, uid, ids, context=None):
        '''
        recursive method to get all hr.department ids which have ancestor
        related to ids
        '''
        child_ids = self.search(cr, uid, [('parent_id', 'in', ids)], context=context)
        sub_child_ids = []
        if child_ids:
            sub_child_ids = self._get_ids_to_update(cr, uid, child_ids, context=context)
        return ids + sub_child_ids

    _name = "hr.department"
    _columns = {
        'name': fields.char('Department Name', size=64, required=True),
        'complete_name': fields.function(_dept_name_get_fnc, method=True,
                                         type="char", string='Name', size=512,
                                         store = {
                                             'hr.department': (_get_ids_to_update, ['child_ids', 'name'], 10),
                                         }),
        'company_id': fields.many2one('res.company', 'Company', select=True, required=False),
        'parent_id': fields.many2one('hr.department', 'Parent Department', select=True),
        'child_ids': fields.one2many('hr.department', 'parent_id', 'Child Departments'),
        'note': fields.text('Note'),
    }

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'hr.department', context=c),
    }

    _order = 'complete_name, name, id'

    def _get_members(self, cr, uid, context=None):
        mids = self.search(cr, uid, [('manager_id', '=', uid)], context=context)
        result = {uid: 1}
        for m in self.browse(cr, uid, mids, context=context):
            for user in m.member_ids:
                result[user.id] = 1
        return list(result.keys())

    def _check_recursion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from hr_department where id IN %s',(tuple(ids),))
            ids = [_f for _f in [x[0] for x in cr.fetchall()] if _f]
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error! You can not create recursive departments.', ['parent_id'])
    ]

hr_department()

class ir_action_window(osv.osv):
    _inherit = 'ir.actions.act_window'

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        obj_dept = self.pool.get('hr.department')
        select = ids
        if isinstance(ids, int):
            select = [ids]
        res = super(ir_action_window, self).read(cr, uid, select, fields=fields, context=context, load=load)
        for r in res:
            mystring = 'department_users_get()'
            if mystring in (r.get('domain', '[]') or ''):
                r['domain'] = r['domain'].replace(mystring, str(obj_dept._get_members(cr, uid)))
        if isinstance(ids, int):
            if res:
                return res[0]
            else:
                return False
        return res

ir_action_window()

class res_users(osv.osv):
    _inherit = 'res.users'
    _description = 'User'

    _columns = {
        'context_department_id': fields.many2one('hr.department', 'Department'),
    }

res_users()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
