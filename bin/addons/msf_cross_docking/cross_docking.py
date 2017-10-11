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
        'location_id': fields.many2one('stock.location', 'Destination', required=True, domain=[('usage', '<>', 'view')],
                                       help="""This location is set according to the Warehouse selected, or according to the option 'Cross docking'
        or freely if you do not select 'Warehouse'.But if the 'Order category' is set to 'Transport' or 'Service',
        you cannot have an other location than 'Service'"""),
    }

    _defaults = {
        'cross_docking_ok': False,
    }

    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id, categ, dest_partner_id=False, warehouse_id=False, delivery_requested_date=False):
        '''
        Changes destination location
        '''
        res = super(purchase_order, self).onchange_internal_type(cr, uid, ids, order_type, partner_id, categ, dest_partner_id, warehouse_id, delivery_requested_date)
        if order_type == 'direct':
            location_id = self.onchange_cross_docking_ok(cr, uid, ids, False, warehouse_id, categ)['value']['location_id']
            if 'value' in res:
                res['value'].update({'location_id': location_id})
            else:
                res.update({'value': {'location_id': location_id}})
        return res

    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, warehouse_id, categ, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        warning = {}
        if cross_docking_ok:
            c_dock_loc = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
            warning = {
                'title': _('Warning'),
                'message': _('The IR lines to an internal location sourced by one of the lines of this PO will not affected by this modification'),
            }
        else:
            warehouse_obj = self.pool.get('stock.warehouse')
            if not warehouse_id:
                warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
                if not warehouse_ids:
                    return {'warning': {'title': _('Error !'), 'message': _('No Warehouse defined !')}, 'value': {'location_id': False}}
                warehouse_id = warehouse_ids[0]
            if categ not in ('service', 'transport'):
                c_dock_loc = warehouse_obj.read(cr, uid, [warehouse_id], ['lot_input_id'])[0]['lot_input_id'][0]
            else:
                c_dock_loc = self.pool.get('stock.location').get_service_location(cr, uid)
        return {
            'value': {'location_id': c_dock_loc},
            'warning': warning,
        }

    def onchange_location_id(self, cr, uid, ids, location_id, categ, context=None):
        """ If location_id == cross docking we tick the box "cross docking".
        @param location_id: Changed value of location_id.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        stock_loc_obj = self.pool.get('stock.location')
        res = {}
        res['value'] = {}
        if location_id == stock_loc_obj.get_cross_docking_location(cr, uid) and categ not in ['service', 'transport']:
            cross_docking_ok = True
        elif location_id != stock_loc_obj.get_cross_docking_location(cr, uid):
            cross_docking_ok = False
        elif location_id != stock_loc_obj.get_service_location(cr, uid) and categ in ['service', 'transport']:
            return {'warning': {'title': _('Error !'), 'message': _("""
            If the 'Order Category' is 'Service' or 'Transport', you cannot have an other location than 'Service'
            """)}, 'value': {'location_id': stock_loc_obj.get_service_location(cr, uid)}}
        res['value']['cross_docking_ok'] = cross_docking_ok
        return res

    def onchange_categ(self, cr, uid, ids, category, warehouse_id, cross_docking_ok, location_id, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of purchase.order to check
        :param category: DB value of the new choosen category
        :param warehouse_id: ID of the new stock.warehouse of the PO
        :param cross_docking_ok: Boolean to know if the PO is a Cross-Docking PO or not
        :param location_id: ID of the new stock.location of the PO
        :param context: Context of the call
        :return: A dictionary containing the warning message if any
        """
        nomen_obj = self.pool.get('product.nomenclature')
        loc_obj = self.pool.get('stock.location')
        wh_obj = self.pool.get('stock.warehouse')
        setup_obj = self.pool.get('unifield.setup.configuration')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        setup = setup_obj.get_config(cr, uid)

        value = {}
        message = {}

        # Get specific location ID
        cross_loc = False
        service_loc = loc_obj.get_service_location(cr, uid)
        if setup.allocation_setup != 'unallocated':
            cross_loc = loc_obj.get_cross_docking_location(cr, uid)

        if cross_docking_ok:
            value['location_id'] = cross_loc
        elif category in ['service', 'transport']:
            value['location_id'] = service_loc
        elif location_id == service_loc or (setup.allocation_setup != 'unallocated' and location_id == cross_loc):
            if warehouse_id:
                value['location_id'] = wh_obj.read(cr, uid, [warehouse_id], ['lot_input_id'])[0]['lot_input_id'][0]
            else:
                value['location_id'] = False

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
                       (tuple(ids),))
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
        stock_loc_obj = self.pool.get('stock.location')
        if 'order_type' in vals and vals['order_type'] == 'direct':
            vals.update({'cross_docking_ok': False})
        if 'cross_docking_ok' in vals and vals['cross_docking_ok']:
            vals.update({'location_id': stock_loc_obj.get_cross_docking_location(cr, uid)})
        elif 'categ' in vals and vals['categ'] in ['service', 'transport']:
            vals.update({'cross_docking_ok': False, 'location_id': stock_loc_obj.get_service_location(cr, uid)})
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        stock_loc_obj = self.pool.get('stock.location')
        if vals.get('order_type') == 'direct':
            vals.update({'cross_docking_ok': False})
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': stock_loc_obj.get_cross_docking_location(cr, uid)})
        elif 'categ' in vals and vals['categ'] in ['service', 'transport']:
            vals.update({'cross_docking_ok': False, 'location_id': stock_loc_obj.get_service_location(cr, uid)})
        return super(purchase_order, self).create(cr, uid, vals, context=context)

    def _check_cross_docking(self, cr, uid, ids, context=None):
        """
        Check that if you select cross docking, you do not have an other location than cross docking
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        stock_loc_obj = self.pool.get('stock.location')
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        for purchase in self.browse(cr, uid, ids, context=context):
            if purchase.cross_docking_ok:
                if setup.allocation_setup == 'unallocated':
                    raise osv.except_osv(_('Error'), _("""The Allocated stocks setup is set to Unallocated.
In this configuration, you cannot made a Cross-docking Purchase order."""))
                cross_docking_location = stock_loc_obj.get_cross_docking_location(cr, uid)
                if purchase.location_id.id != cross_docking_location:
                    raise osv.except_osv(_('Warning !'), _("""If you tick the box \"cross docking\",
you cannot have an other location than \"Cross docking\""""))
                else:
                    return True
            else:
                return True

    _constraints = [
        (_check_cross_docking, 'If you tick the box \"cross docking\", you cannot have an other location than \"Cross docking\"', ['location_id']),
    ]

purchase_order()


class procurement_order(osv.osv):

    _inherit = 'procurement.order'

    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        When you run the scheduler and you have a sale order line with type = make_to_order,
        we modify the location_id to set 'cross docking' of the purchase order created in mirror
        But if the sale_order is an Internal Request we don't want "Cross docking" but "Input" as location_id (i.e. the location of the warehouse_id)
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        stock_loc_obj = self.pool.get('stock.location')
        sol_obj = self.pool.get('sale.order.line')
        procurement = kwargs['procurement']
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        sol_ids = sol_obj.search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if (procurement.tender_line_id or procurement.rfq_line_id or len(sol_ids)) and setup.allocation_setup != 'unallocated':
            if sol_ids:
                browse_so = sol_obj.browse(cr, uid, sol_ids, context=context)[0].order_id
            elif procurement.tender_line_id and procurement.tender_line_id.tender_id and procurement.tender_line_id.tender_id.sale_order_id:
                browse_so = procurement.tender_line_id.tender_id.sale_order_id
            elif procurement.rfq_line_id and procurement.rfq_line_id.order_id and procurement.rfq_line_id.order_id.sale_order_id:
                browse_so = procurement.rfq_line_id.order_id.sale_order_id

            if browse_so:
                req_loc = browse_so.location_requestor_id
                if not (browse_so.procurement_request and req_loc and req_loc.usage != 'customer'):
                    values.update({'cross_docking_ok': True, 'location_id': stock_loc_obj.get_cross_docking_location(cr, uid)})
                values.update({'priority': browse_so.priority, 'categ': browse_so.categ})
        return values

procurement_order()


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

    def default_get(self, cr, uid, fields, context=None):
        '''
        Fill the unallocated_ok field according to Unifield setup
        '''
        res = super(stock_picking, self).default_get(cr, uid, fields, context=context)
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
                        if move.state != 'done':
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
        self.action_assign(cr, uid, ids, context)
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
                        if move.state != 'done':
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
        self.action_assign(cr, uid, ids, context)
        return False

    def _do_incoming_shipment_first_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        This hook refers to delivery_mechanism>delivery_mechanism.py>_do_incoming_shipment.
        It updates the location_dest_id (to cross docking or to stock)
        of selected stock moves when the linked 'incoming shipment' is validated
        -> only related to 'in' type stock.picking
        '''
        values = super(stock_picking, self)._do_incoming_shipment_first_hook(cr, uid, ids, context=context, *args, **kwargs)
        assert values is not None, 'missing values'
        if context is None:
            context = {}

        # UF-1617: If the case comes from the sync_message, then just return the values, not the wizard stuff
        if context.get('sync_message_execution', False):
            return values

        if isinstance(ids, (int, long)):
            ids = [ids]
        # take ids of the wizard from the context.
        # NB: the wizard_ids is created in delivery_mechanism>delivery_mecanism.py> in the method "_stock_picking_action_process_hook"
        wiz_ids = context.get('wizard_ids')
        res = {}
        if not wiz_ids:
            return res
# ------ check the allocation setup ------------------------------------------------------------------------------
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

# ------ referring to locations 'cross docking' and 'stock' ------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        if setup.allocation_setup != 'unallocated':
            cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        stock_location_input = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        stock_location_service = self.pool.get('stock.location').get_service_location(cr, uid)
        stock_location_non_stockable = self.pool.get('stock.location').search(cr, uid, [('non_stockable_ok', '=', True)])
        if stock_location_non_stockable:
            stock_location_non_stockable = stock_location_non_stockable[0]
# ----------------------------------------------------------------------------------------------------------------
        partial_picking_obj = self.pool.get('stock.partial.picking')
        # We browse over the wizard (stock.partial.picking)
        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            """For incoming shipment """
            # we check the dest_type for INCOMING shipment (and not the source_type which is reserved for OUTGOING shipment)
            if var.dest_type == 'to_cross_docking':
                if setup.allocation_setup == 'unallocated':
                    raise osv.except_osv(_('Error'), _("""You cannot made moves from/to Cross-docking locations
                    when the Allocated stocks configuration is set to \'Unallocated\'."""))
                # below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is
                # "default"and we do not want that info on INCOMING shipment
                var.source_type = None
                product_id = values['product_id']
                product_type = self.pool.get('product.product').read(cr, uid, product_id, ['type'], context=context)['type']
                values.update({'location_dest_id': cross_docking_location})
                values.update({'cd_from_bo': True})
            elif var.dest_type == 'to_stock':
                var.source_type = None
                # below, "source_type" is only used for the outgoing shipment. We set it to "None" because
                #by default it is "default"and we do not want that info on INCOMING shipment
                product_id = values['product_id']
                product_type = self.pool.get('product.product').read(cr, uid, product_id, ['type'], context=context)['type']
                if product_type == 'consu' and stock_location_non_stockable:
                    values.update({'location_dest_id': stock_location_non_stockable})
                elif product_type == 'service_recep' and stock_location_service:
                    values.update({'location_dest_id': stock_location_service})
                else:
                    # treat moves towards STOCK if NOT SERVICE
                    values.update({'location_dest_id': stock_location_input})
                values.update({'cd_from_bo': False})

            # Set the 'Direct to stock' boolean field
            if var.dest_type != 'to_cross_docking':
                values['direct_incoming'] = var.direct_incoming

        return values

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data of the current object, which is stock.picking.
        The defaults data are taken from the _do_partial_hook which is on the stock_partial_picking
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


class stock_move(osv.osv):
    _inherit = 'stock.move'
    """
    The field below 'move_cross_docking_ok' is used solely for the view using attrs. I has been named especially
    'MOVE_cross_docking_ok' for not being in conflict with the other 'cross_docking_ok' in the stock.picking object
    which also uses attrs according to the value of cross_docking_ok'.
    """

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
        'move_cross_docking_ok': fields.boolean('Cross docking'),
        'direct_incoming': fields.boolean('Direct incoming'),
        'allocation_setup': fields.function(_get_allocation_setup, type='selection',
                                            selection=[('allocated', 'Allocated'),
                                                       ('unallocated', 'Unallocated'),
                                                       ('mixed', 'Mixed')], string='Allocated setup', method=True, store=False),
    }

    _defaults = {
        'direct_incoming': False,
    }

    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object:
        If cross docking is checked on the purchase order, we set "cross docking" to the destination location
        else we keep the default values i.e. "Input"
        """
        default_data = super(stock_move, self).default_get(cr, uid, fields, context=context)
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        default_data.update({'allocation_setup': setup.allocation_setup})
        if context is None:
            context = {}
        purchase_id = context.get('purchase_id', [])
        if not purchase_id:
            return default_data
        purchase_browse = self.pool.get('purchase.order').browse(cr, uid, purchase_id, context=context)
        # If the purchase order linked has the option cross docking then the new created
        #stock move should have the destination location to cross docking
        if purchase_browse.cross_docking_ok:
            default_data.update({'location_dest_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})
        return default_data

    @check_cp_rw
    def button_cross_docking(self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to cross docking
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Check the allocation setup
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup.allocation_setup == 'unallocated':
            raise osv.except_osv(_('Error'), _("""You cannot made moves from/to Cross-docking locations
            when the Allocated stocks configuration is set to \'Unallocated\'."""))
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state != 'done':
                todo.append(move.id)
                self.infolog(cr, uid, "The source location of the stock move id:%s has been changed to cross-docking location" % (move.id))
        ret = True
        if todo:
            ret = self.write(cr, uid, todo, {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)

            # we cancel availability
            new_todo = self.cancel_assign(cr, uid, todo, context=context)
            if new_todo:
                todo = new_todo
            # we rechech availability
            self.action_assign(cr, uid, todo, context)
            #FEFO
            self.fefo_update(cr, uid, todo, context)
            # below we cancel availability to recheck it
#            stock_picking_id = self.read(cr, uid, todo, ['picking_id'], context=context)[0]['picking_id'][0]
#            picking_todo.append(stock_picking_id)
#            # we cancel availability
#            self.pool.get('stock.picking').cancel_assign(cr, uid, [stock_picking_id])
#            # we recheck availability
#            self.pool.get('stock.picking').action_assign(cr, uid, [stock_picking_id])
#        if picking_todo:
#            self.pool.get('stock.picking').check_all_move_cross_docking(cr, uid, picking_todo, context=context)
        return ret

    @check_cp_rw
    def button_stock(self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to stock
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state != 'done':
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
                    self.write(cr, uid, move.id, {'location_id': id_loc_s, 'move_cross_docking_ok': False}, context=context)
                else:
                    self.write(cr, uid, move.id, {'location_id': move.picking_id.warehouse_id.lot_stock_id.id,
                                                  'move_cross_docking_ok': False}, context=context)
                todo.append(move.id)
                self.infolog(cr, uid, "The source location of the stock move id:%s has been changed to stock location" % (move.id))
            # below we cancel availability to recheck it

        if todo:
            # we cancel availability
            new_todo = self.cancel_assign(cr, uid, todo, context=context)
            if new_todo:
                todo = new_todo
            # we rechech availability
            self.action_assign(cr, uid, todo)

            #FEFO
            self.fefo_update(cr, uid, todo, context)
#            stock_picking_id = self.read(cr, uid, todo, ['picking_id'], context=context)[0]['picking_id'][0]
#            picking_todo.append(stock_picking_id)
            # we cancel availability
#            self.pool.get('stock.picking').cancel_assign(cr, uid, [stock_picking_id])
            # we recheck availability
#            self.pool.get('stock.picking').action_assign(cr, uid, [stock_picking_id])
#        if picking_todo:
#            self.pool.get('stock.picking').check_all_move_cross_docking(cr, uid, picking_todo, context=context)
        return True

stock_move()
