# -*- coding: utf-8 -*-

import time

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp


class stock_inventory(osv.osv):
    _name = "stock.inventory"
    _description = "Inventory"
    _columns = {
        'name': fields.char('Inventory Reference', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.datetime('Creation Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_done': fields.datetime('Date done'),
        'inventory_line_id': fields.one2many('stock.inventory.line', 'inventory_id', 'Inventories', states={'done': [('readonly', True)]}),
        'move_ids': fields.many2many('stock.move', 'stock_inventory_move_rel', 'inventory_id', 'move_id', 'Created Moves'),
        'state': fields.selection( (('draft', 'Draft'), ('done', 'Done'), ('confirm','Validated'),('cancel','Cancelled')), 'State', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True, readonly=True, states={'draft':[('readonly',False)]}),

    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c)
    }

    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return:
        """
        return self.pool.get('stock.move').create(cr, uid, move_vals)

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            move_obj.action_done(cr, uid, inv['move_ids'], context=context)
        self.write(cr, uid, ids, {'state':'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        return True

    def _hook_dont_move(self, cr, uid, *args, **kwargs):
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory and writes its finished date
        @return: True
        """
        if context is None:
            context = {}
        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        product_tmpl_obj = self.pool.get('product.template')
        product_dict = {}
        product_tmpl_dict = {}

        for inv in self.read(cr, uid, ids, ['inventory_line_id', 'date', 'name'], context=context):
            move_ids = []

            # gather all information needed for the lines treatment first to do
            # less requests
            if self._name == 'initial.stock.inventory':
                inv_line_obj = self.pool.get('initial.stock.inventory.line')
            else:
                inv_line_obj = self.pool.get('stock.inventory.line')

            line_read = inv_line_obj.read(cr, uid, inv['inventory_line_id'],
                                          ['product_id', 'product_uom', 'prod_lot_id', 'location_id',
                                           'product_qty', 'inventory_id', 'dont_move', 'comment',
                                           'reason_type_id', 'average_cost'],
                                          context=context)
            product_id_list = [x['product_id'][0] for x in line_read if
                               x['product_id'][0] not in product_dict]
            product_id_list = list(set(product_id_list))
            product_read = product_obj.read(cr, uid, product_id_list,
                                            ['product_tmpl_id'], context=context)
            for product in product_read:
                product_id = product['id']
                product_dict[product_id] = {}
                product_dict[product_id]['p_tmpl_id'] = product['product_tmpl_id'][0]
            tmpl_ids = [x['p_tmpl_id'] for x in list(product_dict.values())]

            product_tmpl_id_list = [x for x in tmpl_ids if x not in
                                    product_tmpl_dict]
            product_tmpl_id_list = list(set(product_tmpl_id_list))
            product_tmpl_read = product_tmpl_obj.read(cr, uid,
                                                      product_tmpl_id_list, ['property_stock_inventory'],
                                                      context=context)
            product_tmpl_dict = dict((x['id'], x['property_stock_inventory'][0]) for x in product_tmpl_read)

            for product_id in product_id_list:
                product_tmpl_id = product_dict[product_id]['p_tmpl_id']
                stock_inventory = product_tmpl_dict[product_tmpl_id]
                product_dict[product_id]['stock_inventory'] = stock_inventory

            for line in line_read:
                pid = line['product_id'][0]
                lot_id = line['prod_lot_id'] and line['prod_lot_id'][0] or False
                product_context.update(uom=line['product_uom'][0],
                                       date=inv['date'], prodlot_id=lot_id)
                amount = location_obj._product_get(cr, uid,
                                                   line['location_id'][0], [pid], product_context)[pid]

                change = line['product_qty'] - amount
                if change and self._hook_dont_move(cr, uid, dont_move=line['dont_move']):
                    location_id = product_dict[line['product_id'][0]]['stock_inventory']
                    value = {
                        'name': 'INV:' + str(inv['id']) + ':' + inv['name'],
                        'product_id': line['product_id'][0],
                        'product_uom': line['product_uom'][0],
                        'prodlot_id': lot_id,
                        'date': inv['date'],
                    }
                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line['location_id'][0],
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line['location_id'][0],
                            'location_dest_id': location_id,
                        })
                    value.update({
                        'comment': line['comment'],
                        'reason_type_id': line['reason_type_id'][0],
                    })

                    if self._name == 'initial.stock.inventory':
                        value.update({'price_unit': line['average_cost']})
                    move_ids.append(self._inventory_line_hook(cr, uid, None, value))
                elif not change:
                    inv_line_obj.write(cr, uid, [line['id']], {'dont_move': True}, context=context)
            message = _('Inventory') + " '" + inv['name'] + "' "+ _("is validated.")
            self.log(cr, uid, inv['id'], message)
            self.write(cr, uid, [inv['id']], {'state': 'confirm', 'move_ids': [(6, 0, move_ids)]})
        return True

    def action_cancel_draft(self, cr, uid, ids, context=None):
        """ Cancels the stock move and change inventory state to draft.
        @return: True
        """
        inv_to_write = set()
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            self.pool.get('stock.move').action_cancel(cr, uid, inv['move_ids'], context=context)
            inv_to_write.add(inv['id'])

        self.write(cr, uid, list(inv_to_write), {'state':'draft'}, context=context)
        return True

    def action_cancel_inventary(self, cr, uid, ids, context=None):
        """ Cancels both stock move and inventory
        @return: True
        """
        move_obj = self.pool.get('stock.move')
        account_move_obj = self.pool.get('account.move')
        for inv in self.browse(cr, uid, ids, context=context):
            move_obj.action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
            for move in inv.move_ids:
                account_move_ids = account_move_obj.search(cr, uid, [('name',
                                                                      '=', move.name)], order='NO_ORDER')
                if account_move_ids:
                    account_move_data_l = account_move_obj.read(cr, uid, account_move_ids, ['state'], context=context)
                    for account_move in account_move_data_l:
                        if account_move['state'] == 'posted':
                            raise osv.except_osv(_('UserError'),
                                                 _('You can not cancel inventory which has any account move with posted state.'))
                        account_move_obj.unlink(cr, uid, [account_move['id']], context=context)
            line_ids = [x.id for x in inv.inventory_line_id]
            if line_ids and self._name != 'initial.stock.inventory':
                self.pool.get('stock.inventory.line').write(cr, uid, line_ids, {'dont_move': False}, context=context)
            self.write(cr, uid, [inv.id], {'state': 'cancel'}, context=context)
            if self._name == 'initial.stock.inventory':
                self.infolog(cr, uid, "The Initial Stock inventory id:%s (%s) has been canceled" % (inv.id, inv.name))
            else:
                self.infolog(cr, uid, "The Physical inventory id:%s (%s) has been canceled" % (inv.id, inv.name))
        return True

stock_inventory()

class stock_inventory_line(osv.osv):
    _name = "stock.inventory.line"
    _description = "Inventory Line"
    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location'),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom'),
        'company_id': fields.related('inventory_id','company_id',type='many2one',relation='res.company',string='Company',store=True, select=True, readonly=True),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot', domain="[('product_id','=',product_id)]"),
        'state': fields.related('inventory_id','state',type='char',string='State',readonly=True),
    }

    def on_change_product_id(self, cr, uid, ids, location_id, product, uom=False, to_date=False):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product
        @return:  Dictionary of changed values
        """
        if not product:
            return {'value': {'product_qty': 0.0, 'product_uom': False}}
        obj_product = self.pool.get('product.product').browse(cr, uid, product)
        uom = uom or obj_product.uom_id.id
        amount = self.pool.get('stock.location')._product_get(cr, uid, location_id, [product], {'uom': uom, 'to_date': to_date})[product]
        result = {'product_qty': amount, 'product_uom': uom}
        return {'value': result}

stock_inventory_line()

