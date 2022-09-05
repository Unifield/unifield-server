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

import logging
from os import path

from osv import osv, fields
import tools
from tools.translate import _


class stock_reason_type(osv.osv):
    _name = 'stock.reason.type'
    _description = 'Reason Types Moves'

    def init(self, cr):
        """
        Load reason_type_data.xml brefore product
        """
        if hasattr(super(stock_reason_type, self), 'init'):
            super(stock_reason_type, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'reason_types_moves')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module reason_types_moves: loading reason_type_data.xml')
            pathname = path.join('reason_types_moves', 'reason_type_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'reason_types_moves', file, {}, mode='init', noupdate=False)

    def return_level(self, cr, uid, type, level=0):
        if type.parent_id:
            level += 1
            self.return_level(cr, uid, type.parent_id, level)

        return level

    def _get_level(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the level of the reason type
        '''
        res = {}

        for type in self.browse(cr, uid, ids, context=context):
            res[type.id] = self.return_level(cr, uid, type)

        return res

    def _get_inventory(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns if the type will be present in inventory line
        '''
        res = {}

        for type in self.browse(cr, uid, ids, context=context):
            tmp_type = type
            while tmp_type.parent_id:
                tmp_type = tmp_type.parent_id
            res[type.id] = tmp_type.inventory_ok

        return res

    def _search_inventory(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the ids of all reason type which are displayed in inventory line
        '''
        res = []

        for arg in args:
            if arg[0] == 'is_inventory' and arg[1] == '=' and arg[2] in (True, 1, 'True', 'true', '1'):
                inv_ids = self.search(cr, uid, [('inventory_ok', '=', True)], context=context)
                res_ids = inv_ids
                while inv_ids:
                    inv_ids = self.search(cr, uid, [('parent_id', 'in', inv_ids)], context=context)
                    res_ids.extend(inv_ids)
                res = [('id', 'in', res_ids)]

        return res


    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            name = record.name
            code = record.code
            if record.parent_id:
                name = record.parent_id.name + ' / ' + name
                code = str(record.parent_id.code) + '.' + str(code)
            res.append((record.id, '%s %s' % (code, name)))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _search_is_fs(self, cr, uid, obj, name, args, context=None):
        for arg in args:
            if arg[0] == 'is_fs' and arg[1] == '=' and arg[2] in (True, 1, 'True', 'true', '1'):
                return [('code', 'in', [6, 20])]
        return []

    _columns = {
        'name': fields.char(size=128, string='Name', required=True, translate=1),
        'code': fields.integer(string='Code', required=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'parent_id': fields.many2one('stock.reason.type', string='Parent reason'),
        'level': fields.function(_get_level, method=True, type='integer', string='Level', readonly=True),
        'inventory_ok': fields.boolean(string='Inventory type', help='If checked, this reason type will be available in inventory line'),
        'is_inventory': fields.function(_get_inventory, fnct_search=_search_inventory,
                                        method=True, type='boolean', string='Inventory type',
                                        readonly=True, help='If checked, this reason type will be available in inventory line'),
        'incoming_ok': fields.boolean(string='Available for incoming shipment ?'),
        'internal_ok': fields.boolean(string='Available for internal picking ?'),
        'outgoing_ok': fields.boolean(string='Available for outgoing movements ?'),
        'pi_discrepancy_type': fields.boolean(string="Is an Adjustment Type in the Physical Inventory's Discrepany lines"),
        'is_fs': fields.function(tools.misc.get_fake, type='boolean', string='For FS out', method=True, fnct_search=_search_is_fs),
    }

    def unlink(self, cr, uid, ids, context=None):
        '''
        Prevent the deletion of standard reason types
        '''
        data_ids = self.pool.get('ir.model.data').search(cr, uid, [('model', '=', 'stock.reason.type'), ('res_id', 'in', ids)])
        if data_ids:
            raise osv.except_osv(_('Error'), _('You cannot delete a standard reason type move'))

        return super(stock_reason_type, self).unlink(cr, uid, ids, context=context)


stock_reason_type()

class stock_inventory_line(osv.osv):
    _name = 'stock.inventory.line'
    _inherit = 'stock.inventory.line'

    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Adjustment type', required=True),
        'comment': fields.text('Comment', readonly=True),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        return super(stock_inventory_line, self).create(cr, uid, vals, context)

stock_inventory_line()

class stock_inventory(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    # @@@override@ stock.stock_inventory._inventory_line_hook()
    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return:
        """
        # Copy the comment
        if inventory_line:
            move_vals.update({
                'comment': inventory_line.comment,
                'reason_type_id': inventory_line.reason_type_id.id,
            })
        move_vals.update({'not_chained': True})

        return super(stock_inventory, self)._inventory_line_hook(cr, uid, inventory_line, move_vals)
        # @@@end

stock_inventory()


class stock_fill_inventory(osv.osv_memory):
    _name = 'stock.fill.inventory'
    _inherit = 'stock.fill.inventory'

    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True, domain=[('is_inventory', '=', True)]),
    }

    def _hook_fill_datas(self, cr, uid, *args, **kwargs):
        '''
        Hook to add data values in fill inventory line data
        '''
        res = super(stock_fill_inventory, self)._hook_fill_datas(cr, uid, *args, **kwargs)
        if kwargs.get('fill_inventory'):
            res.update({'reason_type_id': kwargs['fill_inventory'].reason_type_id.id})

        return res

stock_fill_inventory()



class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    def _get_default_reason(self, cr, uid, context=None):
        res = {}
        toget = [('reason_type_id', 'reason_type_external_supply')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', xml_id)
            res[field] = nom[1]
        return res

    def onchange_move(self, cr, uid, ids, context=None):
        res = {}
        if ids:
            for pick in self.browse(cr, uid, ids, context=context):
                res.update({'reason_type_id': pick.reason_type_id.id})
                min_date = self.get_min_max_date(cr, uid, [pick.id], 'min_date', {}, context=context)[pick.id]['min_date']
                if min_date:
                    res.update({'min_date': min_date, 'manual_min_date_stock_picking': min_date, 'min_date_manually': False})

        return {'value': res}

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Take into account all stock_picking with reason_type_id is a children
        '''

        new_args = []

        for arg in args:
            if arg[0] == 'reason_type_id' and arg[1] in ('=', 'in'):
                new_arg = (arg[0], 'child_of', arg[2])
            else:
                new_arg = arg
            new_args.append(new_arg)

        return super(stock_picking, self).search(cr, uid, new_args,
                                                 offset=offset, limit=limit, order=order,
                                                 context=context, count=False)

    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        return super(stock_picking, self).create(cr, uid, vals, context)

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Set the reason type according to the picking type
        '''
        if not context:
            context = {}

        data_obj = self.pool.get('ir.model.data')
        res = super(stock_picking, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        deli_partner_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        if 'picking_type' in context:
            if context.get('picking_type') == 'incoming_shipment':
                res['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
            elif context.get('picking_type') == 'internal_move':
                res['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]
            elif context.get('picking_type') == 'delivery_order':
                if from_web:
                    res['reason_type_id'] = deli_partner_rt_id
                else:
                    res['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_unit')[1]
            elif context.get('picking_type') == 'picking_ticket':
                res['reason_type_id'] = deli_partner_rt_id

        return res

    def _check_reason_type(self, cr, uid, ids, context=None):
        """
        Do not permit user to create/write an OUT from scratch with some reason types:
         - GOODS RETURN UNIT
         - GOODS REPLACEMENT
         - OTHER
        """
        data_obj = self.pool.get('ir.model.data')
        res = True
        try:
            rt_replacement_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_replacement')[1]
        except ValueError:
            rt_replacement_id = 0
        try:
            rt_return_unit_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]
        except ValueError:
            rt_return_unit_id = 0
        try:
            rt_other_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
        except ValueError:
            rt_other_id = 0

        for sp in self.read(cr, uid, ids, ['purchase_id', 'sale_id', 'type', 'reason_type_id'], context=context):
            if not sp['purchase_id'] and not sp['sale_id'] and sp['type'] == 'out' and sp['reason_type_id']:
                if sp['reason_type_id'][0] in [rt_replacement_id, rt_return_unit_id, rt_other_id]:
                    return False
        return res

    def _get_type_donation_ids(self, cr, uid, context=None):
        data_obj = self.pool.get('ir.model.data')
        type_ids = []
        type_ids.append(data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1])
        type_ids.append(data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1])
        type_ids.append(data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_in_kind_donation')[1])
        return type_ids

    def _get_is_donation(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for rid in ids:
            res[rid] = False
        don_ids = self._get_type_donation_ids(cr, uid)
        for x in self.search(cr, uid, [('id', 'in', ids), ('reason_type_id', 'in', don_ids)], context=context):
            res[x] = True

        return res

    def _search_is_donation(self, cr, uid, obj, name, args, context=None):
        don_ids = self._get_type_donation_ids(cr, uid)
        if not args:
            return []
        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Error'), _('Filter not implemented on field %') % (name, ))

        return [('reason_type_id', 'in', don_ids)]


    def _get_is_loan(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for rid in ids:
            res[rid] = False
        data_obj = self.pool.get('ir.model.data')
        loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        res = self.search(cr, uid, [('id', 'in', ids), ('reason_type_id', 'in', loan_id)], context=context)

        return res

    def _search_is_loan(self, cr, uid, obj, name, args, context=None):
        data_obj = self.pool.get('ir.model.data')
        loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        if not args:
            return []
        if args[0][1] != '=' or not args[0][2]:

            raise osv.except_osv(_('Error'), _('Filter not implemented on field %') % (name,))

        return [('reason_type_id', '=', loan_id)]

    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
        'is_donation': fields.function(_get_is_donation, string='Is Donation ?', method=True, type='boolean', fnct_search=_search_is_donation),
        'is_loan': fields.function(_get_is_loan, string='Is Loan ?', method=True, type='boolean', fnct_search=_search_is_loan),
    }

    def on_change_reason_type_id(self, cr, uid, ids, reason_type_id, context=None):
        if context is None:
            context = {}

        return_reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves',
                                                                                    'reason_type_return_from_unit')[1]

        if reason_type_id == return_reason_type_id:
            return {'value': {'ret_from_unit_rt': True, 'partner_id': False, 'partner_id2': False, 'address_id': False}}
        else:
            return {'value': {'ret_from_unit_rt': False}}

    _constraints = [
        (_check_reason_type, "Wrong reason type for an OUT created from scratch.", ['reason_type_id', ]),
    ]


stock_picking()


class stock_location(osv.osv):
    _name = 'stock.location'
    _inherit = 'stock.location'

    def _get_st_out(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = False
        return res

    def _src_st_out(self, cr, uid, obj, name, args, context=None):
        '''
        Returns location allowed for Standard out
        '''
        res = [('usage', '!=', 'view')]
        loc_obj = self.pool.get('stock.location')
        for arg in args:
            if arg[0] == 'standard_out_ok':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error !'), _('Bad operator !'))
                if arg[2] == 'dest':
                    customer_loc_ids = loc_obj.search(cr, uid, [('usage', '=', 'customer')], context=context)
                    output_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]

                    loc_ids = []
                    loc_ids.extend(customer_loc_ids)
                    loc_ids.append(output_loc_id)
                    res.append(('id', 'in', loc_ids))
                elif arg[2] == 'src':
                    warehouse_ids = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)
                    output_loc_ids = []
                    input_loc_ids = []
                    output_ids = []
                    input_ids = []
                    for w in self.pool.get('stock.warehouse').browse(cr, uid, warehouse_ids, context=context):
                        output_ids.append(w.lot_output_id.id)
                        input_ids.append(w.lot_input_id.id)

                    for loc_id in output_ids:
                        output_loc_ids.extend(self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', loc_id)], context=context))
                    for loc_id in input_ids:
                        input_loc_ids.extend(self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', loc_id)], context=context))

                    res.append(('quarantine_location', '=', False))
                    res.append(('usage', '=', 'internal'))
                    res.append(('cross_docking_location_ok', '=', False))
                    res.append(('id', 'not in', output_loc_ids))
                    res.append(('id', 'not in', input_loc_ids))

        return res

    _columns = {
        'standard_out_ok': fields.function(_get_st_out, fnct_search=_src_st_out, method=True, type='boolean', string='St. Out', store=False),
    }

stock_location()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
