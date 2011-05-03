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
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _

class stock_move(osv.osv):
    _name= 'stock.move'
    _inherit = 'stock.move'
   
    def _search_order(self, cr, uid, obj, name, args, context={}):
        if not len(args):
            return []
        matching_fields = {'order_priority': 'priority', 'order_category': 'categ'}
        sale_obj = self.pool.get('sale.order')
        purch_obj = self.pool.get('purchase.order')

        search_args = []
        for arg in args:
            search_args.append((matching_fields.get(arg[0], arg[0]), arg[1], arg[2]))

        sale_ids = sale_obj.search(cr, uid, search_args, limit=0)
        purch_ids = purch_obj.search(cr, uid, search_args, limit=0)

        newrgs = []
        if sale_ids:
            newrgs.append(('sale_ref_id', 'in', sale_ids))
        if purch_ids:
            newrgs.append(('purchase_ref_id', 'in', purch_ids))
        
        if not newrgs:
            return [('id', '=', 0)]

        if len(newrgs) > 1:
            newrgs.insert(0,'|')
        
        return newrgs

    def _get_order_information(self, cr, uid, ids, fields_name, arg, context={}):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}
        
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = {'order_priority': False,
                            'order_category': False,
                            'order_type': False}
            order = False
            
            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id
                
            if order:
                res[move.id] = {}
                if 'order_priority' in fields_name:
                    res[move.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[move.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[move.id]['order_type'] = order.order_type
        
        return res
    
    _columns = {
        'order_priority': fields.function(_get_order_information, method=True, string='Priority', type='selection', 
                                          selection=ORDER_PRIORITY, multi='move_order', fnct_search=_search_order),
        'order_category': fields.function(_get_order_information, method=True, string='Category', type='selection', 
                                          selection=ORDER_CATEGORY, multi='move_order', fnct_search=_search_order),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection', 
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                                 ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                                 ('direct', 'Direct Purchase Order')], multi='move_order', fnct_search=_search_order),
        'sale_ref_id': fields.related('sale_line_id', 'order_id', type='many2one', relation='sale.order', string='Sale', readonly=True),
        'purchase_ref_id': fields.related('purchase_line_id', 'order_id', type='many2one', relation='purchase.order', string='Purchase', readonly=True),
    }
    
stock_move()

class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
    
    def _get_certificate(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Return True if at least one stock move requires a donation certificate
        '''
        res = {}
        
        for pick in self.browse(cr, uid, ids, context=context):
            certif = False
            if pick.type == 'out':
                for move in pick.move_lines:
                   if move.order_type in ['donation_exp', 'donation_st', 'in_kind']:
                        certif = True
                        break
                        
            res[pick.id] = certif
            
        return res
    
    _columns= {
        'certificate_donation': fields.function(_get_certificate, string='Certif ?', type='boolean', method=True),
    }
    
    def print_gift_certificate(self, cr, uid, ids, context={}):
        '''
        Launch printing of the gift certificate
        '''
        certif = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.certificate_donation:
                certif = True
                        
        if certif:
            data = self.read(cr, uid, ids, [], context)[0]
            datas = {'ids': ids,
                     'model': 'stock.picking',
                     'form': data}
            
            return {'type': 'ir.actions.report.xml',
                    'report_name': 'order.type.gift.certificate',
                    'datas': datas}
        else:
            raise osv.except_osv(_('Warning'), _('This picking doesn\'t require a gift certificate'))
    
    def print_donation_certificate(self, cr, uid, ids, context={}):
        '''
        Launch printing of the donation certificate
        '''
        certif = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.certificate_donation:
                certif = True
                        
        if certif:
            data = self.read(cr, uid, ids, [], context)[0]
            datas = {'ids': ids,
                     'model': 'stock.picking',
                     'form': data}
            
            return {'type': 'ir.actions.report.xml',
                    'report_name': 'order.type.donation.certificate',
                    'datas': datas}
        else:
            raise osv.except_osv(_('Warning'), _('This picking doesn\'t require a donation certificate'))

    def action_process(self, cr, uid, ids, context={}):
        '''
        Override the method to display a message to attach
        a certificate of donation
        '''
        certif = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.type == 'in':
                for move in pick.move_lines:
                    if move.order_type in ['donation_exp', 'donation_st', 'in_kind']:
                        certif = True
                        break
                        
        if certif and not context.get('attach_ok', False):
            partial_id = self.pool.get("stock.certificate.picking").create(
                            cr, uid, {'picking_id': ids[0]}, context=dict(context, active_ids=ids))
            return {'name':_("Attach a certificate of donation"),
                    'view_mode': 'form',
                    'view_id': False,
                    'view_type': 'form',
                    'res_model': 'stock.certificate.picking',
                    'res_id': partial_id,
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'new',
                    'domain': '[]',
                    'context': dict(context, active_ids=ids)}
        else:
            return super(stock_picking, self).action_process(cr, uid, ids, context=context)

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
