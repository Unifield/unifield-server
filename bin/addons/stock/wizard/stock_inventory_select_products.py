# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class stock_inventory_select_product(osv.osv_memory):
    _name = "stock.inventory.select.product"
    _description = "Select product to consider for inventory, using filters"
    _columns = {
        'base_filter': fields.selection((('in_stock', "Items currently in stock at that location"),
                                         ('recent_moves', "Items with recent movement at that location")), "Base filter", select=True)
    }

    def open_wizard(self, cr, uid, view_id, context=None):
        '''
        Open the wizard
        '''
        context = {} if context is None else context

        wiz_id = self.create(cr, uid, {}, context=context)
        context['wizard_id'] = wiz_id

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def view_init(self, cr, uid, fields_list, context=None):
        """
        ???
        """
        context = {} if context is None else context
        super(stock_inventory_select_product, self).view_init(cr, uid, fields_list, context=context)
        return True


stock_inventory_select_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
