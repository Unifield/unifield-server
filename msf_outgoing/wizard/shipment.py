
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
        if step in ('create', 'returnpacks'):
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
            
        else:
            button = ('undefined', 'Undefined: %s'%step)
                
        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="3" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="_Cancel" />
                <button name="select_all" string="Select All"
                    colspan="1" type="object" icon="terp_stock_symbol-selection" />
                <button name="%s" string="%s"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>"""%button
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result
    
    def generate_data_from_partial(self, cr, uid, ids, context=None):
        '''
        data is located in product_moves_shipment_create
        
        we generate the data structure from the shipment wizard
        
        structure :
        {shipment_id: {draft_packing_id: {from_pack: {to_pack: {partial}]}}}}
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        assert 'step' in context, 'No step defined in context'
        step = context['step']
        
        shipment_obj = self.pool.get('stock.picking')
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
            for pack_family in pack_family_list:
                if pack_family.selected_number:
                    # only take into account if packs have been selected
                    fields = ['from_pack', 'to_pack', 'length', 'width', 'height', 'weight', 'selected_number']
                    values = dict(zip(fields, [eval('pack_family.%s'%x) for x in fields]))
                    values.update({'pack_type': pack_family.pack_type.id, 'draft_packing_id': pack_family.draft_packing_id.id})
                    partial_datas_shipment[ship.id] \
                        .setdefault(pack_family.draft_packing_id.id, {}) \
                        .setdefault(pack_family.from_pack, {})[pack_family.to_pack] = values
                
        return partial_datas_shipment
    
    def do_create_shipment(self, cr, uid, ids, context=None):
        '''
        gather data from wizard pass it to the do_create_shipment method of shipment class
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No shipment ids in context. Action call is wrong'
        
        ship_obj = self.pool.get('shipment')
        # shipment ids
        shipment_ids = context['active_ids']
        # generate data structure
        partial_datas_shipment = self.generate_data_from_partial(cr, uid, ids, context=context)
        # call stock_picking method which returns action call
        return ship_obj.do_create_shipment(cr, uid, shipment_ids, context=dict(context, partial_datas_shipment=partial_datas_shipment))
    
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
        # generate data structure
        partial_datas = self.generate_data_from_partial(cr, uid, ids, context=context)
        # call stock_picking method which returns action call
        return ship_obj.do_return_packs(cr, uid, shipment_ids, context=dict(context, partial_datas=partial_datas))
    

shipment_wizard()
