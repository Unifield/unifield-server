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

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp


from msf_outgoing import INTEGRITY_STATUS_SELECTION


class kit_selection(osv.osv_memory):
    '''
    kit selection
    '''
    _name = "kit.selection"

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        sol_obj = self.pool.get('sale.order.line')
        pol_obj = self.pool.get('purchase.order.line')

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # corresponding_so_line_id_kit_selection
            sol_ids = False
            if obj.order_line_id_kit_selection:
                sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [obj.order_line_id_kit_selection.id], context=context)
                assert len(sol_ids) <= 1, 'kit selection purchase line: the number of corresponding sale order line is greater than 1: %s'%len(sol_ids)
            # true if we get some sale order lines
            result[obj.id].update({'corresponding_so_line_id_kit_selection': sol_ids and sol_ids[0] or False})
            # corresponding_so_id_kit_selection
            so_id = False
            if sol_ids:
                datas = sol_obj.read(cr, uid, sol_ids, ['order_id'], context=context)
                for data in datas:
                    if data['order_id']:
                        so_id = data['order_id'][0]
            # write the value
            result[obj.id].update({'corresponding_so_id_kit_selection': so_id})
        return result

    _columns = {'product_id': fields.many2one('product.product', string='Kit Product', readonly=True),
                'kit_id': fields.many2one('composition.kit', string='Theoretical Kit'),
                'order_line_id_kit_selection': fields.many2one('purchase.order.line', string='Purchase Order Line', readonly=True, required=True),
                'impact_so_kit_selection': fields.boolean('Impact Field Order', help='Impact corresponding Field Order by creating a corresponding Field Order line.'),
                # one2many
                'product_ids_kit_selection': fields.one2many('kit.selection.line', 'wizard_id_kit_selection_line', string='Replacement Products'),
                # related fields
                'partner_id_kit_selection': fields.related('order_line_id_kit_selection', 'order_id', 'partner_id', string='Partner', type='many2one', relation='res.partner', readonly=True),
                'pricelist_id_kit_selection': fields.related('order_line_id_kit_selection', 'order_id', 'pricelist_id', string='Currency', type='many2one', relation='product.pricelist', readonly=True),
                'warehouse_id_kit_selection': fields.related('order_line_id_kit_selection', 'order_id', 'warehouse_id', string='Warehouse', type='many2one', relation='stock.warehouse', readonly=True),
                # function fields
                'corresponding_so_line_id_kit_selection': fields.function(_vals_get, method=True, type='many2one', relation='sale.order.line', string='Corresponding Fo Line', multi='get_vals_kit_selection', store=False, readonly=True),
                'corresponding_so_id_kit_selection': fields.function(_vals_get, method=True, type='many2one', relation='sale.order', string='Corresponding Fo', multi='get_vals_kit_selection', store=False, readonly=True),
                }

    _defaults = {'product_id': lambda s, cr, uid, c: c.get('product_id', False),
                 'order_line_id_kit_selection': lambda s, cr, uid, c: c.get('active_ids') and c.get('active_ids')[0] or False,
                 'impact_so_kit_selection': True,
                 }

    def import_items(self, cr, uid, ids, context=None):
        '''
        import lines into product_ids_kit_selection
        '''
        # objects
        line_obj = self.pool.get('kit.selection.line')
        # purchase order line id
        pol_ids = context['active_ids']

        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.kit_id:
                raise osv.except_osv(_('Warning !'), _('A theoretical version should be selected.'))
            if obj.kit_id.state != 'completed':
                raise osv.except_osv(_('Warning !'), _('The theoretical version must be completed.'))
            for item in obj.kit_id.composition_item_ids:
                values = {'order_line_id_kit_selection_line': obj.order_line_id_kit_selection.id,
                          'wizard_id_kit_selection_line': obj.id,
                          'product_id_kit_selection_line': item.item_product_id.id,
                          'qty_kit_selection_line': item.item_qty,
                          'uom_id_kit_selection_line': item.item_uom_id.id,
                          }
                line_obj.create(cr, uid, values, context=dict(context, pol_ids=context['active_ids']))
        return self.pool.get('wizard').open_wizard(cr, uid, pol_ids, w_type='update', context=context)

    def validate_lines(self, cr, uid, ids, context=None):
        '''
        validate the lines

        - qty > 0.0 (must_be_greater_than_0)
        - unit price > 0.0

        return True or False
        '''
        # objects
        # errors
        errors = {'must_be_greater_than_0': False,
                  'price_must_be_greater_than_0': False,
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.product_ids_kit_selection:
                # reset the integrity status
                item.write({'integrity_status': 'empty'}, context=context)
                # qty
                if item.qty_kit_selection_line <= 0.0:
                    # qty is needed
                    errors.update(must_be_greater_than_0=True)
                    item.write({'integrity_status': 'must_be_greater_than_0'}, context=context)
                # unit price
                if item.price_unit_kit_selection_line <= 0.0:
                    # unit price is needed
                    errors.update(price_must_be_greater_than_0=True)
                    item.write({'integrity_status': 'price_must_be_greater_than_0'}, context=context)
        # check the encountered errors
        return all([not x for x in errors.values()])

    def do_de_kitting(self, cr, uid, ids, context=None):
        '''
        create a purchase order line for each kit item and delete the selected kit purchase order line
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        pol_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')
        # id of corresponding purchase order line
        pol_ids = context['active_ids']
        pol_id = context['active_ids'][0]
        pol = pol_obj.browse(cr, uid, pol_id, context=context)
        # integrity constraint
        integrity_check = self.validate_lines(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, pol_ids, w_type='update', context=context)
        # process
        ctx_keep_info = context.copy()
        ctx_keep_info['keepDateAndDistrib'] = True
        for obj in self.browse(cr, uid, ids, context=context):
            if not len(obj.product_ids_kit_selection):
                raise osv.except_osv(_('Warning !'), _('Replacement Items must be selected.'))
            # to keep a link to previous line (for copy) and as a flag to write in the first loop
            last_line_id = False
            # for each item from the product_ids_kit_selection
            for item_v in obj.product_ids_kit_selection:
                # price unit is mandatory
                if item_v.price_unit_kit_selection_line <= 0.0:
                    raise osv.except_osv(_('Warning !'), _('Unit Price must be specified for each line.'))
                # selected product_id
                product_id = item_v.product_id_kit_selection_line.id
                # selected qty
                qty = item_v.qty_kit_selection_line
                if qty <= 0.0:
                    raise osv.except_osv(_('Warning !'), _('Quantity must be greater than 0.0.'))
                # selected uom
                uom_id = item_v.uom_id_kit_selection_line.id
                # price unit
                price_unit = item_v.price_unit_kit_selection_line
                # call purchase order line on change function
                data = self.pool.get('kit.selection.line')._call_pol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit,
                                                                               type='product_id_change',
                                                                               context=dict(context, pol_ids=context['active_ids']))
                # common dictionary of data
                values = {'product_id': product_id,
                          'price_unit': item_v.price_unit_kit_selection_line,
                          'product_uom': uom_id,
                          'default_code': data['value']['default_code'],
                          'name': data['value']['name'],
                          'default_name': data['value']['default_name'],
                          }
                # if we are treating a line with link to so
                # if Internal Request, we do not update corresponding Internal Request
                if obj.corresponding_so_line_id_kit_selection and obj.impact_so_kit_selection and not obj.corresponding_so_id_kit_selection.procurement_request:
                    # if we have already update the existing pol, we create a new sol
                    # an go through the whole process
                    # if not, we simply update the pol, corresponding sol will be updated
                    # when the pol is confirmed
                    if last_line_id:
                        # we create a Fo line by copying related Fo line. we then execute procurement creation function, and process the procurement
                        # the merge into the actual Po is forced
                        # copy the original sale order line, reset po_cft to 'po' (we don't want a new tender if any)
                        values.update({'line_number': obj.corresponding_so_line_id_kit_selection.line_number, # the Fo is not draft anyway (sourced), following sequencing policy, split Fo line maintains original one
                                       'po_cft': 'po',
                                       'product_uom_qty': pol.product_qty*qty,
                                       'product_uom': uom_id,
                                       'product_uos_qty': pol.product_qty*qty,
                                       'product_uos': uom_id,
                                       'so_back_update_dest_po_id_sale_order_line': obj.order_line_id_kit_selection.order_id.id,
                                       'so_back_update_dest_pol_id_sale_order_line': obj.order_line_id_kit_selection.id,
                                       })
                        # copy existing sol
                        last_line_id = sol_obj.copy(cr, uid, last_line_id, values, context=ctx_keep_info)
                        # /* code deletion for partial confirmation US-3185 */
                    else:
                        # first item to be treated, we update the existing purchase order line
                        # sale order line will be updated when the Po is confirmed
                        last_line_id = obj.corresponding_so_line_id_kit_selection.id
                        # update values for pol structure
                        values.update({'product_qty': pol.product_qty*qty})
                        pol_obj.write(cr, uid, [obj.order_line_id_kit_selection.id], values, context=context)
                else:
                    # no link to so, or no impact desired
                    # create a new pol
                    # update values for pol structure
                    values.update({'product_qty': pol.product_qty*qty})
                    # following new sequencing policy, we check if resequencing occur (behavior 1).
                    # if not (behavior 2), the split line keeps the same line number as original line
                    if not pol_obj.allow_resequencing(cr, uid, [obj.order_line_id_kit_selection.id], context=context):
                        # set default value for line_number as the same as original line
                        values.update({'line_number': obj.order_line_id_kit_selection.line_number})

                    if last_line_id:
                        # the existing purchase order line has already been updated, we create a new one
                        # copy the original purchase order line
                        last_line_id = pol_obj.copy(cr, uid, last_line_id, values, context=ctx_keep_info)
                        # if original po line is confirmed, we action_confirm new line
                        if obj.order_line_id_kit_selection.state == 'confirmed':
                            pol_obj.action_confirm(cr, uid, [last_line_id], context=context)
                    else:
                        # first item to be treated, we update the existing line
                        last_line_id = obj.order_line_id_kit_selection.id
                        pol_obj.write(cr, uid, [last_line_id], values, context=context)

        return {'type': 'ir.actions.act_window_close'}

kit_selection()


class kit_selection_line(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'kit.selection.line'

    def create(self, cr, uid, vals, context=None):
        '''
        default price unit from pol on_change function
        '''
        # objects
        # id of corresponding purchase order line
        pol_id = context.get('active_ids', False) and context['active_ids'][0]
        if pol_id and ('price_unit_kit_selection_line' not in vals or vals.get('price_unit_kit_selection_line') == 0.0):
            # selected product_id
            product_id = vals.get('product_id_kit_selection_line', False)
            # selected qty
            qty = vals.get('qty_kit_selection_line', 0.0)
            # selected uom
            uom_id = vals.get('uom_id_kit_selection_line', False)
            # price unit
            price_unit = vals.get('price_unit_kit_selection_line', 0.0)
            # gather default values
            data = self._call_pol_on_change(cr, uid, context['active_ids'],
                                            product_id, qty, uom_id, price_unit, type='product_id_on_change',
                                            context=dict(context, pol_ids=context['active_ids']))
            # update price_unit value
            vals.update({'price_unit_kit_selection_line': data['value']['price_unit']})
        return super(kit_selection_line, self).create(cr, uid, vals, context=context)

    def _call_pol_on_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, type, context=None):
        '''
        core function from purchase order line

        def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        pol_obj = self.pool.get('purchase.order.line')
        prod_obj = self.pool.get('product.product')
        # id of corresponding purchase order line
        pol_id = context['pol_ids'][0]
        pol = pol_obj.browse(cr, uid, pol_id, context=context)
        # pricelist from purchase order
        pricelist_id = pol.order_id.pricelist_id.id
        # partner_id from purchase order
        partner_id = pol.order_id.partner_id.id
        # date_order from purchase order
        date_order = pol.order_id.date_order
        # fiscal_position from purchase order
        fiscal_position_id = pol.order_id.fiscal_position.id
        # date_planned from purchase order line
        date_planned = pol.date_planned
        # name
        name = False
        if product_id:
            name = prod_obj.read(cr, uid, product_id, ['name'], context=context)['name']
        # notes
        notes = pol.notes
        # state
        state = pol.order_id.state
        # gather default values
        if type in ['product_id_change', 'product_uom_change']:
            data = getattr(pol_obj, type)(cr, uid, ids, pricelist=pricelist_id, product=product_id, qty=qty, uom=uom_id,
                                          partner_id=partner_id, date_order=date_order, fiscal_position=fiscal_position_id, date_planned=date_planned,
                                          name=name, price_unit=price_unit, notes=notes)
        elif type == 'product_id_on_change':
            data = getattr(pol_obj, type)(cr, uid, ids, pricelist=pricelist_id, product=product_id,
                                          qty=qty, uom=uom_id, partner_id=partner_id, date_order=date_order,
                                          fiscal_position=fiscal_position_id, date_planned=date_planned, name=name,
                                          price_unit=price_unit, notes=notes, state=state, old_price_unit=False)
        return data

    def on_product_id_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, context=None):
        '''
        core function from purchase order line

        def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]

        # result
        result = {'value': {'qty_kit_selection_line': 0.0,
                            'uom_id_kit_selection_line': False,
                            'price_unit_kit_selection_line': 0.0}}
        # gather default values
#        data = self._call_pol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, 'product_id_change', context=context)
        data = self._call_pol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, 'product_id_on_change', context=context)
        # update result price_unit and default uom
        result['value'].update({'price_unit_kit_selection_line': 'price_unit' in data['value'] and data['value']['price_unit'] or 0.0,
                                'qty_kit_selection_line': 'product_qty' in data['value'] and data['value']['product_qty'] or 0.0,
                                'uom_id_kit_selection_line': 'product_uom' in data['value'] and data['value']['product_uom'] or False})

        uom_id = result.get('value', {}).get('uom_id_kit_selection_line')
        qty = result.get('value', {}).get('qty_kit_selection_line')
        if qty:
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty_kit_selection_line', result=result)

        # return result
        return result

    def on_uom_id_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, context=None):
        '''
        core function from purchase order line

        def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]

        # result
        result = {'value': {'qty_kit_selection_line': 0.0,
                            'price_unit_kit_selection_line': 0.0}}
        # gather default values
        data = self._call_pol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, 'product_uom_change', context=context)
        # update result price_unit - qty
        result['value'].update({'price_unit_kit_selection_line': 'price_unit' in data['value'] and data['value']['price_unit'] or 0.0,
                                'qty_kit_selection_line': 'product_qty' in data['value'] and data['value']['product_qty'] or 0.0})
        # return result
        return result

    _columns = {'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'order_line_id_kit_selection_line': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True, required=True),
                'wizard_id_kit_selection_line': fields.many2one('kit.selection', string='Kit Selection wizard'),
                # data
                'product_id_kit_selection_line': fields.many2one('product.product', string='Product', required=True),
                'qty_kit_selection_line': fields.float(string='Qty', required=True, related_uom='uom_id_kit_selection_line'),
                'uom_id_kit_selection_line': fields.many2one('product.uom', string='UoM', required=True),
                'price_unit_kit_selection_line': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price')),
                }

    _defaults = {'integrity_status': 'empty',
                 }

kit_selection_line()


