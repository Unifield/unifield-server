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

class return_shipment_processor(osv.osv):
    """
    Wizard to return products to stock from a draft shipment
    """
    _name = 'return.shipment.processor'
    _inherit = 'shipment.processor'
    _description = 'Return products to stock wizard'

    _columns = {
        'family_ids': fields.one2many(
            'return.shipment.family.processor',
            'wizard_id',
            string='Lines',
        ),
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
    _inherit = 'shipment.family.processor'
    _description = 'Family to returns to stock'

    _columns = {
        'wizard_id': fields.many2one(
            'return.shipment.processor',
            string='Wizard',
            required=True,
            readonly=True,
            ondelete='cascade',
            help="Wizard to process the return of the shipment",
        ),
    }

return_shipment_family_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
