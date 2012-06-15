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
        'parent_id': fields.many2one('msf.instance', 'Parent', domain=[('level', '!=', 'project'), ('state', '=', 'active')]),
        'name': fields.char('Name', size=64, required=True),
        'note': fields.char('Note', size=256),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC')], required=True),
        'partner_id': fields.many2one('res.partner', string='Associated Partner', required=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('active', 'Active'),
                                   ('inactive', 'Inactive')], 'State', required=True),
    }
    
    _defaults = {
        'state': 'draft',
    }

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

    def _check_cost_center_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('cost_center_id','=',instance.cost_center_id.id)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
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

    _constraints = [
        (_check_name_code_unicity, 'You cannot have the same code or name than an active instance!', ['code', 'name']),
        (_check_cost_center_unicity, 'You cannot have the same cost_center than an active instance!', ['cost_center_id']),
        (_check_database_unicity, 'You cannot have the same database than an active instance!', ['instance']),
    ]
    
    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            txt = rs.code
            res += [(rs.id, txt)]
        return res
    
    def button_deactivate(self, cr, uid, ids, context=None):
        """
        Deactivate instance
        """
        self.write(cr, uid, ids, {'state': 'inactive'}, context=context)
        return True
    
msf_instance()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
