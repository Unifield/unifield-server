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
from msf_order_date import TRANSPORT_TYPE
import time

class return_shipment_processor(osv.osv):
    """
    Wizard to return products to stock from a draft shipment
    """
    _name = 'return.shipment.processor'
    _description = 'Return products to stock wizard'
    _rec_name = 'date'

    _columns = {
        'shipment_id': fields.many2one(
            'shipment',
            string='Shipment',
            required=True,
            readonly=True,
            ondelete='cascade',
            help="Linked shipment",
        ),
        'date': fields.datetime(string='Date', required=True),
        'transport_type': fields.selection(
            string='Transport type',
            selection=TRANSPORT_TYPE,
            readonly=True,
        ),
        'address_id': fields.many2one(
            'res.partner.address',
            string='Address',
            help="Address of the customer",
            ondelete='set null',
        ),
        'partner_id': fields.related(
            'address_id',
            'partner_id',
            type='many2one',
            relation='res.partner',
            string='Customer',
            write_relate=False,
        ),
        'step': fields.selection(
            string='Step',
            selection=[
                ('create', 'Create'),
                ('return', 'Return Packs'),
                ('return_from_shipment', 'Return Packs from shipment'),
            ],
            readonly=True,
        ),
        'family_ids': fields.one2many(
            'return.shipment.family.processor',
            'wizard_id',
            string='Lines',
        ),
    }

    _defaults = {
        'step': 'create',
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def create_lines(self, cr, uid, ids, context=None):
        """
        Create the lines of the wizard
        """
        # Objects
        family_obj = self.pool.get(self._columns['family_ids']._obj)  # Get the object of the o2m field because of heritage

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        for wizard in self.browse(cr, uid, ids, context=context):
            shipment = wizard.shipment_id

            for family in shipment.pack_family_memory_ids:
                if family.state == 'done':
                    continue

                family_vals = {
                    'wizard_id': wizard.id,
                    'sale_order_id': family.sale_order_id and family.sale_order_id.id or False,
                    'from_pack': family.from_pack,
                    'to_pack': family.to_pack,
                    'selected_number': 0 if self._name == 'return.shipment.processor' else family.num_of_packs,
                    'pack_type': family.pack_type and family.pack_type.id or False,
                    'length': family.length,
                    'width': family.width,
                    'height': family.height,
                    'weight': family.weight,
                    'draft_packing_id': family.draft_packing_id and family.draft_packing_id.id or False,
                    'description_ppl': family.description_ppl,
                    'ppl_id': family.ppl_id and family.ppl_id.id or False,
                    'comment': family.comment,
                }

                family_obj.create(cr, uid, family_vals, context=context)

        return True

    def select_all(self, cr, uid, ids, context=None):
        """
        Select all button, write max number of packs in each pack family line
        """
        # Objects
        family_obj = self.pool.get(self._columns['family_ids']._obj)  # Get the object of the o2m field because of heritage

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            for family in wiz.family_ids:
                family_obj.write(cr, uid, [family.id], {'selected_number': int(family.num_of_packs), }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Packs'),
            'res_model': self._name,
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': ids[0],
            'nodestroy': True,
            'target': 'new',
            'context': context,
        }

    def deselect_all(self, cr, uid, ids, context=None):
        """
        De-select all button, write 0 as number of packs in each pack family line
        """
        # Objects
        family_obj = self.pool.get(self._columns['family_ids']._obj)  # Get the object of the o2m field because of heritage
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        family_ids = []
        for wiz in self.browse(cr, uid, ids, context=context):
            for family in wiz.family_ids:
                family_ids.append(family.id)

        family_obj.write(cr, uid, family_ids, {'selected_number': 0, }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Packs'),
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'nodestroy': True,
            'target': 'new',
            'context': context,
        }

    def do_return_packs(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the do_return_packs method of shipment object
        """
        # Objects
        shipment_obj = self.pool.get('shipment')
        family_obj = self.pool.get('return.shipment.family.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        negative_line_ids = []
        too_much_line_ids = []

        for wizard in self.browse(cr, uid, ids, context=context):
            total_qty = 0.00

            for family in wizard.family_ids:
                if family.selected_number < 0.00:
                    negative_line_ids.append(family.id)
                elif family.selected_number > int(family.num_of_packs):
                    too_much_line_ids.append(family.id)
                else:
                    total_qty += family.selected_number

            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('You must select a quantity to return before performing the return.'),
                )

        if negative_line_ids:
            family_obj.write(cr, uid, negative_line_ids, {'integrity_status': 'negative'}, context=context)

        if too_much_line_ids:
            family_obj.write(cr, uid, too_much_line_ids, {'integrity_status': 'return_qty_too_much'}, context=context)

        if negative_line_ids or too_much_line_ids:
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'new',
                'context': context,
            }

        return shipment_obj.do_return_packs(cr, uid, ids, context=context)

return_shipment_processor()


class return_shipment_family_processor(osv.osv):
    """
    Wizard line to return products to stock from a draft shipment family
    """
    _name = 'return.shipment.family.processor'
    _inherit = 'ppl.family.processor'
    _description = 'Family to returns to stock'
    _order = 'sale_order_id, ppl_id, from_pack, id'

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
            num_of_packs = line.to_pack - line.from_pack + 1
            res[line.id] = {
                'volume': (line.length * line.width * line.height * float(num_of_packs)) / 1000.0,
                'num_of_packs': num_of_packs,
                'selected_weight': line.weight * line.selected_number,
            }

        return res

    _columns = {
        'wizard_id': fields.many2one(
            'return.shipment.processor',
            string='Wizard',
            required=True,
            readonly=True,
            ondelete='cascade',
            help="Wizard to process the return of the shipment",
        ),
        'sale_order_id': fields.many2one(
            'sale.order',
            string='Field Order Ref.',
            readonly=True,
        ),
        'ppl_id': fields.many2one(
            'stock.picking',
            string='PPL Ref.',
            readonly=True,
        ),
        'draft_packing_id': fields.many2one(
            'stock.picking',
            string='Draft Packing Ref.',
            readonly=True,
        ),
        'selected_number': fields.integer(string='Selected number'),
        'volume': fields.function(
            _get_pack_info,
            method=True,
            string=u'Volume [dm³]',
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
        'comment': fields.text(
            string='Comment',
            readonly=True,
        ),
        'integrity_status': fields.selection(
            string=' ',
            selection=[
                ('empty', ''),
                ('ok', 'Ok'),
                ('return_qty_too_much', 'Too much quantity selected'),
                ('negative', 'Negative Value'),
            ],
            readonly=True,
        ),
    }

    _defaults = {
        'integrity_status': 'empty',
    }

return_shipment_family_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
