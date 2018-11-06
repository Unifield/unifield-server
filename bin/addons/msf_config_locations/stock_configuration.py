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
from osv import fields

from tools.translate import _

class stock_location(osv.osv):
    '''
    Change the order and parent_order field.
    '''
    _name = "stock.location"
    _inherit = 'stock.location'
    _parent_order = 'location_id, posz'
    _order = 'location_id, posz'


    def _get_input_output(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the location is the input/output location of a warehouse or a children of it
        '''
        res = {}
        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        output_loc = []
        input_loc = []
        for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
            output_loc.extend(self.search(cr, uid, [('location_id', 'child_of', wh.lot_output_id.id)]))
            input_loc.extend(self.search(cr, uid, [('location_id', 'child_of', wh.lot_input_id.id)]))

        for id in ids:
            if field_name == 'output_ok':
                res[id] = id in output_loc
            elif field_name == 'input_ok':
                res[id] = id in input_loc
            else:
                res[id] = False

        return res

    def _src_input_output(self, cr, uid, obj, name, args, context=None):
        '''
        Return all input/output locations
        '''
        res = []
        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        output_loc = []
        input_loc = []
        for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
            output_loc.extend(self.search(cr, uid, [('location_id', 'child_of', wh.lot_output_id.id)]))
            input_loc.extend(self.search(cr, uid, [('location_id', 'child of', wh.lot_input_id.id)]))

        operator = 'in'
        if (args[0][1] == '=' and args[0][2] == False) or (args[0][1] and '!=' and args[0][2] == True):
            operator = 'not in'

        if args[0][0] == 'output_ok':
            return [('id', operator, output_loc)]
        elif args[0][0] == 'input_ok':
            return [('id', operator, input_loc)]

        return res

    def _get_virtual(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the location is under the Virtual locations view
        '''
        res = {}
        try:
            virtual_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_locations_virtual')[1]
            virtual_ids = self.search(cr, uid, [('location_id', 'child_of', virtual_id)], context=context)
        except:
            virtual_ids = []
        for id in ids:
            res[id] = False
            if id in virtual_ids:
                res[id] = True

        return res

    def _src_virtual(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all virtual locations
        '''
        res = []
        try:
            virtual_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_locations_virtual')[1]
            virtual_ids = self.search(cr, uid, [('location_id', 'child_of', virtual_id)], context=context)
        except:
            return res

        operator = 'in'
        if (args[0][1] == '=' and args[0][2] == False) or (args[0][1] and '!=' and args[0][2] == True):
            operator = 'not in'

        return [('id', operator, virtual_ids)]

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        '''
        Set all object to true
        '''
        res = {}
        for id in ids:
            res[id] = True
        return res

    def _src_pick_src(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the available locations for source location of a picking ticket according to the product.
        '''
        res = [('usage', '=', 'internal')]
        for arg in args:
            if arg[0] == 'picking_ticket_src' and arg[1] == '=':
                if arg[2] == False:
                    break
                if type(arg[2]) != type(1):
                    raise osv.except_osv(_('Error'), _('Bad operand'))
                product = self.pool.get('product.product').browse(cr, uid, arg[2])
                if product.type in ('service_recep', 'consu'):
                    res = [('cross_docking_location_ok', '=', True)]
                else:
                    res = [('usage', '=', 'internal'), ('quarantine_location', '=', False), ('output_ok', '=', False)]

        return res

    def _dest_inc_ship(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the available locations for destination location of an incoming shipment according to the product.
        '''
        res = ['|', '|', '|', '|', ('usage', '=', 'internal'), ('service_location', '=', True), ('non_stockable_ok', '=', True), ('cross_docking_location_ok', '=', True), ('virtual_ok', '=', True)]
        for arg in args:
            if arg[0] == 'incoming_dest' and arg[1] == '=':
                if arg[2] == False:
                    break
                if type(arg[2]) != type(1):
                    raise osv.except_osv(_('Error'), _('Bad operand'))
                product = self.pool.get('product.product').browse(cr, uid, arg[2])
                if product.type in ('service', 'service_recep'):
                    res = ['|', ('cross_docking_location_ok', '=', True), ('service_location', '=', True)]
                elif product.type == 'consu':
                    res = ['|', '|', ('cross_docking_location_ok', '=', True), ('non_stockable_ok', '=', True), ('virtual_ok', '=', True)]
                else:
                    res = [('non_stockable_ok', '=', False), '|', ('usage', '=', 'internal'), ('virtual_ok', '=', True)]

        return res

    def _src_out(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the available locations for source location of an outgoing delivery according to the product
        '''
        res = ['|', ('cross_docking_location_ok', '=', True), ('usage', '=', 'internal'), ('quarantine_location', '=', False), ('output_ok', '=', False), ('input_ok', '=', False)]
        for arg in args:
            # TODO: Refactorize this
            if arg[0] == 'outgoing_src' and arg[1] == '=':
                if arg[2] == False:
                    break
                if type(arg[2]) != type(1):
                    raise osv.except_osv(_('Error'), _('Bad operand'))
                product = self.pool.get('product.product').browse(cr, uid, arg[2])
                if product.type in ('service_recep', 'consu'):
                    # Cross-docking locations
                    res = [('cross_docking_location_ok', '=' ,True)]
                else:
                    # All internal locations except Quarantine (both), Output (& children) and Input locations
                    res = [('usage', '=', 'internal'), ('quarantine_location', '=', False), ('output_ok', '=', False), ('input_ok', '=', False)]

        return res

    def _dest_out(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the available locations for destination location of an outgoing delivery according to the partner in context
        '''
        res = []
        for arg in args:
            if arg[0] == 'outgoing_dest' and arg[1] == '=':
                if not context.get('partner_id'):
                    break
                partner_id = context.get('partner_id')
                if partner_id == self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id:
                    res = [('location_category', '=', 'consumption_unit'), ('usage', '=', 'customer')]

        if not res:
            wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
            output_loc = []
            for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
                output_loc.append(wh.lot_output_id.id)
            res = ['|', ('id', 'in', output_loc), '&', '&', ('usage', '!=', 'view'), ('usage', '=', 'customer'), ('location_category', '!=', 'consumption_unit')]

        return res

    def _src_int(self, cr, uid, obj, name, args, context=None):
        '''
        Return the available locations for source location of an internal picking according to the product
        '''
        res = [('service_location', '=', False), '|', '|', '|', ('cross_docking_location_ok', '=', True), ('quarantine_location', '=', True), ('usage', '=', 'internal'), ('virtual_ok', '=', True)]
        for arg in args:
            if arg[0] == 'internal_src' and arg[1] == '=':
                if arg[2] == False:
                    break
                if type(arg[2]) != type(1):
                    raise osv.except_osv(_('Error'), _('Bad operand'))
                product = self.pool.get('product.product').browse(cr, uid, arg[2])
                if product.type == 'consu':
                    # Cross docking and quarantine locations
                    res = [('service_location', '=', False), '|', ('cross_docking_location_ok', '=', True), ('quarantine_location', '=', True)]
                elif product.type == 'service_recep':
                    # Cross docking locations
                    res = [('cross_docking_location_ok', '=', True)]
                else:
                    # All internal and virtual locations
                    res = [('non_stockable_ok', '=', False), ('service_location', '=', False), '|', ('usage', '=', 'internal'), ('virtual_ok', '=', True)]

        return res

    def _dest_int(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the available locations for destination location of an internal picking according to the product
        '''
        # Inventory, destruction, quarantine and all internal and virtual locations
        res = [('service_location', '=', False), '|', '|', '|', ('usage', 'in', ('internal', 'inventory')), ('destruction_location', '=', True), ('quarantine_location', '=', True), ('virtual_ok', '=', True)]
        for arg in args:
            if arg[0] == 'internal_dest' and arg[1] == '=':
                if arg[2] == False:
                    break
                if type(arg[2]) != type(1):
                    raise osv.except_osv(_('Error'), _('Bad operand'))
                product = self.pool.get('product.product').browse(cr, uid, arg[2])
                if product.type == 'consu':
                    # Inventory, destruction and quarantine location
                    res = [('service_location', '=', False), '|', '|', ('usage', '=', 'inventory'), ('destruction_location', '=', True), ('quarantine_location', '=', True)]
                elif product.type == 'service_recep':
                    # Service location
                    res = [('service_location', '=', True)]
                else:
                    # All internal and virtual locations
                    res = [('non_stockable_ok', '=', False), ('service_location', '=', False), '|', ('usage', '=', 'internal'), ('virtual_ok', '=', True)]

        return res

    def _get_warehouse_input(self, cr, uid, ids, context=None):
        res = []
        for wh in self.browse(cr, uid, ids, context=context):
            res.append(wh.lot_input_id.id)

        input_ids = self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True), ('active', 'in', ('t', 'f'))])
        res.extend(input_ids)

        return res

    def _get_warehouse_output(self, cr, uid, ids, context=None):
        res = []
        for wh in self.browse(cr, uid, ids, context=context):
            res.append(wh.lot_output_id.id)

        output_ids = self.pool.get('stock.location').search(cr, uid, [('output_ok', '=', True), ('active', 'in', ('t', 'f'))])
        res.extend(output_ids)

        return res

    _columns = {
        'central_location_ok': fields.boolean(string='If check, all products in this location are unallocated.'),
        'non_stockable_ok': fields.boolean(string='Non-stockable', help="If checked, the location will be used to store non-stockable products"),
        'output_ok': fields.function(_get_input_output, method=True, string='Output Location', type='boolean',
                                     store={'stock.location': (lambda self, cr, uid, ids, c={}: ids, ['location_id'], 20),
                                            'stock.warehouse': (_get_warehouse_output, ['lot_input_id'], 10)},
                                     help='If checked, the location is the output location of a warehouse or a children.'),
        'input_ok': fields.function(_get_input_output,  method=True, string='Input Location', type='boolean',
                                    store={'stock.location': (lambda self, cr, uid, ids, c={}: ids, ['location_id'], 20),
                                           'stock.warehouse': (_get_warehouse_input, ['lot_input_id'], 10)},
                                    help='If checked, the location is the input location of a warehouse or a children.'),
        'virtual_ok': fields.function(_get_virtual,  method=True, string='Virtual Location', type='boolean',
                                      store={'stock.location': (lambda self, cr, uid, ids, c={}: ids, ['location_id'], 20)},
                                      help='If checked, the location is a virtual location.'),
        'picking_ticket_src': fields.function(_get_dummy, fnct_search=_src_pick_src, method=True, string='Picking Ticket Src. Loc.', type='boolean',
                                              help='Returns the available locations for source location of a picking ticket according to the product.'),
        'incoming_dest': fields.function(_get_dummy, fnct_search=_dest_inc_ship, method=True, string='Incoming shipment Dest. Loc.', type='boolean',
                                         help="Returns the available locations for destination location of an incoming shipment according to the product."),
        'outgoing_src': fields.function(_get_dummy, fnct_search=_src_out, method=True, string='Outgoing delivery Src. Loc.', type='boolean',
                                        help='Returns the available locations for source location of an outgoing delivery according to the product.'),
        'outgoing_dest': fields.function(_get_dummy, fnct_search=_dest_out, method=True, string='Outgoing delivery Dest. Loc.', type='boolean',
                                         help='Returns the available locations for destination location of an outgoing delivery according to the address.'),
        'internal_src': fields.function(_get_dummy, fnct_search=_src_int, method=True, string='Internal Picking Src. Loc.', type='boolean',
                                        help='Returns the available locations form source loctaion of an internal picking according to the product.'),
        'internal_dest': fields.function(_get_dummy, fnct_search=_dest_int, method=True, string='Internal Picking Dest. Loc.', type='boolean',
                                         help='Returns the available locations for destination location of an internal picking according to the product.'),
    }

    def create(self, cr, uid, vals=None, context=None):
        """
        Remove the whitespaces before and after the name of the location
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param vals: Values to be put on the new location
        :param context: Context of the call
        :return: Result of the super() call
        """
        if context is None:
            context = {}

        lang_obj = self.pool.get('res.lang')

        if vals and vals.get('name'):
            loc_name = vals.get('name', '').strip()
            lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True), ('active', '=', True)], context=context)
            if lang_ids:
                langs = lang_obj.browse(cr, uid, lang_ids, fields_to_fetch=['code'], context=context)
                for lang in langs:
                    if self.search_exist(cr, uid, [('name', '=ilike', loc_name)], context={'lang': lang.code}):
                        raise osv.except_osv(_('Warning'), _('A location with a similar name already exists.'))
            else:
                if self.search_exist(cr, uid, [('name', '=ilike', loc_name)], context=context):
                    raise osv.except_osv(_('Warning'), _('A location with a similar name already exists.'))
            vals['name'] = loc_name

        return super(stock_location, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals=None, context=None):
        """
        Remove the whitespaces before and after the name of the location
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of stock.location ID to be updated
        :param vals: Values to be put on the new location
        :param context: Context of the call
        :return: Result of the super() call
        """
        if context is None:
            context = {}

        if not ids:
            return True

        lang_obj = self.pool.get('res.lang')

        if vals and vals.get('name'):
            for loc_id in ids:
                loc_name = vals.get('name', '').strip()
                lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True), ('active', '=', True)], context=context)
                if lang_ids:
                    langs = lang_obj.browse(cr, uid, lang_ids, fields_to_fetch=['code'], context=context)
                    for lang in langs:
                        if self.search_exist(cr, uid, [('id', '!=', loc_id), ('name', '=ilike', loc_name)],
                                             context={'lang': lang.code}):
                            raise osv.except_osv(_('Warning'), _('A location with a similar name already exists.'))
                else:
                    if self.search_exist(cr, uid, [('id', '!=', loc_id), ('name', '=ilike', loc_name)], context=context):
                        raise osv.except_osv(_('Warning'), _('A location with a similar name already exists.'))
                vals['name'] = loc_name

        return super(stock_location, self).write(cr, uid, ids, vals, context=context)


stock_location()


class stock_location_configuration_wizard(osv.osv_memory):
    _name = 'stock.location.configuration.wizard'
    _inherit = 'res.config'

    _columns = {
        'location_name': fields.char(size=64, string='Location name', required=True),
        'location_usage': fields.selection([('stock', 'Stock'), ('consumption_unit', 'Consumption Unit'), ('eprep', 'EPREP')],
                                           string='Location usage'),
        'location_type': fields.selection([('internal', 'Internal'), ('customer', 'External')], string='Location type'),
        'location_id': fields.many2one('stock.location', string='Inactive location to re-activate'),
        'reactivate': fields.boolean(string='Reactivate location ?'),
    }

    _defaults = {
        'reactivate': lambda *a: False,
    }

    def action_add(self, cr, uid, ids, context=None):
        self.confirm_creation(cr, uid, ids[0], context=context)
        return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'stock.location.configuration.wizard',
            'view_id':self.pool.get('ir.ui.view')\
            .search(cr,uid,[('name','=','Configurable Locations Configuration')]),
            'type': 'ir.actions.act_window',
            'target':'new',
        }

    def action_stop(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.confirm_creation(cr, uid, ids, context=context)
        return self.action_next(cr, uid, ids, context=context)

    def execute(self, cr, uid, ids, context=None):
        pass

    def name_on_change(self, cr, uid, ids, location_name, usage, type, context=None):
        '''
        Check if a location with the same parameter exists on
        the instance warehouse
        '''
        res = {}
        warning = {}
        location_obj = self.pool.get('stock.location')

        if location_name:
            inactive_location_ids = location_obj.search(cr, uid, [('name', '=', location_name),
                                                                  ('active', '=', False),
                                                                  ('usage', '=', usage or 'internal'),
                                                                  ('location_category', '=', type)], context=context)
            active_location_ids = location_obj.search(cr, uid, [('name', '=', location_name),
                                                                ('usage', '=', usage or 'internal'),
                                                                ('location_category', '=', type)], context=context)

            if inactive_location_ids:
                warning.update({'title': _('Warning !'),
                                'message': _('An existing but inactive location already exists with the same parameters ! '\
                                             'Please, change the name of the new location, or re-activate the existing location '\
                                             'by clicking on \'Re-activate\' button.')})
                res.update({'reactivate': True, 'location_id': inactive_location_ids[0]})
            elif active_location_ids:
                warning.update({'title': _('Error !'),
                                'message': _('A location with the same name and the parameters already exists and is active. '\
                                             'You cannot have two locations with the same name and parameters. ' \
                                             'Please change the name of the new location before create it.')})
                res.update({'reactivate': False, 'loc_exists': True})
            else:
                res.update({'reactivate': False, 'location_id': False})

        return {'value': res,
                'warning': warning}

    def confirm_creation2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context.update({'reactivate_loc': True})
        return self.confirm_creation(cr, uid, ids, context=context)

    def confirm_creation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        #US-702: This action can only be done in RW instances
        picking_obj = self.pool.get('stock.picking')
        usb_entity = picking_obj._get_usb_entity_type(cr, uid)
        if usb_entity == picking_obj.REMOTE_WAREHOUSE:
            raise osv.except_osv(_('Info!'), _('This action can only be performed at the main instance (CP) and sync to RW!'))

        data_obj = self.pool.get('ir.model.data')
        location_obj = self.pool.get('stock.location')
        parent_location_id = False
        location_category = False
        location_usage = False
        location_name = False
        chained_location_type = 'none'
        chained_auto_packing = 'manual'
        chained_picking_type = 'internal'
        chained_location_id = False
        location = False

        for wizard in self.browse(cr, uid, ids, context=context):
            # Check if errors on location name
            errors = self.name_on_change(cr, uid, ids, wizard.location_name, wizard.location_type, wizard.location_usage, context=context)
            warning = errors.get('warning', {})
            values = errors.get('value', {})
            if warning and (values.get('loc_exists', False) or (values.get('reactivate', True) and not context.get('reactivate_loc', False))):
                raise osv.except_osv(errors.get('warning', {}).get('title', ''), errors.get('warning', {}).get('message', ''))
            # Returns an error if no given location name
            if not wizard.location_name:
                #                # Raise error if location with the same name and the same parameters already exists
                #                if location_obj.search(cr, uid, [('name', '=', wizard.location_name),
                #                                                 ('usage', '=', wizard.location_type or 'internal'),
                #                                                 ('location_category', '=', wizard.location_usage)], context=context):
                raise osv.except_osv(_('Error'), _('You should give a name for the new location !'))
            location = wizard.location_id
            location_name = wizard.location_name
            # Check if all parent locations are activated in the system
            if wizard.location_usage in ('stock', 'eprep') or (wizard.location_type == 'internal' and wizard.location_usage == 'consumption_unit'):
                # Check if 'Configurable locations' location is active − If not, activate it !
                location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')
                if not location_id:
                    raise osv.except_osv(_('Error'), _('Location \'Configurable locations\' not found in the instance or is not activated !'))

                if not location_obj.browse(cr, uid, location_id, context=context).active:
                    location_obj.write(cr, uid, [location_id[1]], {'active': True}, context=context)

                if wizard.location_usage in ('stock', 'eprep'):
                    #                    if wizard.location_usage == 'stock':
                    location_category = 'stock'
                    location_usage = 'internal'
                    # Check if 'Intermediate Stocks' is active − If note activate it !
                    parent_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')
#                    else:
#                        location_stock_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
#                        if not location_stock_id:
#                            raise osv.except_osv(_('Error'), _('Location \'Stock\' not found in the instance or is not activated !'))
#                        location_category = 'eprep'
#                        location_usage = 'internal'
#                        chained_location_type = 'fixed'
#                        chained_auto_packing = 'manual'
#                        chained_picking_type = 'internal'
#                        chained_location_id = location_stock_id[1]
#                        parent_location_id = location_id

                    if not parent_location_id:
                        raise osv.except_osv(_('Error'), _('Location \'Intermediate Stocks\' not found in the instance or is not activated !'))

                    parent_location_id = parent_location_id[1]

                    if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                        location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
                elif wizard.location_usage == 'consumption_unit':
                    location_category = 'consumption_unit'
                    location_usage = 'internal'
                    # Check if 'Internal Consumption Units' is active − If note activate it !
                    parent_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')

                    parent_location_id = parent_location_id[1]

                    if not parent_location_id:
                        raise osv.except_osv(_('Error'), _('Location \'Internal Consumption Units\' not found in the instance or is not activated !'))

                    if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                        location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
                else:
                    raise osv.except_osv(_('Error'), _('The type of the new location is not correct ! Please check the parameters and retry.'))
            elif wizard.location_type == 'customer' and wizard.location_usage == 'consumption_unit':
                location_category = 'consumption_unit'
                location_usage = 'customer'
                chained_picking_type = 'out'
                # Check if 'MSF Customer' location is active − If not, activate it !
                parent_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
                if not parent_location_id:
                    raise osv.except_osv(_('Error'), _('Location \'MSF Customer\' not found in the instance or is not activated !'))

                parent_location_id = parent_location_id[1]

                if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                    location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
            else:
                raise osv.except_osv(_('Error'), _('The type of the new location is not correct ! Please check the parameters and retry.'))

        if not parent_location_id or not location_category or not location_usage:
            raise osv.except_osv(_('Error'), _('Parent stock location not found for the new location !'))

        if not location:
            # Create the new location
            location_obj.create(cr, uid, {'name': location_name,
                                          'location_id': parent_location_id,
                                          'location_category': location_category,
                                          'usage': location_usage,
                                          'chained_location_type': chained_location_type,
                                          'chained_auto_packing': chained_auto_packing,
                                          'chained_picking_type': chained_picking_type,
                                          'chained_location_id': chained_location_id,
                                          'optional_loc': True,
                                          }, context=context)
        else:
            # Reactivate the location
            location_obj.write(cr, uid, [location.id], {'active': True}, context=context)

        return_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_location_tree')

        if return_view_id:
            return {'type': 'ir.actions.act_window',
                    'name': 'Locations Structure',
                    'res_model': 'stock.location',
                    'domain': [('location_id','=',False)],
                    'view_type': 'tree',
                    'target': 'crush',
                    'view_id': [return_view_id[1]],
                    }
        else:
            return {'type': 'ir.actions.act_window'}

stock_location_configuration_wizard()


class stock_remove_location_wizard(osv.osv_memory):
    _name = 'stock.remove.location.wizard'

    _columns = {
        'location_id': fields.many2one('stock.location', string='Location to remove'),
        'location_usage': fields.selection([('internal', 'Internal'), ('customer', 'External')], string='Location type'),
        'location_category': fields.selection([('eprep', 'EPREP'), ('stock', 'Stock'), ('consumption_unit', 'Consumption Unit')],
                                              string='Location type'),
        'error_message': fields.text(string='Information Message', readonly=True),
        'error': fields.boolean(string='Error'),
        'can_force': fields.boolean(string='Can force'),
        'move_from': fields.boolean(string='Has a move from the location'),
        'move_to': fields.boolean(string='Has a move to the location'),
        'not_empty': fields.boolean(string='Location not empty'),
        'has_child': fields.boolean(string='Location has children locations'),
        'related_ir': fields.boolean(string='Location has related IR open'),
    }

    def location_id_on_change(self, cr, uid, ids, location_id, context=None):
        '''
        Check if no moves to this location aren't done
        Check if there is no stock in this location
        '''
        res = {'error_message': '',
               'move_from': False,
               'move_to': False,
               'not_empty': False,
               'has_child': False,
               'related_ir': False}
        warning = {}
        error = False
        can_force = False

        if location_id:
            location = self.pool.get('stock.location').browse(cr, uid, location_id, context=context)

            # Check if no moves to this location aren't done
            move_from = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ('done', 'cancel')), ('location_id', '=', location.id)])
            if move_from:
                error = True
                res['move_from'] = True
                res['error_message'] += '''* You have at least one move from the location '%s' which is not 'Done'.
Please click on the 'See moves' button to see which moves are still in progress from this location.''' %location.name
                res['error_message'] += '\n' + '\n'

            move_to = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ('done', 'cancel')), ('location_dest_id', '=', location.id)])
            if move_to:
                error = True
                can_force = True
                res['move_to'] = True
                res['error_message'] += '''* You have at least one move to the location '%s' which is not 'Done'.
Please click on the 'See moves' button to see which moves are still in progress to this location.''' %location.name
                res['error_message'] += '\n' + '\n'

            # Check if no stock in the location
            if location.stock_real and location.usage == 'internal':
                error = True
                res['not_empty'] = True
                res['error_message'] += '''* The location '%s' is not empty of products. 
Please click on the 'Products in location' button to see which products are still in the location.''' %location.name
                res['error_message'] += '\n' + '\n'

            # Check if the location has children locations
            if location.child_ids:
                error = True
                res['has_child'] = True
                res['error_message'] += '''* The location '%s' has children locations.
Please remove all children locations before remove it. 
Please click on the 'Children locations' button to see all children locations.''' %location.name
                res['error_message'] += '\n' + '\n'

            related_ir = self.pool.get('sale.order').search(cr, uid, [
                ('procurement_request', '=', True),
                ('state', 'in', ('draft','validated')),
                ('location_requestor_id', '=', location_id),
            ], context=context)
            if related_ir:
                error = True
                can_force = True
                res['related_ir'] = True
                res['error_message'] += _("* Warning there are open IR with location '%s'.\n Please click on the 'See documents' button to see all children locations.\n\n") % location.name

        if error:
            warning.update({'title': 'Be careful !',
                            'message': 'You have a problem with this location − Please see the message in the form for more information.'})

        res['error'] = error
        res['can_force'] = error and not (res['not_empty'] or res['has_child'] or res['move_from']) and can_force or False

        return {'value': res,
                'warning': warning}

    def check_error(self, cr, uid, ids, context=None):
        '''
        Check if errors are always here
        '''
        for wizard in self.browse(cr, uid, ids, context=context):
            errors = self.location_id_on_change(cr, uid, ids, wizard.location_id.id, context=context)
            self.write(cr, uid, ids, errors.get('value', {}), context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.remove.location.wizard',
                'res_id': wizard.id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',}

    def location_usage_change(self, cr, uid, ids, usage, context=None):
        if usage and usage == 'customer':
            return {'value': {'location_category': 'consumption_unit'}}

        return {}

    def deactivate_location(self, cr, uid, ids, context=None):

        #US-702: This action can only be done in RW instances
        picking_obj = self.pool.get('stock.picking')
        usb_entity = picking_obj._get_usb_entity_type(cr, uid)
        if usb_entity == picking_obj.REMOTE_WAREHOUSE:
            raise osv.except_osv(_('Info!'), _('This action can only be performed at the main instance (CP) and sync to RW!'))

        '''
        Deactivate the selected location
        '''
        location = False
        data_obj = self.pool.get('ir.model.data')
        location_obj = self.pool.get('stock.location')
        configurable_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')[1]
        intermediate_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
        internal_cu_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')[1]

        for wizard in self.browse(cr, uid, ids, context=context):
            if (wizard.error and not wizard.can_force) or wizard.has_child or wizard.not_empty or wizard.move_from:
                raise osv.except_osv(_('Error'), _('You cannot remove this location because some errors are still here !'))
            location = wizard.location_id

        # De-activate the location
        location_obj.write(cr, uid, [location.id], {'active': False}, context=context)

        # Check if parent location should be also de-activated
        if location.location_id.id in (intermediate_loc_id, internal_cu_loc_id, configurable_loc_id):
            empty = True
            for child in location.location_id.child_ids:
                if child.active:
                    empty = False
            if empty:
                location_obj.write(cr, uid, [location.location_id.id], {'active': False}, context=context)

                if location.location_id.location_id.id == configurable_loc_id:
                    empty2 = True
                    for child in location.location_id.location_id.child_ids:
                        if child.active:
                            empty2 = False
                    if empty2:
                        location_obj.write(cr, uid, [location.location_id.location_id.id], {'active': False}, context=context)

        return_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_location_tree')

        if return_view_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'stock.location',
                    'domain': [('location_id','=',False)],
                    'view_type': 'tree',
                    'target': 'crush',
                    'view_id': [return_view_id[1]],
                    }
        else:
            return {'type': 'ir.actions.act_window'}

    def see_moves(self, cr, uid, ids, context=None):
        '''
        Returns all stock.picking containing a stock move not done from/to the location
        '''
        location = False
        picking_ids = []

        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id

        move_ids = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ('done', 'cancel')), '|', ('location_id', '=', location.id), ('location_dest_id', '=', location.id)])
        for move in self.pool.get('stock.move').browse(cr, uid, move_ids, context=context):
            if move.picking_id and move.picking_id.id not in picking_ids:
                picking_ids.append(move.picking_id.id)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'vpicktree')[1]
        if location.usage == 'customer':
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_out_tree')[1]

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'domain': [('id', 'in', picking_ids)],
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'tree,form',
                'target': 'current',
                }


    def related_ir(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        location = wizard.location_id
        context.update({'procurement_request': True})

        related_ir = self.pool.get('sale.order').search(cr, uid, [
            ('procurement_request', '=', True),
            ('state', 'in', ('draft','validated')),
            ('location_requestor_id', '=', location.id),
        ], context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_tree_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'domain': [('id', 'in', related_ir)],
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': context,
        }


    def products_in_location(self, cr, uid, ids, context=None):
        '''
        Returns a list of products in the location
        '''
        if context is None:
            context = {}
        location = False

        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id

        context.update({'contact_display': 'partner', 'search_default_real':1,
                        'search_default_location_type_internal':1,
                        'search_default_group_product':1,
                        'group_by':[], 'group_by_no_leaf':1})
        context.update({'search_default_location_id': location.id})

        return {'type': 'ir.actions.act_window',
                'res_model': 'report.stock.inventory',
                'view_type': 'form',
                'view_mode': 'tree',
                'domain': [('location_id', '=', location.id)],
                'context': context,
                'target': 'current'}

    def children_location(self, cr, uid, ids, context=None):
        '''
        Returns the list of all children locations
        '''
        location_ids = []
        location = False

        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id

        for loc in location.child_ids:
            location_ids.append(loc.id)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.location',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', location_ids)],
                'target': 'current',}

stock_remove_location_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
