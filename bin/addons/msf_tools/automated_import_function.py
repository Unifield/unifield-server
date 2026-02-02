# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF
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

from tools.translate import _


class automated_import_function(osv.osv):
    _name = 'automated.import.function'

    _columns = {
        'name': fields.char(
            size=64,
            string='Name',
            required=True,
        ),
        'model_id': fields.many2one(
            'ir.model',
            string='Model',
            required=True,
        ),
        'method_to_call': fields.char(
            size=128,
            string='Method to call',
            required=True,
        ),
        'startswith': fields.char('Starts with', size=56),
        'multiple': fields.boolean('Allow multiple jobs'),
        'email_notification': fields.boolean('Allow email notifications'),
    }

    _defaults = {
        'method_to_call': lambda *a: 'import_data_from_csv',
        'multiple': False,
        'email_notification': False,
    }

    _order = 'name'

    def check_method_to_call(self, cr, uid, model_id, method):
        """
        Check if the model implements the method
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param model: ID of ir.model
        :param method: method name
        :return: Return True or False
        """
        model = self.pool.get('ir.model').browse(cr, uid, model_id)
        if not hasattr(self.pool.get(model.model), method):
            raise osv.except_osv(
                _('Error'),
                _('The method \'%s\' of the model \'%s\' is not callable') % (model.model, method),
            )
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Run the check on method to call before create the new record
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param vals: Values to put on the new record
        :param context: Context of the call
        :return: ID of the new automated.import.function
        """
        if vals.get('model_id') and vals.get('method_to_call'):
            self.check_method_to_call(cr, uid, vals.get('model_id'), vals.get('method_to_call'))

        return super(automated_import_function, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Run the check on method to call before update the record(s)
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import.function record to update
        :param vals: Values to put on the new record
        :param context: Context of the call
        :return: True
        """
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]

        if vals.get('model_id') and vals.get('method_to_call'):
            self.check_method_to_call(cr, uid, vals.get('model_id'), vals.get('method_to_call'))
        elif vals.get('model_id') or vals.get('method_to_call'):
            for rec in self.browse(cr, uid, ids, context=context):
                model = vals.get('model_id', rec.model_id)
                func = vals.get('method_to_call', rec.method_to_call)
                self.check_method_to_call(cr, uid, model, func)

        return super(automated_import_function, self).write(cr, uid, ids, vals, context=context)

automated_import_function()
