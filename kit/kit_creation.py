# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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

from osv import osv, fields
from tools.translate import _
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc
import logging
import tools
import time
from os import path

KIT_CREATION_STATE = [('draft', 'Draft'),
                      ('completed', 'Completed'),
                      ('done', 'Closed'),
                      ]

class kit_creation(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'kit.creation'
    
    def on_change_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        on change function
        '''
        pass
    
    
    _columns = {'reference_kit_creation': fields.char(string='Reference', size=1024, required=True),
                'creation_date_kit_creation': fields.date(string='Creation Date', required=True),
                'product_id_kit_creation': fields.many2one('product.product', string='Product', required=True, domain=[('type', '=', 'product'), ('subtype', '=', 'kit')]),
                'version_id_kit_creation': fields.many2one('composition.kit', string='Version', domain=[('composition_type', '=', 'theoretical'), ('state', '=', 'completed')]),
                'qty_kit_creation': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_kit_creation': fields.many2one('product.uom', string='UoM', required=True),
                }
    

kit_creation()

