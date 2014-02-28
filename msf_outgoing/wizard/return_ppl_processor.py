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


class return_ppl_processor(osv.osv):
    """
    Wizard to return products from a PPL
    """
    _name = 'return.ppl.processor'
    _inherit = 'ppl.processor'
    _description = 'Wizard to return products from a PPL'

    _columns = {
        'move_ids': fields.one2many(
            'return.ppl.move.processor',
            'wizard_id',
            string='Moves',
            help="Lines of the PPL processor wizard",
        ),
    }

    def do_return_ppl(self, cr, uid, ids, context=None):
        """
        Make some integrity checks and call the method do_return_ppl of the stock.picking object
        """
        # Objects
        picking_obj = self.pool.get('stock.picking')
        line_obj = self.pool.get('return.ppl.move.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        negative_move_ids = []
        too_much_ids = []

        for wizard in self.browse(cr, uid, ids, context=context):

            total_qty = 0.00

            for move in wizard.move_ids:
                if move.quantity < 0.00:
                    negative_move_ids.append(move.id)
                elif move.quantity > move.ordered_quantity:
                    too_much_ids.append(move.id)
                else:
                    total_qty += move.quantity

            if not total_qty:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('You must enter quantities to return before clicking on the \'Return\' button'),
                )

        if negative_move_ids:
            line_obj.write(cr, uid, negative_move_ids, {'integrity_status': 'negative'}, context=context)

        if too_much_ids:
            line_obj.write(cr, uid, too_much_ids, {'integrity_status': 'return_qty_too_much'}, context=context)

        if negative_move_ids or too_much_ids:
            return {
                'type': 'ir.actions.act_window',
                'model': 'return.ppl.processor',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'new',
                'context': context,
            }

        return picking_obj.do_return_ppl(cr, uid, ids, context=context)

return_ppl_processor()


class return_ppl_move_processor(osv.osv):
    """
    Lines with products to return from a PPL
    """
    _name = 'return.ppl.move.processor'
    _inherit = 'ppl.move.processor'
    _description = 'Line of the wizard to return products from a PPL'

    _columns = {
        'wizard_id': fields.many2one(
            'return.ppl.processor',
            string='Wizard',
            required=True,
            ondelete='cascade',
            help="Return PPL processing wizard",
        ),
    }

    def _get_line_data(self, cr, uid, wizard=False, move=False, context=None):
        """
        Just put the 0 as quantity into the return.ppl.move.processor
        """
        res = super(return_ppl_move_processor, self)._get_line_data(cr, uid, wizard, move, context=context)

        res['quantity'] = 0.00

        return res

return_ppl_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
