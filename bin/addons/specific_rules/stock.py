# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import decimal_precision as dp

import time

class initial_stock_inventory(osv.osv):
    _name = 'initial.stock.inventory'
    _description = "Initial Stock Inventory"
    _inherit = 'stock.inventory'

    def unlink(self, cr, uid, ids, context=None):
        '''
        Prevent the deletion of a non-draft/cancel initial inventory
        '''
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.state not in ('draft', 'cancel'):
                raise osv.except_osv(_('Error'), _('You cannot remove an initial inventory which is done'))

        return super(initial_stock_inventory, self).unlink(cr, uid, ids, context=context)

    _columns = {
        'inventory_line_id': fields.one2many('initial.stock.inventory.line', 'inventory_id', string='Inventory lines'),
        'move_ids': fields.many2many('stock.move', 'initial_stock_inventory_move_rel', 'inventory_id', 'move_id', 'Created Moves'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }

    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        '''
        Add the price in the stock move
        '''
        if inventory_line:
            move_vals['price_unit'] = inventory_line.average_cost
        return super(initial_stock_inventory, self)._inventory_line_hook(cr, uid, inventory_line, move_vals)

    def action_confirm(self, cr, uid, ids, context=None):
        '''
        Override the action_confirm method to check the batch mgmt/perishable data
        '''
        if isinstance(ids, int):
            ids = [ids]

        product_dict = {}
        prodlot_obj = self.pool.get('stock.production.lot')
        product_obj = self.pool.get('product.product')

        self.check_integrity(cr, uid, ids, context=context)

        for inventory in self.browse(cr, uid, ids, context=context):
            # Prevent confirmation with no lines
            if len(inventory.inventory_line_id) == 0:
                raise osv.except_osv(_('Error'), _('Please enter at least one line in stock inventory before confirm it.'))

            for inventory_line in inventory.inventory_line_id:
                if inventory_line.product_id and inventory_line.product_id.state.code != 'forbidden':
                    # Check product constrainsts
                    product_obj._get_restriction_error(cr, uid, [inventory_line.product_id.id], {'location_id': inventory_line.location_id.id}, context=context)

                # Don't check integrity on line with no quantity
                if inventory_line.product_qty == 0.0:
                    inventory_line.write({'dont_move': True})
                    continue

                # Check if there is two lines with the same product and with difference average cost
                if inventory_line.product_id.id not in product_dict:
                    product_dict.update({inventory_line.product_id.id: inventory_line.average_cost})
                elif product_dict[inventory_line.product_id.id] != inventory_line.average_cost:
                    raise osv.except_osv(_('Error'), _('You cannot have two lines for the product %s with different average cost.') % product_obj.name_get(cr, uid, [inventory_line.product_id.id], context=context)[0][1])

                # Returns error if the line is batch mandatory or perishable without prodlot
                if inventory_line.product_id.batch_management and not inventory_line.prodlot_name:
                    raise osv.except_osv(_('Error'), _('You must assign a Batch Number on the product %s.') % product_obj.name_get(cr, uid, [inventory_line.product_id.id])[0][1])
                elif inventory_line.product_id.perishable and not inventory_line.expiry_date:
                    raise osv.except_osv(_('Error'), _('You must assign an Expiry Date on the product %s.') % product_obj.name_get(cr, uid, [inventory_line.product_id.id])[0][1])

                if inventory_line.product_id.batch_management:
                    # if no production lot, we create a new one
                    prodlot_ids = prodlot_obj.search(cr, uid, [('name', '=', inventory_line.prodlot_name),
                                                               ('type', '=', 'standard'),
                                                               ('product_id', '=', inventory_line.product_id.id),
                                                               ('life_date', '=', inventory_line.expiry_date)], context=context)
                    prodlot_id = prodlot_ids and prodlot_ids[0] or False
                    # no prodlot, create a new one
                    if not prodlot_ids:
                        prodlot_id = prodlot_obj.create(cr, uid, {'name': inventory_line.prodlot_name,
                                                                  'type': 'standard',
                                                                  'life_date': inventory_line.expiry_date,
                                                                  'product_id': inventory_line.product_id.id}, context=context)

                    self.pool.get('initial.stock.inventory.line').write(cr, uid, [inventory_line.id], {'prod_lot_id': prodlot_id}, context=context)

                if inventory_line.product_id.perishable and not inventory_line.product_id.batch_management:
                    if not inventory_line.prodlot_name and inventory_line.expiry_date:
                        prodlot_ids = prodlot_obj.search(cr, uid, [
                            ('type', '=', 'internal'),
                            ('product_id', '=', inventory_line.product_id.id),
                            ('life_date', '=', inventory_line.expiry_date),
                        ], context=context)
                        if prodlot_ids:
                            self.pool.get('initial.stock.inventory.line').write(cr, uid, [inventory_line.id], {
                                'prodlot_name': prodlot_obj.read(cr, uid, prodlot_ids[0], ['name'], context=context)['name'],
                            }, context=context)

                # Check if product is non-stockable
                if inventory_line.product_id.product_tmpl_id.type in ('service_recep', 'consu'):
                    raise osv.except_osv(_('Error'), _('Please remove non-stockable product %s to validate.')
                                         % (inventory_line.product_id.default_code,))

        return super(initial_stock_inventory, self).action_confirm(cr, uid, ids, context=context)

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.check_integrity(cr, uid, ids, context=context)

        move_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')
        sptc_obj = self.pool.get('standard.price.track.changes')
        for inv in self.browse(cr, uid, ids, context=context):
            # Set the cost price on product form with the new value, and process the stock move
            for move in inv.move_ids:
                new_std_price = move.price_unit
                sptc_obj.track_change(cr,
                                      uid,
                                      move.product_id.id,
                                      _('Initial stock inventory %s') % inv.name,
                                      vals={
                                          'standard_price': new_std_price,
                                          'old_price': move.product_id.standard_price,
                                      },
                                      context=context)
                prod_obj.write(cr, uid, move.product_id.id, {'standard_price': new_std_price}, context=context)
                move_obj.action_done(cr, uid, move.id, context=context)

            message = _('Inventory') + " '" + inv.name + "' " + _("is done.")
            self.log(cr, uid, inv.id, message)
            self.write(cr, uid, [inv.id], {'state':'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

            self.infolog(cr, uid, 'The Initial stock inventory id:%s (%s) has been validated' % (
                inv.id,
                inv.name,
            ))

        return True

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        location_id = False
        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        if wh_ids:
            location_id = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_stock_id.id
        for inventory in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
            # Get all products for the defined nomenclature
            if inventory.nomen_manda_3:
                nom = inventory.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif inventory.nomen_manda_2:
                nom = inventory.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif inventory.nomen_manda_1:
                nom = inventory.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif inventory.nomen_manda_0:
                nom = inventory.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if inventory.sublist_id:
                for line in inventory.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            # Check if products in already existing lines are in domain
            products = []
            for line in inventory.inventory_line_id:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('initial.stock.inventory.line').unlink(cr, uid, line.id, context=context)

            c = context.copy()
            c.update({'location': location_id, 'compute_child': False, 'to_date': inventory.date})
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=c):
                # Check if the product is not already on the report
                if product.type not in ('consu', 'service', 'service_recep') and product.id not in products:
                    batch_mandatory = product.batch_management
                    date_mandatory = product.perishable
                    values = {'product_id': product.id,
                              'uom_id': product.uom_id.id,
                              'product_qty': 0.00,
                              'average_cost': product.standard_price,
                              'hidden_batch_management_mandatory': batch_mandatory,
                              'hidden_perishable_mandatory': date_mandatory,
                              'inventory_id': inventory.id, }
                    v = self.pool.get('initial.stock.inventory.line').on_change_product_id(cr, uid, [], location_id, product.id, product.uom_id.id, False)['value']
                    # Remove product_qty from values because it has been computed before
                    v.pop('product_qty')
                    values.update(v)
                    if batch_mandatory:
                        values.update({'err_msg': 'You must assign a batch number'})
                    if date_mandatory:
                        values.update({'err_msg': 'You must assign an expiry date'})
                    self.pool.get('initial.stock.inventory.line').create(cr, uid, values)

        return {'type': 'ir.actions.act_window',
                'res_model': 'initial.stock.inventory',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, False, False, context={'withnum': 1})

initial_stock_inventory()


class initial_stock_inventory_line(osv.osv):
    _name = 'initial.stock.inventory.line'
    _description = "Initial Stock Inventory Line"
    _inherit = 'stock.inventory.line'

    def _get_error_msg(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = ''
            if not line.location_id:
                res[line.id] = _('You must define a stock location')
            if line.hidden_batch_management_mandatory and not line.prodlot_name:
                res[line.id] = _('You must define a batch number')
            elif line.hidden_perishable_mandatory and not line.expiry_date:
                res[line.id] = _('You must define an expiry date')

        return res

    def _get_bm_perishable(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'hidden_batch_management_mandatory': line.product_id.batch_management,
                'hidden_perishable_mandatory': line.product_id.perishable,
            }

        return res

    def _get_products(self, cr, uid, ids, context=None):
        inv_ids = self.pool.get('initial.stock.inventory').search(cr, uid, [
            ('state', 'not in', ['done', 'cancel']),
        ], context=context)
        return self.pool.get('initial.stock.inventory.line').search(cr, uid, [
            ('inventory_id', 'in', inv_ids),
            ('product_id', 'in', ids),
        ], context=context)

    _columns = {
        'inventory_id': fields.many2one('initial.stock.inventory', string='Inventory', ondelete='cascade'),
        'prodlot_name': fields.char(size=64, string='Batch'),
        'average_cost': fields.float(string='Initial average cost', digits_compute=dp.get_precision('Sale Price Computation'), required=True, en_thousand_sep=False),
        'currency_id': fields.many2one('res.currency', string='Functional currency', readonly=True),
        'err_msg': fields.function(_get_error_msg, method=True, type='char', string='Message', store=False),
        'hidden_perishable_mandatory': fields.function(
            _get_bm_perishable,
            type='boolean',
            method=True,
            string='Hidden Flag for Perishable product',
            multi='bm_perishable',
            store={
                'initial.stock.inventory.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                'product.product': (_get_products, ['perishable'], 20),
            },
        ),
        'hidden_batch_management_mandatory': fields.function(
            _get_bm_perishable,
            type='boolean',
            method=True,
            string='Hidden Flag for Perishable product',
            multi='bm_perishable',
            store={
                'initial.stock.inventory.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                'product.product': (_get_products, ['batch_management'], 20),
            },
        ),
    }

    _defaults = {
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'average_cost': lambda *a: 0.00,
        'product_qty': lambda *a: 0.00,
        'reason_type_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_stock_initialization')[1],
    }

    def _check_batch_management(self, cr, uid, ids, context=None):
        '''
        check for batch management
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.batch_management and obj.inventory_id.state not in ('draft', 'cancel'):
                if not obj.prod_lot_id or obj.prod_lot_id.type != 'standard':
                    return False
        return True

    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable ONLY
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.perishable and not obj.product_id.batch_management and obj.inventory_id.state not in ('draft', 'cancel'):
                if (not obj.prod_lot_id and not obj.expiry_date) or (obj.prod_lot_id and obj.prod_lot_id.type != 'internal'):
                    return False
        return True

    def _check_prodlot_need(self, cr, uid, ids, context=None):
        """
        If the inv line has a prodlot but does not need one, return False.
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.prod_lot_id and obj.inventory_id.state not in ('draft', 'cancel'):
                if not obj.product_id.perishable and not obj.product_id.batch_management:
                    return False
        return True

    def _check_same_cost(self, cr, uid, ids, context=None):
        '''
        If the inv line has a different average cost than the other lines with the same product
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            other_lines = self.search(cr, uid, [('product_qty', '!=', 0.00), ('inventory_id', '=', obj.inventory_id.id), ('product_id', '=', obj.product_id.id)], context=context)
            if other_lines and obj.product_qty != 0.00:
                cost = self.browse(cr, uid, other_lines[0], context=context).average_cost
                if cost != obj.average_cost:
                    raise osv.except_osv(_('Error'), _('You cannot have two lines with the product %s and different average cost.') % self.pool.get('product.product').name_get(cr, uid, [obj.product_id.id])[0][1])
                    return False

        return True

    _constraints = [(_check_batch_management,
                     'You must assign a Batch Number which corresponds to Batch Number Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_perishable,
                     'You must assign a Batch Numbre which corresponds to Expiry Date Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_prodlot_need,
                     'The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory',
                     ['prod_lot_id']),
                    (_check_same_cost,
                     'You cannot have two lines with the same product and different average cost.',
                     ['product_id', 'average_cost'])
                    ]

    def product_change(self, cr, uid, ids, product_id, location_id, field_change, change_price=False, prodlot_id=False):
        '''
        Set the UoM with the default UoM of the product
        '''
        value = {'product_uom': False,
                 'hidden_perishable_mandatory': False,
                 'hidden_batch_management_mandatory': False,}

        if product_id:
            product_obj = self.pool.get('product.product')
            context = {}
            if location_id:
                context = {'location': location_id, 'compute_child': False}
            if prodlot_id:
                context.update({'prodlot_id': prodlot_id})
            product = product_obj.browse(cr, uid, product_id, context=context)
            if location_id and product.state.code != 'forbidden':
                # Test the compatibility of the product with the location
                value, test = product_obj._on_change_restriction_error(cr, uid, product_id, field_name=field_change, values=value, vals={'location_id': location_id})
                if test:
                    return value
            value.update({'product_uom': product.uom_id.id,
                          'hidden_perishable_mandatory': product.perishable,
                          'hidden_batch_management_mandatory': product.batch_management})
            if change_price:
                value.update({'average_cost': product.standard_price,})

            # Don't recompute the product qty according to batch because no selection of batch
#            if location_id:
#                value.update({'product_qty': product.qty_available})

        return {'value': value}

    def change_lot(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        res = super(initial_stock_inventory_line, self).change_lot(cr, uid, ids, location_id, product, prod_lot_id, uom=uom, to_date=to_date)
        if 'warning' not in res:
            if 'value' not in res:
                res.update({'value': {}})

            res['value'].update({'err_msg': ''})

        return res

    def change_expiry(self, cr, uid, id, expiry_date, product_id, type_check, context=None):
        res = super(initial_stock_inventory_line, self).change_expiry(cr, uid, id, expiry_date, product_id, type_check, context=None)
        if 'warning' not in res:
            if 'value' not in res:
                res.udptae({'value': {}})

            res['value'].update({'err_msg': ''})

        return res

    def _get_usb_entity_type(self, cr, uid, context=None):
        '''
        Verify if the given instance is Remote Warehouse instance, if no, just return False, if yes, return the type (RW or CP) 
        '''
        entity = self.pool.get('sync.client.entity').get_entity(cr, uid)
        if not entity.__hasattr__('usb_instance_type'):
            return False

        return entity.usb_instance_type

    def create(self, cr, uid, vals, context=None):
        '''
        Set the UoM with the default UoM of the product
        '''
        if context is None:
            context = {}
        prod_obj = self.pool.get('product.product')

        if vals.get('product_id', False):
            product = prod_obj.browse(cr, uid, vals['product_id'], context=context)
            vals['product_uom'] = product.uom_id.id

            #US-803: update the price from RW
            rw_type = self._get_usb_entity_type(cr, uid)
            if context.get('sync_update_execution') and vals.get('average_cost', False) and rw_type == 'central_platform':
                context['rw_sync'] = True
                prod_obj.write(cr, uid, product.id, {'standard_price': vals['average_cost']}, context=context)

        return super(initial_stock_inventory_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set the UoM with the default UoM of the product
        '''
        if not ids:
            return True
        if vals.get('product_id', False):
            prod_obj = self.pool.get('product.product')
            product = prod_obj.browse(cr, uid, vals['product_id'], context=context)
            vals['product_uom'] = product.uom_id.id

            #US-803: update the price from RW
            rw_type = self._get_usb_entity_type(cr, uid)
            if context.get('sync_update_execution') and vals.get('average_cost', False) and rw_type == 'central_platform':
                context['rw_sync'] = True
                prod_obj.write(cr, uid, product.id, {'standard_price': vals['average_cost']}, context=context)

        return super(initial_stock_inventory_line, self).write(cr, uid, ids, vals, context=context)

initial_stock_inventory_line()

class stock_cost_reevaluation(osv.osv):
    _name = 'stock.cost.reevaluation'
    _description = 'Cost reevaluation'

    _columns = {
        'name': fields.char(size=64, string='Reference', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.date(string='Creation date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'reevaluation_line_ids': fields.one2many('stock.cost.reevaluation.line', 'reevaluation_id', string='Lines',
                                                 readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([('draft', 'Draft'), ('confirm', 'Validated'), ('done', 'Done'), ('cancel', 'Cancel')],
                                  string='State', readonly=True, required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    _sql_constraints = [
        ('name_unique', "unique(name)", 'The Reference of the Product Cost Revaluation must be unique'),
    ]

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        Set the state to 'draft' and the creation date to the current date
        '''
        if not default:
            default = {}
        name = self.read(cr, uid, ids, ['name'])['name']
        i = 1
        new_name = '%s (copy %s)' % (name, i)
        while self.search_count(cr, uid, [('name', '=', new_name)]):
            i += 1
            new_name = '%s (copy %s)' % (name, i)

        if not 'state' in default:
            default.update({'state': 'draft'})

        default.update({'date': time.strftime('%Y-%m-%d'),
                        'name': new_name})

        return super(stock_cost_reevaluation, self).copy(cr, uid, ids, default=default, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        '''
        Confirm the cost reevaluation (don't change the price at this time)
        '''
        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            # Prevent confirmation without lines
            if len(obj.reevaluation_line_ids) == 0:
                raise osv.except_osv(_('Error'), _('Please enter at least one revaluation line before confirm it.'))

            # Check if there are two lines with the same product
            products = []
            for line in obj.reevaluation_line_ids:
                if line.product_id.id not in products:
                    products.append(line.product_id.id)
                else:
                    raise osv.except_osv(_('Error'), _('You cannot have two lines with the same product. (Product : [%s] %s)') % (line.product_id.default_code, line.product_id.name))

        return self.write(cr, uid, ids, {'state': 'confirm'}, context=context)

    def action_done(self, cr, uid, ids, context=None):
        '''
        Change the price of the products in the lines
        '''
        sptc_obj = self.pool.get('standard.price.track.changes')

        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.reevaluation_line_ids:
                sptc_obj.track_change(cr,
                                      uid,
                                      line.product_id.id,
                                      _('Product cost reevaluation %s') % obj.name,
                                      vals={
                                          'standard_price': line.average_cost,
                                          'old_price': line.product_id.standard_price,
                                      }, context=context)
                self.pool.get('product.product').write(cr, uid, line.product_id.id, {'standard_price': line.average_cost})

        return self.write(cr, uid, ids, {'state': 'done'}, context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        Change the state of the document to cancel
        '''
        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def action_cancel_draft(self, cr, uid, ids, context=None):
        '''
        Change the state of the document to draft
        '''
        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for inventory in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
            # Get all products for the defined nomenclature
            if inventory.nomen_manda_3:
                nom = inventory.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif inventory.nomen_manda_2:
                nom = inventory.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif inventory.nomen_manda_1:
                nom = inventory.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif inventory.nomen_manda_0:
                nom = inventory.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if inventory.sublist_id:
                for line in inventory.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            # Check if products in already existing lines are in domain
            products = []
            for line in inventory.reevaluation_line_ids:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('stock.cost.reevaluation.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids):
                # Check if the product is not already on the report
                if product.id not in products:
                    values = {'product_id': product.id,
                              'average_cost': product.standard_price,
                              'reevaluation_id': inventory.id, }
                    self.pool.get('stock.cost.reevaluation.line').create(cr, uid, values)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.cost.reevaluation',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, False, False, context={'withnum': 1})

stock_cost_reevaluation()

class stock_cost_reevaluation_line(osv.osv):
    _name = 'stock.cost.reevaluation.line'
    _description = 'Cost reevaluation line'
    _rec_name = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'average_cost': fields.float(string='Average cost', digits_compute=dp.get_precision('Sale Price Computation'), required=True, en_thousand_sep=False),
        'currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'reevaluation_id': fields.many2one('stock.cost.reevaluation', string='Header'),
    }

    _defaults = {
        'currency_id': lambda obj, cr, uid, c = {}: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
    }

    def product_id_change(self, cr, uid, ids, product_id, context=None):
        '''
        Change the average price with the cost price of the product
        '''
        if product_id:
            cost_price = self.pool.get('product.product').browse(cr, uid, product_id, context=context).standard_price
            return {'value': {'average_cost': cost_price}}

        return {'value': {'average_cost': 0.00}}

stock_cost_reevaluation_line()

