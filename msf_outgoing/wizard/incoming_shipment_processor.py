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

from osv import fields
from osv import osv
from tools.translate import _


class stock_incoming_processor(osv.osv):
    """
    Incoming shipment processing wizard
    """
    _name = 'stock.incoming.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process an incoming shipment'

    _columns = {
        'move_ids': fields.one2many(
            'stock.move.in.processor',
            'wizard_id',
            string='Moves',
        ),
        'dest_type': fields.selection([
            ('to_cross_docking', 'To Cross Docking'),
            ('to_stock', 'To Stock'),
            ('default', 'Other Types'),
            ],
            string='Destination Type',
            readonly=False,
            help="The default value is the one set on each stock move line.",
        ),
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'),
            ],
            string='Source Type',
            readonly=False,
        ),
        'direct_incoming': fields.boolean(
            string='Direct to Stock ?',
        ),
    }

    _defaults = {
        'dest_type': 'default',
        'direct_incoming': True,
    }

    # Models methods
    def create(self, cr, uid, vals, context=None):
        """
        Update the dest_type value according to picking
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')

        if not vals.get('picking_id', False):
            raise osv.except_osv(
                _('Error'),
                _('No picking defined !'),
            )

        picking = picking_obj.browse(cr, uid, vals.get('picking_id'), context=context)

        if not vals.get('dest_type', False):
            if not picking.backorder_id:
                if picking.purchase_id and picking.purchase_id.cross_docking_ok:
                    vals['dest_type'] = 'to_cross_docking'
                elif picking.purchase_id:
                    vals['dest_type'] = 'to_stock'
            elif picking.cd_from_bo:
                vals['dest_type'] = 'to_cross_docking'
            elif not picking.cd_from_bo:
                vals['dest_type'] = 'to_stock'

        if not vals.get('source_type', False):
            vals['source_type'] = 'default'

        return super(stock_incoming_processor, self).create(cr, uid, vals, context=context)

    def _get_prodlot_from_expiry_date(self, cr, uid, expiry_date, product_id, context=None):
        """
        Search if an internal batch exists in the system with this expiry date.
        If no, create the batch.
        """
        # Objects
        lot_obj = self.pool.get('stock.production.lot')
        seq_obj = self.pool.get('ir.sequence')

        # Double check to find the corresponding batch
        lot_ids = lot_obj.search(cr, uid, [
                            ('life_date', '=', expiry_date),
                            ('type', '=', 'internal'),
                            ('product_id', '=', product_id),
                            ], context=context)

        # No batch found, create a new one
        if not lot_ids:
            vals = {
                'product_id': product_id,
                'life_date': expiry_date,
                'name': seq_obj.get(cr, uid, 'stock.lot.serial'),
                'type': 'internal',
            }
            lot_id = lot_obj.create(cr, uid, vals, context)
        else:
            lot_id = lot_ids[0]

        return lot_id

    def do_incoming_shipment(self, cr, uid, ids, context=None):
        """
        Made some integrity check on lines and run the do_incoming_shipment of stock.picking
        """
        # Objects
        in_proc_obj = self.pool.get('stock.move.in.processor')
        picking_obj = self.pool.get('stock.picking')

        to_unlink = []

        for proc in self.browse(cr, uid, ids, context=context):
            total_qty = 0.00

            for line in proc.move_ids:
                # If one line as an error, return to wizard
                if line.integrity_status != 'empty':
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': proc._name,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'res_id': line.wizard_id.id,
                        'target': 'new',
                        'context': context,
                    }

            for line in proc.move_ids:
                # if no quantity, don't process the move
                if not line.quantity:
                    to_unlink.append(line.id)
                    continue

                total_qty += line.quantity

                if line.exp_check \
                   and not line.lot_check \
                   and not line.prodlot_id \
                   and line.expiry_date:
                    if line.type_check == 'in':
                        prodlot_id = self._get_prodlot_from_expiry_date(cr, uid, line.expiry_date, line.product_id.id, context=context)
                        in_proc_obj.write(cr, uid, [line.id], {'prodlot_id': prodlot_id}, context=context)
                    else:
                        # Should not be reached thanks to UI checks
                        raise osv.except_osv(
                            _('Error !'),
                            _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...')
                        )

            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _("You have to enter the quantities you want to process before processing the move")
                )

        if to_unlink:
            in_proc_obj.unlink(cr, uid, to_unlink, context=context)

        return picking_obj.do_incoming_shipment(cr, uid, ids, context=context)

    """
    Controller methods
    """
    def onchange_dest_type(self, cr, uid, ids, dest_type, picking_id=False, context=None):
        """
        Raise a message if the user change a default dest type (cross docking or IN stock).
        @param dest_type: Changed value of dest_type.
        @return: Dictionary of values.
        """
        # Objects
        pick_obj = self.pool.get('stock.picking')
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

        if context is None:
            context = {}

        if not picking_id:
            return {}

        result = {}

        picking = pick_obj.browse(cr, uid, picking_id, context=context)
        if picking.purchase_id and dest_type != 'to_cross_docking'and picking.purchase_id.cross_docking_ok:
            # display warning
            result['warning'] = {
                'title': _('Error'),
                'message': _('You want to receive the IN on an other location than Cross Docking but "Cross docking" was checked.')
            }
        elif picking.purchase_id and dest_type == 'to_cross_docking' and not picking.purchase_id.cross_docking_ok:
            # display warning
            result['warning'] = {
                'title': _('Error'),
                'message': _('You want to receive the IN on Cross Docking but "Cross docking" was not checked.')
            }

        if dest_type == 'to_cross_docking' and setup.allocation_setup == 'unallocated':
            result['value'].update({
                'dest_type': 'default'
            })

            result['warning'] = {'title': _('Error'),
                                 'message': _('The Allocated stocks setup is set to Unallocated.' \
'In this configuration, you cannot made moves from/to Cross-docking locations.')
            }

        return result

    def launch_simulation(self, cr, uid, ids, context=None):
        '''
        Launch the simulation screen
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No picking defined.')
            )

        pick_obj = self.pool.get('stock.picking')
        simu_obj = self.pool.get('wizard.import.in.simulation.screen')
        line_obj = self.pool.get('wizard.import.in.line.simulation.screen')

        for wizard in self.browse(cr, uid, ids, context=context):
            picking_id = wizard.picking_id.id

            simu_id = simu_obj.create(cr, uid, {'picking_id': picking_id, }, context=context)
            for move in pick_obj.browse(cr, uid, picking_id, context=context).move_lines:
                if move.state not in ('draft', 'cancel', 'done'):
                    line_obj.create(cr, uid, {'move_id': move.id,
                                              'simu_id': simu_id,
                                              'move_product_id': move.product_id and move.product_id.id or False,
                                              'move_product_qty': move.product_qty or 0.00,
                                              'move_uom_id': move.product_uom and move.product_uom.id or False,
                                              'move_price_unit': move.price_unit or move.product_id.standard_price,
                                              'move_currency_id': move.price_currency_id and move.price_currency_id.id or False,
                                              'line_number': move.line_number, }, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.in.simulation.screen',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'same',
                'res_id': simu_id,
                'context': context}

stock_incoming_processor()


class stock_move_in_processor(osv.osv):
    """
    Incoming moves processing wizard
    """
    _name = 'stock.move.in.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard lines for incoming shipment processing'

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'stock.incoming.processor',
            string='Wizard',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
        ),
        'state': fields.char(size=32, string='State', readonly=True),
    }

    """
    Model methods
    """
    def _get_line_data(self, cr, uid, wizard=False, move=False, context=None):
        """
        Update the unit price and the currency of the move line wizard if the
        move is attached to a purchase order line
        """
        line_data = super(stock_move_in_processor, self)._get_line_data(cr, uid, wizard, move, context=context)
        if wizard.picking_id.purchase_id and move.purchase_line_id and move.product_id.cost_method == 'average':
            line_data.update({
                'cost': move.purchase_line_id.price_unit,
                'currency': wizard.picking_id.purchase_id.pricelist_id.currency_id.id,
            })

        return line_data

stock_move_in_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

