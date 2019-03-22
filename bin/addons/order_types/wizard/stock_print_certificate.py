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

class stock_print_certificate(osv.osv_memory):
    _name = 'stock.print.certificate'
    _description = 'Print a certificate from an Outgoing donation'
    
    _columns = {
        'type': fields.selection([('gift', 'Gift certificate'), ('donation', 'Donation certificate')], 
                                 string='Type of certificate', required=True),
        'picking_id': fields.many2one('stock.picking', 'Picking id'),
        'valuation_ids': fields.one2many('stock.certificate.valuation', 'print_id', string='Product valuation'),
    }
    
    def print_certificate(self, cr, uid, ids, context=None):
        '''
        Prints the certificate
        '''
        pick_obj = self.pool.get('stock.picking')
        valuation_obj = self.pool.get('stock.certificate.valuation')
        
        for cert in self.browse(cr, uid, ids):
            data = []
            picking = pick_obj.browse(cr, uid, cert.picking_id.id)
            for move in picking.move_lines:
                valuation = move.product_id.list_price
                val_ids = valuation_obj.search(cr, uid, [('move_id', '=', move.id), ('print_id', '=', cert.id)])
                if val_ids:
                    valuation = valuation_obj.read(cr, uid, val_ids, ['unit_price'])[0]['unit_price']
                
                data.append({'product_code': move.product_id.default_code,
                             'product_name': move.product_id.name,
                             'product_qty': move.product_qty,
                             'product_uom': move.product_uom.name,
                             'prodlot_name': move.prodlot_id.name,
                             'life_date': move.prodlot_id.life_date,
                             'valuation': valuation})
            
            datas = {'ids': [picking.id],
                     'model': 'stock.picking',
                     'form': data}
            
            if cert.type == 'gift':
                return {'type': 'ir.actions.report.xml',
                        'report_name': 'order.type.gift.certificate',
                        'datas': datas}
            else:
                return {
                    'type': 'ir.actions.report.xml',
                    'report_name': 'order.type.donation.certificate',
                    'datas': datas,
                    'context': context,
                }
            
        return True
    
stock_print_certificate()

class stock_certificate_valuation(osv.osv_memory):
    _name = 'stock.certificate.valuation'
    _description = 'Valuation of product in Outgoing donation'
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        Forbid the deletion of a line
        '''
        if uid != 1:
            raise osv.except_osv(_('Errror'), _('You cannot remove this line !'))
        else:
            return super(stock_certificate_valuation, self).unlink(cr, uid, ids, context)
    
    _columns = {
        'print_id': fields.many2one('stock.print.certificate', string='Print'),
        'picking_id': fields.many2one('stock.picking', string='Picking'),
        'move_id': fields.many2one('stock.move', string='Move'),
        'product_id': fields.many2one('product.product', string='Product'),
        'qty': fields.float(digits=(16,2), string='Qty'),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'unit_price': fields.float(digits=(16,2), string='Unit Price'),
    }
    
stock_certificate_valuation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
