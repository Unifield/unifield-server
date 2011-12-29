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

import time

from tools.translate import _
from dateutil.relativedelta import relativedelta
from datetime import datetime


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    _columns = {
        'leadtime': fields.integer(string='Lead Time'),
    }
    
    _defaults = {
        'leadtime': lambda *a: 2,
    }
    
res_partner()

fields_date = ['date_order', 'delivery_requested_date', 'delivery_confirmed_date',
               'est_transport_lead_time', 'ready_to_ship_date', 'shipment_date',
               'arrival_date', 'receipt_date']

fields_date_line = ['date_planned', 'confirmed_delivery_date']

def get_field_description(self, cr, uid, field, context={}):
    '''
    Returns the description of the field
    '''
    field_obj = self.pool.get('ir.model.fields')
    field_ids = field_obj.search(cr, uid, [('model', '=', self._name), ('name', '=', field)])
    if not field_ids:
        return field
    
    return field_obj.browse(cr, uid, field_ids[0]).field_description

def check_date_order(self, cr, uid, date=False, context={}):
    '''
    Checks if the creation date of the order is in an opened period
    
    @param : date : Creation date
    @return True if the date is in an opened period, False if not
    '''
    if not date:
        return True
            
    if isinstance(date, datetime):
        date = date.strftime('%Y-%m-%d')
    
    res = False
    
    period_obj = self.pool.get('account.period')
    ## TODO: See if the period state changed in financial part of Unifiedl
    period_ids = period_obj.search(cr, uid, [('state', '=', 'draft')], context=context)
    for p in period_obj.browse(cr, uid, period_ids, context=context):
        if date >= p.date_start and date <= p.date_stop:
            return True
            
    return res

def check_delivery_requested(self, date=False, context={}):
    '''
    Checks if the delivery requested date is equal of a date between today and today + 24 months
    
    @param: Date to test (Delivery requested date)
    @return : False if the date is not in the scale
    '''
    if not date:
        return True

    return True
    
    if isinstance(date, datetime):
        date = date.strftime('%Y-%m-%d')
    
    res = False
    two_years = (datetime.now() + relativedelta(years=2)).strftime('%Y-%m-%d')
    if date >= (datetime.now()).strftime('%Y-%m-%d') and date <= two_years:
        res = True
        
    return res

def check_delivery_confirmed(self, confirmed_date=False, date_order=False, context={}):
    '''
    Checks if the delivery confirmed date is older than the creation date
    
    @param: Date to test (Delivery requested date)
    @return : False if the date is not in the scale
    '''
    if not confirmed_date or not date_order:
        return True

    return True
    
    if isinstance(confirmed_date, datetime):
        confirmed_date = confirmed_date.strftime('%Y-%m-%d')
        
    if isinstance(date_order, datetime):
        date_order = date_order.strftime('%Y-%m-%d')
    
    res = False
    if confirmed_date > date_order:
        res = True
        
    return res 

def check_dates(self, cr, uid, data, context={}):
    '''
    Runs all tests on dates
    '''
    # Comment this line if you would check date on PO/SO creation/write
    return True
    
    date_order = data.get('date_order', False)
    requested_date = data.get('delivery_requested_date', False)
    confirmed_date = data.get('delivery_confirmed_date', False)
    ready_to_ship = data.get('ready_to_ship_date', False)
    # Check if the creation date is in an opened period
    if not check_date_order(self, cr, uid, date_order, context=context):
        raise osv.except_osv(_('Error'), _('The creation date is not in an opened period !'))
    if not check_delivery_requested(self, requested_date, context=context):
        raise osv.except_osv(_('Error'), _('The Delivery Requested Date should be between today and today + 24 months !'))
    if not check_delivery_confirmed(self, confirmed_date, date_order, context=context):
        raise osv.except_osv(_('Error'), _('The Delivery Confirmed Date should be older than the Creation date !'))
    if not check_delivery_confirmed(self, ready_to_ship, date_order, context=context):
        raise osv.except_osv(_('Error'), _('The Ready to Ship Date should be older than the Creation date !'))
    
    return True

def common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
    '''
    Common function when type of order is changing
    '''
    v = {}
#    if internal_type == 'international' and rts and not shipment_date:
#        v.update({'shipment_date': rts})
        
    return v

def common_requested_date_change(self, cr, uid, ids, requested_date, confirmed_date, date_order, leadtime=0, context={}):
    '''
    Common function when requested date is changing
    '''
    message = {}
    v = {}
    if isinstance(leadtime, str):
        leadtime = int(leadtime)
    
    if not confirmed_date:
        confirmed_date = requested_date
    if not date_order:
#        return {'value': {'delivery_confirmed_date': confirmed_date},
        return {'value': {},
                'warning': message}
    
    # Set the message if the user enter a wrong requested date
#    if not check_delivery_requested(self, requested_date, context=context):
#        message = {'title': _('Warning'),
#                   'message': _('The Delivery Requested Date should be between today and today + 24 months !')}
    
    # Set the message if the user enter a wrong confirmed date    
#    if not check_delivery_confirmed(self, confirmed_date, date_order, context):
#        message = {'title': _('Warning'),
#                   'message': _('The Delivery Confirmed Date should be older than the Creation date !')}
    if requested_date and leadtime:
        requested = datetime.strptime(requested_date, '%Y-%m-%d')
        ready_to_ship = requested - relativedelta(days=leadtime)
        v.update({'ready_to_ship_date': ready_to_ship.strftime('%Y-%m-%d')})
        
#    v.update({'delivery_confirmed_date': confirmed_date})
    
    return {'value': v,
            'warning': message}
    
def common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context={}):
    '''
    Common function when ready_to_ship date is changing
    '''
    message = {}
    v = {}
    if not ready_to_ship or not date_order:
        return {}
    
    # Set the message if the user enter a wrong ready to ship date
#    if not check_delivery_confirmed(self, ready_to_ship, date_order, context=context):
#        message = {'title': _('Warning'),
#                   'message': _('The Ready To Ship Date should be older than the Creation date !')}
#    else:
#        if not shipment:
#            v.update({'shipment_date': ready_to_ship})
    if not shipment:
        v.update({'shipment_date': ready_to_ship})
        
    return {'warning': message, 'value': v}

def common_onchange_transport_leadtime(self, cr, uid, ids, requested_date=False, leadtime=0, context={}):
    '''
    Common fonction when transport lead time is changing
    '''
    res = {}
    if requested_date and leadtime!=0.00:
        requested = datetime.strptime(requested_date, '%Y-%m-%d')
        ready_to_ship = requested - relativedelta(days=round(leadtime*7,0))
        res = {'ready_to_ship_date': ready_to_ship.strftime('%Y-%m-%d')}
    
    return {'value': res}

def common_onchange_partner_id(self, cr, uid, ids, part, res={}):
    '''
    Common function when Partner is changing
    '''
    
    requested_date = time.strftime('%Y-%m-%d')
    if part:
        partner = self.pool.get('res.partner').browse(cr, uid, part)
        # TODO: Show the po_lead if it's those of company or those of partner
        requested_date = datetime.strptime(requested_date, '%Y-%m-%d')
        requested_date = requested_date + relativedelta(days=partner.leadtime)
        requested_date = requested_date.strftime('%Y-%m-%d')
    
    if check_delivery_requested(self, requested_date):
        res['value'].update({'delivery_requested_date': requested_date,})
#                             'ready_to_ship_date': requested_date,})
#                             'delivery_confirmed_date': requested_date})
    else:
        res.update({'warning': {'title': _('Warning'), 
                                'message': _('The Delivery Requested Date should be between today and today + 24 months !')}})
    
    return res

def common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, parent_class, context={}):
    '''
    Checks if dates are later than header dates 
    '''
    min_confirmed = min_requested = False
    
    order_id = context.get('active_id', [])
    if isinstance(order_id, (int, long)):
        order_id = [order_id]
        
    if order_id:
        min_confirmed = self.pool.get(parent_class).browse(cr, uid, order_id[0]).delivery_confirmed_date
        min_requested = self.pool.get(parent_class).browse(cr, uid, order_id[0]).delivery_requested_date
    
    for line in self.browse(cr, uid, ids, context=context):
        min_confirmed = line.order_id.delivery_confirmed_date
        min_requested = line.order_id.delivery_requested_date
        
#    if min_confirmed and confirmed_date:
#        if min_confirmed > confirmed_date:
#            return {'warning': {'title': _('Warning'),
#                                'message': _('You cannot define a delivery confirmed date older than the PO delivery confirmed date !')}}
    
#    if min_requested and requested_date:
#        if min_requested > requested_date:
#            return {'warning': {'title': _('Warning'),
#                                'message': _('You cannot define a delivery requested date older than the PO delivery requested date !')}}
#    
    return {'value': {'date_planned': requested_date,}}
#                      'confirmed_delivery_date': confirmed_date}}
        

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit= 'purchase.order'
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Checks if dates are good before writing
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not 'date_order' in data:
            data.update({'date_order': self.browse(cr, uid, ids[0]).date_order})
        
        check_dates(self, cr, uid, data, context=context)
        
        return super(purchase_order, self).write(cr, uid, ids, data, context=context)
    
    def create(self, cr, uid, data, context={}):
        '''
        Checks if dates are good before creation
        '''
        partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'))
        requested_date = (datetime.today() + relativedelta(days=partner.supplier_lt)).strftime('%Y-%m-%d')
        
        if 'delivery_requested_date' not in data:
            data['delivery_requested_date'] = requested_date
#        if 'delivery_confirmed_date' not in data:
#            data['delivery_confirmed_date'] = requested_date
            
        check_dates(self, cr, uid, data, context=context)

        return super(purchase_order, self).create(cr, uid, data, context=context)
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        '''
        Displays the Creation date field as readonly if the user is not in the Purchase / Admin group
        '''
        res = super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
        group_id = False
        
        data_obj = self.pool.get('ir.model.data')
        user_obj = self.pool.get('res.users')
        data_ids = data_obj.search(cr, uid, [('module', '=', 'msf_order_date'), ('model', '=', 'res.groups'),
                                             ('name', '=', 'purchase_admin_group')])
        data_info = data_obj.read(cr, uid, data_ids, ['res_id'])
        if data_info and view_type == 'form':
            group_id = data_info[0]['res_id']
            for g in user_obj.browse(cr, uid, uid).groups_id:
                if g.id == group_id:
                    res['fields']['date_order'].update({'readonly': False})
                    
        return res
    
    def _get_receipt_date(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the date of the first picking for the the PO
        '''
        res = {}
        pick_obj = self.pool.get('stock.picking')
        
        for order in self.browse(cr, uid, ids, context=context):
            pick_ids = pick_obj.search(cr, uid, [('purchase_id', '=', order.id)], offset=0, limit=1, order='date_done', context=context)
            if not pick_ids:
                res[order.id] = False
            else:
                res[order.id] = pick_obj.browse(cr, uid, pick_ids[0]).date_done

        return res

    
    _columns = {
        'date_order': fields.date('Creation Date', select=True, readonly=True, 
                                  required=True, help="Date on which order is created."),
        'delivery_requested_date': fields.date(string='Delivery Requested Date', readonly=True, 
                                            states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]}),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date', 
                                               help='Will be confirmed by supplier for SO could be equal to RTS + estimated transport Lead-Time'),
        'transport_type': fields.selection([('flight', 'By Flight'), ('road', 'By Road'),
                                            ('boat', 'By Boat')], string='Transport Type',
                                            help='Number of days this field has to be associated with a transport mode selection'),
        'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time', help="Estimated Transport Lead-Time in weeks"),
        'ready_to_ship_date': fields.date(string='Ready To Ship Date', 
                                          help='Commitment date = date on which delivery of product is to/can be made.'),
        'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
        'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrical of the goods at custom'),
        'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, readonly=True,
                                         string='Receipt Date', help='for a PO, date of the first godd receipt.'),
        'internal_type': fields.selection([('national', 'National'), #('internal', 'Internal'),
                                        ('international', 'International')], string='Type', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
    }
    
    _defaults = {
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'internal_type': lambda *a: 'national',
    }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
        '''
        Set the shipment date if the internal_type == international
        '''        
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
    
    def requested_date_change(self, cr, uid, ids, requested_date, confirmed_date, date_order, leadtime=0, context={}):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
        message = {}
        v = {}
        line_obj = self.pool.get('purchase.order.line')
        if isinstance(leadtime, str):
            leadtime = int(leadtime)
        
#        if not confirmed_date:
#            confirmed_date = requested_date
        if not date_order:
            #return {'value': {'delivery_confirmed_date': confirmed_date},
            return {'value': {},
                    'warning': message}
        
        # Set the message if the user enter a wrong requested date
        if not check_delivery_requested(self, requested_date, context=context):
            message = {'title': _('Warning'),
                       'message': _('The Delivery Requested Date should be between today and today + 24 months !')}
        
        # Set the message if the user enter a wrong confirmed date    
        if not check_delivery_confirmed(self, confirmed_date, date_order, context):
            message = {'title': _('Warning'),
                       'message': _('The Delivery Confirmed Date should be older than the Creation date !')}
        if requested_date:
            requested = datetime.strptime(requested_date, '%Y-%m-%d')
#            ready_to_ship = requested - relativedelta(days=leadtime)
#            v.update({'ready_to_ship_date': ready_to_ship.strftime('%Y-%m-%d')})
            # Change the date on all lines
            line_ids = line_obj.search(cr, uid, [('order_id', 'in', ids)])
            #line_obj.write(cr, uid, line_ids, {'date_planned': requested_date, 'confirmed_delivery_date': confirmed_date})
            line_obj.write(cr, uid, line_ids, {'date_planned': requested_date, })
            
        v.update({'delivery_confirmed_date': confirmed_date})
        
        return {'value': v,
                'warning': message}
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context={}):
        '''
        Checks the entered value
        '''
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)
    
    def onchange_transport_leadtime(self, cr, uid, ids, requested_date=False, leadtime=0, context={}):
        '''
        Fills the Ready to ship date
        '''
        return common_onchange_transport_leadtime(self, cr, uid, ids, requested_date, leadtime, context=context)

    
    def onchange_partner_id(self, cr, uid, ids, part):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        
        return common_onchange_partner_id(self, cr, uid, ids, part, res)
        return res
    
purchase_order()


class purchase_order_line(osv.osv):
    _name= 'purchase.order.line'
    _inherit = 'purchase.order.line'
    
    _columns = {
        'date_planned': fields.date(string='Requested Date', required=True, select=True,
                                    help='Header level dates has to be populated by default with the possibility of manual updates'),
        'confirmed_delivery_date': fields.date(string='Confirmed Delivery Date',
                                               help='Header level dates has to be populated by default with the possibility of manual updates.'),
    }
    
    def _get_planned_date(self, cr, uid, context):
        '''
            Returns planned_date
        '''
        order_obj= self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        po = order_obj.browse(cr, uid, context.get('purchase_id', []))
        if po:
            res = po.delivery_requested_date
        
        return res

    def _get_confirmed_date(self, cr, uid, context):
        '''
            Returns confirmed date
        '''
        order_obj= self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
       
        if context.get('purchase_id', []): 
            po_id = context.get('purchase_id', [])
            res = order_obj.browse(cr, uid, po_id, context=context).delivery_confirmed_date
        
        return res

    _defaults = {
        'date_planned': _get_planned_date,
        'confirmed_delivery_date': _get_confirmed_date,
    }
    
    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context={}):
        '''
        Checks if dates are later than header dates 
        '''
        return common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, 'purchase.order', context=context)

    
purchase_order_line()

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Checks if dates are good before writing
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        if not 'date_order' in data:
            data.update({'date_order': self.browse(cr, uid, ids[0]).date_order})
            
        check_dates(self, cr, uid, data, context=context)
        
        return super(sale_order, self).write(cr, uid, ids, data, context=context)
    
    def create(self, cr, uid, data, context={}):
        '''
        Checks if dates are good before creation
        '''
        partner = False
        if data.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'))
        requested_date = (datetime.today() + relativedelta(days=(partner and partner.leadtime) and partner.leadtime or 0)).strftime('%Y-%m-%d')
        if 'delivery_requested_date' not in data:
            data['delivery_requested_date'] = requested_date
#        if 'delivery_confirmed_date' not in data:
#            data['delivery_confirmed_date'] = requested_date
        
        check_dates(self, cr, uid, data, context=context)
        
        return super(sale_order, self).create(cr, uid, data, context=context)
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        '''
        Displays the Creation date field as readonly if the user is not in the Purchase / Admin group
        '''
        res = super(sale_order, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        
        group_id = False
        
        data_obj = self.pool.get('ir.model.data')
        user_obj = self.pool.get('res.users')
        data_ids = data_obj.search(cr, uid, [('module', '=', 'msf_order_date'), ('model', '=', 'res.groups'),
                                             ('name', '=', 'sale_admin_group')])
        data_info = data_obj.read(cr, uid, data_ids, ['res_id'])
        if data_info and view_type == 'form':
            group_id = data_info[0]['res_id']
            for g in user_obj.browse(cr, uid, uid).groups_id:
                if g.id == group_id:
                    res['fields']['date_order'].update({'readonly': False})
                    
        return res
    
    def _get_receipt_date(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the date of the first picking for the the PO
        '''
        res = {}
        pick_obj = self.pool.get('stock.picking')
        
        for order in self.browse(cr, uid, ids, context=context):
            pick_ids = pick_obj.search(cr, uid, [('sale_id', '=', order.id)], offset=0, limit=1, order='date_done', context=context)
            if not pick_ids:
                res[order.id] = False
            else:
                res[order.id] = pick_obj.browse(cr, uid, pick_ids[0]).date_done
            
        return res

    
    _columns = {
        'date_order': fields.date('Creation Date', select=True, readonly=True, 
                                  required=True, help="Date on which order is created."),
        'delivery_requested_date': fields.date(string='Delivery Requested Date', readonly=True, #required=True, 
                                            states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]}),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date', #required=True, 
                                               help='Will be confirmed by supplier for SO could be equal to RTS + estimated transport Lead-Time'),
        'transport_type': fields.selection([('flight', 'By Flight'), ('road', 'By Road'),
                                            ('boat', 'By Boat')], string='Transport Type',
                                            help='Number of days this field has to be associated with a transport mode selection'),
        'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time', help="Estimated Transport Lead-Time in weeks"),
        'ready_to_ship_date': fields.date(string='Ready To Ship Date', 
                                          help='Commitment date = date on which delivery of product is to/can be made.'),
        'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
        'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrical of the goods at custom'),
        'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, readonly=True,
                                         string='Receipt Date', help='for a PO, date of the first godd receipt.'),
        'internal_type': fields.selection([('national', 'National'), #('internal', 'Internal'),
                                        ('international', 'International')], string='Type', readonly=True, states={'draft': [('readonly', False)]}),
    }
    
    _defaults = {
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'internal_type': lambda *a: 'national',
    }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
        '''
        Set the shipment date if the internal_type == international
        '''
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
    
    def requested_date_change(self, cr, uid, ids, requested_date, confirmed_date, date_order, leadtime=0, context={}):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
        return common_requested_date_change(self, cr, uid, ids, requested_date, confirmed_date, date_order, leadtime, context=context)
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context={}):
        '''
        Checks the entered value
        '''
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)

    
    def onchange_transport_leadtime(self, cr, uid, ids, requested_date=False, leadtime=0, context={}):
        '''
        Fills the Ready to ship date
        '''
        return common_onchange_transport_leadtime(self, cr, uid, ids, requested_date, leadtime, context=context)
    
    def onchange_partner_id(self, cr, uid, ids, part):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(sale_order, self).onchange_partner_id(cr, uid, ids, part)
        
        return common_onchange_partner_id(self, cr, uid, ids, part, res)
    
sale_order()


class sale_order_line(osv.osv):
    _name= 'sale.order.line'
    _inherit = 'sale.order.line'
    
    _columns = {
        'date_planned': fields.date(string='Requested Date', required=True, select=True,
                                    help='Header level dates has to be populated by default with the possibility of manual updates'),
        'confirmed_delivery_date': fields.date(string='Confirmed Delivery Date',
                                               help='Header level dates has to be populated by default with the possibility of manual updates.'),
    }
    
    def _get_planned_date(self, cr, uid, context, *a):
        '''
            Returns planned_date
        '''
        order_obj= self.pool.get('sale.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        so = order_obj.browse(cr, uid, context.get('sale_id', []))
        if so:
            if so.partner_id.customer_lt:
                res = (datetime.now() + relativedelta(days=so.partner_id.customer_lt)).strftime('%Y-%m-%d')
            
            else:
                res = so.delivery_requested_date
        
        return res

    def _get_confirmed_date(self, cr, uid, context, *a):
        '''
            Returns confirmed date
        '''
        order_obj= self.pool.get('sale.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        po = order_obj.browse(cr, uid, context.get('sale_id', []))
        if po:
            res = po.delivery_confirmed_date
        
        return res

    _defaults = {
        'date_planned': _get_planned_date,
        'confirmed_delivery_date': _get_confirmed_date,
    }
    
    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context={}):
        '''
        Checks if dates are later than header dates 
        '''
        return common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, 'sale.order', context=context)
            
    
sale_order_line()


class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    # @@@overwrite purchase.procurement_order.make_po
    def make_po(self, cr, uid, ids, context=None):
        '''
        Overwritten the default method to change the requested date of purchase lines
        '''
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        res = super(procurement_order, self).make_po(cr, uid, ids, context=context)
        
        for key in res:
            purchase = po_obj.browse(cr, uid, res.get(key))
            for line in purchase.order_line:
                pol_obj.write(cr, uid, [line.id], {'date_planned': (datetime.now()+relativedelta(days=+2)).strftime('%Y-%m-%d')})
        
        return res
    # @@@end

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
