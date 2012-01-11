
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 TeMPO Consulting, MSF.
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
import time
import netsvc

class shipment_wizard(osv.osv_memory):
    _name = "shipment.wizard"
    _description = "Shipment Wizard"
    _columns = {
        'date': fields.datetime('Date', required=True),
        'transport_type': fields.selection([('by_road', 'By road')],
                                           string="Transport Type", readonly=True),
        'address_id': fields.many2one('res.partner.address', 'Address', help="Address of customer"),
        'partner_id': fields.related('address_id', 'partner_id', type='many2one', relation='res.partner', string='Customer'),
        'product_moves_shipment_create' : fields.one2many('stock.move.memory.shipment.create', 'wizard_id', 'Pack Families'),
        'product_moves_shipment_returnpacks' : fields.one2many('stock.move.memory.shipment.returnpacks', 'wizard_id', 'Pack Families'),
        'product_moves_shipment_returnpacksfromshipment' : fields.one2many('stock.move.memory.shipment.returnpacksfromshipment', 'wizard_id', 'Pack Families'),
     }
    
    def select_all(self, cr, uid, ids, context=None):
        '''
        select all buttons, write max number of packs in each pack family line
        '''
        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.product_moves_shipment_create:
                line.write({'selected_number':int(line.num_of_packs),}, context=context)
            for line in wiz.product_moves_shipment_returnpacks:
                line.write({'selected_number':int(line.num_of_packs),}, context=context)
            for line in wiz.product_moves_shipment_returnpacksfromshipment:
                line.write({'return_from': line.from_pack,
                            'return_to': line.to_pack,}, context=context)
        
        return {
                'name': 'Create Shipment',
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'shipment.wizard',
                'res_id': ids[0],
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': context,
                }
        
    def deselect_all(self, cr, uid, ids, context=None):
        '''
        select all buttons, write max number of packs in each pack family line
        '''
        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.product_moves_shipment_create:
                line.write({'selected_number':0,}, context=context)
            for line in wiz.product_moves_shipment_returnpacks:
                line.write({'selected_number':0,}, context=context)
            for line in wiz.product_moves_shipment_returnpacksfromshipment:
                line.write({'return_from': 0,
                            'return_to': 0,}, context=context)
        
        return {
                'name': 'Create Shipment',
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'shipment.wizard',
                'res_id': ids[0],
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': context,
                }
    
    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
         
         data is generated for the corresponding picking (shipment.packing_ids)
         by the generate_data_from_picking_for_pack_family method in stock.picking
        """
        if context is None:
            context = {}
        
        # we need the step info
        assert 'step' in context, 'Step not defined in context'
        step = context['step']
            
        pick_obj = self.pool.get('stock.picking')
        shipment_obj = self.pool.get('shipment')
        
        # call to super
        res = super(shipment_wizard, self).default_get(cr, uid, fields, context=context)
        
        # shipment calling the wizard
        shipment_ids = context.get('active_ids', [])
        if not shipment_ids:
            return res

        result = []
        if step in ('create', 'returnpacks', 'returnpacksfromshipment'):
            # generate data from shipment
            shipments = shipment_obj.browse(cr, uid, shipment_ids, context=context)
            for ship in shipments:
                address_id = ship.address_id.id
                # gather the picking sharing this draft shipment - the address_id is specified as integrity check
                picking_ids = pick_obj.search(cr, uid, [('shipment_id', '=', ship.id), ('address_id', '=', address_id)], context=context)
                data = pick_obj.generate_data_from_picking_for_pack_family(cr, uid, picking_ids, object_type='memory', context=None)
                # structure the data to display
                result.extend(self.__create_pack_families_memory(data, context=context))
        else:
            # this line should never be reached
            assert False, 'should not reach this line'

        if 'product_moves_shipment_create' in fields and step in ('create'):
            res.update({'product_moves_shipment_create': result})
            
        if 'product_moves_shipment_returnpacks' in fields and step in ('returnpacks'):
            res.update({'product_moves_shipment_returnpacks': result})
            
        if 'product_moves_shipment_returnpacksfromshipment' in fields and step in ('returnpacksfromshipment'):
            res.update({'product_moves_shipment_returnpacksfromshipment': result})
            
        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})
            
        if 'transport_type' in fields:
            res.update({'transport_type': 'by_road'})
            
        if 'address_id' in fields:
            res.update({'address_id': address_id})
            
        return res
    
    def __create_pack_families_memory(self, data, context=None):
        '''
        generates the memory objects data
        
        - wizard_id seems to be filled automatically
        '''
        assert context, 'No context defined'
        
        # list for the current pick object
        result = []
        
        for picking_id in data:
            for from_pack in data[picking_id]:
                for to_pack in data[picking_id][from_pack]:
                    # get a move_id no matter which from the sequence 
                    move_id = data[picking_id][from_pack][to_pack].keys()[0]
                    pack_family_memory = data[picking_id][from_pack][to_pack][move_id]
                    # we add the reference to the draft packing object
                    pack_family_memory.update({'draft_packing_id': picking_id})
                    # by default, all packs are selected for shipment
                    num_of_pack = pack_family_memory.get('to_pack') - pack_family_memory.get('from_pack') + 1
                    pack_family_memory.update(selected_number=num_of_pack)
                    # create the memory pack_family
                    result.append(pack_family_memory)
        
        # return the list of dictionaries
        return result
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # integrity check
        assert context, 'No context defined'
        # call super
        result = super(shipment_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # working objects
        assert 'step' in context, 'No step defined in context'
        step = context['step']
        
        _moves_arch_lst = """<form string="%s">
                        <field name="date" invisible="1"/>
                        <separator colspan="4" string="%s"/>
                        <field name="product_moves_shipment_%s" colspan="4" nolabel="1" mode="tree,form"></field>
                        """ % (_('Process Document'), _('Products'), step)
        _moves_fields = result['fields']

        # add field related to picking type only
        _moves_fields.update({
                            'product_moves_shipment_' + step: {'relation': 'stock.move.memory.shipment.' + step, 'type' : 'one2many', 'string' : 'Product Moves'}, 
                            })

        # specify the button according to the screen
        if step == 'create':
            button = ('do_create_shipment', 'Create Shipment')
            
        elif step == 'returnpacks':
            button = ('do_return_packs', 'Return Packs')
            
        elif step == 'returnpacksfromshipment':
            button = ('do_return_packs_from_shipment', 'Return Packs from Shipment')
            
        else:
            button = ('undefined', 'Undefined: %s'%step)
                
        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="4" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="_Cancel" />
                <button name="select_all" string="Select All"
                    colspan="1" type="object" icon="terp_stock_symbol-selection" />
                <button name="deselect_all" string="Deselect All"
                    colspan="1" type="object" icon="terp_stock_symbol-selection" />
                <button name="%s" string="%s"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>"""%button
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result
    
    def generate_data_from_partial(self, cr, uid, ids, conditions=None, context=None):
        '''
        data is located in product_moves_shipment_create
        
        we generate the data structure from the shipment wizard
        
        QUESTION: why partial data is stored in a list, we have one partial for each to/from pack couple at this level?
        
        structure :
        {shipment_id: {draft_packing_id: {from_pack: {to_pack: {[partial,]}]}}}}
        
        fields:
        {'selected_weight': {'function': '_vals_get', 'digits': (16, 2), 'fnct_inv': False, 'string': 'Selected Weight [kg]', 'fnct_inv_arg': False, 'readonly': 1, 'fnct_search': False, 'func_obj': False, 'type': 'float', 'store': False, 'func_method': True},
        'weight': {'digits': (16, 2), 'selectable': True, 'type': 'float', 'string': 'Weight p.p [kg]'},
        'pack_type': {'domain': [], 'string': 'Pack Type', 'relation': 'pack.type', 'context': {}, 'selectable': True, 'type': 'many2one'},
        'ppl_id': {'domain': [], 'string': 'PPL Ref', 'relation': 'stock.picking', 'context': {}, 'selectable': True, 'type': 'many2one'},
        'draft_packing_id': {'domain': [], 'string': 'Draft Packing Ref', 'relation': 'stock.picking', 'context': {}, 'selectable': True, 'type': 'many2one'},
        'wizard_id': {'domain': [], 'string': 'Wizard', 'relation': 'stock.partial.move', 'context': {}, 'selectable': True, 'type': 'many2one'},
        'height': {'digits': (16, 2), 'selectable': True, 'type': 'float', 'string': 'Height [cm]'},
        'from_pack': {'selectable': True, 'type': 'integer', 'string': 'From p.'},
        'length': {'digits': (16, 2), 'selectable': True, 'type': 'float', 'string': 'Length [cm]'},
        'to_pack': {'selectable': True, 'type': 'integer', 'string': 'To p.'},
        'integrity_status': {'selectable': True, 'readonly': True, 'selection': [('empty', ''), ('ok', u'Ok'), ('negative', u'Negative Value'), ('missing_lot', u'Production Lot is Missing'), ('missing_date', u'Expiry Date is Missing'), ('no_lot_needed', u'No Production Lot/Expiry Date Needed'), ('wrong_lot_type', u'Wrong Production Lot Type'), ('wrong_lot_type_need_internal', u'Need Expiry Date (Internal) not Production Lot (Standard)'), ('wrong_lot_type_need_standard', u'Need Production Lot (Standard) not Expiry Date (Internal)'), ('empty_picking', u'Empty Picking Ticket'), ('missing_1', u'The first sequence must start with 1'), ('to_smallaer_than_from', u'To value must be greater or equal to From value'), ('overlap', u'The sequence overlaps previous one'), ('gap', u'A gap exist in the sequence'), ('missing_weight', u'Weight is Missing')], 'type': 'selection', 'string': ' '},
        'num_of_packs': {'function': '_vals_get', 'digits': (16, 2), 'fnct_inv': False, 'string': '#Packs', 'fnct_inv_arg': False, 'readonly': 1, 'fnct_search': False, 'func_obj': False, 'type': 'integer', 'store': False, 'func_method': True},
        'selected_number': {'selectable': True, 'type': 'integer', 'string': 'Selected Number'},
        'width': {'digits': (16, 2), 'selectable': True, 'type': 'float', 'string': 'Width [cm]'},
        'sale_order_id': {'domain': [], 'string': 'Sale Order Ref', 'relation': 'sale.order', 'context': {}, 'selectable': True, 'type': 'many2one'}}
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        assert 'step' in context, 'No step defined in context'
        step = context['step']
        
        # condition for data to be added
        if conditions is None:
            conditions = []
        
        shipment_obj = self.pool.get('stock.picking')
        memory_move_obj = self.pool.get('stock.move.memory.shipment.%s'%step)
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # returned datas
        partial_datas_shipment = {}
        
        # picking ids
        shipment_ids = context['active_ids']
        for ship in shipment_obj.browse(cr, uid, shipment_ids, context=context):
            # for each picking
            partial_datas_shipment[ship.id] = {}
            # ppl moves
            pack_family_list = eval('partial.product_moves_shipment_%s'%step)
            # organize data according to from pack / to pack
            for memory_move in pack_family_list:
                # all returns True if applied on an empty list
                # only take into account if packs have been selected
                if all([getattr(memory_move, cond) for cond in conditions]):
                    # retrieve fields from object
                    fields = memory_move_obj.fields_get(cr, uid, context=context)
                    values = {}
                    # add the id of memory move
                    values.update({'memory_move_id': memory_move.id})
                    for key in fields.keys():
                        type= fields[key]['type']
                        if type not in ('one2many', 'many2one', 'one2one'):
                            values[key] = getattr(memory_move, key)
                        elif type in ('many2one'):
                            tmp = getattr(memory_move, key)
                            values[key] = getattr(tmp, "id")
                        else:
                            assert False, 'copy of %s value is not implemented'%type

                    # openerp bug, function with int type returns a string
                    if isinstance(values['num_of_packs'], str):
                        values['num_of_packs'] = int(values['num_of_packs'])

                    partial_datas_shipment[ship.id] \
                        .setdefault(memory_move.draft_packing_id.id, {}) \
                        .setdefault(memory_move.from_pack, {}) \
                        .setdefault(memory_move.to_pack, []).append(values)
                
        return partial_datas_shipment
    
    def integrity_check_packs(self, cr, uid, ids, data, context=None):
        '''
        integrity check on create shipment data
        - no negative values (<0)
        - at least one positive one (>0)
        - no more than available quantity #packs
        
        {12: {176: {1: {1: [{'selected_weight': 0.0, 'weight': 0.0, 'pack_type': False, 'ppl_id': 175, 'draft_packing_id': 176, 'wizard_id': 1, 'height': 0.0, 'from_pack': 1, 'length': 0.0, 'to_pack': 1, 'integrity_status': 'empty', 'num_of_packs': '1', 'selected_number': 1, 'width': 0.0, 'sale_order_id': False}]}}}}
        
        return True/False
        '''
        memory_move_obj = self.pool.get('stock.move.memory.shipment.create')
        # validate the data
        for shipment_data in data.values():
            # total sum not including negative values
            sum_qty = 0
            # flag to detect negative values
            negative_value = False
            # flag to detect excessive return quantity
            too_much = False
            for packing_data in shipment_data.values():
                for from_data in packing_data.values():
                    for to_data in from_data.values():
                        for data in to_data:
                            # quantity check
                            if data['selected_number'] < 0.0:
                                # a negative value has been selected, update the memory line
                                # update the new value for integrity check with 'negative' value (selection field)
                                negative_value = True
                                memory_move_obj.write(cr, uid, [data['memory_move_id']], {'integrity_status': 'negative'}, context=context)
                            elif data['selected_number'] > int(data['num_of_packs']):
                                # cannot return more products than available
                                too_much = True
                                memory_move_obj.write(cr, uid, [data['memory_move_id']], {'integrity_status': 'return_qty_too_much',}, context=context)
                            else:
                                sum_qty += data['selected_number']
                            
            # if error, return False
            if not sum_qty or negative_value or too_much:
                return False
        return True
    
    def set_integrity_status(self, cr, uid, ids, field_name, status='empty', context=None):
        '''
        for all moves set the status to ok (default value) or other if specified
        '''
        for wiz in self.browse(cr, uid, ids, context=context):
            for memory_move in getattr(wiz, field_name):
                memory_move.write({'integrity_status': status,}, context=context)
    
    def do_create_shipment(self, cr, uid, ids, context=None):
        '''
        gather data from wizard pass it to the do_create_shipment method of shipment class
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        
        ship_obj = self.pool.get('shipment')
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_shipment_create'
        # shipment ids
        shipment_ids = context['active_ids']
        # generate data structure - selected_number must be non zero to be taken into account
        partial_datas_shipment = self.generate_data_from_partial(cr, uid, ids, conditions=['selected_number'], context=context)
        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - sequence -> no prodlot check as the screen is readonly
        packs_check = self.integrity_check_packs(cr, uid, ids, partial_datas_shipment, context=context)
        if not packs_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, shipment_ids, type='update', context=context)
        # call stock_picking method which returns action call
        return ship_obj.do_create_shipment(cr, uid, shipment_ids, context=dict(context, partial_datas_shipment=partial_datas_shipment))
    
    def integrity_check_return_packs(self, cr, uid, ids, data, context=None):
        '''
        integrity check on shipment data
        '''
        for shipment_data in data.values():
            for packing_data in shipment_data.values():
                for from_pack_data in packing_data.values():
                    for to_pack_data in from_pack_data.values():
                        for partial in to_pack_data:
                            if partial.get('selected_number', False):
                                return True
        
        return False
    
    def do_return_packs(self, cr, uid, ids, context=None):
        '''
        gather data from wizard pass it to the do_return_packs method of shipment class
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        
        ship_obj = self.pool.get('shipment')
        # shipment ids
        shipment_ids = context['active_ids']
        # generate data structure - selected_number must be non zero to be taken into account
        partial_datas = self.generate_data_from_partial(cr, uid, ids, conditions=['selected_number'], context=context)
        # integrity check on wizard data
        if not self.integrity_check_return_packs(cr, uid, ids, partial_datas, context=context):
            raise osv.except_osv(_('Warning !'), _('You must at least select one pack to return!'))
        # call stock_picking method which returns action call
        return ship_obj.do_return_packs(cr, uid, shipment_ids, context=dict(context, partial_datas=partial_datas))
    
    def integrity_check_return_packs_from_shipment(self, cr, uid, ids, data, context=None):
        '''
        integrity check on shipment data
        '''
        for shipment_data in data.values():
            for packing_data in shipment_data.values():
                for from_pack_data in packing_data.values():
                    for to_pack_data in from_pack_data.values():
                        for partial in to_pack_data:
                            if partial.get('return_from', False) and partial.get('return_to', False):
                                return True
        
        return False
    
    def do_return_packs_from_shipment(self, cr, uid, ids, context=None):
        '''
        gather data from wizard pass it to the do_return_packs method of shipment class
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        
        ship_obj = self.pool.get('shipment')
        # shipment ids
        shipment_ids = context['active_ids']
        # generate data structure - return_from and return_to must be non zero
        partial_datas = self.generate_data_from_partial(cr, uid, ids, conditions=['return_from', 'return_to'], context=context)
        # integrity check on wizard data
        if not self.integrity_check_return_packs_from_shipment(cr, uid, ids, partial_datas, context=context):
            raise osv.except_osv(_('Warning !'), _('You must at least select one pack to return!'))
        # call stock_picking method which returns action call
        return ship_obj.do_return_packs_from_shipment(cr, uid, shipment_ids, context=dict(context, partial_datas=partial_datas))
    

shipment_wizard()
