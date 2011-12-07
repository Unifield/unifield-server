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

def common_onchange_partner_id(self, cr, uid, ids, part=False, res=None, date_order=False):
    '''
    Common function when Partner is changing
    
    VALIDATED for sprint3
    '''
    if res is None:
        res = {}
    requested_date = False
    
    # reset the confirmed date
    res['value'].update({'delivery_confirmed_date': False,})
    # reset transport type field
    res['value'].update({'transport_type': '',})
    
    if part:
        partner = self.pool.get('res.partner').browse(cr, uid, part)
        # update transport type field
        res['value'].update({'transport_type': partner.transport_0,})
        # update the partner type field
        res['value'].update({'partner_type': partner.partner_type,})
        # with order_date, update requested_date
        if date_order:
            requested_date = datetime.strptime(date_order, '%Y-%m-%d')
            requested_date = requested_date + relativedelta(days=partner.supplier_lt)
            requested_date = requested_date.strftime('%Y-%m-%d')
            res['value'].update({'delivery_requested_date': requested_date,})
    
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
            
        # fill partner_type
        if data.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
            data.update({'partner_type': partner.partner_type,})
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
        
        # fill partner_type
        if data.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
            data.update({'partner_type': partner.partner_type,})
            # erase delivery_confirmed_date if partner_type is internal or section and the date is not filled by synchro - considered updated by synchro by default
            if partner.partner_type in ('internal', 'section') and not data.get('confirmed_date_by_synchro', True):
                data.update({'delivery_confirmed_date': False,})
        
        if 'delivery_requested_date' not in data and data.get('partner_id', False):
            # by default delivery requested date is equal to today + supplier lead time - filled for compatibility because requested date is now mandatory
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
            requested_date = (datetime.today() + relativedelta(days=partner.supplier_lt)).strftime('%Y-%m-%d')
            data['delivery_requested_date'] = requested_date
        
        # if comes from automatique data - fill confirmed date
        if context.get('update_mode') in ['init', 'update']:
            data['delivery_confirmed_date'] = '2011-12-06'
            
        check_dates(self, cr, uid, data, context=context)
        
        return super(purchase_order, self).create(cr, uid, data, context=context)
    
#    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
#        '''
#        Displays the Creation date field as readonly if the user is not in the Purchase / Admin group
#        '''
#        res = super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type)
#        
#        group_id = False
#        
#        data_obj = self.pool.get('ir.model.data')
#        user_obj = self.pool.get('res.users')
#        data_ids = data_obj.search(cr, uid, [('module', '=', 'msf_order_date'), ('model', '=', 'res.groups'),
#                                             ('name', '=', 'purchase_admin_group')])
#        data_info = data_obj.read(cr, uid, data_ids, ['res_id'])
#        if data_info and view_type == 'form':
#            group_id = data_info[0]['res_id']
#            for g in user_obj.browse(cr, uid, uid).groups_id:
#                if g.id == group_id:
#                    res['fields']['date_order'].update({'readonly': False})
#                    
#        return res
    
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
    
    _columns = {'date_order':fields.date('Creation Date', readonly=True, required=True,
                                         states={'draft':[('readonly',False)],}, select=True, help="Date on which this document has been created."),
                'delivery_requested_date': fields.date(string='Delivery Requested Date', required=True,),
                'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Will be confirmed by supplier for SO could be equal to RTS + estimated transport Lead-Time'),
                'transport_type': fields.selection(readonly=True, selection=TRANSPORT_TYPE, string='Transport Mode',),
                'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time', help="Estimated Transport Lead-Time in weeks"),
                'ready_to_ship_date': fields.date(string='Ready To Ship Date', 
                                                  help='Commitment date = date on which delivery of product is to/can be made.'),
                'shipment_date': fields.date(readonly=True, string='Shipment Date', help='Date on which picking is created at supplier'),
                'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrical of the goods at custom'),
                'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                                string='Receipt Date', help='for a PO, date of the first godd receipt.'),
                'internal_type': fields.selection([('national', 'National'), #('internal', 'Internal'),
                                                   ('international', 'International')], string='Type', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
                'history_ids': fields.one2many('history.order.date', 'purchase_id', string='Dates History'),
                # not a function because a function value is only filled when saved, not with on change of partner id
                'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True,),
                # to know if the delivery_confirmed_date can be erased - to be confirmed
                'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
                }
    
    _defaults = {'date_order': lambda *a: time.strftime('%Y-%m-%d'),
                 'internal_type': lambda *a: 'national',
                 'confirmed_date_by_synchro': False,
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

    def onchange_partner_id_order_date(self, cr, uid, ids, part, date_order):
        '''
        Fills the Requested and Confirmed delivery dates
        
        SPRINT3 VALIDATED
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        
        res = common_onchange_partner_id(self, cr, uid, ids, part=part, res=res, date_order=date_order)
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
        
#        for line in self.browse(cr, uid, ids):
#            if 'date_planned' in data:
#                if line.order_id.delivery_requested_date > data['date_planned']:
#                    raise osv.except_osv(_('Error'), _('You cannot have a Delivery Requested date for a line older than the Order Delivery Requested Date'))
#            if data.get('confirmed_delivery_date', False):
#                 if line.order_id.delivery_confirmed_date > data['confirmed_delivery_date']:
#                    raise osv.except_osv(_('Error'), _('You cannot have a Delivery Confirmed date for a line older than the Order Delivery Confirmed Date'))
        
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
            # update the function_updated flag - dirty hack to used attrs on dates when the fields function have not yet been updated...
            obj.write({'function_updated': True}, context=context)
        
        return result
    
    def _get_line_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        self is purchase.order
        '''
        result = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', 'in', ids)], context=context)
        return result
    
    _columns = {'date_planned': fields.date(string='Requested Date', required=True, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
                'confirmed_delivery_date': fields.date(string='Delivery Confirmed Date',
                                                       help='Header level dates has to be populated by default with the possibility of manual updates.'),
                'history_ids': fields.one2many('history.order.date', 'purchase_line_id', string='Dates History'),
                # not replacing the po_state from sale_followup
                'po_state_stored': fields.function(_vals_get_order_date, method=True, type='selection', selection=PURCHASE_ORDER_STATE_SELECTION,
                                                   string='Po State', multi='get_vals_order_date',
                                                   store={'purchase.order': (_get_line_ids_from_po_ids, ['state'], 10),
                                                          'purchase.order.line': (lambda self, cr, uid, ids, c={}: ids, ['order_id'], 10)}),
                'po_partner_type_stored': fields.function(_vals_get_order_date, method=True, type='selection', selection=PARTNER_TYPE,
                                                          string='Po Partner Type', multi='get_vals_order_date',
                                                          store={'purchase.order': (_get_line_ids_from_po_ids, ['partner_type'], 10),
                                                                 'purchase.order.line': (lambda self, cr, uid, ids, c={}: ids, ['order_id'], 10)}),
                'function_updated': fields.boolean(readonly=True, string='Functions updated'),
                }
    _defaults = {'function_updated': False,}
    
    
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
        
        create_history(self, cr, uid, ids, data, 'sale.order', 'sale_id', fields_date, context=context)
        
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
        'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True, 
                                         string='Receipt Date', help='for a PO, date of the first godd receipt.'),
        'internal_type': fields.selection([('national', 'National'), #('internal', 'Internal'),
                                        ('international', 'International')], string='Type', readonly=True, states={'draft': [('readonly', False)]}),
        'history_ids': fields.one2many('history.order.date', 'sale_id', string='Dates History'),
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
    
    _columns = {
        'date_planned': fields.date(string='Requested Date', required=True, select=True,
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

