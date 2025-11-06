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

class ppl_processor(osv.osv):
    """
    Wizard to process the Pre-Packing List
    """
    _name = 'ppl.processor'
    _inherit = 'stock.picking.processor'
    _description = 'Wizard to process the third step of the P/P/S'

    _columns = {
        'name': fields.char('Name', size=256),
        'family_ids': fields.one2many(
            'ppl.family.processor',
            'wizard_id',
            string='Families',
            help="Pack of products",
        ),
        'draft_step2': fields.boolean('Draft', help='Usefull for internal management of save as draft order'),
    }

    _defaults = {
        'draft_step2': lambda *a: False,
    }

    def create(self, cr, uid, vals, context=None):
        if 'picking_id' in vals:
            vals['name'] = self.pool.get('stock.picking').read(cr, uid, vals['picking_id'], ['name']).get('name')
        return super(ppl_processor, self).create(cr, uid, vals, context=context)

    def do_reset_step2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pick_id = []
        for proc in self.browse(cr, uid, ids, context=context):
            pick_id = proc['picking_id']['id']

        self.write(cr, uid, ids, {'draft_step2': False}, context=context)

        return self.pool.get('stock.picking').ppl_step2_run_wiz(cr, uid, pick_id, context=context)

    def do_save_draft_step2(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        self.write(cr, uid, ids, {'draft_step2': True}, context=context)

        return {}

    def check_sequences(self, cr, uid, sequences, ppl_move_obj, field='integrity_status', context=None):
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
                    sequences[i] = (seqb[0], seqb[1], seqb[2])
                # Rule #3: if from[i] != from[i-1] -> from[i] == to[i-1]+1
                elif (seq[0] != seqb[0]) and not (seq[0] == seqb[1] + 1):
                    if seq[0] < seqb[1] + 1:
                        overlap_ids.append(seq[2])
                        sequences[i] = (min(seq[0], seqb[0]), seqb[1], seqb[2])
                    elif seq[0] > seqb[1] + 1:
                        gap_ids.append(seq[2])
            # rule #4: to[i] >= from[i]
            if not (seq[1] >= seq[0]):
                to_smaller_ids.append(seq[2])
        ok = True
        import_ppl_errors = ''
        if missing_ids:
            if ppl_move_obj:
                ppl_move_obj.write(cr, uid, missing_ids, {field: 'missing_1'}, context=context)
            else:
                import_ppl_errors += _('The first From pack must be equal to 1.\n')
            ok = False

        if to_smaller_ids:
            if ppl_move_obj:
                ppl_move_obj.write(cr, uid, to_smaller_ids, {field: 'to_smaller_than_from'}, context=context)
            else:
                import_ppl_errors += _('To pack must be greater than From pack on line(s) %s.\n') \
                    % (', '.join(['%s' % (x,) for x in to_smaller_ids]))
            ok = False

        if overlap_ids:
            if ppl_move_obj:
                ppl_move_obj.write(cr, uid, overlap_ids, {field: 'overlap'}, context=context)
            else:
                import_ppl_errors += _('The sequence From pack - To Pack of line(s) %s overlaps a previous one.\n') \
                    % (', '.join(['%s' % (x,) for x in overlap_ids]))
            ok = False

        if gap_ids:
            if ppl_move_obj:
                ppl_move_obj.write(cr, uid, gap_ids, {field: 'gap'}, context=context)
            else:
                import_ppl_errors += _('A gap exists with the sequence From pack - To Pack of line(s) %s.\n') \
                    % (', '.join(['%s' % (x,) for x in gap_ids]))
            ok = False

        if not ppl_move_obj:
            return import_ppl_errors
        else:
            return ok

    def _check_rounding(self, cr, uid, uom_obj, num_of_packs, quantity, context=None):
        if context is None:
            context = {}


        if uom_obj.rounding == 1:
            if quantity % int(num_of_packs) != 0:
                return False
        else:
            qty_per_pack = quantity/int(num_of_packs)
            rounded_qty_pp = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, uom_obj.id, qty_per_pack)
            if abs(qty_per_pack - rounded_qty_pp) < uom_obj.rounding \
                    and abs(qty_per_pack - rounded_qty_pp) != 0:
                return False

        return True

    def check_qty_pp(self, cr, uid, lines, context=None):
        '''
        Check quantities per pack integrity with UoM
        '''
        if context is None:
            context = {}

        rounding_issues = []
        for line in lines:
            if not self._check_rounding(cr, uid, line.uom_id, line.num_of_packs, line.quantity, context=context):
                rounding_issues.append(line.line_number)
        return rounding_issues

    def do_ppl_step2(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the method do_ppl_step2 of stock.picking document
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # disable "save as draft":
        self.write(cr, uid, ids, {'draft_step2': False}, context=context)

        parcel_ids_error = []
        for wizard in self.browse(cr, uid, ids, context=context):
            treated_moves = 0
            has_vol = 0
            has_weight = 0
            error_vol = False
            total = 0
            for family in wizard.family_ids:
                total += 1
                if family.weight > 0:
                    has_weight += 1
                if family.length > 0 and family.width > 0 and family.height > 0:
                    has_vol += 1
                if family.length+family.width+family.height != 0 and family.length*family.width*family.height == 0:
                    error_vol = True
                treated_moves += len(family.move_ids)

                if family.parcel_ids:
                    nb_p = len(family.parcel_ids.split(','))
                    if nb_p != family.to_pack - family.from_pack + 1:
                        parcel_ids_error.append(_('%s - %s, %d Parcel IDs found') % (family.from_pack, family.to_pack, nb_p))

            if parcel_ids_error:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('Inconsitent Parcel IDs, click on icon box to edit Parcel IDs: %s') % ('\n'.join(parcel_ids_error),)
                )

            nb_pick_moves = move_obj.search(cr, uid, [
                ('picking_id', '=', wizard.picking_id.id),
                ('state', 'in', ['confirmed', 'assigned']),
            ], count=True, context=context)

            if nb_pick_moves != treated_moves:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('The number of treated moves (%s) are not compatible with the number of moves in PPL (%s).') % (treated_moves, nb_pick_moves),
                )

        if (has_vol and has_vol!=total) or (has_weight and has_weight!=total) or error_vol:
            raise osv.except_osv(
                _('Processing Error'),
                _('Some weight and/or volume information is missing: please fill them all or empty them all.'),
            )

        # Call the stock.picking method
        return picking_obj.do_ppl_step2_bg(cr, uid, ids, context=context)

ppl_processor()


class ppl_family_processor(osv.osv):
    """
    PPL family that merge some stock moves into one pack
    """
    _name = 'ppl.family.processor'
    _description = 'PPL family'
    _rec_name = 'from_pack'

    _order = 'from_pack, id'

    def _get_has_parcel(self, cr, uid, ids, name, arg, context=None):
        ret = {}
        for x in self.read(cr, uid, ids, ['from_pack', 'to_pack', 'parcel_ids'], context=context):
            if not x['parcel_ids']:
                ret[x['id']] = {'has_parcel': False, 'has_parcel_ids_error': False}
            else:
                nb = x['to_pack'] - x['from_pack'] + 1
                ret[x['id']] = {'has_parcel': True, 'has_parcel_ids_error': nb != len(x['parcel_ids'].split(','))}

        return ret

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
        'parcel_ids': fields.text('Parcel Ids'),
        'has_parcel': fields.function(_get_has_parcel, type='boolean', method=True, string='Has Parcel IDs', multi='get_all'),
        'has_parcel_ids_error': fields.function(_get_has_parcel, type='boolean', method=True, string='Has Parcel IDs error', multi='get_all'),
        'pack_type': fields.many2one(
            'pack.type',
            string='Pack Type',
            ondelete='set null',
        ),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        'move_ids': fields.one2many('stock.move', 'ppl_wizard_id', string='Moves'),
    }

    def onchange_pack_type(self, cr, uid, ids, pack_type):
        """
        Update values of the PPL family from the stock pack selected
        """
        # Objects
        p_type_obj = self.pool.get('pack.type')

        res = {}

        if pack_type :
            # if 'pack_type' is not a list, turn it into list
            if isinstance(pack_type, int):
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

    def select_parcel_ids(self, cr, uid, ids, context=None):
        ppl_line = self.read(cr, uid, ids[0], ['parcel_ids', 'from_pack', 'to_pack'], context=context)
        if not ppl_line['parcel_ids']:
            raise osv.except_osv(_('Error !'), _('Parcel list is not defined.'))
        wiz = self.pool.get('shipment.parcel.ppl.selection').create(cr, uid, {
            'ppl_line_id': ids[0],
            'parcel_number': ppl_line['to_pack'] - ppl_line['from_pack'] + 1,
            'parcel_ids': '\n'.join(ppl_line['parcel_ids'].split(',')),
        }, context=context)

        return {
            'name': _("List PPL Parcel IDs"),
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.parcel.ppl.selection',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': wiz,
            'target': 'new',
            'keep_open': True,
            'context': context,
        }

ppl_family_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
