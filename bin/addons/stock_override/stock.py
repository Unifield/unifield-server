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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

import netsvc
from osv import fields, osv
import tools
from tools.translate import _

import decimal_precision as dp
from msf_partner import PARTNER_TYPE
from order_types.stock import check_cp_rw
from order_types.stock import check_rw_warning



#----------------------------------------------------------
# Procurement Order
#----------------------------------------------------------
class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'

    def create(self, cr, uid, vals, context=None):
        '''
        create method for filling flag from yml tests
        '''
        if context is None:
            context = {}
        return super(procurement_order, self).create(cr, uid, vals, context=context)

    # @@@override: procurement>procurement.order->action_confirm()
    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms procurement and writes exception message if any.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')

        for procurement in self.browse(cr, uid, ids, context=context):
            if procurement.product_qty <= 0.00:
                raise osv.except_osv(_('Data Insufficient !'),
                                     _('Please check the Quantity in Procurement Order(s), it should not be less than 1!'))
            if procurement.product_id.type in ('product', 'consu'):
                if not procurement.move_id:
                    if procurement.procure_method == 'make_to_order':
                        reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
                        source = procurement.product_id.product_tmpl_id.property_stock_procurement.id
                    else:
                        source = procurement.location_id.id
                        reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
                    id = move_obj.create(cr, uid, {
                        'name': procurement.name,
                        'location_id': source,
                        'location_dest_id': procurement.location_id.id,
                        'product_id': procurement.product_id.id,
                        'product_qty': procurement.product_qty,
                        'product_uom': procurement.product_uom.id,
                        'date_expected': procurement.date_planned,
                        'state': 'draft',
                        'company_id': procurement.company_id.id,
                        'auto_validate': True,
                        'reason_type_id': reason_type_id,
                    })
                    move_obj.action_confirm(cr, uid, [id], context=context)
                    if procurement.procure_method == 'make_to_order':
                        move_obj.write(cr, uid, [id], {'state': 'hidden'}, context=context)
                    self.write(cr, uid, [procurement.id], {'move_id': id, 'close_move': 1})
        self.write(cr, uid, ids, {'state': 'confirmed', 'message': ''})
        return True
    # @@@END override: procurement>procurement.order->action_confirm()

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset link to purchase order from update of on order purchase order
        '''
        if not default:
            default = {}
        default.update({'so_back_update_dest_po_id_procurement_order': False,
                        'so_back_update_dest_pol_id_procurement_order': False})
        return super(procurement_order, self).copy_data(cr, uid, id, default, context=context)

    _columns = {
        'so_back_update_dest_po_id_procurement_order': fields.many2one('purchase.order', string='Destination of new purchase order line', readonly=True),
        'so_back_update_dest_pol_id_procurement_order': fields.many2one('purchase.order.line', string='Original purchase order line', readonly=True),
    }

    _defaults = {
    }


procurement_order()


#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------
class stock_picking(osv.osv):
    _inherit = "stock.picking"
    _description = "Picking List"

    def _hook_state_list(self, cr, uid, *args, **kwargs):
        '''
        Change terms into states list
        '''
        state_list = kwargs['state_list']

        state_list['done'] = _('is closed.')
        state_list['shipped'] = _('is shipped.')  # UF-1617: New state for the IN of partial shipment

        return state_list

    def _get_stock_picking_from_partner_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of res.partner objects for which values have changed

        return the list of ids of stock.picking objects which need to get their fields updated

        self is res.partner object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick_obj = self.pool.get('stock.picking')
        result = pick_obj.search(cr, uid, [('partner_id2', 'in', ids)], context=context)
        return result

    def _vals_get_stock_ov(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})
            if obj.partner_id2:
                result[obj.id].update({'partner_type_stock_picking': obj.partner_id2.partner_type})

        return result

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = False
            for line in pick.move_lines:
                if line.inactive_product:
                    res[pick.id] = True
                    break

        return res

    def _get_is_esc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the partner is an ESC
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = pick.partner_id2 and pick.partner_id2.partner_type == 'esc' or False

        return res

    def _get_dpo_incoming(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the picking is an incoming and if one the stock move are linked to dpo_line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = {'dpo_incoming': False,
                            'dpo_out': False}
            if pick.type == 'in':
                for move in pick.move_lines:
                    if move.sync_dpo or move.dpo_line_id:
                        res[pick.id]['dpo_incoming'] = True
                        break

            if pick.type == 'out' and pick.subtype in ('standard', 'picking'):
                for move in pick.move_lines:
                    if move.sync_dpo or move.dpo_line_id:
                        res[pick.id]['dpo_out'] = True
                        break
        return res

    def _get_dpo_picking_ids(self, cr, uid, ids, context=None):
        result = set()
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.read(cr, uid, ids, ['picking_id'], context=context):
            if obj['picking_id']:
                result.add(obj['picking_id'][0])
        return list(result)

    def _get_do_not_sync(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        current_company_p_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
        for pick in self.read(cr, uid, ids, ['partner_id'], context=context):
            res[pick['id']] = False
            if pick['partner_id'] and pick['partner_id'][0] == current_company_p_id:
                res[pick['id']] = True
        return res

    def _src_do_not_sync(self, cr, uid, obj, name, args, context=None):
        '''
        Returns picking ticket that do not synched because the partner of the
        picking is the partner of the current company.
        '''
        res = []
        curr_partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id

        if context is None:
            context = {}

        for arg in args:

            eq_false = arg[1] == '=' and arg[2] in (False, 'f', 'false', 'False', 0)
            neq_true = arg[1] in ('!=', '<>') and arg[2] in (True, 't', 'true', 'True', 1)
            eq_true = arg[1] == '=' and arg[2] in (True, 't', 'true', 'True', 1)
            neq_false = arg[1] in ('!=', '<>') and arg[2] in (False, 'f', 'false', 'False', 0)

            if arg[0] == 'do_not_sync' and (eq_false or neq_true):
                res.append(('partner_id', '!=', curr_partner_id))
            elif arg[0] == 'do_not_sync' and (eq_true or neq_false):
                res.append(('partner_id', '=', curr_partner_id))

        return res

    def _get_is_company(self, cr, uid, ids, field_name, args, context=None):
        """
        Return True if the partner_id2 of the stock.picking is the same partner
        as the partner linked to res.company of the res.users
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of stock.picking to update
        :param field_name: List of names of fields to update
        :param args: Extra parametrer
        :param context: Context of the call
        :return: A dictionary with stock.picking ID as keys and True or False a values
        """
        user_obj = self.pool.get('res.users')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        cmp_partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
        for pick in self.read(cr, uid, ids, ['partner_id2'], context=context):
            res[pick['id']] = pick['partner_id2'] and pick['partner_id2'][0] == cmp_partner_id or False

        return res

    _columns = {
        'state': fields.selection([
            ('draft', 'Draft'),
            ('auto', 'Waiting'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Available'),
            ('shipped', 'Available Shipped'),  # UF-1617: new state of IN for partial shipment
            ('updated', 'Available Updated'),
            ('done', 'Closed'),
            ('cancel', 'Cancelled'),
            ('import', 'Import in progress'),
        ], 'State', readonly=True, select=True,
            help="* Draft: not confirmed yet and will not be scheduled until confirmed\n"\
                 "* Confirmed: still waiting for the availability of products\n"\
                 "* Available: products reserved, simply waiting for confirmation.\n"\
                 "* Available Shipped: products already shipped at supplier, simply waiting for arrival confirmation.\n"\
                 "* Waiting: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n"\
                 "* Closed: has been processed, can't be modified or cancelled anymore\n"\
                 "* Cancelled: has been cancelled, can't be confirmed anymore"),
        'address_id': fields.many2one('res.partner.address', 'Delivery address', help="Address of partner", readonly=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain="[('partner_id', '=', partner_id)]"),
        'partner_id2': fields.many2one('res.partner', 'Partner', required=False),
        'ext_cu': fields.many2one('stock.location', string='Ext. C.U.'),
        'partner_type': fields.related(
            'partner_id',
            'partner_type',
            type='selection',
            selection=PARTNER_TYPE,
            readonly=True,
        ),
        'from_wkf': fields.boolean('From wkf'),
        'from_wkf_sourcing': fields.boolean('From wkf sourcing'),
        'update_version_from_in_stock_picking': fields.integer(string='Update version following IN processing'),
        'partner_type_stock_picking': fields.function(_vals_get_stock_ov, method=True, type='selection', selection=PARTNER_TYPE, string='Partner Type', multi='get_vals_stock_ov', readonly=True, select=True,
                                                      store={'stock.picking': (lambda self, cr, uid, ids, c=None: ids, ['partner_id2'], 10),
                                                             'res.partner': (_get_stock_picking_from_partner_ids, ['partner_type'], 10), }),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False),
        'fake_type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'shipment_ref': fields.char(string='Ship Reference', size=256, readonly=True),  # UF-1617: indicating the reference to the SHIP object at supplier
        'move_lines': fields.one2many('stock.move', 'picking_id', 'Internal Moves', states={'done': [('readonly', True)], 'cancel': [('readonly', True)], 'import': [('readonly', True)]}),
        'state_before_import': fields.char(size=64, string='State before import', readonly=True),
        'is_esc': fields.function(_get_is_esc, method=True, string='ESC Partner ?', type='boolean', store=False),
        'dpo_incoming': fields.function(_get_dpo_incoming, method=True, type='boolean', string='DPO Incoming', multi='dpo',
                                        store={'stock.move': (_get_dpo_picking_ids, ['sync_dpo', 'dpo_line_id', 'picking_id'], 10,),
                                               'stock.picking': (lambda self, cr, uid, ids, c={}: ids, ['move_lines'], 10)}),
        'dpo_out': fields.function(_get_dpo_incoming, method=True, type='boolean', string='DPO Out', multi='dpo',
                                   store={'stock.move': (_get_dpo_picking_ids, ['sync_dpo', 'dpo_line_id', 'picking_id'], 10,),
                                          'stock.picking': (lambda self, cr, uid, ids, c={}: ids, ['move_lines'], 10)}),
        'previous_chained_pick_id': fields.many2one('stock.picking', string='Previous chained picking', ondelete='set null', readonly=True),
        'do_not_sync': fields.function(
            _get_do_not_sync,
            fnct_search=_src_do_not_sync,
            method=True,
            type='boolean',
            string='Do not sync.',
            store=False,
        ),
        'company_id2': fields.many2one('res.partner', string='Company', required=True),
        'is_company': fields.function(
            _get_is_company,
            method=True,
            type='boolean',
            string='Is Company ?',
            store={
                'stock.picking': (lambda self, cr, uid, ids, c={}: ids, ['partner_id2'], 10),
            }
        ),
        'incoming_id': fields.many2one('stock.picking', string='Incoming ref', readonly=True),
        'from_pick_cancel_id': fields.many2one('stock.picking', string='Linked Picking/Out', readonly=True,
                                               help='Picking or Out that created this Internal Move after cancellation'),
    }

    _defaults = {
        'from_wkf': lambda *a: False,
        'from_wkf_sourcing': lambda *a: False,
        'update_version_from_in_stock_picking': 0,
        'fake_type': 'in',
        'shipment_ref':False,
        'company_id2': lambda s,c,u,ids,ctx=None: s.pool.get('res.users').browse(c,u,u).company_id.partner_id.id,
        'from_pick_cancel_id': False,
    }


    def on_change_ext_cu(self, cr, uid, ids, ext_cu, context=None):
        if context is None:
            context = {}

        if not ids:
            return {}

        for pick in self.browse(cr, uid, ids, context=context):
            moves = [move.id for move in pick.move_lines]
            if not moves:
                return {}
            if ext_cu:
                self.pool.get('stock.move').write(cr, uid, [move.id for move in pick.move_lines], {'location_id': ext_cu}, context=context)
                message =  _('The source location of lines has been changed to the same as header value')
            else: # not ext_cu set defualt location because source location of stock.move is a mandatory field:
                other_supplier_location = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')
                self.pool.get('stock.move').write(cr, uid, [move.id for move in pick.move_lines], {'location_id': other_supplier_location[1]}, context=context)
                message = _("Warning, you have removed header value source location! The lines will be re-set to have 'Other Supplier' as the source location. Please check this is correct!")

        return {
            'warning': {
                'title': _('Warning'),
                'message': message,
            }
        }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update(shipment_ref=False)

        if not 'from_wkf_sourcing' in default:
            default['from_wkf_sourcing'] = False

        if not 'previous_chained_pick_id' in default:
            default['previous_chained_pick_id'] = False

        if not 'from_pick_cancel_id' in default:
            default['from_pick_cancel_id'] = False

        return super(stock_picking, self).copy_data(cr, uid, id, default=default, context=context)

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the stock picking contains a line with an inactive products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_tbd = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        inactive_lines = self.pool.get('stock.move').search(cr, uid, [('product_id.active', '=', False),
                                                                      ('product_id', '!=', product_tbd),
                                                                      ('picking_id', 'in', ids),
                                                                      ('picking_id.state', 'not in', ['draft', 'cancel', 'done'])],
                                                            count=True, context=context)

        if inactive_lines:
            plural = inactive_lines == 1 and _('A product has') or _('Some products have')
            l_plural = inactive_lines == 1 and _('line') or _('lines')
            p_plural = inactive_lines == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False
        return True

    _constraints = [
        (_check_active_product, "You cannot validate this document because it contains a line with an inactive product", ['order_line', 'state'])
    ]

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('stock.move')
        res = True

        for picking in self.read(cr, uid, ids, ['type', 'state', 'move_lines'], context=context):
            if picking['type'] == 'internal' and picking['state'] not in ('draft', 'done', 'cancel'):
                res = res and line_obj._check_restriction_line(cr, uid,
                                                               picking['move_lines'], context=context)
        return res

    # UF-2148: override and use only this method when checking the cancel condition: if a line has 0 qty, then whatever state, it is always allowed to be canceled
    def allow_cancel(self, cr, uid, ids, context=None):
        for pick in self.browse(cr, uid, ids, context=context):
            if not pick.move_lines:
                return True
            for move in pick.move_lines:
                if move.state == 'done' and move.product_qty != 0:
                    raise osv.except_osv(_('Error'), _('You cannot cancel picking because stock move is in done state !'))
        return True


    def create(self, cr, uid, vals, context=None):
        '''
        create method for filling flag from yml tests
        '''
        if context is None:
            context = {}

        if not context.get('active_id', False):
            vals['from_wkf'] = True
        # in case me make a copy of a stock.picking coming from a workflow
        if context.get('not_workflow', False):
            vals['from_wkf'] = False

        if vals.get('from_wkf') and vals.get('purchase_id'):
            po = self.pool.get('purchase.order').browse(cr, uid, vals.get('purchase_id'), context=context)
            for line in po.order_line:
                if line.linked_sol_id:
                    vals['from_wkf_sourcing'] = True
                    break

        if not vals.get('partner_id2') and vals.get('address_id'):
            addr = self.pool.get('res.partner.address').browse(cr, uid, vals.get('address_id'), context=context)
            vals['partner_id2'] = addr.partner_id and addr.partner_id.id or False

        if not vals.get('address_id') and vals.get('partner_id2'):
            addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
            if not addr.get('delivery'):
                vals['address_id'] = addr.get('default')
            else:
                vals['address_id'] = addr.get('delivery')

        res = super(stock_picking, self).create(cr, uid, vals, context=context)

        return res


    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not vals.get('address_id') and vals.get('partner_id2'):
            for pick in self.read(cr, uid, ids, ['partner_id'], context=context):
                if pick['partner_id'] and pick['partner_id'][0] != vals.get('partner_id2'):
                    addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
                    if not addr.get('delivery'):
                        vals['address_id'] = addr.get('default')
                    else:
                        vals['address_id'] = addr.get('delivery')

        elif not vals.get('partner_id2') and vals.get('address_id'):
            for pick in self.read(cr, uid, ids, ['address_id'], context=context):
                if pick['address_id'] and pick['address_id'][0] != vals.get('address_id'):
                    addr = self.pool.get('res.partner.address').read(cr, uid,
                                                                     vals.get('address_id'), ['partner_id'], context=context)
                    vals['partner_id2'] = addr['partner_id'] and addr['partner_id'][0] or False

        res = super(stock_picking, self).write(cr, uid, ids, vals, context=context)

        return res

    def go_to_simulation_screen(self, cr, uid, ids, context=None):
        '''
        Return the simulation screen
        '''
        simu_obj = self.pool.get('wizard.import.in.simulation.screen')
        line_obj = self.pool.get('wizard.import.in.line.simulation.screen')

        if isinstance(ids, (int, long)):
            ids = [ids]

        picking_id = ids[0]
        if not picking_id:
            raise osv.except_osv(_('Error'), _('No picking defined'))

        simu_id = simu_obj.create(cr, uid, {'picking_id': picking_id, }, context=context)
        for move in self.browse(cr, uid, picking_id, context=context).move_lines:
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

    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        if context is None:
            context = {}

        v = {}
        d = {}

        partner = False

        if not partner_id:
            v.update({'address_id': False, 'is_esc': False})
        else:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            d.update({'address_id': [('partner_id', '=', partner_id)]})
            v.update({'is_esc': partner.partner_type == 'esc'})


        if address_id:
            addr = self.pool.get('res.partner.address').browse(cr, uid, address_id, context=context)

        if not address_id or addr.partner_id.id != partner_id:
            addr = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
            if not addr.get('delivery'):
                addr = addr.get('default')
            else:
                addr = addr.get('delivery')

            v.update({'address_id': addr})

        if partner_id and ids:
            context['partner_id'] = partner_id

            out_loc_ids = self.pool.get('stock.location').search(cr, uid, [
                ('outgoing_dest', '=', context['partner_id']),
            ], order='NO_ORDER', context=context)
            move_ids = self.pool.get('stock.move').search(cr, uid, [
                ('picking_id', 'in', ids),
                ('location_dest_id', 'not in', out_loc_ids),
            ], limit=1, order='NO_ORDER', context=context)
            if move_ids:
                return {
                    'value': {'partner_id2': False, 'partner_id': False,},
                    'warning': {
                        'title': _('Error'),
                        'message': _("""
You cannot choose this supplier because some destination locations are not available for this partner.
"""),
                    },
                }

            picking = self.browse(cr, uid, ids[0], context=context)
            if not picking.origin and partner.partner_type in ('internal', 'intermission', 'section'):
                return {
                    'value': {'partner_id2': False, 'partner_id': False,},
                    'warning': {
                        'title': _('Error'),
                        'message': _("In a PICK from scratch, your are not allowed to choose this type of partner."),
                    },
                }

        return {'value': v,
                'domain': d}

    def return_to_state(self, cr, uid, ids, context=None):
        '''
        Return to initial state if the picking is 'Import in progress'
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for pick in self.read(cr, uid, ids, ['state_before_import'], context=context):
            self.write(cr, uid, [pick['id']], {'state': pick['state_before_import']}, context=context)

        return True

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the picking to done
        '''
        move_ids = []

        if isinstance(ids, (int, long)):
            ids = [ids]

        for pick in self.browse(cr, uid, ids, context=context):
            for move in pick.move_lines:
                if move.state not in ('cancel', 'done'):
                    move_ids.append(move.id)

        # Set all stock moves to done
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        return True

    def expired_assign(self, cr, uid, ids, context=False):
        '''
        Check the moves' availability for INT created to quarantine/destroy expired products
        '''
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        wf_service = netsvc.LocalService("workflow")

        new_moves_ids_to_confirm = []
        move_ids_to_assign = []
        pick_ids_to_assign = []

        for pick in self.browse(cr, uid, ids, context=context):
            for move in pick.move_lines:
                if pick.from_manage_expired and not move.prodlot_id:
                    raise osv.except_osv(_('Warning !'),
                                         _('All lines of Internal Moves created with Manage Expired Stock should have a batch number.'))
                if move.state == 'confirmed':
                    available_qty = lot_obj.read(cr, uid, move.prodlot_id.id, ['stock_available'],
                                                 context={'location_id': move.location_id.id})['stock_available']
                    if available_qty >= move.product_qty > 0.00:
                        move_ids_to_assign.append(move.id)
                        # picking to available
                        if pick.id not in pick_ids_to_assign:
                            pick_ids_to_assign.append(pick.id)
                    elif move.product_qty > available_qty > 0.00:
                        # update the move
                        move_obj.write(cr, uid, move.id, {'product_qty': available_qty}, context=context)
                        move_ids_to_assign.append(move.id)
                        # split with new qty
                        split_move_id = move_obj.copy(cr, uid, move.id, {'product_qty': move.product_qty - available_qty}, context=context)
                        new_moves_ids_to_confirm.append(split_move_id)
                        # picking to available
                        if pick.id not in pick_ids_to_assign:
                            pick_ids_to_assign.append(pick.id)

        move_obj.action_confirm(cr, uid, new_moves_ids_to_confirm, context=context)
        move_obj.force_assign(cr, uid, move_ids_to_assign, context=context)
        for pick_id in pick_ids_to_assign:
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)

        return True

    @check_cp_rw
    def force_assign(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self).force_assign(cr, uid, ids)
        for pick in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, 'Force availability ran on stock.picking id:%s (%s)' % (
                pick['id'], pick['name'],
            ))
        return res

    @check_cp_rw
    def cancel_assign(self, cr, uid, ids, *args, **kwargs):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self).cancel_assign(cr, uid, ids)
        for pick in self.read(cr, uid, ids, ['name']):
            self.infolog(cr, uid, 'Cancel availability ran on stock.picking id:%s (%s)' % (
                pick['id'], pick['name'],
            ))
        return res

    def check_availability_manually(self, cr, uid, ids, context=None, initial_location=False):
        '''
        US-2677 : Cancel assigned moves' availability and re-check it
        '''
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        prodlot_obj = self.pool.get('stock.production.lot')

        moves_ids_to_reassign = []
        product_data = {}
        qties = {}
        move_ids = move_obj.search(cr, uid, [('picking_id', 'in', ids), ('state', '=', 'assigned')], context=context)
        if move_ids:
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                prodlot_id = move.prodlot_id and move.prodlot_id.id or False
                key = (move.product_id.id, move.location_id.id, prodlot_id)

                if key in product_data:
                    product_data[key] += uom_obj._compute_qty(cr, uid, move.product_uom.id,
                                                              move.product_qty, move.product_id.uom_id.id)
                else:
                    product_data[key] = uom_obj._compute_qty(cr, uid, move.product_uom.id,
                                                             move.product_qty, move.product_id.uom_id.id)

                if key not in qties:
                    if prodlot_id:
                        qties[key] = prodlot_obj.read(cr, uid, prodlot_id, ['stock_available'],
                                                      context={'location_id': move.location_id.id})['stock_available']
                    else:
                        qties[key] = prod_obj.read(cr, uid, move.product_id.id, ['qty_available'],
                                                   context={'location_id': move.location_id.id})['qty_available']

                if product_data[key] > qties[key] or (move.product_id.batch_management and not key[2] and qties[key]):
                    moves_ids_to_reassign.append(move.id)

        if moves_ids_to_reassign:
            move_obj.cancel_assign(cr, uid, moves_ids_to_reassign, context=context)
            if initial_location:
                move_obj.write(cr, uid, moves_ids_to_reassign, {'location_id': initial_location}, context=context)
            for pick_id in ids:
                # trigger transition from Assigned to Confirmed if needed
                netsvc.LocalService("workflow").trg_write(uid, 'stock.picking', pick_id, cr)
        return self.action_assign(cr, uid, ids, context=context)


    def export_pick(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids,(int,long)):
            ids = [ids]

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pick.export.xls',
            'datas': {'ids': ids},
            'context': context,
        }


    @check_rw_warning
    def call_cancel_wizard(self, cr, uid, ids, context=None):
        '''
        Call the wizard of cancelation (ask user if he wants to resource goods)
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick_data in self.read(cr, uid, ids, ['sale_id', 'purchase_id', 'subtype', 'state'], context=context):
            # if draft and shipment is in progress, we cannot cancel
            if pick_data['subtype'] == 'picking' and pick_data['state'] in ('draft',):
                if self.has_picking_ticket_in_progress(cr, uid, [pick_data['id']], context=context)[pick_data['id']]:
                    raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and      try to cancel again.'))
            # if not draft or qty does not match, the shipping is already in progress
            elif pick_data['subtype'] == 'picking' and pick_data['state'] in ('done',):
                raise osv.except_osv(_('Warning !'), _('The shipment process is completed and cannot be canceled!'))

            if pick_data['sale_id'] or pick_data['purchase_id']:
                return {'type': 'ir.actions.act_window',
                        'res_model': 'stock.picking.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': dict(context, active_id=pick_data['id'])}

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_validate(uid, 'stock.picking', id, 'button_cancel', cr)

        return True

    def _do_partial_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking

        - allow to modify the defaults data for move creation and copy
        '''
        defaults = kwargs.get('defaults')
        assert defaults is not None, 'missing defaults'

        return defaults

    def _picking_done_cond(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking

        - allow to conditionally execute the picking processing to done
        '''
        return True

    def _custom_code(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking

        - allow to execute specific custom code before processing picking to done
        - no supposed to modify partial_datas
        '''
        return True

    # UF-1617: Empty hook here, to be implemented in sync modules
    def _hook_create_sync_messages(self, cr, uid, ids, context=None):
        return True

    # @@@override stock>stock.py>stock_picking>_get_invoice_type
    def _get_invoice_type(self, pick):
        src_usage = dest_usage = None
        inv_type = None
        if pick.invoice_state == '2binvoiced':
            if pick.move_lines:
                src_usage = pick.move_lines[0].location_id.usage
                dest_usage = pick.move_lines[0].location_dest_id.usage
            if pick.type == 'out' and dest_usage == 'supplier':
                inv_type = 'in_refund'
            elif pick.type == 'out' and dest_usage == 'customer':
                inv_type = 'out_invoice'
            elif (pick.type == 'in' and src_usage == 'supplier') or (pick.type == 'internal'):
                inv_type = 'in_invoice'
            elif pick.type == 'in' and src_usage == 'customer':
                inv_type = 'out_refund'
            else:
                inv_type = 'out_invoice'
        return inv_type


    def draft_force_assign(self, cr, uid, ids, context=None):
        '''
        Confirm all stock moves
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self).draft_force_assign(cr, uid, ids)

        move_obj = self.pool.get('stock.move')
        move_ids = move_obj.search(cr, uid, [('state', '=', 'draft'), ('picking_id', 'in', ids)], context=context)
        move_obj.action_confirm(cr, uid, move_ids, context=context)

        return res

    def is_invoice_needed(self, cr, uid, sp=None, invoice_type=None):
        """
        Check if invoice is needed. Cases where we do not need invoice:
        - OUT from scratch (without purchase_id and sale_id) AND stock picking type in internal, external or esc
        - OUT from FO AND stock picking type in internal, external or esc
        So all OUT that have internal, external or esc should return FALSE from this method.
        This means to only accept intermission and intersection invoicing on OUT with reason type "Deliver partner".
        """
        res = True
        if not sp:
            return res
        # Fetch some values
        try:
            rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        except ValueError:
            rt_id = False
        # type out and partner_type in internal, external or esc
        if sp.type == 'out' and not sp.purchase_id and not sp.sale_id and sp.partner_id.partner_type in ['external', 'internal', 'esc']:
            res = False
        if sp.type == 'out' and not sp.purchase_id and not sp.sale_id and rt_id and sp.partner_id.partner_type in ['intermission', 'section']:
            # Search all stock moves attached to this one. If one of them is deliver partner, then is_invoice_needed is ok
            res = False
            sm_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', sp.id)])
            if sm_ids:
                if self.pool.get('stock.move').search_exist(cr, uid,
                                                            [('id', 'in', sm_ids),
                                                             ('reason_type_id', '=', rt_id)]):
                    res = True
        # partner is itself (those that own the company)
        company_partner_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id
        if sp.partner_id.id == company_partner_id.id:
            res = False

        # (US-952) Move out on an external partner should not create a Stock Transfer Voucher
        # US-1212: but should create refund
        if sp.type == 'out' and sp.partner_id.partner_type == 'external' and invoice_type != 'in_refund':
            res = False

        return res

    def _create_invoice(self, cr, uid, stock_picking):
        """
        Creates an invoice for the specified stock picking
        @param stock_picking browse_record: The stock picking for which to create an invoice
        """
        picking_type = False
        invoice_type = self._get_invoice_type(stock_picking)

        # Check if no invoice needed
        if not self.is_invoice_needed(cr, uid, stock_picking, invoice_type):
            return

        # we do not create invoice for procurement_request (Internal Request)
        if not stock_picking.sale_id.procurement_request and stock_picking.subtype == 'standard':
            if stock_picking.type == 'in' or stock_picking.type == 'internal':
                if invoice_type == 'out_refund':
                    picking_type = 'sale_refund'
                else:
                    picking_type = 'purchase'
            elif stock_picking.type == 'out':
                if invoice_type == 'in_refund':
                    picking_type = 'purchase_refund'
                else:
                    picking_type = 'sale'

            # Set journal type based on picking type
            journal_type = picking_type

            # Disturb journal for invoice only on intermission partner type
            if stock_picking.partner_id.partner_type == 'intermission':
                journal_type = 'intermission'

            # Find appropriate journal
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', journal_type),
                                                                            ('is_current_instance', '=', True)])
            if not journal_ids:
                raise osv.except_osv(_('Warning'), _('No journal of type %s found when trying to create invoice for picking %s!') % (journal_type, stock_picking.name))

            # Create invoice
            self.action_invoice_create(cr, uid, [stock_picking.id], journal_ids[0], False, invoice_type, {})

    def action_done(self, cr, uid, ids, context=None):
        """
        Create automatically invoice or NOT (regarding some criteria in is_invoice_needed)
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self).action_done(cr, uid, ids, context=context)

        move_obj = self.pool.get('stock.move')
        # In case of processed IN, we close the linked PO lines:
        wf_service = netsvc.LocalService("workflow")

        if res:
            for sp in self.browse(cr, uid, ids):
                self.update_processing_info(cr, uid, sp.id, False, {
                    'close_in': _('Invoice creation in progress'),
                }, context=context)

                # close PO line if needed:
                if sp.type == 'in' and sp.purchase_id:
                    for stock_move in sp.move_lines:
                        if stock_move.purchase_line_id:
                            # get done qty for this PO line:
                            domain = [('purchase_line_id', '=', stock_move.purchase_line_id.id), ('state', 'in', ['done', 'cancel', 'cancel_r']), ('type', '=', 'in')]
                            done_moves = move_obj.search(cr, uid, domain, context=context)
                            done_qty = 0
                            for done_move in move_obj.browse(cr, uid, done_moves, context=context):
                                done_qty += done_move.product_qty
                            # if stock moves sum is equal to PO line qty, then PO line is done:
                            if done_qty >= stock_move.purchase_line_id.product_qty:
                                wf_service.trg_validate(uid, 'purchase.order.line', stock_move.purchase_line_id.id, 'done', cr)

                    po_id = sp.purchase_id.id
                    bo_id = False
                    if sp.backorder_id and sp.backorder_id.state not in ('done', 'cancel'):
                        bo_id = sp.backorder_id.id
                    else:
                        picking_ids = self.search(cr, uid, [
                            ('purchase_id', '=', po_id),
                            ('id', '!=', sp.id),
                            ('state', 'not in', ['done', 'cancel']),
                        ], limit=1, context=context)
                        if picking_ids:
                            bo_id = picking_ids[0]

                    if bo_id:
                        netsvc.LocalService("workflow").trg_change_subflow(uid, 'purchase.order', [po_id], 'stock.picking', [sp.id], bo_id, cr)

                self._create_invoice(cr, uid, sp)

        return res

    def _get_price_unit_invoice(self, cr, uid, move_line, type):
        '''
        Update the Unit price according to the UoM received and the UoM ordered
        '''
        res = super(stock_picking, self)._get_price_unit_invoice(cr, uid, move_line, type)
        if type == 'in_refund':
            if move_line.picking_id and move_line.picking_id.purchase_id:
                po_line_obj = self.pool.get('purchase.order.line')
                po_line_id = po_line_obj.search(cr, uid, [('order_id', '=', move_line.picking_id.purchase_id.id),
                                                          ('product_id', '=', move_line.product_id.id),
                                                          ('state', '!=', 'cancel')
                                                          ], limit=1)
                if po_line_id:
                    return po_line_obj.read(cr, uid, po_line_id[0], ['price_unit'])['price_unit']

        if move_line.purchase_line_id:
            po_uom_id = move_line.purchase_line_id.product_uom.id
            move_uom_id = move_line.product_uom.id
            uom_ratio = self.pool.get('product.uom')._compute_price(cr, uid, move_uom_id, 1, po_uom_id)
            return res / uom_ratio

        return res

    def action_confirm(self, cr, uid, ids, context=None):
        """
            stock.picking: action confirm
            if INCOMING picking: confirm and check availability
        """
        super(stock_picking, self).action_confirm(cr, uid, ids, context=context)
        move_obj = self.pool.get('stock.move')

        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.read(cr, uid, ids, ['move_lines', 'type']):
            if pick['move_lines'] and pick['type'] == 'in':
                not_assigned_move = move_obj.search(cr, uid,
                                                    [('id', 'in', pick['move_lines']),
                                                     ('state', '=', 'confirmed')])
                if not_assigned_move:
                    move_obj.action_assign(cr, uid, not_assigned_move)
        return True


    # UF-1617: Handle the new state Shipped of IN
    def action_shipped_wkf(self, cr, uid, ids, context=None):
        """ Changes picking state to assigned.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.write(cr, uid, ids, {'state': 'shipped'})
        self.log_picking(cr, uid, ids, context=context)
        move_obj = self.pool.get('stock.move')

        for pick in self.read(cr, uid, ids, ['move_lines', 'type']):
            if pick['move_lines'] and pick['type'] == 'in':
                not_assigned_move = pick['move_lines']
                if not_assigned_move:
                    move_obj.write(cr, uid, not_assigned_move, {'state':
                                                                'confirmed'})
                    move_obj.action_assign(cr, uid, not_assigned_move)

        return True


    def action_updated_wkf(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'updated'}, context=context)

        return True


    @check_cp_rw
    def change_all_location(self, cr, uid, ids, context=None):
        '''
        Launch the wizard to change all destination location of stock moves
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return {'type': 'ir.actions.act_window',
                'res_model': 'change.dest.location',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': self.pool.get('change.dest.location').create(cr, uid, {'picking_id': ids[0]}, context=context),
                'context': context,
                'target': 'new'}

stock_picking()

# ----------------------------------------------------
# Move
# ----------------------------------------------------

#
# Fields:
#   location_dest_id is only used for predicting futur stocks
#
class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock Move with hook"

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the stock move to manually done
        '''
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def _get_from_dpo(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the move has a dpo_id
        '''
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for move in self.read(cr, uid, ids, ['dpo_id'], context=context):
            res[move['id']] = False
            if move['dpo_id']:
                res[move['id']] = True

        return res

    def _search_from_dpo(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the list of moves from or not from DPO
        '''
        for arg in args:
            if arg[0] == 'from_dpo' and arg[1] == '=':
                return [('dpo_id', '!=', False)]
            elif arg[0] == 'from_dpo' and arg[1] in ('!=', '<>'):
                return [('dpo_id', '=', False)]

        return []

    def _default_location_destination(self, cr, uid, context=None):
        if not context:
            context = {}
        if context.get('picking_type') == 'out':
            partner_id = context.get('partner_id')
            company_part_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id
            if partner_id != company_part_id:
                wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
                if wh_ids:
                    return self.pool.get('stock.warehouse').read(cr, uid, wh_ids[0], ['lot_output_id'])['lot_output_id'][0]

        return False

    def _default_is_ext_cu(self, cr, uid, context=None):
        if not context:
            context = {}
        if context.get('ext_cu', False):
            return True
        return False


    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        product_tbd = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = dict([(x, {'inactive_product': False,
                         'inactive_error': ''}) for x in ids])
        pick_ids = set()
        pick_ids_add = pick_ids.add
        product_ids = set()
        product_ids_add = product_ids.add
        for stock_move_dict in self.read(cr, uid, ids, ['picking_id', 'product_id'],
                                         context=context):
            if stock_move_dict['picking_id']:
                pick_ids_add(stock_move_dict['picking_id'][0])
            product_ids_add(stock_move_dict['product_id'][0])

        product_ids = product_ids.difference((product_tbd,))
        product_module = self.pool.get('product.product')
        inactive_product_ids = product_module.search(cr, uid,
                                                     [('id', 'in', list(product_ids)), ('active', '=', False)],
                                                     context=context)
        pick_ids = self.pool.get('stock.picking').search(cr,
                                                         uid, [('id', 'in', list(pick_ids)), ('state', 'not in', ('cancel', 'done'))],
                                                         context=context)
        stock_move_inactive_prod_ids = self.search(cr, uid,
                                                   [('id', 'in', ids),
                                                    ('picking_id', 'in', pick_ids),
                                                    ('product_id', 'in', inactive_product_ids)],
                                                   context=context)
        for stock_move_id in stock_move_inactive_prod_ids:
            res[stock_move_id]={'inactive_product': True,
                                'inactive_error': _('The product in line is inactive !')}
        return res

    def _is_expired_lot(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the lot of stock move is expired
        '''
        res = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        product_tbd = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = {'expired_lot': False, 'product_tbd': False}
            if move.prodlot_id and move.prodlot_id.is_expired:
                res[move.id]['expired_lot'] = True

            if move.product_id.id == product_tbd:
                res[move.id]['product_tbd'] = True

        return res

    def _is_price_changed(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = False
            if m.purchase_line_id and abs(m.purchase_line_id.price_unit - m.price_unit) > 10**-3:
                res[m.id] = True

        return res

    def _get_state_to_display(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context is None:
            context = {}

        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = self.pool.get('ir.model.fields').get_browse_selection(cr, uid, move, 'state', context=context)
            if move.state == 'cancel' and move.has_to_be_resourced:
                res[move.id] = 'Cancelled-r'

        return res



    _columns = {
        'price_unit': fields.float('Unit Price', digits_compute=dp.get_precision('Picking Price Computation'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Closed'), ('cancel', 'Cancelled'), ('hidden', 'Hidden')], 'State', readonly=True, select=True,
                                  help='When the stock move is created it is in the \'Draft\' state.\n After that, it is set to \'Not Available\' state if the scheduler did not find the products.\n When products are reserved it is set to \'Available\'.\n When the picking is done the state is \'Closed\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'state_to_display': fields.function(_get_state_to_display, type='char', method=True, string='State', readonly=True),
        'address_id': fields.many2one('res.partner.address', 'Delivery address', help="Address of partner", readonly=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain="[('partner_id', '=', partner_id)]"),
        'partner_id2': fields.many2one('res.partner', 'Partner', required=False),
        'already_confirmed': fields.boolean(string='Already confirmed'),
        'dpo_id': fields.many2one('purchase.order', string='Direct PO', help='PO from where this stock move is sourced.'),
        'dpo_line_id': fields.integer(string='Direct PO line', help='PO line from where this stock move is sourced (for sync. engine).'),
        'from_dpo': fields.function(_get_from_dpo, fnct_search=_search_from_dpo, type='boolean', method=True, store=False, string='From DPO ?'),
        'sync_dpo': fields.boolean(string='Sync. DPO'),
        'from_wkf_line': fields.related('picking_id', 'from_wkf', type='boolean', string='Internal use: from wkf'),
        'is_ext_cu': fields.boolean(string='Ext. CU'),
        'fake_state': fields.related('state', type='char', store=False, string="Internal use"),
        'processed_stock_move': fields.boolean(string='Processed Stock Move'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Error', store=False, multi='inactive'),
        'to_correct_ok': fields.boolean(string='Line to correct'),
        'text_error': fields.text(string='Error', readonly=True),
        'inventory_ids': fields.many2many('stock.inventory', 'stock_inventory_move_rel', 'move_id', 'inventory_id', 'Created Moves'),
        'expired_lot': fields.function(_is_expired_lot, method=True, type='boolean', string='Lot expired', store=False, multi='attribute'),
        'product_tbd': fields.function(_is_expired_lot, method=True, type='boolean', string='TbD', store=False, multi='attribute'),
        'has_to_be_resourced': fields.boolean(string='Has to be resourced'),
        'from_wkf': fields.related('picking_id', 'from_wkf', type='boolean', string='From wkf'),
        'price_changed': fields.function(_is_price_changed, method=True, type='boolean', string='Price changed',
                                         store={
                                             'stock.move': (lambda self, cr, uid, ids, c=None: ids, ['price_unit', 'purchase_order_line'], 10),
                                         },
                                         ),
        'linked_incoming_move': fields.many2one('stock.move', 'Linked Incoming move', readonly=True, help="Link between INT and IN")
    }

    _defaults = {
        'location_dest_id': _default_location_destination,
        'processed_stock_move': False,  # to know if the stock move has already been partially or completely processed
        'inactive_product': False,
        'inactive_error': lambda *a: '',
        'has_to_be_resourced': False,
        'is_ext_cu': _default_is_ext_cu,
    }

    @check_rw_warning
    def call_cancel_wizard(self, cr, uid, ids, context=None):
        '''
        Call the wizard to ask user if he wants to re-source the need
        '''
        mem_obj = self.pool.get('stock.picking.processing.info')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        backmove_ids = self.search(cr, uid, [('backmove_id', 'in', ids), ('state', 'not in', ('done', 'cancel'))], context=context)

        for move in self.browse(cr, uid, ids, context=context):
            mem_ids = mem_obj.search_exist(cr, uid, [
                ('picking_id', '=', move.picking_id.id),
                ('end_date', '=', False),
            ], context=context)
            if mem_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('The processing of the picking is in progress - You can\'t cancel this move.'),
                )
            if backmove_ids or move.product_qty == 0.00:
                raise osv.except_osv(_('Error'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try to cancel again.'))
            if (move.sale_line_id and move.sale_line_id.order_id) or (move.purchase_line_id and move.purchase_line_id.order_id and move.purchase_line_id.linked_sol_id):
                vals = {'move_id': ids[0]}
                if 'from_int' in context:
                    """UFTP-29: we are in a INT stock move - line by line cancel
                    do not allow Cancel and Resource if move linked to a PO line
                    => the INT is sourced from a PO-IN flow
                    'It should only be possible to resource an INT created from the sourcing of an IR / FO from stock,
                     but not an INT created by an incoming shipment (Origin field having a "PO" ref.)'
                    """
                    if move.purchase_line_id:
                        vals['cancel_only'] = True

                if move.sale_line_id and move.sale_line_id.type == 'make_to_order':
                    vals['cancel_only'] = True

                wiz_id = self.pool.get('stock.move.cancel.wizard').create(cr, uid, vals, context=context)

                return {'type': 'ir.actions.act_window',
                        'res_model': 'stock.move.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': wiz_id,
                        'context': context}
            if move.type == 'in' and move.purchase_line_id:
                vals = {'move_id': ids[0]}

                if not move.purchase_line_id.linked_sol_id:
                    vals['cancel_only'] = True

                wiz_id = self.pool.get('stock.move.cancel.wizard').create(cr, uid, vals, context=context)

                return {'type': 'ir.actions.act_window',
                        'res_model': 'stock.move.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': wiz_id,
                        'context': context}


        return self.unlink(cr, uid, ids, context=context)

    def get_price_changed(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        move = self.browse(cr, uid, ids[0], context=context)
        if move.price_changed:
            price_unit = move.price_unit
            raise osv.except_osv(
                _('Information'),
                _('The initial unit price (coming from Purchase order line) is %s %s - The new unit price is %s %s') % (
                    move.purchase_line_id.price_unit,
                    move.purchase_line_id.currency_id.name,
                    price_unit,
                    move.price_currency_id.name)
            )

        return True

    @check_cp_rw
    def confirm_and_force_assign(self, cr, uid, ids, context=None, vals=None):
        '''
        when action_confirm and force_assign are both called, it is faster to
        use confirm_and_force_assign to do only one write per move.
        '''
        if not context:
            context = {}
        if vals is None:
            vals = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_product_quantity(cr, uid, ids, context=context)
        vals = {'already_confirmed': True}

        ids_assign = ids[:]
        self.prepare_force_assign(cr, uid, ids_assign, context=context)

        # if ids and ids_assign are equal, it is possible to call one write on
        # all ids
        res = []
        if set(ids) == set(ids_assign):
            self.prepare_action_confirm(cr, uid, ids, context)
            vals.update({'state': 'assigned'})
            self.write(cr, uid, ids, vals)
        else:
            res = super(stock_move, self).action_confirm(cr, uid,
                                                         ids=ids, context=context, vals=vals)
            res = super(stock_move, self).force_assign(cr, uid,
                                                       ids=ids_assign, context=context)
        return res

    def prepare_force_assign(self, cr, uid, ids, context=None):
        '''
        split in smaller methods to ease the reusing of the code in other parts
        '''
        product_tbd = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

        picking_name_dict = {}
        pick_obj = self.pool.get('stock.picking')
        if isinstance(ids, (int, long)):
            ids = [ids]

        for move in self.read(cr, uid, ids,
                              ['product_id', 'from_wkf_line', 'picking_id', 'line_number'], context=context):
            if move['product_id'][0] == product_tbd and move['from_wkf_line']:
                ids.pop(ids.index(move['id']))
            else:
                picking_id = move['picking_id'] and move['picking_id'][0] or False
                if picking_id not in picking_name_dict:
                    picking_id_name = pick_obj.read(cr, uid,
                                                    picking_id, ['name'], context)['name']
                    picking_name_dict[picking_id] = picking_id_name
                else:
                    picking_id_name = picking_name_dict[picking_id]

                self.infolog(cr, uid, 'Force availability run on stock move #%s (id:%s) of picking id:%s (%s)' % (
                    move['line_number'], move['id'], picking_id, picking_id_name,
                ))

    @check_cp_rw
    def force_assign(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.prepare_force_assign(cr, uid, ids, context=context)
        return super(stock_move, self).force_assign(cr, uid, ids, context=context)

    def _uom_constraint(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.read(cr, uid, ids, ['product_id', 'product_uom'], context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid,
                                                        move['product_id'][0], move['product_uom'][0], context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))

        return True

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is restriction on lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id and move.picking_id.type == 'internal' and move.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, move.product_id.id, vals={'constraints': {'location_id': move.location_dest_id}}, context=context):
                    return False

        return True

    _constraints = [(_uom_constraint, 'Constraint error on Uom', [])]

    def create(self, cr, uid, vals, context=None):
        '''
        1/ Add the corresponding line number: (delivery_mechanism)
             - if a corresponding purchase order line or sale order line
               exist, we take the line number from there
        2/ Add subtype on creation if product is specified (product_asset)
        3/ Complete info normally generated by javascript on_change function (specific_rules)
        4/ Update the partner or the address according to the other (stock_override)
        5/ Set default values for data.xml and tests.yml (reason_types)
        '''
        # Objects
        pick_obj = self.pool.get('stock.picking')
        seq_obj = self.pool.get('ir.sequence')
        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')
        addr_obj = self.pool.get('res.partner.address')
        user_obj = self.pool.get('res.users')
        location_obj = self.pool.get('stock.location')
        partner_obj = self.pool.get('res.partner')

        if context is None:
            context = {}

        id_cross = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        id_nonstock = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
        id_pack = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1]

        # line number correspondance to be checked with Magali
        val_type = vals.get('type', False)
        picking = False
        if vals.get('picking_id', False):
            picking = pick_obj.read(cr, uid, vals['picking_id'],
                                    ['move_sequence_id', 'type', 'reason_type_id'], context=context)
            if not vals.get('line_number', False):
                # new number need - gather the line number form the sequence
                sequence_id = picking['move_sequence_id'][0]
                line = seq_obj.get_id(cr, uid, sequence_id, code_or_id='id', context=context)
                # update values with line value
                vals['line_number'] = line

            if not val_type:
                val_type = picking['type']

        if vals.get('product_id', False):
            product = prod_obj.read(cr, uid, vals['product_id'],
                                    ['subtype',
                                     'type',
                                     'batch_management',
                                     'perishable',],
                                    context=context)
            vals['subtype'] = product['subtype']

            if not context.get('non_stock_noupdate') and vals.get('picking_id') \
                    and product['type'] == 'consu' \
                    and vals.get('location_dest_id') != id_cross:
                if vals.get('sale_line_id'):
                    if picking['type'] == 'out':
                        vals['location_id'] = id_cross
                    else:
                        vals['location_id'] = id_nonstock
                    vals['location_dest_id'] = id_pack
                else:
                    if picking['type'] != 'out':
                        vals['location_dest_id'] = id_nonstock

            if product['batch_management']:
                vals['hidden_batch_management_mandatory'] = True
            elif product['perishable']:
                vals['hidden_perishable_mandatory'] = True
            else:
                vals.update({'hidden_batch_management_mandatory': False,
                             'hidden_perishable_mandatory': False})

        if not vals.get('partner_id2', False):
            if vals.get('address_id', False):
                addr = addr_obj.read(cr, uid, vals['address_id'], ['partner_id'], context=context)
                vals['partner_id2'] = addr['partner_id'] and addr['partner_id'][0] or False
            else:
                vals['partner_id2'] = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id

        if not vals.get('address_id', False) and vals.get('partner_id2', False):
            addr = partner_obj.address_get(cr, uid, vals['partner_id2'], ['delivery', 'default'])
            vals['address_id'] = addr.get('delivery', addr.get('default', False))

        if val_type == 'in' and not vals.get('date_expected'):
            vals['date_expected'] = time.strftime('%Y-%m-%d %H:%M:%S')

        if vals.get('date_expected'):
            vals['date'] = vals.get('date_expected')

        if vals.get('location_dest_id', False):
            if not vals.get('reason_type_id', False):
                loc_dest_id = location_obj.read(cr, uid, vals['location_dest_id'],
                                                ['virtual_location', 'scrap_location', 'usage'], context=context)
                if not loc_dest_id['virtual_location']:
                    if loc_dest_id['scrap_location']:
                        vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
                    elif loc_dest_id['usage'] == 'inventory':
                        vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]

            # If the source location and teh destination location are the same, the state should be 'Closed'
            if vals.get('location_id', False) == vals.get('location_dest_id', False):
                vals['state'] = 'done'

        # Change the reason type of the picking if it is not the same
        if picking and not context.get('from_claim') and not context.get('from_chaining') \
                and vals.get('reason_type_id', False) != picking['reason_type_id'][0]:
            other_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
            pick_obj.write(cr, uid, [picking['id']], {'reason_type_id': other_type_id}, context=context)

        return super(stock_move, self).create(cr, uid, vals, context=context)

    def _check_locations_active(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        wrong_loc_ids = self.search(cr, uid, [('id', 'in', ids), '|', ('location_id.active', '=', False), ('location_dest_id.active', '=', False)], context=context)
        if wrong_loc_ids:
            error = []
            for move in self.browse(cr, uid, wrong_loc_ids, fields_to_fetch=['picking_id', 'line_number', 'product_id', 'location_id', 'location_dest_id']):
                if not move.location_id.active:
                    error.append(_("Source Location %s is inactive, can't process %s, line %s, product %s") % (move.location_id.name, move.picking_id and move.picking_id.name or '', move.line_number, move.product_id and move.product_id.default_code or ''))
                if not move.location_dest_id.active:
                    error.append(_("Destination Location %s is inactive, can't process %s, line %s, product %s") % (move.location_dest_id.name, move.picking_id and move.picking_id.name or '', move.line_number, move.product_id and move.product_id.default_code or ''))

            if error:
                raise osv.except_osv(_('Warning'), "\n".join(error[0:10]))

        return True

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
        if not ids:
            return True
        # Objects
        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        pick_obj = self.pool.get('stock.picking')
        addr_obj = self.pool.get('res.partner.address')
        partner_obj = self.pool.get('res.partner')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        product = None
        pick_dict = {}
        id_cross = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]

        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.read(cr, uid, vals['product_id'],
                                    ['batch_management', 'perishable', 'type'], context=context)
            vals.update({
                'hidden_batch_management_mandatory': product['batch_management'],
                'hidden_perishable_mandatory': product['perishable'],
            })

            if vals.get('picking_id'):
                pick_dict = pick_obj.read(cr, uid, vals['picking_id'], ['type'], context=context)

        if pick_dict and product and product['type'] == 'consu' and vals.get('location_dest_id') != id_cross:
            id_nonstock = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')
            if vals.get('sale_line_id'):
                id_pack = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')
                vals.update({
                    'location_id': pick_dict['type'] == 'out' and id_cross or id_nonstock[1],
                    'location_dest_id': id_pack[1],
                })
            elif pick_dict['type'] != 'out':
                vals['location_dest_id'] = id_nonstock[1]

        if vals.get('location_dest_id'):
            dest_dict = loc_obj.read(cr, uid, vals['location_dest_id'],
                                     ['virtual_location', 'usage', 'scrap_location'], context=context)
            if dest_dict['usage'] == 'inventory' and not dest_dict['virtual_location']:
                vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            if dest_dict['scrap_location'] and not dest_dict['virtual_location']:
                vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
            # if the source location and the destination location are the same, the state is done
            if 'location_id' in vals and vals['location_dest_id'] == vals['location_id']:
                vals['state'] = 'done'

        addr = vals.get('address_id')
        partner = vals.get('partner_id2')

        no_add = not addr and partner
        no_part = not partner and addr

        if vals.get('date_expected') and vals.get('state') not in ('done', 'cancel'):
            if self.search_exist(cr, uid, [('id', 'in', ids), ('state', 'not in', ['done', 'cancel'])], context=context):
                vals['date'] = vals.get('date_expected')
        if no_add:
            if self.search_exist(cr, uid, [('id', 'in', ids), ('partner_id', '!=', vals.get('partner_id2'))], context=context):
                addr = partner_obj.address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
                vals['address_id'] = addr.get('delivery', False) or addr.get('default')
        if no_part:
            if self.search_exist(cr, uid, [('id', 'in', ids), ('address_id', '!=', vals['address_id'])], context=context):
                addr = addr_obj.read(cr, uid, vals.get('address_id'), ['partner_id'], context=context)
                vals['partner_id2'] = addr['partner_id'] and addr['partner_id'][0] or False
        if 'reason_type_id' in vals:
            pick_ids = pick_obj.search(cr, uid, [('reason_type_id', '!=', vals['reason_type_id']), ('move_lines', 'in', ids)], order='NO_ORDER', context=context)
            if pick_ids:
                other_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
                pick_obj.write(cr, uid, pick_ids, {'reason_type_id': other_type_id}, context=context)

        return super(stock_move, self).write(cr, uid, ids, vals, context=context)


    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        v = {}
        d = {}

        if not partner_id:
            v.update({'address_id': False})
        else:
            d.update({'address_id': [('partner_id', '=', partner_id)]})

        if address_id:
            addr = self.pool.get('res.partner.address').browse(cr, uid, address_id, context=context)

        if not address_id or addr.partner_id.id != partner_id:
            addr = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
            if not addr.get('delivery'):
                addr = addr.get('default')
            else:
                addr = addr.get('delivery')
            v.update({'address_id': addr})

        return {'value': v,
                'domain': d}

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        Remove the already confirmed flag
        '''
        if default is None:
            default = {}
        default.update({'already_confirmed':False})

        return super(stock_move, self).copy(cr, uid, id, default, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        Remove the dpo_line_id link
        '''
        if default is None:
            default = {}

        if not 'dpo_line_id' in default:
            default['dpo_line_id'] = 0

        if not 'sync_dpo' in default:
            default['sync_dpo'] = False

        return super(stock_move, self).copy_data(cr, uid, id, default, context=context)

    def check_product_quantity(self, cr, uid, ids, context=None):
        '''
        check that all move have a product quantity > 0
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        no_product = self.search(cr, uid, [
            ('id', 'in', ids),
            ('product_qty', '<=', 0.00),
        ], limit=1, order='NO_ORDER', context=context)

        if no_product:
            raise osv.except_osv(_('Error'), _('You cannot confirm a stock move without quantity.'))

    def _hook_move_cancel_state(self, cr, uid, *args, **kwargs):
        '''
        Change the state of the chained move
        '''
        if kwargs.get('context'):
            kwargs['context'].update({'call_unlink': True})
        return {'state': 'cancel'}, kwargs.get('context', {})


    def _hook_cancel_assign_batch(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the cancel_assign method from stock>stock.py>stock_move class

        -  it erases the batch number associated if any and reset the source location to the original one.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        prodlot_to_write_list = []
        for line in self.browse(cr, uid, ids, context):
            if line.prodlot_id:
                prodlot_to_write_list.append(line.id)
            # UF-2426: If the cancel is called from sync, do not change the source location!
            if not context.get('sync_message_execution', False) and line.location_id.location_id and line.location_id.location_id.usage != 'view':
                self.write(cr, uid, ids, {'location_id': line.location_id.location_id.id})
        self.write(cr, uid, prodlot_to_write_list, {'prodlot_id': False, 'expired_date': False})
        return True

    def check_assign(self, cr, uid, ids, context=None):
        res = super(stock_move, self).check_assign(cr, uid, ids, context=context)
        return res

    @check_cp_rw
    def cancel_assign(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_move, self).cancel_assign(cr, uid, ids, context=context)
        res = []

        fields_to_read = ['picking_id', 'product_id', 'product_uom', 'location_id',
                          'product_qty', 'product_uos_qty', 'location_dest_id',
                          'prodlot_id', 'asset_id', 'composition_list_id', 'line_number']
        stock_picking_obj = self.pool.get('stock.picking')

        qty_data = {}
        for move_data in self.read(cr, uid, ids, fields_to_read, context=context):
            search_domain = [('state', '=', 'confirmed'), ('id', '!=', move_data['id'])]
            picking_id = move_data['picking_id'] and move_data['picking_id'][0] or False

            self.infolog(cr, uid, 'Cancel availability run on stock move #%s (id:%s) of picking id:%s (%s)' % (
                move_data['line_number'],
                move_data['id'],
                picking_id,
                stock_picking_obj.read(cr, uid, picking_id, ['name'], context=context)['name'],
            ))

            for f in fields_to_read:
                if f in ('product_qty', 'product_uos_qty'):
                    continue
                d = move_data[f]
                if isinstance(move_data[f], tuple):
                    d = move_data[f][0]
                search_domain.append((f, '=', d))

            move_ids = self.search(cr, uid, search_domain, context=context)
            if move_ids:
                move = self.read(cr, uid, move_ids[0], ['product_qty', 'product_uos_qty'], context=context)
                res.append(move['id'])
                if move_data['id'] not in qty_data:
                    qty_data[move['id']] = {
                        'product_qty': move['product_qty'] + move_data['product_qty'],
                        'product_uos_qty': move['product_uos_qty'] + move_data['product_uos_qty'],
                    }
                else:
                    qty_data[move['id']] = {
                        'product_qty': move['product_qty'] + qty_data[move_data['id']]['product_qty'],
                        'product_uos_qty': move['product_uos_qty'] + qty_data[move_data['id']]['product_uos_qty'],
                    }

                self.write(cr, uid, [move['id']], qty_data[move['id']].copy(), context=context)

                # Update all link objects
                proc_ids = self.pool.get('procurement.order').search(cr, uid,
                                                                     [('move_id', '=', move_data['id'])], order='NO_ORDER',context=context)
                if proc_ids:
                    self.pool.get('procurement.order').write(cr, uid, proc_ids, {'move_id': move['id']}, context=context)

                pol_ids = self.pool.get('purchase.order.line').search(cr, uid,
                                                                      [('move_dest_id', '=', move_data['id'])],
                                                                      order='NO_ORDER', context=context)
                if pol_ids:
                    self.pool.get('purchase.order.line').write(cr, uid, pol_ids, {'move_dest_id': move['id']}, context=context)

                move_dest_ids = self.search(cr, uid, [('move_dest_id', '=',
                                                       move_data['id'])], order='NO_ORDER', context=context)
                if move_dest_ids:
                    self.write(cr, uid, move_dest_ids, {'move_dest_id': move['id']}, context=context)

                backmove_ids = self.search(cr, uid, [('backmove_id', '=',
                                                      move_data['id'])], order='NO_ORDER', context=context)
                if backmove_ids:
                    self.write(cr, uid, backmove_ids, {'backmove_id': move['id']}, context=context)

                pack_backmove_ids = self.search(cr, uid,
                                                [('backmove_packing_id', '=', move_data['id'])],
                                                order='NO_ORDER', context=context)
                if pack_backmove_ids:
                    self.write(cr, uid, pack_backmove_ids, {'backmove_packing_id': move['id']}, context=context)

                #self.write(cr, uid, [move_data['id']], {'state': 'draft'}, context=context)
                self.unlink(cr, uid, move_data['id'], context=context, force=True)

        return res

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        defaults = kwargs.get('defaults')
        assert defaults is not None, 'missing defaults'

        return defaults


    # @@@override stock>stock.py>stock_move>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial pickings and moves done.
        @param partial_datas: Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date, delivery
                          moves with product_id, product_qty, uom
        """

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        complete, too_many, too_few = [], [], []
        move_product_qty = {}
        prodlot_ids = {}
        internal_loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal'), ('cross_docking_location_ok', '=', False)])
        ctx_avg = context.copy()
        ctx_avg['location'] = internal_loc_ids
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s' % (move.id), False)
            assert partial_data, _('Missing partial picking data for move #%s') % (move.id)
            product_qty = partial_data.get('product_qty', 0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom', False)
            product_price = partial_data.get('product_price', 0.0)
            product_currency = partial_data.get('product_currency', False)
            prodlot_ids[move.id] = partial_data.get('prodlot_id')
            if move.product_qty == product_qty:
                complete.append(move)
            elif move.product_qty > product_qty:
                too_few.append(move)
            else:
                too_many.append(move)

            # Average price computation
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average') and not move.location_dest_id.cross_docking_location_ok:
                product = product_obj.browse(cr, uid, move.product_id.id, context=ctx_avg)
                move_currency_id = move.company_id.currency_id.id
                context['currency_id'] = move_currency_id
                qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                if qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                                                     move_currency_id, product_price, round=False, context=context)
                    new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                                       product.uom_id.id)
                    if product.qty_available <= 0:
                        new_std_price = new_price
                    else:
                        # Get the standard price
                        amount_unit = product.price_get('standard_price', context)[product.id]
                        new_std_price = ((amount_unit * product.qty_available)\
                                         + (new_price * qty)) / (product.qty_available + qty)

                    product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price})

                    # Record the values that were chosen in the wizard, so they can be
                    # used for inventory valuation if real-time valuation is enabled.
                    self.write(cr, uid, [move.id],
                               {'price_unit': product_price,
                                'price_currency_id': product_currency,
                                })

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty,
                    'picking_id' : move.picking_id.id,
                    'state': 'assigned',
                    'move_dest_id': False,
                    'price_unit': move.price_unit,
                }
                prodlot_id = prodlot_ids[move.id]
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                # override : call to hook added
                defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
                new_move = self.copy(cr, uid, move.id, defaults)
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, [move.id],
                       {
                'product_qty' : move.product_qty - product_qty,
                'product_uos_qty':move.product_qty - product_qty,
            })


        for move in too_many:
            self.write(cr, uid, [move.id],
                       {
                'product_qty': move.product_qty,
                'product_uos_qty': move.product_qty,
            })
            complete.append(move)

        for move in complete:
            # override : refactoring
            defaults = {}
            prodlot_id = prodlot_ids.get(move.id)
            if prodlot_id:
                defaults.update(prodlot_id=prodlot_id)
            defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
            self.write(cr, uid, [move.id], defaults)
            # override : end
            self.action_done(cr, uid, [move.id], context=context)
            if  move.picking_id.id :
                # TOCHECK : Done picking if all moves are done
                cr.execute("""
                    SELECT move.id FROM stock_picking pick
                    RIGHT JOIN stock_move move ON move.picking_id = pick.id AND move.state = %s
                    WHERE pick.id = %s""",
                           ('done', move.picking_id.id))
                res = cr.fetchall()
                if len(res) == len(move.picking_id.move_lines):
                    picking_obj.action_move(cr, uid, [move.picking_id.id])
                    wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_done', cr)

        return [move.id for move in complete]
    # @@@override end

    def _get_destruction_products(self, cr, uid, ids, product_ids=False, context=None, recursive=False):
        """ Finds the product quantity and price for particular location.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = []
        for move in self.browse(cr, uid, ids, context=context):
            # add this move into the list of result
            sub_total = move.product_qty * move.product_id.standard_price

            currency = ''
            if move.purchase_line_id and move.purchase_line_id.currency_id:
                currency = move.purchase_line_id.currency_id.name
            elif move.sale_line_id and move.sale_line_id.currency_id:
                currency = move.sale_line_id.currency_id.name

            result.append({
                'prod_name': move.product_id.name,
                'prod_code': move.product_id.code,
                'prod_price': move.product_id.standard_price,
                'sub_total': sub_total,
                'currency': currency,
                'origin': move.origin,
                'expired_date': move.expired_date,
                'prodlot_id': move.prodlot_id.name,
                'dg_check': move.product_id and move.product_id.dg_txt or '',
                'np_check': move.product_id and move.product_id.cs_txt or '',
                'uom': move.product_uom.name,
                'prod_qty': move.product_qty,
            })
        return result

    def in_action_confirm(self, cr, uid, ids, context=None):
        """
            Incoming: draft or confirmed: validate and assign
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.action_confirm(cr, uid, ids, context)
        self.action_assign(cr, uid, ids, context)
        return True

    # @@@override stock>stock.py>stock_move>_chain_compute
    def _chain_compute(self, cr, uid, moves, context=None):
        """ Finds whether the location has chained location type or not.
        @param moves: Stock moves
        @return: Dictionary containing destination location with chained location type.
        """
        result = {}
        if context is None:
            context = {}

        moves_by_location = {}
        pick_by_journal = {}

        for m in moves:
            partner_id = m.picking_id and m.picking_id.address_id and m.picking_id.address_id.partner_id or False
            dest = self.pool.get('stock.location').chained_location_get(
                cr,
                uid,
                m.location_dest_id,
                partner_id,
                m.product_id,
                m.product_id.nomen_manda_0,
                context
            )
            if dest and not m.not_chained:
                if dest[1] == 'transparent' and context.get('action_confirm', False):
                    newdate = (datetime.strptime(m.date, '%Y-%m-%d %H:%M:%S') + relativedelta(days=dest[2] or 0)).strftime('%Y-%m-%d')
                    moves_by_location.setdefault(dest[0].id, {}).setdefault(newdate, [])
                    moves_by_location[dest[0].id][newdate].append(m.id)
                    journal_id = dest[3] or (m.picking_id and m.picking_id.stock_journal_id and m.picking_id.stock_journal_id.id) or False
                    pick_by_journal.setdefault(journal_id, set())
                    pick_by_journal[journal_id].add(m.picking_id.id)
                elif not context.get('action_confirm', False):
                    result.setdefault(m.picking_id, [])
                    result[m.picking_id].append((m, dest))

        for journal_id, pick_ids in pick_by_journal.iteritems():
            if journal_id:
                self.pool.get('stock.picking').write(cr, uid, list(pick_ids), {'journal_id': journal_id}, context=context)

        new_moves = []
        for location_id in moves_by_location.keys():
            for newdate, move_ids in moves_by_location[location_id].iteritems():
                self.write(cr, uid, move_ids, {'location_dest_id': location_id,
                                               'date': newdate}, context=context)
                new_moves.extend(move_ids)

        if new_moves:
            new_moves = self.browse(cr, uid, new_moves, context=context)
            res2 = self._chain_compute(cr, uid, new_moves, context=context)
            for pick_id in res2.keys():
                result.setdefault(pick_id, [])
                result[pick_id] += res2[pick_id]

        return result
    # @@@override end

    # @@@override stock>stock.py>stock_move>_create_chained_picking
    def _create_chained_picking(self, cr, uid, pick_name, picking, ptype, move, context=None):
        if context is None:
            context = {}

        res_obj = self.pool.get('res.company')
        picking_obj = self.pool.get('stock.picking')
        data_obj = self.pool.get('ir.model.data')

        context['from_chaining'] = True

        reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]

        pick_values = {
            'name': pick_name,
            'origin': tools.ustr(picking.origin or ''),
            'type': ptype,
            'note': picking.note,
            'move_type': picking.move_type,
            'stock_journal_id': move[0][1][3],
            'company_id': move[0][1][4] or res_obj._company_default_get(cr, uid, 'stock.company', context=context),
            'address_id': picking.address_id.id,
            'invoice_state': 'none',
            'date': picking.date,
            'sale_id': picking.sale_id and picking.sale_id.id or False,
            'auto_picking': picking.type == 'in' and any(m.direct_incoming for m in picking.move_lines),
            'reason_type_id': reason_type_id,
            'previous_chained_pick_id': picking.id,
        }

        return picking_obj.create(cr, uid, pick_values, context=context)
    # @@@override end

stock_move()

#-----------------------------------------
#   Stock location
#-----------------------------------------
class stock_location(osv.osv):
    _name = 'stock.location'
    _inherit = 'stock.location'

    def _product_value(self, cr, uid, ids, field_names, arg, context=None):
        """Computes stock value (real and virtual) for a product, as well as stock qty (real and virtual).
        @param field_names: Name of field
        @return: Dictionary of values
        """
        result = super(stock_location, self)._product_value(cr, uid, ids, field_names, arg, context=context)

        product_product_obj = self.pool.get('product.product')
        currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        currency_obj = self.pool.get('res.currency')
        currency = currency_obj.read(cr, uid, currency_id, ['rounding'], context=context)
        if context.get('product_id'):
            view_ids = self.search(cr, uid, [('usage', '=', 'view')], context=context)
            result.update(dict([(i, {}.fromkeys(field_names, 0.0)) for i in list(set([aaa for aaa in view_ids]))]))
            for loc_id in view_ids:
                c = (context or {}).copy()
                c['location'] = loc_id
                c['compute_child'] = True
                for prod in product_product_obj.read(cr, uid, [context.get('product_id')],
                                                     ['qty_available', 'virtual_available', 'standard_price'], context=c):
                    for f in field_names:
                        if f == 'stock_real':
                            if loc_id not in result:
                                result[loc_id] = {}
                            result[loc_id][f] += prod['qty_available']
                        elif f == 'stock_virtual':
                            result[loc_id][f] += prod['virtual_available']
                        elif f == 'stock_real_value':
                            amount = prod['qty_available'] * prod['standard_price']
                            amount = currency_obj.round(cr, uid, currency['rounding'], amount)
                            result[loc_id][f] += amount
                        elif f == 'stock_virtual_value':
                            amount = prod['virtual_available'] * prod['standard_price']
                            amount = currency_obj.round(cr, uid, currency['rounding'], amount)
                            result[loc_id][f] += amount

        return result

    def _fake_get(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            result[id] = False
        return result

    def _prod_loc_search(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0] or not arg[0][2] or not arg[0][2][0]:
            return []
        if context is None:
            context = {}
        id_nonstock = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        prod_obj = self.pool.get('product.product').read(cr, uid, arg[0][2][0], ['type'])
        if prod_obj and prod_obj['type'] == 'consu':
            if arg[0][2][1] == 'in':
                id_virt = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_locations_virtual')[1]
                ids_child = self.pool.get('stock.location').search(cr, uid,
                                                                   [('location_id', 'child_of', id_virt)],
                                                                   order='NO_ORDER')
                return [('id', 'in', [id_nonstock, id_cross] + ids_child)]
            else:
                return [('id', 'in', [id_cross])]

        elif prod_obj and  prod_obj['type'] != 'consu':
            if arg[0][2][1] == 'in':
                return [('id', 'in', ids_child)]
            else:
                return [('id', 'not in', [id_nonstock]), ('usage', '=', 'internal')]

        return [('id', 'in', [])]

    def _cd_search(self, cr, uid, ids, fields, arg, context=None):
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        if context is None:
            context = {}
        if arg[0][2]:
            obj_pol = arg[0][2][0] and self.pool.get('purchase.order.line').browse(cr, uid, arg[0][2][0]) or False
            if  (obj_pol and obj_pol.order_id.cross_docking_ok) or arg[0][2][1]:
                return [('id', 'in', [id_cross])]
        return []

    def _check_usage(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0][2]:
            return []
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        prod_obj = self.pool.get('product.product').read(cr, uid, arg[0][2], ['type'])
        if prod_obj['type'] == 'service_recep':
            ids = self.pool.get('stock.location').search(cr, uid, [('usage',
                                                                    '=', 'inventory')], order='NO_ORDER')
            return [('id', 'in', ids)]
        elif prod_obj['type'] == 'consu':
            return []
        else:
            ids = self.pool.get('stock.location').search(cr, uid, [('usage',
                                                                    '=', 'internal')], order='NO_ORDER')
            return [('id', 'in', ids)]
        return []

    def _search_filter_partner_ext_cu(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0][2] or not isinstance(arg[0][2], list) or not len(arg[0][2]) == 2:
            return []
        if context is None:
            context = {}

        partner_id2 = arg[0][2][0]
        ext_cu = arg[0][2][1]

        domain = []
        if not partner_id2 and not ext_cu:
            domain = []
        elif partner_id2:
            domain = [('usage', '=', 'supplier')]
        else: # ext_cu
            domain = [('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')]

        return domain

    _columns = {
        'chained_location_type': fields.selection([('none', 'None'), ('customer', 'Customer'), ('fixed', 'Fixed Location'), ('nomenclature', 'Nomenclature')],
                                                  'Chained Location Type', required=True,
                                                  help="Determines whether this location is chained to another location, i.e. any incoming product in this location \n" \
                                                  "should next go to the chained location. The chained location is determined according to the type :"\
                                                  "\n* None: No chaining at all"\
                                                  "\n* Customer: The chained location will be taken from the Customer Location field on the Partner form of the Partner that is specified in the Picking list of the incoming products." \
                                                  "\n* Fixed Location: The chained location is taken from the next field: Chained Location if Fixed." \
                                                  "\n* Nomenclature: The chained location is taken from the options field: Chained Location is according to the nomenclature level of product."\
                                                  ),
        'filter_partner_ext_cu': fields.function(_fake_get, method=True, type='boolean', string='Filter location by partner', fnct_search=_search_filter_partner_ext_cu),
        'chained_options_ids': fields.one2many('stock.location.chained.options', 'location_id', string='Chained options'),
        'optional_loc': fields.boolean(string='Is an optional location ?'),
        'stock_real': fields.function(_product_value, method=True, type='float', string='Real Stock', multi="stock"),
        'stock_virtual': fields.function(_product_value, method=True, type='float', string='Virtual Stock', multi="stock"),
        'stock_real_value': fields.function(_product_value, method=True, type='float', string='Real Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'stock_virtual_value': fields.function(_product_value, method=True, type='float', string='Virtual Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'check_prod_loc': fields.function(_fake_get, method=True, type='many2one', relation='stock.location', string='zz', fnct_search=_prod_loc_search),
        'check_cd': fields.function(_fake_get, method=True, type='many2one', relation='stock.location', string='zz', fnct_search=_cd_search),
        'check_usage': fields.function(_fake_get, method=True, type='many2one', relation='stock.location', string='zz', fnct_search=_check_usage),
        'virtual_location': fields.boolean(string='Virtual location'),

    }

    # @@@override stock>stock.py>stock_move>chained_location_get
    def chained_location_get(self, cr, uid, location, partner=None, product=None, nomenclature=None, context=None):
        """ Finds chained location
        @param location: Location id
        @param partner: Partner id
        @param product: Product id
        @param nomen: Nomenclature of the product
        @return: List of values
        """
        result = None
        if location.chained_location_type == 'customer':
            if partner:
                result = partner.property_stock_customer
        elif location.chained_location_type == 'fixed':
            result = location.chained_location_id
        elif location.chained_location_type == 'nomenclature':
            nomen_id = nomenclature and nomenclature.id or (product and product.nomen_manda_0.id)
            for opt in location.chained_options_ids:
                if opt.nomen_id.id == nomen_id:
                    result = opt.dest_location_id
        if result:
            return result, location.chained_auto_packing, location.chained_delay, location.chained_journal_id and location.chained_journal_id.id or False, location.chained_company_id and location.chained_company_id.id or False, location.chained_picking_type
        return result
    # @@@override end

    def on_change_location_type(self, cr, uid, ids, chained_location_type, context=None):
        '''
        If the location type is changed to 'Nomenclature', set some other fields values
        '''
        if chained_location_type and chained_location_type == 'nomenclature':
            return {'value': {'chained_auto_packing': 'transparent',
                              'chained_picking_type': 'internal',
                              'chained_delay': 0}}

        return {}


stock_location()


class stock_location_chained_options(osv.osv):
    _name = 'stock.location.chained.options'
    _rec_name = 'location_id'

    _columns = {
        'dest_location_id': fields.many2one('stock.location', string='Destination Location', required=True),
        'nomen_id': fields.many2one('product.nomenclature', string='Nomenclature Level', required=True),
        'location_id': fields.many2one('stock.location', string='Location', required=True),
    }


stock_location_chained_options()


class stock_move_cancel_wizard(osv.osv_memory):
    _name = 'stock.move.cancel.wizard'

    def _check_from_cross_docking(self, cr, uid, ids, field_name, args, context=None):
        """
        Is the move from the Cross docking Location ?
        """
        if context is None:
            context = {}
        res = {}

        data_obj = self.pool.get('ir.model.data')
        cross_docking_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        for wiz_move in self.browse(cr, uid, ids, context=context):
            if wiz_move.move_id.location_id.id == cross_docking_id:
                res[wiz_move.id] = True

        return res

    _columns = {
        'move_id': fields.many2one('stock.move', string='Move', required=True),
        'cancel_only': fields.boolean('Just allow cancel only', invisible=True),
        'is_move_from_cross_docking': fields.function(_check_from_cross_docking, method=True, type='boolean',
                                                      string='Is the move from the Cross docking Location ?',
                                                      store=False, readonly=True),
    }

    _defaults = {
        'move_id': lambda self, cr, uid, c: c.get('active_id'),
        'cancel_only': False,
        'is_move_from_cross_docking': False,
    }

    def ask_cancel(self, cr, uid, ids, context=None, *args, **kw):
        if context is None:
            context = {}

        move_id = self.pool.get('stock.move.cancel.wizard').read(cr, uid, ids[0], ['move_id'], context=context)['move_id']
        wiz_id = self.pool.get('stock.move.cancel.more.wizard').create(cr, uid, {'move_id': move_id}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.move.cancel.more.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': wiz_id,
                'context': context}

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just call the cancel of stock.move (re-sourcing flag not set)
        '''
        # Objects
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')

        wf_service = netsvc.LocalService("workflow")
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            move_id = wiz.move_id.id
            picking_id = wiz.move_id.picking_id.id
            move_obj.action_cancel(cr, uid, [wiz.move_id.id], context=context)
            move_ids = move_obj.search(cr, uid, [('id', '=', wiz.move_id.id)],
                                       limit=1, order='NO_ORDER', context=context)
            if move_ids and  wiz.move_id.has_to_be_resourced:
                self.infolog(cr, uid, "The stock.move id:%s of the picking id:%s (%s) has been canceled and resourced" % (
                    move_id,
                    picking_id,
                    pick_obj.read(cr, uid, picking_id, ['name'], context=context)['name'],
                ))
            else:
                self.infolog(cr, uid, "The stock.move id:%s of the picking id:%s (%s) has been canceled" % (
                    move_id,
                    picking_id,
                    pick_obj.read(cr, uid, picking_id, ['name'], context=context)['name'],
                ))

            if move_ids and wiz.move_id.picking_id:
                lines = wiz.move_id.picking_id.move_lines
                if all(l.state == 'cancel' for l in lines):
                    wf_service.trg_validate(uid, 'stock.picking', wiz.move_id.picking_id.id, 'button_cancel', cr)

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Call the cancel and resource method of the stock move
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Objects
        move_obj = self.pool.get('stock.move')

        move_ids = [x['move_id'] for x in self.read(cr, uid, ids, ['move_id'], context=context)]
        move_obj.write(cr, uid, move_ids, {'has_to_be_resourced': True}, context=context)

        return self.just_cancel(cr, uid, ids, context=context)


stock_move_cancel_wizard()


class stock_move_cancel_more_wizard(osv.osv_memory):
    _name = 'stock.move.cancel.more.wizard'

    _columns = {
        'move_id': fields.many2one('stock.move', string='Move', required=True),
    }

    _defaults = {
        'move_id': lambda self, cr, uid, c: c.get('active_id'),
    }

    def no_cancel(self, uid, ids, context=None, *args, **kw):
        return {'type': 'ir.actions.act_window_close'}

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just call the cancel of stock.move (re-sourcing flag not set)
        '''
        # Objects
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')

        wf_service = netsvc.LocalService("workflow")
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            move_id = wiz.move_id.id
            picking_id = wiz.move_id.picking_id.id
            move_obj.action_cancel(cr, uid, [wiz.move_id.id], context=context)
            move_ids = move_obj.search(cr, uid, [('id', '=', wiz.move_id.id)],
                                       limit=1, order='NO_ORDER', context=context)
            if move_ids and  wiz.move_id.has_to_be_resourced:
                self.infolog(cr, uid, "The stock.move id:%s of the picking id:%s (%s) has been canceled and resourced" % (
                    move_id,
                    picking_id,
                    pick_obj.read(cr, uid, picking_id, ['name'], context=context)['name'],
                ))
            else:
                self.infolog(cr, uid, "The stock.move id:%s of the picking id:%s (%s) has been canceled" % (
                    move_id,
                    picking_id,
                    pick_obj.read(cr, uid, picking_id, ['name'], context=context)['name'],
                ))

            if move_ids and wiz.move_id.picking_id:
                lines = wiz.move_id.picking_id.move_lines
                if all(l.state == 'cancel' for l in lines):
                    wf_service.trg_validate(uid, 'stock.picking', wiz.move_id.picking_id.id, 'button_cancel', cr)

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_create_int(self, cr, uid, ids, context=None):
        """
        Create/Update INT with stock in Cross Docking while cancelling Picking
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        self.pool.get('data.tools').load_common_data(cr, uid, ids, context=context)
        stock_loc = loc_obj.browse(cr, uid, context['common']['stock_id'], fields_to_fetch=['chained_options_ids'],
                                   context=context)
        cross_docking_id = context['common']['cross_docking']
        int_reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]
        int_id = False

        for wiz_move in self.browse(cr, uid, ids, context=context):
            # Create/Update and validate INT for lines from Cross docking
            move = wiz_move.move_id
            if move.product_qty > 0:
                pick_ids = [move.picking_id.id]
                if move.picking_id.backorder_id:
                    pick_ids.append(move.picking_id.backorder_id.id)
                int_ids = pick_obj.search(cr, uid, [('type', '=', 'internal'), ('subtype', '=', 'standard'),
                                                    ('from_pick_cancel_id', 'in', pick_ids), ('state', 'not in', ['done', 'cancel'])],
                                          limit=1, context=context)
                if not int_ids:  # Create the INT
                    int_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal')
                    int_data = {
                        'name': int_name,
                        'type': 'internal',
                        'subtype': 'standard',
                        'min_date': datetime.today(),
                        'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                        'partner_id2': move.picking_id.partner_id2 and move.picking_id.partner_id2.id or False,
                        'order_category': move.picking_id.order_category,
                        'origin': move.picking_id.backorder_id and move.picking_id.backorder_id.name or move.picking_id.name,
                        'address_id': move.picking_id.address_id and move.picking_id.address_id.id or False,
                        'invoice_state': 'none',
                        'reason_type_id': int_reason_type_id,
                        'from_pick_cancel_id': move.picking_id.backorder_id and move.picking_id.backorder_id.id or move.picking_id.id,
                    }
                    int_id = pick_obj.create(cr, uid, int_data, context=context)
                    int_id = int(int_id)
                    self.infolog(cr, uid, _('The Internal Move id:%s (%s) has been created.') % (int_id, int_name))
                else:
                    int_id = int(int_ids[0])
                    int_name = pick_obj.read(cr, uid, int_id, ['name'], context=context)['name']
                # Add the move
                if move.state != 'cancel' and move.location_id.id == cross_docking_id:
                    dest_loc_id = stock_loc.id
                    for opt in stock_loc.chained_options_ids:
                        if opt.nomen_id.id == move.product_id.nomen_manda_0.id:
                            dest_loc_id = opt.dest_location_id.id
                    m_data = {
                        'name': move.name,
                        'picking_id': int_id,
                        'product_id': move.product_id.id,
                        'product_qty': move.product_qty,
                        'product_uom': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': dest_loc_id,
                        'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
                        'expired_date': move.expired_date or False,
                        'reason_type_id': int_reason_type_id,
                    }
                    move_obj.create(cr, uid, m_data, context=context)

                pick_obj.draft_force_assign(cr, uid, [int_id], context=context)
                self.infolog(cr, uid, _('The Internal Move id:%s (%s) has been updated.') % (int_id, int_name))
                # Cancel Move
                move_obj.action_cancel(cr, uid, [move.id], context=context)
                self.infolog(cr, uid, _('The stock.move id:%s of the picking id:%s (%s) has been cancelled') % (
                    move.id, move.picking_id.id, pick_obj.read(cr, uid, move.picking_id.id, ['name'], context=context)['name'],
                ))
                if all(l.state == 'cancel' for l in move.picking_id.move_lines):
                    wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_cancel', cr)

        # Change INT to available
        if int_id:
            pick_obj.action_assign(cr, uid, [int_id], context=context)

        return {'type': 'ir.actions.act_window_close'}


stock_move_cancel_more_wizard()


class stock_picking_cancel_wizard(osv.osv_memory):
    _name = 'stock.picking.cancel.wizard'

    def _get_allow_cr(self, cr, uid, context=None):
        """
        Define if the C&R are allowed on the wizard
        """
        if context is None:
            context = {}

        picking_id = context.get('active_id')
        for move in self.pool.get('stock.picking').browse(cr, uid, picking_id, context=context).move_lines:
            if move.sale_line_id and move.sale_line_id.type == 'make_to_order':
                return False

        return True

    def _check_from_cross_docking(self, cr, uid, context=None):
        """
        Is one of the moves from the Cross docking Location ?
        """
        if context is None:
            context = {}

        data_obj = self.pool.get('ir.model.data')
        cross_docking_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        picking_id = context.get('active_id')
        for move in self.pool.get('stock.picking').browse(cr, uid, picking_id, context=context).move_lines:
            if move.location_id.id == cross_docking_id:
                return True

        return False

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Picking', required=True),
        'allow_cr': fields.boolean(string='Allow Cancel and resource'),
        'has_moves_from_cross_docking': fields.boolean(string='Is one of the moves from the Cross docking Location ?'),
    }

    _defaults = {
        'picking_id': lambda self, cr, uid, c: c.get('active_id'),
        'allow_cr': _get_allow_cr,
        'has_moves_from_cross_docking': _check_from_cross_docking,
    }

    def ask_cancel(self, cr, uid, ids, context=None, *args, **kw):
        if context is None:
            context = {}

        picking_id = self.pool.get('stock.picking.cancel.wizard').read(cr, uid, ids[0], ['picking_id'], context=context)['picking_id']
        wiz_id = self.pool.get('stock.picking.cancel.more.wizard').create(cr, uid, {'picking_id': picking_id}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking.cancel.more.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': wiz_id,
                'context': context}

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just call the cancel of the stock.picking
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        msg_type = {
            'in': 'Incoming Shipment',
            'internal': 'Internal Picking',
            'out': {
                'standard': 'Delivery Order',
                'picking': 'Picking Ticket',
            }
        }

        wf_service = netsvc.LocalService("workflow")
        for wiz in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'stock.picking', wiz.picking_id.id, 'button_cancel', cr)
            self.infolog(cr, uid, "The %s id:%s (%s) has been canceled%s." % (
                wiz.picking_id.type == 'out' and msg_type.get('out', {}).get(wiz.picking_id.subtype, '') or msg_type.get(wiz.picking_id.type),
                wiz.picking_id.id,
                wiz.picking_id.name,
                wiz.picking_id.has_to_be_resourced and ' and resourced' or '',
            ))

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Call the cancel and resource method of the picking
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects declarations
        pick_obj = self.pool.get('stock.picking')

        # variables declarations
        pick_ids = []

        for wiz in self.read(cr, uid, ids, ['picking_id'], context=context):
            pick_ids.append(wiz['picking_id'])

        # Set the boolean 'has_to_be_resourced' to True for each picking
        vals = {'has_to_be_resourced': True}
        pick_obj.write(cr, uid, pick_ids, vals, context=context)

        return self.just_cancel(cr, uid, ids, context=context)


stock_picking_cancel_wizard()


class stock_picking_cancel_more_wizard(osv.osv_memory):
    _name = 'stock.picking.cancel.more.wizard'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Picking', required=True),
    }

    _defaults = {
        'picking_id': lambda self, cr, uid, c: c.get('active_id'),
    }

    def no_cancel(self, uid, ids, context=None, *args, **kw):
        return {'type': 'ir.actions.act_window_close'}

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just call the cancel of the stock.picking
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        msg_type = {
            'in': 'Incoming Shipment',
            'internal': 'Internal Picking',
            'out': {
                'standard': 'Delivery Order',
                'picking': 'Picking Ticket',
            }
        }

        wf_service = netsvc.LocalService("workflow")
        for wiz in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'stock.picking', wiz.picking_id.id, 'button_cancel', cr)
            self.infolog(cr, uid, "The %s id:%s (%s) has been canceled." % (
                wiz.picking_id.type == 'out' and msg_type.get('out', {}).get(wiz.picking_id.subtype, '') or msg_type.get(wiz.picking_id.type),
                wiz.picking_id.id,
                wiz.picking_id.name,
            ))

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_create_int(self, cr, uid, ids, context=None):
        """
        Create/Update INT with stock in Cross Docking while cancelling Picking
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]
        msg_type = {
            'in': 'Incoming Shipment',
            'internal': 'Internal Picking',
            'out': {
                'standard': 'Delivery Order',
                'picking': 'Picking Ticket',
            }
        }

        wf_service = netsvc.LocalService("workflow")
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        self.pool.get('data.tools').load_common_data(cr, uid, ids, context=context)
        stock_loc = loc_obj.browse(cr, uid, context['common']['stock_id'], fields_to_fetch=['chained_options_ids'],
                                   context=context)
        cross_docking_id = context['common']['cross_docking']
        int_reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]

        for wiz in self.browse(cr, uid, ids, context=context):
            # Create/Update and validate INT for lines from Cross docking
            pick_ids = [wiz.picking_id.id]
            if wiz.picking_id.backorder_id:
                pick_ids.append(wiz.picking_id.backorder_id.id)
            int_ids = pick_obj.search(cr, uid, [('type', '=', 'internal'), ('subtype', '=', 'standard'),
                                                ('from_pick_cancel_id', 'in', pick_ids), ('state', 'not in', ['done', 'cancel'])],
                                      limit=1, context=context)
            if not int_ids:  # Create the INT
                int_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal')
                int_data = {
                    'name': int_name,
                    'type': 'internal',
                    'subtype': 'standard',
                    'min_date': datetime.today(),
                    'partner_id': wiz.picking_id.partner_id and wiz.picking_id.partner_id.id or False,
                    'partner_id2': wiz.picking_id.partner_id2 and wiz.picking_id.partner_id2.id or False,
                    'order_category': wiz.picking_id.order_category,
                    'origin': wiz.picking_id.backorder_id and wiz.picking_id.backorder_id.name or wiz.picking_id.name,
                    'address_id': wiz.picking_id.address_id and wiz.picking_id.address_id.id or False,
                    'invoice_state': 'none',
                    'reason_type_id': int_reason_type_id,
                    'from_pick_cancel_id': wiz.picking_id.backorder_id and wiz.picking_id.backorder_id.id or wiz.picking_id.id,
                }
                int_id = pick_obj.create(cr, uid, int_data, context=context)
                self.infolog(cr, uid, _('The Internal Move id:%s (%s) has been created.') % (int_id, int_name))
            else:
                int_id = int_ids[0]
                int_name = pick_obj.read(cr, uid, int_id, ['name'], context=context)['name']
            # Add the moves
            moves_ids_to_cancel = []
            for m in (move for move in wiz.picking_id.move_lines
                      if (move.state != 'cancel' and move.location_id.id == cross_docking_id and move.product_qty > 0)):
                dest_loc_id = stock_loc.id
                for opt in stock_loc.chained_options_ids:
                    if opt.nomen_id.id == m.product_id.nomen_manda_0.id:
                        dest_loc_id = opt.dest_location_id.id
                m_data = {
                    'name': m.name,
                    'picking_id': int_id,
                    'product_id': m.product_id.id,
                    'product_qty': m.product_qty,
                    'product_uom': m.product_uom.id,
                    'location_id': m.location_id.id,
                    'location_dest_id': dest_loc_id,
                    'prodlot_id': m.prodlot_id and m.prodlot_id.id or False,
                    'expired_date': m.expired_date or False,
                    'reason_type_id': int_reason_type_id,
                }
                move_obj.create(cr, uid, m_data, context=context)
                moves_ids_to_cancel.append(m.id)

            # Cancel Moves
            move_obj.action_cancel(cr, uid, moves_ids_to_cancel, context=context)
            if all(l.state == 'cancel' for l in wiz.picking_id.move_lines):
                # Cancel Picking
                wf_service.trg_validate(uid, 'stock.picking', wiz.picking_id.id, 'button_cancel', cr)
                self.infolog(cr, uid, _('The %s id:%s (%s) has been cancelled.') % (
                    wiz.picking_id.type == 'out' and msg_type.get('out', {}).get(wiz.picking_id.subtype, '') or msg_type.get(wiz.picking_id.type),
                    wiz.picking_id.id, wiz.picking_id.name,
                ))

            # Change INT to available
            pick_obj.draft_force_assign(cr, uid, [int_id], context=context)
            pick_obj.action_assign(cr, uid, [int_id], context=context)
            self.infolog(cr, uid, _('The Internal Move id:%s (%s) has been updated.') % (int_id, int_name))

        return {'type': 'ir.actions.act_window_close'}


stock_picking_cancel_more_wizard()
