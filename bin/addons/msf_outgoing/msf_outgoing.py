# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import netsvc
from datetime import datetime, date

from order_types.stock import check_cp_rw
from msf_order_date import TRANSPORT_TYPE
from msf_partner import PARTNER_TYPE

from dateutil.relativedelta import relativedelta
import tools
import time
from lxml import etree
from tools.sql import drop_view_if_exists


class stock_parcel_id(osv.osv):
    _name = 'stock.parcel_id'

    _columns = {
        'name': fields.char('Parcel ID', size=256),
        'pack_id': fields.integer('Pack id'),
    }
stock_parcel_id()



class stock_warehouse(osv.osv):
    """
    Add new packing, dispatch and distribution locations for input
    """
    _inherit = 'stock.warehouse'
    _name = "stock.warehouse"

    _columns = {
        'lot_packing_id': fields.many2one(
            'stock.location',
            string='Location Packing',
            required=True,
            domain=[('usage', '<>', 'view')]
        ),
        'lot_dispatch_id': fields.many2one(
            'stock.location',
            string='Location Dispatch',
            required=True,
            domain=[('usage', '<>', 'view')]
        ),
        'lot_distribution_id': fields.many2one(
            'stock.location',
            string='Location Distribution',
            required=True,
            domain=[('usage', '<>', 'view')]
        ),
    }

    def default_get(self, cr, uid, fields_list, context=None, from_web=False):
        """
        Get the default locations
        """
        # Objects
        data_get = self.pool.get('ir.model.data').get_object_reference

        if context is None:
            context = {}

        res = super(stock_warehouse, self).default_get(cr, uid, fields_list, context=context, from_web=from_web)

        res['lot_packing_id'] = data_get(cr, uid, 'msf_outgoing', 'stock_location_packing')[1]
        res['lot_dispatch_id'] = data_get(cr, uid, 'msf_outgoing', 'stock_location_dispatch')[1]
        res['lot_distribution_id'] = data_get(cr, uid, 'msf_outgoing', 'stock_location_distribution')[1]

        return res

stock_warehouse()


class pack_type(osv.osv):
    """
    Type of pack (name, length, width, height) like bag, box...
    """
    _name = 'pack.type'
    _description = 'Pack Type'
    _columns = {
        'name': fields.char(string='Name', size=1024),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
    }

pack_type()


class shipment(osv.osv):
    '''
    a shipment presents the data from grouped stock moves in a 'sequence' way
    '''
    _name = 'shipment'
    _description = 'Shipment'

    def copy(self, cr, uid, copy_id, default=None, context=None):
        '''
        prevent copy
        '''
        raise osv.except_osv(_('Error !'), _('Shipment copy is forbidden.'))

    def copy_data(self, cr, uid, copy_id, default=None, context=None):
        '''
        reset one2many fields
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        # reset one2many fields
        default.update(pack_family_memory_ids=[], in_ref=False)
        return super(shipment, self).copy_data(cr, uid, copy_id, default=default, context=context)

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi function for global shipment values
        '''
        picking_obj = self.pool.get('stock.picking')
        pack_family_obj = self.pool.get('pack.family.memory')
        curr_obj = self.pool.get('res.currency')

        result = {}
        shipment_result = self.read(cr, uid, ids, ['pack_family_memory_ids', 'state'], context=context)
        pack_family_list = []
        for shipment in shipment_result:
            pack_family_list.extend(shipment['pack_family_memory_ids'])
        pack_family_result = pack_family_obj.read(cr, uid, pack_family_list,
                                                  ['not_shipped', 'state', 'num_of_packs', 'total_weight',
                                                   'total_volume', 'total_amount', 'currency_id'])

        pack_family_dict = dict((x['id'], x) for x in pack_family_result)

        for shipment in shipment_result:
            default_values = {
                'total_amount': 0.0,
                'currency_id': False,
                'num_of_packs': 0,
                'total_weight': 0.0,
                'total_volume': 0.0,
                'state': 'draft',
                'backshipment_id': False,
                'packing_list': False,
            }
            result[shipment['id']] = default_values
            current_result = result[shipment['id']]
            # gather the state from packing objects, all packing must have the same state for shipment
            # for draft shipment, we can have done packing and draft packing
            packing_ids = picking_obj.search(cr, uid, [('shipment_id', '=', shipment['id'])], order='id', context=context)
            # fields to check and get
            state = None
            backshipment_id = None
            # delivery validated
            delivery_validated = None
            # browse the corresponding packings
            for packing in picking_obj.browse(cr, uid, packing_ids, fields_to_fetch=['state', 'delivered',
                                                                                     'backorder_id'], context=context):
                # state check
                # because when the packings are validated one after the other, it triggers the compute of state, and if we have multiple packing for this shipment, it will fail
                # if one packing is draft, even if other packing have been shipped, the shipment must stay draft until all packing are done
                if state not in ('draft', 'assigned'):
                    state = packing.state

                # all corresponding shipment must be dev validated or not
                if packing.delivered:
                    # integrity check
                    if delivery_validated is not None and delivery_validated != packing.delivered:
                        # two packing have different delivery validated values -> problem
                        assert False, 'All packing do not have the same validated value - %s - %s' % (delivery_validated, packing.delivered)
                    # update the value
                    delivery_validated = packing.delivered

                # backshipment_id check
                #if backshipment_id and packing.backorder_id and packing.backorder_id.shipment_id and backshipment_id != packing.backorder_id.shipment_id.id:
                #    assert False, 'all packing of the shipment have not the same draft shipment correspondance - %s - %s' % (backshipment_id, packing.backorder_id.shipment_id.id)
                backshipment_id = packing.backorder_id and packing.backorder_id.shipment_id.id or False
            # if state is in ('draft', 'done', 'cancel'), the shipment keeps the same state
            if state not in ('draft', 'done', 'cancel',):
                state = 'shipped'
            elif state == 'done':
                if delivery_validated:
                    # special state corresponding to delivery validated
                    state = 'delivered'

            current_result['backshipment_id'] = backshipment_id
            has_non_ret_sub_ship = self.search_exist(cr, uid, [('state', '!=', 'cancel'),
                                                               ('backshipment_id', '=', shipment['id'])], context=context)

            all_returned = True
            pack_fam_ids = shipment['pack_family_memory_ids']
            for pack_fam_id in pack_fam_ids:
                memory_family = pack_family_dict.get(pack_fam_id)
                # taken only into account if not done (done means returned packs)
                if memory_family and not memory_family['not_shipped']:
                    # The state will not be changed to Returned if all packs are not returned
                    all_returned = False
                    if shipment['state'] in ('delivered', 'done') or memory_family['state'] not in ('done',):
                        # num of packs
                        num_of_packs = memory_family['num_of_packs']
                        current_result['num_of_packs'] += int(num_of_packs)
                        # total weight
                        total_weight = memory_family['total_weight']
                        current_result['total_weight'] += float(total_weight)
                        # total volume
                        total_volume = memory_family['total_volume']
                        current_result['total_volume'] += float(total_volume)
                        # total amount and currency
                        currency_id = memory_family['currency_id'] or False
                        total_amount = memory_family['total_amount']
                        if current_result.get('currency_id') and currency_id and current_result['currency_id'][0] != currency_id[0]:
                            current_result['total_amount'] = curr_obj.compute(cr, uid, current_result['currency_id'][0],
                                                                              currency_id[0], current_result.get('total_amount', 0.00),
                                                                              round=False, context=context)
                        current_result['total_amount'] += total_amount
                        if currency_id:
                            current_result['currency_id'] = currency_id

            if pack_fam_ids and all_returned and not has_non_ret_sub_ship:
                state = 'cancel'

            current_result['state'] = state

        comp_curr_id = self.pool.get('res.users').get_company_currency_id(cr, uid)
        for ship in self.browse(cr, uid, ids, fields_to_fetch=['additional_items_ids'], context=context):
            for add in ship.additional_items_ids:
                result[ship.id]['num_of_packs'] += add.nb_parcels or 0
                result[ship.id]['total_weight'] += add.weight or 0
                result[ship.id]['total_volume'] += add.volume or 0
                add_value = add.value or 0
                if add_value and result.get(ship.id) and result[ship.id].get('currency_id') \
                        and result[ship.id]['currency_id'][0] != comp_curr_id:
                    add_value = curr_obj.compute(cr, uid, comp_curr_id, result[ship.id]['currency_id'][0], add_value,
                                                 round=False, context=context)
                result[ship.id]['total_amount'] += add_value

        return result

    def _search_backshipment_id(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0][2]:
            return []
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        ship_ids = self.search(cr, uid, [('parent_id', arg[0][1], arg[0][2])], context=context)
        return [('id', 'in', ship_ids)]

    def _get_shipment_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of stock.picking objects for which state has changed

        return the list of ids of shipment object which need to get their state field updated
        '''
        pack_obj = self.pool.get('stock.picking')
        result = []
        for packing in pack_obj.read(cr, uid, ids, ['shipment_id'], context=context):
            if packing['shipment_id'] and packing['shipment_id'][0] not in result:
                result.append(packing['shipment_id'][0])
        return result

    def _search_packing_list(self, cr, uid, obj, name, args, context=None):
        ret_ids = self.pool.get('pack.family.memory').search(cr, uid, args, context=context)
        return [('pack_family_memory_ids', 'in', ret_ids)]

    def _packs_search(self, cr, uid, obj, name, args, context=None):
        """
        Searches Ids of shipment
        """
        if context is None:
            context = {}

        cr.execute('''
            select p.shipment_id as id
                from pack_family_memory p
                where p.shipment_id is not null and  not_shipped != 't'
                group by p.shipment_id
            having sum(case when p.to_pack != 0 then  p.to_pack - p.from_pack + 1 else 0 end) %s %s
        ''' % (args[0][1], args[0][2]))  # not_a_user_entry

        return [('id', 'in', [x[0] for x in cr.fetchall()])]

    def _get_is_company(self, cr, uid, ids, field_name, args, context=None):
        """
        Return True if the partner_id2 of the shipment is the same partner
        as the partner linked to res.company of the res.users
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of shipment to update
        :param field_name: List of names of fields to update
        :param args: Extra parametrer
        :param context: Context of the call
        :return: A dictionary with shipment ID as keys and True or False a values
        """
        user_obj = self.pool.get('res.users')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}
        cmp_partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
        for ship in self.read(cr, uid, ids, ['partner_id2'], context=context):
            res[ship['id']] = ship['partner_id2'][0] == cmp_partner_id

        return res

    def _get_object_name(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = _('Shipment')

        for x in self.search(cr, uid, [('id', 'in', ids), ('parent_id', '=', False)], context=context):
            ret[x] = _('Shipment List')
        return ret

    def _check_loan(self, cr, uid, ids, field_name, args, context=None):
        """
        Check if the Shipment contains Pack(s) with the Loan or Loan Return Reason Type
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        data_obj = self.pool.get('ir.model.data')
        loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        loan_return_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan_return')[1]

        res = {}
        for ship in self.browse(cr, uid, ids, fields_to_fetch=['pack_family_memory_ids'], context=context):
            has_loan, has_ret_loan = False, False
            for pack in ship.pack_family_memory_ids:
                if pack.ppl_id and pack.ppl_id.reason_type_id.id == loan_id:
                    has_loan = True
                if pack.ppl_id and pack.ppl_id.reason_type_id.id == loan_return_id:
                    has_ret_loan = True
            res[ship.id] = {'has_loan': has_loan, 'has_ret_loan': has_ret_loan}

        return res

    _columns = {
        'name': fields.char(string='Reference', size=1024),
        'date': fields.datetime(string='Creation Date'),
        'shipment_expected_date': fields.datetime(string='Expected Ship Date'),
        'shipment_actual_date': fields.datetime(string='Actual Ship Date'),
        'transport_type': fields.selection(TRANSPORT_TYPE,
                                           string="Transport Type", readonly=False),
        'address_id': fields.many2one('res.partner.address', 'Address', help="Address of customer", required=1),
        'sequence_id': fields.many2one('ir.sequence', 'Shipment Sequence', help="This field contains the information related to the numbering of the shipment.", ondelete='cascade'),
        # cargo manifest things
        'cargo_manifest_reference': fields.char(string='Cargo Manifest Reference', size=1024,),
        'date_of_departure': fields.date(string='Date of Departure'),
        'planned_date_of_arrival': fields.date(string='Planned Date of Arrival'),
        'transit_via': fields.char(string='Transit via', size=1024),
        'registration': fields.char(string='Registration', size=1024),
        'driver_name': fields.char(string='Driver Name', size=1024),
        # -- shipper
        'shipper_name': fields.char(string='Name', size=1024),
        'shipper_contact': fields.char(string='Contact', size=1024),
        'shipper_address': fields.char(string='Address', size=1024),
        'shipper_phone': fields.char(string='Phone', size=1024),
        'shipper_email': fields.char(string='Email', size=1024),
        'shipper_other': fields.char(string='Other', size=1024),
        'shipper_date': fields.date(string='Date'),
        'shipper_signature': fields.char(string='Signature', size=1024),
        # -- carrier
        'carrier_id': fields.many2one('res.partner', string='Carrier', domain=[('transporter', '=', True)]),
        'carrier_name': fields.char(string='Name', size=1024),
        'carrier_address': fields.char(string='Address', size=1024),
        'carrier_phone': fields.char(string='Phone', size=1024),
        'carrier_email': fields.char(string='Email', size=1024),
        'carrier_other': fields.char(string='Other', size=1024),
        'carrier_date': fields.date(string='Date'),
        'carrier_signature': fields.char(string='Signature', size=1024),
        # -- consignee
        'consignee_name': fields.char(string='Name', size=1024),
        'consignee_contact': fields.char(string='Contact', size=1024),
        'consignee_address': fields.char(string='Address', size=1024),
        'consignee_phone': fields.char(string='Phone', size=1024),
        'consignee_email': fields.char(string='Email', size=1024),
        'consignee_other': fields.char(string='Other', size=1024),
        'consignee_date': fields.date(string='Date'),
        'consignee_signature': fields.char(string='Signature', size=1024),
        # functions
        'partner_id': fields.related('address_id', 'partner_id', type='many2one', relation='res.partner', string='Customer', store=True, write_relate=False),
        'partner_id2': fields.many2one('res.partner', string='Customer', required=False),
        'partner_type': fields.related('partner_id', 'partner_type', type='selection', selection=PARTNER_TYPE, readonly=True),
        'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals',),
        'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
        'num_of_packs': fields.function(_vals_get, method=True, fnct_search=_packs_search, type='integer', string='Number of Packs', multi='get_vals_X',),
        'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals',),
        'total_volume': fields.function(_vals_get, method=True, type='float', string='Total Volume[dm³]', multi='get_vals',),
        'state': fields.function(_vals_get, method=True, type='selection', selection=[('draft', 'Draft'),
                                                                                      ('shipped', 'Ready to ship'),
                                                                                      ('done', 'Dispatched'),
                                                                                      ('delivered', 'Received'),
                                                                                      ('cancel', 'Returned')], string='State', multi='get_vals',
                                 store={
                                     'stock.picking': (_get_shipment_ids, ['state', 'shipment_id', 'delivered'], 10),
        }),
        'backshipment_id': fields.function(_vals_get, method=True, type='many2one', relation='shipment', string='Draft Shipment', multi='get_vals', fnct_search=_search_backshipment_id),
        'parent_id': fields.many2one('shipment', string='Parent shipment'),
        # TODO check if really deprecated ?
        'invoice_id': fields.many2one('account.invoice', string='Related invoice (deprecated)'),
        'additional_items_ids': fields.one2many('shipment.additionalitems', 'shipment_id', string='Additional Items'),
        'picking_ids': fields.one2many(
            'stock.picking',
            'shipment_id',
            string='Associated Packing List',
        ),
        'packing_list': fields.function(_vals_get, method=True, type='char', multi='get_vals', string='Supplier Packing List', fnct_search=_search_packing_list),
        'in_ref': fields.char(string='IN Reference', size=1024),
        'is_company': fields.function(
            _get_is_company,
            method=True,
            type='boolean',
            string='Is Company ?',
            store={
                'shipment': (lambda self, cr, uid, ids, c={}: ids, ['partner_id2'], 10),
            }
        ),
        'object_name': fields.function(_get_object_name, type='char', method=True, string='Title', internal="1"),
        'has_loan': fields.function(_check_loan, method=True, type='boolean', multi='check_loan', string='Has Loan Pack(s)'),
        'has_ret_loan': fields.function(_check_loan, method=True, type='boolean', multi='check_loan', string='Has Loan Return Pack(s)'),
    }

    def _get_sequence(self, cr, uid, context=None):
        ir_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'msf_outgoing', 'seq_shipment')
        return self.pool.get('ir.model.data').browse(cr, uid, ir_id).res_id

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        The 'Shipper' fields must be filled automatically with the
        default address of the current instance
        """
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')

        res = super(shipment, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        instance_partner = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id
        instance_addr_id = partner_obj.address_get(cr, uid, instance_partner.id)['default']
        instance_addr = addr_obj.browse(cr, uid, instance_addr_id, context=context)

        addr = ''
        if instance_addr.street:
            addr += instance_addr.street
            addr += ' '
        if instance_addr.street2:
            addr += instance_addr.street2
            addr += ' '
        if instance_addr.zip:
            addr += instance_addr.zip
            addr += ' '
        if instance_addr.city:
            addr += instance_addr.city
            addr += ' '
        if instance_addr.country_id:
            addr += instance_addr.country_id.name

        res.update({
            'shipper_name': instance_partner.name,
            'shipper_contact': 'Supply responsible',
            'shipper_address': addr,
            'shipper_phone': instance_addr.phone,
            'shipper_email': instance_addr.email,
        })

        return res

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'sequence_id': _get_sequence,
        'in_ref': False,
    }
    _order = 'name desc'

    def create(self, cr, uid, vals, context=None):
        """
        Update the consignee values by default
        """
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')
        so_obj = self.pool.get('sale.order')

        if vals.get('partner_id2') and not context.get('create_shipment'):
            if vals.get('sale_id'):
                sale_brw = so_obj.browse(cr, uid, vals['sale_id'], context=context)
                consignee_partner = sale_brw.partner_id
                consignee_addr_id = sale_brw.partner_shipping_id.id
            else:
                consignee_partner = partner_obj.browse(cr, uid, vals.get('partner_id2'), context=context)
                consignee_addr_id = partner_obj.address_get(cr, uid, consignee_partner.id)['default']

            consignee_addr = addr_obj.browse(cr, uid, consignee_addr_id, context=context)

            addr = ''
            if consignee_addr.street:
                addr += consignee_addr.street
                addr += ' '
            if consignee_addr.street2:
                addr += consignee_addr.street2
                addr += ' '
            if consignee_addr.zip:
                addr += consignee_addr.zip
                addr += ' '
            if consignee_addr.city:
                addr += consignee_addr.city
                addr += ' '
            if consignee_addr.country_id:
                addr += consignee_addr.country_id.name

            vals.update({
                'consignee_name': consignee_partner.name,
                'consignee_contact': consignee_partner.partner_type == 'internal' and 'Supply responsible' or consignee_addr.name,
                'consignee_address': addr,
                'consignee_phone': consignee_addr.phone,
                'consignee_email': consignee_addr.email,
            })

        return super(shipment, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Force values for carrier if carrier_id is filled
        """
        if not ids:
            return True
        if vals.get('carrier_id'):
            test_fields = [
                'carrier_name', 'carrier_address',
                'carrier_phone', 'carrier_email',
            ]

            sel_vals = self.selected_carrier(cr, uid, ids, vals.get('carrier_id'), context=context)['value']
            for f in test_fields:
                if not vals.get(f):
                    vals[f] = sel_vals.get(f, False)

        return super(shipment, self).write(cr, uid, ids, vals, context=context)


    def selected_carrier(self, cr, uid, ids, carrier_id, context=None):
        """
        Update the different carrier fields if a carrier is selected
        """
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')

        if carrier_id:
            carrier = partner_obj.browse(cr, uid, carrier_id, context=context)
            carrier_addr_id = partner_obj.address_get(cr, uid, carrier_id)['default']
            carrier_addr = addr_obj.browse(cr, uid, carrier_addr_id, context=context)

            addr = ''
            if carrier_addr.street:
                addr += carrier_addr.street
                addr += ' '
            if carrier_addr.street2:
                addr += carrier_addr.street2
                addr += ' '
            if carrier_addr.zip:
                addr += carrier_addr.zip
                addr += ' '
            if carrier_addr.city:
                addr += carrier_addr.city
                addr += ' '
            if carrier_addr.country_id:
                addr += carrier_addr.country_id.name

            return {
                'value': {
                    'carrier_name': carrier.name,
                    'carrier_address': addr,
                    'carrier_phone': carrier_addr.phone,
                    'carrier_email': carrier_addr.email,
                },
            }

        return {}

    def attach_draft_pick_to_ship(self, cr, uid, new_shipment_id, family, description_ppl=False, context=None, job_id=False, nb_processed=0, selected_number=None):
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        data_obj = self.pool.get('ir.model.data')

        if selected_number is None:
            selected_number = family.selected_number

        if not selected_number:
            return nb_processed

        if selected_number > family.num_of_packs:
            raise osv.except_osv(
                _('Warning'),
                _("Nb to Ship (%s) can't be larger than Nb Parcels (%s) %s - %s") % (
                    selected_number, family.num_of_packs, family.sale_order_id and family.sale_order_id.name or '', family.ppl_id and family.ppl_id.name or ''
                ))

        # find the corresponding moves
        moves_ids = move_obj.search(cr, uid, [
            ('picking_id', '=', family.draft_packing_id.id),
            ('shipment_line_id', '=', family.id),
            ('state', '!=', 'done'),
        ], context=context)

        if not moves_ids:
            return nb_processed

        sub_ship_parcels = False
        remaining_parcels = False
        if family.parcel_ids:
            available_parcel = family.parcel_ids.split(',')
            if len(available_parcel) != selected_number:
                selected_parcels = []
                if family.selected_parcel_ids:
                    selected_parcels = family.selected_parcel_ids.split(',')
                nb_parcel_selected = len(selected_parcels)
                if nb_parcel_selected != selected_number:
                    raise osv.except_osv(_('Warning'), _('You must select %d parcel ids, selected: %d') % (selected_number, nb_parcel_selected))

                sub_ship_parcels = family.selected_parcel_ids
                remaining_parcels =  ','.join([x for x in available_parcel if x not in selected_parcels])
            else:
                sub_ship_parcels = family.parcel_ids



        picking = family.draft_packing_id
        for move in family.move_lines:
            if move.product_id and move.product_id.state.code == 'forbidden':  # Check constraints on lines
                check_vals = {'location_dest_id': move.location_dest_id.id, 'move': move}
                self.pool.get('product.product')._get_restriction_error(cr, uid, [move.product_id.id], check_vals, context=context)
            if selected_number < int(family.num_of_packs) and move.product_uom.rounding == 1 and \
                    move.qty_per_pack % move.product_uom.rounding != 0:
                raise osv.except_osv(_('Error'), _('Warning, this range of packs contains one or more products with a decimal quantity per pack. All packs must be processed together'))

        # search if the ship already contains a draft PACK
        new_packing_ids = picking_obj.search(cr, uid, [('shipment_id', '=', new_shipment_id), ('backorder_id', '=', picking.id), ('state', 'not in', ['cancel', 'done'])], context=context)
        if new_packing_ids:
            new_packing_id = new_packing_ids[0]
        else:
            # Copy the picking object without moves
            # Creation of moves and update of initial in picking create method
            sequence = picking.sequence_id
            packing_number = sequence.get_id(code_or_id='id', context=context)

            # New packing data
            packing_data = {
                'name': '%s-%s' % (picking.name, packing_number),
                'backorder_id': picking.id,
                'shipment_id': new_shipment_id,
                'move_lines': [],
                'description_ppl': description_ppl or picking.description_ppl,  # US-803: added the description
                'claim': picking.claim or False,  #TEST ME
            }
            # Update context for copy
            context.update({
                'keep_prodlot': True,
                'keepLineNumber': True,
                'allow_copy': True,
                'non_stock_noupdate': True,
            })

            new_packing_id = picking_obj.copy(cr, uid, picking.id, packing_data, context=context)

        # create picking to move from Shipment to Distrib
        shadow_pack_data = {
            'name': '%s-s' % picking.name,
            'move_lines': [],
            'description_ppl': description_ppl or picking.description_ppl,
            'shipment_id': False,
            'backorder_id': picking.id,
        }
        new_ctx = context.copy()
        new_ctx.update({
            'keep_prodlot': True,
            'keepLineNumber': True,
            'allow_copy': True,
            'non_stock_noupdate': True,
        })
        shadow_pack_id = picking_obj.copy(cr, uid, picking.id, shadow_pack_data, context=new_ctx)
        ###

        selected_from_pack = family.to_pack - selected_number + 1

        if selected_number == int(family.num_of_packs):
            initial_from_pack = 0
            initial_to_pack = 0
        else:
            initial_from_pack = family.from_pack
            initial_to_pack = family.to_pack - selected_number

        dest_location = picking.warehouse_id.lot_output_id.id
        if family.draft_packing_id.sale_id and family.draft_packing_id.sale_id.procurement_request and \
                family.draft_packing_id.sale_id.location_requestor_id:
            dest_location = family.draft_packing_id.sale_id.location_requestor_id.id

        ship_line_id = self.pool.get('pack.family.memory').copy(cr, uid, family.id, {
            'move_lines': [],
            'shipment_id': new_shipment_id,
            'from_pack': selected_from_pack,
            'to_pack': family.to_pack,
            'selected_number': selected_number,
            'draft_packing_id': new_packing_id,
            # TODO 'ppl_id': False,
            'location_id': picking.warehouse_id.lot_distribution_id.id,
            'location_dest_id': data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')[1],
            'state': 'assigned',
            'parcel_ids': sub_ship_parcels,
            'select_parcel_ids': False,
        }, context=context)

        # For corresponding moves
        for move in move_obj.browse(cr, uid, moves_ids, context=context):
            # We compute the selected quantity
            selected_qty = move.qty_per_pack * selected_number

            if move.old_out_location_dest_id:
                # IR > OUT destination changed on OUT, converted to PICK
                final_dest = move.old_out_location_dest_id.id
            else:
                # dest from IR or MSF Customer
                final_dest = dest_location

            move_vals = {
                'picking_id': new_packing_id,
                'line_number': move.line_number,
                'product_qty': selected_qty,
                'backmove_packing_id': move.id,
                'location_id': picking.warehouse_id.lot_distribution_id.id,
                'location_dest_id': final_dest,
                'shipment_line_id': ship_line_id,
            }

            new_move = move_obj.copy(cr, uid, move.id, move_vals, context=context)
            move_obj.action_confirm(cr, uid, new_move, context=context)

            # to move stock fro Shipment to Distrib
            shadow_move_vals = {
                'picking_id': shadow_pack_id,
                'backmove_packing_id': False,
                'location_id': picking.warehouse_id.lot_dispatch_id.id,
                'location_dest_id': picking.warehouse_id.lot_distribution_id.id,
                'state': 'done',
                'product_qty': selected_qty,
                'line_number': move.line_number,
            }
            move_obj.copy(cr, uid, move.id, shadow_move_vals, context=context)

            # Update corresponding initial move
            initial_qty = max(move.product_qty - selected_qty, 0)

            # if all packs have been selected, from/to have been set to 0
            # update the original move object - the corresponding original shipment (draft)
            # is automatically updated generically in the write method
            move_obj.write(cr, uid, [move.id], {
                'product_qty': initial_qty,
            }, context=context)

            nb_processed += 1
            if job_id and nb_processed % 10 == 0:
                self.pool.get('job.in_progress').write(cr, uid, [job_id], {'nb_processed': nb_processed})

        new_max_selected = initial_to_pack - initial_from_pack + 1
        if initial_from_pack or initial_to_pack:
            self.pool.get('pack.family.memory').write(cr, uid, family.id, {
                'from_pack': initial_from_pack,
                'to_pack':initial_to_pack,
                'selected_number': min(new_max_selected, selected_number),
                'parcel_ids': remaining_parcels,
                'select_parcel_ids': False,
            }, context=context)
        else:
            self.pool.get('pack.family.memory').unlink(cr, uid, family.id, context=context)

        # Reset context
        context.update({
            'keep_prodlot': False,
            'keepLineNumber': False,
            'allow_copy': False,
            'non_stock_noupdate': False,
            'draft_packing_id': False,
        })
        picking_obj.write(cr, uid, [shadow_pack_id], {'state': 'done'}, context=context)
        # confirm the new packing
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', new_packing_id, 'button_confirm', cr)
        # simulate check assign button, as stock move must be available
        picking_obj.force_assign(cr, uid, [new_packing_id])

        return nb_processed

    def do_create_shipment_bg(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        assert len(ids) == 1, 'do_create_shipment_bg can only process 1 object'

        cr.execute("""
            select
                count(m.id)
            from stock_move m, pack_family_memory pack
            where
                m.shipment_line_id = pack.id and
                pack.selected_number > 0 and
                m.state = 'assigned' and
                pack.shipment_id = %s
        """, (ids[0], ))
        nb_lines = cr.fetchone()[0] or 0

        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, ids, 'shipment', self.do_create_shipment, nb_lines, _('Create Shipment'), context=context)

    def do_create_shipment(self, cr, uid, ids, context=None, job_id=False):
        """
        Create the shipment

        """
        # Objects
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cp_fields = [
            'consignee_name', 'consignee_contact', 'consignee_address',
            'consignee_phone', 'consignee_email', 'consignee_other',
            'consignee_date', 'shipper_name', 'shipper_contact',
            'shipper_address', 'shipper_phone', 'shipper_email',
            'shipper_other', 'shipper_date', 'carrier_name',
            'carrier_address', 'carrier_phone', 'carrier_email',
            'carrier_other', 'carrier_date',
        ]

        for shipment in self.browse(cr, uid, ids, context=context):
            shipment_number = shipment.sequence_id.get_id(code_or_id='id', context=context)
            shipment_name = '%s-%s' % (shipment.name, shipment_number)

            ship_val = {
                'name': shipment_name,
                'address_id': shipment.address_id.id,
                'partner_id': shipment.partner_id.id,
                'partner_id2': shipment.partner_id.id,
                'shipment_expected_date': shipment.shipment_expected_date,
                'parent_id': shipment.id,
                'transport_type': shipment.transport_type,
                'carrier_id': shipment.carrier_id and shipment.carrier_id.id or False,
                'shipment_actual_date': shipment.shipment_actual_date,
            }
            for cpf in cp_fields:
                ship_val[cpf] = shipment[cpf]

            context['create_shipment'] = True
            new_shipment_id = self.create(cr, uid, ship_val, context=context)
            del context['create_shipment']

            # Log creation message
            message = _('The new Shipment (%s) has been created and is "Ready to Ship".')
            self.log(cr, uid, new_shipment_id, message % (shipment_name,))
            self.infolog(cr, uid, message % (shipment_name,))

            context['shipment_id'] = new_shipment_id

            # US-803: point 9, add the ship description, then remove it from the context
            description_ppl = context.get('description_ppl', False)
            if context.get('description_ppl', False):
                del context['description_ppl']

            nb_processed = 0
            for family in shipment.pack_family_memory_ids:
                if not family.selected_number or family.state != 'assigned':
                    continue
                nb_processed = self.attach_draft_pick_to_ship(cr, uid, new_shipment_id, family, description_ppl, context=context, job_id=job_id, nb_processed=nb_processed)

            if not nb_processed:
                raise osv.except_osv(_('Warning'), _('Please set "Nb Parcels To Ship" to create a Shipment.'))


        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_shipment_form')
        view_id = view_id and view_id[1] or False

        return {
            'name': _("Shipment"),
            'type': 'ir.actions.act_window',
            'res_model': 'shipment',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': new_shipment_id,
            'target': 'crush',
            'context': context,
        }

    @check_cp_rw
    def return_packs(self, cr, uid, ids, context=None):
        """
        Open the wizard to return packs from draft shipment
        """
        # Objects
        proc_obj = self.pool.get('return.shipment.processor')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        processor_id = proc_obj.create(cr, uid, {'shipment_id': ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'name': _('Return Packs'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': processor_id,
            'target': 'new',
            'context': context,
        }

    def do_return_packs(self, cr, uid, wizard_ids, context=None):
        """
        Return the selected packs to the draft picking ticket

        BE CAREFUL: the wizard_ids parameters is the IDs of the return.shipment.processor objects,
        not those of shipment objects
        """
        # Objects
        proc_obj = self.pool.get('return.shipment.processor')
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process'),
            )

        shipment_ids = []
        counter = 0
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            draft_picking = None
            shipment = wizard.shipment_id
            shipment_ids.append(shipment.id)
            # log flag - res.log for draft shipment is displayed only one time for each draft shipment
            log_flag = False

            for family in wizard.family_ids:
                if not family.selected_number:
                    continue
                ship_line = family.shipment_line_id
                draft_picking = family.ppl_id and family.ppl_id.previous_step_id and family.ppl_id.previous_step_id.backorder_id or False
                counter = counter + 1

                # Update initial move
                if family.selected_number == int(family.num_of_packs):
                    # If al packs have been selected, from/to are set to 0
                    initial_from_pack = 0
                    initial_to_pack = 0
                    selected_number = 0
                else:
                    initial_from_pack = family.from_pack
                    initial_to_pack = family.to_pack - family.selected_number
                    selected_number = initial_to_pack - initial_from_pack + 1

                back_ship_line_id = self.pool.get('pack.family.memory').copy(cr, uid, ship_line.id, {
                    'from_pack': family.to_pack - family.selected_number + 1,
                    'to_pack': family.to_pack,
                    'selected_number': family.selected_number,
                    'state': 'returned',
                    'move_lines': False,
                    'not_shipped': True,
                    'parcel_ids': family.selected_parcel_ids,
                    'select_parcel_ids': False,
                }, context=context)

                # Update the moves, decrease the quantities
                for move in ship_line.move_lines:
                    if move.state != 'assigned':
                        raise osv.except_osv(
                            _('Error'),
                            _('All returned lines must be \'Available\'. Please check this and re-try.')
                        )
                    if family.selected_number < int(family.num_of_packs) and move.product_uom.rounding == 1 and \
                            move.qty_per_pack % move.product_uom.rounding != 0:
                        raise osv.except_osv(_('Error'), _('Warning, this range of packs contains one or more products with a decimal quantity per pack. All packs must be processed together'))
                    """
                    Stock moves are not canceled as for PPL return process
                    because this represents a draft packing, meaning some shipment could be canceled and
                    return to this stock move
                    """
                    return_qty = family.selected_number * move.qty_per_pack
                    move_vals = {
                        'product_qty': max(move.product_qty - return_qty, 0),
                    }

                    move_obj.write(cr, uid, [move.id], move_vals, context=context)

                    """
                    Create a back move with the quantity to return to the good location.
                    The good location is store in the 'initial_location' field
                    """
                    cp_vals = {
                        'product_qty': return_qty,
                        'date_expected': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'line_number': move.line_number,
                        'location_dest_id': move.initial_location.id,
                        'state': 'done',
                        'not_shipped': True,  # BKLG-13: set the pack returned to stock also as not_shipped, for showing to view ship draft
                        'shipment_line_id': back_ship_line_id,
                    }
                    context['non_stock_noupdate'] = True

                    move_obj.copy(cr, uid, move.id, cp_vals, context=context)

                    context['non_stock_noupdate'] = False

                    # Find the corresponding move in draft in the draft picking ticket: use browse to invalidate cache
                    draft_move = move_obj.browse(cr, uid, move.backmove_id.id, fields_to_fetch=['product_qty', 'qty_processed'], context=context)
                    # Increase the draft move with the move quantity

                    draft_initial_qty = draft_move.product_qty + return_qty
                    qty_processed = max(draft_move.qty_processed - return_qty, 0)
                    move_obj.write(cr, uid, [draft_move.id], {'product_qty': draft_initial_qty, 'qty_to_process': draft_initial_qty, 'qty_processed': qty_processed, 'pack_info_id': False}, context=context)

                if initial_from_pack or initial_to_pack:
                    remaining_pack_ids = False
                    if ship_line.parcel_ids:
                        remaining_pack_ids = ','.join([x for x in ship_line.parcel_ids.split(',') if x not in family.selected_parcel_ids.split(',')])
                    self.pool.get('pack.family.memory').write(cr, uid, ship_line.id, {
                        'from_pack': initial_from_pack,
                        'to_pack': initial_to_pack,
                        'selected_number': min(ship_line.selected_number, selected_number),
                        'parcel_ids': remaining_pack_ids,
                        'selected_parcel_ids': False,
                    }, context=context)
                else:
                    self.pool.get('pack.family.memory').unlink(cr, uid, ship_line.id, context=context)

            # log the increase action - display the picking ticket view form - log message for each draft packing because each corresponds to a different draft picking
            if not log_flag:
                draft_shipment_name = self.read(cr, uid, shipment.id, ['name'], context=context)['name']
                self.log(cr, uid, shipment.id, _("Packs from the draft Shipment (%s) have been returned to stock.") % (draft_shipment_name,))
                self.infolog(cr, uid, "Packs from the draft Shipment id:%s (%s) have been returned to stock." % (
                    shipment.id, shipment.name,
                ))
                log_flag = True

            if draft_picking:
                picking_obj.log(cr, uid, draft_picking.id, _("The corresponding Draft Picking Ticket (%s) has been updated.") % (draft_picking.name,), action_xmlid='msf_outgoing.action_picking_ticket')

        # Call complete_finished on the shipment object
        # If everything is allright (all draft packing are finished) the shipment is done also
        self.complete_finished(cr, uid, shipment_ids, context=context)


        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_picking_ticket', ['form', 'tree'], context=context)
        res['res_id'] = draft_picking.id
        return res

    def add_packs(self, cr, uid, ids, context=None):
        ship = self.browse(cr, uid, ids[0], fields_to_fetch=['partner_id', 'address_id'], context=context)
        other_ship_ids = self.search(cr, uid, [('state', '=', 'draft'), ('partner_id', '=', ship.partner_id.id), ('address_id', '=', ship.address_id.id)], context=context)
        pack_ids = self.pool.get('pack.family.memory').search(cr, uid, [('pack_state', '=', 'draft'), ('state', 'not in', ['done', 'returned']), ('shipment_id', 'in', other_ship_ids)], context=context)
        if not pack_ids:
            raise osv.except_osv(_('Warning !'), _('No Pack Available'))
        proc_id = self.pool.get('shipment.add.pack.processor').create(cr, uid, {'shipment_id': ids[0]}, context=context)
        cr.execute('''insert into shipment_add_pack_processor_line
                (wizard_id, draft_packing_id, sale_order_id, ppl_id, from_pack, to_pack, num_of_packs, pack_type, volume, weight, create_date, create_uid, shipment_line_id)
            select
                %s, draft_packing_id, sale_order_id, ppl_id, from_pack, to_pack, to_pack - from_pack + 1, pack_type, round(length*width*height*(to_pack - from_pack + 1)/1000,4), weight*(to_pack - from_pack + 1), NOW(), %s, id
                from pack_family_memory
                where id in %s
        ''', (proc_id, uid, tuple(pack_ids)))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.add.pack.processor',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': proc_id,
            'target': 'new',
            'context': context,
        }

    @check_cp_rw
    def return_packs_from_shipment(self, cr, uid, ids, context=None):
        """
        Open the wizard to return packs from draft shipment
        """
        # Objects
        proc_obj = self.pool.get('return.pack.shipment.processor')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        processor_id = proc_obj.create(cr, uid, {'shipment_id': ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'name': _('Return Packs from Shipment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': processor_id,
            'target': 'new',
            'context': context,
        }


    def do_return_packs_from_shipment(self, cr, uid, wizard_ids, context=None):
        """
        Return the selected packs to the PPL

        BE CAREFUL: the wizard_ids parameters is the IDs of the return.shipment.processor objects,
        not those of shipment objects
        """
        # Objects
        proc_obj = self.pool.get('return.pack.shipment.processor')
        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )
        shipment_ids = []

        counter = 0
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            shipment = wizard.shipment_id
            shipment_ids.append(shipment.id)

            for family in wizard.family_ids:
                ship_line = family.shipment_line_id
                draft_packing = family.draft_packing_id.backorder_id
                draft_shipment_id = draft_packing.shipment_id.id

                if family.return_from == 0 and family.return_to == 0:
                    continue

                counter = counter + 1

                stay = []
                if family.to_pack >= family.return_to:
                    if family.return_from == family.from_pack:
                        if family.return_to != family.to_pack:
                            stay.append([family.return_to + 1, family.to_pack])
                    elif family.return_to == family.to_pack:
                        # Do not start at beginning, but same end
                        stay.append([family.from_pack, family.return_from - 1])
                    else:
                        # In the middle, two now tuple in stay
                        stay.append([family.from_pack, family.return_from - 1])
                        stay.append([family.return_to + 1, family.to_pack])

                inital_pck_nb = ship_line.to_pack - ship_line.from_pack + 1
                return_pck_nb = 0

                stay_parcel_ids = False
                if family.selected_parcel_ids:
                    returned_parcel_ids = family.selected_parcel_ids.split(',')
                    stay_parcel_ids = [x for x in family.parcel_ids.split(',') if x not in returned_parcel_ids]

                for seq in stay:
                    seq.append(self.pool.get('pack.family.memory').copy(cr, uid, ship_line.id, {
                        'from_pack': seq[0],
                        'to_pack': seq[1],
                        'selected_number': seq[1] - seq[0] + 1,
                        'move_lines': [],
                        'state': 'assigned',
                        'selected_parcel_ids': False,
                        'parcel_ids': ','.join(stay_parcel_ids[family.from_pack - seq[0]:seq[1] - seq[0] + 1]),
                    }, context=context))
                    return_pck_nb +=  seq[1] - seq[0] + 1

                # back move
                back_ship_line_id = False
                if family.return_from or family.return_to:
                    back_ship_line_id = self.pool.get('pack.family.memory').copy(cr, uid, ship_line.id, {
                        'from_pack': family.return_from,
                        'to_pack': family.return_to,
                        'selected_number': family.return_to - family.return_from + 1,
                        'move_lines': [],
                        'state': 'returned',
                        'not_shipped': True,
                        'location_id': draft_packing.warehouse_id.lot_distribution_id.id,
                        'location_dest_id': draft_packing.warehouse_id.lot_dispatch_id.id,
                        'selected_parcel_ids': False,
                        'parcel_ids': family.selected_parcel_ids,
                    }, context=context)
                    return_pck_nb += family.return_to - family.return_from + 1

                    draft_ship_line_id = self.pool.get('pack.family.memory').copy(cr, uid, ship_line.id, {
                        'from_pack': family.return_from,
                        'to_pack': family.return_to,
                        'selected_number': family.return_to - family.return_from + 1,
                        'move_lines': [],
                        'state': 'assigned',
                        'shipment_id': shipment.parent_id.id,
                        'location_id': draft_packing.warehouse_id.lot_dispatch_id.id,
                        'draft_packing_id': draft_packing.id,
                        'location_dest_id': draft_packing.warehouse_id.lot_distribution_id.id,
                        'selected_parcel_ids': False,
                        'parcel_ids': family.selected_parcel_ids,
                    }, context=context)


                for move in ship_line.move_lines:
                    if move.state != 'assigned':
                        raise osv.except_osv(
                            _('Error'),
                            _('One of the returned family is not \'Available\'. Check the state of the pack families and re-try.'),
                        )

                    if (family.from_pack != family.return_from or family.to_pack != family.return_to) \
                            and move.product_uom.rounding == 1 and move.qty_per_pack % move.product_uom.rounding != 0:
                        raise osv.except_osv(_('Error'), _('Warning, this range of packs contains one or more products with a decimal quantity per pack. All packs must be processed together'))


                    for seq in stay:
                        # Corresponding number of packs
                        selected_number = seq[1] - seq[0] + 1
                        # Quantity to return
                        new_qty = selected_number * move.qty_per_pack
                        # For both cases, we update the from/to and compute the corresponding quantity
                        # if the move has been updated already, we copy/update
                        move_values = {
                            'product_qty': new_qty,
                            'line_number': move.line_number,
                            'state': 'assigned',
                            'shipment_line_id': seq[2],
                        }
                        # The original move is never modified, but canceled
                        move_obj.copy(cr, uid, move.id, move_values, context=context)

                    if back_ship_line_id:
                        # Get the back_to_draft sequences
                        selected_number = family.return_to - family.return_from + 1
                        # Quantity to return
                        new_qty = selected_number * move.qty_per_pack
                        # values
                        move_values = {
                            'line_number': move.line_number,
                            'product_qty': new_qty,
                            'location_id': move.picking_id.warehouse_id.lot_distribution_id.id,
                            'location_dest_id': move.picking_id.warehouse_id.lot_dispatch_id.id,
                            'not_shipped': True,
                            'state': 'done',
                            'shipment_line_id': back_ship_line_id,
                        }

                        # Create a back move in the packing object
                        # Distribution -> Dispatch
                        context['non_stock_noupdate'] = True
                        move_obj.copy(cr, uid, move.id, move_values, context=context)
                        context['non_stock_noupdate'] = False


                        # Create the draft move
                        # Dispatch -> Distribution
                        # Picking_id = draft_picking
                        move_values.update({
                            'location_id': move.picking_id.warehouse_id.lot_dispatch_id.id,
                            'location_dest_id': move.picking_id.warehouse_id.lot_distribution_id.id,
                            'picking_id': draft_packing.id,
                            'state': 'assigned',
                            'not_shipped': False,
                            'shipment_line_id': draft_ship_line_id,
                        })

                        context['non_stock_noupdate'] = True
                        move_obj.copy(cr, uid, move.id, move_values, context=context)
                        context['non_stock_noupdate'] = False

                    move_values = {
                        'product_qty': 0.00,
                        'state': 'done',
                    }
                    move_obj.write(cr, uid, [move.id], move_values, context=context)
                self.pool.get('pack.family.memory').unlink(cr, uid, ship_line.id, context=context)


                if return_pck_nb != inital_pck_nb:
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('The sum of the processed quantities is not equal to the sum of the initial quantities'),
                    )

            # log corresponding action
            shipment_log_msg = _('Packs from the shipped Shipment (%s) have been returned to %s location.') % (shipment.name, _('Dispatch'))
            self.log(cr, uid, shipment.id, shipment_log_msg)
            self.infolog(cr, uid, "Packs from the shipped Shipment id:%s (%s) have been returned to Dispatch location." % (
                shipment.id, shipment.name,
            ))

            draft_log_msg = _('The corresponding Draft Shipment (%s) has been updated.') % family.draft_packing_id.backorder_id.shipment_id.name
            self.log(cr, uid, draft_shipment_id, draft_log_msg)

        # call complete_finished on the shipment object
        # if everything is allright (all draft packing are finished) the shipment is done also
        self.complete_finished(cr, uid, shipment_ids, context=context)

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_shipment_form')
        return {
            'name': _("Shipment"),
            'view_mode': 'form,tree',
            'view_id': [view_id and view_id[1] or False],
            'view_type': 'form',
            'res_model': 'shipment',
            'res_id': draft_shipment_id,
            'type': 'ir.actions.act_window',
            'target': 'crush',
        }

    def _manual_create_rw_shipment_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        return

    def complete_finished(self, cr, uid, ids, context=None):
        '''
        - check all draft packing corresponding to this shipment
          - check the stock moves (qty and from/to)
          - check all corresponding packing are done or canceled (no ongoing shipment)
          - if all packings are ok, the draft is validated
        - if all draft packing are ok, the shipment state is done
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")

        for shipment in self.browse(cr, uid, ids, context=context):
            if shipment.state != 'draft':
                # it's not a draft shipment, check all corresponding packing, trg.write them
                packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id)], context=context)
                for packing_id in packing_ids:
                    wf_service.trg_write(uid, 'stock.picking', packing_id, cr)

                # this shipment is possibly finished, we now check the corresponding draft shipment
                # this will possibly validate the draft shipment, if everything is finished and corresponding draft picking
                shipment = shipment.backshipment_id

            # draft packing for this shipment - some draft packing can already be done for this shipment, so we filter according to state
            draft_packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '=', 'draft'), ], context=context)
            for draft_packing in pick_obj.browse(cr, uid, draft_packing_ids, context=context):
                if draft_packing.subtype != 'packing':
                    raise osv.except_osv(
                        _('Error'),
                        _('The draft packing must be a \'Packing\' subtype')
                    )
                if draft_packing.state != 'draft':
                    raise osv.except_osv(
                        _('Error'),
                        _('The draft packing must be in \'Draft\' state')
                    )

                # we check if the corresponding draft packing can be moved to done.
                # if all packing with backorder_id equal to draft are done or canceled
                # and the quantity for each stock move (state != done) of the draft packing is equal to zero

                # we first check the stock moves quantities of the draft packing
                # we can have done moves when some packs are returned
                treat_draft = True
                for move in draft_packing.move_lines:
                    if move.state not in ('done',):
                        if move.product_qty:
                            treat_draft = False
                        elif move.shipment_line_id and (move.shipment_line_id.from_pack or move.shipment_line_id.to_pack):
                            # qty = 0, from/to pack should have been set to zero
                            raise osv.except_osv(
                                _('Error'),
                                _('There are stock moves with 0 quantity on the pack family sequence: %s %s') % (draft_packing.name, move.line_number)
                            )

                # check if ongoing packing are present, if present, we do not validate the draft one, the shipping is not finished
                if treat_draft:
                    linked_packing_ids = pick_obj.search(cr, uid, [('backorder_id', '=', draft_packing.id),
                                                                   ('state', 'not in', ['done', 'cancel'])], context=context)
                    if linked_packing_ids:
                        treat_draft = False

                if treat_draft:
                    # trigger the workflow for draft_picking
                    # confirm the new picking ticket
                    wf_service.trg_validate(uid, 'stock.picking', draft_packing.id, 'button_confirm', cr)
                    # we force availability
                    pick_obj.force_assign(cr, uid, [draft_packing.id])
                    # finish
                    pick_obj.action_move(cr, uid, [draft_packing.id])
                    wf_service.trg_validate(uid, 'stock.picking', draft_packing.id, 'button_done', cr)
                    # ask for draft picking validation, depending on picking completion
                    # if picking ticket is not completed, the validation will not complete
                    if draft_packing.previous_step_id.previous_step_id.backorder_id:
                        draft_packing.previous_step_id.previous_step_id.backorder_id.validate(context=context)


            # all draft packing are validated (done state) - the state of shipment is automatically updated -> function
        return True

    def shipment_create_invoice(self, cr, uid, ids, context=None):
        '''
        Create invoices for validated shipment
        '''
        invoice_obj = self.pool.get('account.invoice')
        line_obj = self.pool.get('account.invoice.line')
        partner_obj = self.pool.get('res.partner')
        distrib_obj = self.pool.get('analytic.distribution')
        sale_line_obj = self.pool.get('sale.order.line')
        sale_obj = self.pool.get('sale.order')
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id

        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for shipment in self.browse(cr, uid, ids, context=context):
            make_invoice = False
            move = False
            cur_id = False
            for pack in shipment.pack_family_memory_ids:
                for move in pack.move_lines:
                    if move.state != 'cancel' and (not move.sale_line_id or move.sale_line_id.order_id.order_policy == 'picking' and not move.sale_line_id.in_name_goods_return) and not move.picking_id.claim:
                        make_invoice = True
                        cur_id = pack.currency_id.id
                        break
                if make_invoice:
                    break

            if not make_invoice:
                continue

            payment_term_id = False
            partner = shipment.partner_id2
            if not partner:
                raise osv.except_osv(_('Error, no partner !'),
                                     _('Please put a partner on the shipment if you want to generate invoice.'))

            # (US-952) No STV created when a shipment is generated on an external supplier
            if partner.partner_type in ('external', 'esc'):
                continue

            account_id = partner.property_account_receivable.id
            payment_term_id = partner.property_payment_term and partner.property_payment_term.id or False

            addresses = partner_obj.address_get(cr, uid, [partner.id], ['contact', 'invoice'])
            today = time.strftime('%Y-%m-%d', time.localtime())

            invoice_vals = {
                'name': shipment.name,
                'origin': shipment.name or '',
                'type': 'out_invoice',
                'account_id': account_id,
                'partner_id': partner.id,
                'address_invoice_id': addresses['invoice'],
                'address_contact_id': addresses['contact'],
                'payment_term': payment_term_id,
                'fiscal_position': partner.property_account_position.id,
                'date_invoice': context.get('date_inv', False) or today,
                'user_id': uid,
                'from_supply': True,
            }

            if cur_id:
                invoice_vals['currency_id'] = cur_id
            # Journal type
            journal_type = 'sale'
            # Disturb journal for invoice only on intermission partner type
            if shipment.partner_id2.partner_type == 'intermission':
                if not company.intermission_default_counterpart or not company.intermission_default_counterpart.id:
                    raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
                invoice_vals['is_intermission'] = True
                invoice_vals['account_id'] = company.intermission_default_counterpart.id
                journal_type = 'intermission'
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', journal_type),
                                                                            ('is_current_instance', '=', True)])
            if not journal_ids:
                raise osv.except_osv(_('Warning'), _('No %s journal found!') % (journal_type,))
            invoice_vals['journal_id'] = journal_ids[0]

            # US-1669 Use cases "IVO from supply / Shipment" and "STV from supply / Shipment":
            # - add FO to the Source Doc. WARNING: only one FO ref is taken into account even if there are several FO
            # - add Customer References (partner + PO) to the Description
            out_invoice = True
            debit_note = 'is_debit_note' in invoice_vals and invoice_vals['is_debit_note']
            inkind_donation = 'is_inkind_donation' in invoice_vals and invoice_vals['is_inkind_donation']
            intermission = 'is_intermission' in invoice_vals and invoice_vals['is_intermission']
            is_ivo = out_invoice and not debit_note and not inkind_donation and intermission
            is_stv = out_invoice and not debit_note and not inkind_donation and not intermission

            # US-3822 Block STV creation if the partner is internal
            if is_stv and partner.partner_type == 'internal':
                continue

            invoice_id_by_fo = {}
            header_ad_on_inv = {}
            # For each stock moves, create an invoice line
            for pack in shipment.pack_family_memory_ids:
                if pack.not_shipped:
                    continue
                for move in pack.move_lines:
                    if move.state == 'cancel':
                        continue

                    if move.sale_line_id and (move.sale_line_id.order_id.order_policy != 'picking' or move.sale_line_id.in_name_goods_return):
                        continue

                    if move.picking_id.claim:
                        continue

                    # create 1 FO = 1 Invoice
                    order_id = move.sale_line_id and move.sale_line_id.order_id or False
                    if order_id not in invoice_id_by_fo:
                        new_invoice_vals = invoice_vals.copy()
                        if is_ivo or is_stv:
                            # add "synced" tag + real_doc_type for STV and IVO created from Supply flow
                            real_doc_type = is_stv and 'stv' or 'ivo'
                            new_invoice_vals.update({'synced': True,
                                                     'real_doc_type': real_doc_type,
                                                     })
                            origin_inv = 'origin' in new_invoice_vals and new_invoice_vals['origin'] or False
                            fo = move and move.sale_line_id and move.sale_line_id.order_id or False
                            new_origin = origin_inv and fo and "%s:%s" % (origin_inv, fo.name)
                            new_origin = new_origin and new_origin[:64]  # keep only 64 characters (because of the JE ref size)
                            if new_origin:
                                new_invoice_vals.update({'origin': new_origin})
                            name_inv = 'name' in new_invoice_vals and new_invoice_vals['name'] or False
                            new_name_inv = name_inv and fo and fo.client_order_ref and "%s : %s" % (fo.client_order_ref, name_inv)
                            if new_name_inv:
                                new_invoice_vals.update({'name': new_name_inv})
                            # this one does not work (check with new pps process US-5859)
                            #new_invoice_vals['picking_id'] = pack.draft_packing_id and pack.draft_packing_id.id or False

                        invoice_id = invoice_obj.create(cr, uid, new_invoice_vals,
                                                        context=context)

                        # Change currency for the intermission invoice
                        if shipment.partner_id2.partner_type == 'intermission':
                            company_currency = company.currency_id and company.currency_id.id or False
                            if not company_currency:
                                raise osv.except_osv(_('Warning'), _('No company currency found!'))
                            wiz_account_change = self.pool.get('account.change.currency').create(cr, uid, {'currency_id': company_currency}, context=context)
                            self.pool.get('account.change.currency').change_currency(cr, uid, [wiz_account_change], context={'active_id': invoice_id})

                        invoice_id_by_fo[order_id] = invoice_id

                    invoice_id = invoice_id_by_fo[order_id]


                    origin = move.picking_id.name or ''
                    if move.picking_id.origin:
                        origin += ':' + move.picking_id.origin


                    account_id = False
                    if move.sale_line_id and move.sale_line_id.cv_line_ids:
                        account_id = move.sale_line_id.cv_line_ids[0].account_id.id
                    if not account_id:
                        account_id = move.product_id.product_tmpl_id.\
                            property_account_income.id
                    if not account_id:
                        account_id = move.product_id.categ_id.\
                            property_account_income_categ.id

                    # Compute unit price from FO line if the move is linked to
                    price_unit = move.product_id.list_price
                    if move.sale_line_id and move.sale_line_id.product_id.id == move.product_id.id:
                        uos_id = move.product_id.uos_id and move.product_id.uos_id.id or False
                        price = move.sale_line_id.price_unit
                        price_unit = self.pool.get('product.uom')._compute_price(cr, uid, move.sale_line_id.product_uom.id, price, move.product_uom.id)

                    # Get discount from FO line
                    discount = 0.00
                    if move.sale_line_id and move.sale_line_id.product_id.id == move.product_id.id:
                        discount = move.sale_line_id.discount

                    # Get taxes from FO line
                    taxes = move.product_id.taxes_id
                    if move.sale_line_id and move.sale_line_id.product_id.id == move.product_id.id:
                        taxes = [x.id for x in move.sale_line_id.tax_id]

                    if shipment.partner_id2:
                        tax_ids = self.pool.get('account.fiscal.position').map_tax(cr, uid, shipment.partner_id2.property_account_position, taxes)
                    else:
                        tax_ids = [x.id for x in taxes]

                    distrib_id = False
                    if move.sale_line_id:
                        sol_ana_dist_id = False
                        if move.sale_line_id.cv_line_ids:
                            sol_ana_dist_id = move.sale_line_id.cv_line_ids[0].analytic_distribution_id or False
                            if not header_ad_on_inv.get(invoice_id) and move.sale_line_id.cv_line_ids[0].commit_id.analytic_distribution_id:
                                # set AD invoice header from 1st CV AD header
                                header_ad_on_inv[invoice_id] = True
                                ad_header_id = distrib_obj.copy(cr, uid, move.sale_line_id.cv_line_ids[0].commit_id.analytic_distribution_id.id, context=context)
                                self.pool.get('account.invoice').write(cr, uid, [invoice_id], {'analytic_distribution_id': ad_header_id})

                        else:
                            sol_ana_dist_id = move.sale_line_id.analytic_distribution_id or move.sale_line_id.order_id.analytic_distribution_id
                        if sol_ana_dist_id:
                            distrib_id = distrib_obj.copy(cr, uid, sol_ana_dist_id.id, context=context)
                            # create default funding pool lines (if no one)
                            self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [distrib_id])

                    # set UoS if it's a sale and the picking doesn't have one
                    uos_id = move.product_uos and move.product_uos.id or False
                    if not uos_id:
                        uos_id = move.product_uom.id
                    account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, partner.property_account_position, account_id)

                    line_data = {
                        'name': move.name,
                        'origin': origin,
                        'invoice_id': invoice_id,
                        'uos_id': uos_id,
                        'product_id': move.product_id.id,
                        'account_id': account_id,
                        'price_unit': price_unit,
                        'discount': discount,
                        'quantity': move.product_qty or move.product_uos_qty,
                        'invoice_line_tax_id': [(6, 0, tax_ids)],
                        'analytic_distribution_id': distrib_id,
                    }
                    if move.sale_line_id:
                        line_data['sale_order_line_id'] = move.sale_line_id.id
                        if move.sale_line_id.cv_line_ids:
                            line_data['cv_line_ids'] = [(6, 0, [move.sale_line_id.cv_line_ids[0].id])]

                    line_id = line_obj.create(cr, uid, line_data, context=context)

                    if move.sale_line_id:
                        sale_obj.write(cr, uid, [move.sale_line_id.order_id.id], {'invoice_ids': [(4, invoice_id)], })
                        sale_line_obj.write(cr, uid, [move.sale_line_id.id], {'invoiced': True,
                                                                              'invoice_lines': [(4, line_id)], })

        return True

    def open_select_actual_ship_date_wizard(self, cr, uid, ids, context=None):
        """
        Open the split line wizard: the user can confirm the Actual Ship Date
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if ids:
            db_datetime_format = self.pool.get('date.tools').get_db_datetime_format(cr, uid, context=context)
            wiz_data = {'shipment_id': ids[0], 'shipment_actual_date': time.strftime(db_datetime_format)}
            wiz_id = self.pool.get('select.actual.ship.date.wizard').create(cr, uid, wiz_data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'select.actual.ship.date.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context}

        return True

    def validate_bg(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        assert len(ids) == 1, 'validate_bg can only process 1 object'

        cr.execute("""
            select
                count(m.id)
            from stock_move m, pack_family_memory pack
            where
                m.shipment_line_id = pack.id and
                pack.selected_number > 0 and
                m.state = 'assigned' and
                pack.shipment_id = %s
        """, (ids[0], ))
        nb_lines = cr.fetchone()[0] or 0

        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, ids, 'shipment', self.validate, nb_lines, _('Create Shipment'), context=context)

    def validate(self, cr, uid, ids, context=None, job_id=False):
        '''
        validate the shipment

        change the state to Done for the corresponding packing
        - validate the workflow for all the packings
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if context.get('shipment_actual_date'):
            self.write(cr, uid, ids, {'shipment_actual_date': context['shipment_actual_date']}, context=context)
        for shipment in self.browse(cr, uid, ids, context=context):

            # validate should only be called on shipped shipments
            if shipment.state != 'shipped':
                raise osv.except_osv(
                    _('Error'),
                    _('The state of the shipment must be \'Ready to ship\'. Please check it and re-try.')
                )
            # corresponding packing objects - only the distribution -> customer ones
            # we have to discard picking object with state done, because when we return from shipment
            # all object of a given picking object, he is set to Done and still belong to the same shipment_id
            # another possibility would be to unlink the picking object from the shipment, set shipment_id to False
            # but in this case the returned pack families would not be displayed anymore in the shipment
            packing_ids = pick_obj.search(cr, uid, [
                ('shipment_id', '=', shipment.id),
                ('state', 'not in', ['done', 'cancel']),
            ], context=context)

            nb_processed = 0
            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                assert packing.subtype == 'packing' and packing.state == 'assigned'
                # trigger standard workflow
                if packing.sale_id and not packing.sale_id.shipment_date:
                    self.pool.get('sale.order').write(cr, uid, [packing.sale_id.id], {'shipment_date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
                pick_obj.action_move(cr, uid, [packing.id])
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_done', cr)
                pick_obj._hook_create_sync_messages(cr, uid, packing.id, context)  # UF-1617: Create the sync message for batch and asset before shipping

                # UF-1617: set the flag to this packing object to indicate that the SHIP has been done, for synchronisation purpose
                cr.execute('update stock_picking set already_shipped=\'t\' where id=%s', (packing.id,))

                # closing FO lines:
                for stock_move in packing.move_lines:
                    if stock_move.product_id and stock_move.product_id.state.code == 'forbidden':  # Check constraints on lines
                        check_vals = {'location_dest_id': stock_move.location_dest_id.id, 'move': stock_move}
                        self.pool.get('product.product')._get_restriction_error(cr, uid, [stock_move.product_id.id],
                                                                                check_vals, context=context)
                    if stock_move.sale_line_id:
                        open_moves = self.pool.get('stock.move').search_exist(cr, uid, [
                            ('sale_line_id', '=', stock_move.sale_line_id.id),
                            ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                            ('type', '=', 'out'),
                            ('id', '!=', stock_move.id),
                            ('product_qty', '!=', 0.0),
                        ], context=context)
                        if not open_moves:
                            wf_service.trg_validate(uid, 'sale.order.line', stock_move.sale_line_id.id, 'done', cr)
                    nb_processed += 1
                    if job_id and nb_processed % 10 == 0:
                        self.pool.get('job.in_progress').write(cr, uid, [job_id], {'nb_processed': nb_processed})

            # Create automatically the invoice
            self.shipment_create_invoice(cr, uid, shipment.id, context=context)

            # log validate action
            self.log(cr, uid, shipment.id, _('The Shipment %s has been dispatched.') % (shipment.name,))
            self.infolog(cr, uid, "The Shipment id:%s (%s) has been dispatched." % (
                shipment.id, shipment.name,
            ))
            self.pool.get('pack.family.memory').write(cr, uid, [x.id for x in shipment.pack_family_memory_ids], {'state': 'done'}, context=context)

        self.complete_finished(cr, uid, ids, context=context)
        return True

    def set_delivered(self, cr, uid, ids, context=None):
        '''
        set the delivered flag
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        for shipment in self.browse(cr, uid, ids, context=context):
            # validate should only be called on shipped shipments
            if shipment.state != 'done':
                raise osv.except_osv(
                    _('Error'),
                    _('The shipment must be \'Dispatched\'. Please check this and re-try')
                )
            # gather the corresponding packing and trigger the corresponding function
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '=', 'done')], context=context)
            # set delivered all packings, but disable touch on ir.model.data
            ctx = context.copy()
            ctx['sync_update_execution'] = True
            pick_obj.write(cr, uid, packing_ids, {'delivered': True}, context=ctx)

        return True

    def copy_all(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Error'), _('Please select at least one line.'))

        cr.execute('''
            update pack_family_memory set selected_number = (to_pack-from_pack)+1
            where id in %s
            ''', (tuple(context.get('button_selected_ids')), ))
        return True

    def uncopy_all(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Error'), _('Please select at least one line.'))

        cr.execute('''
            update pack_family_memory set selected_number = 0 where id in %s
            ''', (tuple(context.get('button_selected_ids')), ))
        return True


shipment()


class shipment_additionalitems(osv.osv):
    _name = "shipment.additionalitems"
    _description = "Additional Items"

    _columns = {
        'name': fields.char(string='Additional Item', size=1024, required=True),
        'shipment_id': fields.many2one('shipment', string='Shipment', readonly=True, on_delete='cascade'),
        'nb_parcels': fields.integer('Nb Parcels'),
        'comment': fields.char(string='Comment', size=1024),
        'volume': fields.float(digits=(16, 2), string='Volume[dm³]'),
        'weight': fields.float(digits=(16, 2), string='Weight[kg]'),
        'value': fields.float('Value', help='Total Value of the additional item. The value is to be defined in the currency selected for the partner.'),  # The string is modified in the fields_view_get
        'kc': fields.boolean('CC', help='Defines whether the additional item must respect the cold chain.'),
        'dg': fields.boolean('DG', help='Defines whether the additional item is a dangerous good.'),
        'cs': fields.boolean('CS', help='Defines whether the additional item is a controlled substance.'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='tree', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        res = super(shipment_additionalitems, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        company_currency_name = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.currency_id.name
        for field in res['fields']:
            if field == 'value':
                res['fields'][field]['string'] = _('Value [') + company_currency_name + _(']')

        return res


shipment_additionalitems()


class shipment2(osv.osv):
    '''
    add pack_family_ids
    '''
    _inherit = 'shipment'

    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        v = {}
        d = {}

        if not partner_id:
            v.update({'address_id': False})
            address_id = False
        elif address_id:
            d.update({'address_id': [('partner_id', '=', partner_id)]})

        addr = False
        if address_id:
            addr = self.pool.get('res.partner.address').browse(cr, uid, address_id, context=context)

        if partner_id and (not address_id or (addr and addr.partner_id.id != partner_id)):
            addr = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
            if not addr.get('delivery'):
                addr = addr.get('default')
            else:
                addr = addr.get('delivery')

            address_id = addr

            v.update({'address_id': addr})

        if address_id:
            error = self.on_change_address_id(cr, uid, ids, address_id, context=context)
            if error:
                error['value'] = {'address_id': False}
                error['domain'] = d
                return error

        warning = {
            'title': _('Warning'),
            'message': _('The field you are modifying may impact the shipment mechanism, please check the correct process.'),
        }

        return {'value': v, 'domain': d, 'warning': warning}

    def on_change_shipper_name(self, cr, uid, ids, shipper_name):
        return {
            'value': {'shipper_name': shipper_name},
            'warning': {
                'title': _('Warning'),
                'message': _('The field you are modifying may impact the shipment mechanism, please check the correct process.'),
            }
        }

    def on_change_consignee_name(self, cr, uid, ids, consignee_name, context=None):
        if context is None:
            context = {}

        message = _('The field you are modifying may impact the shipment mechanism, please check the correct process.')
        if ids and self.search_exist(cr, uid, [('id', '!=', ids[0]), ('consignee_name', '=', consignee_name),
                                               ('state', '=', 'draft')], context=context):
            consignee_name = self.read(cr, uid, ids[0], ['consignee_name'], context=context)['consignee_name']
            message = _('Another Draft Shipment exists with this Consignee.')

        return {
            'value': {'consignee_name': consignee_name},
            'warning': {
                'title': _('Warning'),
                'message': message,
            }
        }

    def on_change_address_id(self, cr, uid, ids, address_id, context=None):
        other_ids = self.search(cr, uid, [('id', 'not in', ids), ('state', '=', 'draft'), ('address_id', '=', address_id)], context=context)
        if other_ids:
            other = []
            for ship in self.read(cr, uid, other_ids, ['name']):
                other.append(ship['name'])
            return {
                'value': {'address_id': False},
                'warning': {
                    'title': _('Warning'),
                    'message': _('You can only have one draft shipment for a given address, please check %s') % (', '.join(other))
                }
            }
        return {}

    _columns = {
        'pack_family_memory_ids': fields.one2many('pack.family.memory', 'shipment_id', string='Memory Families'),
    }


shipment2()


class select_actual_ship_date_wizard(osv.osv_memory):
    _name = 'select.actual.ship.date.wizard'
    _description = 'Confirm the Actual Ship Date'

    _columns = {
        'shipment_id': fields.many2one('shipment', string='Shipment id', readonly=True),
        'shipment_actual_date': fields.datetime(string='Actual Ship Date'),
    }

    def validate_ship(self, cr, uid, ids, context=None):
        '''
        Launch the validate_bg method
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        ship_obj = self.pool.get('shipment')
        for wiz in self.browse(cr, uid, ids, context=context):
            context['shipment_actual_date'] = wiz.shipment_actual_date
            ship_obj.validate_bg(cr, uid, [wiz.shipment_id.id], context=context)

            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'view_shipment_form')
            view_id = view_id and view_id[1] or False

            return {
                'name': _("Shipment"),
                'type': 'ir.actions.act_window',
                'res_model': 'shipment',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'view_id': [view_id],
                'res_id': wiz.shipment_id.id,
                'target': 'crush',
                'context': context,
            }

        return {'type': 'ir.actions.act_window_close'}

    def cancel(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


select_actual_ship_date_wizard()


class ppl_customize_label(osv.osv):
    '''
    label preferences
    '''
    _name = 'ppl.customize.label'

    _columns = {
        'name': fields.char(string='Name', size=1024,),
        'notes': fields.text(string='Notes'),
        'pre_packing_list_reference': fields.boolean(string='Pre-Packing List Reference'),
        'destination_partner': fields.boolean(string='Destination Partner'),
        'destination_address': fields.boolean(string='Destination Address'),
        'requestor_order_reference': fields.boolean(string='Requestor Order Reference'),
        'weight': fields.boolean(string='Weight'),
        'packing_parcel_number': fields.boolean(string='Packing Parcel Number'),
        'specific_information': fields.boolean(string='Specific Information'),
        'logo': fields.boolean(string='Company Logo'),
        'packing_list': fields.boolean(string='Supplier Packing List'),
    }

    _defaults = {
        'name': 'My Customization',
        'notes': '',
        'pre_packing_list_reference': True,
        'destination_partner': True,
        'destination_address': True,
        'requestor_order_reference': True,
        'weight': True,
        'packing_parcel_number': True,
        'specific_information': True,
        'logo': True,
        'packing_list': False,
    }

ppl_customize_label()


class stock_picking(osv.osv):
    '''
    override stock picking to add new attributes
    - flow_type: the type of flow (full, quick)
    - subtype: the subtype of picking object (picking, ppl, packing)
    - previous_step_id: the id of picking object of the previous step, picking for ppl, ppl for packing
    '''
    _inherit = 'stock.picking'
    _name = 'stock.picking'

    # For use only in Remote Warehouse
    CENTRAL_PLATFORM = "central_platform"
    REMOTE_WAREHOUSE = "remote_warehouse"


    def _auto_init(self, cr, context=None):
        res = super(stock_picking, self)._auto_init(cr, context=context)
        if not cr.index_exists('stock_picking', 'stock_picking_name3_index'):
            cr.execute('CREATE INDEX stock_picking_name3_index ON stock_picking (substring(name, 1, 3))')

        if not cr.constraint_exists('stock_picking', 'stock_picking_only_ppl_in_ppl_view'):
            cr.execute("select max(id) from stock_picking where subtype='ppl' and substring(name, 1, 3)!='PPL'")
            max_id = cr.fetchone()[0]
            if max_id:
                cr.execute("alter table stock_picking add constraint stock_picking_only_ppl_in_ppl_view check (id<=%s or subtype!='ppl' or substring(name, 1, 3)='PPL')", (max_id, ))
            else:
                cr.execute("alter table stock_picking add constraint stock_picking_only_ppl_in_ppl_view check (subtype!='ppl' or substring(name, 1, 3)='PPL')")

        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Set the appropriate search view according to the context
        '''
        if not context:
            context = {}

        if not view_id and context.get('wh_dashboard') and view_type == 'search':
            try:
                if context.get('pick_type') == 'incoming':
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_search')[1]
                elif context.get('pick_type') == 'delivery':
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_out_search')[1]
                elif context.get('pick_type') == 'picking_ticket':
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_search')[1]
                elif context.get('pick_type') == 'pack':
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'view_ppl_search')[1]
            except ValueError:
                pass
        if not view_id and context.get('pick_type') == 'incoming' and view_type == 'tree':
            try:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_tree')[1]
            except ValueError:
                pass

        res = super(stock_picking, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # US-688 Do not show the button new, duplicate in the tree and form view of picking
        if view_type in ['tree', 'form'] and res['name'] in ['picking.ticket.form', 'picking.ticket.tree']:
            root = etree.fromstring(res['arch'])
            root.set('hide_new_button', 'True')
            root.set('hide_delete_button', 'True')
            root.set('hide_duplicate_button', 'True')
            res['arch'] = etree.tostring(root, encoding='unicode')

        return res

    def change_description_save(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

    # This method is empty for non-Remote Warehouse instances, to be implemented at RW module
    def _get_usb_entity_type(self, cr, uid, context=None):
        return False

    def unlink(self, cr, uid, ids, context=None):
        '''
        unlink test for draft
        '''
        datas = self.read(cr, uid, ids, ['state', 'type', 'subtype'], context=context)
        if [data for data in datas if data['state'] != 'draft']:
            raise osv.except_osv(_('Warning !'), _('Only draft picking tickets can be deleted.'))
        ids_picking_draft = [data['id'] for data in datas if data['subtype'] == 'picking' and data['type'] == 'out' and data['state'] == 'draft']
        if ids_picking_draft:
            data = self.has_picking_ticket_in_progress(cr, uid, ids, context=context)
            if [x for x in list(data.values()) if x]:
                raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try again.'))

        return super(stock_picking, self).unlink(cr, uid, ids, context=context)

    def copy_web(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}

        data_obj = self.pool.get('ir.model.data')

        context['web_copy'] = True
        default.update({'partner_id': False, 'partner_id2': False, 'address_id': False, 'ext_cu': False, 'sale_id': False, 'invoice_state': 'none'})
        pick_type = self.read(cr, uid, id, ['type'], context=context)['type']
        if pick_type == 'out':
            default['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        else:
            default['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
        if pick_type == 'internal':  # Duplication of SYS-INT
            default['subtype'] = 'standard'

        return self.copy(cr, uid, id, default, context=context)

    def copy(self, cr, uid, copy_id, default=None, context=None):
        '''
        set the name corresponding to object subtype
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}

        if 'incoming_id' not in default:
            default['incoming_id'] = False

        obj = self.browse(cr, uid, copy_id, context=context)
        if not context.get('allow_copy', False):
            if obj.subtype == 'picking' and default.get('subtype', 'picking') == 'picking':
                if not obj.backorder_id or obj.claim:
                    # draft, new ref
                    default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket'),
                                   origin=False,
                                   date=date.today().strftime('%Y-%m-%d'),
                                   sale_id=False,
                                   )
                else:
                    # if the corresponding draft picking ticket is done, we do not allow copy
                    if obj.backorder_id and obj.backorder_id.state == 'done':
                        raise osv.except_osv(_('Error !'), _('Corresponding Draft picking ticket is Closed. This picking ticket cannot be copied.'))
                    if obj.backorder_id and not obj.backorder_id.claim:
                        raise osv.except_osv(_('Error !'), _('You cannot duplicate a Picking Ticket linked to a Draft Picking Ticket.'))
                    # picking ticket, use draft sequence, keep other fields
                    base = obj.name
                    base = base.split('-')[0] + '-'
                    default.update(name=base + obj.backorder_id.sequence_id.get_id(code_or_id='id', context=context),
                                   date=date.today().strftime('%Y-%m-%d'),
                                   )

            elif obj.subtype == 'ppl':
                raise osv.except_osv(_('Error !'), _('Pre-Packing List copy is forbidden.'))

        if context.get('picking_type') == 'delivery_order' and obj.partner_id2 and not context.get('allow_copy', False):
            # UF-2539: do not allow to duplicate (validated by Skype 03/12/2014)
            # as since UF-2539 it is not allowed to select other internal
            # instances partner, but it was previously in UF 1.0.
            # case of a FO, pick generated, then converted to an OUT.
            if obj.partner_id2.partner_type == 'internal':
                instance_partner_id = False
                user = self.pool.get('res.users').browse(cr, uid, [uid],
                                                         context=context)[0]
                if user and user.company_id and user.company_id.partner_id:
                    instance_partner_id = user.company_id.partner_id.id
                if instance_partner_id and obj.partner_id2.id != instance_partner_id:
                    msg_format = "You can not duplicate from an other partner" \
                        " instance of current one '%s'"
                    msg_intl = _(msg_format)
                    raise osv.except_osv(_('Error !'), msg_intl % (
                        user.company_id.name or '', ))

        if context.get('picking_type') == 'internal_move' and context.get('allow_copy') and obj.previous_chained_pick_id:
            default['previous_chained_pick_id'] = obj.previous_chained_pick_id.id

        result = super(stock_picking, self).copy(cr, uid, copy_id, default=default, context=context)
        if not context.get('allow_copy', False):
            if obj.subtype == 'picking' and obj.backorder_id:
                # confirm the new picking ticket - the picking ticket should not stay in draft state !
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', result, 'button_confirm', cr)
                # we force availability
                self.force_assign(cr, uid, [result])
        return result

    def copy_data(self, cr, uid, copy_id, default=None, context=None):
        '''
        reset one2many fields
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        # reset one2many fields
        default.update(backorder_ids=[])
        default.update(already_replicated=False)
        default.update(previous_step_ids=[])
        default.update(pack_family_memory_ids=[])
        default.update(in_ref=False)
        # US-779: Reset the ref to rw document
        default.update(rw_sdref_counterpart=False)

        if context.get('from_button'):
            default.update(purchase_id=False)
        if not context.get('wkf_copy'):
            context['not_workflow'] = True
        result = super(stock_picking, self).copy_data(cr, uid, copy_id, default=default, context=context)

        return result

    def has_picking_ticket_in_progress(self, cr, uid, ids, context=None):
        '''
        ids is the list of draft picking object we want to test
        completed means, we recursively check that next_step link object is cancel or done

        return true if picking tickets are in progress, meaning picking ticket or ppl or shipment not done exist
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = []
        res = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # by default, nothing is in progress
            res[obj.id] = False
            # treat only draft picking
            assert obj.subtype in 'picking' and obj.state == 'draft', 'the validate function should only be called on draft picking ticket objects'
            for picking in obj.backorder_ids:
                # take care, is_completed returns a dictionary
                if not picking.is_completed()[picking.id]:
                    res[obj.id] = True
                    break

        return res

    def validate(self, cr, uid, ids, context=None):
        '''
        validate or not the draft picking ticket
        '''
        # objects
        move_obj = self.pool.get('stock.move')

        for draft_picking in self.read(cr, uid, ids, ['subtype', 'state'], context=context):
            # the validate function should only be called on draft picking ticket
            assert draft_picking['subtype'] == 'picking' and draft_picking['state'] == 'draft', 'the validate function should only be called on draft picking ticket objects'
            # check the qty of all stock moves
            treat_draft = True
            move_ids = move_obj.search(cr, uid, [('picking_id', '=', draft_picking['id']),
                                                 ('product_qty', '!=', 0.0),
                                                 ('state', 'not in', ['done', 'cancel'])], context=context)
            if move_ids:
                treat_draft = False

            if treat_draft:
                # then all child picking must be fully completed, meaning:
                # - all picking must be 'completed'
                # completed means, we recursively check that next_step link object is cancel or done
                if self.has_picking_ticket_in_progress(cr, uid, [draft_picking['id']], context=context)[draft_picking['id']]:
                    treat_draft = False

            if treat_draft:
                # - all picking are completed (means ppl completed and all shipment validated)
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', draft_picking['id'], 'button_confirm', cr)
                # we force availability
                self.force_assign(cr, uid, draft_picking['id'])
                # finish
                self.action_move(cr, uid, draft_picking['id'])
                wf_service.trg_validate(uid, 'stock.picking', draft_picking['id'], 'button_done', cr)

        return True

    def _get_overall_qty(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        if not ids:
            return result
        if isinstance(ids, int):
            ids = [ids]
        cr.execute('''select p.id, sum(m.product_qty)
            from stock_picking p, stock_move m
            where m.picking_id = p.id and m.picking_id in %s
            group by p.id''', (tuple(ids,),))
        for i in cr.fetchall():
            result[i[0]] = i[1] or 0
        return result

    def _is_one_of_the_move_lines(self, cr, uid, ids, field, arg, context=None):
        result = dict.fromkeys(ids, '')
        move_obj = self.pool.get('stock.move')
        for stock_picking in self.read(cr, uid, ids, ['move_lines'], context=context):
            current_id = stock_picking['id']
            result[current_id] = ''
            for move in move_obj.read(cr, uid, stock_picking['move_lines'],
                                      [field], context):
                if move[field]:
                    result[current_id] = move[field]
                    break
        return result

    def _get_currency(self, cr, uid, ids, field, arg, context=None):
        result = dict.fromkeys(ids, False)
        move_obj = self.pool.get('stock.move')
        for stock_picking in self.read(cr, uid, ids, ['move_lines'], context=context):
            current_id = stock_picking['id']
            result[current_id] = False
            for move in move_obj.read(cr, uid, stock_picking['move_lines'],
                                      [field], context):
                if move[field]:
                    result[current_id] = move[field]
                    break
        return result


    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        pack_fam_obj = self.pool.get('pack.family.memory')
        result = {}
        # pack.family.memory are long to read, read all in on time is much faster
        picking_to_families = dict((x['id'], x['pack_family_memory_ids']) for x in self.read(cr, uid, ids, ['pack_family_memory_ids'], context=context))
        family_set = set()
        for val in list(picking_to_families.values()):
            family_set.update(val)

        family_read_result = pack_fam_obj.read(cr, uid,
                                               list(family_set),
                                               ['num_of_packs', 'total_weight', 'total_volume', 'shipment_id', 'not_shipped'],
                                               context=context)

        family_dict = dict((x['id'], x) for x in family_read_result)
        parent_id_ship = {}
        for current_id, family_ids in list(picking_to_families.items()):
            default_values = {
                'num_of_packs': 0,
                'total_weight': 0.0,
                'total_volume': 0.0,

            }
            result[current_id] = default_values
            if family_ids:
                num_of_packs = 0
                total_weight = 0
                total_volume = 0
                for family_id in family_ids:
                    if family_id in family_dict:
                        family = family_dict[family_id]
                        if family['shipment_id'] and family['not_shipped']:
                            if family['shipment_id'][0] not in parent_id_ship:
                                parent_id_ship[family['shipment_id'][0]] = self.pool.get('shipment').read(cr, uid, family['shipment_id'][0], ['parent_id'], context=context)['parent_id']
                            if parent_id_ship.get(family['shipment_id'][0]):
                                continue
                        num_of_packs += int(family['num_of_packs'])
                        total_weight += float(family['total_weight'])
                        total_volume += float(family['total_volume'])

                result[current_id]['num_of_packs'] = num_of_packs
                result[current_id]['total_weight'] = total_weight
                result[current_id]['total_volume'] = total_volume
        return result

    def is_completed(self, cr, uid, ids, context=None):
        '''
        recursive test of completion
        - to be applied on picking ticket

        ex:
        for picking in draft_picking.backorder_ids:
            # take care, is_completed returns a dictionary
            if not picking.is_completed()[picking.id]:
                ...balbala

        ***BEWARE: RETURNS A DICTIONARY !
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            completed = stock_picking.state in ('done', 'cancel')
            result[stock_picking.id] = completed
            if completed:
                for next_step in stock_picking.previous_step_ids:
                    if not next_step.is_completed()[next_step.id]:
                        completed = False
                        result[stock_picking.id] = completed
                        break

        return result

    def _qty_search(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of stock picking
            @return: Ids of locations
        """
        if context is None:
            context = {}
        stock_pickings = self.pool.get('stock.picking').search(cr, uid, [], context=context)
        # result dic
        result = {}
        for stock_picking in self.browse(cr, uid, stock_pickings, context=context):
            result[stock_picking.id] = 0.0
            for move in stock_picking.move_lines:
                result[stock_picking.id] += move.product_qty
        # construct the request
        # adapt the operator
        op = args[0][1]
        if op == '=':
            op = '=='
        ids = [('id', 'in', [x for x in list(result.keys()) if eval("%s %s %s" % (result[x], op, args[0][2]))])]
        return ids

    def _get_picking_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of stock.move objects for which values have changed
        return the list of ids of picking object which need to get their state field updated

        self is stock.move object
        '''
        result = []
        for obj in self.read(cr, uid, ids, ['picking_id'], context=context):
            if obj['picking_id'] and obj['picking_id'][0] not in result:
                result.append(obj['picking_id'][0])
        return result

    def _get_draft_moves(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if there is draft moves on Picking Ticket
        '''
        res = {}

        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = False
            for move in pick.move_lines:
                if move.state == 'draft':
                    res[pick.id] = True
                    continue

        return res

    def _get_lines_state(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the state according to line states and picking state
        If the Picking Ticket is not draft, don't compute the line state
        Else, for all moves with quantity, check the state of the move
        and set the line state with these values :
        'mixed': 'Partially Available'
        'assigned': 'Available'
        'confirmed': 'Not available'
        '''
        res = {}

        for pick in self.browse(cr, uid, ids, context=context):
            if pick.type != 'out' or pick.subtype != 'picking':
                res[pick.id] = False
                continue

            res[pick.id] = 'confirmed'
            available = False
            confirmed = False
            processed = True
            empty = len(pick.move_lines)
            for move in pick.move_lines:
                if move.product_qty == 0.00 or move.state == 'cancel' or (pick.is_subpick and move.state == 'done'):
                    continue

                processed = False

                if move.state != 'assigned':
                    confirmed = True
                else:
                    available = True

                if confirmed and available:
                    break

            if available and confirmed:
                res[pick.id] = 'mixed'
            elif available:
                res[pick.id] = 'assigned'
            elif confirmed:
                res[pick.id] = 'confirmed'
            elif processed and (empty or pick.is_subpick):
                res[pick.id] = 'processed'
            elif empty == 0:
                res[pick.id] = 'empty'
            else:
                res[pick.id] = False

        return res

    _columns = {
        'flow_type': fields.selection([('full', 'Full'), ('quick', 'Quick')], readonly=True, states={'draft': [('readonly', False), ], }, string='Flow Type'),
        'subtype': fields.selection([('standard', 'Standard'), ('picking', 'Picking'), ('ppl', 'PPL'), ('packing', 'Packing'), ('sysint', 'System Internal')], string='Subtype', select=1),
        'backorder_ids': fields.one2many('stock.picking', 'backorder_id', string='Backorder ids',),
        'previous_step_id': fields.many2one('stock.picking', 'Previous step'),
        'previous_step_ids': fields.one2many('stock.picking', 'previous_step_id', string='Previous Step ids',),
        'shipment_id': fields.many2one('shipment', string='Shipment'),
        'sequence_id': fields.many2one('ir.sequence', 'Picking Ticket Sequence', help="This field contains the information related to the numbering of the picking tickets.", ondelete='cascade'),
        # attributes for specific packing labels
        'ppl_customize_label': fields.many2one('ppl.customize.label', string='Labels Customization',),
        # warehouse info (locations) are gathered from here - allow shipment process without sale order
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True,),
        # flag for converted picking
        'converted_to_standard': fields.boolean(string='Converted to Standard'),
        # functions
        'num_of_packs': fields.function(_vals_get, method=True,
                                        type='integer', string='#Packs', multi='get_vals_integer'),
        'total_volume': fields.function(_vals_get, method=True, type='float', string='Total Volume[dm³]', multi='get_vals'),
        'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals'),
        'currency_id': fields.function(_get_currency, method=True, type='many2one', relation='res.currency', string='Currency', multi=False),
        'is_dangerous_good': fields.function(_is_one_of_the_move_lines, method=True,
                                             type='char', size=8, string='Dangerous Good'),
        'is_keep_cool': fields.function(_is_one_of_the_move_lines, method=True,
                                        type='char', size=8, string='Cold Chain'),
        'is_narcotic': fields.function(_is_one_of_the_move_lines, method=True,
                                       type='char', size=8, string='CS'),
        'overall_qty': fields.function(_get_overall_qty, method=True, fnct_search=_qty_search, type='float', string='Overall Qty',
                                       store={'stock.move': (_get_picking_ids, ['product_qty', 'picking_id'], 10), }),
        'line_state': fields.function(_get_lines_state, method=True, type='selection',
                                      selection=[('confirmed', 'Not available'),
                                                 ('assigned', 'Available'),
                                                 ('empty', 'Empty'),
                                                 ('processed', 'Processed'),
                                                 ('mixed', 'Partially available')], string='Lines state',
                                      store={'stock.move': (_get_picking_ids, ['picking_id', 'state', 'product_qty'], 10),
                                             'stock.picking': (lambda self, cr, uid, ids, c={}: ids, ['move_lines'], 10)}),
        'pack_family_memory_ids': fields.one2many('pack.family.memory', 'ppl_id', string='Memory Families'),
        # TODO: Remove in a future release when Parcel Comment is added/used at line level for PPLs
        'description_ppl': fields.char('Parcel Comment', size=256),
        'already_shipped': fields.boolean(string='The shipment is done'),  # UF-1617: only for indicating the PPL that the relevant Ship has been closed
        'has_draft_moves': fields.function(_get_draft_moves, method=True, type='boolean', string='Has draft moves ?', store=False),
        'has_to_be_resourced': fields.boolean(string='Picking has to be resourced'),
        'in_ref': fields.char(string='IN Reference', size=1024),
        'from_manage_expired': fields.boolean(string='The Picking was created with Manage Expired Stock'),
        'requestor': fields.char(size=128, string='Requestor'),
        'from_ir': fields.related('sale_id', 'procurement_request', type='boolean', relation='sale.order', string='Is the linked Sale Order IR', write_relate=False),
    }

    _defaults = {
        'flow_type': 'full',
        'ppl_customize_label': lambda obj, cr, uid, c: len(obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'), ], context=c)) and obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'), ], context=c)[0] or False,
        'subtype': 'standard',
        'warehouse_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)) and obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)[0] or False,
        'converted_to_standard': False,
        'already_shipped': False,
        'line_state': 'empty',
        'in_ref': False,
        'from_manage_expired': False,
    }

    _order = 'name desc'

    # constraints set in _auto_init due to existing failure
    #_sql_constraints = [
    #    ('only_ppl_in_ppl_view', "check(subtype!='ppl' or substring(name, 1, 3)='PPL')", 'Only PPL can be created in PPL view')
    #]

    def onchange_move(self, cr, uid, ids, context=None):
        '''
        Display or not the 'Confirm' button on Picking Ticket
        '''
        res = super(stock_picking, self).onchange_move(cr, uid, ids, context=context)

        if ids:
            has_draft_moves = self._get_draft_moves(cr, uid, ids, 'has_draft_moves', False)[ids[0]]
            res.setdefault('value', {}).update({'has_draft_moves': has_draft_moves})

        return res

    def picking_ticket_data(self, cr, uid, ids, context=None):
        '''
        generate picking ticket data for report creation

        - sale order line without product: does not work presently

        - many sale order line with same product: stored in different dictionary with line id as key.
            so the same product could be displayed many times in the picking ticket according to sale order

        - many stock move with same product: two cases, if from different sale order lines, the above rule applies,
            if from the same order line, they will be stored according to prodlot id

        - many stock move with same prodlot (so same product): if same sale order line, the moves will be
            stored in the same structure, with global quantity, i.e. this batch for this product for this
            sale order line will be displayed only once with summed quantity from concerned stock moves

        [sale_line.id][product_id][prodlot_id]

        other prod lot, not used are added in order that all prod lot are displayed

        to check, if a move does not come from the sale order line:
        stored with line id False, product is relevant, multiple
        product for the same 0 line id is possible
        '''
        result = {}
        for stock_picking in self.browse(cr, uid, ids, context=context):
            values = {}
            result[stock_picking.id] = {'obj': stock_picking,
                                        'lines': values,
                                        }
            for move in stock_picking.move_lines:
                if move.product_id:  # product is mandatory at stock_move level ;)
                    sale_line_id = move.sale_line_id and move.sale_line_id.id or False
                    # structure, data is reorganized in order to regroup according to sale order line > product > production lot
                    # and to sum the quantities corresponding to different levels because this is impossible within the rml framework
                    values \
                        .setdefault(sale_line_id, {}) \
                        .setdefault('products', {}) \
                        .setdefault(move.product_id.id, {}) \
                        .setdefault('uoms', {}) \
                        .setdefault(move.product_uom.id, {}) \
                        .setdefault('lots', {})

                    # ** sale order line info**
                    values[sale_line_id]['obj'] = move.sale_line_id or False

                    # **uom level info**
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['obj'] = move.product_uom

                    # **prodlot level info**
                    if move.prodlot_id:
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'].setdefault(move.prodlot_id.id, {})
                        # qty corresponding to this production lot
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id].setdefault('reserved_qty', 0)
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id]['reserved_qty'] += move.product_qty
                        # store the object for info retrieval
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['lots'][move.prodlot_id.id]['obj'] = move.prodlot_id

                    # **product level info**
                    # total quantity from STOCK_MOVES for one sale order line (directly for one product)
                    # or if not linked to a sale order line, stock move created manually, the line id is False
                    # and in this case the product is important
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id].setdefault('qty_to_pick_sm', 0)
                    values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['qty_to_pick_sm'] += move.product_qty
                    # total quantity from SALE_ORDER_LINES, which can be different from the one from stock moves
                    # if stock moves have been created manually in the picking, no present in the so, equal to 0 if not linked to an so

                    # UF-2227: Qty of FO line is only taken once, and use it, do not accumulate for the case the line got split!
                    if 'qty_to_pick_so' not in values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]:
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id].setdefault('qty_to_pick_so', 0)
                        values[sale_line_id]['products'][move.product_id.id]['uoms'][move.product_uom.id]['qty_to_pick_so'] += move.sale_line_id and move.sale_line_id.product_uom_qty or 0.0

                    # store the object for info retrieval
                    values[sale_line_id]['products'][move.product_id.id]['obj'] = move.product_id

            # all moves have been treated
            # complete the lot lists for each product
            for sale_line in list(values.values()):
                for product in list(sale_line['products'].values()):
                    for uom in list(product['uoms'].values()):
                        # loop through all existing production lot for this product - all are taken into account, internal and external
                        for lot in product['obj'].prodlot_ids:
                            if lot.id not in list(uom['lots'].keys()):
                                # the lot is not present, we add it
                                uom['lots'][lot.id] = {}
                                uom['lots'][lot.id]['obj'] = lot
                                # reserved qty is 0 since no stock moves correspond to this lot
                                uom['lots'][lot.id]['reserved_qty'] = 0.0

        return result

    def action_confirm_moves(self, cr, uid, ids, context=None):
        '''
        Confirm all stock moves of the picking
        '''
        moves_to_confirm = []
        for pick in self.browse(cr, uid, ids, context=context):
            for move in pick.move_lines:
                if move.state == 'draft':
                    moves_to_confirm.append(move.id)

        self.pool.get('stock.move').action_confirm(cr, uid, moves_to_confirm, context=context)

        return True

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new picking
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result

        example of name: 'PICK/xxxxx'
        example of code: 'picking.xxxxx'
        example of prefix: 'PICK'
        example of padding: 5
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        default_name = 'Stock Picking'
        default_code = 'stock.picking'
        default_prefix = ''
        default_padding = 0

        if vals is None:
            vals = {}

        name = vals.get('name', False)
        if not name:
            name = default_name
        code = vals.get('code', False)
        if not code:
            code = default_code
        prefix = vals.get('prefix', False)
        if not prefix:
            prefix = default_prefix
        padding = vals.get('padding', False)
        if not padding:
            padding = default_padding

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': prefix,
            'padding': padding,
        }
        return seq_pool.create(cr, uid, seq)

    def get_packing_list_label(self, cr, uid, context=None):
        try:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'default_label_packing_list')[1]
        except:
            return False

    def change_packing_list(self, cr, uid, ids, pl, context=None):
        if pl:
            label = self.get_packing_list_label(cr, uid, context=context)
            if label:
                return {'value': {'ppl_customize_label': label}}
        return {}

    def create(self, cr, uid, vals, context=None):
        '''
        creation of a stock.picking of subtype 'packing' triggers
        special behavior :
         - creation of corresponding shipment
        '''
        # Objects
        sale_order_obj = self.pool.get('sale.order')
        # For picking ticket from scratch, invoice it !
        if not vals.get('sale_id') and not vals.get('purchase_id') and not vals.get('invoice_state') and 'type' in vals and vals['type'] == 'out':
            vals['invoice_state'] = '2binvoiced'
        # objects
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)

        if context is None:
            context = {}

        if vals.get('packing_list'):
            label = self.get_packing_list_label(cr, uid, context=context)
            if label:
                vals['ppl_customize_label'] = label

        if context.get('sync_update_execution', False) or context.get('sync_message_execution', False):
            # UF-2066: in case the data comes from sync, some False value has been removed, but needed in some assert.
            # The following lines are to re-enter explicitly the values, even if they are already set to False
            vals['backorder_id'] = vals.get('backorder_id', False)
            vals['shipment_id'] = vals.get('shipment_id', False)
        else:  # if it is a CONSO-OUT --_> set the state for replicating back to CP
            if 'name' in vals and 'OUT-CONSO' in vals['name']:
                vals.update(already_replicated=False,)

        # the action adds subtype in the context depending from which screen it is created
        if context.get('picking_screen', False) and not vals.get('name', False):
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket')
            vals.update(subtype='picking',
                        backorder_id=False,
                        name=pick_name,
                        flow_type='full',
                        )

        if context.get('ppl_screen', False) and not vals.get('name', False):
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'ppl')
            vals.update(subtype='ppl',
                        backorder_id=False,
                        name=pick_name,
                        flow_type='full',
                        )
        shipment_obj = self.pool.get('shipment')

        # sequence creation
        # if draft picking
        if 'subtype' in vals and vals['subtype'] == 'picking':
            # creation of a new picking ticket
            assert 'backorder_id' in vals, 'No backorder_id'

            if not vals['backorder_id']:
                # creation of *draft* picking ticket
                vals.update(sequence_id=self.create_sequence(cr, uid, {'name': vals['name'],
                                                                       'code': vals['name'],
                                                                       'prefix': '',
                                                                       'padding': 2}, context=context))

        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'backorder_id' in vals, 'No backorder_id'
            assert 'shipment_id' in vals, 'No shipment_id'

            if not vals['backorder_id']:
                # creation of *draft* picking ticket
                vals.update(sequence_id=self.create_sequence(cr, uid, {'name': vals['name'],
                                                                       'code': vals['name'],
                                                                       'prefix': '',
                                                                       'padding': 2,
                                                                       }, context=context))

        # create packing object
        new_packing_id = super(stock_picking, self).create(cr, uid, vals, context=context)

        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'backorder_id' in vals, 'No backorder_id'
            assert 'shipment_id' in vals, 'No shipment_id'

            if vals['backorder_id'] and vals['shipment_id']:
                # ship of existing shipment
                # no new shipment
                # TODO
                return new_packing_id


            if not vals['backorder_id']:
                # creation of packing after ppl validation
                # find an existing shipment or create one - depends on new pick state
                shipment_ids = shipment_obj.search(cr, uid, [('state', '=', 'draft'), ('address_id', '=', vals['address_id'])], context=context)
                # only one 'draft' shipment should be available
                if len(shipment_ids) > 1:
                    other = shipment_obj.read(cr, uid, shipment_ids, ['name'], context=context)
                    raise osv.except_osv(
                        _('Error'),
                        _('You can only have one draft shipment for a given address, please check %s') % ', '.join(x['name'] for x in other),
                    )
                # get rts of corresponding sale order
                sale_id = self.read(cr, uid, [new_packing_id], ['sale_id'], context=context)
                sale_id = sale_id[0]['sale_id']
                if sale_id:
                    sale_id = sale_id[0]
                    rts = sale_order_obj.read(cr, uid, sale_id, ['ready_to_ship_date'], context=context)['ready_to_ship_date']
                else:
                    # today
                    rts = date.today().strftime(db_date_format)
                # rts + shipment lt
                shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                rts_obj = datetime.strptime(rts, db_date_format)
                rts = rts_obj + relativedelta(days=shipment_lt or 0)
                rts = rts.strftime(db_date_format)

                if not len(shipment_ids):
                    # only create new shipment if we don't already have one through sync
                    if not vals['shipment_id'] and not context.get('offline_synchronization', False):
                        # no shipment, create one - no need to specify the state, it's a function
                        name = self.pool.get('ir.sequence').get(cr, uid, 'shipment')
                        addr = self.pool.get('res.partner.address').browse(cr, uid, vals['address_id'], context=context)
                        partner_id = addr.partner_id and addr.partner_id.id or False
                        values = {'name': name,
                                  'address_id': vals['address_id'],
                                  'partner_id2': partner_id,
                                  'shipment_expected_date': rts,
                                  'shipment_actual_date': time.strftime(db_datetime_format),
                                  'sale_id': vals.get('sale_id', False),
                                  'transport_type': sale_id and sale_order_obj.read(cr, uid, sale_id, ['transport_type'], context=context)['transport_type'] or False,
                                  'sequence_id': self.create_sequence(cr, uid, {'name': name,
                                                                                'code': name,
                                                                                'prefix': '',
                                                                                'padding': 2}, context=context)}

                        shipment_id = shipment_obj.create(cr, uid, values, context=context)
                        # Log creation message
                        message = _('The new Shipment List (%s) has been created.')
                        shipment_obj.log(cr, uid, shipment_id, message % (name,))
                        shipment_obj.infolog(cr, uid, message % (name,))
                    else:
                        shipment_id = vals['shipment_id']
                else:
                    shipment_id = shipment_ids[0]
                    shipment = shipment_obj.browse(cr, uid, shipment_id, fields_to_fetch=['shipment_expected_date', 'name'], context=context)
                    # if expected ship date of shipment is greater than rts, update shipment_expected_date and shipment_actual_date
                    if shipment.shipment_expected_date:
                        shipment_expected = datetime.strptime(shipment.shipment_expected_date, db_datetime_format)
                        if rts_obj < shipment_expected:
                            shipment.write({'shipment_expected_date': rts, 'shipment_actual_date': rts, }, context=context)
                    shipment_name = shipment.name
                    shipment_obj.log(cr, uid, shipment_id, _('The PPL has been added to the existing Draft Shipment %s.') % (shipment_name,))

                # update the new pick with shipment_id
                self.write(cr, uid, [new_packing_id], {'shipment_id': shipment_id}, context=context)

        return new_packing_id

    def _get_keep_move(self, cr, uid, ids, context=None):
        '''
        Returns for each stock move of the draft PT, if we should keep it
        '''
        pick_moves = {}
        for pick in self.browse(cr, uid, ids, context=context):
            for bo in pick.backorder_ids:
                if not bo.is_completed()[bo.id]:
                    # Check for each stock move of the draft PT, if there is an in progress stock move
                    pick_moves.setdefault(pick.id, {})
                    for m in bo.move_lines:
                        if m.state not in ('done', 'cancel'):
                            pick_moves[pick.id].setdefault(m.backmove_id.id, True)
                    steps = bo.previous_step_ids
                    while steps:
                        for next_step in steps:
                            steps.remove(next_step)
                            for m in next_step.move_lines:
                                if m.state not in ('done', 'cancel'):
                                    pick_moves[pick.id].setdefault(m.backmove_id.id, True)
                            steps.extend(next_step.previous_step_ids)

        return pick_moves

    @check_cp_rw
    def convert_to_standard(self, cr, uid, ids, context=None):
        '''
        check of back orders exists, if not, convert to standard: change subtype to standard, and trigger workflow

        only one picking object at a time
        '''
        if not context:
            context = {}
        # objects
        move_obj = self.pool.get('stock.move')
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        moves_states = {}
        pick_to_check = set()

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.subtype == 'standard':
                raise osv.except_osv(
                    _('Bad state'),
                    _('The document you want to convert is already a standard OUT'),
                )

            if obj.subtype != 'picking' or obj.state not in ('draft', 'assigned'):
                raise osv.except_osv(
                    _('Error'),
                    _('The convert function should only be called on draft picking ticket objects'),
                )

            # log a message concerning the conversion
            new_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
            # in case of return claim
            if '-return' in obj.name:
                new_name += '-return'
            elif '-surplus' in obj.name:
                new_name += '-surplus'

            if context.get('rw_backorder_name', False):
                new_name = context.get('rw_backorder_name')
                del context['rw_backorder_name']

            self.log(cr, uid, obj.id, _('The Picking Ticket (%s) has been converted to simple Out (%s).') % (obj.name, new_name), action_xmlid='stock.action_picking_tree')

            keep_move = self._get_keep_move(cr, uid, [obj.id], context=context).get(obj.id, None)
            # change subtype and name and add requestor
            default_vals = {'name': new_name,
                            'move_lines': [],
                            'subtype': 'standard',
                            'converted_to_standard': True,
                            'backorder_id': False,
                            'requestor': obj.address_id and obj.address_id.name or False,
                            }
            new_pick_id = False
            new_lines = []

            if obj.state == 'draft' and keep_move is not None:
                context['wkf_copy'] = True
                context['allow_copy'] = True
                new_pick_id = self.copy(cr, uid, obj.id, default_vals, context=context)
                pick_to_check.add(obj.id)
            else:
                self.write(cr, uid, obj.id, default_vals, context=context)

            if obj.backorder_id:
                pick_to_check.add(obj.backorder_id.id)

            # all destination location of the stock moves must be output location of warehouse - lot_output_id
            # if corresponding sale order, date and date_expected are updated to rts + shipment lt
            for move in obj.move_lines:
                # was previously set to confirmed/assigned, otherwise, when we confirm the stock picking,
                # using draft_force_assign, the moves are not treated because not in draft
                # and the corresponding chain location on location_dest_id was not computed
                # we therefore set them back in draft state before treatment
                if move.product_qty == 0.0:
                    vals = {'state': 'done'}
                else:
                    # Save the state of this stock move to set it before action_assign()
                    moves_states[move.id] = move.state
                    if move.state not in ('cancel', 'done'):
                        vals = {'state': 'draft'}
                    else:
                        vals = {'state': move.state}
                vals.update({'backmove_id': False, 'composition_list_id': False})
                # If the move comes from a DPO, don't change the destination location
                if move.dpo_id:
                    pass
                elif move.old_out_location_dest_id:
                    vals.update({'location_dest_id': move.old_out_location_dest_id.id})
                else:
                    vals.update({'location_dest_id': obj.warehouse_id.lot_output_id.id})

                if obj.sale_id:
                    # compute date
                    shipment_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                    rts = datetime.strptime(obj.sale_id.ready_to_ship_date, db_date_format)
                    rts = rts + relativedelta(days=shipment_lt or 0)
                    rts = rts.strftime(db_date_format)
                    vals.update({'date': rts, 'date_expected': rts, 'state': 'draft'})

                if not new_pick_id:
                    move.write(vals, context=context)
                    keep_backmove = move_obj.search(cr, uid, [('backmove_id', '=', move.backmove_id.id)], context=context)
                    if move.backmove_id and move.backmove_id.product_qty == 0.00:
                        keep_backmove = move_obj.search(cr, uid, [('backmove_id', '=', move.backmove_id.id), ('state', 'not in', ('done', 'cancel'))], context=context)
                        if not keep_backmove:
                            move_obj.write(cr, uid, [move.backmove_id.id], {'state': 'done'}, context=context)
                            move_obj.update_linked_documents(cr, uid, move.backmove_id.id, move.id, context=context)
                    if move.product_qty == 0.00:
                        if move.sale_line_id:
                            other_linked_moves = move_obj.search(cr, uid, [
                                ('id', '!=', move.id),
                                ('sale_line_id', '=', move.sale_line_id.id),
                                ('state', 'not in', ['cancel', 'done'])
                            ], order='NO_ORDER', limit=1, context=context)
                            if not other_linked_moves:
                                other_linked_moves = move_obj.search(cr, uid, [
                                    ('id', '!=', move.id),
                                    ('sale_line_id', '=', move.sale_line_id.id),
                                    ('state', '!=', 'cancel')
                                ], order='NO_ORDER', limit=1, context=context)
                            if other_linked_moves:
                                move_obj.update_linked_documents(cr, uid, move.id, other_linked_moves[0], context=context)
                        move.unlink(force=True)
#                        move.action_done(context=context)
                elif move.product_qty != 0.00:
                    vals.update({'picking_id': new_pick_id,
                                 'line_number': move.line_number,
                                 'state': moves_states[move.id],
                                 'product_qty': move.product_qty, })

                    new_move_id = move_obj.copy(cr, uid, move.id, vals, context=context)

                    # Compute the chained location as an initial confirmation of move
                    if move.state == 'assigned':
                        new_move = move_obj.browse(cr, uid, new_move_id, context=context)
                        tmp_ac = context.get('action_confirm', False)
                        context['action_confirm'] = True
                        move_obj.create_chained_picking(cr, uid, [new_move], context=context)
                        context['action_confirm'] = tmp_ac

                    # Update all linked objects to avoid close of related documents
                    if move.id not in keep_move or not keep_move[move.id]:
                        move_obj.update_linked_documents(cr, uid, move.id, new_move_id, context=context)

                    # Set the stock move to done with 0.00 qty
                    if (move.id in keep_move and keep_move[move.id])\
                            or ('return' in move.picking_id.name or 'surplus' in move.picking_id.name):
                        m_st = move.state
                    else:
                        m_st = 'done'
                        moves_states[move.id] = 'done'
                    move_obj.write(cr, uid, [move.id], {'product_qty': 0.00,
                                                        'state': m_st}, context=context)

                    new_lines.append(new_move_id)

            if pick_to_check:
                for ptc_id in pick_to_check:
                    ptc = self.browse(cr, uid, ptc_id, context=context)
                    if ptc.state == 'draft' and ptc.subtype == 'picking' and self.has_picking_ticket_in_progress(cr, uid, [ptc_id], context=context)[ptc_id]:
                        continue
                    if ptc.state == 'draft':
                        self.validate(cr, uid, list(pick_to_check), context=context)
                    ptc = self.browse(cr, uid, ptc_id, context=context)
                    if all(m.state == 'cancel' or (m.product_qty == 0.00 and m.state in ('done', 'cancel')) for m in ptc.move_lines):
                        ptc.action_done(context=context)

            # trigger workflow (confirm picking)
            self.draft_force_assign(cr, uid, [new_pick_id or obj.id])

            for s in moves_states:
                move_obj.write(cr, uid, [s], {'state': moves_states[s]}, context=context)

            # check availability
            self.action_assign(cr, uid, [new_pick_id or obj.id], context=context)

            if 'assigned' in list(moves_states.values()):
                # Add an empty write to display the 'Process' button on OUT
                self.write(cr, uid, [new_pick_id or obj.id], {'state': 'assigned'}, context=context)

            self.infolog(cr, uid, "The Picking Ticket id:%s (%s) has been converted to simple Out id:%s (%s)." % (
                obj.id, obj.name,
                new_pick_id or obj.id, new_name,
            ))

            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'stock.action_picking_tree', ['form', 'tree'], context=context)
            res['res_id'] = new_pick_id or obj.id
            return res

    def _hook_create_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        return True

    def _hook_delete_rw_out_sync_messages(self, cr, uid, ids, context=None, out=True):
        return True

    @check_cp_rw
    def convert_to_pick(self, cr, uid, ids, context=None):
        '''
        Change simple OUTs to draft Picking Tickets
        '''
        context = context or {}

        # Objects
        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')

        move_to_update = []

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')
        tree_view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_tree')
        view_id = view_id and view_id[1] or False
        tree_view_id = tree_view_id and tree_view_id[1] or False
        search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_search')
        search_view_id = search_view_id and search_view_id[1] or False

        for out in self.browse(cr, uid, ids, context=context):
            if out.subtype == 'picking':
                raise osv.except_osv(
                    _('Bad document'),
                    _('The document you want to convert is already a Picking Ticket')
                )
            if not out.sale_id and not out.claim:
                raise osv.except_osv(_('Error'), _('You can not convert a Delivery Order from scratch into a Picking Ticket'))
            if out.state in ('cancel', 'done'):
                raise osv.except_osv(_('Error'), _('You cannot convert %s delivery orders') % (out.state == 'cancel' and _('Canceled') or _('Done')))

            # log a message concerning the conversion
            new_name = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket')
            # in case of return claim
            if '-return' in out.name:
                new_name += '-return'
            elif '-surplus' in out.name:
                new_name += '-surplus'

            # change subtype and name
            default_vals = {'name': new_name,
                            'subtype': 'picking',
                            'converted_to_standard': False,
                            'state': 'draft',
                            'sequence_id': self.create_sequence(cr, uid, {'name': new_name,
                                                                          'code': new_name,
                                                                          'prefix': '',
                                                                          'padding': 2}, context=context)
                            }

            self.write(cr, uid, [out.id], default_vals, context=context)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', out.id, 'convert_to_picking_ticket', cr)
            # we force availability

            self.log(cr, uid, out.id, _('The Delivery order (%s) has been converted to draft Picking Ticket (%s).') % (out.name, new_name), action_xmlid='msf_outgoing.action_picking_ticket')
            self.infolog(cr, uid, "The Delivery order id:%s (%s) has been converted to draft Picking Ticket id:%s (%s)." % (
                out.id, out.name, out.id, new_name,
            ))

            for move in out.move_lines:
                move_to_update.append(move.id)

        pack_loc_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1]
        if move_to_update:
            for move in move_obj.browse(cr, uid, move_to_update, context=context):
                # Remove all KCL references from the OUT process wizard lines linked to the move
                if move.product_id.subtype == 'kit':
                    out_m_proc_obj = self.pool.get('outgoing.delivery.move.processor')
                    out_m_proc_ids = out_m_proc_obj.search(cr, uid, [('move_id', '=', move.id), ('composition_list_id', '!=', False)], context=context)
                    if out_m_proc_ids:
                        out_m_proc_obj.write(cr, uid, out_m_proc_ids, {'composition_list_id': False}, context=context)

                move_obj.write(cr, uid, [move.id], {
                    'location_dest_id': pack_loc_id,
                    'old_out_location_dest_id': move.location_dest_id.id,
                    'qty_to_process': move.product_qty,
                }, context=context)

        # Create a sync message for RW when converting the OUT back to PICK, except the caller of this method is sync
        if not context.get('sync_message_execution', False):
            self._hook_create_rw_out_sync_messages(cr, uid, [out.id], context, False)

        context.update({'picking_type': 'picking', 'search_view_id': search_view_id, 'from_button': False})
        return {'name': _('Picking Tickets'),
                'view_mode': 'form,tree',
                'view_id': [view_id, tree_view_id],
                'search_view_id': search_view_id,
                'view_type': 'form',
                'res_model': 'stock.picking',
                'res_id': out.id,
                'type': 'ir.actions.act_window',
                'target': 'crush',
                'domain': [('type', '=', 'out'), ('subtype', '=', 'picking')],
                'context': context}

    def do_partial_out(self, cr, uid, wizard_ids, context=None):
        """
        Process the stock picking from selected stock moves

        BE CAREFUL: the wizard_ids parameters is the IDs of the outgoing.delivery.processor objects,
        not those of stock.picking objects
        """
        return self.do_partial(cr, uid, wizard_ids, 'outgoing.delivery.processor', context)

    def do_partial(self, cr, uid, wizard_ids, proc_model=False, context=None):
        """
        Process the stock picking from selected stock moves

        BE CAREFUL: the wizard_ids parameters is the IDs of the internal.picking.processor objects,
        not those of stock.picking objects
        """
        # Objects
        proc_obj = self.pool.get('internal.picking.processor')
        picking_obj = self.pool.get('stock.picking')
        sequence_obj = self.pool.get('ir.sequence')
        uom_obj = self.pool.get('product.uom')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")

        res = {}

        if proc_model:
            proc_obj = self.pool.get(proc_model)

        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids = [wizard_ids]

        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            new_picking_id = False
            processed_moves = []
            new_split_move = {}
            move_data = {}
            for line in wizard.move_ids:
                move = line.move_id

                if move.product_id and move.product_id.state.code == 'forbidden':  # Check constraints on lines
                    check_vals = {'location_dest_id': move.location_dest_id.id, 'move': move}
                    self.pool.get('product.product')._get_restriction_error(cr, uid, [move.product_id.id], check_vals,
                                                                            context=context)

                if move.picking_id.id != picking.id:
                    continue

                if move.id not in move_data:
                    move_data.setdefault(move.id, {
                        'original_qty': move.product_qty,
                        'processed_qty': 0.00,
                        'total_qty': move.product_qty,
                    })

                if line.quantity <= 0.00:
                    continue

                # Handle the Kit in the OUT
                if proc_model == 'outgoing.delivery.processor' and line.composition_list_id:
                    if line.quantity > 1:
                        raise osv.except_osv(_('Warning'), _('A line qty is greater than 1. If the Kit Reference is filled, then the line must be split'))
                    else:
                        self.pool.get('composition.kit').close_kit(cr, uid, [line.composition_list_id.id], self._name, context=context)

                orig_qty = move.product_qty
                if move.original_qty_partial and move.original_qty_partial != -1:
                    orig_qty = move.original_qty_partial

                if line.uom_id.id != move.product_uom.id:
                    quantity = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, move.product_uom.id)
                else:
                    quantity = line.quantity

                move_data[move.id]['processed_qty'] += quantity

                values = {
                    'line_number': move.line_number,
                    'product_qty': line.quantity,
                    'product_uos_qty': line.quantity,
                    'state': 'assigned',
                    'move_dest_id': False,
                    'price_unit': move.price_unit,
                    'processed_stock_move': True,
                    'prodlot_id': line.prodlot_id and line.prodlot_id.id or False,
                    'asset_id': line.asset_id and line.asset_id.id or False,
                    'composition_list_id': line.composition_list_id and line.composition_list_id.id or False,
                    'original_qty_partial': orig_qty,
                    'location_id': line.location_id and line.location_id.id,
                }
                if picking.type == 'out':
                    values['reason_type_id'] = picking.reason_type_id.id

                # If claim expects replacement
                # or claim is from INT created by processing an IN to Stock instead of Cross Docking
                if wizard.register_a_claim and (wizard.claim_replacement_picking_expected
                                                or (picking.type == 'internal'
                                                    and move.purchase_line_id.linked_sol_id.order_id
                                                    and move.purchase_line_id.linked_sol_id.order_id.procurement_request
                                                    and wizard.claim_type in ('scrap', 'quarantine', 'return'))):
                    values.update({
                        'purchase_line_id': move.purchase_line_id and move.purchase_line_id.id or False,
                    })

                if quantity < move.product_qty and move_data[move.id]['original_qty'] > move_data[move.id]['processed_qty']:
                    # Create a new move
                    new_move_id = move_obj.copy(cr, uid, move.id, values, context=context)
                    processed_moves.append(new_move_id)
                    new_split_move[new_move_id] = True

                    # Update the original move

                    # here we can't use move.product_qty bc this value is bowser_record cached on not flush with the following write
                    move_data[move.id]['total_qty'] -= quantity
                    wr_vals = {
                        'product_qty': move_data[move.id]['total_qty'],
                        'product_uos_qty': move_data[move.id]['total_qty'],
                        'qty_to_process': move_data[move.id]['total_qty'],
                    }
                    move_obj.write(cr, uid, [move.id], wr_vals, context=context)
                else:
                    # Update the original move
                    move_obj.write(cr, uid, [move.id], values, context=context)
                    processed_moves.append(move.id)


            if not len(move_data):
                pick_type = 'Internal picking'
                if picking.type == 'out':
                    pick_type = 'Outgoing Delivery'

                raise osv.except_osv(
                    _('Error'),
                    _('An error occurs during the processing of the %(pick_type)s, maybe the %(pick_type)s has been already processed. Please check this and retry') % {'pick_type': pick_type},
                )

            # We check if all stock moves and all quantities are processed
            # If not, create a backorder
            need_new_picking = False
            for move in picking.move_lines:
                if not new_split_move.get(move.id) and move.state not in ('done', 'cancel') and (not move_data.get(move.id, False) or \
                                                                                                 move_data[move.id]['original_qty'] != move_data[move.id]['processed_qty']):
                    need_new_picking = True
                    break

            rw_full_process = context.get('rw_full_process', False)
            if rw_full_process:
                del context['rw_full_process']
            if need_new_picking and not rw_full_process:
                cp_vals = {
                    'name': sequence_obj.get(cr, uid, 'stock.picking.%s' % (picking.type)),
                    'move_lines': [],
                    'state': 'draft',
                    'claim': picking.claim,
                    'claim_name': picking.claim_name
                }
                context['allow_copy'] = True

                new_picking_id = picking_obj.copy(cr, uid, picking.id, cp_vals, context=context)

                context['allow_copy'] = False
                move_obj.write(cr, uid, processed_moves, {'picking_id': new_picking_id}, context=context)

            # At first we confirm the new picking (if necessary)
            pick_to_check = False
            if new_picking_id:
                self.write(cr, uid, [picking.id], {'backorder_id': new_picking_id}, context=context)

                rw_name = context.get('rw_backorder_name', False)
                update_vals = {}
                if rw_name:
                    update_vals.update({'name': rw_name})
                    del context['rw_backorder_name']

                if picking.type == 'internal':
                    update_vals.update({'associate_pick_name': picking.name})

                if len(update_vals) > 0:
                    self.write(cr, uid, [new_picking_id], update_vals, context=context)

                # Claim specific code
                self._claim_registration(cr, uid, wizard, new_picking_id, context=context)

                if wizard.register_a_claim and wizard.claim_type in ('return', 'surplus'):
                    move_ids = move_obj.search(cr, uid, [('picking_id', '=', new_picking_id)])
                    move_obj.action_cancel(cr, uid, move_ids, context=context)
                    self.action_cancel(cr, uid, [new_picking_id], context=context)
                    # check the OUT availability
                    out_domain = [('backorder_id', '=', new_picking_id), ('type', '=', 'out')]
                    out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                    self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                else:
                    # We confirm the new picking after its name was possibly modified by custom code - so the link message (top message) is correct
                    wf_service.trg_validate(uid, 'stock.picking', new_picking_id, 'button_confirm', cr)
                    # Then we finish the picking
                    self.action_move(cr, uid, [new_picking_id])
                    wf_service.trg_validate(uid, 'stock.picking', new_picking_id, 'button_done', cr)
                    pick_to_check = new_picking_id
                # UF-1617: Hook a method to create the sync messages for some extra objects: batch number, asset once the OUT/partial is done
                self._hook_create_sync_messages(cr, uid, new_picking_id, context)

                wf_service.trg_write(uid, 'stock.picking', picking.id, cr)
                delivered_pack_id = new_picking_id

                new_pick_name = self.read(cr, uid, new_picking_id, ['name'], context=context)['name']
                self.infolog(cr, uid, "The Outgoing Delivery id:%s (%s) has been processed. Backorder id:%s (%s) has been created." % (
                    new_picking_id, new_pick_name, picking.id, picking.name,
                ))
            else:
                self.infolog(cr, uid, "The Outgoing Delivery id:%s (%s) has been processed." % (
                    picking.id, picking.name,
                ))
                # Claim specific code
                self._claim_registration(cr, uid, wizard, picking.id, context=context)

                if wizard.register_a_claim and wizard.claim_type in ('return', 'surplus'):
                    move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking.id)])
                    move_obj.action_cancel(cr, uid, move_ids, context=context)
                    self.action_cancel(cr, uid, [picking.id], context=context)
                    # check the OUT availability
                    out_domain = [('backorder_id', '=', picking.id), ('type', '=', 'out')]
                    out_id = picking_obj.search(cr, uid, out_domain, order='id desc', limit=1, context=context)[0]
                    self.pool.get('picking.tools').check_assign(cr, uid, out_id, context=context)
                else:
                    self.action_move(cr, uid, [picking.id])
                    wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)
                    update_vals = {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}
                    pick_to_check = picking.id
                    self.write(cr, uid, picking.id, update_vals)

                # UF-1617: Hook a method to create the sync messages for some extra objects: batch number, asset once the OUT/partial is done
                self._hook_create_sync_messages(cr, uid, [picking.id], context)

                delivered_pack_id = picking.id

            if pick_to_check:
                sale_line_id_checked = {}
                for move in self.browse(cr, uid, pick_to_check, fields_to_fetch=['move_lines'], context=context).move_lines:
                    if move.sale_line_id and move.sale_line_id.id not in sale_line_id_checked:
                        open_moves = self.pool.get('stock.move').search_exist(cr, uid, [
                            ('sale_line_id', '=', move.sale_line_id.id),
                            ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                            ('type', '=', 'out'),
                            ('id', '!=', move.id),
                        ], context=context)
                        if not open_moves:
                            sale_line_id_checked[move.sale_line_id.id] = True
                            wf_service.trg_validate(uid, 'sale.order.line', move.sale_line_id.id, 'done', cr)
            # UF-1617: set the delivered_pack_id (new or original) to become already_shipped
            self.write(cr, uid, [delivered_pack_id], {'already_shipped': True})

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[picking.id] = {'delivered_picking': delivered_pack.id or False}

            if picking.type == 'out' and picking.sale_id and picking.sale_id.procurement_request:
                wf_service.trg_write(uid, 'sale.order', picking.sale_id.id, cr)

        return res



    def do_create_picking_bg(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        assert len(ids) == 1, 'do_create_picking_bg can only process 1 object'

        for picking_id in ids:
            pick_data = self.read(cr, uid, picking_id, ['type', 'subtype'], context=context)
            if pick_data['type'] != 'out' or pick_data['subtype'] != 'picking':
                raise osv.except_osv(_('Warning'), _('This action can only be done on a Picking'))
            self.check_integrity(cr, uid, picking_id, context)

        nb_lines = self.pool.get('stock.move').search(cr, uid, [('qty_to_process', '>=', 0), ('state', '=', 'assigned'),('product_qty', '>', 0), ('picking_id', 'in', ids)], count=True)

        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, ids, 'stock.picking', self.do_create_picking, nb_lines, _('Create Picking'), context=context)


    def do_create_picking(self, cr, uid, ids, context=None, only_pack_ids=False, job_id=False):
        """
            from draft picking ticket create a sub-picking
            it will process all available stock.move with a qty in qty_to_process

            only_pack_ids : used for import from IN to P/P/S, then it will process only these moves
        """

        # Objects
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for picking in self.browse(cr, uid, ids, context=context):
            res = False
            if picking.type != 'out' or picking.subtype != 'picking':
                raise osv.except_osv(_('Warning'), _('This action can only be done on a Picking'))
            if not job_id:
                self.check_integrity(cr, uid, picking.id, context)

            sequence = picking.sequence_id
            ticket_number = sequence.get_id(code_or_id='id', context=context)
            pick_name = '%s-%s' % (picking.name or 'NoName/000', ticket_number)
            copy_data = {
                'name': pick_name,
                'backorder_id': picking.id,
                'move_lines': [],
                'is_subpick': True,
            }
            tmp_allow_copy = context.get('allow_copy')
            context.update({
                'wkf_copy': True,
                'allow_copy': True,
            })
            new_picking_id = self.copy(cr, uid, picking.id, copy_data, context=context)
            if picking.claim:
                self.write(cr, uid, new_picking_id, ({'claim': True}), context=context)

            if tmp_allow_copy is None:
                del context['allow_copy']
            else:
                context['allow_copy'] = tmp_allow_copy

            if only_pack_ids:
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking.id), ('pack_info_id', 'in', only_pack_ids)], context=context)
                move_to_process = move_obj.browse(cr, uid, move_ids, context=context)
            else:
                move_to_process = picking.move_lines

            nb_processed = 0
            # Create stock moves corresponding to processing lines
            # for now, each new line from the wizard corresponds to a new stock.move
            # it could be interesting to regroup according to production lot/asset id
            for line in move_to_process:
                if line.product_id and line.product_id.state.code == 'forbidden':  # Check constraints on lines
                    check_vals = {'location_dest_id': line.location_dest_id.id, 'move': line}
                    self.pool.get('product.product')._get_restriction_error(cr, uid, [line.product_id.id], check_vals, context=context)

                if line.qty_to_process <= 0 or line.state != 'assigned' or line.product_qty == 0:
                    continue

                nb_processed += 1
                if job_id and nb_processed % 10 == 0:
                    self.pool.get('job.in_progress').write(cr, uid, [job_id], {'nb_processed': nb_processed})

                # Copy the stock move and set the quantity
                cp_values = {
                    'picking_id': new_picking_id,
                    'product_qty': line.qty_to_process,
                    'product_uom': line.product_uom.id,
                    'product_uos_qty': line.qty_to_process,
                    'product_uos': line.product_uom.id,
                    'prodlot_id': line.prodlot_id and line.prodlot_id.id,
                    'asset_id': line.asset_id and line.asset_id.id,
                    'composition_list_id': line.composition_list_id and line.composition_list_id.id,
                    'pt_created': True,
                    'backmove_id': line.id,
                    'pack_info_id': line.pack_info_id and line.pack_info_id.id or False,
                }
                context['keepLineNumber'] = True
                move_obj.copy(cr, uid, line.id, cp_values, context=context)
                context['keepLineNumber'] = False


                initial_qty = max(line.product_qty - line.qty_to_process, 0.00)
                qty_processed = (line.qty_processed or 0) + line.qty_to_process
                wr_vals = {
                    'product_qty': initial_qty,
                    'product_uos_qty': initial_qty,
                    'processed_stock_move': True,
                    'qty_processed': qty_processed,
                }
                if initial_qty == 0:
                    wr_vals['qty_to_process'] = qty_processed
                else:
                    wr_vals['qty_to_process'] = initial_qty
                # Remove The KCL Ref from the original line if the whole line is not processed
                if line.composition_list_id and line.qty_to_process < line.product_qty:
                    wr_vals['composition_list_id'] = False

                context['keepLineNumber'] = True
                move_obj.write(cr, uid, [line.id], wr_vals, context=context)
                context['keepLineNumber'] = False


            # Confirm the new picking ticket
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', new_picking_id, 'button_confirm', cr)
            # We force availability
            self.force_assign(cr, uid, [new_picking_id])
            self.infolog(cr, uid, "The Validated Picking Ticket id:%s (%s) has been generated by the Draft Picking Ticket id:%s (%s)" % (
                new_picking_id, self.read(cr, uid, new_picking_id, ['name'], context=context)['name'],
                picking.id, picking.name,
            ))

        if not nb_processed:
            raise osv.except_osv(_('Warning'), _('No line to process'))

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_picking_ticket', ['form', 'tree'], context=context)
        res['res_id'] = new_picking_id
        return res

    def check_integrity(self, cr, uid, pid, context=None):
        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')

        if not move_obj.search_exist(cr, uid, [('picking_id', '=', pid), ('state', '=', 'assigned'), ('qty_to_process', '!=', 0), ('product_qty', '!=', 0)], context=context):
            raise osv.except_osv(_('Warning'), _('No line to process, please set Qty to process'))

        neg_ids = move_obj.search(cr, uid, [('picking_id', '=', pid), ('state', '=', 'assigned'), ('qty_to_process', '<', 0)], context=context)
        if neg_ids:
            neg = move_obj.browse(cr, uid, neg_ids, fields_to_fetch=['line_number'], context=context)
            raise osv.except_osv(_('Warning'), _('Qty to process must be positive, line(s): %s') % ', '.join(['#%s' % x.line_number for x in neg]))

        # Do not process more that requested
        cr.execute('''
            select
                line_number, qty_to_process, product_qty
            from stock_move
            where
                qty_to_process!=0 and
                product_qty!=0 and
                state='assigned' and
                picking_id=%s and
                qty_to_process > product_qty
        ''', (pid,))
        error = []
        for x in cr.fetchall():
            error.append(_('#%d qty to process %s, qty in move %s') % (x[0], x[1], x[2]))
        if error:
            raise osv.except_osv(
                _('Warning'),
                _("Processed quantites can't be larger than quantity in move, please check these lines:\n %s") % "\n".join(error)
            )

        # BN/ED: check qty in stock
        cr.execute('''
            select
                sum(qty_to_process), location_id, prodlot_id, product_uom
            from stock_move
            where
                qty_to_process!=0 and
                product_qty!=0 and
                prodlot_id is not null and
                state='assigned' and
                picking_id=%s
            group by location_id, prodlot_id, product_uom
        ''', (pid,))
        needed_qty = {}
        for x in cr.fetchall():
            needed_qty.setdefault(x[1], {})
            needed_qty[x[1]].setdefault(x[2], 0)
            lot = lot_obj.browse(cr, uid, x[2], fields_to_fetch=['stock_available', 'product_id', 'name'], context={'location_id': x[1]})
            if lot.product_id.uom_id.id != x[3]:
                qty = uom_obj._compute_qty(cr, uid, x[3], x[0], lot.product_id.uom_id.id)
            else:
                qty = x[0]
            needed_qty[x[1]][x[2]] += qty
            if lot.stock_available < needed_qty[x[1]][x[2]]:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('Processing quantity %d %s for %s is larger than the available quantity in Batch Number %s (%d) !') %
                    (needed_qty[x[1]][x[2]], lot.product_id.uom_id.name, lot.product_id.default_code, lot.name, lot.stock_available)
                )

        # BN/ED: check lot is set
        cr.execute("""
            select line_number
            from
                stock_move m
                left join stock_production_lot l on l.id=m.prodlot_id
                left join product_product p on m.product_id = p.id
            where
                m.picking_id = %s and
                m.state='assigned' and
                m.qty_to_process!=0 and
                (p.batch_management='t' or p.perishable='t') and
                l.id is null
        """, (pid, ))
        l = ['#%s' % x[0] for x in cr.fetchall()]
        if l:
            raise osv.except_osv(
                _('Processing Error'),
                _('Batch number is needed on lines %s !') % ','.join(l)
            )

        # Check if there is a KCL line with a qty > 1
        if move_obj.search_exist(cr, uid, [('picking_id', '=', pid), ('state', '=', 'assigned'), ('qty_to_process', '>', 1), ('composition_list_id', '!=', False)], context=context):
            raise osv.except_osv(_('Warning'), _('A line qty is greater than 1. If the Kit Reference is filled, then the line must be split'))

        return True

    def do_validate_picking_bg(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        assert len(ids) == 1, 'do_validate_picking_bg can only process 1 object'

        for picking_id in ids:
            pick_data = self.read(cr, uid, picking_id, ['type', 'subtype'], context=context)
            if pick_data['type'] != 'out' or pick_data['subtype'] != 'picking':
                raise osv.except_osv(_('Warning'), _('This action can only be done on a Picking'))
            self.check_integrity(cr, uid, picking_id, context)
            # Check if the processed sub-Pick has at least a non-fully processed line and there is a signature
            if not context.get('partial_process_sign'):
                cr.execute("""
                    SELECT m.id FROM stock_move m LEFT JOIN stock_picking p ON m.picking_id = p.id
                        , signature s LEFT JOIN signature_line sl ON sl.signature_id = s.id
                    WHERE s.signature_res_id = p.id AND s.signature_res_model = 'stock.picking' AND s.signature_res_id = %s 
                        AND sl.signed = 't' AND m.picking_id = %s AND m.qty_to_process < m.product_qty LIMIT 1
                """, (picking_id, picking_id))
                if cr.fetchone():
                    wiz_id = self.pool.get('warning.pick.partial.process.sign.wizard').create(cr, uid, {'picking_id': picking_id}, context=context)
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'warning.pick.partial.process.sign.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': wiz_id,
                        'context': context
                    }
            else:
                context.pop('partial_process_sign')

        nb_lines = self.pool.get('stock.move').search(cr, uid, [('state', '=', 'assigned'), ('picking_id', 'in', ids)], count=True)
        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, ids, 'stock.picking', self.do_validate_picking, nb_lines, _('Validate Picking'), context=context)

    def do_validate_picking(self, cr, uid, ids, context=None, job_id=False, ignore_quick=False):
        '''
        Validate the picking ticket from selected stock moves

        Move here the logic of validate picking

        '''

        date_tools = self.pool.get('date.tools')
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        today = time.strftime(db_date_format)
        nb_processed = 0
        for picking in self.browse(cr, uid, ids, context=context):

            if picking.state != 'assigned':
                raise osv.except_osv(
                    _('Error'),
                    _('The picking ticket is not in \'Available\' state. Please check this and re-try')
                )
            if picking.type != 'out' or picking.subtype != 'picking':
                raise osv.except_osv(_('Warning'), _('This action can only be done on a Picking'))

            if not job_id:
                self.check_integrity(cr, uid, picking.id, context)
            ppl_number = 'PPL/%s' % picking.name.split("/")[1]
            # We want the copy to keep the batch number reference from picking ticket to pre-packing list
            cp_vals = {
                'name': ppl_number,
                'subtype': 'ppl',
                'previous_step_id': picking.id,
                'backorder_id': False,
                'move_lines': [],
            }
            context.update({
                'keep_prodlot': True,
                'allow_copy': True,
                'keepLineNumber': True,
            })

            new_ppl_id = self.copy(cr, uid, picking.id, cp_vals, context=context)
            if picking.claim:
                self.write(cr, uid, new_ppl_id, ({'claim': True}), context=context)

            new_ppl = self.browse(cr, uid, new_ppl_id, context=context)
            context.update({
                'keep_prodlot': False,
                'allow_copy': False,
                'keepLineNumber': False,
            })

            # For each processed lines, save the processed quantity to update the draft picking ticket
            # and create a new line on PPL
            for line in picking.move_lines:
                if line.product_id:  # Check constraints on lines
                    check_vals = {'location_dest_id': line.location_dest_id.id, 'move': line}
                    self.pool.get('product.product')._get_restriction_error(cr, uid, [line.product_id.id], check_vals, context=context)

                if line.state != 'assigned':
                    line.qty_to_process = 0

                orig_qty = line.product_qty
                if line.original_qty_partial and line.original_qty_partial != -1:
                    orig_qty = line.original_qty_partial

                nb_processed += 1
                if job_id and nb_processed % 10 == 0:
                    self.pool.get('job.in_progress').write(cr, uid, [job_id], {'nb_processed': nb_processed})

                values = {
                    'product_qty': line.qty_to_process,
                    'product_uos_qty': line.qty_to_process,
                    'qty_to_process': line.qty_to_process,
                    'product_uom': line.product_uom.id,
                    'product_uos': line.product_uom.id,
                    'prodlot_id': line.prodlot_id and line.prodlot_id.id,
                    'line_number': line.line_number,
                    'asset_id': line.asset_id and line.asset_id.id,
                    'composition_list_id': line.composition_list_id and line.composition_list_id.id,
                    'original_qty_partial': orig_qty,
                    'pack_info_id': line.pack_info_id and line.pack_info_id.id or False,
                }

                # update main pick
                if line.qty_to_process < line.product_qty:
                    # unassigned line in sub-pick must be closed and pushed back to main pick
                    if line.state == 'confirmed':
                        values['state'] = 'assigned'
                    move_obj.write(cr, uid, [line.id], values, context=context)


                    diff_qty = line.product_qty - line.qty_to_process
                    if line.backmove_id:
                        backmove_line = move_obj.browse(cr, uid, line.backmove_id.id, fields_to_fetch=['qty_processed', 'product_qty'], context=context)
                        if line.backmove_id.product_uom.id != line.product_uom.id:
                            diff_qty = uom_obj._compute_qty(cr, uid, line.product_uom.id, diff_qty, line.backmove_id.product_uom.id)
                        backorder_qty = max(backmove_line.product_qty + diff_qty, 0)
                        if backorder_qty != 0.00:
                            new_val = {'product_qty': backorder_qty, 'qty_processed': backmove_line.qty_processed and backmove_line.qty_processed - diff_qty or 0, 'qty_to_process': backorder_qty}
                            move_obj.write(cr, uid, [line.backmove_id.id], new_val, context=context)

                if line.qty_to_process:
                    values.update({
                        'picking_id': new_ppl_id,
                        'initial_location': line.location_id.id,
                        'location_id': line.location_dest_id.id,
                        'location_dest_id': new_ppl.warehouse_id.lot_dispatch_id.id,
                        'date': today,
                        'date_expected': today,
                        'from_pack': 1,
                        'to_pack': 1,
                    })
                    if line.pack_info_id:
                        values.update({
                            'from_pack': line.pack_info_id.parcel_from or 1,
                            'to_pack': line.pack_info_id.parcel_to or 1,
                            'length': line.pack_info_id.total_length,
                            'width': line.pack_info_id.total_width,
                            'height': line.pack_info_id.total_height,
                            'weight': line.pack_info_id.total_weight,
                            'parcel_ids': line.pack_info_id.parcel_ids,
                        })

                    context.update({
                        'keepLineNumber': True,
                        'non_stock_noupdate': True,
                    })
                    move_obj.copy(cr, uid, line.id, values, context=context)
                    context.update({
                        'keepLineNumber': False,
                        'non_stock_noupdate': False,
                    })

            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', new_ppl_id, 'button_confirm', cr)
            # simulate check assign button, as stock move must be available
            self.force_assign(cr, uid, [new_ppl_id])
            # trigger standard workflow for validated picking ticket
            self.action_move(cr, uid, [picking.id])
            wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)

            # if the flow type is in quick mode, we perform the ppl steps automatically
            if not ignore_quick and picking.flow_type == 'quick' and new_ppl:
                context['from_quick_flow'] = picking.id
                res = self.quick_mode(cr, uid, new_ppl.id, context=context)
                return res

            self.infolog(cr, uid, "The Validated Picking Ticket id:%s (%s) has been validated" % (
                picking.id, picking.name,
            ))

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_ppl', ['form', 'tree'], context=context)
        res['res_id'] = new_ppl and new_ppl.id or False
        return res


    def quick_mode(self, cr, uid, ids, context=None):
        """
        Perform the PPL steps automatically

        """
        # Objects
        if context is None:
            context = {}

        if not isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        return self.ppl_step2(cr, uid, ids, context=context)

    def check_ppl_integrity(self, cr, uid, ids, context=None):

        move_obj = self.pool.get('stock.move')
        for picking_id in ids:
            move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking_id), ('state', '=', 'assigned')], context=context)
            sequences = []
            move_obj.write(cr, uid, move_ids, {'integrity_error': 'empty'}, context=context)
            for line in move_obj.browse(cr, uid, move_ids, fields_to_fetch=['from_pack', 'to_pack'], context=context):
                sequences.append((line.from_pack, line.to_pack, line.id))
            if sequences:
                self.pool.get('ppl.processor').check_sequences(cr, uid, sequences, move_obj, 'integrity_error', context=context)

        return True

    def ppl_step2(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        self.check_ppl_integrity(cr, uid, [ids[0]], context=context)
        issue_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', ids[0]), ('integrity_error', '!=', 'empty'), ('state', '!=', 'done')], context=context)
        if issue_ids:
            cr.commit()
            move = self.pool.get('stock.move').browse(cr, uid, issue_ids, fields_to_fetch=['line_number'], context=context)
            raise osv.except_osv(
                _('Error'),
                _('The pre-packing list has pack integrity issues, lines:\n - %s\nClick on Check Integrity button to display details.') % ("\n -".join(['#%d'%x.line_number for x in move]))
            )

        ppl_processor = self.pool.get('ppl.processor')
        picking = self.browse(cr, uid, ids[0], fields_to_fetch=['move_lines', 'address_id'], context=context)
        if picking.address_id and picking.address_id.active is False:  # Check the Delivery Address
            addr_name = self.pool.get('res.partner.address').name_get(cr, uid, [picking.address_id.id])[0][1]
            raise osv.except_osv(
                _('Error'),
                _('The Pre-Packing List is using a deactivated Delivery Address (%s). Please select another one to be able to process.')
                % (addr_name))
        rounding_issues = []
        for move in picking.move_lines:
            if move.product_id and move.product_id.state.code == 'forbidden':  # Check constraints on lines
                check_vals = {'location_dest_id': move.location_dest_id.id, 'move': move}
                self.pool.get('product.product')._get_restriction_error(cr, uid, [move.product_id.id], check_vals, context=context)

            if move.state == 'done':
                continue
            if not ppl_processor._check_rounding(cr, uid, move.product_uom, move.num_of_packs, move.product_qty, context=context):
                rounding_issues.append(move.line_number)

        if rounding_issues:
            rounding_issues.sort()
            wiz_check_ppl_id = self.pool.get('check.ppl.integrity').create(cr, uid, {
                'picking_id': ids[0],
                'line_number_with_issue': ', '.join([str(x) for x in rounding_issues]),
            }, context=context)
            return {
                'name': _("PPL integrity"),
                'type': 'ir.actions.act_window',
                'res_model': 'check.ppl.integrity',
                'target': 'new',
                'res_id': [wiz_check_ppl_id],
                'view_mode': 'form',
                'view_type': 'form',
                'context': context,
            }

        return self.ppl_step2_run_wiz(cr, uid, ids, context)

    def ppl_step2_run_wiz(self, cr, uid, ids, context=None):

        family_obj = self.pool.get('ppl.family.processor')
        ppl_processor = self.pool.get('ppl.processor')

        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        picking = self.browse(cr, uid, ids[0], context=context)
        if picking.state != 'assigned':
            raise osv.except_osv(
                _('Error'),
                _('The pre-packing list is not in \'Available\' state. Please check this and re-try')
            )

        # TODO : refresh saved as draft
        existing = ppl_processor.search(cr, uid, [('picking_id', '=', ids[0]), ('draft_step2', '=', True)], limit=1, context=context)
        existing_data = {}
        if existing:
            wizard_id = existing[0]
            for wiz in ppl_processor.browse(cr, uid, existing):
                for fam in wiz.family_ids:
                    key='f%st%s' % (fam.from_pack, fam.to_pack)
                    existing_data[key] = {'pack_type': fam.pack_type and fam.pack_type.id or False, 'length': fam.length, 'width': fam.width, 'height': fam.height, 'weight': fam.weight, 'id': fam.id}
        else:
            wizard_id = ppl_processor.create(cr, uid, {'picking_id': ids[0]}, context=context)

        families_data = {}

        for line in picking.move_lines:
            if line.state == 'done':
                continue
            key = 'f%st%s' % (line.from_pack, line.to_pack)
            if key not in families_data:
                families_data[key] =  {
                    'wizard_id': wizard_id,
                    'move_ids': [(6, 0, [])],
                    'from_pack': line.from_pack,
                    'to_pack': line.to_pack,
                    'pack_type': line.pack_type.id,
                    'length': line.length,
                    'width': line.width,
                    'height': line.height,
                    'weight': line.weight,
                    'parcel_ids': line.parcel_ids,
                }

                if existing_data.get(key):
                    families_data[key].update(existing_data[key])
                    del existing_data[key]

            families_data[key]['move_ids'][0][2].append(line.id)

        for family_data in sorted(families_data.values(), key=lambda x: x.get('from_pack') or 0):
            if 'id' in family_data:
                fam_id = family_data['id']
                del family_data['id']
                family_obj.write(cr, uid, fam_id, family_data)
            else:
                family_obj.create(cr, uid, family_data)

        if existing_data:
            family_obj.unlink(cr, uid, [x['id'] for x in list(existing_data.values())], context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step2_form_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ppl.processor',
            'res_id': wizard_id,
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def do_ppl_step2_bg(self, cr, uid, wizard_ids, context=None):
        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids, = [wizard_ids]

        proc = self.pool.get('ppl.processor').browse(cr, uid, wizard_ids, fields_to_fetch=['picking_id'], context=context)

        nb_lines = self.pool.get('ppl.family.processor').search(cr, uid, [('wizard_id', 'in', wizard_ids)], count=True)
        # if from quick flow: attach progress to Picking Ticket
        if context.get('from_quick_flow'):
            main_object_id = context['from_quick_flow']
        else:
            main_object_id = proc[0].picking_id.id
        return self.pool.get('job.in_progress')._prepare_run_bg_job(cr, uid, wizard_ids, 'stock.picking', self.do_ppl_step2, nb_lines, _('Validate PPL'), main_object_id=main_object_id, return_success={'type': 'ir.actions.act_window_close'}, context=context)


    def do_ppl_step2(self, cr, uid, wizard_ids, context=None, job_id=False):
        '''
        Create the Pack families and the shipment

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        '''
        # Objects
        proc_obj = self.pool.get('ppl.processor')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")

        date_tools = self.pool.get('date.tools')
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)
        today = time.strftime(db_datetime_format)


        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process '),
            )

        pickings = {}
        shipment_id = False
        shipment_name = False
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            pickings.setdefault(picking.id, picking.name)

            if picking.state != 'assigned':
                raise osv.except_osv(
                    _('Error'),
                    _('The pre-packing list is not in \'Available\' state. Please check this and re-try')
                )

            # Create the new packing
            # Copy to 'packing' stock.picking
            # Draft shipment is automatically created or updated if a shipment already exists
            pack_number = picking.name.split("/")[1]

            pack_values = {
                'name': 'PACK/' + pack_number,
                'subtype': 'packing',
                'previous_step_id': picking.id,
                'backorder_id': False,
                'shipment_id': False,
                'origin': picking.origin,
                'move_lines': [],
                'date': today,  # Set date as today for the new PACK object
            }

            # Change the context for copy
            context.update({
                'keep_prodlot': True,
                'keepLineNumber': True,
                'allow_copy': True,
            })
            context['offline_synchronization'] = False
            # Create the packing with pack_values and the updated context
            new_packing_id = self.copy(cr, uid, picking.id, pack_values, context=context)
            if picking.claim:
                self.write(cr, uid, new_packing_id, ({'claim': True}), context=context)

            obj = self.browse(cr, uid, new_packing_id, fields_to_fetch=['shipment_id', 'name'], context=context)
            if obj and obj.shipment_id and obj.shipment_id.id:
                shipment_id = obj.shipment_id.id
                shipment_name = obj.shipment_id.name
            else:
                raise Exception("For some reason, there is no shipment created for the Packing list: " + obj.name)

            # Reset context values
            context.update({
                'keep_prodlot': False,
                'keepLineNumber': False,
                'allow_copy': False,
            })

            # Set default values for packing move creation
            pack_move_data = {
                'picking_id': new_packing_id,
                'state': 'assigned',
                'location_id': picking.warehouse_id.lot_dispatch_id.id,
                'location_dest_id': picking.warehouse_id.lot_distribution_id.id,
                'from_pack': False,
                'to_pack': False,
                'parcel_ids': False,
            }

            nb_processed = 0
            # Create the stock moves in the packing
            for family in wizard.family_ids:
                move_to_write = [x.id for x in family.move_ids]
                if move_to_write:
                    ship_line_id = self.pool.get('pack.family.memory').create(cr, uid,
                                                                              {
                                                                                  'from_pack': family.from_pack,
                                                                                  'to_pack': family.to_pack,
                                                                                  'parcel_ids': family.parcel_ids,
                                                                                  'selected_number': family.to_pack - family.from_pack + 1,
                                                                                  'pack_type': family.pack_type and family.pack_type.id or False,
                                                                                  'length': family.length,
                                                                                  'width': family.width,
                                                                                  'height': family.height,
                                                                                  'weight': family.weight,
                                                                                  'volume_set': family.length * family.height * family.width > 0,
                                                                                  'weight_set': family.weight > 0,
                                                                                  'sale_order_id': picking.sale_id and picking.sale_id.id or False,
                                                                                  'ppl_id': picking.id,
                                                                                  'draft_packing_id': new_packing_id,
                                                                                  'location_id': picking.warehouse_id.lot_dispatch_id.id,
                                                                                  'location_dest_id': picking.warehouse_id.lot_distribution_id.id,
                                                                                  'shipment_id': shipment_id,
                                                                                  'state': 'assigned',
                                                                              }, context=context)
                    pack_move_data['shipment_line_id'] = ship_line_id

                # Create a move line in the Packing
                context.update({
                    'keepLineNumber': True,
                    'non_stock_noupdate': True,
                })
                for move_to_copy in move_to_write:
                    move_obj.copy(cr, uid, move_to_copy, pack_move_data, context=context)
                context.update({
                    'keepLineNumber': False,
                    'non_stock_noupdate': False,
                })

                nb_processed += 1
                if job_id and nb_processed % 2:
                    self.pool.get('job.in_progress').write(cr, uid, [job_id], {'nb_processed': nb_processed})


            # Trigger standard workflow on PPL
            self.action_move(cr, uid, [picking.id])
            wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)



        for pid, pname in pickings.items():
            self.infolog(cr, uid, "Products of Pre-Packing List id:%s (%s) have been packed in Shipment id:%s (%s)" % (
                pid, pname, shipment_id, shipment_name,
            ))

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_shipment', ['form', 'tree'], context=context)
        res['res_id'] = shipment_id
        return res


    def _manual_create_rw_messages(self, cr, uid, context=None):
        return

    @check_cp_rw
    def ppl_return(self, cr, uid, ids, context=None):
        """
        Open wizard to return products from a PPL
        """
        # Objects
        proc_obj = self.pool.get('return.ppl.processor')

        if isinstance(ids, int):
            ids = [ids]

        data = self.read(cr, uid, ids[0], ['state', 'name', 'type', 'subtype'], context=context)
        if data['type'] != 'out' or data['subtype'] != 'ppl':
            raise osv.except_osv(
                _('Error'),
                _('The object %s is not a pre-packing list. Please check this and re-try.') % (data['name'])
            )

        processor_id = proc_obj.create(cr, uid, {'picking_id': ids[0]}, context=context)
        proc_obj.create_lines(cr, uid, processor_id, context=context)

        return {
            'name': _('Return products'),
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'res_id': processor_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }


    def do_return_ppl(self, cr, uid, wizard_ids, context=None):
        """
        Returns products from PPL to the draft picking ticket

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        """
        # Objects
        proc_obj = self.pool.get('return.ppl.processor')
        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(wizard_ids, int):
            wizard_ids = [wizard_ids]

        counter = 0
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            draft_picking_id = picking.previous_step_id.backorder_id.id

            # get the linked "save as draft" ppl.processor wizard if has:
            ppl_processor_wiz = self.pool.get('ppl.processor').search(cr, uid, [
                ('picking_id', '=', picking.id),
                ('draft_step2', '=', True),
            ], context=context)
            if ppl_processor_wiz:
                ppl_processor_wiz = self.pool.get('ppl.processor').browse(cr, uid, ppl_processor_wiz[0], context=context)

            move_to_unlink = set()
            for line in wizard.move_ids:
                return_qty = line.quantity

                if not return_qty:
                    continue

                if line.move_id.state != 'assigned':
                    raise osv.except_osv(
                        _('Error'),
                        _('Line %s :: The move is not \'Available\'. Check the state of the stock move and re-try.') % line.move_id.line_number,
                    )

                counter = counter + 1

                initial_qty = max(line.move_id.product_qty - return_qty, 0)

                move_values = {
                    'product_qty': initial_qty,
                    'date_expected': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }

                if not initial_qty:
                    """
                    If all products of the move are sent back to draft picking ticket,
                    the move state is done
                    """
                    move_values['state'] = 'done'

                if initial_qty:
                    move_obj.write(cr, uid, [line.move_id.id], move_values, context=context)
                else:
                    move_to_unlink.add(line.move_id.id)

                """
                Create a back move with the quantity to return to the good location.
                Good location is stored in the 'initial_location' field
                """
                return_values = {
                    'product_qty': return_qty,
                    'location_dest_id': line.move_id.initial_location.id,
                    'state': 'done',
                    'ppl_returned_ok': True,
                }
                context['keepLineNumber'] = True
                move_obj.copy(cr, uid, line.move_id.id, return_values, context=context)
                context['keepLineNumber'] = False
                # Increase the draft move with the returned quantity : must broswe the record again to invalidate cache
                draft_move = move_obj.browse(cr, uid, line.move_id.backmove_id.id, fields_to_fetch=['product_qty', 'qty_processed'], context=context)
                draft_move_qty = draft_move.product_qty + return_qty
                qty_processed = max(draft_move.qty_processed - return_qty, 0)
                move_obj.write(cr, uid, [draft_move.id], {'product_qty': draft_move_qty, 'qty_to_process': draft_move_qty, 'qty_processed': qty_processed}, context=context)

            if move_to_unlink:
                context.update({'call_unlink': True})
                move_obj.unlink(cr, uid, list(move_to_unlink), context=context)
                context.pop('call_unlink')

            # Log message for PPL
            ppl_view = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_ppl_form')[1]
            context['view_id'] = ppl_view
            log_message = _('Products from Pre-Packing List (%s) have been returned to stock.') % (picking.name,)
            self.log(cr, uid, picking.id, log_message, action_xmlid='msf_outgoing.action_ppl')
            self.infolog(cr, uid, "Products from Pre-Packing List id:%s (%s) have been returned to stock." % (
                picking.id, picking.name,
            ))

            # Log message for draft picking ticket
            log_message = _('The corresponding Draft Picking Ticket (%s) has been updated.') % (picking.previous_step_id.backorder_id.name,)
            self.log(cr, uid, draft_picking_id, log_message, action_xmlid='msf_outgoing.action_picking_ticket')

            # If all moves are done or canceled, the PPL is canceled
            cancel_ppl = move_obj.search(cr, uid, [('picking_id', '=', picking.id), ('state', '!=', 'assigned')], count=True, context=context)

            if cancel_ppl:
                """
                we dont want the back move (done) to be canceled - so we dont use the original cancel workflow state because
                action_cancel() from stock_picking would be called, this would cancel the done stock_moves
                instead we move to the new return_cancel workflow state which simply set the stock_picking state to 'cancel'
                TODO THIS DOESNT WORK - still done state - replace with trigger for now
                wf_service.trg_validate(uid, 'stock.picking', picking.id, 'return_cancel', cr)
                """
                wf_service.trg_write(uid, 'stock.picking', picking.id, cr)

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')
        view_id = view_id and view_id[1] or False
        context['picking_type'] = 'picking_ticket'

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_picking_ticket', ['form', 'tree'], context=context)
        res['res_id'] = draft_picking_id
        return res

    def _manual_create_rw_picking_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        return

    def _create_sync_message_for_field_order(self, cr, uid, picking, context=None):
        fo_obj = self.pool.get('sale.order')
        if picking.sale_id:
            return_info = {}
            if picking.sale_id.original_so_id_sale_order:
                fo_obj._manual_create_sync_picking_message(cr, uid, picking.sale_id.original_so_id_sale_order.id, return_info, 'purchase.order.normal_fo_create_po', context=context)
            else:
                fo_obj._manual_create_sync_picking_message(cr, uid, picking.sale_id.id, return_info, 'purchase.order.normal_fo_create_po', context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        override cancel state action from the workflow

        - depending on the subtype and state of the stock.picking object
          the behavior will be different

        Cancel button is active for the picking object:
        - subtype: 'picking'
        Cancel button is active for the shipment object:
        - subtype: 'packing'

        state is not taken into account as picking is canceled before
        '''
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        obj_data = self.pool.get('ir.model.data')
        wf_service = netsvc.LocalService("workflow")

        # check the state of the picking
        for picking in self.browse(cr, uid, ids, context=context):
            # update PO line if needed:
            # e.g.: 300 qty => received 250, then cancel 50 => need to update PO line at cancelation
            if picking.type == 'in' and picking.purchase_id:
                for stock_move in picking.move_lines:
                    if stock_move.purchase_line_id:
                        if picking.purchase_id.order_type != 'direct':
                            if not move_obj.search_exist(cr, uid, [('purchase_line_id', '=', stock_move.purchase_line_id.id), ('state', 'not in', ['cancel', 'cancel_r', 'done'])], context=context):
                                # all in lines processed for this po line
                                wf_service.trg_validate(uid, 'purchase.order.line', stock_move.purchase_line_id.id, 'done', cr)
                        elif abs(stock_move.purchase_line_id.in_qty_remaining) < 0.001:
                            if move_obj.search_exist(cr, uid, [('purchase_line_id', '=', stock_move.purchase_line_id.id), ('id', '!=',  stock_move.id), ('state', '=', 'done')], context=context):
                                wf_service.trg_validate(uid, 'purchase.order.line', stock_move.purchase_line_id.id, 'done', cr)

            # if draft and shipment is in progress, we cannot cancel
            if picking.subtype == 'picking' and picking.state in ('draft',):
                if self.has_picking_ticket_in_progress(cr, uid, [picking.id], context=context)[picking.id]:
                    raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try to cancel again.'))
                self._create_sync_message_for_field_order(cr, uid, picking, context=context)
                return super(stock_picking, self).action_cancel(cr, uid, ids, context=context)
            # if not draft or qty does not match, the shipping is already in progress
            if picking.subtype == 'picking' and picking.state in ('done',):
                raise osv.except_osv(_('Warning !'), _('The shipment process is completed and cannot be canceled!'))


        for picking in self.browse(cr, uid, ids, context=context):

            if picking.subtype == 'picking':
                # for each picking
                # get the draft picking
                draft_picking_id = picking.backorder_id.id

                # for each move from picking ticket - could be split moves
                for move in picking.move_lines:
                    # find the corresponding move in draft
                    draft_move = move.backmove_id
                    if draft_move:
                        # increase the draft move with the move quantity
                        mainpick_move = move_obj.read(cr, uid, [draft_move.id], ['product_qty', 'qty_processed'], context=context)[0]
                        initial_qty = mainpick_move['product_qty']
                        initial_qty += move.product_qty
                        move_obj.write(cr, uid, [draft_move.id], {'product_qty': initial_qty, 'qty_processed': mainpick_move['qty_processed'] and mainpick_move['qty_processed'] - move.product_qty or 0, 'qty_to_process': initial_qty}, context=context)

                        # log the increase action
                        # TODO refactoring needed
                        obj_data = self.pool.get('ir.model.data')
                        res = obj_data.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1]
                        context.update({'view_id': res, 'picking_type': 'picking_ticket'})
                        self.log(cr, uid, draft_picking_id, _("The corresponding Draft Picking Ticket (%s) has been updated.") % (picking.backorder_id.name,), context=context)
                        self.infolog(cr, uid, "The Validated Picking Ticket id:%s (%s) has been canceled. The corresponding Draft Picking Ticket id:%s (%s) has been updated." % (
                            picking.id, picking.name, picking.backorder_id.id, picking.backorder_id.name,
                        ))

            if picking.subtype == 'packing':

                # for each move from the packing
                for move in picking.move_lines:
                    # corresponding draft move from draft **packing** object
                    draft_move_id = move.backmove_packing_id.id
                    # check the to_pack of draft move
                    # if equal to draft to_pack = move from_pack - 1 (as we always take the pack with the highest number available)
                    # we can increase the qty and update draft to_pack
                    # otherwise we copy the draft packing move with updated quantity and from/to
                    # we always create a new move
                    draft_read = move_obj.read(cr, uid, [draft_move_id], ['product_qty', 'to_pack'], context=context)[0]
                    draft_to_pack = draft_read['to_pack']
                    if draft_to_pack + 1 == move.from_pack and False:  # DEACTIVATED
                        # updated quantity
                        draft_qty = draft_read['product_qty'] + move.product_qty
                        # update the draft move
                        move_obj.write(cr, uid, [draft_move_id], {'product_qty': draft_qty, 'to_pack': move.to_pack}, context=context)
                    else:
                        # copy draft move (to be sure not to miss original info) with move qty and from/to
                        move_obj.copy(cr, uid, draft_move_id, {'product_qty': move.product_qty,
                                                               'from_pack': move.from_pack,
                                                               'to_pack': move.to_pack,
                                                               'state': 'assigned'}, context=context)

        super(stock_picking, self).action_cancel(cr, uid, ids, context=context)
        return True

    def import_pick(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No PICK selected'))

        wiz_id = self.pool.get('wizard.pick.import').create(cr, uid, {'picking_id': ids[0]}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.pick.import',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def ppl_pack_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning'), _('Please select at least one line.'))

        wiz_id = self.pool.get('ppl.set_pack_on_lines').create(cr, uid, {'picking_id': ids[0], 'from_pack': 1, 'to_pack': 1}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ppl.set_pack_on_lines',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '190px',
            'width': '220px',
        }


stock_picking()


class warning_pick_partial_process_sign_wizard(osv.osv_memory):
    _name = 'warning.pick.partial.process.sign.wizard'
    _description = 'The Picking Ticket is partially processed and signed'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Picking id', readonly=True),
    }

    def continue_validation(self, cr, uid, ids, context=None):
        '''
        Launch the do_validate_picking_bg method
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pick_obj = self.pool.get('stock.picking')
        for wiz in self.browse(cr, uid, ids, context=context):
            context['partial_process_sign'] = True
            pick_obj.do_validate_picking_bg(cr, uid, [wiz.picking_id.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def cancel(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


warning_pick_partial_process_sign_wizard()


class wizard(osv.osv):
    '''
    class offering open_wizard method for wizard control
    '''
    _name = 'wizard'

    def open_wizard(self, cr, uid, ids, name=False, model=False, step='default', w_type='create', context=None):
        '''
        WARNING : IDS CORRESPOND TO ***MAIN OBJECT IDS*** (picking for example) take care when calling the method from wizards
        return the newly created wizard's id
        name, model, step are mandatory only for type 'create'
        '''
        if context is None:
            context = {}

        if w_type == 'create':
            assert name, 'type "create" and no name defined'
            assert model, 'type "create" and no model defined'
            assert step, 'type "create" and no step defined'
            vals = {}

            # create the memory object - passing the picking id to it through context
            wizard_id = self.pool.get(model).create(
                cr, uid, vals, context=dict(context,
                                            active_ids=ids,
                                            model=model,
                                            step=step,
                                            back_model=context.get('model', False),
                                            back_wizard_ids=context.get('wizard_ids', False),
                                            back_wizard_name=context.get('wizard_name', False),
                                            back_step=context.get('step', False),
                                            wizard_name=name))

        elif w_type == 'back':
            # open the previous wizard
            assert context['back_wizard_ids'], 'no back_wizard_ids defined'
            wizard_id = context['back_wizard_ids'][0]
            assert context['back_wizard_name'], 'no back_wizard_name defined'
            name = context['back_wizard_name']
            assert context['back_model'], 'no back_model defined'
            model = context['back_model']
            assert context['back_step'], 'no back_step defined'
            step = context['back_step']

        elif w_type == 'update':
            # refresh the same wizard
            assert context['wizard_ids'], 'no wizard_ids defined'
            wizard_id = context['wizard_ids'][0]
            assert context['wizard_name'], 'no wizard_name defined'
            name = context['wizard_name']
            assert context['model'], 'no model defined'
            model = context['model']
            assert context['step'], 'no step defined'
            step = context['step']

        # call action to wizard view
        return {
            'name': name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            model=model,
                            step=step,
                            back_model=context.get('model', False),
                            back_wizard_ids=context.get('wizard_ids', False),
                            back_wizard_name=context.get('wizard_name', False),
                            back_step=context.get('step', False),
                            wizard_name=name)
        }

wizard()

class product_product(osv.osv):
    _inherit = 'product.product'

    _columns = {
        'prodlot_ids': fields.one2many('stock.production.lot', 'product_id', string='Batch Numbers',),
    }

product_product()




class pack_family_memory_old(osv.osv):
    _name = 'pack.family.memory.old'
    _auto = False
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'pack_family_memory')
        tools.sql.drop_view_if_exists(cr, 'pack_family_memory_old')
        cr.execute('''create or replace view pack_family_memory_old as (
            select
                min(m.id) as id,
                p.shipment_id as shipment_id,
                from_pack as from_pack,
                to_pack as to_pack,
                m.parcel_ids as parcel_ids,
                array_agg(m.id) as move_lines,
                min(packing_list) as packing_list,
                bool_and(m.volume_set) as volume_set,
                bool_and(m.weight_set) as weight_set,
                case when to_pack=0 then 0 else to_pack-min(from_pack)+1 end as num_of_packs,
                p.sale_id as sale_order_id,
                case when p.subtype = 'ppl' then p.id else p.previous_step_id end as ppl_id,
                min(m.length) as length,
                min(m.width) as width,
                min(m.height) as height,
                min(m.weight) as weight,
                case when bool_and(m.not_shipped) = 't' then 'returned' else min(m.state) end as state,
                min(m.location_id) as location_id,
                min(m.location_dest_id) as location_dest_id,
                min(m.pack_type) as pack_type,
                min(m.selected_number) as selected_number,
                p.id as draft_packing_id,
                p.details as description_ppl,
                '_name'::varchar(5) as name,
                min(pl.currency_id) as currency_id,
                sum(sol.price_unit * m.product_qty) as total_amount,
                bool_and(m.not_shipped) as not_shipped,
                ''::varchar(1) as comment,
                p.flow_type = 'quick' as quick_flow,
                p.state as pack_state,
                p.description_ppl as parcel_comment
            from stock_picking p
            inner join stock_move m on m.picking_id = p.id and m.state != 'cancel' and m.product_qty > 0
            left join sale_order so on so.id = p.sale_id
            left join sale_order_line sol on sol.id = m.sale_line_id
            left join product_pricelist pl on pl.id = so.pricelist_id
            where p.shipment_id is not null
            group by p.shipment_id, p.details, p.description_ppl, from_pack, to_pack, sale_id, p.subtype, p.id, p.previous_step_id, m.not_shipped, parcel_ids
    )
    ''')
    _columns = {
    }
pack_family_memory_old()

class pack_family_memory(osv.osv):
    '''
    dynamic memory object for pack families
    '''
    _name = 'pack.family.memory'
    _order = 'sale_order_id, ppl_id, from_pack, id'


    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        if not ids:
            return {}
        result = {}

        for _id in ids:
            result[_id] = {
                'amount': 0.0,
                'total_weight': 0.0,
                'total_volume': 0.0,
                'num_of_packs': 0,
                'fake_state': False,
                'pack_state': False,
                'currency_id': False,
                'total_amount': 0,
                'parcel_ids_error': False,
            }

        cr.execute('''
            select p.id, pl.currency_id, cur.name, sum(sol.price_unit * m.product_qty) from
                pack_family_memory p, sale_order so, product_pricelist pl, stock_move m, sale_order_line sol, res_currency cur
            where
                p.sale_order_id = so.id and
                pl.id = so.pricelist_id and
                m.shipment_line_id = p.id and
                sol.id = m.sale_line_id and
                cur.id = pl.currency_id and
                p.id in %s
            group by
                p.id, pl.currency_id, cur.name
            ''', (tuple(ids), ))
        for x in cr.fetchall():
            result[x[0]]['currency_id'] = (x[1], x[2])
            result[x[0]]['total_amount'] = x[3]

        for pf_memory in self.browse(cr, uid, ids, fields_to_fetch=['from_pack', 'to_pack', 'parcel_ids', 'selected_parcel_ids', 'selected_number',
                                                                    'weight', 'length', 'width', 'height', 'state', 'shipment_id'],
                                     context=context):
            values = result[pf_memory['id']]

            num_of_packs = 0
            if pf_memory['to_pack']:
                num_of_packs = pf_memory['to_pack'] - pf_memory['from_pack'] + 1
                values['num_of_packs'] = num_of_packs
            if num_of_packs:
                values['amount'] = values['total_amount'] / num_of_packs
            values['total_weight'] = pf_memory['weight'] * num_of_packs
            values['total_volume'] = round((pf_memory['length'] * pf_memory['width'] * pf_memory['height'] * num_of_packs) / 1000.0, 4)
            values['fake_state'] = pf_memory['state']
            values['pack_state'] = pf_memory.shipment_id.state
            if pf_memory['selected_number'] and pf_memory['parcel_ids']:
                nb_parcel = len(pf_memory['parcel_ids'].split(','))
                if not pf_memory['selected_parcel_ids']:
                    nb_parcel_selected = 0
                else:
                    nb_parcel_selected = len(pf_memory['selected_parcel_ids'].split(','))
                if pf_memory['selected_number'] != nb_parcel and pf_memory['selected_number'] != nb_parcel_selected:
                    values['parcel_ids_error'] = True

        return result

    _columns = {
        'name': fields.char(string='Reference', size=1024),
        'shipment_id': fields.many2one('shipment', string='Shipment'),
        'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
        'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
        'ppl_id': fields.many2one('stock.picking', string="PPL Ref"),
        'from_pack': fields.integer(string='From p.'),
        'to_pack': fields.integer(string='To p.'),
        'parcel_ids': fields.text('Parcel Ids'),
        'selected_parcel_ids': fields.text('Selected Parcel Ids'),
        'parcel_comment': fields.char(string='Parcel Comment', size=256),
        'pack_type': fields.many2one('pack.type', string='Pack Type'),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        'move_lines': fields.one2many('stock.move', 'shipment_line_id',  'Stock Moves'),
        'packing_list': fields.char('Supplier Packing List', size=30),
        'fake_state': fields.function(_vals_get, method=True, type='char', String='Fake state', multi='get_vals'),
        'state': fields.selection(selection=[
            ('draft', 'Draft'),
            ('assigned', 'Available'),
            ('returned', 'Returned'),
            ('cancel', 'Cancelled'),
            ('done', 'Closed'), ], string='State'),
        'pack_state': fields.function(_vals_get, method=True, type='char', string='Pack State', multi='get_vals'),
        'location_id': fields.many2one('stock.location', string='Src Loc.'),
        'location_dest_id': fields.many2one('stock.location', string='Dest. Loc.'),
        'total_amount': fields.function(_vals_get, method=True, type=' float', string='Total Amount',  multi='get_vals'),
        'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', multi='get_vals'),
        'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals'),
        'num_of_packs': fields.function(_vals_get, method=True, type='integer', string='Nb. Parcels',  multi='get_vals'),
        'selected_number': fields.integer('Nb. Parcels to Ship'),
        'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals'),
        'total_volume': fields.function(_vals_get, method=True, type='float', string='Total Volume[dm³]', multi='get_vals'),
        'description_ppl': fields.char('Details', size=256),
        'not_shipped': fields.boolean(string='Not shipped'),
        'comment': fields.char(string='Comment', size=1024),
        'volume_set': fields.boolean('Volume set at PPL'),
        'weight_set': fields.boolean('Weight set at PPL'),
        'quick_flow': fields.boolean('From quick flow'),
        'parcel_ids_error': fields.function(_vals_get, method=True, type='boolean', string='Parcel Error', multi='get_vals'),
    }

    _defaults = {
        'shipment_id': False,
        'draft_packing_id': False,
    }

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, int):
            ids = [ids]

        if 'total_weight' in vals or 'total_volume' in vals:
            for ship_line in self.read(cr, uid, ids, ['num_of_packs'], context=context):
                to_write = vals.copy()
                if ship_line['num_of_packs']:
                    if 'total_weight' in vals:
                        try:
                            to_write['total_weight'] = float(vals['total_weight']) or 0
                        except Exception:
                            raise osv.except_osv(_('Error'), _('The Total Weight[kg] must be a number'))

                        to_write['total_weight'] = vals['total_weight'] or 0
                        to_write['weight'] =  to_write['total_weight'] / ship_line['num_of_packs']
                    if 'total_volume' in vals:
                        try:
                            to_write['total_volume'] = float(vals['total_volume'])
                        except Exception:
                            raise osv.except_osv(_('Error'), _('The Total Volume[dm³] must be a number'))
                        size = (to_write['total_volume']**(1.0/3))*10. or 0
                        to_write['length'] = size / ship_line['num_of_packs']
                        to_write['width'] = size
                        to_write['height'] = size
                super(pack_family_memory, self).write(cr, uid, ship_line['id'], to_write, context=context)
        else:
            super(pack_family_memory, self).write(cr, uid, ids, vals, context=context)

        return True

    def change_description(self, cr, uid, ids, context=None):

        if isinstance(ids, int):
            ids = [ids]

        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_change_desc_wizard')
        pack_obj = self.read(cr, uid, ids, ['draft_packing_id'], context=context)
        for pack in pack_obj:
            res_id = pack['draft_packing_id'][0]
            return {
                'name': _('Change parcel comment'),
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [res and res[1] or False],
                'res_model': 'stock.picking',
                'context': "{}",
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id': res_id or False,
            }
        return {}

    def change_selected_number(self, cr, uid, ids, selected_number, context=None):
        if not selected_number:
            return {}

        cr.execute('''select m.id
            from
                pack_family_memory p,
                stock_move m,
                product_uom u
            where
                m.shipment_line_id = p.id and
                m.product_uom = u.id and
                u.rounding=1 and
                (product_qty / (p.to_pack-p.from_pack+1)) %% 1 != 0 and
                p.to_pack-p.from_pack+1 != %s and
                p.id in %s
        ''', (selected_number, tuple(ids)))
        if cr.rowcount:
            return {
                'warning': {
                    'message': _('Warning, this range of packs contains one or more products with a decimal quantity per pack. All packs must be processed together')
                }
            }

        return {}

    def select_parcel_ids(self, cr, uid, ids, context=None):
        ship_line = self.read(cr, uid, ids[0], ['parcel_ids', 'selected_parcel_ids', 'selected_number'], context=context)
        if not ship_line['parcel_ids']:
            raise osv.except_osv(_('Error !'), _('Parcel list is not defined.'))
        wiz = self.pool.get('shipment.parcel.selection').create(cr, uid, {
            'shipment_line_id': ids[0],
            'parcel_number': ship_line['selected_number'],
            'selected_item_ids': ship_line['selected_parcel_ids'],
            'available_items_ids': ship_line['parcel_ids'],
        }, context=context)

        return {
            'name': _("Select Shipment Parcel Ids"),
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.parcel.selection',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': wiz,
            'target': 'new',
            'context': context,
        }


pack_family_memory()


class stock_reserved_products(osv.osv):
    _auto = False
    _name ='stock.reserved.products'
    _description = "Reserved Products"
    _order = 'location_id, hidden_product_code, picking_id desc'
    _columns = {
        'location_id': fields.many2one('stock.location', 'Location Stock'),
        'product_id': fields.many2one('product.product', 'Product'),
        'uom_id': fields.many2one('product.uom', 'UoM'),
        'product_code': fields.char('Product', size=256),
        'hidden_product_code': fields.char('Product', size=256),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch Number - Expiry Date', context={'with_expiry': True}),
        'picking_id': fields.char('Document', size=256),
        'product_qty': fields.float('Qty', related_uom='uom_id', group_operator='no_group'),
    }

    def init(self, cr):
        drop_view_if_exists(cr, 'stock_reserved_products')
        cr.execute("""
        create or replace view stock_reserved_products as (
            select
                ('x'||md5(''||COALESCE(m.location_id,0)||COALESCE(m.product_id,0)||COALESCE(m.prodlot_id,0)||COALESCE(m.picking_id,0)))::bit(32)::int as id,
                m.location_id,
                m.product_id,
                m.prodlot_id,
                t.uom_id as uom_id,
                CASE WHEN ship.name IS NOT NULL THEN ship.name||' - '||pick.name ELSE pick.name END as picking_id,
                p.default_code as hidden_product_code,
                CASE WHEN GROUPING(m.location_id, m.product_id, p.default_code, m.picking_id, m.prodlot_id)=0 THEN  '' ELSE p.default_code END as product_code,
                sum(product_qty/m_uom.factor*p_uom.factor) as product_qty
            from
                stock_move m
                inner join product_product p on p.id = m.product_id
                inner join product_template t on t.id = p.product_tmpl_id
                inner join stock_picking pick on pick.id = m.picking_id
                left join shipment ship on ship.id = m.pick_shipment_id
                inner join product_uom m_uom on m_uom.id = m.product_uom
                inner join product_uom p_uom on p_uom.id = t.uom_id
            where
                m.state = 'assigned' and
                m.product_qty > 0 and
                m.type in ('internal', 'out')
            group by
                GROUPING SETS (m.location_id, (m.location_id, m.product_id, t.uom_id, p.default_code), (m.location_id, m.product_id, t.uom_id, p.default_code, m.picking_id, ship.name, pick.name, m.prodlot_id))
            having(GROUPING(m.location_id, m.product_id, p.default_code) = 0)
        )
        """)

stock_reserved_products()

class stock_move(osv.osv):
    _inherit = 'stock.move'
    _columns = {
        'shipment_line_id': fields.many2one('pack.family.memory', 'Shipment Line'),
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if 'shipment_line_id' not in default:
            default['shipment_line_id'] = False
        return super(stock_move, self).copy_data(cr, uid, id, default, context)

stock_move()
