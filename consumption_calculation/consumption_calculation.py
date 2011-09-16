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

import time
import base64


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _description = 'Real Average Consumption'
    _rec_name = 'period_from'
    
    def _get_nb_lines(self, cr, uid, ids, field_name, args, context={}):
        '''
        Returns the # of lines on the real average consumption
        '''
        res = {}
        
        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)
            
        return res
    
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
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
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
                'view_mode': 'form,tree',
                'res_id': ids[0],
                }
        
    def import_rac(self, cr, uid, ids, context={}):
        '''
        Launches the wizard to import lines from a file
        '''
        context.update({'active_id': ids[0]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.rac',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }
        
    def export_rac(self, cr, uid, ids, context={}):
        '''
        Creates a CSV file and launches the wizard to save it
        '''
        rac = self.browse(cr, uid, ids[0], context=context)
        
        export = 'Product reference;Product name;Product UoM;Consumed Qty;Remark'
        export += '\n'
        
        for line in rac.line_ids:
            export += '%s;%s;%s;%s;%s' % (line.name.default_code, line.name.name, line.uom_id.id, line.consumed_qty, line.remark)
            export += '\n'
            
        file = base64.encodestring(export.encode("utf-8"))
        
        export_id = self.pool.get('wizard.export.rac').create(cr, uid, {'rac_id': ids[0], 'file': file, 
                                                                        'filename': 'rac_%s.csv' % (rac.cons_location_id.name.replace(' ', '_')), 
                                                                        'message': 'The RAC lines has been exported. Please click on Save As button to download the file'})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.export.rac',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                }
        
    def nomen_change(self, cr, uid, ids, nomen_id, context={}):
        context.update({'test_id': nomen_id})
        
        return {}
    
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
    }
    
    def product_onchange(self, cr, uid, ids, product_id, context={}):
        '''
        Set the product uom when the product change
        '''
        v = {}
        
        if product_id:
            uom = self.pool.get('product.product').browse(cr, uid, product_id, context=context).uom_id.id
            v.update({'uom_id': uom})
        else:
            v.update({'uom_id': False})
        
        return {'value': v}
    
real_average_consumption_line()


class monthly_review_consumption(osv.osv):
    _name = 'monthly.review.consumption'
    _description = 'Monthly review consumption'
    
    def _get_nb_lines(self, cr, uid, ids, field_name, args, context={}):
        '''
        Returns the # of lines on the monthly review consumption
        '''
        res = {}
        
        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)
            
        return res
    
    _columns = {
        'creation_date': fields.date(string='Creation date'),
        'cons_location_id': fields.many2one('stock.location', string='Location', domain=[('usage', '=', 'internal')], required=True),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'line_ids': fields.one2many('monthly.review.consumption.line', 'mrc_id', string='Lines'),
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
    }
    
    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'period_to': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def import_fmc(self, cr, uid, ids, context={}):
        '''
        Launches the wizard to import lines from a file
        '''
        context.update({'active_id': ids[0]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fmc',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }
        
    def export_fmc(self, cr, uid, ids, context={}):
        '''
        Creates a CSV file and launches the wizard to save it
        '''
        fmc = self.browse(cr, uid, ids[0], context=context)
        
        export = 'Product reference;Product name;FMC;Valid until'
        export += '\n'
        
        for line in fmc.line_ids:
            export += '%s;%s;%s;%s' % (line.name.default_code, line.name.name, line.fmc, line.valid_until or '')
            export += '\n'
            
        file = base64.encodestring(export.encode("utf-8"))
        
        export_id = self.pool.get('wizard.export.fmc').create(cr, uid, {'fmc_id': ids[0], 'file': file, 
                                                                        'filename': 'fmc_%s.csv' % (fmc.cons_location_id.name.replace(' ', '_')), 
                                                                        'message': 'The FMC lines has been exported. Please click on Save As button to download the file'})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.export.fmc',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
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
    
    def _get_last_fmc(self, cr, uid, ids, field_name, args, context={}):
        '''
        Returns the last fmc date
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            context.update({'sloc_id': line.mrc_id.cons_location_id.id})
            res[line.id] = self.product_onchange(cr, uid, line.id, line.name.id, context=context).get('value', None).get('last_reviewed', None)
            
        return res
    
    _columns = {
        'name': fields.many2one('product.product', string='Product', required=True),
        'amc': fields.function(_get_amc, string='AMC', method=True, readonly=True),
        'fmc': fields.float(digits=(16,2), string='FMC'),
        'last_reviewed': fields.function(_get_last_fmc, method=True, type='date', string='Last reviewed on', readonly=True),
        'valid_until': fields.date(string='Valid until'),
        'valid_ok': fields.boolean(string='OK', readonly=True),
        'mrc_id': fields.many2one('monthly.review.consumption', string='MRC', required=True, ondelete='cascade'),
    }
    
    def valid_line(self, cr, uid, ids, context={}):
        '''
        Valid the line and enter data in product form
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
                
        for line in self.browse(cr, uid, ids, context=context):
            if line.valid_ok:
                raise osv.except_osv(_('Error'), _('The line is already validated !'))
            
            self.write(cr, uid, [line.id], {'valid_ok': True}, context=context)
            
        return
    
    def display_graph(self, cr, uid, ids, context={}):
        '''
        Display the graph view of the line
        '''
        raise osv.except_osv('Error !', 'Not implemented yet !')
    
    def product_onchange(self, cr, uid, ids, product_id, context={}):
        '''
        Fill data in the line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')
        
        last_fmc_reviewed = None
        
        if not product_id:
            return {'value': {'amc': 0.00,
                              'fmc': 0.00,
                              'last_reviewed': None,
                              'valid_until': False,
                              'valid_ok': False}}
        
        if context.get('sloc_id', False):
            mrc_ids = self.pool.get('monthly.review.consumption').search(cr, uid, [('cons_location_id', '=', context.get('sloc_id'))], context=context)
            line_ids = line_obj.search(cr, uid, [('name', '=', product_id), ('mrc_id', 'in', mrc_ids)], order='valid_until desc', context=context)
            
            for line in self.browse(cr, uid, [line_ids[0]], context=context):
                last_fmc_reviewed = line.mrc_id.creation_date
                
                    
        amc = product_obj.compute_amc(cr, uid, ids, context=context)
        
        return {'value': {'amc': amc,
                          'fmc': amc,
                          'last_reviewed': last_fmc_reviewed,
                          'valid_until': False,
                          'valid_ok': False}}
        
    
monthly_review_consumption_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _compute_fmc(self, cr, uid, ids, field_name, args, context={}):
        '''
        Returns the last value of the FMC
        '''
        if not context:
            context = {}
            
        res = {}
        location_ids = []
        fmc_obj = self.pool.get('monthly.review.consumption')
        fmc_line_obj = self.pool.get('monthly.review.consumption.line')
        
        # Filter for some locations only
        if context.get('location_id', False):
            if type(context['location_id']) == type(1):
                location_ids = [context['location_id']]
            elif type(context['location_id']) in (type(''), type(u'')):
                location_ids = self.pool.get('stock.location').search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context.get('location_id', [])
        else:
            location_ids = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
            
        # Search all Review report for locations
        fmc_ids = fmc_obj.search(cr, uid, [('cons_location_id', 'in', location_ids)], context=context)
        
        for product in ids:
            res[product] = 0.00
            last_date = False
            
            # Search all validated lines with the product
            line_ids = fmc_line_obj.search(cr, uid, [('name', '=', product), ('valid_ok', '=', True), ('mrc_id', 'in', fmc_ids)], context=context)
            
            # Get the last created line
            for line in fmc_line_obj.browse(cr, uid, line_ids, context=context):
                if not last_date:
                    last_date = line.valid_until or line.mrc_id.period_to
                    res[product] = line.fmc
                elif line.valid_until and line.valid_until > last_date:
                    last_date = line.valid_until
                    res[product] = line.fmc
                elif line.mrc_id.period_to > last_date:
                    last_date = line.mrc_id.period_to
                    res[product] = line.fmc                
        
        return res
    
    def compute_mac(self, cr, uid, ids, field_name, args, context={}):
        '''
        Compute the Real Average Consumption
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        line_obj = self.pool.get('real.average.consumption.line')
        rac_obj = self.pool.get('real.average.consumption')
        uom_obj = self.pool.get('product.uom')
        
        rac_domain = [('created_ok', '=', True)]
        res = {}
        
        from_date = False
        to_date = False
        
        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
            rac_domain.append(('period_to', '>', from_date))
        
        if context.get('to_date', False):
            to_date = context.get('to_date')
            rac_domain.append(('period_to', '<', to_date))
        
        # Filter for one or some locations    
        if context.get('location_id', False):
            if type(context['location_id']) == type(1):
                location_ids = [context['location_id']]
            elif type(context['location_id']) in (type(''), type(u'')):
                location_ids = self.pool.get('stock.location').search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context.get('location_id', [])
            
            # Update the domain of research
            rac_domain.append(('location_id', 'in', location_ids))
        
        
        rac_ids = rac_obj.search(cr, uid, rac_domain, context=context)
        
        for id in ids:
            res[id] = 0.00
            line_ids = line_obj.search(cr, uid, [('rac_id', 'in', rac_ids), ('product_id', '=', id)], context=context)
            
            for line in line_obj.browse(cr, uid, line_ids, context=context):
                res[id] += uom_obj._compute_qty(cr, uid, line.uom_id.id, line.consumed_qty, line.product_id.uom_id.id)
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
                
                uom_id = self.browse(cr, uid, ids[0], context=context).uom_id.id
                res[id] = res[id]/nb_months
                res[id] = self.pool.get('product.uom')._compute_qty(cr, uid, uom_id, res[id], uom_id)
            
        return res
    
    def compute_amc(self, cr, uid, ids, context={}):
        '''
        Compute the Average Monthly Consumption with this formula :
            AMC = (sum(OUTGOING (except reason types Loan, Donation, Loss, Discrepancy))
                  -
                  sum(INCOMING with reason type Return from unit)) / Number of period's months
        '''
        if not context:
            context = {}
        
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
            
        # Get all reason types
        loan_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        donation_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
        donation_exp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
        loss_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
        discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
        return_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]

        # Update the domain
        domain = [('state', '=', 'done'), ('reason_type_id', 'not in', (loan_id, donation_id, donation_exp_id, loss_id, discrepancy_id)), ('product_id', 'in', ids)]
        
        # Add locations filters in domain if locations are passed in context
        if context.get('location_id', False):
            if type(context['location_id']) == type(1):
                location_ids = [context['location_id']]
            elif type(context['location_id']) in (type(''), type(u'')):
                location_ids = self.pool.get('stock.location').search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context.get('location_id', [])
            domain.append('|')
            domain.append(('location_id', 'in', location_ids))
            domain.append(('location_dest_id', 'in', location_ids))
        
        
        out_move_ids = move_obj.search(cr, uid, domain, context=context)
        
        for move in move_obj.browse(cr, uid, out_move_ids, context=context):
            if move.reason_type_id.id == return_id and move.type == 'in':
                res -= uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
            elif move.type == 'out':
                res += uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
            
            # Update the limit in time
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
        try:
            to_date_str = time.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            to_date_str = time.strptime(to_date, '%Y-%m-%d %H:%M:%S')
        
        try:
            from_date_str = time.strptime(from_date, '%Y-%m-%d')
        except ValueError:
            from_date_str = time.strptime(from_date, '%Y-%m-%d %H:%M:%S')
        
        nb_months = (to_date_str.tm_year-from_date_str.tm_year)*12
        nb_months += to_date_str.tm_mon-from_date_str.tm_mon
        nb_months -= to_date_str.tm_mday < from_date_str.tm_mday and ((from_date_str.tm_mday-to_date_str.tm_mday)/30)
        nb_months += to_date_str.tm_mday > from_date_str.tm_mday and ((to_date_str.tm_mday-from_date_str.tm_mday)/30)
        
        if not nb_months: nb_months = 1
        
        uom_id = self.browse(cr, uid, ids[0], context=context).uom_id.id
        res = res/nb_months
        res = self.pool.get('product.uom')._compute_qty(cr, uid, uom_id, res, uom_id)
            
        return res
    
    
    _columns = {
        'procure_delay': fields.float(digits=(16,2), string='Procurement Lead Time', 
                                        help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'monthly_consumption': fields.function(compute_mac, method=True, string='Monthly consumption', readonly=True),
        'reviewed_consumption': fields.function(_compute_fmc, method=True, type='float', string='Forecasted Monthly Consumption', readonly=True),
    }
    
    _defaults = {
        'procure_delay': lambda *a: 1,
    }

    
product_product()
