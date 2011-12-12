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

# import partner_type from msf_partner
from msf_partner import PARTNER_TYPE
from msf_order_date import TRANSPORT_TYPE
from msf_order_date import ZONE_SELECTION
from purchase_override import PURCHASE_ORDER_STATE_SELECTION

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

def get_type(self):
    '''
    return type corresponding to object
    '''
    if self._name == 'sale.order':
        return 'so'
    if self._name == 'purchase.order':
        return 'po'
    
    return False

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

def create_history(self, cr, uid, ids, data, class_name, field_name, fields, context={}):
    '''
    Creates an entry in dates history of the object self._name
    '''
    history_obj = self.pool.get('history.order.date')
    
    for order in self.pool.get(class_name).read(cr, uid, ids, fields, context=context):
        for field in fields:
            if field in data and data.get(field, False) != order[field]:
                history_obj.create(cr, uid, {'name': get_field_description(self, cr, uid, field),
                                             field_name: order['id'],
                                             'old_value': order[field] or False,
                                             'new_value': data.get(field, False),
                                             'user_id': uid,
                                             'time': time.strftime('%y-%m-%d %H:%M:%S')})
                
    return

def common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
    '''
    Common function when type of order is changing
    '''
    v = {}
#    if internal_type == 'international' and rts and not shipment_date:
#        v.update({'shipment_date': rts})
        
    return v
    
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

def compute_rts(self, cr, uid, requested_date=False, transport_lt=0, type=False, context=None):
    '''
    requested - transport lt - shipment lt
    '''
    if context is None:
        context = {}
    company_obj = self.pool.get('res.company')
    # need request_date for computation
    if requested_date:
        company_id = company_obj._company_default_get(cr, uid, False, context=context)
        if type == 'so':
            company_id = company_obj._company_default_get(cr, uid, 'sale.order', context=context)
        if type == 'po':
            company_id = company_obj._company_default_get(cr, uid, 'purchase.order', context=context)
        shipment_lt = company_obj.read(cr, uid, [company_id], ['shipment_lead_time'], context=context)[0]['shipment_lead_time']
        requested = datetime.strptime(requested_date, '%Y-%m-%d')
        rts = requested - relativedelta(days=transport_lt or 0)
        rts = rts - relativedelta(days=shipment_lt or 0)
        rts = rts.strftime('%Y-%m-%d')
        return rts
    
    return False

def compute_requested_date(self, cr, uid, part=False, date_order=False, type=False, context=None):
    '''
    compute requested date according to type
    
    SPRINT3 validated - yaml test ok
    '''
    if context is None:
        context = {}
    # part and date_order are need for computation
    if part and date_order:
        partner = self.pool.get('res.partner').browse(cr, uid, part)
        requested_date = datetime.strptime(date_order, '%Y-%m-%d')
        if type == 'so':
            requested_date = requested_date + relativedelta(days=partner.customer_lt)
        if type == 'po':
            requested_date = requested_date + relativedelta(days=partner.supplier_lt)
        requested_date = requested_date.strftime('%Y-%m-%d')
        return requested_date
    
    return False

def compute_transport_type(self, cr, uid, part=False, type=False, context=None):
    '''
    return the preferred transport type of partner
    '''
    if part:
        partner_obj = self.pool.get('res.partner')
        res = partner_obj.read(cr, uid, [part], ['transport_0'], context=context)[0]['transport_0']
        return res
        
    return False

def common_requested_date_change(self, cr, uid, ids, requested_date=False, transport_lt=0, type=False, res=None, context=None):
    '''
    Common function when requested date is changing
    '''
    if context is None:
        context = {}
    if res is None:
        res = {}
    # compute rts - only for so
    if type == 'so':
        rts = compute_rts(self, cr, uid, requested_date=requested_date, transport_lt=transport_lt, type=type, context=context)
        res.setdefault('value', {}).update({'ready_to_ship_date': rts})
    return res

def common_onchange_transport_lt(self, cr, uid, ids, requested_date=False, transport_lt=0, type=False, res=None, context=None):
    '''
    Common fonction when transport lead time is changed
    '''
    if context is None:
        context = {}
    if res is None:
        res = {}
    # compute rts - only for so
    if type == 'so':
        rts = compute_rts(self, cr, uid, requested_date=requested_date, transport_lt=transport_lt, type=type, context=context)
        res.setdefault('value', {}).update({'ready_to_ship_date': rts})
    return res

def common_onchange_transport_type(self, cr, uid, ids, part=False, transport_type=False, type=False, res=None, context=None):
    '''
    fills the estimated transport lead time corresponding to the selected transport,
    0.0 if no transport selected
    '''
    if context is None:
        context = {}
    if res is None:
        res = {}
    # get the value if partner
    partner_obj = self.pool.get('res.partner')
    # returns a dictionary
    lead_time = partner_obj.get_transport_lead_time(cr, uid, part, transport_type, context=context)
    lead_time = lead_time and lead_time.get(part) or lead_time
    res.setdefault('value', {}).update({'est_transport_lead_time': lead_time,})
    # call onchange_transport_lt and update **VALUE** of res
    res_transport_lt = self.onchange_transport_lt(cr, uid, ids, requested_date=requested_date, transport_lt=res['value']['est_transport_lead_time'], context=None)
    res.setdefault('value', {}).update(res_transport_lt.setdefault('value', {}))
    return res

def common_onchange_date_order(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, type=False, res=None, context=None,):
    '''
    Common function when the Creation date (order_date) is changed
    
    - modify requested date
    - call on_change_requested_date
    '''
    if context is None:
        context = {}
    if res is None:
        res = {}
    # compute requested date
    requested_date = compute_requested_date(self, cr, uid, part=part, date_order=date_order, type=type, context=context)
    res.setdefault('value', {}).update({'delivery_requested_date': requested_date})
    # call onchange_requested_date and update **VALUE** of res
    res_requested_date = self.onchange_requested_date(cr, uid, ids, requested_date=res['value']['delivery_requested_date'], transport_lt=transport_lt, context=context)
    res.setdefault('value', {}).update(res_requested_date.setdefault('value', {}))
    
    return res

def common_onchange_partner_id(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, type=False, res=None, context=None):
    '''
    Common function when Partner is changing
    '''
    if context is None:
        context = {}
    if res is None:
        res = {}
    # compute requested date
    requested_date = compute_requested_date(self, cr, uid, part=part, date_order=date_order, type=type, context=context)
    res.setdefault('value', {}).update({'delivery_requested_date': requested_date})
    # call onchange_requested_date and update **VALUE** of res
    res_requested_date = self.onchange_requested_date(cr, uid, ids, requested_date=res['value']['delivery_requested_date'], transport_lt=transport_lt, context=context)
    res.setdefault('value', {}).update(res_requested_date.setdefault('value', {}))
    # compute transport type
    transport_type = compute_transport_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'transport_type': transport_type,})
    # call onchange_transport_type and update **VALUE** of res
    res_transport_type = self.onchange_transport_type(cr, uid, ids, part=part, transport_type=res['value']['transport_type'], requested_date=res['value']['delivery_requested_date'], context=context)
    res.setdefault('value', {}).update(res_transport_type.setdefault('value', {}))
    
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
         
    return {'value': {'date_planned': requested_date,}}
#                      'confirmed_delivery_date': confirmed_date}}

def common_create(self, cr, uid, data, type, context=None):
    '''
    common for create function so and po
    '''
    if context is None:
        context = {}
        
    # if comes from automatic data - fill confirmed date
    if context.get('update_mode') in ['init', 'update']:
        data['delivery_confirmed_date'] = '2011-12-06'
        
    # fill partner_type data
    if data.get('partner_id', False):
        partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
        # partner type - always set
        data.update({'partner_type': partner.partner_type,})
        # internal type (zone) - always set
        data.update({'internal_type': partner.zone,})
        # transport type - only if not present (can be modified by user to False)
        if 'transport_type' not in data:
            data.update({'transport_type': partner.transport_0,})
        # est_transport_lead_time - only if not present (can be modified by user to False)
        if 'est_transport_lead_time' not in data:
            data.update({'est_transport_lead_time': partner.transport_0_lt,})
        # by default delivery requested date is equal to today + supplier lead time - filled for compatibility because requested date is now mandatory    
        if not data.get('delivery_requested_date', False):
            # PO - supplier lead time / SO - customer lead time
            if type == 'so':
                requested_date = (datetime.today() + relativedelta(days=partner.customer_lt)).strftime('%Y-%m-%d')
            if type == 'po':
                requested_date = (datetime.today() + relativedelta(days=partner.supplier_lt)).strftime('%Y-%m-%d')
            data['delivery_requested_date'] = requested_date
        
    return data
        

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit= 'purchase.order'
    
    def write(self, cr, uid, ids, data, context=None):
        '''
        Checks if dates are good before writing
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if not 'date_order' in data:
            data.update({'date_order': self.browse(cr, uid, ids[0]).date_order})
            
        # fill partner_type and zone
        if data.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
            # partner type - always set
            data.update({'partner_type': partner.partner_type,})
            # internal type (zone) - always set
            data.update({'internal_type': partner.zone,})
            # erase delivery_confirmed_date if partner_type is internal or section and the date is not filled by synchro - considered updated by synchro by default
            if partner.partner_type in ('internal', 'section') and not data.get('confirmed_date_by_synchro', True):
                data.update({'delivery_confirmed_date': False,})
        
        check_dates(self, cr, uid, data, context=context)
        
        create_history(self, cr, uid, ids, data, 'purchase.order', 'purchase_id', fields_date, context=context)
            
        return super(purchase_order, self).write(cr, uid, ids, data, context=context)
    
    def create(self, cr, uid, data, context=None):
        '''
        Checks if dates are good before creation
        
        Delivery Requested Date: creation date + supplier lead time from partner (supplier_lt)
        '''
        if context is None:
            context = {}
        # common function for so and po
        data = common_create(self, cr, uid, data, type=get_type(self), context=context)
        # fill partner_type data
        if data.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
            # erase delivery_confirmed_date if partner_type is internal or section and the date is not filled by synchro - considered updated by synchro by default
            if partner.partner_type in ('internal', 'section') and not data.get('confirmed_date_by_synchro', True):
                data.update({'delivery_confirmed_date': False,})
        # deprecated ?
        check_dates(self, cr, uid, data, context=context)
        
        return super(purchase_order, self).create(cr, uid, data, context=context)
    
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
    
    def _get_vals_order_dates(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return function values
        '''
        res = {}
        pick_obj = self.pool.get('stock.picking')
        
        if isinstance(field_name, str):
            field_name = [field_name] 
        
        for obj in self.browse(cr, uid, ids, context=context):
            # default dic
            res[obj.id] = {}
            # default value
            for f in field_name:
                res[obj.id].update({f:False})
            # get corresponding partner type
            if obj.partner_id:
                partner_type = obj.partner_id.partner_type
                res[obj.id]['partner_type'] = partner_type
            
        return res
    
    def _hook_action_picking_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        modify data for stock move creation
        - date is set to False
        - date_expected is set to delivery_confirmed_date
        '''
        move_values = super(purchase_order, self)._hook_action_picking_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        order_line = kwargs['order_line']
        move_values.update({'date': order_line.confirmed_delivery_date,'date_expected': order_line.confirmed_delivery_date,})
        return move_values
    
    _columns = {'date_order':fields.date(string='Creation Date', readonly=True, required=True,
                                         states={'draft':[('readonly',False)],}, select=True, help="Date on which this document has been created."),
                'delivery_requested_date': fields.date(string='Delivery Requested Date', required=True,),
                'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Will be confirmed by supplier for SO could be equal to RTS + estimated transport Lead-Time'),
                'ready_to_ship_date': fields.date(string='Ready To Ship Date', 
                                                  help='Commitment date = date on which delivery of product is to/can be made.'),
                'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
                'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrical of the goods at custom'),
                'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                                string='Receipt Date', help='for a PO, date of the first godd receipt.'),
                'history_ids': fields.one2many('history.order.date', 'purchase_id', string='Dates History'),
                # BETA - to know if the delivery_confirmed_date can be erased - to be confirmed
                'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
                # FIELDS PART OF CREATE/WRITE methods
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode',),
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time',),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True,),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'internal_type': fields.selection(string='Type', selection=ZONE_SELECTION, readonly=True,),
                }
    
    _defaults = {'date_order': lambda *a: time.strftime('%Y-%m-%d'),
                 'confirmed_date_by_synchro': False,
                 }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
        '''
        Set the shipment date if the internal_type == international
        '''        
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
    
    def onchange_requested_date(self, cr, uid, ids, requested_date=False, transport_lt=0, context=None):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
#        message = {}
#        v = {}
#        line_obj = self.pool.get('purchase.order.line')
#        if isinstance(leadtime, str):
#            leadtime = int(leadtime)
#        
##        if not confirmed_date:
##            confirmed_date = requested_date
#        if not date_order:
#            #return {'value': {'delivery_confirmed_date': confirmed_date},
#            return {'value': {},
#                    'warning': message}
#        
#        # Set the message if the user enter a wrong requested date
#        if not check_delivery_requested(self, requested_date, context=context):
#            message = {'title': _('Warning'),
#                       'message': _('The Delivery Requested Date should be between today and today + 24 months !')}
#        
#        # Set the message if the user enter a wrong confirmed date    
#        if not check_delivery_confirmed(self, confirmed_date, date_order, context):
#            message = {'title': _('Warning'),
#                       'message': _('The Delivery Confirmed Date should be older than the Creation date !')}
#        if requested_date:
#            requested = datetime.strptime(requested_date, '%Y-%m-%d')
##            ready_to_ship = requested - relativedelta(days=leadtime)
##            v.update({'ready_to_ship_date': ready_to_ship.strftime('%Y-%m-%d')})
#            # Change the date on all lines
#            line_ids = line_obj.search(cr, uid, [('order_id', 'in', ids)])
#            #line_obj.write(cr, uid, line_ids, {'date_planned': requested_date, 'confirmed_delivery_date': confirmed_date})
#            line_obj.write(cr, uid, line_ids, {'date_planned': requested_date, })
#            
#        v.update({'delivery_confirmed_date': confirmed_date})
#        
#        return {'value': v,
#                'warning': message}
        return {}
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context={}):
        '''
        Checks the entered value
        '''
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)
    
    def onchange_transport_lt(self, cr, uid, ids, requested_date=False, leadtime=0, context={}):
        '''
        Fills the Ready to ship date
        '''
        return common_onchange_transport_lt(self, cr, uid, ids, requested_date, leadtime, context=context)
    
    def onchange_transport_type(self, cr, uid, ids, part, transport_type, context=None):
        '''
        transport type changed
        '''
        if context is None:
            context = {}
        res = {}
        res = common_onchange_transport_type(self, cr, uid, ids, part=part, transport_type=transport_type, type=get_type(self), res=res, context=context)
        return res

    def onchange_partner_id(self, cr, uid, ids, part, date_order, context=None):
        '''
        Fills the Requested and Confirmed delivery dates
        
        
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        
        #res = common_onchange_partner_id(self, cr, uid, ids, part=part, res=res, date_order=date_order, type=get_type(self),)
        return res
    
    def requested_data(self, cr, uid, ids, context=None):
        '''
        data for requested
        '''
        return {'name': _('Do you want to update the Requested Date of all order lines ?'),}
    
    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed
        '''
        return {'name': _('Do you want to update the Confirmed Delivery Date of all order lines ?'),}
    
    def update_date(self, cr, uid, ids, context=None):
        '''
        open the update lines wizard
        '''
        # we need the context
        if context is None:
            context = {}
        # field name
        field_name = context.get('field_name', False)
        assert field_name, 'The button is not correctly set.'
        # data
        data = getattr(self, field_name + '_data')(cr, uid, ids, context=context)
        name = data['name']
        model = 'update.lines'
        obj = self.pool.get(model)
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)
    
    def wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        Checks if the Delivery Confirmed Date has been filled
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        for order in self.browse(cr, uid, ids, context=context):
            if not order.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in order.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': order.delivery_confirmed_date,}, context=context)
            
        return super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)
    
purchase_order()


class purchase_order_line(osv.osv):
    _name= 'purchase.order.line'
    _inherit = 'purchase.order.line'
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Create history if date values changed
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        create_history(self, cr, uid, ids, data, 'purchase.order.line', 'purchase_line_id', fields_date_line, context=context)
                    
        return super(purchase_order_line, self).write(cr, uid, ids, data, context=context)
    
    def _vals_get_order_date(self, cr, uid, ids, fields, arg, context=None):
        '''
        get values for functions
        '''
        if context is None:
            context = {}
        if isinstance(fields, str):
            fields = [fields]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f: False})
            # po state
            result[obj.id]['po_state_stored'] = obj.order_id.state
            # po partner type
            result[obj.id]['po_partner_type_stored'] = obj.order_id.partner_type
        
        return result
    
    def _get_line_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        self is purchase.order
        '''
        result = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', 'in', ids)], context=context)
        return result
    
    def _get_planned_date(self, cr, uid, context):
        '''
        Returns planned_date
        
        SPRINT3 validated
        '''
        order_obj= self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        if context.get('purchase_id', False):
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            res = po.delivery_requested_date
        
        return res

    def _get_confirmed_date(self, cr, uid, context):
        '''
        Returns confirmed date
        
        SPRINT3 validated
        '''
        order_obj= self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
       
        if context.get('purchase_id', False):
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            res = po.delivery_confirmed_date
        
        return res
    
    def _get_default_state(self, cr, uid, context=None):
        '''
        default value for state fields.related
        
        why, beacause if we try to pass state in the context,
        the context is simply reset without any values specified...
        '''
        if context is None:
            context= {}
        if context.get('purchase_id', False):
            order_obj= self.pool.get('purchase.order')
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            return po.state
        
        return False
    
    _columns = {'date_planned': fields.date(string='Delivery Requested Date', required=True, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
                'confirmed_delivery_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Header level dates has to be populated by default with the possibility of manual updates.'),
                'history_ids': fields.one2many('history.order.date', 'purchase_line_id', string='Dates History'),
                # not replacing the po_state from sale_followup - should ?
                'po_state_stored': fields.related('order_id', 'state', type='selection', selection=PURCHASE_ORDER_STATE_SELECTION, string='Po State', readonly=True,),
                'po_partner_type_stored': fields.related('order_id', 'partner_type', type='selection', selection=PARTNER_TYPE, string='Po Partner Type', readonly=True,),
                }
    
    _defaults = {'po_state_stored': _get_default_state,
                 'po_partner_type_stored': lambda obj, cr, uid, c: c and c.get('partner_type', False),
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
        
        create_history(self, cr, uid, ids, data, 'sale.order', 'sale_id', fields_date, context=context)
        
        return super(sale_order, self).write(cr, uid, ids, data, context=context)
    
    def create(self, cr, uid, data, context=None):
        '''
        Checks if dates are good before creation
        '''
        if context is None:
            context = {}
        company_obj = self.pool.get('res.company')
        # common function for so and po
        data = common_create(self, cr, uid, data, type=get_type(self), context=context)
        # ready_to_ship_date only mandatory for so
        if 'ready_to_ship_date' not in data:
            rts = compute_rts(self, cr, uid, data.get('delivery_requested_date'), data.get('est_transport_lead_time'), type=get_type(self), context=context)
            data.update({'ready_to_ship_date': rts,})
        # deprecated ?
        check_dates(self, cr, uid, data, context=context)
        
        return super(sale_order, self).create(cr, uid, data, context=context)
    
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
    
    _columns = {'date_order':fields.date(string='Creation Date', required=True, select=True, help="Date on which this document has been created."),
                'delivery_requested_date': fields.date(string='Delivery Requested Date', required=True,),
                'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Will be confirmed by supplier for SO could be equal to RTS + estimated transport Lead-Time'),
                'ready_to_ship_date': fields.date(string='Ready To Ship Date', required=True,
                                                  help='Commitment date = date on which delivery of product is to/can be made.'),
                'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
                'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrical of the goods at custom'),
                'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                                string='Receipt Date', help='for a PO, date of the first godd receipt.'),
                'history_ids': fields.one2many('history.order.date', 'sale_id', string='Dates History'),
                # BETA - to know if the delivery_confirmed_date can be erased - to be confirmed
                'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
                # FIELDS PART OF CREATE/WRITE methods
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode',),
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time',),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True,),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'internal_type': fields.selection(string='Type', selection=ZONE_SELECTION, readonly=True,),
                }
    
    _defaults = {'date_order': lambda *a: time.strftime('%Y-%m-%d'),
                 'confirmed_date_by_synchro': False,
                 }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
        '''
        Set the shipment date if the internal_type == international
        '''
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context={}):
        '''
        Checks the entered value
        '''
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)
    
    def onchange_requested_date(self, cr, uid, ids, requested_date=False, transport_lt=0, context=None):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
        if context is None:
            context = {}
        res = {}
        # compute ready to ship date
        res = common_requested_date_change(self, cr, uid, ids, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res

    def onchange_transport_lt(self, cr, uid, ids, requested_date=False, transport_lt=0, context=None):
        '''
        Fills the Ready to ship date
        
        SPRINT3 validated - YAML ok
        '''
        if context is None:
            context = {}
        res = {}
        # compute ready to ship date
        res = common_onchange_transport_lt(self, cr, uid, ids, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res
    
    def onchange_transport_type(self, cr, uid, ids, part=False, transport_type=False, requested_date=False, context=None):
        '''
        transport type changed
        
        requested date is in the signature because it is needed for children on_change call
        '''
        if context is None:
            context = {}
        res = {}
        res = common_onchange_transport_type(self, cr, uid, ids, part=part, transport_type=transport_type, type=get_type(self), res=res, context=context)
        return res
    
    def onchange_partner_id(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        Fills the Requested and Confirmed delivery dates
        
        
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        res = super(sale_order, self).onchange_partner_id(cr, uid, ids, part)
        # compute requested date and transport type
        res = common_onchange_partner_id(self, cr, uid, ids, part=part, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res
    
    def onchange_date_order(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        date_order is changed (creation date)
        
        SPRINT3 validated - YAML ok
        '''
        if context is None:
            context = {}
        res = {}
        # compute requested date
        res = common_onchange_date_order(self, cr, uid, ids, part=part, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res
    
    def requested_data(self, cr, uid, ids, context=None):
        '''
        data for requested for change line wizard
        '''
        return {'name': _('Do you want to update the Requested Date of all order lines ?'),}
    
    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        return {'name': _('Do you want to update the Confirmed Delivery Date of all order lines ?'),}
    
    def update_date(self, cr, uid, ids, context=None):
        '''
        open the update lines wizard
        '''
        # we need the context
        if context is None:
            context = {}
        # field name
        field_name = context.get('field_name', False)
        assert field_name, 'The button is not correctly set.'
        # data
        data = getattr(self, field_name + '_data')(cr, uid, ids, context=context)
        name = data['name']
        model = 'update.lines'
        obj = self.pool.get(model)
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)
    
    def action_wait(self, cr, uid, ids, *args):
        '''
        check delivery_confirmed_date field
        '''
        for obj in self.browse(cr, uid, ids):
            if not obj.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in obj.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': obj.delivery_confirmed_date,})
            
        return super(sale_order, self).action_wait(cr, uid, ids, args)
    
sale_order()


class sale_order_line(osv.osv):
    _name= 'sale.order.line'
    _inherit = 'sale.order.line'
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Create history if date values changed
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
#        for line in self.browse(cr, uid, ids):
#            if 'date_planned' in data:
#                if line.order_id.delivery_requested_date > data['date_planned']:
#                    raise osv.except_osv(_('Error'), _('You cannot have a Delivery Requested date for a line older than the Order Delivery Requested Date'))
#            if data.get('confirmed_delivery_date', False):
#                 if line.order_id.delivery_confirmed_date > data['confirmed_delivery_date']:
#                    raise osv.except_osv(_('Error'), _('You cannot have a Delivery Confirmed date for a line older than the Order Delivery Confirmed Date'))
        
        create_history(self, cr, uid, ids, data, 'sale.order.line', 'sale_line_id', fields_date_line, context=context)
                    
        return super(sale_order_line, self).write(cr, uid, ids, data, context=context)
    
    _columns = {'date_planned': fields.date(string='Requested Date', required=True, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
                'confirmed_delivery_date': fields.date(string='Confirmed Delivery Date',
                                                       help='Header level dates has to be populated by default with the possibility of manual updates.'),
                'history_ids': fields.one2many('history.order.date', 'sale_line_id', string='Dates History'),
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


class history_order_date(osv.osv):
    _name = 'history.order.date'
    _description = 'Date history'
    
    _columns = {
        'name': fields.char(size=128, string='Modified field', required=True),
        'purchase_id': fields.many2one('purchase.order', string='Order'),
        'purchase_line_id': fields.many2one('purchase.order.line', string='Line'),
        'sale_id': fields.many2one('sale.order', string='Order'),
        'sale_line_id': fields.many2one('sale.order.line', string='Line'),
        'old_value': fields.char(size=64, string='Old value'),
        'new_value': fields.char(size=64, string='New value'),
        'user_id': fields.many2one('res.users', string='User'),
        'time': fields.datetime(string='Time', required=True),
    }
    
    _defaults = {
        'time': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
history_order_date()


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


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
    
    def get_min_max_date(self, cr, uid, ids, field_name, arg, context=None):
        '''
        call super - modify logic for min_date (Expected receipt date)
        '''
        result = super(stock_picking, self).get_min_max_date(cr, uid, ids, field_name, arg, context=context)
        # modify the min_date value for delivery_confirmed_date from corresponding purchase_order if exist
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.purchase_id:
                result.setdefault(obj.id, {}).update({'min_date': obj.purchase_id.delivery_confirmed_date,})
        return result
    
    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
        '''
        call super
        '''
        result = super(stock_picking, self)._set_minimum_date(cr, uid, ids, name, value, arg, context=context)
        return result

    _columns = {'date': fields.datetime('Creation Date', help="Date of Order", select=True),
                'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                                            method=True, store=True, type='datetime', string='Expected Receipt Date', select=1,
                                            help="Expected date for the picking to be processed"),
                }

    # @@@override stock>stock.py>stock_picking>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        '''
        Write the shipment date on accoding order
        '''
        date_tools = self.pool.get('date.tools')
        res = super(stock_picking, self).do_partial(cr, uid, ids, partial_datas, context=context)

        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.sale_id and not picking.sale_id.shipment_date:
                date_format = date_tools.get_date_format(cr, uid, context=context)
                so_obj.write(cr, uid, [picking.sale_id.id], {'shipment_date': picking.date_done})

        return res

stock_picking()


class lang(osv.osv):
    '''
    define getter for date / time / datetime formats
    '''
    _inherit = 'res.lang'
    
    def _get_format(self, cr, uid, type, context=None):
        '''
        generic function
        '''
        type = type + '_format'
        assert type in self._columns, 'Specified format field does not exist'
        user_obj = self.pool.get('res.users')
        # get user context lang
        user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        # get coresponding id
        lang_id = self.search(cr, uid, [('code','=',user_lang)])
        # return format value or from default function if not exists
        format = lang_id and self.read(cr, uid, lang_id[0], [type], context=context)[type] or getattr(self, '_get_default_%s'%type)(cr, uid, context=context)
        return format
    
lang()


class res_company(osv.osv):
    '''
    add time related fields
    '''
    _inherit = 'res.company'
    
    _columns = {'shipment_lead_time': fields.float(digits=(16,2), string='Shipment Lead Time'),
                }
    
    _defaults = {'shipment_lead_time': 0.0,
                 }

res_company()
