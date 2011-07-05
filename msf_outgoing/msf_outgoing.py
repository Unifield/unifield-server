# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import osv, fields
from tools.translate import _
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp

class stock_warehouse(osv.osv):
    '''
    add new packing, dispatch and distribution locations for input
    '''
    _inherit = "stock.warehouse"
    _name = "stock.warehouse"
    _columns = {
        'lot_packing_id': fields.many2one('stock.location', 'Location Packing', required=True, domain=[('usage','<>','view')]),
        'lot_dispatch_id': fields.many2one('stock.location', 'Location Dispatch', required=True, domain=[('usage','<>','view')]),
        'lot_distribution_id': fields.many2one('stock.location', 'Location Distribution', required=True, domain=[('usage','<>','view')]),
    }

stock_warehouse()

class stock_picking(osv.osv):
    '''
    override stock picking to add new attributes
    - flow_type: the type of flow (full, quick)
    - subtype: the subtype of picking object (picking, ppl, packing)
    - previous_step_id: the id of picking object of the previous step, picking for ppl, ppl for packing
    '''
    _inherit = 'stock.picking'
    _name = 'stock.picking'
    _columns = {'flow_type': fields.selection([('full', 'Full'),('quick', 'Quick')], string='Flow Type'),
                'subtype': fields.selection([('picking', 'Picking'),('ppl', 'PPL'),('packing', 'Packing')], string='Subtype'),
                'previous_step_id': fields.many2one('stock.picking', 'Previous step'),
                }
    
    #@@@override stock
    def action_assign(self, cr, uid, ids, *args):
        '''
        override to remove the error message, return False instead
        '''
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
            if not move_ids:
                return False
            self.pool.get('stock.move').action_assign(cr, uid, move_ids)
        return True
    #@@@end
    
    def create_picking(self, cr, uid, ids, context=None):
        '''
        open the wizard to create (partial) picking tickets
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
        
        # data
        name = _("Create Picking Ticket")
        model = 'create.picking'
        step = 'create'
        
        # create the memory object - passing the picking id to it through context
        wizard_id = self.pool.get("create.picking").create(
            cr, uid, {}, context=dict(context,
                                      active_ids=ids,
                                      step=step,
                                      back_model=model,
                                      back_wizard_ids=context.get('wizard_ids', False),
                                      wizard_name=name))
        
        # call action to wizard view
        return {
            'name':name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            step=step,
                            back_model=model,
                            back_wizard_ids=context.get('wizard_ids', False),
                            wizard_name=name)
        }
        
    def do_create_picking(self, cr, uid, ids, partial_datas, context=None):
        '''
        create the picking ticket from selected stock moves
        
        move here the logic of create picking
        available for picking loop
        '''
        pass
        
        
    def validate_picking(self, cr, uid, ids, context=None):
        '''
        validate the picking ticket
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        # data
        name = _("Validate Picking Ticket")
        model = 'create.picking'
        step = 'validate'
            
        # create the memory object - passing the picking id to it through context
        wizard_id = self.pool.get("create.picking").create(
            cr, uid, {}, context=dict(context,
                                      active_ids=ids,
                                      step=step,
                                      back_model=model,
                                      back_wizard_ids=context.get('wizard_ids', False),
                                      wizard_name=name))
        
        # call action to wizard view
        return {
            'name':name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            step=step,
                            back_model=model,
                            back_wizard_ids=context.get('wizard_ids', False),
                            wizard_name=name)
        }
        
    def do_validate_picking(self, cr, uid, ids, partial_datas, context=None):
        '''
        validate the picking ticket from selected stock moves
        
        move here the logic of validate picking
        available for picking loop
        '''
        pass
#        for pick in..
#        
#            ...
#        
#            self.action_move(cr, uid, [pick.id])
#            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
#        
    def ppl(self, cr, uid, ids, context=None):
        '''
        pack the ppl
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        # data
        name = _("PPL Information - step1")
        model = 'create.picking'
        step = 'ppl1'
        
        # create the memory object - passing the picking id to it through context
        wizard_id = self.pool.get("create.picking").create(
            cr, uid, {}, context=dict(context,
                                      active_ids=ids,
                                      step=step,
                                      back_model=model,
                                      back_wizard_ids=context.get('wizard_ids', False),
                                      wizard_name=name))
        # call action to wizard view
        return {
            'name': name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            step=step,
                            back_model=model,
                            back_wizard_ids=context.get('wizard_ids', False),
                            wizard_name=name)
        }
        
    def do_ppl1(self, cr, uid, ids, partial_datas_ppl1, context=None):
        '''
        - receives generated data from ppl
        - call action to ppl2 step with partial_datas_ppl1 in context
        '''
        # we need the context for the wizard switch
        assert context, 'No context defined'
            
        # data
        name = _("PPL Information - step2")
        model = 'create.picking'
        step = 'ppl2'
        
        # create the memory object - passing the picking id to it through context
        wizard_id = self.pool.get("create.picking").create(
            cr, uid, {}, context=dict(context,
                                      active_ids=ids,
                                      step=step,
                                      back_model=model,
                                      back_wizard_ids=context.get('wizard_ids', False),
                                      wizard_name=name,
                                      partial_datas_ppl1=partial_datas_ppl1))
        # call action to wizard view
        return {
            'name': name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            step=step,
                            back_model=model,
                            back_wizard_ids=context.get('wizard_ids', False),
                            wizard_name=name,
                            partial_datas_ppl1=partial_datas_ppl1)
        }
        
stock_picking()


class stock_move(osv.osv):
    '''
    
    '''
    _inherit = 'stock.move'
    _name = 'stock.move'
    
    def _product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        facade for product_available function from product (stock)
        '''
        # get the corresponding product ids
        result = {}
        for d in self.read(cr, uid, ids, ['product_id'], context):
            result[d['id']] = d['product_id'][0]
        
        # get the virtual stock identified by product ids
        virtual = self.pool.get('product.product')._product_available(cr, uid, result.values(), field_names, arg, context)
        
        # replace product ids by corresponding stock move id
        result = dict([id, virtual[result[id]]] for id in result.keys())
        return result
    
    _columns = {'virtual_available': fields.function(_product_available, method=True, type='float', string='Virtual Stock', help="Future stock for this product according to the selected locations or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming.", multi='qty_available', digits_compute=dp.get_precision('Product UoM')),
                'qty_per_pack': fields.integer(string='Qty p.p'),
                'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                }

stock_move()


class sale_order(osv.osv):
    '''
    re-override to modify behavior for outgoing workflow
    '''
    _inherit = 'sale.order'
    _name = 'sale.order'

    # @@@override@sale_override.sale.order.action_ship_create
    def action_ship_create(self, cr, uid, ids, *args, **kwargs):
        """
        - no call to confirmation for picking object's workflow
        - fill the new picking attributes (flow_type: 'full', subtype: 'picking')
        - the picking state is 'draft'
        - the move state is 'confirmed'
        """
        wf_service = netsvc.LocalService("workflow")
        picking_id = False
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        for order in self.browse(cr, uid, ids, context={}):
            proc_ids = []
            output_id = order.shop_id.warehouse_id.lot_packing_id.id
            picking_id = False
            for line in order.order_line:
                proc_id = False
                date_planned = datetime.now() + relativedelta(days=line.delay or 0.0)
                date_planned = (date_planned - timedelta(days=company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')

                if line.state == 'done':
                    continue
                move_id = False
                if line.product_id and line.product_id.product_tmpl_id.type in ('product', 'consu') and not line.order_id.procurement_request:
                    location_id = order.shop_id.warehouse_id.lot_stock_id.id
                    if not picking_id:
                        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
                        picking_id = self.pool.get('stock.picking').create(cr, uid, {
                            'name': pick_name,
                            'origin': order.name,
                            'type': 'out',
                            # 'state': 'auto',
                            'state': 'draft',
                            'move_type': order.picking_policy,
                            'sale_id': order.id,
                            'address_id': order.partner_shipping_id.id,
                            'note': order.note,
                            'invoice_state': (order.order_policy=='picking' and '2binvoiced') or 'none',
                            'company_id': order.company_id.id,
                            # subtype
                            'subtype': 'picking',
                            # flow type
                            'flow_type': 'full',
                        })
                    move_data =  {
                        'name': line.name[:64],
                        'picking_id': picking_id,
                        'product_id': line.product_id.id,
                        'date': date_planned,
                        'date_expected': date_planned,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'product_packaging': line.product_packaging.id,
                        'address_id': line.address_allotment_id.id or order.partner_shipping_id.id,
                        'location_id': location_id,
                        'location_dest_id': output_id,
                        'sale_line_id': line.id,
                        'tracking_id': False,
                        #'state': 'draft',
                        'state': 'confirmed',
                        #'state': 'waiting',
                        'note': line.notes,
                        'company_id': order.company_id.id,
                    }
                    move_data = self._hook_ship_create_stock_move(cr, uid, ids, move_data, line, *args, **kwargs)
                    move_id = self.pool.get('stock.move').create(cr, uid, move_data)

                if line.product_id:
                    proc_data = {
                        'name': line.name,
                        'origin': order.name,
                        'date_planned': date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                                or line.product_uom_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                        'company_id': order.company_id.id,
                    }
                    proc_data = self._hook_ship_create_procurement_order(cr, uid, ids, proc_data, line, *args, **kwargs)
                    proc_id = self.pool.get('procurement.order').create(cr, uid, proc_data)
                    proc_ids.append(proc_id)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'procurement_id': proc_id})
                    if order.state == 'shipping_except':
                        for pick in order.picking_ids:
                            for move in pick.move_lines:
                                if move.state == 'cancel':
                                    mov_ids = move_obj.search(cr, uid, [('state', '=', 'cancel'),('sale_line_id', '=', line.id),('picking_id', '=', pick.id)])
                                    if mov_ids:
                                        for mov in move_obj.browse(cr, uid, mov_ids):
                                            move_obj.write(cr, uid, [move_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})
                                            proc_obj.write(cr, uid, [proc_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})

            val = {}

            if picking_id:
                # the picking is kept in 'draft' state
                #wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
                self.pool.get('stock.picking').log_picking(cr, uid, [picking_id])

            for proc_id in proc_ids:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                if order.state == 'proc_progress':
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)

            if order.state == 'shipping_except':
                val['state'] = 'progress'
                val['shipped'] = False

                if (order.order_policy == 'manual'):
                    for line in order.order_line:
                        if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            val['state'] = 'manual'
                            break
            self.write(cr, uid, [order.id], val)
        return True
        # @@@end

sale_order()


class pack_type(osv.osv):
    '''
    pack type corresponding to a type of pack (name, length, width, height)
    '''
    _name = 'pack.type'
    _description = 'Pack Type'
    _columns = {'name': fields.char(string='Name', size=1024),
                'length': fields.float(digits=(16,2), string='Length [cm]'),
                'width': fields.float(digits=(16,2), string='Width [cm]'),
                'height': fields.float(digits=(16,2), string='Height [cm]'),
                }
    
pack_type()
