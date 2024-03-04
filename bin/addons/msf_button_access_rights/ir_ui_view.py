#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from osv import osv
from osv import fields
from lxml import etree
import logging

class ir_ui_view(osv.osv):
    """
    Inherit the ir.ui.view model to delete button access rules when deleting a view
    and add button access rules tab and reparse view tab to view
    """

    _inherit = "ir.ui.view"

    def _get_button_access_rules(self, cr, uid, ids, field_name, arg, context):
        res = dict.fromkeys(ids)
        records = self.browse(cr, 1, ids)
        pool = self.pool.get('msf_button_access_rights.button_access_rule')
        for record in records:
            search = pool.search(cr, 1, [('view_id','=',record.id)])
            res[record.id] = search
        return res

    _columns = {
        'button_access_rules_ref': fields.function(_get_button_access_rules, type='one2many', obj='msf_button_access_rights.button_access_rule', method=True, string='Button Access Rules'),
    }

    def generate_button_access_rules(self, cr, uid, view_ids, context=None):
        """
        Called by create method of ir.model.data after xml id is created for a view.
        This method generates the first set of button access rules for a new view.
        """
        if isinstance(view_ids, int):
            view_ids = [view_ids]

        buttons = []
        for view in self.browse(cr, 1, view_ids, fields_to_fetch=['model', 'arch']):
            model_id = self.pool.get('ir.model').search(cr, 1, [('model','=',view.model)])

            if model_id:
                try:
                    new_buttons = self.parse_view(view.arch, model_id[0], view.id)
                except (ValueError, etree.XMLSyntaxError) as e:
                    logging.getLogger(self._name).warn('Error when parsing view %s' % view.id)
                    print(e)
                self._write_button_objects(cr, 1, new_buttons)
                buttons += new_buttons
        return buttons

    def write(self, cr, uid, ids, vals, context=None):
        """
        Update button access rules for this view
        """
        if not ids:
            return True
        if not isinstance(ids, list):
            ids = [ids]

        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')
        model_pool = self.pool.get('ir.model')

        arch = vals.get('arch', False)

        for i in ids:
            # get old view xml
            view = self.browse(cr, 1, i)
            xml = arch or view.arch

            # parse the old xml into a list of button dictionaries
            try:
                buttons = self.parse_view(xml)
            except (ValueError, etree.XMLSyntaxError) as e:
                logging.getLogger(self._name).warn('Error when parsing view %s: %s' % (i, e))
                buttons = False

            # if we have some buttons we need to create/update Button Access Rule's from them
            if buttons:
                model_search = model_pool.search(cr, 1, [('model','=',view.model)])

                if model_search:
                    model_id = model_search[0]
                    rule_id_list = []

                    # for each button in the old view, update it with the new view_id and model_id
                    for button in buttons:
                        button.update({'view_id': i, 'model_id': model_id})

                        # look for existing BAR's with the same name and view_id
                        existing_button_search = rules_pool.search(cr, 1, [('view_id', '=', i),('name','=',button['name']),'|',('active','=',True),('active','=',False)])
                        if existing_button_search:
                            # a BAR exists so update it with the new view information and append the id to the list of existing BAR's
                            rules_pool.write(cr, 1, existing_button_search[0], {'label':button['label'], 'type':button['type'], 'model_id': model_id, 'active':True})
                            rule_id_list.append(existing_button_search[0])
                        else:
                            # does not exist so create it (First convert group xml ids to db ids)
                            if button['groups']:
                                button['group_ids'] = []
                                data_pool = self.pool.get('ir.model.data')
                                for g in button['groups'].split(','):
                                    g_split = g.strip().split('.',1)
                                    if len(g_split) == 2:
                                        try:
                                            group = data_pool.get_object(cr, 1, g_split[0], g_split[1])
                                            if group:
                                                group_id = group.id
                                                button['group_ids'].append(group_id)
                                        except ValueError:
                                            pass
                                del button['groups']
                                if button['group_ids']:
                                    button['group_ids'] = [(6, 0, button['group_ids'])]
                            # create BAR and append it's ID to the list of BAR's
                            rule_id_list.append(rules_pool.create(cr, 1, button))

                    # now we have a list of buttons, of corresponding BAR's, and of all existing BAR's. Set inactive each BAR which is now un-needed
                    rules_search = rules_pool.search(cr, 1, [('view_id', '=', i)])
                    for id in rule_id_list:
                        if rules_search.count(id):
                            rules_search.remove(id)
                    rules_pool.write(cr, 1, rules_search, {'active':0})

        # perform the final writes to the views
        return super(ir_ui_view, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        # delete button access rules
        pool = self.pool.get('msf_button_access_rights.button_access_rule')
        for i in ids:
            search = pool.search(cr, uid, [('view_id','=',i)])
            pool.unlink(cr, uid, search)

        return super(ir_ui_view, self).unlink(cr, uid, ids, context=context)

    def _button_dict(self, name, label, type, groups=None, model_id=None, view_id=None):
        return {
            'name': name,
            'label': label,
            'type': type,
            'groups': groups,
            'model_id': model_id,
            'view_id': view_id,
        }

    def parse_view(self, view_xml_text, model_id=None, view_id=None):
        """
        Pass view_xml_text to extract button objects for each button in the view (Ignore special and position buttons). Return _button_dict pseudo object
        @raise XMLSyntaxError: thrown by lxml when there is an error while parsing the xml
        """

        button_object_list = []

        if view_xml_text:
            view_xml = etree.fromstring(isinstance(view_xml_text, str) and view_xml_text.encode('utf8') or view_xml_text)
            buttons = view_xml.xpath("//button[ @name and (@type != 'special' or not (@type)) and not (@position) ]")

            for button in buttons:

                name = button.attrib.get('name', '')
                label = button.attrib.get('string', '')
                groups = button.attrib.get('groups','')
                type = button.attrib.get('type', '').lower() or 'workflow'

                if name:
                    button_object_list.append(self._button_dict(name, label, type, groups, model_id, view_id))

        return button_object_list

    def _get_xmlname(self, cr, uid, btype, name):
        xmlname = False
        data_obj = self.pool.get('ir.model.data')

        if btype == 'action':
            model = self.pool.get('ir.actions.actions').read(cr, uid, int(name), ['type'])['type']
            xmlid = data_obj.search(cr, uid, [('res_id', '=', name), ('module', '!=', 'sd'), ('model', '=', model)])
            if xmlid:
                data = data_obj.read(cr, uid, xmlid[0], ['module', 'name'])
                xmlname = '%s.%s' % (data['module'], data['name'])
        return xmlname

    def _write_button_objects(self, cr, uid, buttons):
        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')
        to_write = []
        for button in buttons:
            xmlname = self._get_xmlname(cr, uid, button.get('type'), button['name'])
            existing_rule_search = rules_pool.search(cr, uid, [
                ('name','=',button['name']),
                ('view_id','=',button['view_id']),
                ('xmlname', '=', xmlname)
            ])
            if not existing_rule_search:
                rules_pool.create(cr, uid, button)
            else:
                to_write += existing_rule_search

        if to_write:
            rules_pool.write(cr, uid, to_write, {'deprecated': 'f'})


ir_ui_view()
