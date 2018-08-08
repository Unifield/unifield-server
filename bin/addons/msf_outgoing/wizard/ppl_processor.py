# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

from tools.translate import _
from msf_outgoing import PACK_INTEGRITY_STATUS_SELECTION

class ppl_processor(osv.osv):
    """
    Wizard to process the Pre-Packing List
    """
    _name = 'ppl.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process the third step of the P/P/S'

    _columns = {
        'move_ids': fields.one2many(
            'ppl.move.processor',
            'wizard_id',
            string='Moves',
            help="Lines of the PPL processor wizard",
        ),
        'family_ids': fields.one2many(
            'ppl.family.processor',
            'wizard_id',
            string='Families',
            help="Pack of products",
        ),
        'draft_step1': fields.boolean('Draft', help='Usefull for internal management of save as draft order'),
        'draft_step2': fields.boolean('Draft', help='Usefull for internal management of save as draft order'),
    }

    _defaults = {
        'draft_step1': lambda *a: False,
        'draft_step2': lambda *a: False,
    }

    def write(self, cr, uid, ids, vals, context=None):
        if 'move_ids' in vals:
            vals['draft_step2'] = False
        return super(ppl_processor, self).write(cr, uid, ids, vals, context=context)

    def do_reset_step1(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft_step1': False, 'draft_step2': False}, context=context)

        return self.pool.get('stock.picking').ppl(cr, uid, pick_id, context=context)

    def do_save_draft_step1(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'draft_step1': True}, context=context)

        return {}

    def do_reset_step2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft_step2': False}, context=context) #TODO Do not reset step 1 ?

        return self.pool.get('stock.picking').ppl(cr, uid, pick_id, context=context)

    def do_save_draft_step2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'draft_step2': True, 'draft_step1': True}, context=context)

        return {}



    def do_check_ppl(self, cr, uid, ids, context=None):
        """
        Run a check of the integrity of lines
        """
        if context is None:
            context = {}

        res = self.do_ppl_step1(cr, uid, ids, context=context, just_check=True)

        return res

    def check_sequences(self, cr, uid, sequences, ppl_move_obj, context=None):
        """
        check pack sequences integrity
        sequences is a list of tuples: [(from, to, internal_id), ...]
        """
        missing_ids = []
        to_smaller_ids = []
        overlap_ids = []
        gap_ids = []
        # Sort the sequence according to from value
        sequences = sorted(sequences, key=lambda seq: seq[0])

        # Rule #1, the first from value must be equal o 1
        if sequences[0][0] != 1:
            missing_ids.append(sequences[0][2])

        # Go through the list of sequences applying the rules
        for i in range(len(sequences)):
            seq = sequences[i]
            # Rules #2-#3 applies from second element
            if i > 0:
                # Previous sequence
                seqb = sequences[i - 1]
                # Rule #2: if from[i] == from[i-1] -> to[i] == to[i-1]
                if (seq[0] == seqb[0]) and not (seq[1] == seqb[1]):
                    overlap_ids.append(seq[2])
                # Rule #3: if from[i] != from[i-1] -> from[i] == to[i-1]+1
                if (seq[0] != seqb[0]) and not (seq[0] == seqb[1] + 1):
                    if seq[0] < seqb[1] + 1:
                        overlap_ids.append(seq[2])
                    if seq[0] > seqb[1] + 1:
                        gap_ids.append(seq[2])
            # rule #4: to[i] >= from[i]
            if not (seq[1] >= seq[0]):
                to_smaller_ids.append(seq[2])
        ok = True
        if missing_ids:
            ppl_move_obj.write(cr, uid, missing_ids, {'integrity_status': 'missing_1'}, context=context)
            ok = False

        if to_smaller_ids:
            ppl_move_obj.write(cr, uid, to_smaller_ids, {'integrity_status': 'to_smaller_than_from'}, context=context)
            ok = False

        if overlap_ids:
            ppl_move_obj.write(cr, uid, overlap_ids, {'integrity_status': 'overlap'}, context=context)
            ok = False

        if gap_ids:
            ppl_move_obj.write(cr, uid, gap_ids, {'integrity_status': 'gap'}, context=context)
            ok = False

        return ok

    def do_ppl_step1(self, cr, uid, ids, context=None, just_check=False):
        """
        Make some integrity checks and call the do_ppl_step1 method of the stock.picking object
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        ppl_move_obj = self.pool.get('ppl.move.processor')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        ok_ids = []
        ok = True
        for wizard in self.browse(cr, uid, ids, context=context):
            # List of sequences
            sequences = []

            for line in wizard.move_ids:
                sequences.append((line.from_pack, line.to_pack, line.id))
                ok_ids.append(line.id)

            # If no data, we return False
            if not sequences:
                return False

            ok = ok and self.check_sequences(cr, uid, sequences, ppl_move_obj)

        if ok and just_check:
            ppl_move_obj.write(cr, uid, ok_ids, {'integrity_status': 'empty'}, context=context)

        if not ok or just_check:
            view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step1_form_view')[1]
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': [view_id],
                'target': 'new',
                'res_id': ids[0],
                'context': context,
            }

        # Call stock_picking method which returns action call
        return picking_obj.do_ppl_step1(cr, uid, ids, context=context)

    def do_ppl_step2(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the method do_ppl_step2 of stock.picking document
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        family_obj = self.pool.get('ppl.family.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft_step1': False, 'draft_step2': False}, context=context)

        family_no_weight = []
        for wizard in self.browse(cr, uid, ids, context=context):
            treated_moves = []
            for family in wizard.family_ids:
                if family.weight <= 0.00:
                    family_no_weight.append(family.id)

                # Integrity check on stock moves
                for line in family.move_ids:
                    move = line.move_id
                    treated_moves.append(move.id)
                    error_word = ''

                    if line.product_id.id != move.product_id.id:
                        error_word = 'product'

                    if line.uom_id.id != move.product_uom.id:
                        error_word = 'UoM'

                    if line.prodlot_id.id != move.prodlot_id.id:
                        error_word = 'Batch number'

                    if line.asset_id.id != move.asset_id.id:
                        error_word = 'asset'

                    if line.composition_list_id.id != move.composition_list_id.id:
                        error_word = 'kit composition list'


                    if error_word:
                        error_dict = {
                            'word': error_word,
                            'l_num': line.line_number,
                        }
                        raise osv.except_osv(
                            _('Processing Error'),
                            _('Line %(l_num)s: The processed %(word)s is not the same as the initial move %(word)s.') % error_dict,
                        )

            nb_pick_moves = move_obj.search(cr, uid, [
                ('picking_id', '=', wizard.picking_id.id),
                ('state', 'in', ['confirmed', 'assigned']),
            ], count=True, context=context)

            if nb_pick_moves != len(set(treated_moves)):
                raise osv.except_osv(
                    _('Processing Error'),
                    _('The number of treated moves (%s) are not compatible with the number of moves in PPL (%s).') % (len(set(treated_moves)), nb_pick_moves),
                )

        if family_no_weight:
            family_obj.write(cr, uid, family_no_weight, {'integrity_status': 'missing_weight'}, context=context)
            # Return to PPL - Step 2 wizard
            return picking_obj.ppl_step2(cr, uid, ids, context=context)

        # Call the stock.picking method
        return picking_obj.do_ppl_step2(cr, uid, ids, context=context)

    def do_ppl_back(self, cr, uid, ids, context=None):
        """
        Return to the first of the PPL processing
        """
        # Objects
        data_obj = self.pool.get('ir.model.data')

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step1_form_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_id': ids[0],
            'target': 'new',
            'context': context,
        }

ppl_processor()


class ppl_family_processor(osv.osv):
    """
    PPL family that merge some stock moves into one pack
    """
    _name = 'ppl.family.processor'
    _description = 'PPL family'
    _rec_name = 'from_pack'

    _order = 'from_pack, id'

    _columns = {
        'wizard_id': fields.many2one(
            'ppl.processor',
            string='Wizard',
            required=True,
            ondelete='cascade',
            help="PPL processing wizard",
        ),
        'from_pack': fields.integer(string='From p.'),
        'to_pack': fields.integer(string='To p.'),
        'pack_type': fields.many2one(
            'pack.type',
            string='Pack Type',
            ondelete='set null',
        ),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        'integrity_status': fields.selection(
            string='Integrity status',
            selection=[
                ('empty', ''),
                ('missing_weight', 'Weight is missing'),
            ],
            readonly=True,
        ),
        'move_ids': fields.one2many(
            'ppl.move.processor',
            'pack_id',
            string='Moves',
        ),
    }

    _defaults = {
        'integrity_status': 'empty',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if 'weight' in vals:
            vals['integrity_status'] = 'empty' if (vals['weight'] and vals['weight'] > 0) else 'missing_weight'
        return super(ppl_family_processor, self).write(cr, uid, ids, vals, context=context)

    """
    Controller methods
    """
    def onchange_pack_type(self, cr, uid, ids, pack_type):
        """
        Update values of the PPL family from the stock pack selecetd
        """
        # Objects
        p_type_obj = self.pool.get('pack.type')

        res = {}

        if pack_type :
            # if 'pack_type' is not a list, turn it into list
            if isinstance(pack_type, (int, long)):
                pack_type = [pack_type]

            p_type = p_type_obj.browse(cr, uid, pack_type[0])

            res.update({
                'value': {
                    'length': p_type.length,
                    'width': p_type.width,
                    'height': p_type.height,
                },
            })

        return res

ppl_family_processor()


class ppl_move_processor(osv.osv):
    """
    Wizard lines to process a Pre-Packing List line
    """
    _name = 'ppl.move.processor'
    _inherit = 'stock.move.processor'
    _description = 'Wizard to process a line on the third step of the P/P/S'

    def _get_pack_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns the number of packs
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'num_of_packs': 0,
                'qty_per_pack': 0,
            }

            num_packs = line.to_pack - line.from_pack + 1
            if num_packs:
                qty_per_pack = line.quantity / num_packs
            else:
                qty_per_pack = 0

            res[line.id].update({
                'num_of_packs': num_packs,
                'qty_per_pack': qty_per_pack,
            })

        return res

    def _get_move_info(self, cr, uid, ids, field_name, args, context=None):
        return super(ppl_move_processor, self)._get_move_info(cr, uid, ids, field_name, args, context=context)

    def _get_product_info(self, cr, uid, ids, field_name, args, context=None):
        return super(ppl_move_processor, self)._get_product_info(cr, uid, ids, field_name, args, context=context)

    _columns = {
        'wizard_id': fields.many2one(
            'ppl.processor',
            string='Wizard',
            required=True,
            readonly=True,
            select=True,
            ondelete='cascade',
            help="PPL processor wizard",
        ),
        'move_id': fields.many2one('stock.move', string='Stock move', readonly=True),
        'from_pack': fields.integer(string='From p.', required=True),
        'to_pack': fields.integer(string='To p.', required=True),
        'num_of_packs': fields.function(
            _get_pack_info,
            method=True,
            string='#Packs',
            type='integer',
            store=False,
            readonly=True,
            help="Number of packs",
            multi='pack',
        ),
        'qty_per_pack': fields.function(
            _get_pack_info,
            method=True,
            string='Qty p.p.',
            type='float',
            store=False,
            readonly=True,
            help="Quantity per pack",
            multi='pack',
        ),
        'integrity_status': fields.selection(
            string=' ',
            selection=PACK_INTEGRITY_STATUS_SELECTION,
            readonly=True,
        ),
        'pack_id': fields.many2one(
            'ppl.family.processor',
            string='Pack',
            ondelete='set null',
        ),
        'ordered_product_id': fields.function(
            _get_move_info,
            method=True,
            string='Ordered product',
            type='many2one',
            relation='product.product',
            store={
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                 'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
            },
            readonly=True,
            multi='move_info',
            help="",
        ),
        'type_check': fields.function(
            _get_move_info,
            method=True,
            string='Picking Type Check',
            type='char',
            size=32,
            store={
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['move_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
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
                'ppl.move.processor': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20),
            },
            readonly=True,
            multi='product_info',
            help="Ticked if the product is a Controlled Substance",
        ),
    }

    _defaults = {
        'integrity_status': 'empty',
    }

    """
    Model methods
    """
    def create(self, cr, uid, vals, context=None):
        """
        Default value of qty_per_pack to quantity of from_pack and to_pack to 1.
        Those fields have a constraint assigned to them, and must
        therefore be completed with default value at creation
        """
        if context is None:
            context = {}

        if not vals.get('qty_per_pack', False):
            vals['qty_per_pack'] = vals['ordered_quantity']

        if not vals.get('from_pack', False):
            vals['from_pack'] = 1

        if not vals.get('to_pack', False):
            vals['to_pack'] = 1

        if vals.get('wizard_id', False):
            rel_obj = self._columns['wizard_id']._obj
            self.pool.get(rel_obj).write(cr, uid, [vals['wizard_id']], {'draft_step2': False}, context=context)

        return super(ppl_move_processor, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Remove the integrity status value if from_pack or to_pack is changed.
        """
        if vals.get('from_pack') or vals.get('to_pack'):
            vals['integrity_status'] = 'empty'

        return super(ppl_move_processor, self).write(cr, uid, ids, vals, context=context)

    def _get_line_data(self, cr, uid, wizard=False, move=False, context=None):
        """
        Just put the stock move product quantity into the ppl.move.processor
        """
        res = super(ppl_move_processor, self)._get_line_data(cr, uid, wizard, move, context=context)

        # For Remote Warehouse purpose
        from_pack = move.from_pack
        to_pack = move.to_pack
        if from_pack == 0 or to_pack == 0:
            from_pack == 1
            to_pack == 1

        res.update({
            'quantity': move.product_qty,
            'ordered_quantity': move.product_qty,
            'from_pack': from_pack,
            'to_pack': to_pack,
            'length': move.length,
            'width': move.width,
            'height': move.height,
            'weight': move.weight,
            'move_id': move.id,
        })

        return res

    def split(self, cr, uid, ids, new_qty=0.00, uom_id=False, context=None):
        """
        Split the line according to new parameters
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No line to split !'),
            )

        # New quantity must be greater than 0.00
        if new_qty <= 0.00:
            raise osv.except_osv(
                _('Error'),
                _('Selected quantity must be greater than 0.00 !'),
            )

        pick_wiz_id = False
        for line in self.browse(cr, uid, ids, context=context):
            pick_wiz_id = line.wizard_id.id
            if new_qty > line.ordered_quantity:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) exceeds the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.ordered_quantity, line.uom_id.name),
                )
            elif new_qty == line.ordered_quantity:
                # Cannot select more than initial quantity
                raise osv.except_osv(
                    _('Error'),
                    _('Selected quantity (%0.1f %s) cannot be equal to the initial quantity (%0.1f %s)') %
                    (new_qty, line.uom_id.name, line.ordered_quantity, line.uom_id.name),
                )

            update_qty = line.ordered_quantity - new_qty
            wr_vals = {
                'qty_per_pack': line.quantity > update_qty and update_qty or line.quantity,
                'ordered_quantity': update_qty,
                'quantity': update_qty,
            }
            self._update_split_wr_vals(vals=wr_vals)  # w/o overriding, just return wr_vals
            self.write(cr, uid, [line.id], wr_vals, context=context)

            # Create a copy of the move_processor with the new quantity
            cp_vals = {
                'qty_per_pack': 0.00,
                'ordered_quantity': new_qty,
                'quantity': new_qty,
            }
            self._update_split_cp_vals(vals=cp_vals)  # w/o overriding, just return cp_vals
            self.copy(cr, uid, line.id, cp_vals, context=context)

        return pick_wiz_id

    # View methods
    def from_to_pack_change(self, cr, uid, ids, from_pack, to_pack):
        """
        Remove the integrity status when from/to pack value is changed
        """
        if from_pack or to_pack:
            return {
                'value': {'integrity_status': 'empty',},
            }

        return {}

ppl_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
