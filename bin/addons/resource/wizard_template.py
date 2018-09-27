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
import time
from lxml import etree
from msf_field_access_rights.osv_override import _get_instance_level

class finance_query_method(osv.osv):
    _name = 'finance.query.method'
    _description = 'Common methods to manage sync'

    _columns = {
        'hq_template': fields.boolean('HQ Template', readonly='1'),
        'created_on_hq': fields.boolean('Flag used on HQ instance only for sync purpose', readonly='1', internal=1),
    }

    _defaults = {
        'hq_template': False,
        'created_on_hq': False,
        #'created_on_hq': lambda self, cr, uid, *a, **b: self._is_hq(cr, uid)
    }

    def _is_hq(self, cr, uid):
        return _get_instance_level(self, cr, uid) == 'hq'

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        for field in ('hq_template', 'created_on_hq'):
            if field not in default:
                default[field] = False
        return super(finance_query_method, self).copy_data(cr, uid, id, default=default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context.get('sync_update_execution'):
            # set was_synced for each records when hq_template = on, do not reset this value
            # on unlink if was was_synced!=True => delete ir_model_data, so deletion does not trigger update
            # search_deleted: real deleted + records was_synced and hq_template = False, then reset was_synced after
            ids_tosync = self.search(cr,uid, [('id', 'in', ids), ('created_on_hq', '=', True), ('hq_template', '=', True)], context=context)
            if ids_tosync:
                self._gen_update_to_del(cr, uid, ids_tosync, context=None)
        return super(finance_query_method, self).unlink(cr, uid, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            if 'hq_template' in vals and not vals['hq_template']:
                ids_tosync = self.search(cr,uid, [('id', 'in', ids), ('created_on_hq', '=', True), ('hq_template', '=', True)], context=context)
                if ids_tosync:
                    self._gen_update_to_del(cr, uid, ids_tosync, context=None)
            elif vals.get('created_on_hq') and vals.get('hq_template'):
                self._del_previous_update(cr, uid, ids, context=None)

        return super(finance_query_method, self).write(cr, uid, ids, vals, context=context)

finance_query_method()

class wizard_template(osv.osv):
    """
    Used to store the values from a wizard in order to reload them later
    """

    _name = 'wizard.template'
    _description = 'Wizard Template'
    _inherit = 'finance.query.method'

    def _get_sync_values(self, cr, uid, ids, field_name, args, context=None):

        ret = {}

        for wizard in self.read(cr, uid, ids, ['values', 'wizard_name'], context=context):
            data = wizard['values'] and eval(wizard['values']) or {}
            obj = self.pool.get(wizard['wizard_name'])
            ret[wizard['id']] = {}
            for k in data:
                if data[k] and obj._columns.get(k) and obj._columns.get(k)._type in ('one2many', 'many2one', 'many2many'):
                    sdref = self.pool.get(obj._columns.get(k)._obj).get_sd_ref(cr, uid, data[k])
                    if isinstance(sdref, basestring):
                        ret[wizard['id']][k] = sdref
                    else:
                        ret[wizard['id']][k] = ','.join(sdref.values())
                else:
                    ret[wizard['id']][k] = data[k]
        return ret

    def _set_sync_values(self, cr, uid, id, name, value, arg, context):
        wiz = self.read(cr, uid, id, ['wizard_name'], context=context)
        obj = self.pool.get(wiz['wizard_name'])

        data = eval(value)
        new_data = {}
        for k in data:
            if obj._columns.get(k) and obj._columns.get(k)._type in ('one2many', 'many2one', 'many2many'):
                if obj._columns.get(k)._type == 'many2one':
                    new_data[k] = data[k] and self.pool.get(obj._columns.get(k)._obj).find_sd_ref(cr, uid, data[k])
                else:
                    new_data[k] = data[k] and self.pool.get(obj._columns.get(k)._obj).find_sd_ref(cr, uid, data[k].split(',')).values()
            else:
                new_data[k] = data[k]

        cr.execute('update wizard_template set values=%s where id=%s', ('%s'%new_data, id))
        return True


    _columns = {
        'name': fields.char('Template name', size=128, required=True, select=1),
        'user_id': fields.many2one('res.users', string='User', ondelete='cascade', required=True),
        'wizard_name': fields.char('Wizard name', size=256, required=True),
        'values': fields.text('Values', help='Values from the wizard, stored as a dictionary'),
        'last_modification': fields.datetime('Last Modification Date'),
        'sync_values': fields.function(_get_sync_values, string='Sdrefed values', type='text', method=True, fnct_inv=_set_sync_values),
    }

    _defaults = {
        'user_id': lambda self, cr, uid, *a, **b: uid,
    }
    _sql_constraints = [
        ('name_user_id_wizard_name_uniq', 'UNIQUE(name, user_id, wizard_name)',
         'This template name already exists for this wizard. Please choose another name.')
    ]


    def _clean_data(self, cr, uid, data, context=None):
        for field in ['template_name', 'id', 'display_load_button', 'saved_templates']:
            if field in data:
                del data[field]

    def save_template(self, cr, uid, ids, wizard_name, context=None):
        """
        Store all the fields values of the wizard in parameter.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        """
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
            self._clean_data(cr, uid, data, context)
            # create a new wizard_template to store the values
            vals = {
                'name': template_name,
                'user_id': uid,
                'wizard_name': wizard_obj._name,
                'values': data,
                'last_modification': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            if context.get('from_query'):
                vals['hq_template'] = True
                vals['created_on_hq'] = True

            self.create(cr, uid, vals, context=context)
        return True

    def load_template(self, cr, uid, ids, wizard_name, context=None):
        """
        Load the values in the fields of the wizard in parameter, according to the template selected.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        """
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

    def delete_template(self, cr, uid, ids, wizard_name, context=None):
        """
        Delete the template selected in the "saved_templates_field" of the "wizard_name"
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        """
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
        self.unlink(cr, uid, selected_template_id, context=context)
        # close the wizard
        return {'type': 'ir.actions.act_window_close'}

    def edit_template(self, cr, uid, ids, wizard_name, context=None):
        """
        Edit the values of the fields stored in the selected template.
        :param wizard_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        """
        if context is None:
            context = {}
        # object corresponding to the current wizard
        wizard_obj = self.pool.get(wizard_name)
        # get a dictionary containing ALL fields values of the selected template
        data = ids and wizard_obj.read(cr, uid, ids[0], context=context)
        if data:
            selected_template_id = data['saved_templates']
            if not selected_template_id:
                raise osv.except_osv(_('Error !'), _('You have to choose a template to replace.'))
            self._clean_data(cr, uid, data, context=context)

            # update the existing record with the new values
            vals = {
                'values': data,
                'last_modification': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            if context.get('from_query'):
                vals['hq_template'] = True
                vals['created_on_hq'] = True

            return self.write(cr, uid, selected_template_id, vals, context=context)
        return True

wizard_template()


class wizard_template_form(osv.osv_memory):
    """
    Used to build the part of form that should be added to the wizards to use the "wizard template" functionality
    """

    _name = 'wizard.template.form'
    _description = 'Wizard Template Form'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if  context is None:
            context = {}
        view = super(wizard_template_form, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if context.get('from_query') and view_type == 'form':
            form = etree.fromstring(view['arch'])
            fields = form.xpath('//group[@name="wizard_template"]')
            for field in fields:
                field.set('invisible', "1")
            fields = form.xpath('//button[@name="save_query"]')
            for field in fields:
                field.set('invisible', "0")
            view['arch'] = etree.tostring(form)

        return view

    def _get_templates(self, cr, uid, context=None):
        """
        Return the recorded templates for the wizard in parameter and the current user,
        as a list of tuples with key (wizard template id) and value (template name), ordered by template name.
        Ex: [(4, 'a template'), (2, 'other template')]
        """
        if context is None:
            context = {}
        wizard_template_obj = self.pool.get('wizard.template')
        # TODO user_id filter
        template_ids = wizard_template_obj.search(cr, uid, [('wizard_name', '=', self._name), '|', ('user_id', '=', uid), ('hq_template', '=', True)],
                                                  context=context, order='name') or []
        templates = template_ids and wizard_template_obj.browse(cr, uid, template_ids,
                                                                fields_to_fetch=['name', 'hq_template'], context=context) or []
        names = [(t.id, '%s%s' % (t.name, t.hq_template and ' (SYNC)' or '')) for t in templates]
        return names

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
        """
        Whenever a new template is selected, display the "load" button
        (and don't display the other options for the template, such as "delete"...)
        """
        res = {}
        res['value'] = {'display_load_button': True}
        return res

    def save_query(self, cr, buid, ids, context=None):
        uid = hasattr(buid, 'realUid') and buid.realUid or buid
        self.pool.get('wizard.template').edit_template(cr, uid, ids, wizard_name=self._name, context=context)
        return {'type': 'ir.actions.act_window_close', 'context': context}

wizard_template_form()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
