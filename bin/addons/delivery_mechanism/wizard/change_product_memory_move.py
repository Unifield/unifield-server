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
import decimal_precision as dp


class change_product_memory_move(osv.osv_memory):
    '''
    wizard called to split a memory stock move from create picking wizard
    '''
    _name = "change.product.memory.move"
    _description = "Change Product of Memory Move"
    _columns = {'old_product_id': fields.many2one('product.product', string='Present Product', readonly=True),
                'old_uom_id': fields.many2one('product.uom', 'Restricted UoM', readonly=True),
                'old_uom_category_id': fields.many2one('product.uom.categ', 'Restricted UoM Category', readonly=True),
                'new_product_id': fields.many2one('product.product', string='New Product'),
                'change_reason': fields.char(string='Change Reason', size=1024),
                }
    _defaults = {'old_product_id': lambda obj, cr, uid, c: c and c.get('product_id', False),
                 'old_uom_id': lambda obj, cr, uid, c: c and c.get('uom_id', False),
                 'old_uom_category_id': lambda obj, cr, uid, c: c and c.get('uom_category_id', False),
                 }
    
    def cancel(self, cr, uid, ids, context=None):
        '''
        return to picking creation wizard
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        wiz_obj = self.pool.get('wizard')
        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)

    def change_product(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        assert context['class_name'], 'No class name defined'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # class corresponding to calling object
        class_name = context['class_name']
        # objects
        wiz_obj = self.pool.get('wizard')
        # integrity check
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.change_reason or not obj.new_product_id:
                raise osv.except_osv(_('Error !'), _('You must select a new product and specify a reason.'))
        
        # memory moves selected
        memory_move_ids = context['memory_move_ids']
        memory_move_obj = self.pool.get(class_name)
        # new product and change reason
        data = self.read(cr, uid, ids, ['change_reason', 'new_product_id'], context=context)[0]
        change_reason = data['change_reason']
        new_product_id = data['new_product_id']
        values = {'change_reason': change_reason, 'product_id': new_product_id}
        # update the object    
        memory_move_obj.write(cr, uid, memory_move_ids, values, context=context)
        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)
    
change_product_memory_move()
