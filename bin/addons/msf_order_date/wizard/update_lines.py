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
        header_name = _('Value to be used')
        btn_name_yes_s = _('Yes - Selected lines')
        btn_name_yes = _('Yes - All lines')
        btn_name_no = _('No')
        has_selection = context.get('button_selected_ids')
        button_selection = ""

        if str(field_name) == 'stock_take':
            if has_selection:
                button_selection = '<button name="update_stock_take_date_select" string="%s" type="object" icon="gtk-apply" />' % (btn_name_yes_s, )
            _moves_arch_lst = """
                            <form>
                            <separator colspan="4" string="%s: %s-"/>
                            <field colspan="2" name="stock_take_date" />
                            <group colspan="2" col="3">
                                %s
                                <button name="update_stock_take_date" string="%s" type="object" icon="gtk-apply" />
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                            </group>
                            """ % (obj_name, header_name, button_selection, btn_name_yes, btn_name_no)

            _moves_fields = result['fields']
            # add field related to picking type only
            _moves_fields.update({'stock_take_date': {'type': 'date', 'string': 'Date of Stock Take', 'readonly': True, },})

            _moves_arch_lst += """</form>"""
        else:
            if has_selection:
                button_selection = '<button name="update_delivery_%s_date_select" string="%s" type="object" icon="gtk-apply" />' % (field_name, btn_name_yes_s)
            _moves_arch_lst = """
                            <form>
                            <separator colspan="4" string="%s: %s-"/>
                            <field name="delivery_%s_date" />
                            <group colspan="2" col="3">
                                %s
                                <button name="update_delivery_%s_date" string="%s" type="object" icon="gtk-apply" />
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                            </group>
                            """ % (obj_name, header_name, field_name, button_selection, field_name, btn_name_yes, btn_name_no)

            _moves_fields = result['fields']
            # add field related to picking type only
            _moves_fields.update({'delivery_%s_date'%field_name: {'type' : 'date', 'string' : 'Delivery %s date'%field_name, 'readonly': True,},
                                  })

            _moves_arch_lst += """</form>"""

        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

    def update_delivery_requested_date_select(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.update_delivery_requested_date(cr, uid, ids, context=context, selected=True)

    def update_delivery_requested_date(self, cr, uid, ids, context=None, selected=False):
        '''
        update all corresponding lines
        '''
        # switch according to type
        obj_type = context['type']
        obj_obj = self.pool.get(obj_type)
        # working objects
        obj_ids = context.get('active_ids', [])

        if obj_type == 'purchase.order':
            line_obj = self.pool.get('purchase.order.line')
        else:
            line_obj = self.pool.get('sale.order.line')

        for obj in obj_obj.browse(cr, uid, obj_ids, fields_to_fetch=['delivery_requested_date'], context=context):
            requested_date = obj.delivery_requested_date
            dom = [('order_id', '=', obj.id), ('state', 'in',['draft', 'validated', 'validated_n'])]
            if selected and context.get('button_selected_ids'):
                dom += [('id', 'in', context['button_selected_ids'])]
            line_ids = line_obj.search(cr, uid, dom, context=context)
            if line_ids:
                line_obj.write(cr, uid, line_ids, {'date_planned': requested_date}, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def update_delivery_confirmed_date_select(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.update_delivery_confirmed_date(cr, uid, ids, context=context, selected=True)

    def update_delivery_confirmed_date(self, cr, uid, ids, context=None, selected=False):
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
                if selected and context.get('button_selected_ids'):
                    if line.id in context['button_selected_ids'] and line.state in ('draft', 'validated', 'validated_n'):
                        line.write({'confirmed_delivery_date': confirmed_date})
                else:
                    if line.state in ('draft', 'validated', 'validated_n'):
                        line.write({'confirmed_delivery_date': confirmed_date})

        return {'type': 'ir.actions.act_window_close'}

    def update_stock_take_date_select(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.update_stock_take_date(cr, uid, ids, context=context, selected=True)

    def update_stock_take_date(self, cr, uid, ids, context=None, selected=False):
        '''
        update all corresponding lines
        '''
        # switch according to type
        obj_type = context['type']
        obj_obj = self.pool.get(obj_type)
        # working objects
        obj_ids = context.get('active_ids', [])

        if obj_type == 'purchase.order':
            line_obj = self.pool.get('purchase.order.line')
        else:
            line_obj = self.pool.get('sale.order.line')

        for obj in obj_obj.browse(cr, uid, obj_ids, context=context):
            stock_take_date = obj.stock_take_date
            dom = [('order_id', '=', obj.id), ('state', 'in', ['draft', 'validated', 'validated_n'])]
            if selected and context.get('button_selected_ids'):
                dom += [('id', 'in', context.get('button_selected_ids'))]
            line_ids = line_obj.search(cr, uid, dom, context=context)
            if line_ids:
                line_obj.write(cr, uid, line_ids, {'stock_take_date': stock_take_date}, context=context)

        return {'type': 'ir.actions.act_window_close'}


update_lines()
