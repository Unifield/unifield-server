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
import time

from msf_outgoing import INTEGRITY_STATUS_SELECTION


class create_picking_processor(osv.osv):
    """
    Create picking processing wizard
    """
    _name = 'create.picking.processor'
    _inherit = 'internal.picking.processor'
    _description = 'Wizard to process the first step of the Pick/Pack/Ship'

    _columns = {
        'move_ids': fields.one2many(
            'create.picking.move.processor',
            'wizard_id',
            string='Moves',
        ),
        'draft': fields.boolean('Draft'),
    }

    """
    Model methods
    """
    def do_create_picking(self, cr, uid, ids, context=None):
        """
        Made some integrity checks and launch create_picking method of the stock.picking object
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')

        wizard_brw_list = self.browse(cr, uid, ids, context=context)

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft': False}, context=context)

        self.integrity_check_quantity(cr, uid, wizard_brw_list, context=context)
        self.integrity_check_prodlot(cr, uid, wizard_brw_list, context=context)
        # call stock_picking method which returns action call
        return picking_obj.do_create_picking(cr, uid, ids, context=context)


    def do_reset(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft': False}, context=context)

        return self.pool.get('stock.picking').create_picking(cr, uid, pick_id, context=context)


    def do_save_draft(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        self.write(cr, uid, ids, {'draft': True}, context=context)

        return {}

create_picking_processor()


class create_picking_move_processor(osv.osv):
    """
    Create picking moves processing wizard
    """
    _name = 'create.picking.move.processor'
    _inherit = 'internal.move.processor'
    _description = 'Wizard lines for create picking processor'

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        return super(create_picking_move_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(create_picking_move_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

    def _get_integrity_status(self, cr, uid, ids, field_name, args, context=None):
        return super(create_picking_move_processor, self)._get_integrity_status(cr, uid, ids, field_name, args, context=context)

    _columns = {
        # Parent wizard
        'wizard_id': fields.many2one(
            'create.picking.processor',
            string='Wizard',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
        ),
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected product to receive",
            multi='move_info',
        ),
        'comment': fields.function(
            _get_move_info,
            method=True,
            string='Comment',
            type='text',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Comment of the move",
            multi='move_info',
        ),
        'ordered_uom_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM',
            type='many2one',
            relation='product.uom',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Expected UoM to receive",
            multi='move_info',
        ),
        'ordered_uom_category': fields.function(
            _get_move_info,
            method=True,
            string='Ordered UoM category',
            type='many2one',
            relation='product.uom.categ',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Category of the expected UoM to receive",
            multi='move_info'
        ),
        'location_id': fields.function(
            _get_move_info,
            method=True,
            string='Location',
            type='many2one',
            relation='stock.location',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Source location of the move",
            multi='move_info'
        ),
        'location_supplier_customer_mem_out': fields.function(
            _get_move_info,
            method=True,
            string='Location Supplier Customer',
            type='boolean',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            multi='move_info',
            help="",
        ),
        'integrity_status': fields.function(
            _get_integrity_status,
            method=True,
            string='',
            type='selection',
            selection=INTEGRITY_STATUS_SELECTION,
            store={
                'create.picking.move.processor': (
                    lambda self, cr, uid, ids, c=None: ids,
                    ['product_id', 'wizard_id', 'quantity', 'asset_id', 'prodlot_id', 'expiry_date'],
                    20
                ),
            },
            readonly=True,
            help="Integrity status (e.g: check if a batch is set for a line with a batch mandatory product...)",
        ),
        'type_check': fields.function(
            _get_move_info,
            method=True,
            string='Picking Type Check',
            type='char',
            size=32,
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            help="Return the type of the picking",
            multi='move_info',
        ),
        'lot_check': fields.function(
            _get_product_info,
            method=True,
            string='B.Num',
            type='boolean',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A batch number is required on this line",
        ),
        'exp_check': fields.function(
            _get_product_info,
            method=True,
            string='Exp.',
            type='boolean',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An expiry date is required on this line",
        ),
        'asset_check': fields.function(
            _get_product_info,
            method=True,
            string='Asset',
            type='boolean',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="An asset is required on this line",
        ),
        'kit_check': fields.function(
            _get_product_info,
            method=True,
            string='Kit',
            type='boolean',
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="A kit is required on this line",
        ),
        'kc_check': fields.function(
            _get_product_info,
            method=True,
            string='KC',
            type='char',
            size=8,
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Heat Sensitive Item",
        ),
        'ssl_check': fields.function(
            _get_product_info,
            method=True,
            string='SSL',
            type='char',
            size=8,
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Short Shelf Life product",
        ),
        'dg_check': fields.function(
            _get_product_info,
            method=True,
            string='DG',
            type='char',
            size=8,
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Dangerous Good",
        ),
        'np_check': fields.function(
            _get_product_info,
            method=True,
            string='CS',
            type='char',
            size=8,
            store={
                'create.picking.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
    }

create_picking_move_processor()


class create_picking(osv.osv_memory):
    _name = "create.picking"
    _description = "Create Picking"
    _columns = {
        'date': fields.datetime('Date', required=True),
        'product_moves_picking' : fields.one2many('stock.move.memory.picking', 'wizard_id', 'Moves'),
        'product_moves_ppl' : fields.one2many('stock.move.memory.ppl', 'wizard_id', 'Moves'),
        'product_moves_families' : fields.one2many('stock.move.memory.families', 'wizard_id', 'Pack Families'),
        'product_moves_returnproducts': fields.one2many('stock.move.memory.returnproducts', 'wizard_id', 'Return Products')
    }

    def copy_all(self, cr, uid, ids, context=None):
        create = self.browse(cr, uid, ids[0], context=context)
        if create.product_moves_picking:
            for move in create.product_moves_picking:
                self.pool.get('stock.move.memory.picking').write(cr, uid, [move.id], {'quantity': move.ordered_quantity})
        if create.product_moves_ppl:
            for move in create.product_moves_ppl:
                self.pool.get('stock.move.memory.ppl').write(cr, uid, [move.id], {'quantity': move.ordered_quantity})
        if create.product_moves_families:
            for move in create.product_moves_families:
                self.pool.get('stock.move.memory.families').write(cr, uid, [move.id], {'quantity': move.ordered_quantity})
        if create.product_moves_returnproducts:
            for move in create.product_moves_returnproducts:
                self.pool.get('stock.move.memory.returnproducts').write(cr, uid, [move.id], {'quantity': move.ordered_quantity})
        return self.pool.get('wizard').open_wizard(cr, uid, [ids[0]], w_type='update', context=context)

    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}

        # we need the step info
        assert 'step' in context, 'Step not defined in context'
        step = context['step']

        pick_obj = self.pool.get('stock.picking')
        res = super(create_picking, self).default_get(cr, uid, fields, context=context)
        picking_ids = context.get('active_ids', [])
        if not picking_ids:
            return res

        result = []
        if step in ('create', 'validate', 'ppl1', 'returnproducts'):
            # memory moves wizards
            # data generated from stock.moves
            for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                result.extend(self.__create_partial_picking_memory(pick, step, context=context))
        elif step in ('ppl2'):
            # pack families wizard
            # data generated from previous wizard data
            for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                result.extend(self.__create_pack_families_memory(pick, context=context))

        if 'product_moves_picking' in fields and step in ('create', 'validate'):
            res.update({'product_moves_picking': result})

        if 'product_moves_ppl' in fields and step in ('ppl1'):
            res.update({'product_moves_ppl': result})

        if 'product_moves_returnproducts' in fields and step in ('returnproducts'):
            res.update({'product_moves_returnproducts': result})

        if 'product_moves_families' in fields and step in ('ppl2'):
            res.update({'product_moves_families': result})

        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})

        return res

    def __create_partial_picking_memory(self, pick, step, context=None):
        '''
        generates the memory objects data depending on wizard step

        - wizard_id seems to be filled automatically
        '''
        assert context, 'No context defined'
        assert 'step' in context, 'No step defined in context'
        step = context['step']

        # list for the current pick object
        result = []
        for move in pick.move_lines:
            if move.state in ('done', 'cancel', 'confirmed', 'draft') or move.product_qty == 0.00:
                continue
            move_memory = {
                'line_number': move.line_number,
                'product_id' : move.product_id.id,
                'asset_id': move.asset_id.id,
                'composition_list_id': move.composition_list_id.id,
                'ordered_quantity' : move.product_qty,
                'uom_ordered': move.product_uom.id,
                'product_uom' : move.product_uom.id,
                'prodlot_id' : move.prodlot_id.id,
                'move_id' : move.id,
                # specific management rules
                'expiry_date': move.expired_date,
            }
            if step == 'ppl1':
                move_memory['quantity'] = move.product_qty

            # the first wizard of ppl, we set default values as everything is packed in one pack
#            if step == 'ppl1':
#                move_memory.update({'qty_per_pack': move.product_qty, 'from_pack': 1, 'to_pack': 1})
            # append the created dict
            result.append(move_memory)

        # return the list of dictionaries
        return result

    def __create_pack_families_memory(self, pick, context=None):
        '''
        generates the memory objects data depending on wizard step

        - wizard_id seems to be filled automatically
        '''
        assert context, 'No context defined'
        assert 'step' in context, 'No step defined in context'
        assert 'partial_datas_ppl1' in context, 'No partial data from step1'
        partial_datas_ppl1 = context['partial_datas_ppl1']

        # list for the current pick object
        result = []
        from_packs = partial_datas_ppl1[pick.id].keys()
        # we want the lines sorted in from_pack order
        from_packs.sort()
        for from_pack in from_packs:
            for to_pack in partial_datas_ppl1[pick.id][from_pack]:
                family_memory = {
                    'from_pack': from_pack,
                    'to_pack': to_pack, }

                # append the created dict
                result.append(family_memory)

        # return the list of dictionaries
        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # integrity check
        assert context, 'No context defined'
        # call super
        result = super(create_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # working objects
        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)
        assert 'step' in context, 'No step defined in context'
        step = context['step']

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        # get picking subtype
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            picking_subtype = pick.subtype

        # select field to display
        if picking_subtype == 'picking':
            field = 'picking'
        elif picking_subtype == 'ppl':
            if step == 'ppl1':
                field = 'ppl'
            elif step == 'ppl2':
                field = 'families'
            elif step == 'returnproducts':
                field = 'returnproducts'

        _moves_arch_lst = """<form string="%s">""" % (_('Process Document'),)

        if step in ['create', 'validate', 'returnproducts']:
            _moves_arch_lst += """
                <button name="select_all" string="%s"
                    colspan="1" type="object"  icon="gtk-jump-to" />
                <button name="deselect_all" string="%s"
                    colspan="1" type="object" icon="gtk-undo" />""" % (_('Copy all'), _('Clear all'))

        _moves_arch_lst += """
                <field name="date" invisible="1"/>
                <separator colspan="4" string="%s"/>
                <field name="product_moves_%s" colspan="4" nolabel="1" mode="tree,form"></field>
                """ % (_('Products'), field)

        _moves_fields = result['fields']

        # add field related to picking type only
        _moves_fields.update({
            'product_moves_' + field: {'relation': 'stock.move.memory.' + field, 'type' : 'one2many', 'string' : 'Product Moves'},
        })

        # specify the button according to the screen
        # picking, two wizard steps
        # refactoring is needed here !
        if picking_subtype == 'picking':
            if step == 'create':
                button = ('do_create_picking', _('Create Picking'))
            elif step == 'validate':
                button = ('do_validate_picking', _('Validate Picking'))
        # ppl, two wizard steps
        elif picking_subtype == 'ppl':
            if step == 'ppl1':
                button = ('do_ppl1', _('Next'))
            if step == 'ppl2':
                button = ('do_ppl2', _('Validate PPL'))
            if step == 'returnproducts':
                button = ('do_return_products', _('Return'))

        else:
            button = ('undefined', 'Undefined')

        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="4" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="%s" />""" % _('_Cancel')

        if step == 'ppl2':
            _moves_arch_lst += """
                <button name="back_ppl1" string="%s"
                    colspan="1" type="object" icon="gtk-go-back" />""" % _('Previous')


        _moves_arch_lst += """
                <button name="%s" string="%s"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>""" % button

        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        # add messages from specific management rules
        result = self.pool.get('stock.partial.picking').add_message(cr, uid, result, context=context)
        return result

    def select_all(self, cr, uid, ids, context=None):
        '''
        select all buttons, write max qty in each line

        should be modified for more generic way, with something like:

        fields = self.fields_get(cr, uid, context=context)
        # loop through fields, if one2many, we set the values for all lines
        for key in fields.keys():
            type = fields[key]['type']
            if type in ['one2many']:
                lines = getattr(wiz, key)
                for line in lines:
                    line.write({'quantity': line.initial_qty}, context=context)

        the problem is that in the different wizard we use different fields for
        selected qty (quantity, qty_to_return, ...). This should be unified as well
        to allow previous idea.
        '''
        # picking ids
        picking_ids = context['active_ids']
        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.product_moves_picking:
                # get the qty from the corresponding stock move
                original_qty = line.ordered_quantity
                line.write({'quantity':original_qty, }, context=context)
            for line in wiz.product_moves_returnproducts:
                line.write({'qty_to_return':line.ordered_quantity, }, context=context)
        # update the current wizard
        return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)

    def deselect_all(self, cr, uid, ids, context=None):
        '''
        deselect all buttons, write 0 qty in each line
        '''
        # picking ids
        picking_ids = context['active_ids']
        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.product_moves_picking:
                line.write({'quantity':0.0, }, context=context)
            for line in wiz.product_moves_returnproducts:
                line.write({'qty_to_return':0.0, }, context=context)
        # update the current wizard
        return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)

    def generate_data_from_partial(self, cr, uid, ids, context=None):
        '''
        data is located in product_moves_ppl

        we generate the data structure from the first ppl wizard (ppl1)

        structure :
        {pick_id: {from_pack: {to_pack: {move_id: [{partial},]}}}}

        data are indexed by pack_id, then by pack_family information (from_pack/to_pack)
        and finally by move_id. Move_id indexing is added because within one
        pack sequence we can find the same move_id multiple time thanks to split function.

        with partial beeing the info for one stock.move.memory.ppl
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'

        pick_obj = self.pool.get('stock.picking')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # returned datas
        partial_datas_ppl1 = {}

        # picking ids
        picking_ids = context['active_ids']
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas_ppl1[pick.id] = {}
            # ppl moves
            memory_moves_list = partial.product_moves_ppl
            # organize data according to from pack / to pack
            for move in memory_moves_list:
                partial_datas_ppl1[pick.id] \
                    .setdefault(move.from_pack, {}) \
                    .setdefault(move.to_pack, {}) \
                    .setdefault(move.move_id.id, []).append({'memory_move_id': move.id,
                                                             'product_id': move.product_id.id,
                                                             'product_qty': move.ordered_quantity,
                                                             'product_uom': move.product_uom.id,
                                                             'prodlot_id': move.prodlot_id.id,
                                                             'asset_id': move.asset_id.id,
                                                             'line_number': move.line_number,
                                                             'composition_list_id': move.composition_list_id.id,
                                                             'move_id': move.move_id.id,
                                                             'qty_per_pack': move.qty_per_pack,
                                                             'from_pack': move.from_pack,
                                                             'to_pack': move.to_pack,
                                                             })

        return partial_datas_ppl1

    def update_data_from_partial(self, cr, uid, ids, context=None):
        '''
        update the list corresponding to moves for each sequence with ppl2 information

        generated structure from step ppl1 wizard is updated with step ppl2 wizard,
        the partial dictionaries are updated with pack_family related information

        structure :
        {pick_id: {from_pack: {to_pack: {move_id: [{partial},]}}}}
        '''
        assert context, 'no context defined'
        assert 'partial_datas_ppl1' in context, 'partial_datas_ppl1 not in context'
        family_obj = self.pool.get('stock.move.memory.families')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # returned datas
        partial_datas_ppl1 = context['partial_datas_ppl1']
        # picking ids
        picking_ids = context['active_ids']
        for picking_id in picking_ids:
            # for each picking
            for from_pack in partial_datas_ppl1[picking_id]:
                for to_pack in partial_datas_ppl1[picking_id][from_pack]:
                    # find corresponding sequence info
                    family_ids = family_obj.search(cr, uid, [('wizard_id', '=', ids[0]), ('from_pack', '=', from_pack), ('to_pack', '=', to_pack)], context=context)
                    # only one line should match
                    assert len(family_ids) == 1, 'No the good number of families : %i' % len(family_ids)
                    family = family_obj.read(cr, uid, family_ids, ['pack_type', 'length', 'width', 'height', 'weight'], context=context)[0]
                    # remove id key
                    family['memory_move_id'] = family.pop('id')
                    for move in partial_datas_ppl1[picking_id][from_pack][to_pack]:
                        for partial in partial_datas_ppl1[picking_id][from_pack][to_pack][move]:
                            partial.update(family)

    def set_integrity_status(self, cr, uid, ids, field_name, status='empty', context=None):
        '''
        for all moves set the status to ok (default value) or other if specified
        '''
        for wiz in self.browse(cr, uid, ids, context=context):
            for memory_move in getattr(wiz, field_name):
                memory_move.write({'integrity_status': status, }, context=context)

    def set_integrity_status_for_empty_moves(self, cr, uid, ids, field_name, status='empty_picking', context=None):
        '''
        for all moves set the status to empty_picking if move qty is 0

        deprecated - not used, by default the validation is empty not ok
        '''
        for wiz in self.browse(cr, uid, ids, context=context):
            for memory_move in getattr(wiz, field_name):
                if not memory_move.quantity:
                    memory_move.write({'integrity_status': status, }, context=context)

    def integrity_check_create_picking(self, cr, uid, ids, data, context=None):
        '''
        integrity check on create picking data
        - rule #1: no negative values (<0)
        - rule #2: at least one positive value (>0)

        return True/False
        '''
        memory_move_obj = self.pool.get('stock.move.memory.picking')
        # validate the data
        for picking_data in data.values():
            # total sum not including negative values
            sum_qty = 0
            # flag to detect negative values
            negative_value = False
            for move_data in picking_data.values():
                for list_data in move_data:
                    # rule #1: quantity check
                    if list_data['product_qty'] < 0.0:
                        # a negative value has been selected, update the memory line
                        # update the new value for integrity check with 'negative' value (selection field)
                        negative_value = True
                        memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'negative', }, context=context)
                    else:
                        # rule #2: no empty picking
                        sum_qty += list_data['product_qty']
            # if error, return False
            if not sum_qty or negative_value:
                return False
        return True

    def integrity_check_prodlot(self, cr, uid, ids, data, validate=True, context=None):
        '''
        check production lot
        - rule #1 a batch management product needs a standard production lot ***ONLY AT PICKING VALIDATION STAGE
        - rule #2 a expiry date product needs an internal production lot ***ONLY AT PICKING VALIDATION STAGE
        - rule #3 a not lot managed product does not allow production lot
        - rule #4 a batch management product does not allow internal production lot
        - rule #5 a expiry date product does not allow standard production lot

        - the production lot is mandatory only if it is the validation stage
        '''
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        memory_move_obj = self.pool.get('stock.move.memory.picking')
        lot_obj = self.pool.get('stock.production.lot')
        # flag to detect missing prodlot
        missing_lot = False
        # has prodlot but should not
        lot_not_needed = False
        # wrong production lot type
        wrong_lot_type = False
        # validate the data
        for picking_data in data.values():
            prodlot_integrity = {}
            for move_data in picking_data.values():
                for list_data in move_data:
                    # product id must exist
                    prod_id = list_data['product_id']
                    prod = prod_obj.browse(cr, uid, prod_id, context=context)
                    # a production lot is defined, corresponding checks
                    if list_data['prodlot_id']:
                        if list_data['location_id']:
                            context.update({'location_id': list_data['location_id']})
                        lot = lot_obj.browse(cr, uid, list_data['prodlot_id'], context=context)
                        # a prod lot is defined, the product must be either perishable or batch_management
                        if not (prod.perishable or prod.batch_management):
                            # rule #3: should not have production lot
                            lot_not_needed = True
                            memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'no_lot_needed', }, context=context)
                        # rule #5: perishable -> the prod lot must be of type 'internal'
                        if prod.perishable and not prod.batch_management and lot.type != 'internal':
                            wrong_lot_type = True
                            memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'wrong_lot_type_need_internal', }, context=context)
                        # rule #4: batch_management -> the prod lot must be of type 'standard'
                        if prod.batch_management and lot.type != 'standard':
                            wrong_lot_type = True
                            memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'wrong_lot_type_need_standard', }, context=context)

                        if list_data['location_id']:
                            loc_id = list_data['location_id']
                            # Add a check on prodlot quantity
                            if lot.id not in prodlot_integrity:
                                prodlot_integrity.update({lot.id: {}})
                            if loc_id not in prodlot_integrity[lot.id]:
                                prodlot_integrity[lot.id].update({loc_id: 0.00})
                            product_qty = uom_obj._compute_qty(cr, uid, list_data['product_uom'], list_data['product_qty'], lot.product_id.uom_id.id)
                            prodlot_integrity[lot.id][loc_id] += product_qty

                            if lot.stock_available < product_qty:
                                uom = self.pool.get('product.uom').browse(cr, uid, list_data['product_uom']).name
                                raise osv.except_osv(_('Processing Error'), \
                                                     _('Processing quantity %d %s for %s is larger than the available quantity in Batch Number %s (%d) !')\
                                                     % (list_data['product_qty'], uom, prod.name, \
                                                        lot.name, lot.stock_available))

                    # only mandatory at validation stage
                    elif validate:
                        # no production lot defined, corresponding checks
                        # rule #1 a batch management product needs a standard production lot
                        if prod.batch_management:
                            missing_lot = True
                            memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'missing_lot', }, context=context)
                        # rule #2 a expiry date product needs an internal production lot
                        elif prod.perishable:
                            missing_lot = True
                            memory_move_obj.write(cr, uid, [list_data['memory_move_id']], {'integrity_status': 'missing_date', }, context=context)

                # Check prodlot qty integrity
                for prodlot in prodlot_integrity:
                    for location in prodlot_integrity[prodlot]:
                        tmp_prodlot = lot_obj.browse(cr, uid, prodlot, context={'location_id': location})
                        prodlot_qty = tmp_prodlot.stock_available
                        if prodlot_qty < prodlot_integrity[prodlot][location]:
                            raise osv.except_osv(_('Processing Error'), \
                                                 _('Processing quantity %d for %s is larger than the available quantity in Batch Number %s (%d) !')\
                                                 % (prodlot_integrity[prodlot][location], tmp_prodlot.product_id.name, tmp_prodlot.name, \
                                                    prodlot_qty))

        # if error, return False
        if missing_lot or lot_not_needed or wrong_lot_type:
            return False
        return True

    def do_create_picking_first_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_create_picking: This hook's first aim was to complete the module msf_cross_docking
        '''
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'partial_datas missing'

        return partial_datas

    def do_create_picking(self, cr, uid, ids, context=None):
        '''
        create the picking ticket from selected stock moves
        -> only related to 'out' type stock.picking

        - transform data from wizard
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        # picking ids
        picking_ids = context['active_ids']
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_picking'

        pick_obj = self.pool.get('stock.picking')
        # partial datas
        partial_datas = {}

        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            total_qty = 0
            # for each picking
            partial_datas[pick.id] = {}
            # out moves for delivery
            memory_moves_list = partial.product_moves_picking
            # organize data according to move id
            for move in memory_moves_list:
                # !!! only take into account if the quantity is greater than 0 !!!
                if move.quantity:
                    total_qty += move.quantity
                    partial_datas[pick.id].setdefault(move.move_id.id, []).append({'memory_move_id': move.id,
                                                                                   'product_id': move.product_id.id,
                                                                                   'product_qty': move.quantity,
                                                                                   'product_uom': move.product_uom.id,
                                                                                   'prodlot_id': move.prodlot_id.id,
                                                                                   'line_number': move.line_number,
                                                                                   'location_id': move.location_id.id,
                                                                                   'asset_id': move.asset_id.id,
                                                                                   'composition_list_id': move.composition_list_id.id,
                                                                                   })
                    # override : add hook call
                    partial_datas = self.do_create_picking_first_hook(cr, uid, context, move=move, partial_datas=partial_datas)
            if not total_qty and not context.get('yml_test'):
                raise osv.except_osv(_('Processing Error'), _("You have to enter the quantities you want to process before processing the move"))
        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - quantities
        quantity_check = self.integrity_check_create_picking(cr, uid, ids, partial_datas, context=context)
        # prodlot - in separate method because is not checked at picking ticket creation
        prodlot_check = self.integrity_check_prodlot(cr, uid, ids, partial_datas, validate=False, context=context)
        if not quantity_check or not prodlot_check:
            # the windows must be updated to trigger tree colors - so no raise
            return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_create_picking(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))

    def quick_mode(self, cr, uid, ppl, context=None):
        '''
        we do the quick mode, the ppl step is performed automatically
        '''
        assert context, 'missing Context'

        # set the corresponding ppl object
        context['active_ids'] = [ppl.id]

        # set the step
        context['step'] = 'ppl1'
        # create a create_picking object for ppl1
        wizard_ppl1 = self.create(cr, uid, {'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        # the default user values are used, they represent all packs in one pack sequence (pack family from:1, to:1)
        # with a quantity per pack equal to the quantity
        # these values are set in the create method of memory moves

        # ppl1
        # the wizard for ppl2 step is created here, the step is updated there also
        wizard_dic = self.do_ppl1(cr, uid, [wizard_ppl1], context=context)
        partial_datas_ppl1 = wizard_dic['context']['partial_datas_ppl1']
        wizard_ppl2 = wizard_dic['res_id']
        # the default user values are used, all the pack families values are set to zero, False (weight, height, ...)

        # ppl2
        self.do_ppl2(cr, uid, [wizard_ppl2], context=dict(context, partial_datas_ppl1=partial_datas_ppl1))

    def do_validate_picking_first_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_validate_picking: This hook's first aim was to complete the module msf_cross_docking
        '''
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'partial_datas missing'

        return partial_datas

    def do_validate_picking(self, cr, uid, ids, context=None):
        '''
        create the picking ticket from selected stock moves
        -> only related to 'out' type stock.picking

        - transform data from wizard
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        # picking ids
        picking_ids = context['active_ids']
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_picking'

        pick_obj = self.pool.get('stock.picking')

        # partial datas
        partial_datas = {}

        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            total_qty = 0.00
            # for each picking
            partial_datas[pick.id] = {}
            # out moves for delivery
            memory_moves_list = partial.product_moves_picking
            # organize data according to move id
            for move in memory_moves_list:
                total_qty += move.quantity
                partial_datas[pick.id].setdefault(move.move_id.id, []).append({'memory_move_id': move.id,
                                                                               'product_id': move.product_id.id,
                                                                               'product_qty': move.quantity,
                                                                               'product_uom': move.product_uom.id,
                                                                               'prodlot_id': move.prodlot_id.id,
                                                                               'location_id': move.location_id.id,
                                                                               'line_number': move.line_number,
                                                                               'asset_id': move.asset_id.id,
                                                                               'composition_list_id': move.composition_list_id.id,
                                                                               })
                # override : add hook call
                partial_datas = self.do_validate_picking_first_hook(cr, uid, context, move=move, partial_datas=partial_datas)
            if not total_qty:
                raise osv.except_osv(_('Processing Error'), _("You have to enter the quantities you want to process before processing the move"))
        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - quantities
        quantity_check = self.integrity_check_create_picking(cr, uid, ids, partial_datas, context=context)
        # prodlot - in separate method because is not checked at picking ticket creation
        prodlot_check = self.integrity_check_prodlot(cr, uid, ids, partial_datas, context=context)
        if not quantity_check or not prodlot_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_validate_picking(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))

    def integrity_check_return_products(self, cr, uid, ids, data, context=None):
        '''
        integrity check on create picking data
        - #1 no negative values (<0)
        - #2 at least one positive one (>0)
        - #3 no more than available quantity

        return True/Fals
        '''
        memory_move_obj = self.pool.get('stock.move.memory.returnproducts')
        # validate the data
        for picking_data in data.values():
            # total sum not including negative values
            sum_qty = 0
            # flag to detect negative values
            negative_value = False
            # flag to detect excessive return quantity
            too_much = False
            for move_data in picking_data.values():
                # quantity check
                if move_data['qty_to_return'] < 0.0:
                    # a negative value has been selected, update the memory line
                    # update the new value for integrity check with 'negative' value (selection field)
                    negative_value = True
                    memory_move_obj.write(cr, uid, [move_data['memory_move_id']], {'integrity_status': 'negative', }, context=context)
                elif move_data['qty_to_return'] > move_data['product_qty']:
                    # cannot return more products than available
                    too_much = True
                    memory_move_obj.write(cr, uid, [move_data['memory_move_id']], {'integrity_status': 'return_qty_too_much', }, context=context)
                else:
                    sum_qty += move_data['qty_to_return']
            # if error, return False
            if not sum_qty or negative_value or too_much:
                return False
        return True

    def do_return_products(self, cr, uid, ids, context=None):
        '''
        process data and call do_return_products from stock picking

        data structure:
        {picking_id: {move_id: {data}}}
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'

        pick_obj = self.pool.get('stock.picking')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {}
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_returnproducts'

        # picking ids
        picking_ids = context['active_ids']
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas[pick.id] = {}
            # out moves for delivery
            memory_moves_list = partial.product_moves_returnproducts
            # organize data according to move id
            for move in memory_moves_list:
                if move.qty_to_return:
                    partial_datas[pick.id][move.move_id.id] = {'memory_move_id': move.id,
                                                               'product_id': move.product_id.id,
                                                               'product_qty': move.ordered_quantity,
                                                               'product_uom': move.product_uom.id,
                                                               'prodlot_id': move.prodlot_id.id,
                                                               'asset_id': move.asset_id.id,
                                                               'line_number': move.line_number,
                                                               'composition_list_id': move.composition_list_id.id,
                                                               'qty_to_return': move.qty_to_return,
                                                               }

        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - quantities -> no prodlot check as the screen is readonly
        quantity_check = self.integrity_check_return_products(cr, uid, ids, partial_datas, context=context)
        if not quantity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)
        return pick_obj.do_return_products(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))

    def integrity_check_sequences(self, cr, uid, ids, data, context=None):
        '''
        integrity check on ppl1 data for sequence validation
        - #1 first from value must be 1
        - #2 sequence can share the exact same from/to value
        - #3 the numbering  must be a monotonically increasing function
        - #4 there must be no gap within sequence

        return True/False

        {145: {1: {1: {
        417: [{'memory_move_id': 1, 'asset_id': False, 'from_pack': 1, 'prodlot_id': 28, 'qty_per_pack': 10.0,'product_id': 68, 'product_uom': 1, 'product_qty': 10.0, 'to_pack': 1, 'move_id': 417}],
        418: [{'memory_move_id': 2, 'asset_id': False, 'from_pack': 1, 'prodlot_id': 30, 'qty_per_pack': 20.0, 'product_id': 69, 'product_uom': 1, 'product_qty': 20.0, 'to_pack': 1, 'move_id': 418}]
        }}}}
        '''
        memory_move_obj = self.pool.get('stock.move.memory.ppl')
        # validate the data
        for picking_data in data.values():
            # list of sequences for each picking
            sequences = []
            # flag for detecting missing 1 initial from
            missing_1 = False
            # flag for detecting to value smaller than from value
            to_samller_than_from = False
            # flag for detecting overlapping sequences
            overlap = False
            # flag for detecting gap
            gap = False
            # gather the sequences
            for from_data in picking_data.values():
                for to_data in from_data.values():
                    for move_data in to_data.values():
                        for partial in move_data:
                            # we have to treat all partial (split) data for each move as many sequence can exists for the same move
                            # [0]: FROM PACK / [1]: TO PACK / [2]: MEMORY MOVE ID
                            sequences.append((partial['from_pack'], partial['to_pack'], partial['memory_move_id']))
            # if no data, we return False
            if not sequences:
                return False
            # sort the sequences according to from value
            sequences = sorted(sequences, key=lambda seq: seq[0])

            # rule #1, the first from value must be equal to 1
            if sequences[0][0] != 1:
                missing_1 = True
                memory_move_obj.write(cr, uid, [sequences[0][2]], {'integrity_status': 'missing_1', }, context=context)
            # go through the list of sequences applying the rules
            for i in range(len(sequences)):
                seq = sequences[i]
                # rules 2-3 applies from second element
                if i > 0:
                    # previsous sequence
                    seqb = sequences[i - 1]
                    # rule #2: if from[i] == from[i-1] -> to[i] == to[i-1]
                    if (seq[0] == seqb[0]) and not (seq[1] == seqb[1]):
                        overlap = True
                        memory_move_obj.write(cr, uid, [seq[2]], {'integrity_status': 'overlap', }, context=context)
                    # rule #3: if from[i] != from[i-1] -> from[i] == to[i-1]+1
                    if (seq[0] != seqb[0]) and not (seq[0] == seqb[1] + 1):
                        if seq[0] < seqb[1] + 1:
                            overlap = True
                            memory_move_obj.write(cr, uid, [seq[2]], {'integrity_status': 'overlap', }, context=context)
                        if seq[0] > seqb[1] + 1:
                            gap = True
                            memory_move_obj.write(cr, uid, [seq[2]], {'integrity_status': 'gap', }, context=context)
                # rule #4: to[i] >= from[i]
                if not (seq[1] >= seq[0]):
                    to_samller_than_from = True
                    memory_move_obj.write(cr, uid, [seq[2]], {'integrity_status': 'to_smaller_than_from', }, context=context)
            # if error, return False
            if missing_1 or to_samller_than_from or overlap or gap:
                return False
        return True

    def do_ppl1(self, cr, uid, ids, context=None):
        '''
        - generate data
        - call stock.picking>do_ppl1
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        # objects
        pick_obj = self.pool.get('stock.picking')
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_ppl'

        # picking ids
        picking_ids = context['active_ids']
        # generate data structure
        partial_datas_ppl1 = self.generate_data_from_partial(cr, uid, ids, context=context)

        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - sequence -> no prodlot check as the screen is readonly
        sequence_check = self.integrity_check_sequences(cr, uid, ids, partial_datas_ppl1, context=context)
        if not sequence_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)

        # call stock_picking method which returns action call
        return pick_obj.do_ppl1(cr, uid, picking_ids, context=dict(context, partial_datas_ppl1=partial_datas_ppl1))

    def back_ppl1(self, cr, uid, ids, context=None):
        '''
        call back ppl1 step wizard
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'

        wiz_obj = self.pool.get('wizard')

        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)

    def integrity_check_weight(self, cr, uid, ids, data, context=None):
        '''
        integrity check on ppl2 data for weight validation
        - weight must exist if not quick flow type
        return True/False

        {145: {1: {1: {
        417: [{'memory_move_id': 1, 'asset_id': False, 'from_pack': 1, 'prodlot_id': 28, 'qty_per_pack': 10.0,'product_id': 68, 'product_uom': 1, 'product_qty': 10.0, 'to_pack': 1, 'move_id': 417}],
        418: [{'memory_move_id': 2, 'asset_id': False, 'from_pack': 1, 'prodlot_id': 30, 'qty_per_pack': 20.0, 'product_id': 69, 'product_uom': 1, 'product_qty': 20.0, 'to_pack': 1, 'move_id': 418}]
        }}}}
        '''
        memory_move_obj = self.pool.get('stock.move.memory.families')
        move_obj = self.pool.get('stock.move')
        for picking_data in data.values():
            # flag for missing weight
            missing_weight = False
            for from_data in picking_data.values():
                for to_data in from_data.values():
                    for move_data in to_data.values():
                        for partial in move_data:
                            if partial['weight'] <= 0:
                                move = move_obj.browse(cr, uid, partial['move_id'], context=context)
                                flow_type = move.picking_id.flow_type
                                if flow_type != 'quick':
                                    missing_weight = True
                                    memory_move_obj.write(cr, uid, [partial['memory_move_id']], {'integrity_status': 'missing_weight', }, context=context)
        # return false if weight is missing
        if missing_weight:
            return False
        return True

    def do_ppl2(self, cr, uid, ids, context=None):
        '''
        - update partial_datas_ppl1
        - call stock.picking>do_ppl2
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        pick_obj = self.pool.get('stock.picking')
        # name of the wizard field for moves (one2many)
        field_name = 'product_moves_families'
        # picking ids
        picking_ids = context['active_ids']
        # update data structure
        self.update_data_from_partial(cr, uid, ids, context=context)
        # integrity check on wizard data
        partial_datas_ppl1 = context['partial_datas_ppl1']
        # reset the integrity status of all lines
        self.set_integrity_status(cr, uid, ids, field_name=field_name, context=context)
        # integrity check on wizard data - sequence -> no prodlot check as the screen is readonly
        weight_check = self.integrity_check_weight(cr, uid, ids, partial_datas_ppl1, context=context)
        if not weight_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_ppl2(cr, uid, picking_ids, context=context)

create_picking()
