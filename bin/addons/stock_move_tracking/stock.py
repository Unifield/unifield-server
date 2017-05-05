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

class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'
    _order = 'date_expected asc'
    
    def _get_picking_ids(self, cr, uid, ids, context=None):
        res = []
        picking_ids = self.pool.get('stock.picking').browse(cr, uid, ids, context=context)
        for pick in picking_ids:
            res += self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', pick.id)])

        return res
    
    def _get_lot_ids(self, cr, uid, ids, context=None):
        res = []
        lot_ids = self.pool.get('stock.production.lot').browse(cr, uid, ids, context=context)
        for lot in lot_ids:
            res += self.pool.get('stock.move').search(cr, uid, [('prodlot_id', '=', lot.id)])
        
        return res
    
    _columns = {
        'type': fields.related('picking_id', 'type', string='Type', type='selection', 
                               selection=[('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], readonly=True, 
                               store={
                                'stock.picking': (_get_picking_ids, ['type'], 20),
                                'stock.move': (lambda self, cr, uid, ids, c=None: ids, ['picking_id'], 20),
                                }
                               
                               ),
        'expired_date': fields.related('prodlot_id', 'life_date', string='Expiry Date', type='date', readonly=True, 
                                        store={
                                            'stock.production.lot': (_get_lot_ids, ['life_date'], 20),
                                            'stock.move': (lambda self, cr, uid, ids, c=None: ids, ['prodlot_id'], 20), 
                                            }
                                        ),
    }
    
stock_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
