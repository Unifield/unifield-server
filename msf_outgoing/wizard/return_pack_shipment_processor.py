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

class return_pack_shipment_processor(osv.osv):
    """
    Wizard to return Packs from shipment
    """
    _name = 'return.pack.shipment.processor'
    _inherit = 'shipment.processor'
    _description = 'Wizard to return Packs from shipment'

    _columns = {
        'family_ids': fields.one2many(
            'return.pack.shipment.family.processor',
            'wizard_id',
            string='Lines',
        ),
    }

    def do_return_pack_from_shipment(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the do_return_pack_from_shipment method of shipment object
        """
        # Objects
        shipment_obj = self.pool.get('shipment')
        family_obj = self.pool.get('return.pack.shipment.family.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        to_smaller_ids = []
        out_of_range_ids = []
        overlap_ids = []

        for wizard in self.browse(cr, uid, ids, context=context):
            sequences = []
            for family in wizard.family_ids:
                if family.return_from > family.return_to:
                    to_smaller_ids.append(family.id)
                elif not (family.return_from >= family.from_pack and family.return_to <= family.to_pack):
                    out_of_range_ids.append(family.id)
                else:
                    sequences.append((family.return_from, family.return_to, family.id))

            sequences = sorted(sequences, key=lambda seq: seq[0])
            # Go through the list of sequences applying the rules
            for i in range(len(sequences)):
                seq = sequences[i]
                # Rule #3 applies from second element
                if i > 0:
                    # previous sequence
                    seqb = sequences[i - 1]
                    # Rule #3: sfrom[i] > sto[i-1] for i>0 // no overlapping, unique sequence
                    if not (seq[0] > seqb[1]):
                        overlap_ids.append(seq[2])

            if overlap_ids:
                family_obj.write(cr, uid, overlap_ids, {'integrity_status': 'overlap'}, context=context)

            if to_smaller_ids:
                family_obj.write(cr, uid, to_smaller_ids, {'integrity_status': 'to_smaller_than_from'}, context=context)

            if out_of_range_ids:
                family_obj.write(cr, uid, out_of_range_ids, {'integrity_status': 'seq_out_of_range'}, context=context)

            if overlap_ids or to_smaller_ids or out_of_range_ids:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': ids[0],
                    'target': 'new',
                    'context': context,
                }

            if not sequences:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('You must enter the number of packs you want to return before performing the return.'),
                )

        return shipment_obj.do_return_packs_from_shipment(cr, uid, ids, context=context)

return_pack_shipment_processor()


class return_pack_shipment_family_processor(osv.osv):
    """
    Family of the wizard to be returned from shipment
    """
    _name = 'return.pack.shipment.family.processor'
    _inherit = 'shipment.family.processor'
    _description = 'Family to be returned from shipment'

    def _get_pack_info(self, cr, uid, ids, field_name, args, context=None):
        """
        Set information on line with pack information
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            num_of_packs = line.return_to - line.return_from + 1
            res[line.id] = {
                'volume': (line.length * line.width * line.height * float(num_of_packs)) / 100.0,
                'num_of_packs': num_of_packs,
                'selected_weight': line.weight * line.selected_number,
            }

        return res

    _columns = {
        'wizard_id': fields.many2one(
            'return.pack.shipment.processor',
            string='Wizard',
            required=True,
            readonly=True,
            ondelete='cascade',
            help="Wizard to process the return of the pack from the shipment",
        ),
        'return_from': fields.integer(string='Return from'),
        'return_to': fields.integer(string='Return to'),
        'volume': fields.function(
            _get_pack_info,
            method=True,
            string='Volume [dm³]',
            type='float',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'num_of_packs': fields.function(
            _get_pack_info,
            method=True,
            string='# Packs',
            type='integer',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'selected_weight': fields.function(
            _get_pack_info,
            method=True,
            string='Selected Weight',
            type='float',
            store=False,
            readonly=True,
            multi='pack_info',
        ),
        'integrity_status': fields.selection(
            string=' ',
            selection=[
                ('empty', ''),
                ('ok', 'Ok'),
                ('to_smaller_than_from', 'To value must be greater or equal to From value'),
                ('overlap', 'The sequence overlaps previous one'),
                ('seq_out_of_range', 'Selected Sequence is out of range'),
            ],
            readonly=True,
        ),
    }

return_pack_shipment_family_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
