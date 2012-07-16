# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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

from osv import osv, fields
from tools.translate import _
import netsvc
from datetime import datetime, timedelta, date

from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import logging
import tools
import time
from os import path

class stock_warehouse(osv.osv):
    '''
    add new packing, dispatch and distribution locations for input
    '''
    _inherit = "stock.warehouse"
    _name = "stock.warehouse"
    
    _columns = {'lot_packing_id': fields.many2one('stock.location', 'Location Packing', required=True, domain=[('usage','<>','view')]),
                'lot_dispatch_id': fields.many2one('stock.location', 'Location Dispatch', required=True, domain=[('usage','<>','view')]),
                'lot_distribution_id': fields.many2one('stock.location', 'Location Distribution', required=True, domain=[('usage','<>','view')]),
                }
    
    _defaults = {'lot_packing_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Packing'),], context=c)) and obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Packing'),], context=c)[0] or False,
                 'lot_dispatch_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Dispatch'),], context=c)) and obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Dispatch'),], context=c)[0] or False,
                 'lot_distribution_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Distribution'),], context=c)) and obj.pool.get('stock.location').search(cr, uid, [('name', '=', 'Distribution'),], context=c)[0] or False,
                }

stock_warehouse()


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


class shipment(osv.osv):
    '''
    a shipment presents the data from grouped stock moves in a 'sequence' way
    '''
    _name = 'shipment'
    _description = 'represents a group of pack families'
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        prevent copy
        '''
        raise osv.except_osv(_('Error !'), _('Shipment copy is forbidden.'))
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset one2many fields
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        # reset one2many fields
        default.update(pack_family_memory_ids=[])
        result = super(shipment, self).copy_data(cr, uid, id, default=default, context=context)
        
        return result
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi function for global shipment values
        '''
        pf_memory_obj = self.pool.get('pack.family.memory')
        picking_obj = self.pool.get('stock.picking')
        
        result = {}
        for shipment in self.browse(cr, uid, ids, context=context):
            values = {'total_amount': 0.0,
                      'currency_id': False,
                      'num_of_packs': 0,
                      'total_weight': 0.0,
                      'state': 'draft',
                      'backshipment_id': False,
                      }
            result[shipment.id] = values
            # gather the state from packing objects, all packing must have the same state for shipment
            # for draft shipment, we can have done packing and draft packing
            packing_ids = picking_obj.search(cr, uid, [('shipment_id', '=', shipment.id),], context=context)
            # fields to check and get
            state = None
            first_shipment_packing_id = None
            backshipment_id = None
            # delivery validated
            delivery_validated = None
            # browse the corresponding packings
            for packing in picking_obj.browse(cr, uid, packing_ids, context=context):
                # state check
                # because when the packings are validated one after the other, it triggers the compute of state, and if we have multiple packing for this shipment, it will fail
                # if one packing is draft, even if other packing have been shipped, the shipment must stay draft until all packing are done
                if state != 'draft':
                    state = packing.state
                    
                # all corresponding shipment must be dev validated or not
                if packing.delivered:
                    # integrity check
                    if delivery_validated is not None and delivery_validated != packing.delivered:
                        # two packing have different delivery validated values -> problem
                        assert False, 'All packing do not have the same validated value - %s - %s'%(delivery_validated, packing.delivered)
                    # update the value
                    delivery_validated = packing.delivered
                
                # first_shipment_packing_id check - no check for the same reason
                first_shipment_packing_id = packing.first_shipment_packing_id.id
                
                # backshipment_id check
                if backshipment_id and backshipment_id != packing.backorder_id.shipment_id.id:
                    assert False, 'all packing of the shipment have not the same draft shipment correspondance - %s - %s'%(backshipment_id, packing.backorder_id.shipment_id.id)
                backshipment_id = packing.backorder_id and packing.backorder_id.shipment_id.id or False
            
            # if state is in ('draft', 'done', 'cancel'), the shipment keeps the same state
            if state not in ('draft', 'done', 'cancel',):
                if first_shipment_packing_id:
                    # second step of shipment : shipped
                    state = 'shipped'
                else:
                    state = 'packed'
            elif state == 'done':
                if delivery_validated:
                    # special state corresponding to delivery validated
                    state = 'delivered'
                    
            values['state'] = state
            values['backshipment_id'] = backshipment_id
            
            for memory_family in shipment.pack_family_memory_ids:
                # taken only into account if not done (done means returned packs)
                if memory_family.state not in ('done',):
                    # num of packs
                    num_of_packs = memory_family.num_of_packs
                    values['num_of_packs'] += int(num_of_packs)
                    # total weight
                    total_weight = memory_family.total_weight
                    values['total_weight'] += int(total_weight)
                    # total amount
                    total_amount = memory_family.total_amount
                    values['total_amount'] += total_amount
                    # currency
                    currency_id = memory_family.currency_id and memory_family.currency_id.id or False
                    values['currency_id'] = currency_id
                
        return result
    
    def _get_shipment_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of stock.picking objects for which state has changed
        
        return the list of ids of shipment object which need to get their state field updated
        '''
        pack_obj = self.pool.get('stock.picking')
        result = []
        for packing in pack_obj.browse(cr, uid, ids, context=context):
            if packing.shipment_id and packing.shipment_id.id not in result:
                result.append(packing.shipment_id.id)
        return result
    
    def _packs_search(self, cr, uid, obj, name, args, context=None):
        """ 
        Searches Ids of shipment
        """
        if context is None:
            context = {}
            
        shipments = self.pool.get('shipment').search(cr, uid, [], context=context)
        # result dic
        result = {}
        for shipment in self.browse(cr, uid, shipments, context=context):
            result[shipment.id] = shipment.num_of_packs
        # construct the request
        # adapt the operator
        op = args[0][1]
        if op == '=':
            op = '=='
        ids = [('id', 'in', [x for x in result.keys() if eval("%s %s %s"%(result[x], op, args[0][2]))])]
        return ids

    _columns = {'name': fields.char(string='Reference', size=1024),
                'date': fields.datetime(string='Creation Date'),
                'shipment_expected_date': fields.datetime(string='Expected Ship Date'),
                'shipment_actual_date': fields.datetime(string='Actual Ship Date', readonly=True,),
                'transport_type': fields.selection([('by_road', 'By road')],
                                                   string="Transport Type", readonly=True),
                'address_id': fields.many2one('res.partner.address', 'Address', help="Address of customer"),
                'sequence_id': fields.many2one('ir.sequence', 'Shipment Sequence', help="This field contains the information related to the numbering of the shipment.", ondelete='cascade'),
                # cargo manifest things
                'cargo_manifest_reference': fields.char(string='Cargo Manifest Reference', size=1024,),
                'date_of_departure': fields.date(string='Date of Departure'),
                'planned_date_of_arrival': fields.date(string='Planned Date of Arrival'),
                'transit_via': fields.char(string='Transit via', size=1024),
                'registration': fields.char(string='Registration', size=1024),
                'driver_name': fields.char(string='Driver Name', size=1024),
                # -- shipper
                'shipper_name': fields.char(string='Name', size=1024),
                'shipper_address': fields.char(string='Address', size=1024),
                'shipper_phone': fields.char(string='Phone', size=1024),
                'shipper_email': fields.char(string='Email', size=1024),
                'shipper_other': fields.char(string='Other', size=1024),
                'shipper_date': fields.date(string='Date'),
                'shipper_signature': fields.char(string='Signature', size=1024),
                # -- carrier
                'carrier_name': fields.char(string='Name', size=1024),
                'carrier_address': fields.char(string='Address', size=1024),
                'carrier_phone': fields.char(string='Phone', size=1024),
                'carrier_email': fields.char(string='Email', size=1024),
                'carrier_other': fields.char(string='Other', size=1024),
                'carrier_date': fields.date(string='Date'),
                'carrier_signature': fields.char(string='Signature', size=1024),
                # -- consignee
                'consignee_name': fields.char(string='Name', size=1024),
                'consignee_address': fields.char(string='Address', size=1024),
                'consignee_phone': fields.char(string='Phone', size=1024),
                'consignee_email': fields.char(string='Email', size=1024),
                'consignee_other': fields.char(string='Other', size=1024),
                'consignee_date': fields.date(string='Date'),
                'consignee_signature': fields.char(string='Signature', size=1024),
                # functions
                'partner_id': fields.related('address_id', 'partner_id', type='many2one', relation='res.partner', string='Customer', store=True),
                'partner_id2': fields.many2one('res.partner', string='Customer', required=False),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals',),
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
                'num_of_packs': fields.function(_vals_get, method=True, fnct_search=_packs_search, type='integer', string='Number of Packs', multi='get_vals_X',), # old_multi ship_vals
                'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals',),
                'state': fields.function(_vals_get, method=True, type='selection', selection=[('draft', 'Draft'),
                                                                                              ('packed', 'Packed'),
                                                                                              ('shipped', 'Shipped'),
                                                                                              ('done', 'Closed'),
                                                                                              ('delivered', 'Delivered'),
                                                                                              ('cancel', 'Cancelled')], string='State', multi='get_vals',
                                         store= {'stock.picking': (_get_shipment_ids, ['state', 'shipment_id', 'delivered'], 10),}),
                'backshipment_id': fields.function(_vals_get, method=True, type='many2one', relation='shipment', string='Draft Shipment', multi='get_vals',),
                # added by Quentin https://bazaar.launchpad.net/~unifield-team/unifield-wm/trunk/revision/426.20.14
                'parent_id': fields.many2one('shipment', string='Parent shipment'),
                }
    _defaults = {'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),}
    
    
    _order = 'name desc'
    
    def create_shipment(self, cr, uid, ids, context=None):
        '''
        open the wizard to create (partial) shipment
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        wiz_obj = self.pool.get('wizard')
        
        # data
        name = _("Create Shipment")
        model = 'shipment.wizard'
        step = 'create'
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
    
    def do_create_shipment(self, cr, uid, ids, context=None):
        '''
        for each original draft picking:
         - creation of the new packing object with empty moves
         - convert partial data to move related data
         - create corresponding moves in new packing
         - update initial packing object
         - trigger workflow for new packing object
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'partial_datas_shipment' in context, 'partial_datas_shipment no defined in context'
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        shipment_obj = self.pool.get('shipment')
        
        # data from wizard
        partial_datas_shipment = context['partial_datas_shipment']
        # shipment ids from ids must be equal to shipment ids from partial datas
        assert set(ids) == set(partial_datas_shipment.keys()), 'shipment ids from ids and partial do not match'
        
        for draft_shipment in self.browse(cr, uid, partial_datas_shipment.keys(), context=context):
            # for each shipment create a new shipment which will be used by the group of new packing objects
            address_id = shipment_obj.read(cr, uid, [draft_shipment.id], ['address_id'], context=context)[0]['address_id'][0]
            partner_id = shipment_obj.read(cr, uid, [draft_shipment.id], ['partner_id'], context=context)[0]['partner_id'][0]
            sequence = draft_shipment.sequence_id
            shipment_number = sequence.get_id(test='id', context=context)
            # state is a function - not set
            shipment_name = draft_shipment.name + '-' + shipment_number
            # 
            values = {'name': shipment_name, 'address_id': address_id, 'partner_id': partner_id, 'partner_id2': partner_id, 'shipment_expected_date': draft_shipment.shipment_expected_date, 'shipment_actual_date': draft_shipment.shipment_actual_date, 'parent_id': draft_shipment.id}
            shipment_id = shipment_obj.create(cr, uid, values, context=context)
            context['shipment_id'] = shipment_id
            for draft_packing in pick_obj.browse(cr, uid, partial_datas_shipment[draft_shipment.id].keys(), context=context):
                # copy the picking object without moves
                # creation of moves and update of initial in picking create method
                context.update(draft_shipment_id=draft_shipment.id, draft_packing_id=draft_packing.id)
                sequence = draft_packing.sequence_id
                packing_number = sequence.get_id(test='id', context=context)
                new_packing_id = pick_obj.copy(cr, uid, draft_packing.id,
                                               {'name': draft_packing.name + '-' + packing_number,
                                                'backorder_id': draft_packing.id,
                                                'shipment_id': False,
                                                'move_lines': []}, context=dict(context, keep_prodlot=True, allow_copy=True,))

                # confirm the new packing
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', new_packing_id, 'button_confirm', cr)
                # simulate check assign button, as stock move must be available
                pick_obj.force_assign(cr, uid, [new_packing_id])
                
            # log creation message
            self.log(cr, uid, shipment_id, _('The new Shipment %s has been created.')%(shipment_name,))
            # the shipment is automatically shipped, no more pack states in between.
            self.ship(cr, uid, [shipment_id], context=context)
        # TODO which behavior
        return {'type': 'ir.actions.act_window_close'}
    
    def return_packs(self, cr, uid, ids, context=None):
        '''
        open the wizard to return packs from draft shipment
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        wiz_obj = self.pool.get('wizard')
        
        # data
        name = _("Return Packs")
        model = 'shipment.wizard'
        step = 'returnpacks'
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
    
    def do_return_packs(self, cr, uid, ids, context=None):
        '''
        for each original draft picking:
         - convert partial data to move related data
         - update the draft_packing's moves, decrease quantity and update from/to info
         - update initial packing object
         - create a back move for each move with return quantity to initial location
         - increase quantity of related draft_picking_ticket's moves
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'partial_datas' in context, 'partial_datas no defined in context'
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        obj_data = self.pool.get('ir.model.data')
        
        # data from wizard
        partial_datas = context['partial_datas']
        # shipment ids from ids must be equal to shipment ids from partial datas
        assert set(ids) == set(partial_datas.keys()), 'shipment ids from ids and partial do not match'
        
        for draft_shipment_id in partial_datas:
            # log flag - log for draft shipment is displayed only one time for each draft shipment
            log_flag = False
            # for each draft packing
            for draft_packing in pick_obj.browse(cr, uid, partial_datas[draft_shipment_id].keys(), context=context):
                # corresponding draft picking ticket -> draft_packing - ppl - picking_ticket - draft_picking_ticket
                draft_picking = draft_packing.previous_step_id.previous_step_id.backorder_id
                draft_picking_id = draft_packing.previous_step_id.previous_step_id.backorder_id.id
                # for each sequence
                for from_pack in partial_datas[draft_shipment_id][draft_packing.id]:
                    for to_pack in partial_datas[draft_shipment_id][draft_packing.id][from_pack]:
                        # partial data for one sequence of one draft packing
                        data = partial_datas[draft_shipment_id][draft_packing.id][from_pack][to_pack][0]
                        # total number of packs
                        total_num = to_pack - from_pack + 1
                        # number of returned packs
                        selected_number = data['selected_number']
                        # we take the packs with the highest numbers
                        # new moves
                        selected_from_pack = to_pack - selected_number + 1
                        selected_to_pack = to_pack
                        # update initial moves
                        if selected_number == total_num:
                            # if all packs have been selected, from/to are set to 0
                            initial_from_pack = 0
                            initial_to_pack = 0
                        else:
                            initial_from_pack = from_pack
                            initial_to_pack = to_pack - selected_number
                        # find the concerned stock moves
                        move_ids = move_obj.search(cr, uid, [('picking_id', '=', draft_packing.id),
                                                             ('from_pack', '=', from_pack),
                                                             ('to_pack', '=', to_pack)])
                        # update the moves, decrease the quantities
                        for move in move_obj.browse(cr, uid, move_ids, context=context):
                            # stock move are not canceled as for ppl return process
                            # because this represents a draft packing, meaning some shipment could be canceled and
                            # returned to this stock move
                            # initial quantity
                            initial_qty = move.product_qty
                            # quantity to return
                            return_qty = selected_number * move.qty_per_pack
                            # update initial quantity
                            initial_qty = max(initial_qty - return_qty, 0)
                            values = {'product_qty': initial_qty,
                                      'from_pack': initial_from_pack,
                                      'to_pack': initial_to_pack,}
                            
                            move_obj.write(cr, uid, [move.id], values, context=context)
                            
                            # create a back move with the quantity to return to the good location
                            # the good location is stored in the 'initial_location' field
                            copy_id = move_obj.copy(cr, uid, move.id, {'product_qty': return_qty,
                                                             'location_dest_id': move.initial_location.id,
                                                             'from_pack': selected_from_pack,
                                                             'to_pack': selected_to_pack,
                                                             'state': 'done'}, context=context)
                            # find the corresponding move in draft in the draft **picking**
                            draft_move = move.backmove_id
                            # increase the draft move with the move quantity
                            draft_initial_qty = move_obj.read(cr, uid, [draft_move.id], ['product_qty'], context=context)[0]['product_qty']
                            draft_initial_qty += return_qty
                            move_obj.write(cr, uid, [draft_move.id], {'product_qty': draft_initial_qty}, context=context)
            
                # log the increase action - display the picking ticket view form - log message for each draft packing because each corresponds to a different draft picking
                if not log_flag:
                    draft_shipment_name = self.read(cr, uid, draft_shipment_id, ['name'], context=context)['name']
                    self.log(cr, uid, draft_shipment_id, _("Packs from the draft Shipment (%s) have been returned to stock.")%(draft_shipment_name,))
                    log_flag = True
                res = obj_data.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1]
                self.pool.get('stock.picking').log(cr, uid, draft_picking_id, _("The corresponding Draft Picking Ticket (%s) has been updated.")%(draft_picking.name,), context={'view_id': res,})
            
        # call complete_finished on the shipment object
        # if everything is alright (all draft packing are finished) the shipment is done also 
        result = self.complete_finished(cr, uid, partial_datas.keys(), context=context)
        
        # TODO which behavior
        return {'type': 'ir.actions.act_window_close'}
    
    def return_packs_from_shipment(self, cr, uid, ids, context=None):
        '''
        open the wizard to return packs from draft shipment
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        wiz_obj = self.pool.get('wizard')
        
        # data
        name = _("Return Packs from Shipment")
        model = 'shipment.wizard'
        step = 'returnpacksfromshipment'
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
    
    def compute_sequences(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        compute corresponding sequences
        '''
        datas = kwargs['datas']
        from_pack = kwargs['from_pack']
        to_pack = kwargs['to_pack']
        # the list of tuple representing the packing movements from/to - default to sequence value
        stay = [(from_pack, to_pack)]
        # the list of tuple representing the draft packing movements from/to
        back_to_draft = []
        
        # loop the partials
        for partial in datas:
            return_from = partial['return_from']
            return_to = partial['return_to']
            # create the corresponding tuple
            back_to_draft.append((return_from, return_to))
            # stay list must be ordered
            sorted(stay)
            # find the corresponding tuple in the stay list
            for i in range(len(stay)):
                # the tuple are ordered
                seq = stay[i]
                if seq[1] >= return_to:
                    # this is the good tuple
                    # stay tuple creation logic
                    if return_from == seq[0]:
                        if return_to == seq[1]:
                            # all packs for this sequence are sent back - simply remove it
                            break
                        else:
                            # to+1-seq[1] in stay
                            stay.append((return_to+1, seq[1]))
                            break
                    
                    elif return_to == seq[1]:
                        # do not start at beginning, but same end
                        stay.append((seq[0], return_from-1))
                        break
                    
                    else:
                        # in the middle, two new tuple in stay
                        stay.append((seq[0], return_from-1))
                        stay.append((return_to+1, seq[1]))
                        break
            
            # old one is always removed
            stay.pop(i)
            
        # return both values - return order is important
        return stay, back_to_draft
    
    def do_return_packs_from_shipment(self, cr, uid, ids, context=None):
        '''
        return the packs to the corresponding draft packing object
        
        for each corresponding draft packing
        - 
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'partial_datas' in context, 'partial_datas no defined in context'
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        
        # data from wizard
        partial_datas = context['partial_datas']
        # shipment ids from ids must be equal to shipment ids from partial datas
        assert set(ids) == set(partial_datas.keys()), 'shipment ids from ids and partial do not match'
        
        # for each shipment
        for shipment_id in partial_datas:
            # for each packing
            for packing in pick_obj.browse(cr, uid, partial_datas[shipment_id].keys(), context=context):
                # corresponding draft packing -> backorder
                draft_packing_id = packing.backorder_id.id
                # corresponding draft shipment (all packing for a shipment belong to the same draft_shipment)
                draft_shipment_id = packing.backorder_id.shipment_id.id
                # for each sequence
                for from_pack in partial_datas[shipment_id][packing.id]:
                    for to_pack in partial_datas[shipment_id][packing.id][from_pack]:
                        # partial datas for one sequence of one packing
                        # could have multiple data multiple products in the same pack family
                        datas = partial_datas[shipment_id][packing.id][from_pack][to_pack]
                        # the corresponding moves
                        move_ids = move_obj.search(cr, uid, [('picking_id', '=', packing.id),
                                                             ('from_pack', '=', from_pack),
                                                             ('to_pack', '=', to_pack)], context=context)
                        
                        # compute the sequences to stay/to return to draft packing
                        stay, back_to_draft = self.compute_sequences(cr, uid, ids, context=context,
                                                                     datas=datas,
                                                                     from_pack=from_pack,
                                                                     to_pack=to_pack,)
                        
                        # we have the information concerning movements to update the packing and the draft packing
                        
                        # update the packing object, we update the existing move
                        # if needed new moves are created
                        updated = {}
                        for move in move_obj.browse(cr, uid, move_ids, context=context):
                            # update values
                            updated[move.id] = {'initial': move.product_qty, 'partial_qty': 0}
                            # loop through stay sequences
                            for seq in stay:
                                # corresponding number of packs
                                selected_number = seq[1] - seq[0] + 1
                                # quantity to return
                                new_qty = selected_number * move.qty_per_pack
                                # for both cases, we update the from/to and compute the corresponding quantity
                                # if the move has been updated already, we copy/update
                                values = {'from_pack': seq[0],
                                          'to_pack': seq[1],
                                          'product_qty': new_qty,
                                          'state': 'assigned'}
                                
                                # the original move is never modified, but canceled
                                updated[move.id]['partial_qty'] += new_qty
                                new_move_id = move_obj.copy(cr, uid, move.id, values, context=context)
                                
#                            # nothing stays
#                            if 'partial_qty' not in updated[move.id]:
#                                updated[move.id]['partial_qty'] = 0
                                    
                            # loop through back_to_draft sequences
                            for seq in back_to_draft:
                                # for each sequence we add the corresponding stock move to draft packing
                                # corresponding number of packs
                                selected_number = seq[1] - seq[0] + 1
                                # quantity to return
                                new_qty = selected_number * move.qty_per_pack
                                # values
                                location_dispatch = move.picking_id.warehouse_id.lot_dispatch_id.id
                                location_distrib = move.picking_id.warehouse_id.lot_distribution_id.id
                                values = {'from_pack': seq[0],
                                          'to_pack': seq[1],
                                          'product_qty': new_qty,
                                          'location_id': location_distrib,
                                          'location_dest_id': location_dispatch,
                                          'state': 'done'}
                                
                                # create a back move in the packing object
                                # distribution -> dispatch
                                new_back_move_id = move_obj.copy(cr, uid, move.id, values, context=context)
                                updated[move.id]['partial_qty'] += new_qty

                                # create the draft move
                                # dispatch -> distribution
                                # picking_id = draft_picking
                                values.update(location_id=location_dispatch,
                                              location_dest_id=location_distrib,
                                              picking_id=draft_packing_id,
                                              state='assigned')
                                new_draft_move_id = move_obj.copy(cr, uid, move.id, values, context=context)
                                
                            # quantities are right - stay + return qty = original qty
                            assert all([updated[m]['initial'] == updated[m]['partial_qty'] for m in updated.keys()]), 'initial quantity is not equal to the sum of partial quantities (%s).'%(updated)
                            # if packs are returned corresponding move is canceled
                            # cancel move or 0 qty + done ?
                            #move_obj.action_cancel(cr, uid, [move.id], context=context)
                            move_obj.write(cr, uid, [move.id], {'product_qty': 0.0, 'state': 'done', 'from_pack': 0, 'to_pack': 0,}, context=context)
            
            # log corresponding action
            shipment_name = self.read(cr, uid, shipment_id, ['name'], context=context)['name']
            self.log(cr, uid, shipment_id, _("Packs from the shipped Shipment (%s) have been returned to dispatch location.")%(shipment_name,))
            self.log(cr, uid, draft_shipment_id, _("The corresponding Draft Shipment (%s) has been updated.")%(packing.backorder_id.shipment_id.name,))
                            
        # call complete_finished on the shipment object
        # if everything is allright (all draft packing are finished) the shipment is done also 
        self.complete_finished(cr, uid, partial_datas.keys(), context=context)
        
        # TODO which behavior
        return {'type': 'ir.actions.act_window_close'}
        
    def action_cancel(self, cr, uid, ids, context=None):
        '''
        cancel the shipment which is not yet shipped (packed state)
        
        - for each related packing object
         - trigger the cancel workflow signal
         logic is performed in the action_cancel method of stock.picking
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        
        for shipment in self.browse(cr, uid, ids, context=context):
            # shipment state should be 'packed'
            assert shipment.state == 'packed', 'cannot ship a shipment which is not in correct state - packed - %s'%shipment.state
            # for each shipment
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id)], context=context)
            # call cancel workflow on corresponding packing objects
            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                # we cancel each picking object - action_cancel is overriden at stock_picking level for stock_picking of subtype == 'packing'
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_cancel', cr)
            # log corresponding action
            self.log(cr, uid, shipment.id, _("The Shipment (%s) has been canceled.")%(shipment.name,))
            self.log(cr, uid, shipment.backshipment_id.id, _("The corresponding Draft Shipment (%s) has been updated.")%(shipment.backshipment_id.name,))
                
        return True
    
    def ship(self, cr, uid, ids, context=None):
        '''
        we ship the created shipment, the state of the shipment is changed, we do not use any wizard
        - state of the shipment is updated to 'shipped'
        - copy the packing
        - modify locations of moves for the new packing
        - trigger the workflow button_confirm for the new packing
        - trigger the workflow to terminate the initial packing
        - update the draft_picking_id fields of pack_families
        - update the shipment_date of the corresponding sale_order if not set yet
        '''
        pick_obj = self.pool.get('stock.picking')
        pf_obj = self.pool.get('pack.family')
        so_obj = self.pool.get('sale.order')
        # objects
        date_tools = self.pool.get('date.tools')
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)
        
        for shipment in self.browse(cr, uid, ids, context=context):
            # shipment state should be 'packed'
            assert shipment.state == 'packed', 'cannot ship a shipment which is not in correct state - packed - %s'%shipment.state
            # the state does not need to be updated - function
            # update actual ship date (shipment_actual_date) to today + time
            today = time.strftime(db_datetime_format)
            shipment.write({'shipment_actual_date': today,})
            # corresponding packing objects
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id)], context=context)
            
            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                assert packing.subtype == 'packing'
                # update the packing object for the same reason
                # - an integrity check at _get_vals level of shipment states that all packing linked to a shipment must have the same state
                # we therefore modify it before the copy, otherwise new (assigned) and old (done) are linked to the same shipment
                # -> integrity check has been removed
                pick_obj.write(cr, uid, [packing.id], {'shipment_id': False,}, context=context)
                # copy each packing
                new_packing_id = pick_obj.copy(cr, uid, packing.id, {'name': packing.name,
                                                                     'first_shipment_packing_id': packing.id,
                                                                     'shipment_id': shipment.id,}, context=dict(context, keep_prodlot=True, allow_copy=True,))
                pick_obj.write(cr, uid, [new_packing_id], {'origin': packing.origin}, context=context)
                new_packing = pick_obj.browse(cr, uid, new_packing_id, context=context)
                # update the shipment_date of the corresponding sale order if the date is not set yet - with current date
                if new_packing.sale_id and not new_packing.sale_id.shipment_date:
                    # get the date format
                    date_tools = self.pool.get('date.tools')
                    date_format = date_tools.get_date_format(cr, uid, context=context)
                    db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
                    today = time.strftime(date_format)
                    today_db = time.strftime(db_date_format)
                    so_obj.write(cr, uid, [new_packing.sale_id.id], {'shipment_date': today_db,}, context=context)
                    so_obj.log(cr, uid, new_packing.sale_id.id, _("Shipment Date of the Sale Order '%s' has been updated to %s.")%(new_packing.sale_id.name, today))
                
                # update locations of stock moves
                for move in new_packing.move_lines:
                    move.write({'location_id': new_packing.warehouse_id.lot_distribution_id.id,
                                'location_dest_id': new_packing.warehouse_id.lot_output_id.id}, context=context)
                
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', new_packing_id, 'button_confirm', cr)
                # simulate check assign button, as stock move must be available
                pick_obj.force_assign(cr, uid, [new_packing_id])
                # trigger standard workflow
                pick_obj.action_move(cr, uid, [packing.id])
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_done', cr)
                
            # log the ship action
            self.log(cr, uid, shipment.id, _('The Shipment %s has been shipped.')%(shipment.name,))
    
        # TODO which behavior
        return True
    
    def complete_finished(self, cr, uid, ids, context=None):
        '''
        - check all draft packing corresponding to this shipment
          - check the stock moves (qty and from/to)
          - check all corresponding packing are done or canceled (no ongoing shipment)
          - if all packings are ok, the draft is validated
        - if all draft packing are ok, the shipment state is done
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        
        for shipment_base in self.browse(cr, uid, ids, context=context):
            # the shipment which will be treated
            shipment = shipment_base
            
            if shipment.state not in ('draft',):
                # it's not a draft shipment, check all corresponding packing, trg.write them
                packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id),], context=context)
                for packing_id in packing_ids:
                    wf_service.trg_write(uid, 'stock.picking', packing_id, cr)
                
                # this shipment is possibly finished, we now check the corresponding draft shipment
                # this will possibly validate the draft shipment, if everything is finished and corresponding draft picking
                shipment = shipment.backshipment_id
                
            # draft packing for this shipment - some draft packing can already be done for this shipment, so we filter according to state
            draft_packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '=', 'draft'),], context=context)
            for draft_packing in pick_obj.browse(cr, uid, draft_packing_ids, context=context):
                assert draft_packing.subtype == 'packing', 'draft packing which is not packing subtype - %s'%draft_packing.subtype
                assert draft_packing.state == 'draft', 'draft packing which is not draft state - %s'%draft_packing.state
                # we check if the corresponding draft packing can be moved to done.
                # if all packing with backorder_id equal to draft are done or canceled
                # and the quantity for each stock move (state != done) of the draft packing is equal to zero
                
                # we first check the stock moves quantities of the draft packing
                # we can have done moves when some packs are returned
                treat_draft = True
                for move in draft_packing.move_lines:
                    if move.state not in ('done',):
                        if move.product_qty:
                            treat_draft = False
                        elif move.from_pack or move.to_pack:
                            # qty = 0, from/to pack should have been set to zero
                            assert False, 'stock moves with 0 quantity but part of pack family sequence'
                
                # check if ongoing packing are present, if present, we do not validate the draft one, the shipping is not finished
                if treat_draft:
                    linked_packing_ids = pick_obj.search(cr, uid, [('backorder_id', '=', draft_packing.id),
                                                                   ('state', 'not in', ['done', 'cancel'])], context=context)
                    if linked_packing_ids:
                        treat_draft = False
                
                if treat_draft:
                    # trigger the workflow for draft_picking
                    # confirm the new picking ticket
                    wf_service.trg_validate(uid, 'stock.picking', draft_packing.id, 'button_confirm', cr)
                    # we force availability
                    pick_obj.force_assign(cr, uid, [draft_packing.id])
                    # finish
                    pick_obj.action_move(cr, uid, [draft_packing.id])
                    wf_service.trg_validate(uid, 'stock.picking', draft_packing.id, 'button_done', cr)
                    # ask for draft picking validation, depending on picking completion
                    # if picking ticket is not completed, the validation will not complete
                    draft_packing.previous_step_id.previous_step_id.backorder_id.validate(context=context)
            
            # all draft packing are validated (done state) - the state of shipment is automatically updated -> function
        return True
        
    def validate(self, cr, uid, ids, context=None):
        '''
        validate the shipment
        
        change the state to Done for the corresponding packing
        - validate the workflow for all the packings
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        
        for shipment in self.browse(cr, uid, ids, context=context):
            # validate should only be called on shipped shipments
            assert shipment.state in ('shipped',), 'shipment state is not shipped'
            # corresponding packing objects - only the distribution -> customer ones
            # we have to discard picking object with state done, because when we return from shipment
            # all object of a given picking object, he is set to Done and still belong to the same shipment_id
            # another possibility would be to unlink the picking object from the shipment, set shipment_id to False
            # but in this case the returned pack families would not be displayed anymore in the shipment
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '!=', 'done'),], context=context)
            
            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                assert packing.subtype == 'packing' and packing.state == 'assigned'
                # trigger standard workflow
                pick_obj.action_move(cr, uid, [packing.id])
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_done', cr)
                
            # log validate action
            self.log(cr, uid, shipment.id, _('The Shipment %s has been validated.')%(shipment.name,))
            
        result = self.complete_finished(cr, uid, ids, context=context)
        return True
    
    def set_delivered(self, cr, uid, ids, context=None):
        '''
        set the delivered flag
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        for shipment in self.browse(cr, uid, ids, context=context):
            # validate should only be called on shipped shipments
            assert shipment.state in ['done'], 'shipment state is not shipped'
            # gather the corresponding packing and trigger the corresponding function
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '=', 'done')], context=context)
            # set delivered all packings
            pick_obj.set_delivered(cr, uid, packing_ids, context=context)
            
        return True
        
shipment()


class pack_family_memory(osv.osv_memory):
    '''
    dynamic memory object for pack families
    '''
    _name = 'pack.family.memory'
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for pf_memory in self.browse(cr, uid, ids, context=context):
            values = {'move_lines': [],
                      'state': 'draft',
                      'location_id': False,
                      'location_dest_id': False,
                      'total_amount': 0.0,
                      'amount': 0.0,
                      'currency_id': False,
                      'num_of_packs': 0,
                      'total_weight': 0.0,
                      }
            result[pf_memory.id] = values
            # pack family related fields
            if pf_memory.to_pack == 0:
                num_of_packs = 0
            else:
                num_of_packs = pf_memory.to_pack - pf_memory.from_pack + 1
            values['num_of_packs'] = num_of_packs
            values['total_weight'] = pf_memory.weight * num_of_packs
            
            # moves related fields
            for move in pf_memory.draft_packing_id.move_lines:
                if move.from_pack == pf_memory.from_pack:
                    if move.to_pack == pf_memory.to_pack:
                        # this move is in the good packing object and corresponds to this pack family
                        # we add it to the stock move list
                        values['move_lines'].append(move.id)
                        values['state'] = move.state
                        values['location_id'] = move.location_id.id
                        values['location_dest_id'] = move.location_dest_id.id
                        values['total_amount'] += move.total_amount
                        values['amount'] += move.amount
                        values['currency_id'] = move.currency_id and move.currency_id.id or False
                    else:
                        raise osv.except_osv(_('Error !'), _('Integrity check failed! Pack Family and Stock Moves from/to do not match.'))
                    
        return result
    
    _columns = {'name': fields.char(string='Reference', size=1024),
                'shipment_id': fields.many2one('shipment', string='Shipment'),
                'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
                'ppl_id': fields.many2one('stock.picking', string="PPL Ref"),
                'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                'pack_type': fields.many2one('pack.type', string='Pack Type'),
                'length' : fields.float(digits=(16,2), string='Length [cm]'),
                'width' : fields.float(digits=(16,2), string='Width [cm]'),
                'height' : fields.float(digits=(16,2), string='Height [cm]'),
                'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
                # functions
                'move_lines': fields.function(_vals_get, method=True, type='one2many', relation='stock.move', string='Stock Moves', multi='get_vals',),
                'state': fields.function(_vals_get, method=True, type='selection', selection=[('draft', 'Draft'),
                                                                                              ('assigned', 'Available'),
                                                                                              ('stock_return', 'Returned to Stock'),
                                                                                              ('ship_return', 'Returned from Shipment'),
                                                                                              ('cancel', 'Cancelled'),
                                                                                              ('done', 'Closed'),], string='State', multi='get_vals',),
                'location_id': fields.function(_vals_get, method=True, type='many2one', relation='stock.location', string='Src Loc.', multi='get_vals',),
                'location_dest_id': fields.function(_vals_get, method=True, type='many2one', relation='stock.location', string='Dest. Loc.', multi='get_vals',),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals',),
                'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', multi='get_vals',),
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals',),
                'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals',),
                }
    
    _defaults = {'shipment_id': False,
                 'draft_packing_id': False,
                 }
    
pack_family_memory()


class shipment2(osv.osv):
    '''
    add pack_family_ids
    '''
    _inherit = 'shipment'
    
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
    
    def _vals_get_2(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        picking_obj = self.pool.get('stock.picking')
        
        result = {}
        for shipment in self.browse(cr, uid, ids, context=context):
            values = {'pack_family_memory_ids':[],
                      }
            result[shipment.id] = values
            # look for all corresponding packing
            packing_ids = picking_obj.search(cr, uid, [('shipment_id', '=', shipment.id),], context=context)
            # get the corresponding data
            data = picking_obj.generate_data_from_picking_for_pack_family(cr, uid, packing_ids, context=context)
            # create a memory family
            created_ids = picking_obj.create_pack_families_memory_from_data(cr, uid, data, shipment.id, context=context)
            values['pack_family_memory_ids'].extend(created_ids)
            
        return result
    
    _columns = {'pack_family_memory_ids': fields.function(_vals_get_2, method=True, type='one2many', relation='pack.family.memory', string='Memory Families', multi='get_vals_2',),
                }

shipment2()


class ppl_customize_label(osv.osv):
    '''
    label preferences
    '''
    _name = 'ppl.customize.label'
    
    def init(self, cr):
        """
        Load msf_outgoing_data.xml before self
        """
        if hasattr(super(ppl_customize_label, self), 'init'):
            super(ppl_customize_label, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module msf_outgoing: loading data/msf_outgoing_data.xml')
        pathname = path.join('msf_outgoing', 'data/msf_outgoing_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'msf_outgoing', file, {}, mode='init', noupdate=False)

    _columns = {'name': fields.char(string='Name', size=1024,),
                'notes': fields.text(string='Notes'),
                #'packing_list_reference': fields.boolean(string='Packing List Reference'),
                'pre_packing_list_reference': fields.boolean(string='Pre-Packing List Reference'),
                'destination_partner': fields.boolean(string='Destination Partner'),
                'destination_address': fields.boolean(string='Destination Address'),
                'requestor_order_reference': fields.boolean(string='Requestor Order Reference'),
                'weight': fields.boolean(string='Weight'),
                #'shipment_reference': fields.boolean(string='Shipment Reference'),
                'packing_parcel_number': fields.boolean(string='Packing Parcel Number'),
                #'expedition_parcel_number': fields.boolean(string='Expedition Parcel Number'),
                'specific_information': fields.boolean(string='Specific Information'),
                'logo': fields.boolean(string='Company Logo'),
                }
    
    _defaults = {'name': 'My Customization',
                'notes': '',
                #'packing_list_reference': True,
                'pre_packing_list_reference': True,
                'destination_partner': True,
                'destination_address': True,
                'requestor_order_reference': True,
                'weight': True,
                #'shipment_reference': True,
                'packing_parcel_number': True,
                #'expedition_parcel_number': True,
                'specific_information': True,
                'logo': True,
                }

ppl_customize_label()


class stock_picking(osv.osv):
    '''
    override stock picking to add new attributes
    - flow_type: the type of flow (full, quick)
    - subtype: the subtype of picking object (picking, ppl, packing)
    - previous_step_id: the id of picking object of the previous step, picking for ppl, ppl for packing
    '''
    _inherit = 'stock.picking'
    _name = 'stock.picking'
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        unlink test for draft
        '''
        data = self.has_picking_ticket_in_progress(cr, uid, ids, context=context)
        if [x for x in data.values() if x]:
            raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try again.'))
        
        return super(stock_picking, self).unlink(cr, uid, ids, context=context)
   
    def _hook_picking_get_view(self, cr, uid, ids, context=None, *args, **kwargs):
        pick = kwargs['pick']
        obj_data = self.pool.get('ir.model.data')
        view_list = {'standard': ('stock', 'view_picking_out_form'),
                     'picking': ('msf_outgoing', 'view_picking_ticket_form'),
                     'ppl': ('msf_outgoing', 'view_ppl_form'),
                     'packing': ('msf_outgoing', 'view_packing_form'),
                     }
        if pick.type == 'out':
            module, view = view_list.get(pick.subtype,('msf_outgoing', 'view_picking_ticket_form'))
            try:
                return obj_data.get_object_reference(cr, uid, module, view)
            except ValueError, e:
                pass
        
        return super(stock_picking, self)._hook_picking_get_view(cr, uid, ids, context=context, *args, **kwargs)

    def _hook_log_picking_log_cond(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook from stock>stock.py>stock_picking>log_picking
        specify if we display a log or not
        '''
        result = super(stock_picking, self)._hook_log_picking_log_cond(cr, uid, ids, context=context, *args, **kwargs)
        pick = kwargs['pick']
        if pick.subtype == 'packing':
            return False

        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        set the name corresponding to object subtype
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        obj = self.browse(cr, uid, id, context=context)
        if not context.get('allow_copy', False):
            if obj.subtype == 'picking':
                if not obj.backorder_id:
                    # draft, new ref
                    default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket'),
                                   origin=False,
                                   date=date.today().strftime('%Y-%m-%d'),
                                   sale_id=False,
                                   )
                else:
                    # picking ticket, use draft sequence, keep other fields
                    base = obj.name
                    base = base.split('-')[0] + '-'
                    default.update(name=base + obj.backorder_id.sequence_id.get_id(test='id', context=context),
                                   date=date.today().strftime('%Y-%m-%d'),
                                   )
                    
            elif obj.subtype == 'ppl':
                raise osv.except_osv(_('Error !'), _('Pre-Packing List copy is forbidden.'))
                # ppl, use the draft picking ticket sequence
#                if obj.previous_step_id and obj.previous_step_id.backorder_id:
#                    base = obj.name
#                    base = base.split('-')[0] + '-'
#                    default.update(name=base + obj.previous_step_id.backorder_id.sequence_id.get_id(test='id', context=context))
#                else:
#                    default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'ppl'))
                
        result = super(stock_picking, self).copy(cr, uid, id, default=default, context=context)
        if not context.get('allow_copy', False):
            if obj.subtype == 'picking' and obj.backorder_id:
                # confirm the new picking ticket - the picking ticket should not stay in draft state !
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', result, 'button_confirm', cr)
                # we force availability
                self.force_assign(cr, uid, [result])
        return result
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset one2many fields
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        # reset one2many fields
        default.update(backorder_ids=[])
        default.update(previous_step_ids=[])
        default.update(pack_family_memory_ids=[])
        result = super(stock_picking, self).copy_data(cr, uid, id, default=default, context=context)
        
        return result
    
    def _erase_prodlot_hook(self, cr, uid, id, context=None, *args, **kwargs):
        '''
        hook to keep the production lot when a stock move is copied
        '''
        res = super(stock_picking, self)._erase_prodlot_hook(cr, uid, id, context=context, *args, **kwargs)
        
        return res and not context.get('keep_prodlot', False)
    
    def has_picking_ticket_in_progress(self, cr, uid, ids, context=None):
        '''
        ids is the list of draft picking object we want to test
        completed means, we recursively check that next_step link object is cancel or done
        
        return true if picking tickets are in progress, meaning picking ticket or ppl or shipment not done exist
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = []
        res = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # by default, nothing is in progress
            res[obj.id] = False
            # treat only draft picking
            assert obj.subtype == 'picking' and obj.state == 'draft', 'the validate function should only be called on draft picking ticket objects'
            for picking in obj.backorder_ids:
                # take care, is_completed returns a dictionary
                if not picking.is_completed()[picking.id]:
                    res[obj.id] = True
                    break
        
        return res
    
    def validate(self, cr, uid, ids, context=None):
        '''
        validate or not the draft picking ticket
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        
        for draft_picking in self.browse(cr, uid, ids, context=context):
            # the validate function should only be called on draft picking ticket
            assert draft_picking.subtype == 'picking' and draft_picking.state == 'draft', 'the validate function should only be called on draft picking ticket objects'
            #check the qty of all stock moves
            treat_draft = True
            move_ids = move_obj.search(cr, uid, [('picking_id', '=', draft_picking.id),
                                                 ('product_qty', '!=', 0.0),
                                                 ('state', 'not in', ['done', 'cancel'])], context=context)
            if move_ids:
                treat_draft = False
            
            if treat_draft:
                # then all child picking must be fully completed, meaning:
                # - all picking must be 'completed'
                # completed means, we recursively check that next_step link object is cancel or done
                if self.has_picking_ticket_in_progress(cr, uid, [draft_picking.id], context=context)[draft_picking.id]:
                    treat_draft = False
            
            if treat_draft:
                # - all picking are completed (means ppl completed and all shipment validated)
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', draft_picking.id, 'button_confirm', cr)
                # we force availability
                draft_picking.force_assign()
                # finish
                draft_picking.action_move()
                wf_service.trg_validate(uid, 'stock.picking', draft_picking.id, 'button_done', cr)
                
        return True
    
    def _vals_get_2(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            values = {'pack_family_memory_ids':[],
                      }
            result[stock_picking.id] = values
            
            # get the corresponding data for pack family memory
            data = self.generate_data_from_picking_for_pack_family(cr, uid, [stock_picking.id], context=context)
            # create a memory family - no shipment id
            created_ids = self.create_pack_families_memory_from_data(cr, uid, data, shipment_id=False, context=context)
            values['pack_family_memory_ids'].extend(created_ids)
                    
        return result
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            values = {'total_amount': 0.0,
                      'currency_id': False,
                      'is_dangerous_good': False,
                      'is_keep_cool': False,
                      'is_narcotic': False,
                      'num_of_packs': 0,
                      'total_weight': 0.0,
                      #'is_completed': False,
                      'overall_qty': 0.0,
                      }
            result[stock_picking.id] = values
            
            for family in stock_picking.pack_family_memory_ids:
                # number of packs from pack_family
                num_of_packs = family.num_of_packs
                values['num_of_packs'] += int(num_of_packs)
                # total_weight
                total_weight = family.total_weight
                values['total_weight'] += total_weight
                
            for move in stock_picking.move_lines:
                # total amount (float)
                total_amount = move.total_amount
                values['total_amount'] = total_amount
                # currency
                values['currency_id'] = move.currency_id and move.currency_id.id or False
                # dangerous good
                values['is_dangerous_good'] = move.is_dangerous_good
                # keep cool - if heat_sensitive_item is True
                values['is_keep_cool'] = move.is_keep_cool
                # narcotic
                values['is_narcotic'] = move.is_narcotic
                # overall qty of products in all corresponding stock moves
                values['overall_qty'] += move.product_qty
                
            # completed field - based on the previous_step_ids field, recursive call from picking to draft packing and packing
            # - picking checks that the corresponding ppl is completed
            # - ppl checks that the corresponding draft packing and packings are completed
            # the recursion stops there because packing does not have previous_step_ids values
#            completed = stock_picking.state in ('done', 'cancel')
#            if completed:
#                for next_step in stock_picking.previous_step_ids:
#                    if not next_step.is_completed:
#                        completed = False
#                        break
#                    
#            values['is_completed'] = completed
                    
        return result
    
    def is_completed(self, cr, uid, ids, context=None):
        '''
        recursive test of completion
        - to be applied on picking ticket
        
        ex:
        for picking in draft_picking.backorder_ids:
            # take care, is_completed returns a dictionary
            if not picking.is_completed()[picking.id]:
                ...balbala
        
        ***BEWARE: RETURNS A DICTIONARY !
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            # for debugging
            state = stock_picking.state
            subtype = stock_picking.subtype
            completed = stock_picking.state in ('done', 'cancel')
            result[stock_picking.id] = completed
            if completed:
                for next_step in stock_picking.previous_step_ids:
                    if not next_step.is_completed()[next_step.id]:
                        completed = False
                        result[stock_picking.id] = completed
                        break
        
        return result
    
    def init(self, cr):
        """
        Load msf_outgoing_data.xml before self
        """
        if hasattr(super(stock_picking, self), 'init'):
            super(stock_picking, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'msf_outgoing'),])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module msf_outgoing: loading data/msf_outgoing_data.xml')
            pathname = path.join('msf_outgoing', 'data/msf_outgoing_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'msf_outgoing', file, {}, mode='init', noupdate=False)
            
    def _qty_search(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of stock picking
            @return: Ids of locations
        """
        if context is None:
            context = {}
            
        stock_pickings = self.pool.get('stock.picking').search(cr, uid, [], context=context)
        # result dic
        result = {}
        for stock_picking in self.browse(cr, uid, stock_pickings, context=context):
            result[stock_picking.id] = 0.0
            for move in stock_picking.move_lines:
                result[stock_picking.id] += move.product_qty
        # construct the request
        # adapt the operator
        op = args[0][1]
        if op == '=':
            op = '=='
        ids = [('id', 'in', [x for x in result.keys() if eval("%s %s %s"%(result[x], op, args[0][2]))])]
        return ids
    
    def _get_picking_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of stock.move objects for which values have changed
        return the list of ids of picking object which need to get their state field updated
        
        self is stock.move object
        '''
        result = []
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.picking_id and obj.picking_id.id not in result:
                result.append(obj.picking_id.id)
        return result 
    
    _columns = {'flow_type': fields.selection([('full', 'Full'),('quick', 'Quick')], readonly=True, states={'draft': [('readonly', False),],}, string='Flow Type'),
                'subtype': fields.selection([('standard', 'Standard'), ('picking', 'Picking'),('ppl', 'PPL'),('packing', 'Packing')], string='Subtype'),
                'backorder_ids': fields.one2many('stock.picking', 'backorder_id', string='Backorder ids',),
                'previous_step_id': fields.many2one('stock.picking', 'Previous step'),
                'previous_step_ids': fields.one2many('stock.picking', 'previous_step_id', string='Previous Step ids',),
                'shipment_id': fields.many2one('shipment', string='Shipment'),
                'sequence_id': fields.many2one('ir.sequence', 'Picking Ticket Sequence', help="This field contains the information related to the numbering of the picking tickets.", ondelete='cascade'),
                'first_shipment_packing_id': fields.many2one('stock.picking', 'Shipment First Step'),
                #'pack_family_ids': fields.one2many('pack.family', 'ppl_id', string='Pack Families',),
                # attributes for specific packing labels
                'ppl_customize_label': fields.many2one('ppl.customize.label', string='Labels Customization',),
                # warehouse info (locations) are gathered from here - allow shipment process without sale order
                'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True,),
                # flag for converted picking
                'converted_to_standard': fields.boolean(string='Converted to Standard'),
                # functions
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals_X'), # old_multi get_vals
                'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals'),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals'),
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals'),
                'is_dangerous_good': fields.function(_vals_get, method=True, type='boolean', string='Dangerous Good', multi='get_vals'),
                'is_keep_cool': fields.function(_vals_get, method=True, type='boolean', string='Keep Cool', multi='get_vals'),
                'is_narcotic': fields.function(_vals_get, method=True, type='boolean', string='Narcotic', multi='get_vals'),
                'overall_qty': fields.function(_vals_get, method=True, fnct_search=_qty_search, type='float', string='Overall Qty', multi='get_vals',
                                               store= {'stock.move': (_get_picking_ids, ['product_qty', 'picking_id'], 10),}),
                #'is_completed': fields.function(_vals_get, method=True, type='boolean', string='Completed Process', multi='get_vals',),
                'pack_family_memory_ids': fields.function(_vals_get_2, method=True, type='one2many', relation='pack.family.memory', string='Memory Families', multi='get_vals_2',),
                }
    _defaults = {'flow_type': 'full',
                 'ppl_customize_label': lambda obj, cr, uid, c: len(obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'),], context=c)) and obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'),], context=c)[0] or False,
                 'subtype': 'standard',
                 'first_shipment_packing_id': False,
                 'warehouse_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)) and obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)[0] or False,
                 'converted_to_standard': False,
                 }
    #_order = 'origin desc, name asc'
    _order = 'name desc'
    
    def picking_ticket_data(self, cr, uid, ids, context=None):
        '''
        generate picking ticket data for report creation
        
        - sale order line without product: does not work presently
        
        - many sale order line with same product: stored in different dictionary with line id as key.
            so the same product could be displayed many times in the picking ticket according to sale order
        
        - many stock move with same product: two cases, if from different sale order lines, the above rule applies,
            if from the same order line, they will be stored according to prodlot id
            
        - many stock move with same prodlot (so same product): if same sale order line, the moves will be
            stored in the same structure, with global quantity, i.e. this batch for this product for this
            sale order line will be displayed only once with summed quantity from concerned stock moves
        
        [sale_line.id][product_id][prodlot_id]
        
        other prod lot, not used are added in order that all prod lot are displayed 
        
        to check, if a move does not come from the sale order line:
        stored with line id False, product is relevant, multiple
        product for the same 0 line id is possible
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            values = {}
            result[stock_picking.id] = {'obj': stock_picking,
                                        'lines': values,
                                        }
            for move in stock_picking.move_lines:
                if move.product_id: # product is mandatory at stock_move level ;)
                    sale_line_id = move.sale_line_id and move.sale_line_id.id or False
                    # structure, data is reorganized in order to regroup according to sale order line > product > production lot
                    # and to sum the quantities corresponding to different levels because this is impossible within the rml framework
                    values \
                        .setdefault(sale_line_id, {}) \
                        .setdefault('products', {}) \
                        .setdefault(move.product_id.id, {}) \
                        .setdefault('uoms', {}) \
                        .setdefault(move.product_uom.id, {}) \
                        .setdefault('lots', {})
                        
                    # ** sale order line info**
                    values[sale_line_id]['obj'] = move.sale_line_id or False
                    
                    # **uom level info**
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['obj'] = move.product_uom
                    
                    # **prodlot level info**
                    if move.prodlot_id:
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'].setdefault(move.prodlot_id.id, {})
                        # qty corresponding to this production lot
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id].setdefault('reserved_qty', 0)
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id]['reserved_qty'] += move.product_qty
                        # store the object for info retrieval
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id]['obj'] = move.prodlot_id
                    
                    # **product level info**
                    # total quantity from STOCK_MOVES for one sale order line (directly for one product)
                    # or if not linked to a sale order line, stock move created manually, the line id is False
                    # and in this case the product is important
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id].setdefault('qty_to_pick_sm', 0)
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['qty_to_pick_sm'] += move.product_qty
                    # total quantity from SALE_ORDER_LINES, which can be different from the one from stock moves
                    # if stock moves have been created manually in the picking, no present in the so, equal to 0 if not linked to an so
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id].setdefault('qty_to_pick_so', 0)
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['qty_to_pick_so'] += move.sale_line_id and move.sale_line_id.product_uom_qty or 0.0 
                    # store the object for info retrieval
                    values[sale_line_id]['products'][move.product_id.id]['obj'] = move.product_id
                    
            # all moves have been treated
            # complete the lot lists for each product
            for sale_line in values.values():
                for product in sale_line['products'].values():
                    for uom in product['uoms'].values():
                        # loop through all existing production lot for this product - all are taken into account, internal and external
                        for lot in product['obj'].prodlot_ids:
                            if lot.id not in uom['lots'].keys():
                                # the lot is not present, we add it
                                uom['lots'][lot.id] = {}
                                uom['lots'][lot.id]['obj'] = lot
                                # reserved qty is 0 since no stock moves correspond to this lot
                                uom['lots'][lot.id]['reserved_qty'] = 0.0
                    
        return result
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new picking
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        
        example of name: 'PICK/xxxxx'
        example of code: 'picking.xxxxx'
        example of prefix: 'PICK'
        example of padding: 5
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        
        default_name = 'Stock Picking'
        default_code = 'stock.picking'
        default_prefix = ''
        default_padding = 0
        
        if vals is None:
            vals = {}

        name = vals.get('name', False)
        if not name:
            name = default_name
        code = vals.get('code', False)
        if not code:
            code = default_code
        prefix = vals.get('prefix', False)
        if not prefix:
            prefix = default_prefix
        padding = vals.get('padding', False)
        if not padding:
            padding = default_padding

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': prefix,
            'padding': padding,
        }
        return seq_pool.create(cr, uid, seq)
    
    def generate_data_from_picking_for_pack_family(self, cr, uid, pick_ids, object_type='shipment', from_pack=False, to_pack=False, context=None):
        '''
        generate the data structure from the stock.picking object
        
        we can limit the generation to certain from/to sequence
        
        one data for each move_id - here is the difference with data generated from partial
        
        structure:
            {pick_id: {from_pack: {to_pack: {move_id: {data}}}}}
            
        if the move has a quantity equal to 0, it means that no pack are available,
        these moves are therefore not taken into account for the pack families generation
        
        TODO: integrity constraints
        
        Note: why the same dictionary is repeated n times for n moves, because
        it is directly used when we create the pack families. could be refactored
        with one dic per from/to with a 'move_ids' entry
        '''
        assert bool(from_pack) == bool(to_pack), 'from_pack and to_pack must be either both filled or empty'
        result = {}
        
        
        if object_type == 'shipment':
            # all moves are taken into account, therefore the back moves are represented
            # by done pack families
            states = ('cancel')
        elif object_type == 'memory':
            # done moves are not displayed as pf as we cannot select these packs anymore (they are returned)
            states = ('done')
        else:
            assert False, 'Should not reach this line'
        
        for pick in self.browse(cr, uid, pick_ids, context=context):
            result[pick.id] = {}
            for move in pick.move_lines:
                if not from_pack or move.from_pack == from_pack:
                    if not to_pack or move.to_pack == to_pack:
                        # the quantity must be positive and the state depends on the window's type
                        if move.product_qty and move.state not in states:
                            # subtype == ppl - called from stock picking
                            if pick.subtype == 'ppl':
                                result[pick.id] \
                                    .setdefault(move.from_pack, {}) \
                                    .setdefault(move.to_pack, {})[move.id] = {'sale_order_id': pick.sale_id.id,
                                                                              'ppl_id': pick.id, # only change between ppl - packing
                                                                              'from_pack': move.from_pack,
                                                                              'to_pack': move.to_pack,
                                                                              'pack_type': move.pack_type.id,
                                                                              'length': move.length,
                                                                              'width': move.width,
                                                                              'height': move.height,
                                                                              'weight': move.weight,
                                                                              'draft_packing_id': pick.id,
                                                                              }
                            # subtype == packing - caled from shipment
                            elif pick.subtype == 'packing':
                                result[pick.id] \
                                    .setdefault(move.from_pack, {}) \
                                    .setdefault(move.to_pack, {})[move.id] = {'sale_order_id': pick.sale_id.id,
                                                                              'ppl_id': pick.previous_step_id.id,
                                                                              'from_pack': move.from_pack,
                                                                              'to_pack': move.to_pack,
                                                                              'pack_type': move.pack_type.id,
                                                                              'length': move.length,
                                                                              'width': move.width,
                                                                              'height': move.height,
                                                                              'weight': move.weight,
                                                                              'draft_packing_id': pick.id,
                                                                              }
        
        return result
    
    def create_pack_families_memory_from_data(self, cr, uid, data, shipment_id, context=None,):
        '''
        - clear existing pack family memory objects is not necessary thanks to vaccum system
        -> in fact cleaning old memory objects reslults in a bug, because when we click on a
           pf memory to see it's form view, the shipment view is regenerated (delete the pf)
           but then the form view uses the old pf memory id for data and it crashes. Cleaning
           of previous pf memory has therefore been removed.
        - generate new ones based on data
        - return created ids
        '''
        pf_memory_obj = self.pool.get('pack.family.memory')
        # find and delete existing objects
        #ids = pf_memory_obj.search(cr, uid, [('shipment_id', '=', shipment_id),], context=context)
        #pf_memory_obj.unlink(cr, uid, ids, context=context)
        created_ids = []
        # create pack family memory
        for picking in data.values():
            for from_pack in picking.values():
                for to_pack in from_pack.values():
                    for move_id in to_pack.keys():
                        move_data = to_pack[move_id]
                    # create corresponding memory object
                    move_data.update(name='_name',
                                     shipment_id=shipment_id,)
                    id = pf_memory_obj.create(cr, uid, move_data, context=context)
                    created_ids.append(id)
        
        return created_ids
        
    def create(self, cr, uid, vals, context=None):
        '''
        creation of a stock.picking of subtype 'packing' triggers
        special behavior :
         - creation of corresponding shipment
        '''
        # objects
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)
        
        if context is None:
            context = {}
        # the action adds subtype in the context depending from which screen it is created
        if context.get('picking_screen', False) and not vals.get('name', False):
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket')
            vals.update(subtype='picking',
                        backorder_id=False,
                        name=pick_name,
                        flow_type='full',
                        )
        
        if context.get('ppl_screen', False) and not vals.get('name', False):
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'ppl')
            vals.update(subtype='ppl',
                        backorder_id=False,
                        name=pick_name,
                        flow_type='full',
                        )
        # shipment object
        shipment_obj = self.pool.get('shipment')
        # move object
        move_obj = self.pool.get('stock.move')
        
        # sequence creation
        # if draft picking
        if 'subtype' in vals and vals['subtype'] == 'picking':
            # creation of a new picking ticket
            assert 'backorder_id' in vals, 'No backorder_id'
            
            if not vals['backorder_id']:
                # creation of *draft* picking ticket
                vals.update(sequence_id=self.create_sequence(cr, uid, {'name':vals['name'],
                                                                       'code':vals['name'],
                                                                       'prefix':'',
                                                                       'padding':2}, context=context))
                
        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'backorder_id' in vals, 'No backorder_id'
            assert 'shipment_id' in vals, 'No shipment_id'
            
            if not vals['backorder_id']:
                # creation of *draft* picking ticket
                vals.update(sequence_id=self.create_sequence(cr, uid, {'name':vals['name'],
                                                                       'code':vals['name'],
                                                                       'prefix':'',
                                                                       'padding':2,
                                                                       }, context=context))
        
        # create packing object
        new_packing_id = super(stock_picking, self).create(cr, uid, vals, context=context)
        
        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'backorder_id' in vals, 'No backorder_id'
            assert 'shipment_id' in vals, 'No shipment_id'
            
            if vals['backorder_id'] and vals['shipment_id']:
                # ship of existing shipment
                # no new shipment
                # TODO
                return new_packing_id
            
            if vals['backorder_id'] and not vals['shipment_id']:
                # data from do_create_shipment method
                assert 'partial_datas_shipment' in context, 'Missing partial_datas_shipment'
                assert 'draft_shipment_id' in context, 'Missing draft_shipment_id'
                assert 'draft_packing_id' in context, 'Missing draft_packing_id'
                assert 'shipment_id' in context, 'Missing shipment_id'
                draft_shipment_id = context['draft_shipment_id']
                draft_packing_id = context['draft_packing_id']
                data = context['partial_datas_shipment'][draft_shipment_id][draft_packing_id]
                shipment_id = context['shipment_id']
                # We have a backorder_id, no shipment_id
                # -> we have just created a shipment
                # the created packing object has no stock_move
                # - we create the sock move from the data in context
                # - if no shipment in context, create a new shipment object
                # - generate the data from the new picking object
                # - create the pack families
                for from_pack in data:
                    for to_pack in data[from_pack]:
                        # total number of packs
                        total_num = to_pack - from_pack + 1
                        # number of selected packs to ship
                        # note: when the data is generated, lines without selected_number are not kept, so we have nothing to check here
                        selected_number = data[from_pack][to_pack][0]['selected_number']
                        # we take the packs with the highest numbers
                        # new moves
                        selected_from_pack = to_pack - selected_number + 1
                        selected_to_pack = to_pack
                        # update initial moves
                        if selected_number == total_num:
                            # if all packs have been selected, from/to are set to 0
                            initial_from_pack = 0
                            initial_to_pack = 0
                        else:
                            initial_from_pack = from_pack
                            initial_to_pack = to_pack - selected_number
                        
                        # find the corresponding moves
                        moves_ids = move_obj.search(cr, uid, [('picking_id', '=', draft_packing_id),
                                                              ('from_pack', '=', from_pack),
                                                              ('to_pack', '=', to_pack),], context=context)
                        
                        for move in move_obj.browse(cr, uid, moves_ids, context=context):
                            # we compute the selected quantity
                            selected_qty = move.qty_per_pack * selected_number
                            # create the new move - store the back move from draft **packing** object
                            new_move = move_obj.copy(cr, uid, move.id, {'picking_id': new_packing_id,
                                                                        'product_qty': selected_qty,
                                                                        'from_pack': selected_from_pack,
                                                                        'to_pack': selected_to_pack,
                                                                        'backmove_packing_id': move.id,}, context=context)
                            
                            # update corresponding initial move
                            initial_qty = move.product_qty
                            initial_qty = max(initial_qty - selected_qty, 0)
                            # if all packs have been selected, from/to have been set to 0
                            # update the original move object - the corresponding original shipment (draft)
                            # is automatically updated generically in the write method
                            move_obj.write(cr, uid, [move.id], {'product_qty': initial_qty,
                                                                'from_pack': initial_from_pack,
                                                                'to_pack': initial_to_pack}, context=context)
            
            if not vals['backorder_id']:
                # creation of packing after ppl validation
                # find an existing shipment or create one - depends on new pick state
                shipment_ids = shipment_obj.search(cr, uid, [('state', '=', 'draft'), ('address_id', '=', vals['address_id'])], context=context)
                # only one 'draft' shipment should be available
                assert len(shipment_ids) in (0, 1), 'Only one draft shipment should be available for a given address at a time - %s'%len(shipment_ids)
                # get rts of corresponding sale order
                sale_id = self.read(cr, uid, [new_packing_id], ['sale_id'], context=context)
                sale_id = sale_id[0]['sale_id']
                if sale_id:
                    sale_id = sale_id[0]
                    # today
                    today = time.strftime(db_datetime_format)
                    rts = self.pool.get('sale.order').read(cr, uid, [sale_id], ['ready_to_ship_date'], context=context)[0]['ready_to_ship_date']
                else:
                    rts = date.today().strftime(db_date_format)
                # rts + shipment lt
                shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                rts_obj = datetime.strptime(rts, db_date_format)
                rts = rts_obj + relativedelta(days=shipment_lt or 0)
                rts = rts.strftime(db_date_format)
                
                if not len(shipment_ids):
                    # no shipment, create one - no need to specify the state, it's a function
                    name = self.pool.get('ir.sequence').get(cr, uid, 'shipment')
                    addr = self.pool.get('res.partner.address').browse(cr, uid, vals['address_id'], context=context)
                    partner_id = addr.partner_id and addr.partner_id.id or False
                    values = {'name': name,
                              'address_id': vals['address_id'],
                              'partner_id2': partner_id,
                              'shipment_expected_date': rts,
                              'shipment_actual_date': rts,
                              'sequence_id': self.create_sequence(cr, uid, {'name':name,
                                                                            'code':name,
                                                                            'prefix':'',
                                                                            'padding':2}, context=context)}
                    
                    shipment_id = shipment_obj.create(cr, uid, values, context=context)
                    shipment_obj.log(cr, uid, shipment_id, _('The new Draft Shipment %s has been created.')%(name,))
                else:
                    shipment_id = shipment_ids[0]
                    shipment = shipment_obj.browse(cr, uid, shipment_id, context=context)
                    # if expected ship date of shipment is greater than rts, update shipment_expected_date and shipment_actual_date
                    shipment_expected = datetime.strptime(shipment.shipment_expected_date, db_datetime_format)
                    if rts_obj < shipment_expected:
                        shipment.write({'shipment_expected_date': rts, 'shipment_actual_date': rts,}, context=context)
                    shipment_name = shipment.name
                    shipment_obj.log(cr, uid, shipment_id, _('The ppl has been added to the existing Draft Shipment %s.')%(shipment_name,))
            
            # update the new pick with shipment_id
            self.write(cr, uid, [new_packing_id], {'shipment_id': shipment_id}, context=context)
            
        return new_packing_id

    def _hook_action_assign_raise_exception(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_assign method from stock>stock.py>stock_picking class
        
        - allow to choose wether or not an exception should be raised in case of no stock move
        '''
        res = super(stock_picking, self)._hook_action_assign_raise_exception(cr, uid, ids, context=context, *args, **kwargs)
        return res and False
    
    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        stock>stock.py>log_picking
        update the message to be displayed by the function
        '''
        pick = kwargs['pick']
        message = kwargs['message']
        # if the picking is converted to standard, and state is confirmed
        if pick.converted_to_standard and pick.state == 'confirmed':
            return 'The Preparation Picking has been converted to simple Out. ' + message
        return super(stock_picking, self)._hook_log_picking_modify_message(cr, uid, ids, context, *args, **kwargs)
    
    def convert_to_standard(self, cr, uid, ids, context=None):
        '''
        check of back orders exists, if not, convert to standard: change subtype to standard, and trigger workflow
        
        only one picking object at a time
        '''
        # objects
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        
        for obj in self.browse(cr, uid, ids, context=context):
            # the convert function should only be called on draft picking ticket
            assert obj.subtype == 'picking' and obj.state == 'draft', 'the convert function should only be called on draft picking ticket objects'
            if self.has_picking_ticket_in_progress(cr, uid, [obj.id], context=context)[obj.id]:
                    raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try again.'))
            
            # log a message concerning the conversion
            new_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
            self.log(cr, uid, obj.id, _('The Preparation Picking (%s) has been converted to simple Out (%s).')%(obj.name, new_name))
            # change subtype and name
            obj.write({'name': new_name,
                       'subtype': 'standard',
                       'converted_to_standard': True,
                       }, context=context)
            # all destination location of the stock moves must be output location of warehouse - lot_output_id
            # if corresponding sale order, date and date_expected are updated to rts + shipment lt
            for move in obj.move_lines:
                # was previously set to confirmed/assigned, otherwise, when we confirm the stock picking,
                # using draft_force_assign, the moves are not treated because not in draft
                # and the corresponding chain location on location_dest_id was not computed
                # we therefore set them back in draft state before treatment
                vals = {'state': 'draft'}
                # If the move comes from a DPO, don't change the destination location
                if not move.dpo_id:
                    vals.update({'location_dest_id': obj.warehouse_id.lot_output_id.id})

                if obj.sale_id:
                    # compute date
                    shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                    rts = datetime.strptime(obj.sale_id.ready_to_ship_date, db_date_format)
                    rts = rts + relativedelta(days=shipment_lt or 0)
                    rts = rts.strftime(db_date_format)
                    vals.update({'date': rts, 'date_expected': rts, 'state': 'draft'})
                move.write(vals, context=context)

            # trigger workflow
            self.draft_force_assign(cr, uid, [obj.id])
        
            # TODO which behavior
            data_obj = self.pool.get('ir.model.data')
            view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
            view_id = view_id and view_id[1] or False
            # display newly created picking ticket
            return {'name':_("Delivery Orders"),
                    'view_mode': 'form,tree',
                    'view_id': [view_id],
                    'view_type': 'form',
                    'res_model': 'stock.picking',
                    'res_id': obj.id,
                    'type': 'ir.actions.act_window',
                    'target': 'crush',
                    }
    
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
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)

    def do_create_picking_first_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update new_move data. Originally: to complete msf_cross_docking module
        '''
        values = kwargs.get('values')
        assert values is not None, 'missing defaults'
        
        return values

    def do_create_picking(self, cr, uid, ids, context=None):
        '''
        create the picking ticket from selected stock moves
        '''
        assert context, 'context is not defined'
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']
        
        # stock move object
        move_obj = self.pool.get('stock.move')
        
        for pick in self.browse(cr, uid, ids, context=context):
            # create the new picking object
            # a sequence for each draft picking ticket is used for the picking ticket
            sequence = pick.sequence_id
            ticket_number = sequence.get_id(test='id', context=context)
            new_pick_id = self.copy(cr, uid, pick.id, {'name': (pick.name or 'NoName/000') + '-' + ticket_number,
                                                       'backorder_id': pick.id,
                                                       'move_lines': []}, context=dict(context, allow_copy=True,))
            # create stock moves corresponding to partial datas
            # for now, each new line from the wizard corresponds to a new stock.move
            # it could be interesting to regroup according to production lot/asset id
            move_ids = partial_datas[pick.id].keys()
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                # qty selected
                count = 0
                # initial qty
                initial_qty = move.product_qty
                for partial in partial_datas[pick.id][move.id]:
                    # integrity check
                    assert partial['product_id'] == move.product_id.id, 'product id is wrong, %s - %s'%(partial['product_id'], move.product_id.id)
                    assert partial['product_uom'] == move.product_uom.id, 'product uom is wrong, %s - %s'%(partial['product_uom'], move.product_uom.id)
                    # the quantity
                    count = count + partial['product_qty']
                    # copy the stock move and set the quantity
                    values = {'picking_id': new_pick_id,
                              'product_qty': partial['product_qty'],
                              'prodlot_id': partial['prodlot_id'],
                              'asset_id': partial['asset_id'],
                              'composition_list_id': partial['composition_list_id'],
                              'backmove_id': move.id}
                    #add hook
                    values = self.do_create_picking_first_hook(cr, uid, ids, context=context, partial_datas=partial_datas, values=values, move=move)
                    new_move = move_obj.copy(cr, uid, move.id, values, context=context)
                    
                # decrement the initial move, cannot be less than zero
                initial_qty = max(initial_qty - count, 0)
                move_obj.write(cr, uid, [move.id], {'product_qty': initial_qty}, context=context)
                
            # confirm the new picking ticket
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', new_pick_id, 'button_confirm', cr)
            # we force availability
            self.force_assign(cr, uid, [new_pick_id])
        
        # TODO which behavior
        #return {'type': 'ir.actions.act_window_close'}
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')
        view_id = view_id and view_id[1] or False
        # display newly created picking ticket
        return {'name':_("Picking Ticket"),
                'view_mode': 'form,tree',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'stock.picking',
                'res_id': pick.id,
                'type': 'ir.actions.act_window',
                'target': 'crush',
                }
        
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
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)

    def do_validate_picking_first_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update new_move data. Originally: to complete msf_cross_docking module
        '''
        values = kwargs.get('values')
        assert values is not None, 'missing defaults'
        
        return values

    def do_validate_picking(self, cr, uid, ids, context=None):
        '''
        validate the picking ticket from selected stock moves
        
        move here the logic of validate picking
        available for picking loop
        '''
        assert context, 'context is not defined'
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']
        
        # objects
        date_tools = self.pool.get('date.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        today = time.strftime(db_date_format)
        
        # stock move object
        move_obj = self.pool.get('stock.move')
        # create picking object
        create_picking_obj = self.pool.get('create.picking')
        
        for pick in self.browse(cr, uid, ids, context=context):
            # create stock moves corresponding to partial datas
            move_ids = partial_datas[pick.id].keys()
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                # qty selected
                count = 0
                # flag to update the first move - if split was performed during the validation, new stock moves are created
                first = True
                # initial qty
                initial_qty = move.product_qty
                for partial in partial_datas[pick.id][move.id]:
                    # integrity check
                    assert partial['product_id'] == move.product_id.id, 'product id is wrong, %s - %s'%(partial['product_id'], move.product_id.id)
                    assert partial['product_uom'] == move.product_uom.id, 'product uom is wrong, %s - %s'%(partial['product_uom'], move.product_uom.id)
                    # the quantity
                    count = count + partial['product_qty']
                    if first:
                        first = False
                        # update existing move
                        values = {'product_qty': partial['product_qty'],
                                  'prodlot_id': partial['prodlot_id'],
                                  'composition_list_id': partial['composition_list_id'],
                                  'asset_id': partial['asset_id']}
                        values = self.do_validate_picking_first_hook(cr, uid, ids, context=context, partial_datas=partial_datas, values=values, move=move)
                        move_obj.write(cr, uid, [move.id], values, context=context)
                    else:
                        # split happend during the validation
                        # copy the stock move and set the quantity
                        values = {'state': 'assigned',
                                  'product_qty': partial['product_qty'],
                                  'prodlot_id': partial['prodlot_id'],
                                  'composition_list_id': partial['composition_list_id'],
                                  'asset_id': partial['asset_id']}
                        values = self.do_validate_picking_first_hook(cr, uid, ids, context=context, partial_datas=partial_datas, values=values, move=move)
                        new_move = move_obj.copy(cr, uid, move.id, values, context=context)
                # decrement the initial move, cannot be less than zero
                diff_qty = initial_qty - count
                # the quantity after the validation does not correspond to the picking ticket quantity
                # the difference is written back to draft picking ticket
                # is positive if some qty was removed during the validation -> draft qty is increased
                # is negative if some qty was added during the validation -> draft qty is decreased
                if diff_qty != 0:
                    backorder_id = pick.backorder_id.id
                    assert backorder_id, 'No backorder defined.'
                    original_moves = move_obj.search(cr, uid, [('picking_id', '=', backorder_id),
                                                               ('product_id', '=', move.product_id.id),
                                                               ('product_uom', '=', move.product_uom.id)])
                    # original move from the draft picking ticket which will be updated
                    original_move = move.backmove_id
                    assert len(original_moves) == 1, 'No corresponding stock_move have been found in draft picking ticket for product %s and UOM %s'%(move.product_id.name, move.product_uom.name)
                    backorder_qty = move_obj.read(cr, uid, [original_move.id], ['product_qty'], context=context)[0]['product_qty']
                    backorder_qty = max(backorder_qty + diff_qty, 0)
                    move_obj.write(cr, uid, [original_move.id], {'product_qty': backorder_qty}, context=context)

            # create the new ppl object
            ppl_number = pick.name.split("/")[1]
            # we want the copy to keep the production lot reference from picking ticket to pre-packing list
            new_ppl_id = self.copy(cr, uid, pick.id, {'name': 'PPL/' + ppl_number,
                                                      'subtype': 'ppl',
                                                      'previous_step_id': pick.id,
                                                      'backorder_id': False}, context=dict(context, keep_prodlot=True, allow_copy=True,))
            new_ppl = self.browse(cr, uid, new_ppl_id, context=context)
            # update locations of stock moves - if the move quantity is equal to zero, the stock move is removed
            for move in new_ppl.move_lines:
                if move.product_qty:
                    move_obj.write(cr, uid, [move.id], {'initial_location': move.location_id.id,
                                                        'location_id': move.location_dest_id.id,
                                                        'location_dest_id': new_ppl.warehouse_id.lot_dispatch_id.id,
                                                        'date': today,
                                                        'date_expected': today,}, context=context)
                else:
                    move_obj.unlink(cr, uid, [move.id], context=context)
            
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', new_ppl_id, 'button_confirm', cr)
            # simulate check assign button, as stock move must be available
            self.force_assign(cr, uid, [new_ppl_id])
            # trigger standard workflow for validated picking ticket
            self.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
            
            # if the flow type is in quick mode, we perform the ppl steps automatically
            if pick.flow_type == 'quick':
                create_picking_obj.quick_mode(cr, uid, new_ppl, context=context)
        
        # TODO which behavior
        #return {'type': 'ir.actions.act_window_close'}
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')
        view_id = view_id and view_id[1] or False
        # display newly created picking ticket
        return {'name':_("Picking Ticket"),
                'view_mode': 'form,tree',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'stock.picking',
                'res_id': pick.id,
                'type': 'ir.actions.act_window',
                'target': 'crush',
                }

    def ppl(self, cr, uid, ids, context=None):
        '''
        pack the ppl - open the ppl step1 wizard
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        # data
        name = _("PPL Information - step1")
        model = 'create.picking'
        step = 'ppl1'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_ppl1(self, cr, uid, ids, context=None):
        '''
        - receives generated data from ppl in context
        - call action to ppl2 step with partial_datas_ppl1 in context
        - ids are the picking ids
        '''
        # we need the context for the wizard switch
        assert context, 'No context defined'
            
        # data
        name = _("PPL Information - step2")
        model = 'create.picking'
        step = 'ppl2'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_ppl2(self, cr, uid, ids, context=None):
        '''
        finalize the ppl logic
        '''
        # integrity check
        assert context, 'context not defined'
        assert 'partial_datas_ppl1' in context, 'partial_datas_ppl1 no defined in context'
        
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        # data from wizard
        partial_datas_ppl = context['partial_datas_ppl1']
        # picking ids from ids must be equal to picking ids from partial datas
        assert set(ids) == set(partial_datas_ppl.keys()), 'picking ids from ids and partial do not match'
        
        # update existing stock moves - create new one if split occurred
        # for each pick
        for pick in self.browse(cr, uid, ids, context=context):
            # integrity check on move_ids - moves ids from picking and partial must be the same
            # dont take into account done moves, which represents returned products
            from_pick = [move.id for move in pick.move_lines if move.state in ('confirmed', 'assigned')]
            from_partial = []
            # the list of updated stock.moves
            # if a stock.move is updated, the next time a new move is created
            updated = {}
            # load moves data
            # browse returns a list of browse object in the same order as from_partial
            browse_moves = move_obj.browse(cr, uid, from_pick, context=context)
            moves = dict(zip(from_pick, browse_moves))
            # loop through data
            for from_pack in partial_datas_ppl[pick.id]:
                for to_pack in partial_datas_ppl[pick.id][from_pack]:
                    for move in partial_datas_ppl[pick.id][from_pack][to_pack]:
                        # integrity check
                        from_partial.append(move)
                        for partial in partial_datas_ppl[pick.id][from_pack][to_pack][move]:
                            # {'asset_id': False, 'weight': False, 'product_id': 77, 'product_uom': 1, 'pack_type': False, 'length': False, 'to_pack': 1, 'height': False, 'from_pack': 1, 'prodlot_id': False, 'qty_per_pack': 18.0, 'product_qty': 18.0, 'width': False, 'move_id': 179}
                            # integrity check
                            assert partial['product_id'] == moves[move].product_id.id
                            assert partial['asset_id'] == moves[move].asset_id.id
                            assert partial['composition_list_id'] == moves[move].composition_list_id.id
                            assert partial['product_uom'] == moves[move].product_uom.id
                            assert partial['prodlot_id'] == moves[move].prodlot_id.id
                            # dictionary of new values, used for creation or update
                            # - qty_per_pack is a function at stock move level
                            fields = ['product_qty', 'from_pack', 'to_pack', 'pack_type', 'length', 'width', 'height', 'weight']
                            values = dict(zip(fields, [partial["%s"%x] for x in fields]))
                            
                            if move in updated:
                                # if already updated, we create a new stock.move
                                updated[move]['partial_qty'] += partial['product_qty']
                                # force state to 'assigned'
                                values.update(state='assigned')
                                # copy stock.move with new product_qty, qty_per_pack. from_pack, to_pack, pack_type, length, width, height, weight
                                move_obj.copy(cr, uid, move, values, context=context)
                            else:
                                # update the existing stock move
                                updated[move] = {'initial': moves[move].product_qty, 'partial_qty': partial['product_qty']}
                                move_obj.write(cr, uid, [move], values, context=context)
        
            # integrity check - all moves are treated and no more
            assert set(from_pick) == set(from_partial), 'move_ids are not equal pick:%s - partial:%s'%(set(from_pick), set(from_partial))
            # quantities are right
            assert all([updated[m]['initial'] == updated[m]['partial_qty'] for m in updated.keys()]), 'initial quantity is not equal to the sum of partial quantities (%s).'%(updated)
            # copy to 'packing' stock.picking
            # draft shipment is automatically created or updated if a shipment already
            pack_number = pick.name.split("/")[1]
            new_packing_id = self.copy(cr, uid, pick.id, {'name': 'PACK/' + pack_number,
                                                          'subtype': 'packing',
                                                          'previous_step_id': pick.id,
                                                          'backorder_id': False,
                                                          'shipment_id': False}, context=dict(context, keep_prodlot=True, allow_copy=True,))

            self.write(cr, uid, [new_packing_id], {'origin': pick.origin}, context=context)
            # update locations of stock moves and state as the picking stay at 'draft' state.
            # if return move have been done in previous ppl step, we remove the corresponding copied move (criteria: qty_per_pack == 0)
            new_packing = self.browse(cr, uid, new_packing_id, context=context)
            for move in new_packing.move_lines:
                if move.qty_per_pack == 0:
                    move_obj.unlink(cr, uid, [move.id], context=context)
                else:
                    move.write({'state': 'assigned',
                                'location_id': new_packing.warehouse_id.lot_dispatch_id.id,
                                'location_dest_id': new_packing.warehouse_id.lot_distribution_id.id}, context=context)
            
            # trigger standard workflow
            self.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
        
        # TODO which behavior
        #return {'type': 'ir.actions.act_window_close'}
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_ppl_form')
        view_id = view_id and view_id[1] or False
        # display newly created picking ticket
        return {'name':_("Pre-Packing List"),
                'view_mode': 'form,tree',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'stock.picking',
                'res_id': pick.id,
                'type': 'ir.actions.act_window',
                'target': 'crush',
                }
    
    def return_products(self, cr, uid, ids, context=None):
        '''
        open the return products wizard
        '''
        # we need the context
        if context is None:
            context = {}
            
        # data
        name = _("Return Products")
        model = 'create.picking'
        step = 'returnproducts'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
    
    def do_return_products(self, cr, uid, ids, context=None):
        '''
        - update the ppl
        - update the draft picking ticket
        - create the back move
        '''
        # integrity check
        assert context, 'context not defined'
        assert 'partial_datas' in context, 'partial_datas no defined in context'
        partial_datas = context['partial_datas']
        
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        
        for picking in self.browse(cr, uid, ids, context=context):
            # for each picking
            # corresponding draft picking ticket
            draft_picking_id = picking.previous_step_id.backorder_id.id
            
            for move in move_obj.browse(cr, uid, partial_datas[picking.id].keys(), context=context):
                # we browse the updated moves (return qty > 0 is checked during data generation)
                # data from wizard
                data = partial_datas[picking.id][move.id]

                # qty to return
                return_qty = data['qty_to_return']
                # initial qty is decremented
                initial_qty = move.product_qty
                initial_qty = max(initial_qty - return_qty, 0)
                values = {'product_qty': initial_qty}
                
                if not initial_qty:
                    # if all products are sent back to stock, the move state is cancel - done for now, ideologic question, wahouuu!
                    #values.update({'state': 'cancel'})
                    values.update({'state': 'done'})
                move_obj.write(cr, uid, [move.id], values, context=context)
                
                # create a back move with the quantity to return to the good location
                # the good location is stored in the 'initial_location' field
                move_obj.copy(cr, uid, move.id, {'product_qty': return_qty,
                                                 'location_dest_id': move.initial_location.id,
                                                 'state': 'done'})
                
                # increase the draft move with the move quantity
                draft_move_id = move.backmove_id.id
                draft_initial_qty = move_obj.read(cr, uid, [draft_move_id], ['product_qty'], context=context)[0]['product_qty']
                draft_initial_qty += return_qty
                move_obj.write(cr, uid, [draft_move_id], {'product_qty': draft_initial_qty}, context=context)
                
            # log the increase action - display the picking ticket view form
            # TODO refactoring needed
            obj_data = self.pool.get('ir.model.data')
            res = obj_data.get_object_reference(cr, uid, 'msf_outgoing', 'view_ppl_form')[1]
            self.log(cr, uid, picking.id, _("Products from Pre-Packing List (%s) have been returned to stock.")%(picking.name,), context={'view_id': res,})
            res = obj_data.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1]
            self.log(cr, uid, draft_picking_id, _("The corresponding Draft Picking Ticket (%s) has been updated.")%(picking.previous_step_id.backorder_id.name,), context={'view_id': res,})
            # if all moves are done or canceled, the ppl is canceled
            cancel_ppl = True
            for move in picking.move_lines:
                if move.state in ('assigned'):
                    cancel_ppl = False
            
            if cancel_ppl:
                # we dont want the back move (done) to be canceled - so we dont use the original cancel workflow state because
                # action_cancel() from stock_picking would be called, this would cancel the done stock_moves
                # instead we move to the new return_cancel workflow state which simply set the stock_picking state to 'cancel'
                # TODO THIS DOESNT WORK - still done state - replace with trigger for now
                #wf_service.trg_validate(uid, 'stock.picking', picking.id, 'return_cancel', cr)
                wf_service.trg_write(uid, 'stock.picking', picking.id, cr)
                
        # TODO which behavior
        #return {'type': 'ir.actions.act_window_close'}
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_ppl_form')
        view_id = view_id and view_id[1] or False
        # display newly created picking ticket
        return {
            'name':_("Pre-Packing List"),
            'view_mode': 'form,tree',
            'view_id': [view_id],
            'view_type': 'form',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'type': 'ir.actions.act_window',
            'target': 'crush',
        }
    
    def action_cancel(self, cr, uid, ids, context=None):
        '''
        override cancel state action from the workflow
        
        - depending on the subtype and state of the stock.picking object
          the behavior will be different
        
        Cancel button is active for the picking object:
        - subtype: 'picking'
        Cancel button is active for the shipment object:
        - subtype: 'packing'
        
        state is not taken into account as picking is canceled before
        '''
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        obj_data = self.pool.get('ir.model.data')
        
        # check the state of the picking
        for picking in self.browse(cr, uid, ids, context=context):
            # if draft and shipment is in progress, we cannot cancel
            if picking.subtype == 'picking' and picking.state in ('draft',):
                if self.has_picking_ticket_in_progress(cr, uid, [picking.id], context=context)[picking.id]:
                    raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try to cancel again.'))
                return super(stock_picking, self).action_cancel(cr, uid, ids, context=context)
            # if not draft or qty does not match, the shipping is already in progress
            if picking.subtype == 'picking' and picking.state in ('done',):
                raise osv.except_osv(_('Warning !'), _('The shipment process is completed and cannot be canceled!'))
        
        # first call to super method, so if some checks fail won't perform other actions anyway
        # call super - picking is canceled
        super(stock_picking, self).action_cancel(cr, uid, ids, context=context)
        
        for picking in self.browse(cr, uid, ids, context=context):
                
            if picking.subtype == 'picking':
                # for each picking
                # get the draft picking
                draft_picking_id = picking.backorder_id.id
                
                # for each move from picking ticket - could be split moves
                for move in picking.move_lines:
                    # find the corresponding move in draft
                    draft_move = move.backmove_id
                    # increase the draft move with the move quantity
                    initial_qty = move_obj.read(cr, uid, [draft_move.id], ['product_qty'], context=context)[0]['product_qty']
                    initial_qty += move.product_qty
                    move_obj.write(cr, uid, [draft_move.id], {'product_qty': initial_qty}, context=context)
                    # log the increase action
                    # TODO refactoring needed
                    obj_data = self.pool.get('ir.model.data')
                    res = obj_data.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1]
                    self.log(cr, uid, draft_picking_id, _("The corresponding Draft Picking Ticket (%s) has been updated.")%(picking.backorder_id.name,), context={'view_id': res,})
                    
            if picking.subtype == 'packing':
                # for each packing we get the draft packing
                draft_packing_id = picking.backorder_id.id
                
                # for each move from the packing
                for move in picking.move_lines:
                    # corresponding draft move from draft **packing** object
                    draft_move_id = move.backmove_packing_id.id
                    # check the to_pack of draft move
                    # if equal to draft to_pack = move from_pack - 1 (as we always take the pack with the highest number available)
                    # we can increase the qty and update draft to_pack
                    # otherwise we copy the draft packing move with updated quantity and from/to
                    # we always create a new move
                    draft_read = move_obj.read(cr, uid, [draft_move_id], ['product_qty', 'to_pack'], context=context)[0]
                    draft_to_pack = draft_read['to_pack']
                    if draft_to_pack + 1 == move.from_pack and False: # DEACTIVATED
                        # updated quantity
                        draft_qty = draft_read['product_qty'] + move.product_qty
                        # update the draft move
                        move_obj.write(cr, uid, [draft_move_id], {'product_qty': draft_qty, 'to_pack': move.to_pack}, context=context)
                    else:
                        # copy draft move (to be sure not to miss original info) with move qty and from/to
                        move_obj.copy(cr, uid, draft_move_id, {'product_qty': move.product_qty,
                                                               'from_pack': move.from_pack,
                                                               'to_pack': move.to_pack,
                                                               'state': 'assigned'}, context=context)
        
        return True
            
stock_picking()


class wizard(osv.osv):
    '''
    class offering open_wizard method for wizard control
    '''
    _name = 'wizard'
    
    def open_wizard(self, cr, uid, ids, name=False, model=False, step='default', type='create', context=None):
        '''
        WARNING : IDS CORRESPOND TO ***MAIN OBJECT IDS*** (picking for example) take care when calling the method from wizards
        return the newly created wizard's id
        name, model, step are mandatory only for type 'create'
        '''
        if context is None:
            context = {}
        
        if type == 'create':
            assert name, 'type "create" and no name defined'
            assert model, 'type "create" and no model defined'
            assert step, 'type "create" and no step defined'
            # create the memory object - passing the picking id to it through context
            wizard_id = self.pool.get(model).create(
                cr, uid, {}, context=dict(context,
                                          active_ids=ids,
                                          model=model,
                                          step=step,
                                          back_model=context.get('model', False),
                                          back_wizard_ids=context.get('wizard_ids', False),
                                          back_wizard_name=context.get('wizard_name', False),
                                          back_step=context.get('step', False),
                                          wizard_name=name))
        
        elif type == 'back':
            # open the previous wizard
            assert context['back_wizard_ids'], 'no back_wizard_ids defined'
            wizard_id = context['back_wizard_ids'][0]
            assert context['back_wizard_name'], 'no back_wizard_name defined'
            name = context['back_wizard_name']
            assert context['back_model'], 'no back_model defined'
            model = context['back_model']
            assert context['back_step'], 'no back_step defined'
            step = context['back_step']
            
        elif type == 'update':
            # refresh the same wizard
            assert context['wizard_ids'], 'no wizard_ids defined'
            wizard_id = context['wizard_ids'][0]
            assert context['wizard_name'], 'no wizard_name defined'
            name = context['wizard_name']
            assert context['model'], 'no model defined'
            model = context['model']
            assert context['step'], 'no step defined'
            step = context['step']
            
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
                            model=model,
                            step=step,
                            back_model=context.get('model', False),
                            back_wizard_ids=context.get('wizard_ids', False),
                            back_wizard_name=context.get('wizard_name', False),
                            back_step=context.get('step', False),
                            wizard_name=name)
        }
    
wizard()


class product_product(osv.osv):
    '''
    add a getter for keep cool notion
    '''
    _inherit = 'product.product'
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for product in self.browse(cr, uid, ids, context=context):
            values = {'is_keep_cool': False,
                      }
            result[product.id] = values
            # keep cool
            is_keep_cool = bool(product.heat_sensitive_item)# in ('*', '**', '***',)
            values['is_keep_cool'] = is_keep_cool
                    
        return result
    
    _columns = {'is_keep_cool': fields.function(_vals_get, method=True, type='boolean', string='Keep Cool', multi='get_vals',),
                'prodlot_ids': fields.one2many('stock.production.lot', 'product_id', string='Batch Numbers',),
                }
    
product_product()


class stock_move(osv.osv):
    '''
    stock move
    '''
    _inherit = 'stock.move'
    
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
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for move in self.browse(cr, uid, ids, context=context):
            values = {'qty_per_pack': 0.0,
                      'total_amount': 0.0,
                      'amount': 0.0,
                      'currency_id': False,
                      'num_of_packs': 0,
                      'is_dangerous_good': False,
                      'is_keep_cool': False,
                      'is_narcotic': False,
                      'sale_order_line_number': 0,
                      }
            result[move.id] = values
            # number of packs with from/to values (integer)
            if move.to_pack == 0:
                num_of_packs = 0
            else:
                num_of_packs = move.to_pack - move.from_pack + 1
            values['num_of_packs'] = num_of_packs
            # quantity per pack
            if num_of_packs:
                values['qty_per_pack'] = move.product_qty / num_of_packs
            else:
                values['qty_per_pack'] = 0
            # total amount (float)
            total_amount = move.sale_line_id and move.sale_line_id.price_unit * move.product_qty or 0.0
            values['total_amount'] = total_amount
            # amount for one pack
            if num_of_packs:
                amount = total_amount / num_of_packs
            else:
                amount = 0
            values['amount'] = amount
            # currency
            values['currency_id'] = move.sale_line_id and move.sale_line_id.currency_id and move.sale_line_id.currency_id.id or False
            # dangerous good
            values['is_dangerous_good'] = move.product_id and move.product_id.dangerous_goods or False
            # keep cool - if heat_sensitive_item is True
            values['is_keep_cool'] = bool(move.product_id and move.product_id.heat_sensitive_item or False)
            # narcotic
            values['is_narcotic'] = move.product_id and move.product_id.narcotic or False
            # sale_order_line_number
            values['sale_order_line_number'] = move.sale_line_id and move.sale_line_id.line_number or 0
                    
        return result
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Set default values according to type and subtype
        '''
        if not context:
            context = {}
            
        res = super(stock_move, self).default_get(cr, uid, fields, context=context)
        
        if 'warehouse_id' in context and context.get('warehouse_id'):
            warehouse_id = context.get('warehouse_id')
        else:
            warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)[0]
        res.update({'location_output_id': self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_output_id.id})
        
        loc_virtual_ids = self.pool.get('stock.location').search(cr, uid, [('name', '=', 'Virtual Locations')])
        loc_virtual_id = len(loc_virtual_ids) > 0 and loc_virtual_ids[0] or False
        res.update({'location_virtual_id': loc_virtual_id})
        
        if 'type' in context and context.get('type', False) == 'out':
            loc_stock_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_stock_id.id
            res.update({'location_id': loc_stock_id})
        
        if 'subtype' in context and context.get('subtype', False) == 'picking':
            loc_packing_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_packing_id.id
            res.update({'location_dest_id': loc_packing_id})
        elif 'subtype' in context and context.get('subtype', False) == 'standard':
            loc_packing_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_output_id.id
            res.update({'location_dest_id': loc_packing_id})
        
        return res
    
    _columns = {'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                'pack_type': fields.many2one('pack.type', string='Pack Type'),
                'length' : fields.float(digits=(16,2), string='Length [cm]'),
                'width' : fields.float(digits=(16,2), string='Width [cm]'),
                'height' : fields.float(digits=(16,2), string='Height [cm]'),
                'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
                #'pack_family_id': fields.many2one('pack.family', string='Pack Family'),
                'initial_location': fields.many2one('stock.location', string='Initial Picking Location'),
                # relation to the corresponding move from draft **picking** ticket object
                'backmove_id': fields.many2one('stock.move', string='Corresponding move of previous step'),
                # relation to the corresponding move from draft **packing** ticket object
                'backmove_packing_id': fields.many2one('stock.move', string='Corresponding move of previous step in draft packing'),
                # functions
                'virtual_available': fields.function(_product_available, method=True, type='float', string='Virtual Stock', help="Future stock for this product according to the selected locations or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming.", multi='qty_available', digits_compute=dp.get_precision('Product UoM')),
                'qty_per_pack': fields.function(_vals_get, method=True, type='float', string='Qty p.p', multi='get_vals',),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals',),
                'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', multi='get_vals',),
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals_X',), # old_multi get_vals
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
                'is_dangerous_good': fields.function(_vals_get, method=True, type='boolean', string='Dangerous Good', multi='get_vals',),
                'is_keep_cool': fields.function(_vals_get, method=True, type='boolean', string='Keep Cool', multi='get_vals',),
                'is_narcotic': fields.function(_vals_get, method=True, type='boolean', string='Narcotic', multi='get_vals',),
                'sale_order_line_number': fields.function(_vals_get, method=True, type='integer', string='Sale Order Line Number', multi='get_vals_X',), # old_multi get_vals
                # Fields used for domain
                'location_virtual_id': fields.many2one('stock.location', string='Virtual location'),
                'location_output_id': fields.many2one('stock.location', string='Output location'),
                }

stock_move()


class sale_order(osv.osv):
    '''
    re-override to modify behavior for outgoing workflow
    '''
    _inherit = 'sale.order'
    _name = 'sale.order'
    
    def _hook_ship_create_stock_move(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for stock move creation
        '''
        move_data = super(sale_order, self)._hook_ship_create_stock_move(cr, uid, ids, context=context, *args, **kwargs)
        order = kwargs['order']
        # first go to packing location
        packing_id = order.shop_id.warehouse_id.lot_packing_id.id
        move_data['location_dest_id'] = packing_id
        move_data['state'] = 'confirmed'
        return move_data
    
    def _hook_ship_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for stock picking creation
        '''
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        
        picking_data = super(sale_order, self)._hook_ship_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        order = kwargs['order']
        picking_data['state'] = 'draft'
        if setup.delivery_process == 'simple':
            picking_data['subtype'] = 'standard'
            # use the name according to picking ticket sequence
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
        else:
            picking_data['subtype'] = 'picking'
            # use the name according to picking ticket sequence
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket')
            
        picking_data['name'] = pick_name        
        picking_data['flow_type'] = 'full'
        picking_data['backorder_id'] = False
        picking_data['warehouse_id'] = order.shop_id.warehouse_id.id
        
        return picking_data
    
    def _hook_ship_create_execute_picking_workflow(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to avoid the stock picking workflow execution
        - trigger the logging message for the created picking, as it stays in draft state and no call to action_confirm is performed
          for the moment within the msf_outgoing logic
        '''
        cond = super(sale_order, self)._hook_ship_create_execute_picking_workflow(cr, uid, ids, context=context, *args, **kwargs)
        cond = cond and False
        
        # diplay creation message for draft picking ticket
        picking_id = kwargs['picking_id']
        picking_obj = self.pool.get('stock.picking')
        if picking_id:
            picking_obj.log_picking(cr, uid, [picking_id], context=context)
        
        return cond

sale_order()


class procurement_order(osv.osv):
    '''
    procurement order workflow
    '''
    _inherit = 'procurement.order'
    
    def _hook_check_mts_on_message(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the _check_make_to_stock_product method from procurement>procurement.py>procurement.order
        
        - allow to modify the message written back to procurement order
        '''
        message = super(procurement_order, self)._hook_check_mts_on_message(cr, uid, context=context, *args, **kwargs)
        procurement = kwargs['procurement']
        if procurement.move_id.picking_id.state == 'draft' and procurement.move_id.picking_id.subtype == 'picking':
            message = _("Shipment Process in Progress.")
        return message
    
procurement_order()

