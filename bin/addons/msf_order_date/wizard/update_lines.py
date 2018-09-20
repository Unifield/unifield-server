# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

class update_lines(osv.osv_memory):
    _name = "update.lines"
    _description = "Update Lines from order"
    _columns = {
        'delivery_requested_date': fields.date('Delivery Requested Date', readonly=True,),
        'delivery_confirmed_date': fields.date('Delivery Confirmed Date', readonly=True,),
        'stock_take_date': fields.date('Date of Stock Take', readonly=True,),
    }

    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}

        # switch according to type
        type = context['type']
        obj_obj = self.pool.get(type)
        res = super(update_lines, self).default_get(cr, uid, fields, context=context)
        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res

        for obj in obj_obj.browse(cr, uid, obj_ids, context=context):
            delivery_requested_date = obj.delivery_requested_date
            delivery_confirmed_date = obj.delivery_confirmed_date
            stock_take_date = obj.stock_take_date

        if 'delivery_requested_date' in fields:
            res.update({'delivery_requested_date': delivery_requested_date})

        if 'delivery_confirmed_date' in fields:
            res.update({'delivery_confirmed_date': delivery_confirmed_date})

        if 'stock_take_date' in fields:
            res.update({'stock_take_date': stock_take_date})

        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # integrity check
        assert context, 'No context defined'
        # call super
        result = super(update_lines, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # switch according to type
        type = context['type']
        obj_obj = self.pool.get(type)
        obj_ids = context.get('active_ids', [])
        field_name = context.get('field_name', False)

        if not obj_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        obj_name = obj_obj.browse(cr, uid, obj_ids[0], context=context).name

        yes = _('Yes')
        no = _('No')
        value_to_be_used = _('Value to be used-')
        requested = _('requested')
        confirmed = ('_confirmed')
        assert requested
        assert confirmed
        if str(field_name) == 'stock_take':
            _moves_arch_lst = """
                            <form>
                            <separator colspan="4" string="%s: %s"/>
                            <field name="stock_take_date" />
                            <button name="update_stock_take_date" string="%s" type="object" icon="gtk-apply" />
                            <button special="cancel" string="%s" icon="gtk-cancel"/>
                            """ % (obj_name, value_to_be_used, yes, no)

            _moves_fields = result['fields']
            # add field related to picking type only
            _moves_fields.update({'stock_take_date': {'type': 'date', 'string': _('Date of Stock Take'), 'readonly': True, },})

            _moves_arch_lst += """</form>"""
        else:
            _moves_arch_lst = """
                            <form>
                            <separator colspan="4" string="%s: %s"/>
                            <field name="delivery_%s_date" />
                            <button name="update_delivery_%s_date" string="%s" type="object" icon="gtk-apply" />
                            <button special="cancel" string="%s" icon="gtk-cancel"/>
                            """ % (obj_name, value_to_be_used, field_name, field_name, yes, no)
            _moves_fields = result['fields']
            # add field related to picking type only
            _moves_fields.update({'delivery_%s_date'%field_name: {'type' : 'date', 'string' : _('Delivery %s date')% _(field_name), 'readonly': True,},
                                  })

            _moves_arch_lst += """</form>"""

        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

    def update_delivery_requested_date(self, cr, uid, ids, context=None):
        '''
        update all corresponding lines
        '''
        # switch according to type
        type = context['type']
        obj_obj = self.pool.get(type)
        # working objects
        obj_ids = context.get('active_ids', [])
        for obj in obj_obj.browse(cr, uid, obj_ids, context=context):
            requested_date = obj.delivery_requested_date
            for line in obj.order_line:
                if line.state in ('draft', 'validated', 'validated_n'):
                    line.write({'date_planned': requested_date})

        return {'type': 'ir.actions.act_window_close'}

    def update_delivery_confirmed_date(self, cr, uid, ids, context=None):
        '''
        update all corresponding lines
        '''
        # switch according to type
        type = context['type']
        obj_obj = self.pool.get(type)
        # working objects
        obj_ids = context.get('active_ids', [])
        for obj in obj_obj.browse(cr, uid, obj_ids, context=context):
            confirmed_date = obj.delivery_confirmed_date
            for line in obj.order_line:
                if line.state in ('draft', 'validated', 'validated_n'):
                    line.write({'confirmed_delivery_date': confirmed_date})

        return {'type': 'ir.actions.act_window_close'}

    def update_stock_take_date(self, cr, uid, ids, context=None):
        '''
        update all corresponding lines
        '''
        # switch according to type
        type = context['type']
        obj_obj = self.pool.get(type)
        # working objects
        obj_ids = context.get('active_ids', [])
        for obj in obj_obj.browse(cr, uid, obj_ids, context=context):
            stock_take_date = obj.stock_take_date
            for line in obj.order_line:
                if line.state in ('draft', 'validated', 'validated_n'):
                    line.write({'stock_take_date': stock_take_date})

        return {'type': 'ir.actions.act_window_close'}

update_lines()
