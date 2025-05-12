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
from sale import SALE_ORDER_STATE_SELECTION

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
    # # TODO: See if the period state changed in financial part of Unifiedl
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

def common_internal_type_change(self, cr, uid, ids, internal_type, rts, shipment_date, context=None):
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
                                                  'message': _('The number of days between Creation Date and Delivery Expected Date (%s) is less than the supplier lead-time (%s).') % (delta.days, partner.supplier_lt,)})

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
    res.setdefault('value', {}).update({'est_transport_lead_time': lead_time, })
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

def common_onchange_partner_id(self, cr, uid, ids, part=False, order_type=False, date_order=False, transport_lt=0, type=False, res=None, context=None):
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
    res.setdefault('value', {}).update({'transport_type': transport_type, })
    # call onchange_transport_type and update **VALUE** of res
    res_transport_type = self.onchange_transport_type(cr, uid, ids, part=part, transport_type=res['value']['transport_type'], requested_date=res['value']['delivery_requested_date'], context=context)
    res.setdefault('value', {}).update(res_transport_type.setdefault('value', {}))
    # compute partner type
    partner_type = compute_partner_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'partner_type': partner_type, })
    # internal type
    internal_type = compute_internal_type(self, cr, uid, part=part, type=type, context=context)
    res.setdefault('value', {}).update({'internal_type': internal_type, })

    return res

def common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, parent_class, context=None):
    '''
    Checks if dates are later than header dates

    deprecated
    '''
    if context is None:
        context = {}

    return {'value': {'date_planned': requested_date, }}

def common_create(self, cr, uid, data, type, context=None):
    '''
    common for create function so and po
    '''
    if context is None:
        context = {}

    # fill partner_type data
    if data.get('partner_id', False):
        partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id'), context=context)
        # partner type - always set
        data.update({'partner_type': partner.partner_type, })
        # internal type (zone) - always set
        data.update({'internal_type': partner.zone, })
        # transport type - only if not present (can be modified by user to False)
        if 'transport_type' not in data:
            data.update({'transport_type': partner.transport_0, })
        # est_transport_lead_time - only if not present (can be modified by user to False)
        if 'est_transport_lead_time' not in data:
            data.update({'est_transport_lead_time': partner.transport_0_lt, })
        # by default delivery requested date is equal to today + supplier lead time - filled for compatibility because requested date is now mandatory
        if not data.get('delivery_requested_date', False):
            if not context.get('ir_import_id'):
                # PO - supplier lead time / SO - customer lead time
                if type == 'so':
                    requested_date = (datetime.today() + relativedelta(days=partner.customer_lt)).strftime('%Y-%m-%d')
                if type == 'po':
                    requested_date = (datetime.today() + relativedelta(days=partner.supplier_lt)).strftime('%Y-%m-%d')
                data['delivery_requested_date'] = requested_date
            else:
                data['ready_to_ship_date'] = time.strftime('%Y-%m-%d')

    return data


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def write(self, cr, uid, ids, data, context=None):
        '''
        Checks if dates are good before writing
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for order in self.browse(cr, uid, ids, context=context):
            # Fill partner type
            if data.get('partner_id') and isinstance(data.get('partner_id'), str):
                data['partner_id'] = int(data.get('partner_id'))
            partner = self.pool.get('res.partner').browse(cr, uid, data.get('partner_id', order.partner_id.id), context=context)
            # partner type - always set
            data.update({'partner_type': partner.partner_type, })

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
        # common function for so and po
        data = common_create(self, cr, uid, data, type=get_type(self), context=context)
        # ready_to_ship_date only mandatory for so
        if 'ready_to_ship_date' not in data:
            rts = compute_rts(self, cr, uid, data.get('delivery_requested_date'), data.get('est_transport_lead_time'), type=get_type(self), context=context)
            data.update({'ready_to_ship_date': rts, })
        # deprecated ?
        check_dates(self, cr, uid, data, context=context)

        return super(sale_order, self).create(cr, uid, data, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        erase dates
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({'shipment_date': False, })
        fields_to_reset = ['delivery_requested_date', 'ready_to_ship_date', 'date_order', 'delivery_confirmed_date', 'arrival_date']
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        res = super(sale_order, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
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
        'date_order':fields.date(string='Creation Date', required=True, select=True, readonly=True, help="Date on which this document has been created.", states={'draft': [('readonly', False)]}),
        'delivery_requested_date': fields.date(string='Requested Delivery Date'),
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
        'est_transport_lead_time': fields.float(digits=(16, 2), string='Est. Transport Lead Time', help="Estimated Transport Lead-Time in weeks"),
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

    def onchange_partner_id(self, cr, uid, ids, part=False, order_type=False, date_order=False, transport_lt=0, context=None):
        '''
        Fills the Requested and Confirmed delivery dates

        SPRINT3 validated - YAML ok
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        res = super(sale_order, self).onchange_partner_id(cr, uid, ids, part, order_type)
        # compute requested date and transport type
        res = common_onchange_partner_id(self, cr, uid, ids, part=part, order_type=order_type, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        # reset confirmed date
        res.setdefault('value', {}).update({'delivery_confirmed_date': False})

        if res.get('value', {}).get('pricelist_id') and part:
            if ids:
                if isinstance(ids, int):
                    ids = [ids]

                order = self.pool.get('sale.order').browse(cr, uid, ids[0])
                partner = self.pool.get('res.partner').browse(cr, uid, part)
                pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'sale'), ('in_search', '=', partner.partner_type)])
                if order.pricelist_id.id not in pricelist_ids:
                    res.update({'warning': {'title': 'Warning',
                                            'message': 'The currency used currently on the order is not compatible with the new partner. Please change the currency to choose a compatible currency.'}})
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
        return {'name': _('Do you want to update the Requested Delivery Date of all/selected Order lines ?'), }

    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Confirmed Delivery Date of all/selected Order lines ?'), }

    def stock_take_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Date of Stock Take of all/selected Order lines ?'), }

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
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)

sale_order()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    def _get_planned_date(self, cr, uid, context=None):
        '''
            Returns planned_date
        '''
        if context is None:
            context = {}
        order_obj = self.pool.get('sale.order')
        res = datetime.now().strftime('%Y-%m-%d')

        if context.get('sale_id', False):
            so = order_obj.browse(cr, uid, context.get('sale_id'), context=context)
            res = so.delivery_requested_date

        return res

    def _get_default_state(self, cr, uid, context=None):
        '''
        default value for state fields.related

        why, beacause if we try to pass state in the context,
        the context is simply reset without any values specified...
        '''
        if context is None:
            context = {}
        if context.get('sale_id', False):
            order_obj = self.pool.get('sale.order')
            so = order_obj.browse(cr, uid, context.get('sale_id'), context=context)
            return so.state

        return False

    def _get_uom_def(self, cr, uid, context=None):
        if context is None:
            context = {}
        try:
            ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product', 'product_uom_unit')
        except ValueError:
            return False

        if ids:
            return ids[1]
        return False

    _columns = {'date_planned': fields.date(string='Requested DD', required=True, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
                'esti_dd': fields.date(string='Estimated DD', select=True,
                                       help='Header level dates has to be populated by default with the possibility of manual updates'),
                'confirmed_delivery_date': fields.date(string='Confirmed DD',
                                                       help='Header level dates has to be populated by default with the possibility of manual updates.'),
                'so_state_stored': fields.related('order_id', 'state', type='selection', selection=SALE_ORDER_STATE_SELECTION, string='So State', readonly=True,),
                }

    _defaults = {'date_planned': _get_planned_date,
                 'so_state_stored': _get_default_state,
                 'type': lambda *a: 'make_to_order',
                 'product_uom': _get_uom_def,
                 }

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        erase dates
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        if not context.get('keepDateAndDistrib'):
            if 'confirmed_delivery_date' not in default:
                default['confirmed_delivery_date'] = False
        return super(sale_order_line, self).copy_data(cr, uid, id, default=default, context=context)

    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context=None):
        '''
        Checks if dates are later than header dates

        deprecated
        '''
        if context is None:
            context = {}
        return common_dates_change_on_line(self, cr, uid, ids, requested_date, confirmed_date, 'sale.order', context=context)

sale_order_line()


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
            if not result[obj.id].get('min_date') and obj.manual_min_date_stock_picking:
                result.setdefault(obj.id, {}).update({'min_date': obj.manual_min_date_stock_picking})
            elif result[obj.id].get('min_date'):
                continue
            else:
                if obj.purchase_id:
                    result.setdefault(obj.id, {}).update({'min_date': obj.purchase_id.delivery_confirmed_date})
                if obj.sale_id:
                    # rts is a mandatory field
                    if obj.subtype == 'standard':
                        # rts + shipment lt
                        shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                        rts = datetime.strptime(obj.sale_id.ready_to_ship_date, db_date_format)
                        rts = rts + relativedelta(days=shipment_lt or 0)
                        rts = rts.strftime(db_date_format)
                        result.setdefault(obj.id, {}).update({'min_date': rts})
                    elif obj.subtype == 'picking':
                        # rts
                        result.setdefault(obj.id, {}).update({'min_date': obj.sale_id.ready_to_ship_date})
                    elif obj.subtype == 'ppl':
                        # today
                        today = time.strftime(db_date_format)
                        result.setdefault(obj.id, {}).update({'min_date': today})

        return result

    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
        '''
        set the manual conterpart of min_date
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cr.execute("update stock_picking set manual_min_date_stock_picking=%s where id in %s", (value, tuple(ids)))
        return True

    _columns = {'date': fields.datetime('Creation Date', help="Date of Order", select=True),
                'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                                            method=True, store=True, type='datetime', string='Expected Date', select=1,
                                            help="Expected date for the picking to be processed"),
                'manual_min_date_stock_picking': fields.datetime(string='Manual Date'),
                'min_date_manually': fields.boolean(string='change manually')
                }

    _defaults = {'manual_min_date_stock_picking': False,
                 'min_date_manually': False, }

    def change_min_date(self, cr, uid, ids, context=None):
        return {'value': {'min_date_manually': True}}

    def create(self, cr, uid, vals, context=None):
        if not vals.get('purchase id') or not vals.get('sale_id'):
            vals['manual_min_date_stock_picking'] = vals.get('min_date')
        return super(stock_picking, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update all stock moves if the min_date of the picking was changed manually
        '''
        if not ids:
            return True
        move_obj = self.pool.get('stock.move')
        for pick in self.browse(cr, uid, ids, context=context):
            if vals.get('min_date_manually', pick.min_date_manually) and vals.get('min_date', vals.get('manual_min_date_stock_picking')):
                vals.update({'manual_min_date_stock_picking': vals.get('min_date', vals.get('manual_min_date_stock_picking'))})
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', pick.id), ('state', 'not in', ('done', 'cancel'))], context=context)
                move_obj.write(cr, uid, move_ids, {'date_expected': vals.get('min_date', vals.get('manual_min_date_stock_picking'))}, context=context)

        return super(stock_picking, self).write(cr, uid, ids, vals, context=context)

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
            if picking.sale_id and not picking.sale_id.shipment_date and not picking.sale_id.procurement_request:
                sale_id = picking.sale_id.id
                date_format = date_tools.get_date_format(cr, uid, context=context)
                db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
                today = time.strftime(date_format)
                today_db = time.strftime(db_date_format)
                so_obj.write(cr, uid, [sale_id], {'shipment_date': today_db})
                so_obj.log(cr, uid, sale_id, _("Shipment Date of the Field Order '%s' has been updated to %s.") % (picking.sale_id.name, today))
        return res

stock_picking()


class res_company(osv.osv):
    '''
    add time related fields
    '''
    _inherit = 'res.company'

    _columns = {'shipment_lead_time': fields.float(digits=(16, 2), string='Shipment Lead Time'),
                'preparation_lead_time': fields.float(digits=(16, 2), string='Preparation Lead Time'),
                }

    _defaults = {'shipment_lead_time': 0.0,
                 'preparation_lead_time': 0.0,
                 'po_lead': lambda *a: 0.0,  # removed from processes - set to 0.0 for security
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
