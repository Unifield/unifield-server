#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford
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
from osv import orm
import psycopg2

class ir_ui_view(osv.osv):
    """
    Inherit the ir.ui.view model to delete button access rules when deleting a view
    and add button access rules tab and reparse view tab to view
    """

    _name = "ir.ui.view"
    _inherit = "ir.ui.view"
    
    def _get_button_access_rules(self, cr, uid, ids, field_name, arg, context):
        res = dict.fromkeys(ids)
        records = self.browse(cr, uid, ids)
        for record in records:
            pool = self.pool.get('msf_access_rights.button_access_rule')
            search = pool.search(cr, uid, [('view_id','=',record.id)])
            res[record.id] = search
        return res

    _columns = {
        'button_access_rules_ref': fields.function(_get_button_access_rules, type='one2many', obj='msf_access_rights.button_access_rule', method=True, string='Button Access Rules'),
    }

    def create(self, cr, uid, vals, context=None):
        return super(ir_ui_view, self).create(cr, uid, vals, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        # delete button access rules
        pool = self.pool.get('msf_access_rights.button_access_rule')
        for i in ids:
            search = pool.search(cr, uid, [('view_id','=',i)])
            pool.unlink(cr, uid, search)
            
        return super(ir_ui_view, self).unlink(cr, uid, ids, context=context)
    
ir_ui_view()