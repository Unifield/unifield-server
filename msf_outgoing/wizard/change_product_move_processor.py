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


class change_product_move_processor(osv.osv_memory):
    _name = 'change.product.move.processor'
    _description = 'Wizard to switch products on picking processor lines'
    
    _columns = {
        'processor_line_id': fields.integer(string='ID of the processor line', required=True),
        'processor_type': fields.char(size=256, string='Model of the processor line', required=True),
        'move_location_ids': fields.char(size=256, string='Move locations', readonly=True),
        'old_product_id': fields.many2one('product.product', string='Present Product', readonly=True),
        'old_uom_id': fields.many2one('product.uom', 'Restricted UoM', readonly=True),
        'old_uom_category_id': fields.many2one('product.uom.categ', 'Restricted UoM Category', readonly=True),
        'new_product_id': fields.many2one('product.product', string='New Product'),
        'change_reason': fields.char(string='Change Reason', size=1024),
    }

    _defaults = {
        'move_location_ids': [],
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
            if not vals.get('old_product_id'):
                vals['old_product_id'] = line.product_id.id
            if not vals.get('old_uom_id'):
                vals.update({
                    'old_uom_id': line.uom_id.id,
                    'old_uom_category_id': line.uom_id.category_id.id,
                })

        return super(change_product_move_processor, self).create(cr, uid, vals, context=context)
    
    """
    Controller methods
    """
    def return_to_wizard(self, cr, uid, ids, context=None):
        '''
        Return to picking creation wizard
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No wizard found !')
            )
        
        res_model = 'stock.picking.processor'
        res_id = False
        
        for wiz in self.read(cr, uid, ids, ['processor_type', 'processor_line_id'], context=context):
            line_model = self.pool.get(wiz['processor_type'])
            line = line_model.browse(cr, uid, wiz['processor_line_id'], context=context)
            res_model = line_model._columns['wizard_id']._obj
            res_id = line.wizard_id.id
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

    def cancel(self, cr, uid, ids, context=None):
        """
        After a click on cancel button
        """
        return self.return_to_wizard(cr, uid, ids, context=context)

    def change_product(self, cr, uid, ids, context=None):
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
            line_model.change_product(cr, uid, wiz.processor_line_id, wiz.change_reason, wiz.new_product_id.id, context=context)
        
        return self.return_to_wizard(cr, uid, ids, context=context)
    
change_product_move_processor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

