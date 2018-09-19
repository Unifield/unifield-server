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
from xml.sax.saxutils import escape
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
            result['arch'] = """
                <form>
                <separator colspan="6" string="%s: %s"/>
                <button special="cancel" string="%s" icon="gtk-cancel"/>
                </form>""" % (_('You cannot delete product'), ", ".join([sol.product_id.default_code for sol in so_line.browse(cr, uid, prev_lines_ids)]).strip(', '), _('Return to previous screen'))
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
                escaped_default_code = escape(names)
                msg = _('You are about to cancel the products %s, are you sure you wish to proceed ?') % escaped_default_code
                _moves_arch_lst = """
                                <form>
                                <separator colspan="6" string="%s"/>
                                <button name="fake_unlink" string="%s" type="object" icon="gtk-apply"
                                    context="{'ids': %s, 'order_id': %s}"/>
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                                """ % (msg, line_ids, _('OK, cancel lines'), parent_so_id, _('Return to previous screen'))
                _moves_arch_lst += """</form>"""
                result['arch'] = _moves_arch_lst
        else:
            line = so_line.browse(cr, uid, line_ids[0], context=context)
            name = _('line %s') % (line.line_number)
            if line.product_id:
                name = line.product_id.default_code

            if hasattr(line, 'name'):
                escaped_default_code = escape(name)
                msg = _('You are about to cancel the product %s, are you sure you wish to proceed ?') % escaped_default_code
                _moves_arch_lst = """
                                <form>
                                <separator colspan="6" string="%s"/>
                                <button name="fake_unlink" string="%s" type="object" icon="gtk-apply" 
                                    context="{'line_id': %s, 'order_id': %s}"/>
                                <button special="cancel" string="%s" icon="gtk-cancel"/>
                                """ % (msg, _('OK, cancel line'), line.id, line.order_id.id, _('Return to previous screen'))
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
