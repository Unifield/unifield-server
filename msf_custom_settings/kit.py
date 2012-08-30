#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
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

class composition_kit(osv.osv):
    _inherit = 'composition.kit'
    _name = 'composition.kit'
    
    def action_cancel(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Hide the button duplicate and delete for the "Kit Composition List"
        """
        if context is None:
            context = {}
        # call super
        res = super(composition_kit, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # if the view is called from the menu "Kit Composition List" the button duplicate and delete are hidden
        if view_type == 'form' and context.get('composition_type', False) == 'real':
            # fields to be modified
            res['arch'] = res['arch'].replace(
            '<form string="Kit Composition">',
            '<form string="Kit Composition" hide_duplicate_button="1" hide_delete_button="1">')
        
        # in tree view, hide the delete button and replace it by a delete button of type "object" to hide if it is not draft state
        if view_type == 'tree' and context.get('composition_type', False) == 'real':
            res['arch'] = res['arch'].replace(
            '<tree string="Kit Composition">',
            '<tree string="Kit Composition" hide_delete_button="1">')
            res['arch'] = res['arch'].replace(
            '<field name="state"/>',
            """<field name="state"/>
               <button name="delete_button" type="object" icon="gtk-del" string="Delete" 
                states='draft' confirm='Do you really want to delete selected record(s) ?'/>""")
        return res

composition_kit()