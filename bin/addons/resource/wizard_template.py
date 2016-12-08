#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _


class wizard_template(osv.osv):
    '''
    Used to store the values from a wizard in order to reload them later
    '''

    _name = 'wizard.template'
    _description = 'Wizard Template'

    _columns = {
        'name': fields.char('Template name', size=128, required=True, select=1),
        'user_id': fields.many2one('res.users', string='User', ondelete='cascade', required=True),
        'wizard_name': fields.char('Wizard name', size=256, required=True),
        'values': fields.text('Values', help='Values from the wizard, stored as a dictionary'),
    }

    _sql_constraints = [
        ('name_user_id_wizard_name_uniq', 'UNIQUE(name, user_id, wizard_name)',
         'This template name already exists for this wizard. Please choose another name.')
    ]

    def save_template(self, cr, uid, ids, wizard_name, context=None):
        '''
        Store all the fields values of the wizard in parameter.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        '''
        if context is None:
            context = {}
        # object corresponding to the current wizard
        wizard_obj = self.pool.get(wizard_name)
        # get a dictionary with ALL fields values
        data = ids and wizard_obj.read(cr, uid, ids[0], context=context)
        if data:
            template_name = data['template_name']
            if not template_name:
                raise osv.except_osv(_('Error !'), _('You have to choose a template name.'))
            # don't keep the id, and the values of the fields related to the wizard template itself
            del data['template_name']
            if 'id' in data:
                del data['id']
            if 'saved_templates' in data:
                del data['saved_templates']
            if 'display_load_button' in data:
                del data['display_load_button']
            # create a new wizard_template to store the values
            vals = {'name': template_name,
                    'user_id': uid,
                    'wizard_name': wizard_obj._name,
                    'values': data,
                    }
            self.create(cr, uid, vals, context=context)
        return True

    def get_templates(self, cr, uid, wizard_name, context=None):
        '''
        Return the recorded templates for the wizard in parameter and the current user,
        as a list of tuples with key (wizard template id) and value (template name), ordered by template name.
        Ex: [(4, 'a template'), (2, 'other template')]
        '''
        if context is None:
            context = {}
        template_ids = self.search(cr, uid, [('wizard_name', '=', wizard_name), ('user_id', '=', uid)],
                                   context=context, order='name') or []
        templates = template_ids and self.browse(cr, uid, template_ids,
                                                 fields_to_fetch=['name'], context=context) or []
        names = [(t.id, t.name) for t in templates]
        return names

    def load_template(self, cr, uid, ids, wizard_name, context=None):
        '''
        Load the values in the fields of the wizard in parameter, according to the template selected.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        '''
        if context is None:
            context = {}
        # object corresponding to the current wizard
        wizard_obj = self.pool.get(wizard_name)
        # we get the selected template
        data = ids and wizard_obj.read(cr, uid, ids[0], ['saved_templates'], context=context)
        selected_template_id = data and data['saved_templates']
        if not selected_template_id:
            raise osv.except_osv(_('Error !'), _('You have to choose a template to load.'))
        # we get the values from the template as a String and convert them back to a dictionary
        vals = self.browse(cr, uid, selected_template_id, context=context).values
        try:
            vals = eval(vals)
            # we put the value of the selected template in the "Saved templates" selection field
            vals.update({'saved_templates': selected_template_id})
            # we put the "display_load_button" field to False,
            # so as to hide the load button and to show instead the options for the template loaded (delete...)
            if 'display_load_button':
                vals.update({'display_load_button': False})
        except SyntaxError:
            vals = {}
        # we "format" the many2many fields values to make them look like [(6, 0, [1, 2])]
        for i in vals:
            if type(vals[i]) == list:
                vals[i] = [(6, 0, vals[i])]
        # we set the data in a new wizard and display it
        new_id = wizard_obj.create(cr, uid, vals, context=context)
        if context.get('active_model') == 'ir.ui.menu' and context.get('active_id'):
            action = self.pool.get('ir.ui.menu').read(cr, uid, context.get('active_id'), ['action'], context=context)['action']
            model, res_id = action.split(',')
            ret = self.pool.get(model).read(cr, uid, [res_id],
                ['type', 'res_model', 'view_id', 'search_view_id', 'view_mode', 'view_ids', 'name', 'views', 'view_type'],
                context=context)[0]
            ret.update({'context': context, 'res_id': new_id, 'target': 'new'})
            return ret
        return {
            'type': 'ir.actions.act_window',
            'res_model': wizard_name,
            'view_type': 'form',
            'context': context,
            'res_id': new_id,
            'target': 'new',
        }

    def onchange_saved_templates(self, cr, uid, ids, context=None):
        '''
        Whenever a new template is selected, display the "load" button
        (and don't display the other options for the template, such as "delete"...)
        '''
        res = {}
        res['value'] = {'display_load_button': True}
        return res

    def delete_template(self, cr, uid, ids, wizard_name, context=None):
        '''
        Delete the template selected in the "saved_templates_field" of the "wizard_name"
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        '''
        if context is None:
            context = {}
        # object corresponding to the current wizard
        wizard_obj = self.pool.get(wizard_name)
        # get the selected template
        data = ids and wizard_obj.read(cr, uid, ids[0], ['saved_templates'], context=context)
        selected_template_id = data and data['saved_templates']
        if not selected_template_id:
            raise osv.except_osv(_('Error !'), _('You have to choose a template to delete.'))
        # delete the template
        return self.unlink(cr, uid, selected_template_id, context=context)

    def edit_template(self, cr, uid, ids, wizard_name, context=None):
        '''
        Edit the values of the fields stored in the selected template.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        '''
        if context is None:
            context = {}
        # object corresponding to the current wizard
        wizard_obj = self.pool.get(wizard_name)
        # get a dictionary containing ALL fields values of the selected template
        data = ids and wizard_obj.read(cr, uid, ids[0], context=context)
        if data:
            selected_template_id = data['saved_templates']
            if not selected_template_id:
                raise osv.except_osv(_('Error !'), _('You have to choose a template to edit.'))
            # don't keep the id, and the values of the fields related to the wizard template itself
            if 'template_name' in data:
                del data['template_name']
            if 'id' in data:
                del data['id']
            del data['saved_templates']
            if 'display_load_button' in data:
                del data['display_load_button']
            # update the existing record with the new values
            vals = {'values': data}
            return self.write(cr, uid, selected_template_id, vals, context=context)
        return True

wizard_template()


class wizard_template_form(osv.osv_memory):
    '''
    Used to build the part of form that should be added to the wizards to use the "wizard template" functionality
    '''

    _name = 'wizard.template.form'
    _description = 'Wizard Template Form'

    def _get_templates(self, cr, uid, context):
        return self.pool.get('wizard.template').get_templates(cr, uid, wizard_name=self._name, context=context)

    _columns = {
        'template_name': fields.char('Template name', size=128),
        'saved_templates': fields.selection(_get_templates, string='Saved templates'),
        'display_load_button': fields.boolean(),
    }

    _defaults = {
        'display_load_button': True,
    }

    def save_template(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        return self.pool.get('wizard.template').save_template(cr, uid, ids, wizard_name=self._name, context=context)

    def load_template(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        return self.pool.get('wizard.template').load_template(cr, uid, ids, wizard_name=self._name, context=context)

    def delete_template(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        return self.pool.get('wizard.template').delete_template(cr, uid, ids, wizard_name=self._name, context=context)

    def edit_template(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        return self.pool.get('wizard.template').edit_template(cr, uid, ids, wizard_name=self._name, context=context)

    def onchange_saved_templates(self, cr, uid, ids, context=None):
        return self.pool.get('wizard.template').onchange_saved_templates(cr, uid, ids, context=context)

wizard_template_form()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
