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

from osv import osv
from osv import fields

from tools.translate import _
from datetime import datetime, date

import time


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _description = 'Real Average Consumption'
    _rec_name = 'period_from'
    
    _columns = {
        'creation_date': fields.date(string='Creation date'),
        'cons_location_id': fields.many2one('stock.location', string='Consumer location', domain=[('usage', '=', 'internal')], required=True),
        'activity_id': fields.many2one('stock.location', string='Activity'),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'line_ids': fields.one2many('real.average.consumption.line', 'rac_id', string='Lines'),
        'valid_ok': fields.boolean(string='Create and process out moves'),
        'created_ok': fields.boolean(string='Out moves created'),
    }
    
    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'activity_id': lambda obj, cr, uid, context: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'msf_customer_location')[1],
        'period_to': lambda *a: time.strftime('%Y-%m-%d'),
        'valid_ok': lambda *a: True,
    }
    
    def save_and_process(self, cr, uid, ids, context={}):
        '''
        Returns the wizard to confirm the process of all lines
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_confirmation_view')[1],
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                'res_id': ids[0],
                }
        
    def process_moves(self, cr, uid, ids, context={}):
        '''
        Creates all stock moves according to the report lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        move_obj = self.pool.get('stock.move')
        line_obj = self.pool.get('real.average.consumption.line')
        
        reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_consumption_report')[1]
        
        for rac in self.browse(cr, uid, ids, context=context):
            if not rac.valid_ok:
                #return False
                raise osv.except_osv(_('Error'), _('Please check the last checkbox before processing the lines'))
            if rac.created_ok:
                return {'type': 'ir.actions.close_window'}
            
            for line in rac.line_ids:
                move_id = move_obj.create(cr, uid, {'name': 'RAC/%s' % (line.product_id.name),
                                                    'product_uom': line.uom_id.id,
                                                    'product_id': line.product_id.id,
                                                    'date_expected': rac.period_to,
                                                    'date': rac.creation_date,
                                                    'product_qty': line.consumed_qty,
                                                    'location_id': rac.cons_location_id.id,
                                                    'location_dest_id': rac.activity_id.id,
                                                    'reason_type_id': reason_type_id})
                line_obj.write(cr, uid, [line.id], {'move_id': move_id})
                
            self.write(cr, uid, [rac.id], {'created_ok': True}, context=context)
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'target': 'new',
                'res_id': ids[0],
                }
        
        #return {'type': 'ir.actions.act_window_close'}
    
real_average_consumption()


class real_average_consumption_line(osv.osv):
    _name = 'real.average.consumption.line'
    _description = 'Real average consumption line'
    _rec_name = 'product_id'
    
    def _in_stock(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Return the quantity of product in the Consumer location
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.product_id.qty_available
            
        return res 
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'product_qty': fields.function(_in_stock, method=True, string='Indicative stock', readonly=True, store=False),
        'consumed_qty': fields.float(digits=(16,2), string='Qty consumed', required=True),
        'remark': fields.char(size=256, string='Remark'),
        'move_id': fields.many2one('stock.move', string='Move'),
        'rac_id': fields.many2one('real.average.consumption', string='RAC', ondelete='cascade'),
        'list_id': fields.many2one('product.list', string='List'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
    }
    
    _defaults = {
        'list_id': lambda obj, cr, uid, context={}: context.get('rac_id', False) and obj.pool.get('real.average.consumption').browse(cr, uid, context.get('rac_id')).sublist_id.id or False,
        'nomen_id': lambda obj, cr, uid, context={}: context.get('rac_id', False) and obj.pool.get('real.average.consumption').browse(cr, uid, context.get('rac_id')).nomen_id.id or False,
    }
    
real_average_consumption_line()


class monthly_review_consumption(osv.osv):
    _name = 'monthly.review.consumption'
    _description = 'Monthly review consumption'
    
    _columns = {
        'creation_date': fields.date(string='Creation date'),
        'cons_location_id': fields.many2one('stock.location', string='Location', domain=[('usage', '=', 'internal')], required=True),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'line_ids': fields.one2many('monthly.review.consumption.line', 'mrc_id', string='Lines'),
    }
    
    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'period_to': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
monthly_review_consumption()


class monthly_review_consumption_line(osv.osv):
    _name = 'monthly.review.consumption.line'
    _description = 'Monthly review consumption line'
    
    def _get_amc(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Calculate the product AMC for the period
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            context.update({'from_date': line.mrc_id.period_from, 'to_date': line.mrc_id.period_to})
            res[line.id] = self.pool.get('product.product').compute_amc(cr, uid, ids, context=context)
            
        return res
    
    _columns = {
        'name': fields.many2one('product.product', string='Product', required=True),
        'amc': fields.function(_get_amc, string='AMC', method=True, readonly=True),
        'fmc': fields.float(digits=(16,2), string='FMC'),
        'last_reviewed': fields.related('name', 'last_fmc_reviewed', type='date', string='Last reviewed on', readonly=True),
        'valid_until': fields.date(string='Valid until'),
        'valid_ok': fields.boolean(string='OK', readonly=True),
        'mrc_id': fields.many2one('monthly.review.consumption', string='MRC', required=True, ondelete='cascade'),
        'list_id': fields.many2one('product.list', string='List'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
    }
    
    _defaults = {
        'list_id': lambda obj, cr, uid, context={}: context.get('mrc_id', False) and obj.pool.get('monthly.review.consumption').browse(cr, uid, context.get('mrc_id')).sublist_id.id or False,
        'nomen_id': lambda obj, cr, uid, context={}: context.get('mrc_id', False) and obj.pool.get('monthly.review.consumption').browse(cr, uid, context.get('mrc_id')).nomen_id.id or False,
    }
    
    def valid_line(self, cr, uid, ids, context={}):
        '''
        Valid the line and enter data in product form
        '''
        product_obj = self.pool.get('product.product')
        
        for line in self.browse(cr, uid, ids, context=context):
            if line.valid_ok:
                raise osv.except_osv(_('Error'), _('The line is already validated !'))
            
            product_obj.write(cr, uid, [line.name.id], 
                              {'last_fmc': line.fmc,
                               'last_fmc_reviewed': time.strftime('%Y-%m-%d')},
                               context=context)
            
            self.write(cr, uid, [line.id], {'valid_ok': True}, context=context)
            
        return
    
    def display_graph(self, cr, uid, ids, context={}):
        '''
        Display the graph view of the line
        '''
        raise osv.except_osv('Error !', 'Not implemented')
    
    def product_onchange(self, cr, uid, ids, product_id, context={}):
        '''
        Fill data in the line
        '''
        product_obj = self.pool.get('product.product')
        
        if not product_id:
            return {'value': {'amc': 0.00,
                              'fmc': 0.00,
                              'last_reviewed': 'N/A',
                              'valid_until': False,
                              'valid_ok': False}}
            
        product = product_obj.browse(cr, uid, product_id, context=context)
        amc = product_obj.compute_amc(cr, uid, ids, context=context)
        
        return {'value': {'amc': amc,
                          'fmc': amc,
                          'last_reviewed': product.last_fmc_reviewed,
                          'valid_until': False,
                          'valid_ok': False}}
        
    
monthly_review_consumption_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    _columns = {
        'last_fmc_reviewed': fields.date(string='Last reviewed on', readonly=True),
        'last_fmc': fields.float(string='Last FMC', readonly=True),
    }
    
    def compute_mac(self, cr, uid, ids, context={}):
        '''
        Compute the Monthly Average Consumption
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        line_obj = self.pool.get('real.average.consumption.line')
        rac_obj = self.pool.get('real.average.consumption')
        uom_obj = self.pool.get('product.uom')
        
        rac_domain = [('created_ok', '=', True)]
        res = 0.00
        
        from_date = False
        to_date = False
        
        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
            rac_domain.append(('period_to', '>', from_date))
        
        if context.get('to_date', False):
            to_date = context.get('to_date')
            rac_domain.append(('period_to', '<', to_date))
            
        rac_ids = rac_obj.search(cr, uid, rac_domain, context=context)
        line_ids = line_obj.search(cr, uid, [('rac_id', 'in', rac_ids), ('product_id', 'in', ids)], context=context)
        
        for line in line_obj.browse(cr, uid, line_ids, context=context):
            res += uom_obj._compute_qty(cr, uid, line.uom_id.id, line.consumed_qty, line.product_id.uom_id.id)
            if not context.get('from_date') and (not from_date or line.rac_id.period_to < from_date):
                from_date = line.rac_id.period_to
            if not context.get('to_date') and (not to_date or line.rac_id.period_to > to_date):
                to_date = line.rac_id.period_to
            
        # We want the average for the entire period
        if context.get('average', False):
            if to_date < from_date:
                raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
            # Calculate the # of months in the period
            to_date_str = time.strptime(to_date, '%Y-%m-%d')
            from_date_str = time.strptime(from_date, '%Y-%m-%d')
            
            nb_months = (to_date_str.tm_year-from_date_str.tm_year)*12
            nb_months += to_date_str.tm_mon-from_date_str.tm_mon
            nb_months -= to_date_str.tm_mday < from_date_str.tm_mday and ((from_date_str.tm_mday-to_date_str.tm_mday)/30)
            nb_months += to_date_str.tm_mday > from_date_str.tm_mday and ((to_date_str.tm_mday-from_date_str.tm_mday)/30)
            
            if not nb_months: nb_months = 1
            
            res = res/nb_months
            
        return res
    
    def compute_amc(self, cr, uid, ids, context={}):
        '''
        Compute the Average Monthly Consumption with this formula :
            AMC = (sum(OUTGOING (except reason types Lobn, Donation, Loss, Discrepancy))
                  -
                  sum(INCOMING with reason type Return from unit)) / Number of period's months
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        
        res = 0.00
        
        from_date = False
        to_date = False
        
        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
        
        if context.get('to_date', False):
            to_date = context.get('to_date')
            
        loan_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        donation_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
        donation_exp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
        loss_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
        discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
        return_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]
            
        out_move_ids = move_obj.search(cr, uid, [('state', '=', 'done'),
                                                 ('reason_type_id', 'not in', (loan_id, donation_id, donation_exp_id, loss_id, discrepancy_id)), 
                                                 ('product_id', 'in', ids)], context=context)
        
        for move in move_obj.browse(cr, uid, out_move_ids, context=context):
            if move.reason_type_id.id == return_id:
                res -= uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
            else:
                res += uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
                
            if not context.get('from_date') and (not from_date or move.date_expected < from_date):
                from_date = move.date_expected
            if not context.get('to_date') and (not to_date or move.date_expected > to_date):
                to_date = move.date_expected
                
        if not to_date or not from_date:
            return 0.00
            
        # We want the average for the entire period
        if to_date < from_date:
            raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
        # Calculate the # of months in the period
        to_date_str = time.strptime(to_date, '%Y-%m-%d')
        from_date_str = time.strptime(from_date, '%Y-%m-%d')
        
        nb_months = (to_date_str.tm_year-from_date_str.tm_year)*12
        nb_months += to_date_str.tm_mon-from_date_str.tm_mon
        nb_months -= to_date_str.tm_mday < from_date_str.tm_mday and ((from_date_str.tm_mday-to_date_str.tm_mday)/30)
        nb_months += to_date_str.tm_mday > from_date_str.tm_mday and ((to_date_str.tm_mday-from_date_str.tm_mday)/30)
        
        if not nb_months: nb_months = 1
        
        res = round(res/nb_months, 2)
            
        return res
    
product_product()