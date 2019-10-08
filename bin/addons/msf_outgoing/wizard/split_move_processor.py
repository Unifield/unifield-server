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

from osv import fields
from osv import osv
from tools.translate import _

import decimal_precision as dp


class split_move_processor(osv.osv_memory):
    _name = 'split.move.processor'
    _description = 'Wizard to split processor lines'

    _columns = {
        'processor_line_id': fields.integer(string='ID of the processor line', required=True),
        'processor_type': fields.char(size=256, string='Model of the processor line', required=True),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Product UOM'), related_uom='uom_id'),
        'uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
    }

    _defaults = {
        'quantity': 0.00,
    }

    """
    Model methods
    """
    def create(self, cr, uid, vals, context=None):
        """
        Update the readonly fields with the good values
        """
        if vals.get('processor_line_id', False) and vals.get('processor_type', False):
            line = self.pool.get(vals.get('processor_type')).browse(cr, uid, vals.get('processor_line_id'), context=context)
            if not vals.get('uom_id'):
                vals['uom_id'] = line.uom_id.id

        return super(split_move_processor, self).create(cr, uid, vals, context=context)

    """
    Controller methods
    """
    def return_to_wizard(self, cr, uid, ids, context=None):
        '''
        Return to picking creation wizard
        '''
        # Objects
        data_obj = self.pool.get('ir.model.data')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !')
            )

        res_model = 'stock.picking.processor'
        res_id = False
        view_id = False

        for wiz in self.read(cr, uid, ids, ['processor_type', 'processor_line_id'], context=context):
            if wiz['processor_type'] == 'stock.move':
                return {
                    'type': 'ir.actions.act_window_close'
                }
            line_model = self.pool.get(wiz['processor_type'])
            line = line_model.browse(cr, uid, wiz['processor_line_id'], context=context)
            res_model = line_model._columns['wizard_id']._obj
            res_id = line.wizard_id.id

            # Exceptions for PPL processor that need a view_id
            if res_model == 'ppl.processor':
                view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step1_form_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

    def cancel(self, cr, uid, ids, context=None):
        """
        After a click on cancel button
        """
        return self.return_to_wizard(cr, uid, ids, context=context)

    def split(self, cr, uid, ids, context=None):
        """
        Switch from old product to new product or from old UoM to new UoM
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !'),
            )
        # class corresponding to calling object

        for wiz in self.browse(cr, uid, ids, context=context):
            line_model = self.pool.get(wiz.processor_type)

            # Put the treatment at stock.move.processor side
            line_model.split(cr, uid, wiz.processor_line_id, wiz.quantity, wiz.uom_id.id, context=context)

        return self.return_to_wizard(cr, uid, ids, context=context)

    def change_uom(self, cr, uid, ids, uom_id, qty):
        '''
        Check the round of the qty according to the UoM
        '''
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'quantity')

split_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

