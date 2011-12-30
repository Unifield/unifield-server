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

class sale_order(osv.osv):
    
    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', help="This field contains the information related to the numbering of the lines of this order.", required=True, ondelete='cascade'),
                }
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Sale Order'
        code = 'sale.order'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)
    
    def create(self, cr, uid, vals, context=None):
        '''
        create from sale_order
        create the sequence for the numbering of the lines
        '''
        vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})
        
        return super(sale_order, self).create(cr, uid, vals, context)

sale_order()

class sale_order_line(osv.osv):
    '''
    override of sale_order_line class
    '''
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {
                'line_number': fields.integer(string='Line', required=True),
                }
    _order = 'line_number'
    
    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        
        add the corresponding line number
        '''
        # gather the line number from the sale order sequence
        order = self.pool.get('sale.order').browse(cr, uid, vals['order_id'], context)
        sequence = order.sequence_id
        line = sequence.get_id(test='id', context=context)
        vals.update({'line_number': line})
        
        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)
        
        return result
            
sale_order_line()

class purchase_order(osv.osv):
    
    _inherit = 'purchase.order'
    _description = 'Purchase Order'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', help="This field contains the information related to the numbering of the lines of this order.", required=True, ondelete='cascade'),
                }
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Purchase Order'
        code = 'purchase.order'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)
    
    def create(self, cr, uid, vals, context=None):
        '''
        create from purchase_order
        create the sequence for the numbering of the lines
        '''
        vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})
        
        return super(purchase_order, self).create(cr, uid, vals, context)

purchase_order()

class purchase_order_line(osv.osv):
    '''
    override of purchase_order_line class
    '''
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'
    _columns = {
                'line_number': fields.integer(string='Line', required=True),
                }
    _order = 'line_number'
    
    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'purchase.order.line'
        
        add the corresponding line number
        '''
        if not 'line_number' in vals:
            # gather the line number from the sale order sequence
            order = self.pool.get('purchase.order').browse(cr, uid, vals['order_id'], context)
            sequence = order.sequence_id
            line = sequence.get_id(test='id', context=context)
            vals.update({'line_number': line})
        
        # create the new sale order line
        result = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        
        return result
            
purchase_order_line()

class ir_sequence(osv.osv):
    '''
    override of ir_sequence from account as of a bug when the id is a list
    '''
    _inherit = 'ir.sequence'
    
    def get_id(self, cr, uid, sequence_id, test='id', context=None):
        '''
        correct a bug as sequence_id is passed as an array, which
        is not taken into account in the override in account
        '''
        if isinstance(sequence_id, list):
            return super(ir_sequence, self).get_id(cr, uid, sequence_id[0], test, context=context)
        
        return super(ir_sequence, self).get_id(cr, uid, sequence_id, test, context=context)
        
ir_sequence()
