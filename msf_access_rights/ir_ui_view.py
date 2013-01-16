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
from lxml import etree

class button():
    def __init__(self, name, label, type):
        self.name = name
        self.label = label
        self.type = type

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
        # todo: generate button access rules
        return super(ir_ui_view, self).create(cr, uid, vals, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        # delete button access rules
        pool = self.pool.get('msf_access_rights.button_access_rule')
        for i in ids:
            search = pool.search(cr, uid, [('view_id','=',i)])
            pool.unlink(cr, uid, search)
            
        return super(ir_ui_view, self).unlink(cr, uid, ids, context=context)
    
    def parse_view(self, view_xml_text):
        """
        Pass viewxml to extract button objects for each button in the view
        """
        button_object_list = []
        view_xml = etree.fromstring(view_xml_text)
        buttons = view_xml.xpath("//button")
        for but in buttons:
            name = but.attrib.get('name', '')
            label = but.attrib.get('label', '')
            type = but.attrib.get('type', '')
            b = button(name, label, type)
            button_object_list.append(b)
        return button_object_list
    
    def parse_view_button(self, cr, uid, ids, context=None):
        records = self.browse(cr, uid, ids)
        for record in records:
            buttons = self.parse_view(record.arch)
            rules_pool = self.pool.get('msf_access_rights.button_access_rule')
            model_pool = self.pool.get('ir.model')
            for button in buttons:
                model_id = model_pool.search(cr, uid, [('model','=',record.model)])
                vals = {
                    'name': button.name,
                    'label': button.label,
                    'type': button.type,
                    'model_id': model_id[0],
                    'view_id': record.id,
                }
                rules_pool.create(cr, uid, vals)
    
ir_ui_view()