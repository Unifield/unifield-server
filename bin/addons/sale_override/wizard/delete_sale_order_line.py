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

from osv import osv, fields
from product._common import rounding

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
        line_ids = context.get('active_ids', [])

        if not line_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        line_name = so_line.browse(cr, uid, line_ids[0], context=context).name

        _moves_arch_lst = """
                        <form>
                        <separator colspan="6" string="You are about to delete the product %s, are you sure you wish to proceed ?"/>
                        <button name="perm_unlink" string="OK, delete line" type="object" icon="gtk-apply" />
                        <button special="cancel" string="Return to previous screen" icon="gtk-cancel"/>
                        """ % line_name

        _moves_arch_lst += """</form>"""

        result['arch'] = _moves_arch_lst
        return result

delete_sale_order_line_wizard()
