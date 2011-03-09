#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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


from osv import osv
from osv import fields

from tools.translate import _


class stock_adjustment_type(osv.osv):
    _name = 'stock.adjustment.type'
    _description = 'Inventory/Move Adjustment Types'

    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
    }

stock_adjustment_type()


class stock_inventory_line(osv.osv):
    _name = 'stock.inventory.line'
    _inherit = 'stock.inventory.line'

    _columns = {
        'type_id': fields.many2one('stock.adjustment.type', string='Adjustment type'),
        'comment': fields.char(size=128, string='Comment'),
    }

stock_inventory_line()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    _columns = {
        'type_id': fields.many2one('stock.adjustment.type', string='Adjustment type', readonly=True),
        'comment': fields.char(size=128, string='Comment'),
    }

stock_move()


class stock_inventory(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    # @@@override@ stock.stock_inventory.action_confirm()
    def action_confirm(self, cr, uid, ids, context={}):
        """ Confirm the inventory and writes its finished date
        @return True
        """
        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        location_obj = self.pool.get('stock.location')
        for inv in self.browse(cr, uid, ids, context=context):
            move_ids = []
            for line in inv.inventory_line_id:
                pid = line.product_id.id
                product_context.update(uom=line.product_uom.id,date=inv.date)
                amount = location_obj._product_get(cr, uid, line.location_id.id, [pid], product_context)[pid]
         
                change = line.product_qty - amount
                lot_id = line.prod_lot_id.id
                type_id = line.type_id.id
                if change:
                    location_id = line.product_id.product_tmpl_id.property_stock_inventory.id
                    value = {
                        'name': 'INV:' + str(line.inventory_id.id) + ':' + line.inventory_id.name,
                        'product_id': line.product_id.id,
                        'product_uom': line.product_uom.id,
                        'prodlot_id': lot_id,
                        'date': inv.date,
                        # Add by developer for Unifield
                        'comment': line.comment,
                        # End of adding for Unifield
                    }
                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line.location_id.id,
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line.location_id.id,
                            'location_dest_id': location_id,
                        })
                    if lot_id:
                        value.update({
                            'prodlot_id': lot_id,
                            'product_qty': line.product_qty
                        })
                    # Add by developer for Unifield
                    if type_id:
                        value.update({
                            'type_id': type_id,
                        })
                    # End of adding for Unifield
                    move_ids.append(self._inventory_line_hook(cr, uid, line, value))
            message = _('Inventory') + " '" + inv.name + "' "+ _("is done.")
            self.log(cr, uid, inv.id, message)
            self.write(cr, uid, [inv.id], {'state': 'confirm', 'move_ids': [(6, 0, move_ids)]})
        return True

stock_inventory()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

