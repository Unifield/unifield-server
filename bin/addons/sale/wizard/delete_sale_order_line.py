# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
from tools.misc import escape_html
import netsvc
from tools.translate import _


class delete_sale_order_line_wizard(osv.osv_memory):
    _name = 'delete.sale.order.line.wizard'
    _description = 'Delete sale order line'

    _columns = {
    }

    _defaults = {
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        no_cancel_line_btn_name = _('Return to previous screen')
        ok_cancel_line_btn_name = _('OK, cancel line')
        ok_cancel_lines_btn_name = _('OK, cancel lines')
        # integrity check
        assert context, 'No context defined'
        # call super
        result = super(delete_sale_order_line_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # get the line
        so_line = self.pool.get('sale.order.line')
        if hasattr(context, 'lines_ids'):
            line_ids = context.get('lines_ids', [])
        else:
            line_ids = context.get('active_ids', [])

        prev_lines_ids = line_ids
        line_ids = self.filter_sol(cr, uid, line_ids, context=context)

        if not line_ids:
            if not prev_lines_ids:
                return result
            info_string = _('You cannot delete product: %s') % ", ".join([escape_html(sol.product_id.default_code) for sol in so_line.browse(cr, uid, prev_lines_ids)]).strip(', ')
            result['arch'] = """
                <form>
                <separator colspan="6" string="%s"/>
                <button special="cancel" string="%s" icon="gtk-cancel"/>
                </form>""" % (info_string, no_cancel_line_btn_name)
            return result

        if len(line_ids) > 1:
            names = ''
            parent_so_id = 0
            for index, line_id in enumerate(line_ids, start=1):
                line = so_line.browse(cr, uid, line_id, context=context)
                name = _('line %s') % (line.line_number)
                if line.product_id:
                    name = line.product_id.default_code
                if hasattr(line, 'name'):
                    if index == 1:
                        names += name
                        parent_so_id = line.order_id.id
                    elif index == len(line_ids):
                        names += _(' and %s') % (name)
                    else:
                        names += _(', %s') % (name)

            if parent_so_id != 0:
                info_string = _('You are about to cancel the products %s, are you sure you wish to proceed ?') % escape_html(names)
                _moves_arch_lst = """
                                <form>
                                <separator colspan="6" string="%s"/>
                                <button name="fake_unlink" string="%s" type="object" icon="gtk-apply"
                                    context="{'ids': %s, 'order_id': %s}"/>
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                                """ % (info_string, ok_cancel_lines_btn_name, line_ids, parent_so_id, no_cancel_line_btn_name)
                _moves_arch_lst += """</form>"""
                result['arch'] = _moves_arch_lst
        else:
            line = so_line.browse(cr, uid, line_ids[0], context=context)
            name = _('line %s') % (line.line_number)
            if line.product_id:
                name = line.product_id.default_code

            if hasattr(line, 'name'):
                info_string = _('You are about to cancel the product %s, are you sure you wish to proceed ?') % escape_html(name)
                _moves_arch_lst = """
                                <form>
                                <separator colspan="6" string="%s"/>
                                <button name="fake_unlink" string="%s" type="object" icon="gtk-apply" 
                                    context="{'line_id': %s, 'order_id': %s}"/>
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                                """ % (info_string, ok_cancel_line_btn_name, line.id, line.order_id.id, no_cancel_line_btn_name)
                _moves_arch_lst += """</form>"""
                result['arch'] = _moves_arch_lst

        return result

    def filter_sol(self, cr, uid, ids, context=None):
        '''
        filter to keep only sol that can be cancelled
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        to_cancel = []
        for sol in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            if sol.state in ['draft', 'validated']:
                to_cancel.append(sol.id)

        return to_cancel

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        deletes the corresponding line, and asks to cancel the FO if it has no line
        '''
        if context is None:
            context = {}

        wf_service = netsvc.LocalService("workflow")

        if context.get('ids', []) and len(context['ids']) > 1:
            for line_id in self.filter_sol(cr, uid, context.get('ids'), context=context):
                wf_service.trg_validate(uid, 'sale.order.line', line_id, 'cancel', cr)
        else:
            for line_id in self.filter_sol(cr, uid, context.get('line_id', []), context=context):
                wf_service.trg_validate(uid, 'sale.order.line', line_id, 'cancel', cr)

        return {'type': 'ir.actions.act_window_close'}


delete_sale_order_line_wizard()
