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
        """
        Generate the button access rules for this view
        """
        view_id = super(ir_ui_view, self).create(cr, uid, vals, context=context)
        model_id = self.pool.get('ir.model').search(cr, uid, [('model','=',vals['model'])])[0]
        buttons = self.parse_view(vals['arch'], model_id, view_id)
        self._write_button_objects(cr, uid, buttons)
        return view_id
    
    def write(self, cr, uid, ids, vals, context=None):
        """
        Update button access rules for this view
        """
        if not isinstance(ids, list):
            ids = [ids]
        
        rules_pool = self.pool.get('msf_access_rights.button_access_rule')
        model_pool = self.pool.get('ir.model')
        
        arch = vals.get('arch', False)
        
        for i in ids:
            view = self.browse(cr, uid, i)
            xml = arch or view.arch
            if isinstance(xml, unicode):
                xml = str(xml)
                
            try:
                buttons = self.parse_view(xml)
            except ValueError as e:
                print '================= Error when parsing view %s' % i
                print e
                buttons = False
                
            if buttons:
                model_search = model_pool.search(cr, uid, [('model','=',view.model)])
                if model_search:
                    model_id = model_search[0]
                    rule_id_list = []
                    
                    for button in buttons:
                        button.update({'view_id': i, 'model_id': model_id})
                        existing_button_search = rules_pool.search(cr, uid, [('view_id', '=', i),('name','=',button['name'])])
                        if existing_button_search:
                            # exists so update it
                            rules_pool.write(cr, uid, existing_button_search[0], {'name':button['name'], 'label':button['label'], 'type':button['type']})
                            rule_id_list.append(existing_button_search[0])
                        else:
                            # does not exist so create it
                            rule_id_list.append(rules_pool.create(cr, uid, button))
                            
                    rules_search = rules_pool.search(cr, uid, [('view_id', '=', i)])
                    for id in rule_id_list:
                        if rules_search.count(id):
                            rules_search.remove(id)
                        
                    rules_pool.write(cr, uid, rules_search, {'active':0})
            
        super(ir_ui_view, self).write(cr, uid, ids, vals, context=context) 
    
    def unlink(self, cr, uid, ids, context=None):
        # delete button access rules
        pool = self.pool.get('msf_access_rights.button_access_rule')
        for i in ids:
            search = pool.search(cr, uid, [('view_id','=',i)])
            pool.unlink(cr, uid, search)
            
        return super(ir_ui_view, self).unlink(cr, uid, ids, context=context)
    
    def _button_dict(self, name, label, type, model_id=None, view_id=None):
        return {
            'name': name,
            'label': label,
            'type': type,
            'model_id': model_id,
            'view_id': view_id,
        }
    
    def parse_view(self, view_xml_text, model_id=None, view_id=None):
        """
        Pass viewxml to extract button objects for each button in the view
        """
        button_object_list = []
        view_xml = etree.fromstring(view_xml_text)
        buttons = view_xml.xpath("//button")
        
        for button in buttons:
            
            name = button.attrib.get('name', '')
            label = button.attrib.get('string', '')
            type = button.attrib.get('type', '')
            
            button_object_list.append(self._button_dict(name, label, type, model_id, view_id))
            
        return button_object_list
    
    def parse_view_button(self, cr, uid, ids, context=None):
        records = self.browse(cr, uid, ids)
        for record in records:
            
            model_pool = self.pool.get('ir.model')
            model_id = model_pool.search(cr, uid, [('model','=',record.model)])
            buttons = self.parse_view(record.arch, model_id[0], record.id)
            
            self._write_button_objects(cr, uid, buttons)
            
    def _write_button_objects(self, cr, uid, buttons):
        rules_pool = self.pool.get('msf_access_rights.button_access_rule')
        for button in buttons:
            rules_pool.create(cr, uid, button)
    
ir_ui_view()