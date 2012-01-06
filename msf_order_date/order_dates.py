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
from sale_override import SALE_ORDER_STATE_SELECTION

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

def get_field_description(self, cr, uid, field, context=None):
    '''
    Returns the description of the field
    '''
    if context is None:
        context = {}
    field_obj = self.pool.get('ir.model.fields')
    field_ids = field_obj.search(cr, uid, [('model', '=', self._name), ('name', '=', field)])
    if not field_ids:
        return field
    
    return field_obj.browse(cr, uid, field_ids[0]).field_description

def check_date_order(self, cr, uid, date=False, context=None):
    '''
    Checks if the creation date of the order is in an opened period
    
    @param : date : Creation date
    @return True if the date is in an opened period, False if not
    
    deprecated
    '''
    if context is None:
        context = {}
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

def check_delivery_requested(self, date=False, context=None):
    '''
    Checks if the delivery requested date is equal of a date between today and today + 24 months
    
    @param: Date to test (Delivery requested date)
    @return : False if the date is not in the scale
    
    deprecated
    '''
    if context is None:
        context = {}
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

def check_delivery_confirmed(self, confirmed_date=False, date_order=False, context=None):
    '''
    Checks if the delivery confirmed date is older than the creation date
    
    @param: Date to test (Delivery requested date)
    @return : False if the date is not in the scale
    
    deprecated
    '''
    if context is None:
        context = {}
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

def check_dates(self, cr, uid, data, context=None):
    '''
    Runs all tests on dates
    
    deprecated
    '''
    if context is None:
        context = {}
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
    
    deprecated
    '''
    if context is None:
        context = {}
    v = {}
#    if internal_type == 'international' and rts and not shipment_date:
#        v.update({'shipment_date': rts})
        
    return v
    
def common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=None):
    '''
    Common function when ready_to_ship date is changing
    
    deprecated
    '''
    if context is None:
        context = {}
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
    if context is None:
        context = {}
    field = 'transport_0'
    if part:
        partner_obj = self.pool.get('res.partner')
        res = partner_obj.read(cr, uid, [part], [field], context=context)[0][field]
        return res
        
    return False

def compute_internal_type(self, cr, uid, part=False, type=False, context=None):
    '''
    return the zone of partner
    '''
    if context is None:
        context = {}
    field = 'zone'
    if part:
        partner_obj = self.pool.get('res.partner')
        res = partner_obj.read(cr, uid, [part], [field], context=context)[0][field]
        return res
        
    return False

def compute_partner_type(self, cr, uid, part=False, type=False, context=None):
    '''
    return the partner type
    '''
    if context is None:
        context = {}
    field = 'partner_type'
    if part:
        partner_obj = self.pool.get('res.partner')
        res = partner_obj.read(cr, uid, [part], [field], context=context)[0][field]
        return res
        
    return False

def common_requested_date_change(self, cr, uid, ids, part=False, date_order=False, requested_date=False, transport_lt=0, type=False, res=None, context=None):
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
    # display warning if requested date - creation date < default supplier lead time
    if type == 'po' and part and requested_date and date_order:
        # objects
        date_tools = self.pool.get('date.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        partner = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        # compute delta
        requested = datetime.strptime(requested_date, db_date_format)
        creation = datetime.strptime(date_order, db_date_format)
        delta = requested - creation
        # if < supplier_lt, display warning
        if delta.days < partner.supplier_lt:
            res.setdefault('warning', {}).update({'title': _('Warning'),
                                                  'message': _('The number of days between Creation Date and Delivery Expected Date (%s) is less than the supplier lead-time (%s).'%(delta.days,partner.supplier_lt))})
            
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

def common_onchange_transport_type(self, cr, uid, ids, part=False, transport_type=False, requested_date=False, type=False, res=None, context=None):
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
    # if part, we get a dictionary from get_transport_lead_time
    if lead_time:
        lead_time = lead_time.get(part)
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
    res_requested_date = self.onchange_requested_date(cr, uid, ids, part=part, date_order=date_order, requested_date=res['value']['delivery_requested_date'], transport_lt=transport_lt, context=context)
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
    res_requested_date = self.onchange_requested_date(cr, uid, ids, part=part, date_order=date_order, requested_date=res['value']['delivery_requested_date'], transport_lt=transport_lt, context=context)
    res.setdefault('value', {}).update(res_requested_date.setdefault('value', {}))
    # compute transport type
    transport_type = compute_transport_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'transport_type': transport_type,})
    # call onchange_transport_type and update **VALUE** of res
    res_transport_type = self.onchange_transport_type(cr, uid, ids, part=part, transport_type=res['value']['transport_type'], requested_date=res['value']['delivery_requested_date'], context=context)
    res.setdefault('value', {}).update(res_transport_type.setdefault('value', {}))
    # reset confirmed date
    res.setdefault('value', {}).update({'delivery_confirmed_date': False,})
    # compute partner type
    partner_type = compute_partner_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'partner_type': partner_type,})
    # internal type
    internal_type = compute_internal_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'internal_type': internal_type,})
    
    return res
    
def common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, parent_class, context=None):
    '''
    Checks if dates are later than header dates
    
    deprecated
    '''
    if context is None:
        context = {}
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
    if context.get('update_mode') in ['init', 'update'] or data.get('from_yml_test'):
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
    
    def _get_receipt_date(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the date of the first picking for the the PO
        '''
        if context is None:
            context = {}
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
        if context is None:
            context = {}
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
        if context is None:
            context = {}
        move_values = super(purchase_order, self)._hook_action_picking_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        order_line = kwargs['order_line']
        move_values.update({'date': order_line.confirmed_delivery_date,'date_expected': order_line.confirmed_delivery_date,})
        return move_values
    
    _columns = {
                'delivery_requested_date': fields.date(string='Delivery Requested Date', required=True),
                'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date'),
                'ready_to_ship_date': fields.date(string='Ready To Ship Date'),
                'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
                'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrival of the goods at custom'),
                'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                                string='Receipt Date', help='for a PO, date of the first godd receipt.'),
                # BETA - to know if the delivery_confirmed_date can be erased - to be confirmed
                'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
                # FIELDS PART OF CREATE/WRITE methods
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode',
                        help='Number of days this field has to be associated with a transport mode selection'),
                # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
                'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time',
                        help="Estimated Transport Lead-Time in weeks"),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True,),
                # not a function because a function value is only filled when saved, not with on change of partner id
                # from partner_id object
                'internal_type': fields.selection(string='Type', selection=ZONE_SELECTION, readonly=True,),
                }
    
    _defaults = {
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'confirmed_date_by_synchro': False,
    }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context={}):
        '''
        Set the shipment date if the internal_type == international
        
        deprecated
        '''
        if context is None:
            context = {}
        return {}
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=None):
        '''
        Checks the entered value
        
        deprecated
        '''
        if context is None:
            context = {}
        return {}
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)
    
    def onchange_requested_date(self, cr, uid, ids, part=False, date_order=False, requested_date=False, transport_lt=0, context=None):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
        if context is None:
            context = {}
        res = {}
        # compute ready to ship date
        res = common_requested_date_change(self, cr, uid, ids, part=part, date_order=date_order, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
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
    
    def onchange_date_order(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        date_order is changed (creation date)
        '''
        if context is None:
            context = {}
        res = {}
        # compute requested date
        res = common_onchange_date_order(self, cr, uid, ids, part=part, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res
    
    def onchange_transport_type(self, cr, uid, ids, part=False, transport_type=False, requested_date=False, context=None):
        '''
        transport type changed
        requested date is in the signature because it is needed for children on_change call
        
        '''
        if context is None:
            context = {}
        res = {}
        res = common_onchange_transport_type(self, cr, uid, ids, part=part, transport_type=transport_type, requested_date=requested_date, type=get_type(self), res=res, context=context)
        return res

    def onchange_partner_id(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        Fills the Requested and Confirmed delivery dates
        
        SPRINT3 validated - YAML ok
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        # compute requested date and transport type
        res = common_onchange_partner_id(self, cr, uid, ids, part=part, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res
    
    def requested_data(self, cr, uid, ids, context=None):
        '''
        data for requested
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Requested Date of all order lines ?'),}
    
    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed
        '''
        if context is None:
            context = {}
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
        if context is None:
            context = {}
        result = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', 'in', ids)], context=context)
        return result
    
    def _get_planned_date(self, cr, uid, context=None):
        '''
        Returns planned_date
        
        SPRINT3 validated
        '''
        if context is None:
            context = {}
        order_obj= self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        if context.get('purchase_id', False):
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            res = po.delivery_requested_date
        
        return res

    def _get_confirmed_date(self, cr, uid, context=None):
        '''
        Returns confirmed date
        
        SPRINT3 validated
        '''
        if context is None:
            context = {}
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
                # not replacing the po_state from sale_followup - should ?
                'po_state_stored': fields.related('order_id', 'state', type='selection', selection=PURCHASE_ORDER_STATE_SELECTION, string='Po State', readonly=True,),
                'po_partner_type_stored': fields.related('order_id', 'partner_type', type='selection', selection=PARTNER_TYPE, string='Po Partner Type', readonly=True,),
                }
    
    _defaults = {'po_state_stored': _get_default_state,
                 'po_partner_type_stored': lambda obj, cr, uid, c: c and c.get('partner_type', False),
                 'date_planned': _get_planned_date,
                 'confirmed_delivery_date': _get_confirmed_date,
                 }
    
    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context=None):
        '''
        Checks if dates are later than header dates
        
        deprecated
        '''
        if context is None:
            context = {}
        return common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, 'purchase.order', context=context)

purchase_order_line()


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
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
            
        check_dates(self, cr, uid, data, context=context)
        
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
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        erase shipment date
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({'shipment_date': False,})
        res = super(sale_order, self).copy_data(cr, uid, id, default=default, context=context)
        return res
    
    def _get_receipt_date(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the date of the first picking for the the PO
        '''
        if context is None:
            context = {}
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
        'date_order':fields.date(string='Creation Date', required=True, select=True, readonly=True, help="Date on which this document has been created."),
        'delivery_requested_date': fields.date(string='Delivery Requested Date', required=True),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date'),
        'ready_to_ship_date': fields.date(string='Ready To Ship Date', required=True),
        'shipment_date': fields.date(string='Shipment Date', readonly=True, help='Date on which picking is created at supplier'),
        'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrival of the goods at custom'),
        'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                    string='Receipt Date', help='for a PO, date of the first godd receipt.'),
        # BETA - to know if the delivery_confirmed_date can be erased - to be confirmed
        'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
        # FIELDS PART OF CREATE/WRITE methods
        # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
        'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode',
                        help='Number of days this field has to be associated with a transport mode selection'),
        # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
        'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time', help="Estimated Transport Lead-Time in weeks"),
        # not a function because a function value is only filled when saved, not with on change of partner id
        # from partner_id object
        'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True,),
        # not a function because a function value is only filled when saved, not with on change of partner id
        # from partner_id object
        'internal_type': fields.selection(string='Type', selection=ZONE_SELECTION, readonly=True,),
    }
    
    _defaults = {
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'confirmed_date_by_synchro': False,
    }
    
    def internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=None):
        '''
        Set the shipment date if the internal_type == international
        
        deprecated
        '''
        if context is None:
            context = {}
        return {}
        return {'value': common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=context)}
        
    def ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=None):
        '''
        Checks the entered value
        
        deprecated
        '''
        if context is None:
            context = {}
        return {}
        return common_ready_to_ship_change(self, cr, uid, ids, ready_to_ship, date_order, shipment, context=context)
    
    def onchange_requested_date(self, cr, uid, ids, part=False, date_order=False, requested_date=False, transport_lt=0, context=None):
        '''
        Set the confirmed date with the requested date if the first is not fill
        '''
        if context is None:
            context = {}
        res = {}
        # compute ready to ship date
        res = common_requested_date_change(self, cr, uid, ids, part=part, date_order=date_order, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
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
        
        SPRINT3 validated - YAML ok
        '''
        if context is None:
            context = {}
        res = {}
        res = common_onchange_transport_type(self, cr, uid, ids, part=part, transport_type=transport_type, requested_date=requested_date, type=get_type(self), res=res, context=context)
        return res
    
    def onchange_partner_id(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        Fills the Requested and Confirmed delivery dates
        
        SPRINT3 validated - YAML ok
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
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Requested Date of all order lines ?'),}
    
    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        if context is None:
            context = {}
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
            # deactivated
            if not obj.delivery_confirmed_date and False:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in obj.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': obj.delivery_confirmed_date,})
            
        return super(sale_order, self).action_wait(cr, uid, ids, args)
    
    def _hook_ship_create_stock_move(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for stock move creation
        '''
        if context is None:
            context = {}
        # objects
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        # call super
        move_data = super(sale_order, self)._hook_ship_create_stock_move(cr, uid, ids, context=context, *args, **kwargs)
        order = kwargs['order']
        # get shipment lead time
        shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
        # date = rts of so - by default, a picking is created
        rts = order.ready_to_ship_date
        # date, date_expected
        move_data.update({'date': rts,'date_expected': rts})
        
        return move_data
    
    def _hook_ship_create_procurement_order(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for procurement order creation
        '''
        if context is None:
            context = {}
        # objects
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        # call to super
        result = super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, context=context, *args, **kwargs)
        # date_planned = rts - company.prep_lt
        order = kwargs['order']
        # get value from company
        prep_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)
        # rts - prep_lt
        rts = datetime.strptime(order.ready_to_ship_date, db_date_format)
        rts = rts - relativedelta(days=prep_lt or 0)
        rts = rts.strftime(db_date_format)
        result['date_planned'] = rts
        # update from yml flag
        result['from_yml_test'] = order.from_yml_test
        
        return result
    
sale_order()


class sale_order_line(osv.osv):
    _name= 'sale.order.line'
    _inherit = 'sale.order.line'
    
    def _get_planned_date(self, cr, uid, context=None, *a):
        '''
            Returns planned_date
        '''
        if context is None:
            context = {}
        order_obj= self.pool.get('sale.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        so = order_obj.browse(cr, uid, context.get('sale_id', []))
        if so:
            if so.partner_id.customer_lt:
                res = (datetime.now() + relativedelta(days=so.partner_id.customer_lt)).strftime('%Y-%m-%d')
            
            else:
                res = so.delivery_requested_date
        
        return res

    def _get_confirmed_date(self, cr, uid, context=None, *a):
        '''
            Returns confirmed date
        '''
        if context is None:
            context = {}
        order_obj= self.pool.get('sale.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
        
        if 'delivery_confirmed_date' in context:
            res = context['delivery_confirmed_date']
            return res
        so = order_obj.browse(cr, uid, context.get('sale_id', []))
        if so:
            res = so.delivery_confirmed_date
        
        return res
    
    def _get_default_state(self, cr, uid, context=None):
        '''
        default value for state fields.related
        
        why, beacause if we try to pass state in the context,
        the context is simply reset without any values specified...
        '''
        if context is None:
            context= {}
        if context.get('sale_id', False):
            order_obj= self.pool.get('sale.order')
            so = order_obj.browse(cr, uid, context.get('sale_id'), context=context)
            return so.state
        
        return False
    
    _columns = {'date_planned': fields.date(string='Delivery Requested Date', required=True, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
                'confirmed_delivery_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Header level dates has to be populated by default with the possibility of manual updates.'),
                'so_state_stored': fields.related('order_id', 'state', type='selection', selection=SALE_ORDER_STATE_SELECTION, string='So State', readonly=True,),
                }

    _defaults = {'date_planned': _get_planned_date,
                 'confirmed_delivery_date': _get_confirmed_date,
                 'so_state_stored': _get_default_state,
                 }
    
    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context=None):
        '''
        Checks if dates are later than header dates 
        
        deprecated
        '''
        if context is None:
            context = {}
        return common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, 'sale.order', context=context)
    
sale_order_line()


class procurement_order(osv.osv):
    '''
    date modifications
    '''
    _inherit = 'procurement.order'
    
    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
        
        - allow to modify the data for purchase order line creation
        '''
        if context is None:
            context = {}
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        procurement = kwargs['procurement']
        # date_planned (requested date) = date_planned from procurement order (rts - prepartion lead time)
        # confirmed_delivery_date (confirmed date) = False
        line.update({'date_planned': procurement.date_planned, 'confirmed_delivery_date': False,})
        return line
    
    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
        
        - allow to modify the data for purchase order creation
        '''
        if context is None:
            context = {}
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        line = kwargs['line']
        procurement = kwargs['procurement']
        # update from yml flag
        values['from_yml_test'] = procurement.from_yml_test
        # date_planned (requested date) = date_planned from procurement order (rts - prepartion lead time)
        # confirmed_delivery_date (confirmed date) = False
        # both values are taken from line 
        values.update({'delivery_requested_date': line['date_planned'], 'delivery_confirmed_date': line['confirmed_delivery_date'],})
        return values  

procurement_order()


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
    
    def get_min_max_date(self, cr, uid, ids, field_name, arg, context=None):
        '''
        call super - modify logic for min_date (Expected receipt date)
        '''
        if context is None:
            context = {}
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        result = super(stock_picking, self).get_min_max_date(cr, uid, ids, field_name, arg, context=context)
        # modify the min_date value for delivery_confirmed_date from corresponding purchase_order if exist
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.purchase_id:
                result.setdefault(obj.id, {}).update({'min_date': obj.purchase_id.delivery_confirmed_date,})
            if obj.sale_id:
                # rts is a mandatory field
                if obj.subtype == 'standard':
                    # rts + shipment lt
                    shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                    rts = datetime.strptime(obj.sale_id.ready_to_ship_date, db_date_format)
                    rts = rts + relativedelta(days=shipment_lt or 0)
                    rts = rts.strftime(db_date_format)
                    result.setdefault(obj.id, {}).update({'min_date': rts,})
                if obj.subtype == 'picking':
                    # rts
                    result.setdefault(obj.id, {}).update({'min_date': obj.sale_id.ready_to_ship_date,})
                if obj.subtype == 'ppl':
                    # today
                    today = time.strftime(db_date_format)
                    result.setdefault(obj.id, {}).update({'min_date': today,})
                    
        return result
    
    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
        '''
        call super
        '''
        if context is None:
            context = {}
        result = super(stock_picking, self)._set_minimum_date(cr, uid, ids, name, value, arg, context=context)
        return result

    _columns = {'date': fields.datetime('Creation Date', help="Date of Order", select=True),
                'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                                            method=True, store=True, type='datetime', string='Expected Date', select=1,
                                            help="Expected date for the picking to be processed"),
                }

    # @@@override stock>stock.py>stock_picking>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        '''
        shipment date of sale order is updated and logged
        '''
        if context is None:
            context = {}
        date_tools = self.pool.get('date.tools')
        res = super(stock_picking, self).do_partial(cr, uid, ids, partial_datas, context=context)

        so_obj = self.pool.get('sale.order')

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.sale_id and not picking.sale_id.shipment_date:
                sale_id = picking.sale_id.id
                date_format = date_tools.get_date_format(cr, uid, context=context)
                db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
                today = time.strftime(date_format)
                today_db = time.strftime(db_date_format)
                so_obj.write(cr, uid, [sale_id], {'shipment_date': today_db})
                so_obj.log(cr, uid, sale_id, _("Shipment Date of the Sale Order '%s' has been updated to %s."%(picking.sale_id.name, today)))

        return res

stock_picking()


class stock_move(osv.osv):
    '''
    shipment date of sale order is updated
    '''
    _inherit = 'stock.move'
    
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        '''
        update shipment date and logged
        '''
        if context is None:
            context = {}
        date_tools = self.pool.get('date.tools')
        res = super(stock_move, self).do_partial(cr, uid, ids, partial_datas, context=context)
        
        so_obj = self.pool.get('sale.order')

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.picking_id and obj.picking_id.sale_id and not obj.picking_id.sale_id.shipment_date:
                sale_id = obj.picking_id.sale_id.id
                date_format = date_tools.get_date_format(cr, uid, context=context)
                db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
                today = time.strftime(date_format)
                today_db = time.strftime(db_date_format)
                so_obj.write(cr, uid, [sale_id], {'shipment_date': today_db})
                so_obj.log(cr, uid, sale_id, _("Shipment Date of the Sale Order '%s' has been updated to %s."%(obj.picking_id.sale_id.name, today)))

        return res
    
stock_move()


class lang(osv.osv):
    '''
    define getter for date / time / datetime formats
    '''
    _inherit = 'res.lang'
    
    def _get_format(self, cr, uid, type, context=None):
        '''
        generic function
        '''
        if context is None:
            context = {}
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
    
    def _get_db_format(self, cr, uid, type, context=None):
        '''
        generic function - for now constant values
        '''
        if context is None:
            context = {}
        if type == 'date':
            return '%Y-%m-%d'
        if type == 'time':
            return '%H:%M:%S'
        # default value
        return '%Y-%m-%d'
lang()


class res_company(osv.osv):
    '''
    add time related fields
    '''
    _inherit = 'res.company'
    
    _columns = {'shipment_lead_time': fields.float(digits=(16,2), string='Shipment Lead Time'),
                'preparation_lead_time': fields.float(digits=(16,2), string='Preparation Lead Time'),
                }
    
    _defaults = {'shipment_lead_time': 0.0,
                 'preparation_lead_time': 0.0,
                 'po_lead': lambda *a: 0.0, # removed from processes - set to 0.0 for security
                 }

res_company()


class product_template(osv.osv):
    '''
    set delay to 0 to be sure it does not take part to processes
    '''
    _inherit = "product.template"
    _defaults = {'sale_delay': lambda *a: 0,
                 'produce_delay': lambda *a: 0,
                 }

product_template()
