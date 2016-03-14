# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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

class stock_picking_not_available(osv.osv_memory):
    _name = 'stock.picking.not.available'
    
    _columns = {
        'move_id': fields.many2one('stock.move', 'Move id'),
        'picking_id': fields.many2one('stock.picking', 'Picking id'),
    }
    
    def yes(self, cr, uid, ids, context=None):
        context.update({'yesorno': True,})
        picking_ids = []
        for avail in self.browse(cr, uid, ids, context=context):
            picking_ids.append(avail.picking_id.id)
        return self.pool.get('stock.picking').action_process(cr, uid, picking_ids, context=context)

    def no(self, cr, uid, ids, context=None):
        picking_ids = []
        context.update({'yesorno': True,'out':True})
        for avail in self.browse(cr, uid, ids, context=context):
            picking_ids.append(avail.picking_id.id)
        return self.pool.get('stock.picking').action_process(cr, uid, picking_ids, context=context)

stock_picking_not_available()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
