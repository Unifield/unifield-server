# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF
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
from order_types.stock import check_cp_rw


class purchase_order(osv.osv):
    '''
    Enables the option cross docking
    '''
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking'),
    }

    _defaults = {
        'cross_docking_ok': False,
    }

    def onchange_categ(self, cr, uid, ids, category, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of purchase.order to check
        :param category: DB value of the new choosen category
        :param context: Context of the call
        :return: A dictionary containing the warning message if any
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        value = {}
        message = {}

        res = False
        if ids and category in ['log', 'medical']:
            try:
                med_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'MED')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('MED nomenclature Main Type not found'))
            try:
                log_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'LOG')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('LOG nomenclature Main Type not found'))

            nomen_id = category == 'log' and log_nomen or med_nomen
            cr.execute('''SELECT l.id
                          FROM purchase_order_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN purchase_order po ON l.order_id = po.id
                          WHERE (t.nomen_manda_0 != %s) AND po.id in %s LIMIT 1''',
                       (nomen_id, tuple(ids)))
            res = cr.fetchall()

        if ids and category in ['service', 'transport']:
            # Avoid selection of non-service producs on Service PO
            category = category == 'service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT l.id
                          FROM purchase_order_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN purchase_order po ON l.order_id = po.id
                          WHERE (t.type != 'service_recep' %s) AND po.id in %%s LIMIT 1''' % transport_cat,
                       (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this PO'),
            })

        return {'value': value, 'warning': message}

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if ('order_type' in vals and vals['order_type'] == 'direct') or \
                ('categ' in vals and vals['categ'] in ['service', 'transport']):
            vals.update({'cross_docking_ok': False})
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if vals.get('order_type') == 'direct' or ('categ' in vals and vals['categ'] in ['service', 'transport']):
            vals.update({'cross_docking_ok': False})
        return super(purchase_order, self).create(cr, uid, vals, context=context)


purchase_order()


class stock_picking(osv.osv):
    '''
    do_partial(=function which is originally called from delivery_mechanism) modification
    for the selection of the LOCATION for IN (incoming shipment) and OUT (delivery orders)
    '''
    _inherit = 'stock.picking'

    def _get_allocation_setup(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the Unifield configuration value
        '''
        res = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        for order in ids:
            res[order] = setup.allocation_setup
        return res

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking'),
        'direct_incoming': fields.boolean('Direct to stock'),
        'allocation_setup': fields.function(_get_allocation_setup, type='selection',
                                            selection=[('allocated', 'Allocated'),
                                                       ('unallocated', 'Unallocated'),
                                                       ('mixed', 'Mixed')], string='Allocated setup', method=True, store=False),
    }

    _defaults = {
        'direct_incoming': False,
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Fill the unallocated_ok field according to Unifield setup
        '''
        res = super(stock_picking, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res.update({'allocation_setup': setup.allocation_setup})
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Here we check if all stock move are in stock or in cross docking
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move')

        cd_ids = move_obj.search(cr, uid, [('picking_id', 'in', ids), ('move_cross_docking_ok', '=', True)], count=True)
        st_ids = move_obj.search(cr, uid, [('picking_id', 'in', ids), ('move_cross_docking_ok', '=', False)], count=True)

        if cd_ids > st_ids:
            vals['cross_docking_ok'] = True
        else:
            vals['cross_docking_ok'] = False

        return super(stock_picking, self).write(cr, uid, ids, vals, context=context)

    @check_cp_rw
    def button_cross_docking_all(self, cr, uid, ids, context=None):
        """
        set all stock moves with the source location to 'cross docking'
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        # Check the allocation setup
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup.allocation_setup == 'unallocated':
            raise osv.except_osv(_('Error'), _("""You cannot made moves from/to Cross-docking
locations when the Allocated stocks configuration is set to \'Unallocated\'."""))
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        for pick in pick_obj.browse(cr, uid, ids, context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1:
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr, uid, [move_ids], context=context):
                        # Don't change done stock moves
                        if move.state not in ['done', 'cancel']:
                            move_obj.write(cr, uid, [move_ids], {'location_id': cross_docking_location,
                                                                 'move_cross_docking_ok': True}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': True}, context=context)
            else:
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to CROSS DOCKING'))
            self.infolog(cr, uid, "The source location of the stock moves of the picking id:%s (%s) has been changed to cross-docking location" % (
                pick.id, pick.name,
            ))
        # we check availability : cancel then check
        self.cancel_assign(cr, uid, ids)
        self.action_assign(cr, uid, ids, context=context)
        return False

    @check_cp_rw
    def button_stock_all(self, cr, uid, ids, context=None):
        """
        set all stock move with the source location to 'stock'
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        for pick in pick_obj.browse(cr, uid, ids, context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1:
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr, uid, [move_ids], context=context):
                        if move.state not in ['done', 'cancel']:
                            '''
                            Specific rules for non-stockable products:
                               * if the move is an outgoing delivery, picked them from cross-docking
                               * else picked them from the non-stockable location
                            '''
                            if move.product_id.type in ('consu', 'service_recep'):
                                if move.picking_id.type == 'out':
                                    id_loc_s = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
                                elif move.product_id.type == 'consu':
                                    id_loc_s = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
                                else:
                                    id_loc_s = self.pool.get('stock.location').get_service_location(cr, uid)
                                move_obj.write(cr, uid, [move_ids], {'location_id': id_loc_s, 'move_cross_docking_ok': False}, context=context)
                            else:
                                move_obj.write(cr, uid, [move_ids], {'location_id': pick.warehouse_id.lot_stock_id.id,
                                                                     'move_cross_docking_ok': False}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': False}, context=context)
            else:
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to STOCK'))
            self.infolog(cr, uid, "The source location of the stock moves of the picking id:%s (%s) has been changed to stock location" % (
                pick.id, pick.name,
            ))
        # we check availability : cancel then check
        self.cancel_assign(cr, uid, ids)
        self.action_assign(cr, uid, ids, context=context)
        return False


    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data of the current object, which is stock.picking.
        osv_memory object used for the wizard of deliveries.
        For outgoing shipment
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'
        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        # location_id is equivalent to the source location: does it exist when we go through the "_do_partial_hook" in the msf_cross_docking> stock_partial_piking> "do_partial_hook"
        location_id = partial_datas.get('move%s'%(move.id), {}).get('location_id')
        if location_id:
            defaults.update({'location_id': location_id})
        return defaults

    def check_all_move_cross_docking(self, cr, uid, ids, context=None):
        '''
        Check if all stock moves are cross docking or to stock, in this case, the picking will be updated
        '''
        stock_todo = []
        cross_todo = []
        for pick in self.browse(cr, uid, ids, context=context):
            to_cross = True
            to_stock = True
            for move in pick.move_lines:
                to_cross = move.move_cross_docking_ok
                to_stock = not move.move_cross_docking_ok
            if to_cross:
                cross_todo.append(pick.id)
            if to_stock:
                cross_todo.append(pick.id)
        if stock_todo:
            self.write(cr, uid, stock_todo, {'cross docking_ok': False})
        if cross_todo:
            self.write(cr, uid, cross_todo, {'cross docking_ok': True})
        return True

stock_picking()

