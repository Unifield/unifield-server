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
        'name': fields.char('Template name', size=128, required=True),
        'user_id': fields.many2one('res.users', string='User', ondelete='cascade', required=True),
        'wizard_name': fields.char('Wizard name', size=256, required=True),
        'values': fields.text('Values', help='Values from the wizard, stored as a dictionary'),
    }

    _sql_constraints = [
        ('name_user_id_wizard_name_uniq', 'UNIQUE(name, user_id, wizard_name)',
         'This template name already exists for this wizard. Please choose another name.')
    ]

    def save_template(self, cr, uid, ids, context, wizard_name, template_name_field='template_name'):
        '''
        Store all the fields values of the wizard in parameter.
        :param wizard_model_name: String, name of the wizard model (ex: 'wizard.account.partner.balance.tree')
        :param template_name_field: String, name of the field in the wizard containing the chosen template name
        '''
        # get a dictionary with ALL fields values
        wizard_obj = self.pool.get(wizard_name)
        data = ids and wizard_obj.read(cr, uid, ids[0], context=context)
        if data:
            if not data[template_name_field]:
                raise osv.except_osv(_('Error !'), _('You have to choose a template name.'))
            else:
                # create a new wizard_template to store the values
                vals = {'name': data[template_name_field],
                        'user_id': uid,
                        'wizard_name': wizard_obj._name,
                        'values': data,
                        }
                self.create(cr, uid, vals, context=context)
        return True

    def get_templates(self, cr, uid, context, wizard_name):
        '''
        Return the recorded templates for the wizard in parameter and the current user,
        as a list of tuples with key (wizard template id) and value (template name), ordered by template name.
        Ex: [(4, 'a template'), (2, 'other template')]
        '''
        template_ids = self.search(cr, uid, [('wizard_name', '=', wizard_name), ('user_id', '=', uid)],
                                               context=context, order='name') or []
        templates = template_ids and self.browse(cr, uid, template_ids,
                                                             fields_to_fetch=['name'], context=context) or []
        names = [(t.id, t.name) for t in templates]
        return names


wizard_template()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
