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

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp

# xml parser
from lxml import etree

from msf_outgoing import INTEGRITY_STATUS_SELECTION


class stock_partial_move_memory_out(osv.osv_memory):
    '''
    add split method to base out object
    '''
    _inherit = "stock.move.memory.out"

    def split(self, cr, uid, ids, context=None):
        '''
        open the split wizard, the user can select the qty for the new move
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz_obj = self.pool.get('wizard')

        # data - no step needed for present split wizard
        name = _("Split Selected Stock Move")
        model = 'split.memory.move'
        # we need to get the memory move id to know which line to split
        # and class name, to know which type of moves
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], name=name, model=model, w_type='create', context=dict(context, memory_move_ids=ids, class_name=self._name))

    def change_product(self, cr, uid, ids, context=None):
        '''
        open the change product wizard, the user can select the new product
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        wiz_obj = self.pool.get('wizard')
        # data - no step needed for present split wizard
        name = _("Change Product of Selected Stock Move")
        model = 'change.product.memory.move'
        # we need to get the memory move id to know which line to split
        # and class name, to know which type of moves
        data = self.read(cr, uid, ids, ['product_id', 'product_uom'], context=context)[0]
        product_id = data['product_id']
        uom_id = data['product_uom']
        uom_category_id = False
        if uom_id:
            uom_category_id = self.pool.get('product.uom').browse(cr, uid, data['product_uom'], context=context).category_id.id
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], name=name, model=model,
                                   type='create', context=dict(context,
                                                               memory_move_ids=ids,
                                                               class_name=self._name,
                                                               product_id=product_id,
                                                               uom_category_id=uom_category_id,
                                                               uom_id=uom_id))

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        change the function name to do_incoming_shipment
        '''
        if context is None:
            context = {}
        result = super(stock_partial_move_memory_out, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            root = etree.fromstring(result['arch'])
            fields = root.xpath('/tree')
            for field in fields:
                root.set('hide_new_button', 'True')
                root.set('hide_delete_button', 'True')
            result['arch'] = etree.tostring(root)
            picking_obj = self.pool.get('stock.picking')
            picking_ids = context.get('active_ids')
            if picking_ids:
                picking_type = picking_obj.read(cr, uid, picking_ids, ['type'], context=context)[0]['type']
                if picking_type == 'in':
                    # remove the kit column for memory moves
                    # the creation of composition list (if needed) is performed after the IN processing wizard
                    # load the xml tree
                    root = etree.fromstring(result['arch'])
                    # xpath of fields to be modified
                    list = ['//field[@name="composition_list_id"]']
                    for xpath in list:
                        fields = root.xpath(xpath)
                        if not fields:
                            raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                        for field in fields:
                            field.set('invisible', 'True')
                    result['arch'] = etree.tostring(root)
        return result

#    update code to allow delete lines (or not but must be consistent in all wizards)
#    I would say, maybe not allow (by hidding the button not raise exception in method -> causes bug)
#    because then the user can always see the corresponding full list and change its mind
#    if deleted, must cancel and redo
#    
#    would be nice a validator decorator !
    _columns={'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
              'force_complete' : fields.boolean(string='Force'),
              'line_number': fields.integer(string='Line'),
              'change_reason': fields.char(string='Change Reason', size=1024),
              'initial_qty': fields.related('move_id', 'product_qty', string='Initial Qty', readonly=True),
              # override to change the name
              'quantity' : fields.float("Quantity to process", required=True),
              # override for decimal precision - after purchase override so Purchase Price Computation exists
              'cost' : fields.float("Cost", digits_compute=dp.get_precision('Purchase Price Computation'), help="Unit Cost for this product line"),
              }

    _defaults = {'integrity_status': 'empty',
                 'force_complete': False,
                 'quantity': 0.0,
                 }

    def _check_quantity(self, cr, uid, ids, context=None):
        '''
        Checks if quantity is correct
        '''
        for move in self.browse(cr, uid, ids, context=context):
            if move.quantity < 0:
                raise osv.except_osv(_('Warning !'), _('You must assign a positive quantity value or 0.'))
        return True

# no constraint at move level for now because of OEB-99
#    _constraints = [(_check_quantity,
#                     'You must assign a positive quantity value or 0.',
#                     ['quantity']),
#                    ]

    _order = 'line_number asc'

stock_partial_move_memory_out()


class stock_partial_move_memory_in(osv.osv_memory):
    _name = "stock.move.memory.in"
    _inherit = "stock.move.memory.out"

stock_partial_move_memory_in()


class stock_partial_move_memory_picking(osv.osv_memory):
    '''
    add the split method
    '''
    _name = "stock.move.memory.picking"
    _inherit = "stock.move.memory.out"

stock_partial_move_memory_picking()


class stock_partial_move_memory_returnproducts(osv.osv_memory):
    '''
    memory move for ppl return products step
    '''
    _name = "stock.move.memory.returnproducts"
    _inherit = "stock.move.memory.picking"
    _columns = {'qty_to_return': fields.float(string='Qty to return', related_uom='product_uom'),
                }

    def _check_qty_to_return(self, cr, uid, ids, context=None):
        '''
        Checks if qty_to_return is correct
        '''
        for move in self.browse(cr, uid, ids, context=context):
            if move.qty_to_return < 0:
                raise osv.except_osv(_('Warning !'), _('You must assign a positive "quantity to return" value or 0.'))
        return True

# no constraint at move level for now because of OEB-99
#    _constraints = [(_check_qty_to_return,
#                     'You must assign a positive quantity to return value or 0',
#                     ['qty_to_return']),
#                    ]

    _defaults = {
        'qty_to_return': 0.0,
    }

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to UoM
        '''
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty_to_return', result=res)

        return res

stock_partial_move_memory_returnproducts()


class stock_partial_move_memory_ppl(osv.osv_memory):
    '''
    memory move for ppl step
    '''
    _name = "stock.move.memory.ppl"
    _inherit = "stock.move.memory.picking"

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        for memory_move in self.browse(cr, uid, ids, context=context):
            values = {'num_of_packs': 0,
                      'qty_per_pack': 0,
                      }
            result[memory_move.id] = values
            # number of packs with from/to values
            num_of_packs = memory_move.to_pack - memory_move.from_pack + 1
            values['num_of_packs'] = num_of_packs
            if num_of_packs:
                qty_per_pack = memory_move.quantity / num_of_packs
            else:
                qty_per_pack = 0
            values['qty_per_pack'] = qty_per_pack

        return result

    _columns = {'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                # functions
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals',),
                'qty_per_pack': fields.function(_vals_get, method=True, type='float', string='Qty p.p.', multi='get_vals_X',), # old_multi get_vals
                }

    def create(self, cr, uid, vals, context=None):
        '''
        default value of qty_per_pack to quantity
        of from_pack and to_pack to 1

        those fields have a constraint assigned to them, and must
        therefore be completed with default value at creation
        '''
        if 'qty_per_pack' not in vals:
            vals.update(qty_per_pack=vals['quantity_ordered'])

        if 'from_pack' not in vals:
            vals.update(from_pack=1)

        if 'to_pack' not in vals:
            vals.update(to_pack=1)

        return super(stock_partial_move_memory_ppl, self).create(cr, uid, vals, context)

    def _check_from_to_pack(self, cr, uid, ids, context=None):
        """ Checks if from_pack is assigned to memory move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.from_pack < 1:
                raise osv.except_osv(_('Warning !'), _('You must assign a positive "from pack" value.'))
            if move.to_pack < 1:
                raise osv.except_osv(_('Warning !'), _('You must assign a positive "to pack" value.'))
            if move.to_pack < move.from_pack:
                raise osv.except_osv(_('Warning !'), _('"to pack" value must be greater or equal to "from pack" value.'))
        return True

    # existence integrity
    # the constraint are at memory.move level for ppl1 because we do not
    # want to wait until the end of ppl2 and stock.move update to validate
    # the data of this wizard. this is possible because we set default values
    # for qty_per_pack, from_pack and to_pack different from 0
# no constraint at move level for now because of OEB-99
#    _constraints = [(_check_from_to_pack,
#                     'You must assign a positive "from/to pack" value',
#                     ['from_pack', 'to_pack']),
#                    ]

stock_partial_move_memory_ppl()


class stock_partial_move_memory_families(osv.osv_memory):
    '''
    view corresponding to pack families

    integrity constraint 
    '''
    _name = "stock.move.memory.families"
    _rec_name = 'from_pack'
    _columns = {
        'from_pack' : fields.integer(string="From p."),
        'to_pack' : fields.integer(string="To p."),
        'pack_type': fields.many2one('pack.type', 'Pack Type'),
        'length' : fields.float(digits=(16,2), string='Length [cm]'),
        'width' : fields.float(digits=(16,2), string='Width [cm]'),
        'height' : fields.float(digits=(16,2), string='Height [cm]'),
        'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
        'wizard_id' : fields.many2one('stock.partial.move', string="Wizard"),
        'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
    }

    _defaults = {'integrity_status': 'empty',
                 }

    def onchange_pack_type(self, cr, uid, ids, pack_type, context=None):
        '''
        Update values of stock.move.memory.families from the stock_pack selected
        '''
        res = {}
        p_type_obj = self.pool.get('pack.type')
        if pack_type :
            # if 'pack_type' is not a list, turn it into list
            if isinstance(pack_type,(int,long)):
                pack_type = [pack_type]
            p_type_read = p_type_obj.read(cr, uid, pack_type, ['length', 'width', 'height'], context=context)[0]
            length, width, height = p_type_read['length'], p_type_read['width'], p_type_read['height']
            res.update({'value': {'length': length, 'width': width, 'height': height}})
        return res

stock_partial_move_memory_families()


class stock_partial_move_memory_shipment_create(osv.osv_memory):
    '''
    view corresponding to pack families for shipment create

    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.create"
    _inherit = "stock.move.memory.families"
    _rec_name = 'from_pack'

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        if context is None:
            context = {}
        result = {}
        for memory_move in self.browse(cr, uid, ids, context=context):
            values = {'num_of_packs': 0,
                      'selected_weight': 0.0,
                      }
            result[memory_move.id] = values
            # number of packs with from/to values
            num_of_packs = memory_move.to_pack - memory_move.from_pack + 1
            values['num_of_packs'] = num_of_packs
            if not context.get('step') == 'returnpacksfromshipment':
                selected_weight = memory_move.weight * memory_move.selected_number
            if context.get('step') == 'returnpacksfromshipment':
                num_returned = memory_move.return_to > 0 \
                    and memory_move.return_from > 0 \
                    and memory_move.return_to >= memory_move.return_from \
                    and memory_move.return_to - memory_move.return_from + 1 \
                    or 0.0
                selected_weight = memory_move.weight * num_returned
            values['selected_weight'] = selected_weight

        return result

    def _get_volume(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        for shipment in self.browse(cr, uid, ids, context=context):
            vol = ( shipment.length * shipment.width * shipment.height * float(shipment.num_of_packs) ) / 1000.0
            result[shipment.id] = vol
        return result

    _columns = {'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
                'ppl_id': fields.many2one('stock.picking', string="PPL Ref"), 
                'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
                'selected_number': fields.integer(string='Selected Number'),
                # functions
                'volume': fields.function(_get_volume, method=True, type='float', string=u'Volume [dm³]',),
                'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='#Packs', multi='get_vals',),
                'selected_weight' : fields.function(_vals_get, method=True, type='float', string='Selected Weight [kg]', multi='get_vals_X',), # old_multi get_vals
                }

    def _check_selected_number(self, cr, uid, ids, context=None):
        ''' 
        Checks if selected number is correct
        '''
        for move in self.browse(cr, uid, ids, context=context):
            if move.selected_number < 0:
                raise osv.except_osv(_('Warning !'), _('You must assign a positive selected number of packs value or 0.'))
        return True
# no constraint at move level for now because of OEB-99
#    _constraints = [(_check_selected_number,
#                     'You cannot select negative number.',
#                     ['selected_number']),
#                    ]


stock_partial_move_memory_shipment_create()


class stock_partial_move_memory_shipment_returnpacks(osv.osv_memory):
    '''
    view corresponding to pack families for packs return

    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.returnpacks"
    _inherit = "stock.move.memory.shipment.create"

stock_partial_move_memory_shipment_returnpacks()


class stock_partial_move_memory_shipment_returnpacksfromshipment(osv.osv_memory):
    '''
    view corresponding to pack families for packs return from shipment

    integrity constraint 
    '''
    _name = "stock.move.memory.shipment.returnpacksfromshipment"
    _inherit = "stock.move.memory.shipment.returnpacks"
    _columns = {
        'return_from' : fields.integer(string="Return From"),
        'return_to' : fields.integer(string="Return To"),
    }

    def split(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        # objects
        wiz_obj = self.pool.get('wizard')
        if isinstance(ids, (int, long)):
            ids = [ids]

        for memory_move in self.browse(cr, uid, ids, context=context):
            # create new memory move - copy for memory is not implemented
            fields = self.fields_get(cr, uid, context=context)
            values = {}
            for key in fields.keys():
                type= fields[key]['type']
                if type not in ('one2many', 'many2one', 'one2one'):
                    values[key] = getattr(memory_move, key)
                elif type in ('many2one'):
                    tmp = getattr(memory_move, key)
                    values[key] = getattr(tmp, "id")
                else:
                    assert False, 'copy of %s value is not implemented'%type

            self.create(cr, uid, values, context=context)

        # udpate the original wizard
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='update', context=context)

stock_partial_move_memory_shipment_returnpacksfromshipment()
