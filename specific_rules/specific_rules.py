# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

class sale_order_line(osv.osv):
    '''
    override to add message at sale order creation and update
    '''
    _inherit = 'sale.order.line'
    
#    def create(self, cr, uid, vals, context=None):
#        '''
#        display message for short shelf life things
#        '''
#        sol_id = super(sale_order_line, self).create(cr, uid, vals, context=context)
#        sol = self.browse(cr, uid, sol_id, context=context)
#        # log the message
#        if sol.product_id.short_shelf_life:
#            self.log(cr, uid, sol_id, 'Product with short shelf life, check the accuracy of the order quantity, frequency and mode of transport.', context=context)
#        
#        return sol_id
    
#    def write(self, cr, uid, ids, vals, context=None):
#        '''
#        display message for short shelf life things
#        '''
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#            
#        result = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
#            
#        for sol in self.browse(cr, uid, ids, context=context):
#            # log the message
#            if sol.product_id.short_shelf_life:
#                # log the message
#                self.log(cr, uid, sol.id, 'Product with short shelf life, check the accuracy of the order quantity, frequency and mode of transport.', context=context)
#            
#        return result
    
sale_order_line()

class sale_order(osv.osv):
    '''
    
    '''
    _inherit = 'sale.order'
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                # log the message
                if line.product_id.short_shelf_life:
                    # log the message
                    self.log(cr, uid, obj.id, 'Product with Short Shelf Life, check the accuracy of the order quantity, frequency and mode of transport.', context=context)
        
        return super(sale_order, self).write(cr, uid, ids, vals, context=context)
    
sale_order()


class purchase_order(osv.osv):
    '''
    
    '''
    _inherit = 'purchase.order'
    
#    def wkf_confirm_order(self, cr, uid, ids, context=None):
#        '''
#        
#        '''
#        result = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
#        
#        # display message
#        
#        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                # log the message
                if line.product_id.short_shelf_life:
                    # log the message
                    self.log(cr, uid, obj.id, 'Product with Short Shelf Life, check the accuracy of the order quantity, frequency and mode of transport.', context=context)
        
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    
purchase_order()
    
