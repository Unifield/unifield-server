#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
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

from osv import osv
from osv import fields

class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _inherit = 'real.average.consumption'
    
    
    def action_cancel(self, cr, uid, ids, context=None):
        """ Cancels stock move related to the lines of the Real Average Consumption (rac)
        @return: True
        """
        rac = self.browse(cr, uid, ids, context=context)[0]
        move_obj = self.pool.get('stock.move')
        move_ids = []
        
        for line in rac.line_ids:
            move_ids.append(line.move_id.id)
        move_obj.action_cancel(cr, uid, move_ids, context=context)
        self.write(cr, uid, ids, {'created_ok': False}, context=context)
        return True

    
real_average_consumption()


class real_average_consumption_line(osv.osv):
    _inherit = 'real.average.consumption.line'

    # Need to redefine the asset_id field from int to m2o because the
    # product_asset module is not loaded before consumption_calculation
    # module
    _columns = {
        'asset_id': fields.many2one('product.asset', string='Asset'),
    }

real_average_consumption_line()
