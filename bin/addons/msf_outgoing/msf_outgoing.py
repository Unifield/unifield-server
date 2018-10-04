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
import decimal_precision as dp
import logging
import tools
import time
from os import path
from lxml import etree

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

    def default_get(self, cr, uid, fields_list, context=None):
        """
        Get the default locations
        """
        # Objects
        data_get = self.pool.get('ir.model.data').get_object_reference

        if context is None:
            context = {}

        res = super(stock_warehouse, self).default_get(cr, uid, fields_list, context=context)

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
        add_items = self.pool.get('shipment.additionalitems')
        pack_family_obj = self.pool.get('pack.family.memory')

        result = {}
        shipment_result = self.read(cr, uid, ids, ['pack_family_memory_ids',
                                                   'state', 'additional_items_ids'], context=context)
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
            }
            result[shipment['id']] = default_values
            current_result = result[shipment['id']]
            # gather the state from packing objects, all packing must have the same state for shipment
            # for draft shipment, we can have done packing and draft packing
            packing_ids = picking_obj.search(cr, uid, [('shipment_id', '=', shipment['id'])], order='NO_ORDER', context=context)
            # fields to check and get
            state = None
            first_shipment_packing_id = None
            backshipment_id = None
            # delivery validated
            delivery_validated = None
            # browse the corresponding packings
            for packing in picking_obj.browse(cr, uid, packing_ids,
                                              fields_to_fetch=[
                                                  'state',
                                                  'delivered',
                                                  'first_shipment_packing_id',
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

                # first_shipment_packing_id check - no check for the same reason
                first_shipment_packing_id = packing.first_shipment_packing_id.id

                # backshipment_id check
                if backshipment_id and backshipment_id != packing.backorder_id.shipment_id.id:
                    assert False, 'all packing of the shipment have not the same draft shipment correspondance - %s - %s' % (backshipment_id, packing.backorder_id.shipment_id.id)
                backshipment_id = packing.backorder_id and packing.backorder_id.shipment_id.id or False
            # if state is in ('draft', 'done', 'cancel'), the shipment keeps the same state
            if state not in ('draft', 'done', 'cancel',):
                if first_shipment_packing_id:
                    # second step of shipment : shipped
                    state = 'shipped'
                else:
                    state = 'packed'
            elif state == 'done':
                if delivery_validated:
                    # special state corresponding to delivery validated
                    state = 'delivered'

            current_result['state'] = state
            current_result['backshipment_id'] = backshipment_id

            pack_fam_ids = shipment['pack_family_memory_ids']
            for pack_fam_id in pack_fam_ids:
                memory_family = pack_family_dict[pack_fam_id]
                # taken only into account if not done (done means returned packs)
                if not memory_family['not_shipped'] and (shipment['state'] in ('delivered', 'done') or memory_family['state'] not in ('done',)):
                    # num of packs
                    num_of_packs = memory_family['num_of_packs']
                    current_result['num_of_packs'] += int(num_of_packs)
                    # total weight
                    total_weight = memory_family['total_weight']
                    current_result['total_weight'] += int(total_weight)
                    # total volume
                    total_volume = memory_family['total_volume']
                    current_result['total_volume'] += float(total_volume)
                    # total amount
                    total_amount = memory_family['total_amount']
                    current_result['total_amount'] += total_amount
                    # currency
                    currency_id = memory_family['currency_id'] or False
                    current_result['currency_id'] = currency_id
            if shipment['additional_items_ids']:
                item_list = add_items.read(cr, uid, shipment['additional_items_ids'],
                                           ['weight'], context=context)
                for item in item_list:
                    current_result['total_weight'] += item['weight']
        return result

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

    def _packs_search(self, cr, uid, obj, name, args, context=None):
        """
        Searches Ids of shipment
        """
        if context is None:
            context = {}

        cr.execute('''
        select t.id, sum(case when t.tp != 0 then  t.tp - t.fp + 1 else 0 end) as sumpack from (
            select p.shipment_id as id, min(to_pack) as tp, min(from_pack) as fp from stock_picking p
            left join stock_move m on m.picking_id = p.id and m.state != 'cancel' and m.product_qty > 0
            where p.shipment_id is not null
            group by p.shipment_id, to_pack, from_pack
        ) t
        group by t.id
        having sum(case when t.tp != 0 then  t.tp - t.fp + 1 else 0 end) %s %s
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

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        cmp_partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
        for ship in self.read(cr, uid, ids, ['partner_id2'], context=context):
            res[ship['id']] = ship['partner_id2'][0] == cmp_partner_id

        return res

    _columns = {'name': fields.char(string='Reference', size=1024),
                'date': fields.datetime(string='Creation Date'),
                'shipment_expected_date': fields.datetime(string='Expected Ship Date'),
                'shipment_actual_date': fields.datetime(string='Actual Ship Date', readonly=True,),
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
                'partner_id': fields.related('address_id', 'partner_id', type='many2one', relation='res.partner', string='Customer', store=True),
                'partner_id2': fields.many2one('res.partner', string='Customer', required=False),
                'partner_type': fields.related('partner_id', 'partner_type', type='selection', selection=PARTNER_TYPE, readonly=True),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', multi='get_vals',),
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
                'num_of_packs': fields.function(_vals_get, method=True, fnct_search=_packs_search, type='integer', string='Number of Packs', multi='get_vals_X',),  # interger fields.function need their own multi not to be considered as string
                'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals',),
                'total_volume': fields.function(_vals_get, method=True, type='float', string=u'Total Volume[dm³]', multi='get_vals',),
                'state': fields.function(_vals_get, method=True, type='selection', selection=[('draft', 'Draft'),
                                                                                              ('packed', 'Packed'),
                                                                                              ('shipped', 'Shipped'),
                                                                                              ('done', 'Closed'),
                                                                                              ('delivered', 'Delivered'),
                                                                                              ('cancel', 'Cancelled')], string='State', multi='get_vals',
                                         store={
                                             'stock.picking': (_get_shipment_ids, ['state', 'shipment_id', 'delivered'], 10),
                }),
                'backshipment_id': fields.function(_vals_get, method=True, type='many2one', relation='shipment', string='Draft Shipment', multi='get_vals',),
                # added by Quentin https://bazaar.launchpad.net/~unifield-team/unifield-wm/trunk/revision/426.20.14
                'parent_id': fields.many2one('shipment', string='Parent shipment'),
                'invoice_id': fields.many2one('account.invoice', string='Related invoice'),
                'additional_items_ids': fields.one2many('shipment.additionalitems', 'shipment_id', string='Additional Items'),
                'picking_ids': fields.one2many(
                    'stock.picking',
                    'shipment_id',
                    string='Associated Packing List',
    ),
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
    }

    def _get_sequence(self, cr, uid, context=None):
        ir_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'msf_outgoing', 'seq_shipment')
        return self.pool.get('ir.model.data').browse(cr, uid, ir_id).res_id

    def default_get(self, cr, uid, fields, context=None):
        """
        The 'Shipper' fields must be filled automatically with the
        default address of the current instance
        """
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')

        res = super(shipment, self).default_get(cr, uid, fields, context=context)

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

    @check_cp_rw
    def create_shipment(self, cr, uid, ids, context=None):
        """
        Open the wizard to process the shipment
        """
        # Objects
        ship_proc_obj = self.pool.get('shipment.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        for shipment in self.browse(cr, uid, ids, context=context):
            if not shipment.address_id.id:
                raise osv.except_osv(
                    _('Processing Error'),
                    _('Please fill the Address field on %s') % (shipment.name),
                )

            # search for an existing shipment saved as draft ... :
            wiz_ids = self.pool.get('shipment.processor').search(cr, uid, [('shipment_id', '=', shipment.id), ('draft', '=', True)], context=context)
            if wiz_ids:
                ship_proc_id = wiz_ids[0]
            else:
                # ... not found so create a new shipment processor wizard
                ship_proc_vals = {
                    'shipment_id': shipment.id,
                    'address_id': shipment.address_id.id,
                    'transport_type': shipment.transport_type,
                }
                ship_proc_id = ship_proc_obj.create(cr, uid, ship_proc_vals, context=context)
                ship_proc_obj.create_lines(cr, uid, ship_proc_id, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create shipment'),
            'res_model': ship_proc_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': ship_proc_id,
            'context': context,
        }

    def do_create_shipment(self, cr, uid, wizard_ids, context=None):
        """
        Create the shipment

        BE CAREFUL: the wizard_ids parameters is the IDs of the shipment.processor objects,
        not those of shipment objects
        """
        # Objects
        ship_proc_obj = self.pool.get('shipment.processor')
        picking_obj = self.pool.get('stock.picking')
        add_line_obj = self.pool.get('shipment.additionalitems')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = wizard_ids

        cp_fields = [
            'consignee_name', 'consignee_contact', 'consignee_address',
            'consignee_phone', 'consignee_email', 'consignee_other',
            'consignee_date', 'shipper_name', 'shipper_contact',
            'shipper_address', 'shipper_phone', 'shipper_email',
            'shipper_other', 'shipper_date', 'carrier_name',
            'carrier_address', 'carrier_phone', 'carrier_email',
            'carrier_other', 'carrier_date',
        ]

        for wizard in ship_proc_obj.browse(cr, uid, wizard_ids, context=context):
            shipment = wizard.shipment_id
            sequence = shipment.sequence_id

            shipment_number = sequence.get_id(code_or_id='id', context=context)
            shipment_name = '%s-%s' % (shipment.name, shipment_number)
            source_shipment_address_id = shipment.address_id.id if shipment.address_id else False

            if context.get('rw_shipment_name', False) and context.get('sync_message_execution', False):  # RW Sync - update the shipment name same as on RW instance
                shipment_name = context.get('rw_shipment_name')
                del context['rw_shipment_name']

            ship_val = {
                'name': shipment_name,
                'address_id': shipment.address_id.id,
                'partner_id': shipment.partner_id.id,
                'partner_id2': shipment.partner_id.id,
                'shipment_expected_date': shipment.shipment_expected_date,
                'shipment_actual_date': shipment.shipment_actual_date,
                'parent_id': shipment.id,
                'transport_type': shipment.transport_type,
                'carrier_id': shipment.carrier_id and shipment.carrier_id.id or False,
            }
            for cpf in cp_fields:
                ship_val[cpf] = shipment[cpf]

            context['create_shipment'] = True
            shipment_id = self.create(cr, uid, ship_val, context=context)
            del context['create_shipment']

            context['shipment_id'] = shipment_id
            if source_shipment_address_id:
                context['source_shipment_address_id'] = source_shipment_address_id

            for add_line in wizard.additional_line_ids:
                line_vals = {
                    'name': add_line.name,
                    'shipment_id': shipment_id,
                    'picking_id': False,
                    'quantity': add_line.quantity,
                    'uom': add_line.uom_id.id,
                    'comment': add_line.comment,
                    'volume': add_line.volume,
                    'weight': add_line.weight,
                }

                add_line_obj.create(cr, uid, line_vals, context=context)

            # US-803: point 9, add the ship description, then remove it from the context
            description_ppl = context.get('description_ppl', False)
            if context.get('description_ppl', False):
                del context['description_ppl']

            for family in wizard.family_ids:
                if not family.selected_number:  # UTP-1015 fix from Quentin
                    continue

                picking = family.draft_packing_id
                # Copy the picking object without moves
                # Creation of moves and update of initial in picking create method
                sequence = picking.sequence_id
                packing_number = sequence.get_id(code_or_id='id', context=context)

                # New packing data
                packing_data = {
                    'name': '%s-%s' % (picking.name, packing_number),
                    'backorder_id': picking.id,
                    'shipment_id': False,
                    'move_lines': [],
                    'description_ppl': description_ppl or picking.description_ppl,  # US-803: added the description
                }
                # Update context for copy
                context.update({
                    'keep_prodlot': True,
                    'keepLineNumber': True,
                    'allow_copy': True,
                    'non_stock_noupdate': True,
                    'shipment_proc_id': wizard.id,
                    'draft_packing_id': picking.id,
                })

                new_packing_id = picking_obj.copy(cr, uid, picking.id, packing_data, context=context)
                if picking_obj._get_usb_entity_type(cr, uid) == picking_obj.CENTRAL_PLATFORM:
                    picking_obj.write(cr, uid, [new_packing_id], {'already_replicated': True}, context=context)
                if picking.claim:
                    picking_obj.write(cr, uid, [new_packing_id], ({'claim': True}), context=context)

                # Reset context
                context.update({
                    'keep_prodlot': False,
                    'keepLineNumber': False,
                    'allow_copy': False,
                    'non_stock_noupdate': False,
                    'draft_packing_id': False,
                })

                # confirm the new packing
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', new_packing_id, 'button_confirm', cr)
                # simulate check assign button, as stock move must be available
                picking_obj.force_assign(cr, uid, [new_packing_id])

            # Log creation message
            message = _('The new Shipment id:%s (%s) has been created.')
            self.log(cr, uid, shipment.id, message % (shipment.id, shipment_name,))
            self.infolog(cr, uid, message % (shipment.id, shipment.name))
            # The shipment is automatically shipped, no more pack states in between.
            self.ship(cr, uid, [shipment_id], context=context)

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_shipment_form')
        view_id = view_id and view_id[1] or False

        # UF-2531: Run the creation of message if it's at RW at some important point
        usb_entity = picking_obj._get_usb_entity_type(cr, uid)
        if usb_entity == picking_obj.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            picking_obj._manual_create_rw_messages(cr, uid, context=context)

        # Remove unneeded data in context
        context.update({
            'partial_datas_ppl1': {},
            'partial_datas': {},
        })

        return {
            'name': _("Shipment"),
            'type': 'ir.actions.act_window',
            'res_model': 'shipment',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': shipment_id,
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

        if isinstance(ids, (int, long)):
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

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process'),
            )

        shipment_ids = []
        return_info = {}
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
                picking = family.draft_packing_id
                draft_picking = family.ppl_id and family.ppl_id.previous_step_id and family.ppl_id.previous_step_id.backorder_id or False

                # get the linked "save as draft" wizard if has:
                picking_processor_wiz = []
                if draft_picking:
                    picking_processor_wiz = self.pool.get('create.picking.processor').search(cr, uid, [
                        ('picking_id', '=', draft_picking.id),
                        ('draft', '=', True),
                    ], context=context)
                    if picking_processor_wiz:
                        picking_processor_wiz = self.pool.get('create.picking.processor').browse(cr, uid, picking_processor_wiz[0], context=context)

                # reset "save as draft" wizard if has:
                ship_processor_wiz = self.pool.get('shipment.processor').search(cr, uid, [
                    ('shipment_id', '=', shipment.id),
                    ('draft', '=', True),
                ], context=context)
                if ship_processor_wiz and family.selected_number:
                    ship_processor_wiz = self.pool.get('shipment.processor').browse(cr, uid, ship_processor_wiz[0], context=context)
                    related_draft_fam = False
                    for fam in ship_processor_wiz.family_ids:
                        # family = return
                        # fam = SaD
                        if family.ppl_id.id == fam.ppl_id.id and family.from_pack == fam.from_pack:
                            if related_draft_fam:
                                # if we enter there, it means that we have found 2 related draft family
                                # so it's wrong, we stop the searcing
                                related_draft_fam = False
                                break
                            else:
                                related_draft_fam = fam

                    if related_draft_fam:
                        if family.selected_number < related_draft_fam.selected_number: # partial
                            self.pool.get('shipment.family.processor').write(cr, uid, [related_draft_fam.id], {
                                'selected_number': related_draft_fam.selected_number - family.selected_number,
                                'to_pack': related_draft_fam.to_pack - family.selected_number,
                            }, context=context)
                        elif family.selected_number >= related_draft_fam.selected_number: # delete all line
                            self.pool.get('shipment.family.processor').unlink(cr, uid, [related_draft_fam.id], context=context)

                # UF-2531: Store some important info for the return pack messages
                return_info.setdefault(str(counter), {
                    'name': draft_picking.name,
                    'selected_number': family.selected_number,
                    'from_pack': family.from_pack,
                    'to_pack': family.to_pack,
                })
                counter = counter + 1

                # Update initial move
                if family.selected_number == int(family.num_of_packs):
                    # If al packs have been selected, from/to are set to 0
                    initial_from_pack = 0
                    initial_to_pack = 0
                else:
                    initial_from_pack = family.from_pack
                    initial_to_pack = family.to_pack - family.selected_number

                # Find the concerned stock moves
                move_ids = move_obj.search(cr, uid, [
                    ('picking_id', '=', picking.id),
                    ('from_pack', '=', family.from_pack),
                    ('to_pack', '=', family.to_pack)
                ], context=context)

                # Update the moves, decrease the quantities
                for move in move_obj.browse(cr, uid, move_ids, context=context):
                    if move.state != 'assigned':
                        raise osv.except_osv(
                            _('Error'),
                            _('All returned lines must be \'Available\'. Please check this and re-try.')
                        )
                    """
                    Stock moves are not canceled as for PPL return process
                    because this represents a draft packing, meaning some shipment could be canceled and
                    return to this stock move
                    """
                    return_qty = family.selected_number * move.qty_per_pack
                    move_vals = {
                        'product_qty': max(move.product_qty - return_qty, 0),
                        'from_pack': initial_from_pack,
                        'to_pack': initial_to_pack,
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
                        'from_pack': family.to_pack - family.selected_number + 1,
                        'to_pack': family.to_pack,
                        'state': 'done',
                        'not_shipped': True,  # BKLG-13: set the pack returned to stock also as not_shipped, for showing to view ship draft
                    }
                    context['non_stock_noupdate'] = True

                    move_obj.copy(cr, uid, move.id, cp_vals, context=context)

                    context['non_stock_noupdate'] = False

                    # Find the corresponding move in draft in the draft picking ticket
                    draft_move = move.backmove_id
                    # Increase the draft move with the move quantity
                    draft_initial_qty = move_obj.read(cr, uid, [draft_move.id], ['product_qty'], context=context)[0]['product_qty']
                    draft_initial_qty += return_qty
                    move_obj.write(cr, uid, [draft_move.id], {'product_qty': draft_initial_qty}, context=context)

                    # Update or create "save as draft" lines with returned qty:
                    if picking_processor_wiz:
                        save_as_draft_move = self.pool.get('create.picking.move.processor').search(cr, uid, [
                            ('wizard_id', '=', picking_processor_wiz.id),
                            ('move_id', '=', draft_move.id),
                        ], context=context)
                        if not save_as_draft_move:  # then create the SaD line:
                            move_data = self.pool.get('create.picking.move.processor')._get_line_data(cr, uid, wizard=picking_processor_wiz, move=draft_move, context=context)
                            move_data.update({'quantity': return_qty})
                            save_as_draft_move = self.pool.get('create.picking.move.processor').create(cr, uid, move_data, context=context)
                            save_as_draft_move = [save_as_draft_move]
                        else:  # update Sad line
                            for sad_move in self.pool.get('create.picking.move.processor').browse(cr, uid, save_as_draft_move, context=context):
                                self.pool.get('create.picking.move.processor').write(cr, uid, sad_move.id, {
                                    'ordered_quantity': sad_move.ordered_quantity + return_qty,
                                    'quantity': sad_move.quantity + return_qty,
                                }, context=context)

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

        # UF-2531: Create manually the message for the return pack of the ship
        if shipment and shipment.id:
            self._manual_create_rw_shipment_message(cr, uid, shipment.id, return_info, 'usb_shipment_return_packs_shipment_draft', context=context)

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_picking_ticket', ['form', 'tree'], context=context)
        res['res_id'] = draft_picking.id
        return res

    @check_cp_rw
    def return_packs_from_shipment(self, cr, uid, ids, context=None):
        """
        Open the wizard to return packs from draft shipment
        """
        # Objects
        proc_obj = self.pool.get('return.pack.shipment.processor')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
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

    def compute_sequences(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        compute corresponding sequences
        '''
        datas = kwargs['datas']
        from_pack = kwargs['from_pack']
        to_pack = kwargs['to_pack']
        # the list of tuple representing the packing movements from/to - default to sequence value
        stay = [(from_pack, to_pack)]
        # the list of tuple representing the draft packing movements from/to
        back_to_draft = []

        # loop the partials
        for partial in datas:
            return_from = partial['return_from']
            return_to = partial['return_to']
            # create the corresponding tuple
            back_to_draft.append((return_from, return_to))
            # stay list must be ordered
            sorted(stay)
            # find the corresponding tuple in the stay list
            for i in range(len(stay)):
                # the tuple are ordered
                seq = stay[i]
                if seq[1] >= return_to:
                    # this is the good tuple
                    # stay tuple creation logic
                    if return_from == seq[0]:
                        if return_to == seq[1]:
                            # all packs for this sequence are sent back - simply remove it
                            break
                        else:
                            # to+1-seq[1] in stay
                            stay.append((return_to + 1, seq[1]))
                            break

                    elif return_to == seq[1]:
                        # do not start at beginning, but same end
                        stay.append((seq[0], return_from - 1))
                        break

                    else:
                        # in the middle, two new tuple in stay
                        stay.append((seq[0], return_from - 1))
                        stay.append((return_to + 1, seq[1]))
                        break

            # old one is always removed
            stay.pop(i)

        # return both values - return order is important
        return stay, back_to_draft

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

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )
        shipment_ids = []
        return_info = {}

        counter = 0
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            shipment = wizard.shipment_id
            shipment_ids.append(shipment.id)

            for family in wizard.family_ids:
                draft_packing = family.draft_packing_id.backorder_id
                draft_shipment_id = draft_packing.shipment_id.id

                if family.return_from == 0 and family.return_to == 0:
                    continue

                # reset "save as draft" wizard if has:
                ship_processor_wiz = self.pool.get('shipment.processor').search(cr, uid, [
                    ('shipment_id', '=', shipment.id),
                    ('draft', '=', True),
                ], context=context)
                if ship_processor_wiz:
                    self.pool.get('shipment.processor').write(cr, uid, ship_processor_wiz, {'draft': False}, context=context)

                # UF-2531: Store some important info for the return pack messages
                return_info.setdefault(str(counter), {
                    'name': family.ppl_id.name,
                    'from_pack': family.from_pack,
                    'to_pack': family.to_pack,
                    'return_from': family.return_from,
                    'return_to': family.return_to,
                })
                counter = counter + 1

                # Search the corresponding moves
                move_ids = move_obj.search(cr, uid, [
                    ('picking_id', '=', family.draft_packing_id.id),
                    ('from_pack', '=', family.from_pack),
                    ('to_pack', '=', family.to_pack),
                ], context=context)
                stay = []
                if family.to_pack >= family.return_to:
                    if family.return_from == family.from_pack:
                        if family.return_to != family.to_pack:
                            stay.append((family.return_to + 1, family.to_pack))
                    elif family.return_to == family.to_pack:
                        # Do not start at beginning, but same end
                        stay.append((family.from_pack, family.return_from - 1))
                    else:
                        # In the middle, two now tuple in stay
                        stay.append((family.from_pack, family.return_from - 1))
                        stay.append((family.return_to + 1, family.to_pack))

                ### update save as draft move if has ###
                # get the linked "save as draft" wizard:
                ship_processor_wiz = self.pool.get('shipment.processor').search(cr, uid, [
                    ('shipment_id', '=', draft_shipment_id),
                    ('draft', '=', True),
                ], context=context)
                if ship_processor_wiz:
                    # create "save as draft" lines with returned qty:
                    ship_processor_wiz = self.pool.get('shipment.processor').browse(cr, uid, ship_processor_wiz[0], context=context)
                    family_vals = {
                        'wizard_id': ship_processor_wiz.id,
                        'sale_order_id': family.sale_order_id and family.sale_order_id.id or False,
                        'from_pack': family.from_pack,
                        'to_pack': family.to_pack,
                        'selected_number': family.num_of_packs,
                        'pack_type': family.pack_type and family.pack_type.id or False,
                        'length': family.length,
                        'width': family.width,
                        'height': family.height,
                        'weight': family.weight,
                        'draft_packing_id': draft_packing and draft_packing.id or False,
                        'ppl_id': family.ppl_id and family.ppl_id.id or False,
                        'comment': family.comment,
                    }
                    self.pool.get('shipment.family.processor').create(cr, uid, family_vals, context=context)


                move_data = {}
                for move in move_obj.browse(cr, uid, move_ids, context=context):
                    if move.state != 'assigned':
                        raise osv.except_osv(
                            _('Error'),
                            _('One of the returned family is not \'Available\'. Check the state of the pack families and re-try.'),
                        )

                    move_data.setdefault(move.id, {
                        'initial': move.product_qty,
                        'partial_qty': 0,
                    })

                    for seq in stay:
                        # Corresponding number of packs
                        selected_number = seq[1] - seq[0] + 1
                        # Quantity to return
                        new_qty = selected_number * move.qty_per_pack
                        # For both cases, we update the from/to and compute the corresponding quantity
                        # if the move has been updated already, we copy/update
                        move_values = {
                            'from_pack': seq[0],
                            'to_pack': seq[1],
                            'product_qty': new_qty,
                            'line_number': move.line_number,
                            'state': 'assigned',
                        }
                        # The original move is never modified, but canceled
                        move_data[move.id]['partial_qty'] += new_qty

                        move_obj.copy(cr, uid, move.id, move_values, context=context)

                    # Get the back_to_draft sequences
                    selected_number = family.return_to - family.return_from + 1
                    # Quantity to return
                    new_qty = selected_number * move.qty_per_pack
                    # values
                    move_values = {
                        'from_pack': family.return_from,
                        'to_pack': family.return_to,
                        'line_number': move.line_number,
                        'product_qty': new_qty,
                        'location_id': move.picking_id.warehouse_id.lot_distribution_id.id,
                        'location_dest_id': move.picking_id.warehouse_id.lot_dispatch_id.id,
                        'not_shipped': True,
                        'state': 'done',
                    }

                    # Create a back move in the packing object
                    # Distribution -> Dispatch
                    context['non_stock_noupdate'] = True
                    move_obj.copy(cr, uid, move.id, move_values, context=context)
                    context['non_stock_noupdate'] = False

                    move_data[move.id]['partial_qty'] += new_qty

                    # Create the draft move
                    # Dispatch -> Distribution
                    # Picking_id = draft_picking
                    move_values.update({
                        'location_id': move.picking_id.warehouse_id.lot_dispatch_id.id,
                        'location_dest_id': move.picking_id.warehouse_id.lot_distribution_id.id,
                        'picking_id': draft_packing.id,
                        'state': 'assigned',
                        'not_shipped': False,
                    })

                    context['non_stock_noupdate'] = True
                    move_obj.copy(cr, uid, move.id, move_values, context=context)
                    context['non_stock_noupdate'] = False

                    move_values = {
                        'product_qty': 0.00,
                        'state': 'done',
                        'from_pack': 0,
                        'to_pack': 0,
                    }
                    move_obj.write(cr, uid, [move.id], move_values, context=context)

                for move_vals in move_data.values():
                    if round(move_vals['initial'], 13) != round(move_vals['partial_qty'], 13):
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

        # UF-2531: Create manually the message for the return pack of the ship
        if shipment and shipment.id:
            self._manual_create_rw_shipment_message(cr, uid, shipment.id, return_info, 'usb_shipment_return_packs', context=context)

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

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        cancel the shipment which is not yet shipped (packed state)

        - for each related packing object
         - trigger the cancel workflow signal
         logic is performed in the action_cancel method of stock.picking
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")

        for shipment in self.browse(cr, uid, ids, context=context):
            # shipment state should be 'packed'
            assert shipment.state == 'packed', 'cannot ship a shipment which is not in correct state - packed - %s' % shipment.state
            # for each shipment
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id)], context=context)
            # call cancel workflow on corresponding packing objects
            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                # we cancel each picking object - action_cancel is overriden at stock_picking level for stock_picking of subtype == 'packing'
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_cancel', cr)
            # log corresponding action
            self.log(cr, uid, shipment.id, _("The Shipment (%s) has been canceled.") % (shipment.name,))
            self.log(cr, uid, shipment.backshipment_id.id, _("The corresponding Draft Shipment (%s) has been updated.") % (shipment.backshipment_id.name,))

        return True

    def ship(self, cr, uid, ids, context=None):
        '''
        we ship the created shipment, the state of the shipment is changed, we do not use any wizard
        - state of the shipment is updated to 'shipped'
        - copy the packing
        - modify locations of moves for the new packing
        - trigger the workflow button_confirm for the new packing
        - trigger the workflow to terminate the initial packing
        - update the draft_picking_id fields of pack_families
        - update the shipment_date of the corresponding sale_order if not set yet
        '''
        pick_obj = self.pool.get('stock.picking')
        so_obj = self.pool.get('sale.order')
        # objects
        date_tools = self.pool.get('date.tools')
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)

        for shipment in self.browse(cr, uid, ids, context=context):
            # shipment state should be 'packed'
            if shipment.state != 'packed':
                raise osv.except_osv(_('Error, packing in wrong state !'),
                                     _('Cannot process a Shipment which is in an incorrect state'))

            # the state does not need to be updated - function
            # update actual ship date (shipment_actual_date) to today + time
            today = time.strftime(db_datetime_format)
            vals = {'shipment_actual_date': today, }
            if context.get('source_shipment_address_id', False):
                vals['address_id'] = context['source_shipment_address_id']

            if pick_obj._get_usb_entity_type(cr, uid) == pick_obj.REMOTE_WAREHOUSE:
                vals['already_replicated'] = False

            shipment.write(vals)
            # corresponding packing objects
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id)], context=context)

            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                assert packing.subtype == 'packing'
                # update the packing object for the same reason
                # - an integrity check at _get_vals level of shipment states that all packing linked to a shipment must have the same state
                # we therefore modify it before the copy, otherwise new (assigned) and old (done) are linked to the same shipment
                # -> integrity check has been removed
                pick_obj.write(cr, uid, [packing.id], {'shipment_id': False}, context=context)
                # copy each packing
                new_packing_id = pick_obj.copy(cr, uid, packing.id, {'name': packing.name,
                                                                     'first_shipment_packing_id': packing.id,
                                                                     # UF-1617: keepLineNumber must be set so that all line numbers are passed correctly when updating the corresponding IN
                                                                     'shipment_id': shipment.id, }, context=dict(context, keepLineNumber=True, keep_prodlot=True, allow_copy=True,))

                pick_obj.write(cr, uid, [new_packing_id], {'origin': packing.origin}, context=context)
                if packing.claim:
                    pick_obj.write(cr, uid, [new_packing_id], ({'claim': True}), context=context)
                new_packing = pick_obj.browse(cr, uid, new_packing_id, context=context)

                if new_packing.move_lines and pick_obj._get_usb_entity_type(cr, uid) == pick_obj.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):  # RW Sync - set the replicated to True for not syncing it again
                    pick_obj.write(cr, uid, [new_packing_id], {'for_shipment_replicate': True}, context=context)

                # update the shipment_date of the corresponding sale order if the date is not set yet - with current date
                if new_packing.sale_id and not new_packing.sale_id.shipment_date:
                    # get the date format
                    date_tools = self.pool.get('date.tools')
                    date_format = date_tools.get_date_format(cr, uid, context=context)
                    db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
                    today = time.strftime(date_format)
                    today_db = time.strftime(db_date_format)
                    so_obj.write(cr, uid, [new_packing.sale_id.id], {'shipment_date': today_db, }, context=context)
                    so_obj.log(cr, uid, new_packing.sale_id.id, _("Shipment Date of the Field Order '%s' has been updated to %s.") % (new_packing.sale_id.name, tools.ustr(today)))

                # update locations of stock moves
                for move in new_packing.move_lines:
                    move.write({'location_id': new_packing.warehouse_id.lot_distribution_id.id,
                                'location_dest_id': new_packing.warehouse_id.lot_output_id.id}, context=context)

                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', new_packing_id, 'button_confirm', cr)
                # simulate check assign button, as stock move must be available
                pick_obj.force_assign(cr, uid, [new_packing_id])
                # trigger standard workflow
                pick_obj.action_move(cr, uid, [packing.id])
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_done', cr)

            # log the ship action
            self.log(cr, uid, shipment.id, _('The Shipment %s has been shipped.') % (shipment.name,))
            self.infolog(cr, uid, "The Shipment id:%s (%s) has been shipped." % (
                shipment.id, shipment.name,
            ))

        # TODO which behavior
        return True

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

        for shipment_base in self.browse(cr, uid, ids, context=context):
            # the shipment which will be treated
            shipment = shipment_base

            if shipment.state not in ('draft',):
                # it's not a draft shipment, check all corresponding packing, trg.write them
                packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ], context=context)
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
                        elif move.from_pack or move.to_pack:
                            # qty = 0, from/to pack should have been set to zero
                            raise osv.except_osv(
                                _('Error'),
                                _('There are stock moves with 0 quantity on the pack family sequence')
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

                    # UF-1617: set the flag to PPL to indicate that the SHIP has been done, for synchronisation purpose
#                    if draft_packing.previous_step_id and draft_packing.previous_step_id.id:
#                        cr.execute('update stock_picking set already_shipped=\'t\' where id=%s' %draft_packing.previous_step_id.id)

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

        if isinstance(ids, (int, long)):
            ids = [ids]

        for shipment in self.browse(cr, uid, ids, context=context):
            make_invoice = False
            move = False
            for pack in shipment.pack_family_memory_ids:
                for move in pack.move_lines:
                    if move.state != 'cancel' and (not move.sale_line_id or move.sale_line_id.order_id.order_policy == 'picking'):
                        make_invoice = True

            if not make_invoice:
                continue

            payment_term_id = False
            partner = shipment.partner_id2
            if not partner:
                raise osv.except_osv(_('Error, no partner !'),
                                     _('Please put a partner on the shipment if you want to generate invoice.'))

            # (US-952) No STV created when a shipment is generated on an external supplier
            if partner.partner_type == 'external':
                continue

            inv_type = 'out_invoice'

            if inv_type in ('out_invoice', 'out_refund'):
                account_id = partner.property_account_receivable.id
                payment_term_id = partner.property_payment_term and partner.property_payment_term.id or False
            else:
                account_id = partner.property_account_payable.id

            addresses = partner_obj.address_get(cr, uid, [partner.id], ['contact', 'invoice'])
            today = time.strftime('%Y-%m-%d', time.localtime())

            invoice_vals = {
                'name': shipment.name,
                'origin': shipment.name or '',
                'type': inv_type,
                'account_id': account_id,
                'partner_id': partner.id,
                'address_invoice_id': addresses['invoice'],
                'address_contact_id': addresses['contact'],
                'payment_term': payment_term_id,
                'fiscal_position': partner.property_account_position.id,
                'date_invoice': context.get('date_inv', False) or today,
                'user_id': uid,
            }

            cur_id = shipment.pack_family_memory_ids[0].currency_id.id
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
            out_invoice = inv_type == 'out_invoice'
            debit_note = 'is_debit_note' in invoice_vals and invoice_vals['is_debit_note']
            inkind_donation = 'is_inkind_donation' in invoice_vals and invoice_vals['is_inkind_donation']
            intermission = 'is_intermission' in invoice_vals and invoice_vals['is_intermission']
            is_ivo = out_invoice and not debit_note and not inkind_donation and intermission
            is_stv = out_invoice and not debit_note and not inkind_donation and not intermission

            # US-3822 Block STV creation if the partner is internal
            if is_stv and partner.partner_type == 'internal':
                continue

            if is_ivo or is_stv:
                origin_inv = 'origin' in invoice_vals and invoice_vals['origin'] or False
                fo = move and move.sale_line_id and move.sale_line_id.order_id or False
                new_origin = origin_inv and fo and "%s:%s" % (origin_inv, fo.name)
                new_origin = new_origin and new_origin[:64]  # keep only 64 characters (because of the JE ref size)
                if new_origin:
                    invoice_vals.update({'origin': new_origin})
                name_inv = 'name' in invoice_vals and invoice_vals['name'] or False
                new_name_inv = name_inv and fo and fo.client_order_ref and "%s : %s" % (fo.client_order_ref, name_inv)
                if new_name_inv:
                    invoice_vals.update({'name': new_name_inv})

            invoice_id = invoice_obj.create(cr, uid, invoice_vals,
                                            context=context)

            # Change currency for the intermission invoice
            if shipment.partner_id2.partner_type == 'intermission':
                company_currency = company.currency_id and company.currency_id.id or False
                if not company_currency:
                    raise osv.except_osv(_('Warning'), _('No company currency found!'))
                wiz_account_change = self.pool.get('account.change.currency').create(cr, uid, {'currency_id': company_currency}, context=context)
                self.pool.get('account.change.currency').change_currency(cr, uid, [wiz_account_change], context={'active_id': invoice_id})

            # Link the invoice to the shipment
            self.write(cr, uid, [shipment.id], {'invoice_id': invoice_id}, context=context)

            # For each stock moves, create an invoice line
            for pack in shipment.pack_family_memory_ids:
                for move in pack.move_lines:
                    if move.state == 'cancel':
                        continue

                    if move.sale_line_id and move.sale_line_id.order_id.order_policy != 'picking':
                        continue

                    origin = move.picking_id.name or ''
                    if move.picking_id.origin:
                        origin += ':' + move.picking_id.origin

                    if inv_type in ('out_invoice', 'out_refund'):
                        account_id = move.product_id.product_tmpl_id.\
                            property_account_income.id
                        if not account_id:
                            account_id = move.product_id.categ_id.\
                                property_account_income_categ.id
                    else:
                        account_id = move.product_id.product_tmpl_id.\
                            property_account_expense.id
                        if not account_id:
                            account_id = move.product_id.categ_id.\
                                property_account_expense_categ.id

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
                        tax_ids = map(lambda x: x.id, taxes)

                    distrib_id = False
                    if move.sale_line_id:
                        sol_ana_dist_id = move.sale_line_id.analytic_distribution_id or move.sale_line_id.order_id.analytic_distribution_id
                        if sol_ana_dist_id:
                            distrib_id = distrib_obj.copy(cr, uid, sol_ana_dist_id.id, context=context)
                            # create default funding pool lines (if no one)
                            self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [distrib_id])

                    # set UoS if it's a sale and the picking doesn't have one
                    uos_id = move.product_uos and move.product_uos.id or False
                    if not uos_id and inv_type in ('out_invoice', 'out_refund'):
                        uos_id = move.product_uom.id
                    account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, partner.property_account_position, account_id)

                    line_id = line_obj.create(cr, uid, {'name': move.name,
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
                                                        }, context=context)

                    self.pool.get('shipment').write(cr, uid, [shipment.id], {'invoice_id': invoice_id}, context=context)
                    if move.sale_line_id:
                        sale_obj.write(cr, uid, [move.sale_line_id.order_id.id], {'invoice_ids': [(4, invoice_id)], })
                        sale_line_obj.write(cr, uid, [move.sale_line_id.id], {'invoiced': True,
                                                                              'invoice_lines': [(4, line_id)], })

        return True

    @check_cp_rw
    def validate(self, cr, uid, ids, context=None):
        '''
        validate the shipment

        change the state to Done for the corresponding packing
        - validate the workflow for all the packings
        '''
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")

        for shipment in self.browse(cr, uid, ids, context=context):
            # validate should only be called on shipped shipments
            if shipment.state != 'shipped':
                raise osv.except_osv(
                    _('Error'),
                    _('The state of the shipment must be \'Shipped\'. Please check it and re-try.')
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

            for packing in pick_obj.browse(cr, uid, packing_ids, context=context):
                assert packing.subtype == 'packing' and packing.state == 'assigned'
                # trigger standard workflow
                pick_obj.action_move(cr, uid, [packing.id])
                wf_service.trg_validate(uid, 'stock.picking', packing.id, 'button_done', cr)
                pick_obj._hook_create_sync_messages(cr, uid, packing.id, context)  # UF-1617: Create the sync message for batch and asset before shipping

                # UF-1617: set the flag to this packing object to indicate that the SHIP has been done, for synchronisation purpose
                cr.execute('update stock_picking set already_shipped=\'t\' where id=%s', (packing.id,))

                # closing FO lines:
                for stock_move in packing.move_lines:
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

            # Create automatically the invoice
            self.shipment_create_invoice(cr, uid, shipment.id, context=context)

            # log validate action
            self.log(cr, uid, shipment.id, _('The Shipment %s has been closed.') % (shipment.name,))
            self.infolog(cr, uid, "The Shipment id:%s (%s) has been closed." % (
                shipment.id, shipment.name,
            ))

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
                    _('The shipment must be \'Closed\'. Please check this and re-try')
                )
            # gather the corresponding packing and trigger the corresponding function
            packing_ids = pick_obj.search(cr, uid, [('shipment_id', '=', shipment.id), ('state', '=', 'done')], context=context)
            # set delivered all packings
            pick_obj.set_delivered(cr, uid, packing_ids, context=context)

        return True



shipment()


class shipment_additionalitems(osv.osv):
    _name = "shipment.additionalitems"
    _description = "Additional Items"

    _columns = {'name': fields.char(string='Additional Item', size=1024, required=True),
                'shipment_id': fields.many2one('shipment', string='Shipment', readonly=True, on_delete='cascade'),
                'picking_id': fields.many2one('stock.picking', string='Picking', readonly=True, on_delete='cascade'),
                'quantity': fields.float(digits=(16, 2), string='Quantity', required=True),
                'uom': fields.many2one('product.uom', string='UOM', required=True),
                'comment': fields.char(string='Comment', size=1024),
                'volume': fields.float(digits=(16, 2), string=u'Volume[dm³]'),
                'weight': fields.float(digits=(16, 2), string='Weight[kg]', required=True),
                }

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


class ppl_customize_label(osv.osv):
    '''
    label preferences
    '''
    _name = 'ppl.customize.label'

    _columns = {'name': fields.char(string='Name', size=1024,),
                'notes': fields.text(string='Notes'),
                # 'packing_list_reference': fields.boolean(string='Packing List Reference'),
                'pre_packing_list_reference': fields.boolean(string='Pre-Packing List Reference'),
                'destination_partner': fields.boolean(string='Destination Partner'),
                'destination_address': fields.boolean(string='Destination Address'),
                'requestor_order_reference': fields.boolean(string='Requestor Order Reference'),
                'weight': fields.boolean(string='Weight'),
                # 'shipment_reference': fields.boolean(string='Shipment Reference'),
                'packing_parcel_number': fields.boolean(string='Packing Parcel Number'),
                # 'expedition_parcel_number': fields.boolean(string='Expedition Parcel Number'),
                'specific_information': fields.boolean(string='Specific Information'),
                'logo': fields.boolean(string='Company Logo'),
                }

    _defaults = {'name': 'My Customization',
                 'notes': '',
                 # 'packing_list_reference': True,
                 'pre_packing_list_reference': True,
                 'destination_partner': True,
                 'destination_address': True,
                 'requestor_order_reference': True,
                 'weight': True,
                 # 'shipment_reference': True,
                 'packing_parcel_number': True,
                 # 'expedition_parcel_number': True,
                 'specific_information': True,
                 'logo': True,
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
            res['arch'] = etree.tostring(root)

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
            if [x for x in data.values() if x]:
                raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try again.'))

        return super(stock_picking, self).unlink(cr, uid, ids, context=context)


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
                # ppl, use the draft picking ticket sequence
#                if obj.previous_step_id and obj.previous_step_id.backorder_id:
#                    base = obj.name
#                    base = base.split('-')[0] + '-'
#                    default.update(name=base + obj.previous_step_id.backorder_id.sequence_id.get_id(code_or_id='id', context=context))
#                else:
#                    default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'ppl'))

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
        # the tag 'from_button' was added in the web client (openerp/controllers/form.py in the method duplicate) on purpose
        # US-779: Reset the ref to rw document
        default.update(rw_sdref_counterpart=False)

        if context.get('from_button'):
            default.update(purchase_id=False)
        if not context.get('wkf_copy'):
            context['not_workflow'] = True
        result = super(stock_picking, self).copy_data(cr, uid, copy_id, default=default, context=context)

        return result

    def _erase_prodlot_hook(self, cr, uid, pick_id, context=None, *args, **kwargs):
        '''
        hook to keep the production lot when a stock move is copied
        '''
        res = super(stock_picking, self)._erase_prodlot_hook(cr, uid, pick_id, context=context, *args, **kwargs)

        return res and not context.get('keep_prodlot', False)

    def has_picking_ticket_in_progress(self, cr, uid, ids, context=None):
        '''
        ids is the list of draft picking object we want to test
        completed means, we recursively check that next_step link object is cancel or done

        return true if picking tickets are in progress, meaning picking ticket or ppl or shipment not done exist
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
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
        if isinstance(ids, (int, long)):
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
        for val in picking_to_families.values():
            family_set.update(val)

        family_read_result = pack_fam_obj.read(cr, uid,
                                               list(family_set),
                                               ['num_of_packs', 'total_weight', 'total_volume', 'shipment_id', 'not_shipped'],
                                               context=context)

        family_dict = dict((x['id'], x) for x in family_read_result)
        parent_id_ship = {}
        for current_id, family_ids in picking_to_families.items():
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

    def init(self, cr):
        """
        Load msf_outgoing_data.xml before self
        """
        if hasattr(super(stock_picking, self), 'init'):
            super(stock_picking, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'msf_outgoing'), ])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module msf_outgoing: loading data/msf_outgoing_data.xml')
            pathname = path.join('msf_outgoing', 'data/msf_outgoing_data.xml')
            file_to_open = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'msf_outgoing', file_to_open, {}, mode='init', noupdate=False)

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
        ids = [('id', 'in', [x for x in result.keys() if eval("%s %s %s" % (result[x], op, args[0][2]))])]
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
            if pick.type != 'out' or pick.subtype != 'picking' or pick.state != 'draft':
                res[pick.id] = False
                continue

            res[pick.id] = 'confirmed'
            available = False
            confirmed = False
            processed = True
            empty = len(pick.move_lines)
            for move in pick.move_lines:
                if move.product_qty == 0.00 or move.state == 'cancel':
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
            elif processed and empty:
                res[pick.id] = 'processed'
            elif empty == 0:
                res[pick.id] = 'empty'
            else:
                res[pick.id] = False

        return res

    _columns = {'flow_type': fields.selection([('full', 'Full'), ('quick', 'Quick')], readonly=True, states={'draft': [('readonly', False), ], }, string='Flow Type'),
                'subtype': fields.selection([('standard', 'Standard'), ('picking', 'Picking'), ('ppl', 'PPL'), ('packing', 'Packing'), ('sysint', 'System Internal')], string='Subtype'),
                'backorder_ids': fields.one2many('stock.picking', 'backorder_id', string='Backorder ids',),
                'previous_step_id': fields.many2one('stock.picking', 'Previous step'),
                'previous_step_ids': fields.one2many('stock.picking', 'previous_step_id', string='Previous Step ids',),
                'shipment_id': fields.many2one('shipment', string='Shipment'),
                'sequence_id': fields.many2one('ir.sequence', 'Picking Ticket Sequence', help="This field contains the information related to the numbering of the picking tickets.", ondelete='cascade'),
                'first_shipment_packing_id': fields.many2one('stock.picking', 'Shipment First Step'),
                # 'pack_family_ids': fields.one2many('pack.family', 'ppl_id', string='Pack Families',),
                # attributes for specific packing labels
                'ppl_customize_label': fields.many2one('ppl.customize.label', string='Labels Customization',),
                # warehouse info (locations) are gathered from here - allow shipment process without sale order
                'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True,),
                # flag for converted picking
                'converted_to_standard': fields.boolean(string='Converted to Standard'),
                # functions
                'num_of_packs': fields.function(_vals_get, method=True,
                                                type='integer', string='#Packs', multi='get_vals_integer'),
                'total_volume': fields.function(_vals_get, method=True, type='float', string=u'Total Volume[dm³]', multi='get_vals'),
                'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals'),
                'currency_id': fields.function(_get_currency, method=True, type='many2one', relation='res.currency', string='Currency', multi=False),
                'is_dangerous_good': fields.function(_is_one_of_the_move_lines, method=True,
                                                     type='char', size=8, string='Dangerous Good'),
                'is_keep_cool': fields.function(_is_one_of_the_move_lines, method=True,
                                                type='char', size=8, string='Keep Cool'),
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
                # 'is_completed': fields.function(_vals_get, method=True, type='boolean', string='Completed Process', multi='get_vals',),
                'pack_family_memory_ids': fields.one2many('pack.family.memory', 'ppl_id', string='Memory Families'),
                'description_ppl': fields.char('Description', size=256),
                'already_shipped': fields.boolean(string='The shipment is done'),  # UF-1617: only for indicating the PPL that the relevant Ship has been closed
                'has_draft_moves': fields.function(_get_draft_moves, method=True, type='boolean', string='Has draft moves ?', store=False),
                'has_to_be_resourced': fields.boolean(string='Picking has to be resourced'),
                'in_ref': fields.char(string='IN Reference', size=1024),
                'from_manage_expired': fields.boolean(string='The Picking was created with Manage Expired Stock'),
                'requestor': fields.char(size=128, string='Requestor'),
                }

    _defaults = {
        'flow_type': 'full',
        'ppl_customize_label': lambda obj, cr, uid, c: len(obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'), ], context=c)) and obj.pool.get('ppl.customize.label').search(cr, uid, [('name', '=', 'Default Label'), ], context=c)[0] or False,
        'subtype': 'standard',
        'first_shipment_packing_id': False,
        'warehouse_id': lambda obj, cr, uid, c: len(obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)) and obj.pool.get('stock.warehouse').search(cr, uid, [], context=c)[0] or False,
        'converted_to_standard': False,
        'already_shipped': False,
        'line_state': 'empty',
        'in_ref': False,
        'from_manage_expired': False,
    }

    _order = 'name desc'

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
            for sale_line in values.values():
                for product in sale_line['products'].values():
                    for uom in product['uoms'].values():
                        # loop through all existing production lot for this product - all are taken into account, internal and external
                        for lot in product['obj'].prodlot_ids:
                            if lot.id not in uom['lots'].keys():
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

    def generate_data_from_picking_for_pack_family(self, cr, uid, pick_ids, object_type='shipment', from_pack=False, to_pack=False, context=None):
        '''
        USED BY THE SHIPMENT PROCESS WIZARD
        generate the data structure from the stock.picking object

        we can limit the generation to certain from/to sequence

        one data for each move_id - here is the difference with data generated from partial

        structure:
            {pick_id: {from_pack: {to_pack: {move_id: {data}}}}}

        if the move has a quantity equal to 0, it means that no pack are available,
        these moves are therefore not taken into account for the pack families generation

        TODO: integrity constraints

        Note: why the same dictionary is repeated n times for n moves, because
        it is directly used when we create the pack families. could be refactored
        with one dic per from/to with a 'move_ids' entry
        '''
        assert bool(from_pack) == bool(to_pack), 'from_pack and to_pack must be either both filled or empty'
        result = {}


        if object_type == 'shipment':
            # all moves are taken into account, therefore the back moves are represented
            # by done pack families
            states = ('cancel')
        elif object_type == 'memory':
            # done moves are not displayed as pf as we cannot select these packs anymore (they are returned)
            states = ('done')
        else:
            assert False, 'Should not reach this line'

        for pick in self.browse(cr, uid, pick_ids, context=context):
            result[pick.id] = {}
            for move in pick.move_lines:
                if not from_pack or move.from_pack == from_pack:
                    if not to_pack or move.to_pack == to_pack:
                        # the quantity must be positive and the state depends on the window's type
                        if move.product_qty and move.state not in states:
                            # subtype == ppl - called from stock picking
                            if pick.subtype == 'ppl':
                                result[pick.id] \
                                    .setdefault(move.from_pack, {}) \
                                    .setdefault(move.to_pack, {})[move.id] = {'sale_order_id': pick.sale_id.id,
                                                                              'ppl_id': pick.id,  # only change between ppl - packing
                                                                              'from_pack': move.from_pack,
                                                                              'to_pack': move.to_pack,
                                                                              'pack_type': move.pack_type.id,
                                                                              'length': move.length,
                                                                              'width': move.width,
                                                                              'height': move.height,
                                                                              'weight': move.weight,
                                                                              'draft_packing_id': pick.id,
                                                                              'description_ppl': pick.description_ppl,
                                                                              }
                            # subtype == packing - caled from shipment
                            elif pick.subtype == 'packing':
                                result[pick.id] \
                                    .setdefault(move.from_pack, {}) \
                                    .setdefault(move.to_pack, {})[move.id] = {'sale_order_id': pick.sale_id.id,
                                                                              'ppl_id': pick.previous_step_id.id,
                                                                              'from_pack': move.from_pack,
                                                                              'to_pack': move.to_pack,
                                                                              'pack_type': move.pack_type.id,
                                                                              'length': move.length,
                                                                              'width': move.width,
                                                                              'height': move.height,
                                                                              'weight': move.weight,
                                                                              'draft_packing_id': pick.id,
                                                                              }

                                if object_type != 'memory':
                                    result[pick.id][move.from_pack][move.to_pack][move.id]['description_ppl'] = pick.description_ppl

        return result

    def create_pack_families_memory_from_data(self, cr, uid, data, shipment_id, context=None,):
        '''
        **DEPECRATED**
        - clear existing pack family memory objects is not necessary thanks to vaccum system
        -> in fact cleaning old memory objects reslults in a bug, because when we click on a
           pf memory to see it's form view, the shipment view is regenerated (delete the pf)
           but then the form view uses the old pf memory id for data and it crashes. Cleaning
           of previous pf memory has therefore been removed.
        - generate new ones based on data
        - return created ids
        '''
        pf_memory_obj = self.pool.get('pack.family.memory')
        # find and delete existing objects
        # ids = pf_memory_obj.search(cr, uid, [('shipment_id', '=', shipment_id),], context=context)
        # pf_memory_obj.unlink(cr, uid, ids, context=context)
        created_ids = []
        # create pack family memory
        for picking in data.values():
            for from_pack in picking.values():
                for to_pack in from_pack.values():
                    for move_id in to_pack.keys():
                        move_data = to_pack[move_id]
                    # create corresponding memory object
                    move_data.update(name='_name',
                                     shipment_id=shipment_id,)
                    pf_id = pf_memory_obj.create(cr, uid, move_data, context=context)
                    created_ids.append(pf_id)
        return created_ids

    def get_current_pick_sequence_for_rw(self, cr, uid, picking_type, context=None):
        cr.execute('SELECT id FROM ir_sequence WHERE code=%s and active=true ORDER BY id', (picking_type,))
        res = cr.dictfetchone()
        if res and res['id']:
            cr.execute("SELECT last_value from ir_sequence_%03d" % res['id'])  # not_a_user_entry
            res = cr.dictfetchone()
            if res and res['last_value']:
                return res['last_value']
        return False

    def create(self, cr, uid, vals, context=None):
        '''
        creation of a stock.picking of subtype 'packing' triggers
        special behavior :
         - creation of corresponding shipment
        '''
        # Objects
        ship_proc_obj = self.pool.get('shipment.processor')
        sale_order_obj = self.pool.get('sale.order')
        # For Remote Warehouse: If the instance is CP, and if the type=out, subtype=PICK and name does not contain "-", then set the flag to ask syncing this PICK
        usb_entity = self._get_usb_entity_type(cr, uid, context)

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

        if context.get('sync_update_execution', False) or context.get('sync_message_execution', False):
            # UF-2066: in case the data comes from sync, some False value has been removed, but needed in some assert.
            # The following lines are to re-enter explicitly the values, even if they are already set to False
            vals['backorder_id'] = vals.get('backorder_id', False)
            vals['shipment_id'] = vals.get('shipment_id', False)
        else:  # if it is a CONSO-OUT --_> set the state for replicating back to CP
            if 'name' in vals and 'OUT-CONSO' in vals['name']:
                vals.update(already_replicated=False,)
            # UF-2531: When the INT from scratch created in RW, just set it for sync to CP
            if usb_entity == self.REMOTE_WAREHOUSE and (('type' in vals and vals['type'] == 'internal') or
                                                        ('origin' not in vals or vals['origin'] == False)):  # US-702 Sync also the OUT from scratch in RW
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
        # shipment object
        shipment_obj = self.pool.get('shipment')
        # move object
        move_obj = self.pool.get('stock.move')

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
        if not context.get('sync_message_execution', False) and usb_entity == self.CENTRAL_PLATFORM:
            # read the new object
            new_packing = self.browse(cr, uid, new_packing_id, context=context)
            if new_packing and ((new_packing.type == 'out' and new_packing.subtype == 'picking' and new_packing.name.find('-') == -1) or
                                (new_packing.type == 'in' and new_packing.subtype == 'standard') or
                                (new_packing.type == 'internal' and new_packing.subtype == 'standard' and new_packing.sale_id)):
                for_update = {'already_replicated': False}

                '''
                    Only get the current sequence for the IN object at the moment, as we still have problem with the naming of documents functionally
                    A proper functional solution for this should be found, then we will look for technical solution to apply for all cases!

                    Please refer to the code and explanation in sync_so/in_rw.py, method usb_replicate_in(), line 90 for further information on this issue

                '''
#                if new_packing.type in ('in', 'internal'):
#                    seq_obj_name =  'stock.picking.' + vals['type']
#                    sequence_id = self.get_current_pick_sequence_for_rw(cr, uid, seq_obj_name, context)
#                    if sequence_id:
#                        for_update['rw_force_seq'] = sequence_id
                self.write(cr, uid, [new_packing_id], for_update, context=context)

        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'backorder_id' in vals, 'No backorder_id'
            assert 'shipment_id' in vals, 'No shipment_id'

            if vals['backorder_id'] and vals['shipment_id']:
                # ship of existing shipment
                # no new shipment
                # TODO
                return new_packing_id

            if vals['backorder_id'] and not vals['shipment_id']:
                if not context.get('shipment_proc_id', False):
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Missing the ID of the shipment processor in the context'),
                    )
                if not context.get('shipment_id', False):
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Missing the ID of the shipment in the context'),
                    )

                if not context.get('draft_packing_id', False):
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Missing the ID of the draft packing in the context'),
                    )

                ship_proc = ship_proc_obj.browse(cr, uid, context['shipment_proc_id'], context=context)
                shipment_id = context['shipment_id']
                draft_packing_id = context['draft_packing_id']

                for family in ship_proc.family_ids:
                    if family.draft_packing_id.id != draft_packing_id or family.selected_number == 0.00:
                        continue

                    selected_from_pack = family.to_pack - family.selected_number + 1

                    if family.selected_number == int(family.num_of_packs):
                        initial_from_pack = 0
                        initial_to_pack = 0
                    else:
                        initial_from_pack = family.from_pack
                        initial_to_pack = family.to_pack - family.selected_number

                    # find the corresponding moves
                    moves_ids = move_obj.search(cr, uid, [
                        ('picking_id', '=', family.draft_packing_id.id),
                        ('from_pack', '=', family.from_pack),
                        ('to_pack', '=', family.to_pack),
                        ('state', '!=', 'done'),
                    ], context=context)

                    # For corresponding moves
                    for move in move_obj.browse(cr, uid, moves_ids, context=context):
                        # We compute the selected quantity
                        selected_qty = move.qty_per_pack * family.selected_number

                        move_vals = {
                            'picking_id': new_packing_id,
                            'line_number': move.line_number,
                            'product_qty': selected_qty,
                            'from_pack': selected_from_pack,
                            'to_pack': family.to_pack,
                            'backmove_packing_id': move.id,
                        }

                        move_obj.copy(cr, uid, move.id, move_vals, context=context)

                        # Update corresponding initial move
                        initial_qty = max(move.product_qty - selected_qty, 0)


                        # if all packs have been selected, from/to have been set to 0
                        # update the original move object - the corresponding original shipment (draft)
                        # is automatically updated generically in the write method
                        move_obj.write(cr, uid, [move.id], {'product_qty': initial_qty,
                                                            'from_pack': initial_from_pack,
                                                            'to_pack': initial_to_pack}, context=context)

            if not vals['backorder_id']:
                # creation of packing after ppl validation
                # find an existing shipment or create one - depends on new pick state
                shipment_ids = shipment_obj.search(cr, uid, [('state', '=', 'draft'), ('address_id', '=', vals['address_id'])], context=context)

                # UF-2427: If the shipment came from USB sync, and if it is shipped in different ship name, then do not merge them!
                if shipment_ids and shipment_ids[0]:
                    if context.get('rw_shipment_name', False) and context.get('sync_message_execution', False) and usb_entity == self.CENTRAL_PLATFORM:
                        new_name = context.get('rw_shipment_name')
                        names = shipment_obj.read(cr, uid, shipment_ids, ['name'], context=context)
                        found = False
                        for n in names:
                            if new_name == n['name']:
                                # this shipment becomes the one for processing
                                shipment_ids = [n['id']]
                                found = True
                                break
                        if not found:  # If the name is new, then create a new Shipment
                            shipment_ids = []

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
                    # today
                    rts = sale_order_obj.read(cr, uid, sale_id, ['ready_to_ship_date'], context=context)['ready_to_ship_date']
                else:
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
                                  'shipment_actual_date': rts,
                                  'sale_id': vals.get('sale_id', False),
                                  'transport_type': sale_id and sale_order_obj.read(cr, uid, sale_id, ['transport_type'], context=context)['transport_type'] or False,
                                  'sequence_id': self.create_sequence(cr, uid, {'name': name,
                                                                                'code': name,
                                                                                'prefix': '',
                                                                                'padding': 2}, context=context)}

                        shipment_id = shipment_obj.create(cr, uid, values, context=context)
                        shipment_obj.log(cr, uid, shipment_id, _('The new Draft Shipment %s has been created.') % (name,))
                    else:
                        shipment_id = vals['shipment_id']
                else:
                    shipment_id = shipment_ids[0]
                    shipment = shipment_obj.browse(cr, uid, shipment_id, context=context)
                    # if expected ship date of shipment is greater than rts, update shipment_expected_date and shipment_actual_date
                    if shipment.shipment_expected_date:
                        shipment_expected = datetime.strptime(shipment.shipment_expected_date, db_datetime_format)
                        if rts_obj < shipment_expected:
                            shipment.write({'shipment_expected_date': rts, 'shipment_actual_date': rts, }, context=context)
                    shipment_name = shipment.name
                    shipment_obj.log(cr, uid, shipment_id, _('The ppl has been added to the existing Draft Shipment %s.') % (shipment_name,))

            # update the new pick with shipment_id
            self.write(cr, uid, [new_packing_id], {'shipment_id': shipment_id}, context=context)

        return new_packing_id

    def _hook_action_assign_raise_exception(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_assign method from stock>stock.py>stock_picking class

        - allow to choose wether or not an exception should be raised in case of no stock move
        '''
        res = super(stock_picking, self)._hook_action_assign_raise_exception(cr, uid, ids, context=context, *args, **kwargs)
        return res and False

    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        stock>stock.py>log_picking
        update the message to be displayed by the function
        '''
        pick = kwargs['pick']
        message = kwargs['message']
        # if the picking is converted to standard, and state is confirmed
        if pick.converted_to_standard and pick.state == 'confirmed':
            return 'The Preparation Picking has been converted to simple Out. ' + message
        if pick.type == 'out' and pick.subtype == 'picking':
            kwargs['message'] = message.replace('Delivery Order', 'Picking Ticket')
        elif pick.type == 'out' and pick.subtype == 'packing':
            kwargs['message'] = message.replace('Delivery Order', 'Packing List')
        elif pick.type == 'out' and pick.subtype == 'ppl':
            kwargs['message'] = message.replace('Delivery Order', 'Pre-Packing List')
        return super(stock_picking, self)._hook_log_picking_modify_message(cr, uid, ids, context, *args, **kwargs)

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

        wf_service = netsvc.LocalService("workflow")

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
#            if self.has_picking_ticket_in_progress(cr, uid, [obj.id], context=context)[obj.id]:
#                    raise osv.except_osv(_('Warning !'), _('Some Picking Tickets are in progress. Return products to stock from ppl and shipment and try again.'))

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
                vals.update({'backmove_id': False})
                # If the move comes from a DPO, don't change the destination location
                if not move.dpo_id:
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
                                proc_ids = self.pool.get('procurement.order').search(cr, uid, [('move_id', '=', other_linked_moves[0])], context=context)
                                for proc_id in proc_ids:
                                    wf_service.trg_write(uid, 'procurement.order', proc_id, cr)
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

            if 'assigned' in moves_states.values():
                # Add an empty write to display the 'Process' button on OUT
                self.write(cr, uid, [new_pick_id or obj.id], {'state': 'assigned'}, context=context)

            # Create a sync message for RW when converting the OUT back to PICK, except the caller of this method is sync
            if not context.get('sync_message_execution', False):
                # UF-2531: Added this name into the context for keeping the original name of the PICK when making the convert to OUT
                context.update({'original_name': obj.name})
                self._hook_create_rw_out_sync_messages(cr, uid, [new_pick_id or obj.id], context, True)

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
            move_obj.write(cr, uid, move_to_update, {'location_dest_id': pack_loc_id}, context=context)

        # Create a sync message for RW when converting the OUT back to PICK, except the caller of this method is sync
        if not context.get('sync_message_execution', False):
            self._hook_create_rw_out_sync_messages(cr, uid, [out.id], context, False)

        context.update({'picking_type': 'picking', 'search_view_id': search_view_id})
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
        usb_entity = self._get_usb_entity_type(cr, uid)

        # US-379: point 2) Generate RW messages manually and put into the queue when a partial OUT is done
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)

        res = {}

        if proc_model:
            proc_obj = self.pool.get(proc_model)

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            new_picking_id = False
            processed_moves = []
            new_split_move = {}
            move_data = {}
            for line in wizard.move_ids:
                move = line.move_id

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
            to_be_replicated = True
            if rw_full_process:
                del context['rw_full_process']
            if need_new_picking and not rw_full_process:
                cp_vals = {
                    'name': sequence_obj.get(cr, uid, 'stock.picking.%s' % (picking.type)),
                    'move_lines': [],
                    'state': 'draft',
                }
                context['allow_copy'] = True

                new_picking_id = picking_obj.copy(cr, uid, picking.id, cp_vals, context=context)
                # US-327: if it's an internal picking and in partial process, then set the already_replicated to True, so no replicate needed
                if picking.type == 'internal' and (usb_entity == self.REMOTE_WAREHOUSE or context.get('sync_message_execution', False)):
                    to_be_replicated = False
                    self.write(cr, uid, [new_picking_id], {'already_replicated': True}, context=context)

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
                if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False) and to_be_replicated:
                    update_vals.update({'already_replicated': False})

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
                    if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
                        update_vals.update({'already_replicated': False})
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

        # US-379: point 2) Generate RW messages manually and put into the queue when a partial OUT is done
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)
        return res

    @check_cp_rw
    def create_picking(self, cr, uid, ids, context=None):
        '''
        Open the wizard to create (partial) picking tickets
        '''
        # Objects
        proc_obj = self.pool.get('create.picking.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        data = self.read(cr, uid, ids[0], ['state', 'type', 'subtype', 'name'], context=context)
        if data['type'] != 'out' or data['subtype'] != 'picking':
            raise osv.except_osv(
                _('Error'),
                _('%s is not a main-pick !') % (data['name'])
            )
        if data['state'] != 'draft':
            raise osv.except_osv(
                _('Error'),
                _('The picking ticket is not in \'Draft\' state. Please check this and re-try')
            )

        # if wizard already exists, then open it (able save as draft/reset functionnality):
        wiz_ids = proc_obj.search(cr, uid, [('picking_id', 'in', ids), ('draft', '=', True)], context=context)
        if wiz_ids:
            processor_id = wiz_ids[0]
        else:
            processor_id = proc_obj.create(cr, uid, {'picking_id': ids[0]}, context=context)
            proc_obj.create_lines(cr, uid, processor_id, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'res_id': processor_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def do_create_picking(self, cr, uid, wizard_ids, context=None):
        '''
        Create the picking ticket from selected stock moves

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        '''
        # Objects
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        cp_proc_obj = self.pool.get('create.picking.processor')
        usb_entity = self._get_usb_entity_type(cr, uid)

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !')
            )

        for wizard in cp_proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id

            move_data = {}

            # Create the new picking object
            # A sequence for each draft picking ticket is used for the picking ticket

            # UF-2531: Use the name of the PICK sent from the RW sync if it's the case
            pick_name = False
            already_replicated = False
            if 'associate_pick_name' in context:
                pick_name = context.get('associate_pick_name', False)
                del context['associate_pick_name']
                already_replicated = True
            # US-803: Set the pick name that given from sync
            elif 'rw_backorder_name' in context:
                pick_name = context.get('rw_backorder_name', False)
                del context['rw_backorder_name']
                already_replicated = True

            # UF-2531: if not exist, then calculate the name as before
            if not pick_name:
                sequence = picking.sequence_id
                ticket_number = sequence.get_id(code_or_id='id', context=context)
                pick_name = '%s-%s' % (picking.name or 'NoName/000', ticket_number)

            copy_data = {
                'name': pick_name,
                'backorder_id': picking.id,
                'move_lines': [],
                'already_replicated': already_replicated,
            }
            tmp_allow_copy = context.get('allow_copy')
            context.update({
                'wkf_copy': True,
                'allow_copy': True,
            })
            new_picking_id = self.copy(cr, uid, picking.id, copy_data, context=context)
            if picking.claim:
                self.write(cr, uid, new_picking_id, ({'claim': True}), context=context)
            if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
                self.write(cr, uid, new_picking_id, {'already_replicated': False}, context=context)

            if tmp_allow_copy is None:
                del context['allow_copy']
            else:
                context['allow_copy'] = tmp_allow_copy

            # Create stock moves corresponding to processing lines
            # for now, each new line from the wizard corresponds to a new stock.move
            # it could be interesting to regroup according to production lot/asset id
            for line in wizard.move_ids:
                move_data.setdefault(line.move_id.id, {
                    'initial_qty': line.move_id.product_qty,
                    'line_number': line.move_id.line_number,
                    'processed_qty': 0.00,
                })


                if line.uom_id.id != line.move_id.product_uom.id:
                    processed_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.move_id.product_uom.id)
                else:
                    processed_qty = line.quantity

                move_data[line.move_id.id]['processed_qty'] += processed_qty

                # Copy the stock move and set the quantity
                cp_values = {
                    'picking_id': new_picking_id,
                    'product_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'product_uos_qty': line.quantity,
                    'product_uos': line.uom_id.id,
                    'prodlot_id': line.prodlot_id and line.prodlot_id.id,
                    'asset_id': line.asset_id and line.asset_id.id,
                    'composition_list_id': line.composition_list_id and line.composition_list_id.id,
                    'pt_created': True,
                    'backmove_id': line.move_id.id,
                    'pack_info_id': line.move_id.pack_info_id and line.move_id.pack_info_id.id or False,
                }
                context['keepLineNumber'] = True
                move_obj.copy(cr, uid, line.move_id.id, cp_values, context=context)
                context['keepLineNumber'] = False


            # Update initial stock moves
            for move_id, move_vals in move_data.iteritems():
                if move_vals['processed_qty'] > move_vals['initial_qty']:
                    raise osv.except_osv(
                        _('Error'),
                        _('Line %s :: You cannot processed more quantity than the quantity of the stock move - Maybe the line is already processed') % move_vals['line_number']
                    )
                initial_qty = max(move_vals['initial_qty'] - move_vals['processed_qty'], 0.00)
                wr_vals = {
                    'product_qty': initial_qty,
                    'proudct_uos_qty': initial_qty,
                    'processed_stock_move': True,
                }
                context['keepLineNumber'] = True
                move_obj.write(cr, uid, [move_id], wr_vals, context=context)
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


        # UF-2531: Run the creation of message at RW at some important points
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)


        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_picking_ticket', ['form', 'tree'], context=context)
        res['res_id'] = new_picking_id
        return res

    @check_cp_rw
    def validate_picking(self, cr, uid, ids, context=None):
        '''
        Open the wizard to validate the picking ticket
        '''
        # Objects
        proc_obj = self.pool.get('validate.picking.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]

        data = self.read(cr, uid, ids[0], ['state', 'type', 'subtype', 'name'], context=context)

        if data['type'] != 'out' or data['subtype'] != 'picking':
            raise osv.except_osv(
                _('Error'),
                _('%s is not a sub-pick !') % (data['name'])
            )
        if data['state'] != 'assigned':
            raise osv.except_osv(
                _('Error'),
                _('The picking ticket is not in \'Available\' state. Please check this and re-try')
            )

        # if wizard already exists, then open it (able save as draft/reset functionnality):
        wiz_ids = proc_obj.search(cr, uid, [('picking_id', 'in', ids), ('draft', '=', True)], context=context)
        if wiz_ids:
            processor_id = wiz_ids[0]
        else:
            processor_id = proc_obj.create(cr, uid, {'picking_id': ids[0]}, context=context)
            proc_obj.create_lines(cr, uid, processor_id, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'res_id': processor_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }

    def do_validate_picking(self, cr, uid, wizard_ids, context=None):
        '''
        Validate the picking ticket from selected stock moves

        Move here the logic of validate picking

        BE CAREFUL: the wizard_ids parameters is the IDs of the validate.picking.processor objects,
        not those of stock.picking objects
        '''
        # Objects
        date_tools = self.pool.get('date.tools')
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        proc_obj = self.pool.get('validate.picking.processor')
        usb_entity = self._get_usb_entity_type(cr, uid)

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        today = time.strftime(db_date_format)
        update_replicated_flag = self._get_usb_entity_type(cr, uid) == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False)

        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id

            if picking.state != 'assigned':
                raise osv.except_osv(
                    _('Error'),
                    _('The picking ticket is not in \'Available\' state. Please check this and re-try')
                )

            move_data = {}
            for move in picking.move_lines:
                if move.id not in move_data:
                    move_data.setdefault(move.id, {
                        'initial_qty': move.product_qty,
                        'processed_qty': 0.00,
                        'move': move,
                        'first': True,
                    })

            # Create the new ppl object
            # US-702: If the PPL is from RW, then add the suffix RW, if it is created via RW Sync in CP, then use the one from the context (name sent by RW instance)
            ppl_number = 'PPL/%s' % picking.name.split("/")[1]
            if context.get('rw_backorder_name', False):
                ppl_number = context.get('rw_backorder_name')
                del context['rw_backorder_name']
            elif usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False) and ppl_number:
                ppl_number = ppl_number + "-RW"
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
            if update_replicated_flag:
                self.write(cr, uid, new_ppl_id, {'already_replicated': False}, context=context)

            new_ppl = self.browse(cr, uid, new_ppl_id, context=context)
            context.update({
                'keep_prodlot': False,
                'allow_copy': False,
                'keepLineNumber': False,
            })

            # For each processed lines, save the processed quantity to update the draft picking ticket
            # and create a new line on PPL
            for line in wizard.move_ids:
                first = move_data[line.move_id.id]['first']

                orig_qty = line.move_id.product_qty
                if line.move_id.original_qty_partial and line.move_id.original_qty_partial != -1:
                    orig_qty = line.move_id.original_qty_partial

                if line.move_id.id not in move_data:
                    move_data.setdefault(line.move_id.id, {
                        'initial_qty': line.move_id.product_qty,
                        'processed_qty': 0.00,
                        'move': line.move_id,
                    })

                if line.uom_id.id != line.move_id.product_uom.id:
                    processed_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.move_id.product_uom.id)
                else:
                    processed_qty = line.quantity

                move_data[line.move_id.id]['processed_qty'] += processed_qty

                values = {
                    'product_qty': line.quantity,
                    'product_uos_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'product_uos': line.uom_id.id,
                    'prodlot_id': line.prodlot_id and line.prodlot_id.id,
                    'line_number': line.line_number,
                    'asset_id': line.asset_id and line.asset_id.id,
                    'composition_list_id': line.composition_list_id and line.composition_list_id.id,
                    'original_qty_partial': orig_qty,
                    'pack_info_id': line.move_id.pack_info_id and line.move_id.pack_info_id.id or False,
                }

                # Update or create the validate picking ticket line
                if first:
                    move_obj.write(cr, uid, [line.move_id.id], values, context=context)
                    move_data[line.move_id.id]['first'] = False
                else:
                    # Split happened during the validation
                    # Copy the stock move and set the quantity
                    values['state'] = 'assigned'
                    context.update({
                        'keepLineNumber': True,
                        'non_stock_noupdate': True,
                    })
                    move_obj.copy(cr, uid, line.move_id.id, values, context=context)
                    context.update({
                        'keepLineNumber': False,
                        'non_stock_noupdate': False,
                    })

                values.update({
                    'picking_id': new_ppl_id,
                    'initial_location': line.move_id.location_id.id,
                    'location_id': line.move_id.location_dest_id.id,
                    'location_dest_id': new_ppl.warehouse_id.lot_dispatch_id.id,
                    'date': today,
                    'date_expected': today,
                })
                context.update({
                    'keepLineNumber': True,
                    'non_stock_noupdate': True,
                })
                move_obj.copy(cr, uid, line.move_id.id, values, context=context)
                context.update({
                    'keepLineNumber': False,
                    'non_stock_noupdate': False,
                })

            # For each move, check if there is remaining quantity
            for move_vals in move_data.itervalues():
                # The quantity after the validation does not correspond to the picking ticket quantity
                # The difference is written back to draft picking ticket
                # Is positive if some quantity was removed during the validation -> draft quantity is increased
                # Is negative if some quantity was added during the validation -> draft quantity is decreased
                diff_qty = move_vals['initial_qty'] - move_vals['processed_qty']
                if diff_qty != 0.00:
                    # Original move from the draft picking ticket which will be updated
                    if move_vals['move'].backmove_id:  # 2531: Added a check to make sure the following code can be run correctly
                        original_move_id = move_vals['move'].backmove_id.id
                        original_vals = move_obj.browse(cr, uid, original_move_id, context=context)
                        if original_vals.product_uom.id != move_vals['move'].product_uom.id:
                            diff_qty = uom_obj._compute_qty(cr, uid, move_vals['move'].product_uom.id, diff_qty, original_vals.product_uom.id)
                        backorder_qty = max(original_vals.product_qty + diff_qty, 0)
                        if backorder_qty != 0.00:
                            move_obj.write(cr, uid, [original_move_id], {'product_qty': backorder_qty}, context=context)

                if move_vals['processed_qty'] == 0.00:
                    move_obj.write(cr, uid, [move_vals['move'].id], {'product_qty': 0.00}, context=context)

            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', new_ppl_id, 'button_confirm', cr)
            # simulate check assign button, as stock move must be available
            self.force_assign(cr, uid, [new_ppl_id])
            # trigger standard workflow for validated picking ticket
            self.action_move(cr, uid, [picking.id])
            wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)

            # UF-2377 set also this picking to become ready for sync back to the CP
            if update_replicated_flag:
                self.write(cr, uid, picking.id, {'already_replicated': False}, context=context)

            # if the flow type is in quick mode, we perform the ppl steps automatically
            if picking.flow_type == 'quick' and new_ppl:
                return self.quick_mode(cr, uid, new_ppl.id, context=context)

            self.infolog(cr, uid, "The Validated Picking Ticket id:%s (%s) has been validated" % (
                picking.id, picking.name,
            ))

        # UF-2531: Run the creation of message at RW at some important points
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'msf_outgoing.action_ppl', ['form', 'tree'], context=context)
        res['res_id'] = new_ppl and new_ppl.id or False
        return res

    def quick_mode(self, cr, uid, ids, context=None):
        """
        Perform the PPL steps automatically

        """
        # Objects
        proc_obj = self.pool.get('ppl.processor')

        if context is None:
            context = {}

        if not isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        wizard_id = self.ppl(cr, uid, ids, context=context)['res_id']
        proc_obj.do_ppl_step1(cr, uid, wizard_id, context=context)
        return proc_obj.do_ppl_step2(cr, uid, wizard_id, context=context)

    @check_cp_rw
    def ppl(self, cr, uid, ids, context=None):
        """
        Open the wizard to process the step 1 of the PPL
        """
        # Objects
        proc_obj = self.pool.get('ppl.processor')
        data_obj = self.pool.get('ir.model.data')

        if isinstance(ids, (int, long)):
            ids = [ids]

        data = self.read(cr, uid, ids[0], ['state', 'name', 'type', 'subtype'], context=context)

        if data['type'] != 'out' or data['subtype'] != 'ppl':
            raise osv.except_osv(
                _('Error'),
                _('The object %s is not a pre-packing list. Please check this and re-try.') % (data['name'])
            )

        if data['state'] != 'assigned':
            raise osv.except_osv(
                _('Error'),
                _('The pre-packing list is not in \'Available\' state. Please check this and re-try')
            )

        # search for an existing shipment saved as draft ... :
        wiz_ids = self.pool.get('ppl.processor').search(cr, uid, [('picking_id', 'in', ids), ('draft_step1', '=', True)], context=context)
        if wiz_ids:
            processor_id = wiz_ids[0]
        else:
            processor_id = proc_obj.create(cr, uid, {'picking_id': ids[0]}, context=context)
            proc_obj.create_lines(cr, uid, processor_id, context=context)

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step1_form_view')[1]

        return {
            'name': _('PPL Information - step 1'),
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'res_id': processor_id,
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }

    def do_ppl_step1(self, cr, uid, wizard_ids, context=None):
        """
        Open the wizard to process the step 2 of the PPL

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        """
        # Objects
        proc_obj = self.pool.get('ppl.processor')
        proc_line_obj = self.pool.get('ppl.move.processor')
        family_obj = self.pool.get('ppl.family.processor')

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process !'),
            )

        # Create the different pack families according to values in stock moves
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            if wizard.picking_id.state != 'assigned':
                raise osv.except_osv(
                    _('Error'),
                    _('The pre-packing list is not in \'Available\' state. Please check this and re-try')
                )

            if wizard.draft_step2:
                continue
            else:
                fam_ids = self.pool.get('ppl.family.processor').search(cr, uid, [('wizard_id', '=', wizard.id)], context=context)
                self.pool.get('ppl.family.processor').unlink(cr, uid, fam_ids, context=context)

            families_data = {}

            for line in wizard.move_ids:
                key = 'f%st%s' % (line.from_pack, line.to_pack)
                families_data.setdefault(key, {
                    'wizard_id': wizard.id,
                    'move_ids': [],
                    'from_pack': line.from_pack,
                    'to_pack': line.to_pack,
                })

                families_data[key]['move_ids'].append(line.id)

            for family_data in families_data.values():
                move_ids = family_data.get('move_ids', [])
                if 'move_ids' in family_data:
                    del family_data['move_ids']

                fam_id = family_obj.create(cr, uid, family_data)
                if move_ids:
                    proc_line_obj.write(cr, uid, move_ids, {'pack_id': fam_id}, context=context)

        return self.ppl_step2(cr, uid, wizard_ids, context)

    def ppl_step2(self, cr, uid, wizard_ids, context=None):
        """
        Open the wizard of the second step of PPL processing

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        """
        # Objects
        proc_obj = self.pool.get('ppl.processor')
        data_obj = self.pool.get('ir.model.data')

        view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step2_form_view')[1]

        return {
            'name': _('PPL Information - step 2'),
            'type': 'ir.actions.act_window',
            'res_model': proc_obj._name,
            'res_id': wizard_ids[0],
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def do_ppl_step2(self, cr, uid, wizard_ids, context=None):
        '''
        Create the Pack families and the shipment

        BE CAREFUL: the wizard_ids parameters is the IDs of the ppl.processor objects,
        not those of stock.picking objects
        '''
        # Objects
        proc_obj = self.pool.get('ppl.processor')
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        usb_entity = self._get_usb_entity_type(cr, uid)
        date_tools = self.pool.get('date.tools')
        db_datetime_format = date_tools.get_db_datetime_format(cr, uid, context=context)
        today = time.strftime(db_datetime_format)


        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        if not wizard_ids:
            raise osv.except_osv(
                _('Processing Error'),
                _('No data to process '),
            )

        pickings = {}
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            pickings.setdefault(picking.id, picking.name)

            if picking.state != 'assigned':
                raise osv.except_osv(
                    _('Error'),
                    _('The pre-packing list is not in \'Available\' state. Please check this and re-try')
                )

            moves_data = {}

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
            if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):  # RW Sync - set the replicated to True for not syncing it again
                self.write(cr, uid, new_packing_id, {'already_replicated': False}, context=context)

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
            }

            # Create the stock moves in the packing
            for family in wizard.family_ids:
                for line in family.move_ids:
                    move_to_copy = line.move_id.id

                    if line.uom_id.id != line.move_id.product_uom.id:
                        processed_qty = uom_obj._compute_qty(cr, uid, line.uom_id.id, line.quantity, line.move_id.product_uom.id)
                    else:
                        processed_qty = line.quantity

                    values = {
                        'product_qty': line.quantity,
                        'from_pack': family.from_pack,
                        'to_pack': family.to_pack,
                        'pack_type': family.pack_type and family.pack_type.id or False,
                        'length': family.length,
                        'width': family.width,
                        'height': family.height,
                        'weight': family.weight,
                    }

                    if line.move_id.id not in moves_data:
                        moves_data.setdefault(line.move_id.id, {
                            'line_number': line.move_id.line_number,
                            'initial_qty': line.move_id.product_qty,
                            'processed_qty': processed_qty,
                        })
                        move_obj.write(cr, uid, [line.move_id.id], values, context=context)

                    else:
                        # If already updated, we create a new stock move
                        moves_data[line.move_id.id]['processed_qty'] += processed_qty
                        # Force state to 'assigned'
                        values['state'] = 'assigned'
                        # Copy stock move
                        context.update({
                            'keepLineNumber': True,
                            'non_stock_noupdate': True,
                        })
                        move_to_copy = move_obj.copy(cr, uid, line.move_id.id, values, context=context)
                        context.update({
                            'keepLineNumber': False,
                            'non_stock_noupdate': False,
                        })

                    # Create a move line in the Packing
                    context.update({
                        'keepLineNumber': True,
                        'non_stock_noupdate': True,
                    })
                    move_obj.copy(cr, uid, move_to_copy, pack_move_data, context=context)
                    context.update({
                        'keepLineNumber': False,
                        'non_stock_noupdate': False,
                    })

            # Check quantities integrity status
            for m_data in moves_data.values():
                if m_data['initial_qty'] != m_data['processed_qty']:
                    raise osv.except_osv(
                        _('Processing Error'),
                        _('Line %(line_number)s: The sum of processed quantities %(processed_qty)s '\
                          'is not equal to the initial quantity of the stock move %(initial_qty)s.') % m_data
                    )
            # Trigger standard workflow on PPL
            self.action_move(cr, uid, [picking.id])
            wf_service.trg_validate(uid, 'stock.picking', picking.id, 'button_done', cr)

        '''
        This code can be set back to the old one, because the shipment should always be available at this stage!!!!! DUY
        '''
        shipment_id = False
        shipment_name = False
        if new_packing_id:
            obj = self.browse(cr, uid, new_packing_id, context)
            if obj and obj.shipment_id and obj.shipment_id.id:
                shipment_id = obj.shipment_id.id
                shipment_name = obj.shipment_id.name

                if context.get('rw_shipment_name', False) and context.get('sync_message_execution', False):  # RW Sync - update the shipment name same as on RW instance
                    new_name = context.get('rw_shipment_name')
                    if new_name != obj.shipment_id.name:
                        del context['rw_shipment_name']
                        self.pool.get('shipment').write(cr, uid, shipment_id, {'name': new_name}, context=context)
                    return
            else:
                raise Exception, "For some reason, there is no shipment created for the Packing list: " + obj.name

        # UF-2531: Run the creation of message at RW at some important points
        if usb_entity == self.REMOTE_WAREHOUSE and not context.get('sync_message_execution', False):
            self._manual_create_rw_messages(cr, uid, context=context)

        for pid, pname in pickings.iteritems():
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

        if isinstance(ids, (int, long)):
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

        return_info = {}

        if context is None:
            context = {}

        if isinstance(wizard_ids, (int, long)):
            wizard_ids = [wizard_ids]

        counter = 0
        for wizard in proc_obj.browse(cr, uid, wizard_ids, context=context):
            picking = wizard.picking_id
            draft_picking_id = picking.previous_step_id.backorder_id.id

            # get the linked "save as draft" create.picking.processor wizard if has:
            picking_processor_wiz = []
            if draft_picking_id:
                picking_processor_wiz = self.pool.get('create.picking.processor').search(cr, uid, [
                    ('picking_id', '=', draft_picking_id),
                    ('draft', '=', True),
                ], context=context)
                if picking_processor_wiz:
                    picking_processor_wiz = self.pool.get('create.picking.processor').browse(cr, uid, picking_processor_wiz[0], context=context)

            # get the linked "save as draft" ppl.processor wizard if has:
            ppl_processor_wiz = self.pool.get('ppl.processor').search(cr, uid, [
                ('picking_id', '=', picking.id),
                '|', ('draft_step1', '=', True),
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

                # UF-2531: Store some important info for the return pack messages
                return_info.setdefault(str(counter), {
                    'name': picking.previous_step_id.backorder_id.name,
                    'returned_quantity': return_qty,
                    'line_number': line.line_number,
                    'ordered_quantity': line.ordered_quantity,
                })
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

                # Increase the draft move with the returned quantity
                draft_move_id = line.move_id.backmove_id.id
                draft_move_qty = move_obj.read(cr, uid, [draft_move_id], ['product_qty'], context=context)[0]['product_qty']
                draft_move_qty += return_qty
                move_obj.write(cr, uid, [draft_move_id], {'product_qty': draft_move_qty}, context=context)

                # Update or create "save as draft" lines with returned qty:
                if picking_processor_wiz:
                    save_as_draft_move = self.pool.get('create.picking.move.processor').search(cr, uid, [
                        ('wizard_id', '=', picking_processor_wiz.id),
                        ('move_id', '=', draft_move_id),
                    ], context=context)
                    if not save_as_draft_move:  # then create the SaD line:
                        move_data = self.pool.get('create.picking.move.processor')._get_line_data(cr, uid, wizard=picking_processor_wiz, move=line.move_id.backmove_id, context=context)
                        move_data.update({'quantity': return_qty})
                        save_as_draft_move = self.pool.get('create.picking.move.processor').create(cr, uid, move_data, context=context)
                        save_as_draft_move = [save_as_draft_move]
                    else:  # update Sad line
                        for sad_move in self.pool.get('create.picking.move.processor').browse(cr, uid, save_as_draft_move, context=context):
                            self.pool.get('create.picking.move.processor').write(cr, uid, sad_move.id, {
                                'ordered_quantity': sad_move.ordered_quantity + return_qty,
                                'quantity': sad_move.quantity + return_qty,
                            }, context=context)

                if ppl_processor_wiz:
                    sad_move = self.pool.get('ppl.move.processor').search(cr, uid, [
                        ('wizard_id', '=', ppl_processor_wiz.id),
                        ('move_id', '=', line.move_id.id),
                    ], context=context)
                    if sad_move:
                        if ppl_processor_wiz.draft_step1 or ppl_processor_wiz.draft_step2:
                            remaining_qty_to_return = return_qty
                            for sad_move in self.pool.get('ppl.move.processor').browse(cr, uid, sad_move, context=context):
                                if remaining_qty_to_return <= 0:
                                    break
                                if sad_move.quantity > remaining_qty_to_return:
                                    self.pool.get('ppl.move.processor').write(cr, uid, [sad_move.id], {
                                        'quantity': sad_move.quantity - remaining_qty_to_return,
                                    }, context=context)
                                    remaining_qty_to_return = 0
                                else: # sad_move.quantity <= remaining_qty_to_return
                                    self.pool.get('ppl.move.processor').unlink(cr, uid, [sad_move.id], context=context)
                                    remaining_qty_to_return -= sad_move.quantity

                            if ppl_processor_wiz.draft_step2:
                                self.pool.get('ppl.processor').write(cr, uid, [ppl_processor_wiz.id], {'draft_step2': False})

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

        # UF-2531: Create manually the message for the return pack of the ship
        self._manual_create_rw_picking_message(cr, uid, picking.id, return_info, 'usb_picking_return_products', context=context)

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
                        if not move_obj.search_exist(cr, uid, [('purchase_line_id', '=', stock_move.purchase_line_id.id), ('state', 'not in', ['cancel', 'cancel_r', 'done'])], context=context):
                            # all in lines processed for this po line
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

                # get the linked "save as draft" wizard if has:
                picking_processor_wiz = self.pool.get('create.picking.processor').search(cr, uid, [
                    ('picking_id', '=', draft_picking_id),
                    ('draft', '=', True),
                ], context=context)
                if picking_processor_wiz:
                    picking_processor_wiz = self.pool.get('create.picking.processor').browse(cr, uid, picking_processor_wiz[0], context=context)

                # for each move from picking ticket - could be split moves
                for move in picking.move_lines:
                    # find the corresponding move in draft
                    draft_move = move.backmove_id
                    if draft_move:
                        # increase the draft move with the move quantity
                        initial_qty = move_obj.read(cr, uid, [draft_move.id], ['product_qty'], context=context)[0]['product_qty']
                        initial_qty += move.product_qty
                        move_obj.write(cr, uid, [draft_move.id], {'product_qty': initial_qty}, context=context)

                        # Update or create "save as draft" lines with returned qty:
                        if picking_processor_wiz:
                            save_as_draft_move = self.pool.get('create.picking.move.processor').search(cr, uid, [
                                ('wizard_id', '=', picking_processor_wiz.id),
                                ('move_id', '=', draft_move.id),
                            ], context=context)
                            if not save_as_draft_move:  # then create the SaD line:
                                move_data = self.pool.get('create.picking.move.processor')._get_line_data(cr, uid, wizard=picking_processor_wiz, move=move, context=context)
                                move_data.update({'quantity': move.product_qty})
                                save_as_draft_move = self.pool.get('create.picking.move.processor').create(cr, uid, move_data, context=context)
                                save_as_draft_move = [save_as_draft_move]
                            else:  # update Sad line
                                for sad_move in self.pool.get('create.picking.move.processor').browse(cr, uid, save_as_draft_move, context=context):
                                    self.pool.get('create.picking.move.processor').write(cr, uid, sad_move.id, {
                                        'ordered_quantity': sad_move.ordered_quantity + move.product_qty,
                                        'quantity': sad_move.quantity + move.product_qty,
                                    }, context=context)

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

stock_picking()


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
            # if there are already additional items on the shipment we show them in the wizard
            if (name, model, step) == ('Create Shipment', 'shipment.wizard', 'create'):
                vals['product_moves_shipment_additionalitems'] = []
                for s in self.pool.get('shipment').read(cr, uid, ids, ['additional_items_ids']):
                    additionalitems_ids = s['additional_items_ids']
                    for additionalitem in self.pool.get('shipment.additionalitems').read(cr, uid, additionalitems_ids):
                        additionalitem['additional_item_id'] = additionalitem['id']
                        additionalitem.pop('id')
                        additionalitem.pop('shipment_id')
                        vals['product_moves_shipment_additionalitems'].append((0, 0, additionalitem))

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

class stock_move(osv.osv):
    '''
    stock move
    '''
    _inherit = 'stock.move'

    def _product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        facade for product_available function from product (stock)
        '''
        # get the corresponding product ids
        result = {}
        for d in self.read(cr, uid, ids, ['product_id'], context):
            result[d['id']] = d['product_id'][0]

        # get the virtual stock identified by product ids
        virtual = self.pool.get('product.product')._product_available(cr, uid, result.values(), field_names, arg, context)

        # replace product ids by corresponding stock move id
        result = dict([move_id, virtual[result[move_id]]] for move_id in result.keys())
        return result

    def _get_qty_per_pack(self, cr, uid, ids, field, arg, context=None):
        result = {}
        for move in self.read(cr, uid, ids, ['to_pack', 'from_pack', 'product_qty'], context=context):
            result[move['id']] = 0.0
            # number of packs with from/to values (integer)
            if move['to_pack'] == 0:
                num_of_packs = 0
            else:
                num_of_packs = move['to_pack'] - move['from_pack'] + 1
                if num_of_packs:
                    result[move['id']] = move['product_qty'] / num_of_packs
                else:
                    result[move['id']] = 0
        return result

    def _get_num_of_pack(self, cr, uid, ids, field, arg, context=None):
        result = {}
        for move in self.read(cr, uid, ids, ['to_pack', 'from_pack'], context=context):
            result[move['id']] = 0
            # number of packs with from/to values (integer)
            if move['to_pack'] == 0:
                num_of_packs = 0
            else:
                num_of_packs = move['to_pack'] - move['from_pack'] + 1
            result[move['id']] = num_of_packs
        return result

    def _get_danger(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        product_obj = self.pool.get('product.product')
        for move in self.read(cr, uid, ids, ['product_id'], context=context):
            default_values = {
                'is_dangerous_good': '',
                'is_keep_cool': '',
                'is_narcotic': '',
            }
            result[move['id']] = default_values
            if move['product_id']:
                product = product_obj.read(cr, uid, move['product_id'][0],
                                           ['dg_txt', 'kc_txt', 'cs_txt'], context=context)
            result[move['id']]['is_dangerous_good'] = move['product_id'] and product['dg_txt'] or ''
            # keep cool - if heat_sensitive_item is True
            result[move['id']]['is_keep_cool'] = move['product_id'] and product['kc_txt'] or ''
            # narcotic
            result[move['id']]['is_narcotic'] = move['product_id'] and product['cs_txt'] or ''
        return result


    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        uom_obj = self.pool.get('product.uom')
        for move in self.read(cr, uid, ids,
                              ['sale_line_id', 'product_uom', 'to_pack', 'from_pack', 'product_qty'],
                              context=context):
            default_values = {
                'total_amount': 0.0,
                'amount': 0.0,
                'currency_id': False,
                'num_of_packs': 0,
                'sale_order_line_number': 0,
            }
            result[move['id']] = default_values
            # quantity per pack
            # total amount (float)
            total_amount = 0.0
            if move['sale_line_id']:
                sol_obj = self.pool.get('sale.order.line')
                sale_line = sol_obj.read(cr, uid, move['sale_line_id'][0],
                                         ['product_uom', 'currency_id', 'price_unit'], context=context)
                total_amount = sale_line['price_unit'] * move['product_qty'] or 0.0
                total_amount = uom_obj._compute_price(cr, uid, sale_line['product_uom'][0], total_amount, move['product_uom'][0])
            result[move['id']]['total_amount'] = total_amount
            # amount for one pack
            if move['to_pack'] == 0:
                num_of_packs = 0
            else:
                num_of_packs = move['to_pack'] - move['from_pack'] + 1
            result[move['id']]['num_of_packs'] = num_of_packs
            if num_of_packs:
                amount = total_amount / num_of_packs
            else:
                amount = 0
            result[move['id']]['amount'] = amount
            result[move['id']]['currency_id'] = move['sale_line_id'] and sale_line['currency_id'] and sale_line['currency_id'][0] or False
        return result

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set default values according to type and subtype
        '''
        if not context:
            context = {}

        res = super(stock_move, self).default_get(cr, uid, fields, context=context)

        warehouse_obj = self.pool.get('stock.warehouse')
        partner_id = context.get('partner_id')
        auto_company = False
        if partner_id:
            cp_partner_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id
            auto_company = cp_partner_id == partner_id

        if 'warehouse_id' in context and context.get('warehouse_id'):
            warehouse_id = context.get('warehouse_id')
        else:
            warehouse_id = warehouse_obj.search(cr, uid, [], context=context)[0]
        if not auto_company:
            res.update({'location_output_id': warehouse_obj.read(cr, uid,
                                                                 warehouse_id, ['lot_output_id'], context=context)['lot_output_id'][0]})

        loc_virtual_ids = self.pool.get('stock.location').search(cr, uid, [('name', '=', 'Virtual Locations')])
        loc_virtual_id = len(loc_virtual_ids) > 0 and loc_virtual_ids[0] or False
        res.update({'location_virtual_id': loc_virtual_id})

        if 'type' in context and context.get('type', False) == 'out':
            loc_stock_id = warehouse_obj.read(cr, uid,
                                              warehouse_id, ['lot_stock_id'], context=context)['lot_stock_id'][0]
            res.update({'location_id': loc_stock_id})

        if 'subtype' in context and context.get('subtype', False) == 'picking':
            loc_packing_id = warehouse_obj.read(cr, uid, warehouse_id,
                                                ['lot_packing_id'], context=context)['lot_packing_id'][0]
            res.update({'location_dest_id': loc_packing_id})
        elif 'subtype' in context and context.get('subtype', False) == 'standard' and not auto_company:
            loc_output_id = warehouse_obj.read(cr, uid, warehouse_id,
                                               ['lot_output_id'], context=context)['lot_output_id'][0]
            res.update({'location_dest_id': loc_output_id})

        return res

    def _get_pick_shipment_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Link the shipment where a stock move is to this stock move
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        res = {}
        for move in self.browse(cr, uid, ids, fields_to_fetch=['picking_id'], context=context):
            res[move.id] = False
            if move.picking_id and move.picking_id.shipment_id:
                res[move.id] = move.picking_id.shipment_id.id

        return res

    def _get_picking(self, cr, uid, ids, context=None):
        """
        Return the list of stock.move to update
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        picking_ids = self.pool.get('stock.picking').search(cr, uid, [('id', 'in', ids), ('shipment_id', '!=', False)], order='NO_ORDER', context=context)
        return self.pool.get('stock.move').search(cr, uid, [('picking_id', 'in', picking_ids)], order='NO_ORDER', context=context)

    _columns = {'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                'ppl_returned_ok': fields.boolean(string='Has been returned ?', readonly=True, internal=True),
                'pack_type': fields.many2one('pack.type', string='Pack Type'),
                'length': fields.float(digits=(16, 2), string='Length [cm]'),
                'width': fields.float(digits=(16, 2), string='Width [cm]'),
                'height': fields.float(digits=(16, 2), string='Height [cm]'),
                'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
                # 'pack_family_id': fields.many2one('pack.family', string='Pack Family'),
                'initial_location': fields.many2one('stock.location', string='Initial Picking Location'),
                # relation to the corresponding move from draft **picking** ticket object
                'backmove_id': fields.many2one('stock.move', string='Corresponding move of previous step'),
                # relation to the corresponding move from draft **packing** ticket object
                'backmove_packing_id': fields.many2one('stock.move', string='Corresponding move of previous step in draft packing'),
                # functions
                'virtual_available': fields.function(_product_available, method=True, type='float', string='Virtual Stock', help="Future stock for this product according to the selected locations or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming.", multi='qty_available', digits_compute=dp.get_precision('Product UoM')),
                'qty_per_pack': fields.function(_get_qty_per_pack, method=True, type='float', string='Qty p.p'),
                'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', digits_compute=dp.get_precision('Picking Price'), multi='get_vals',),
                'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', digits_compute=dp.get_precision('Picking Price'), multi='get_vals',),
                'num_of_packs': fields.function(_get_num_of_pack, method=True, type='integer', string='#Packs'),  # old_multi get_vals
                'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
                'is_dangerous_good': fields.function(_get_danger, method=True, type='char', size=8, string='Dangerous Good', multi='get_danger'),
                'is_keep_cool': fields.function(_get_danger, method=True, type='char', size=8, string='Keep Cool', multi='get_danger',),
                'is_narcotic': fields.function(_get_danger, method=True, type='char', size=8, string='CS', multi='get_danger',),
                'sale_order_line_number': fields.function(_vals_get,
                                                          method=True, type='integer', string='Sale Order Line Number',
                                                          multi='get_vals_integer',),  # old_multi get_vals
                'pick_shipment_id': fields.function(
                    _get_pick_shipment_id,
                    method=True,
                    type='many2one',
                    relation='shipment',
                    string='Shipment',
                    store={
                        'stock.move': (lambda obj, cr, uid, ids, c={}: ids, ['picking_id'], 10),
                        'stock.picking': (_get_picking, ['shipment_id'], 10),
                    }
    ),
        # Fields used for domain
        'location_virtual_id': fields.many2one('stock.location', string='Virtual location'),
        'location_output_id': fields.many2one('stock.location', string='Output location'),
        'invoice_line_id': fields.many2one('account.invoice.line', string='Invoice line'),
        'pt_created': fields.boolean(string='PT created'),
        'not_shipped': fields.boolean(string='Not shipped'),
    }

    def copy(self, cr, uid, copy_id, values=None, context=None):
        if context is None:
            context = {}

        if values is None:
            values = {}

        if not 'pt_created' in values:
            values['pt_created'] = False

        return super(stock_move, self).copy(cr, uid, copy_id, values, context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        '''
            Confirm or check the procurement order associated to the stock move
        '''
        pol_obj = self.pool.get('purchase.order.line')
        pick_obj = self.pool.get('stock.picking')
        sol_obj = self.pool.get('sale.order.line')
        uom_obj = self.pool.get('product.uom')
        solc_obj = self.pool.get('sale.order.line.cancel')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        move_to_done = []
        pick_to_check = set()

        for move in self.browse(cr, uid, ids, context=context):
            if move.product_qty == 0.00:
                move_to_done.append(move.id)
            """
            A stock move can be re-sourced but there are some conditions

            Re-sourcing checking :
              1) The move should be attached to a picking
              2) The move should have the flag 'has_to_be_resourced' set
              3) The move shouldn't be already canceled
              4) The move should be linked to a purchase order line or a field
                 order line
            """
            if not move.picking_id:
                continue

            if move.state == 'cancel':
                continue

            pick_type = move.picking_id.type
            pick_subtype = move.picking_id.subtype
            pick_state = move.picking_id.state
            subtype_ok = pick_type == 'out' and (pick_subtype == 'standard' or (pick_subtype == 'picking' and pick_state == 'draft'))

            if pick_subtype == 'picking' and pick_state == 'draft':
                pick_to_check.add(move.picking_id.id)
                pick_obj._create_sync_message_for_field_order(cr, uid, move.picking_id, context=context)

            if pick_type == 'in' and move.purchase_line_id:
                # cancel the linked PO line partially or fully:
                resource = move.has_to_be_resourced or move.picking_id.has_to_be_resourced or context.get('do_resource', False)
                pol_product_qty = self.pool.get('purchase.order.line').read(cr, uid, move.purchase_line_id.id, ['product_qty'])['product_qty'] # because value in move.purchase_line_id.product_qty has changed since
                partially_cancelled = False
                if pol_product_qty - move.product_qty != 0:
                    new_line = self.pool.get('purchase.order.line').cancel_partial_qty(cr, uid, [move.purchase_line_id.id], cancel_qty=move.product_qty, resource=resource, context=context)
                    self.write(cr, uid, [move.id], {'purchase_line_id': new_line}, context=context)
                    partially_cancelled = True
                else:
                    signal = 'cancel_r' if resource else 'cancel'
                    wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.id, signal, cr)

                sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [move.purchase_line_id.id], context=context)
                for sol in sol_obj.browse(cr, uid, sol_ids, context=context):
                    # If the line will be sourced in another way, do not cancel the OUT move
                    if solc_obj.search(cr, uid, [('fo_sync_order_line_db_id', '=', sol.sync_order_line_db_id), ('resource_sync_line_db_id', '!=', False)],
                                       limit=1, order='NO_ORDER', context=context):
                        continue

                    diff_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, sol.product_uom.id)
                    if move.picking_id.partner_id2.partner_type not in ['internal', 'section', 'intermission'] and not partially_cancelled:
                        sol_obj.update_or_cancel_line(cr, uid, sol.id, diff_qty, resource=resource, context=context)
                    # Cancel the remaining OUT line
                    if diff_qty < sol.product_uom_qty:
                        data_back = self.create_data_back(move)
                        out_move = self.get_mirror_move(cr, uid, [move.id], data_back, context=context)[move.id]
                        out_move_id = False
                        if out_move['moves']:
                            out_move_id = sorted(out_move['moves'], key=lambda x: abs(x.product_qty - diff_qty))[0].id
                        elif out_move['move_id']:
                            out_move_id = out_move['move_id']

                        if out_move_id:
                            context.setdefault('not_resource_move', []).append(out_move_id)
                            self.action_cancel(cr, uid, [out_move_id], context=context)

                not_done_moves = self.pool.get('stock.move').search(cr, uid, [
                    ('purchase_line_id', '=', move.purchase_line_id.id),
                    ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                    ('picking_id.type', '=', 'in'),
                ], context=context)
                if not not_done_moves:
                    # all in lines processed or will be processed for this po line
                    wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.id, 'done', cr)

                if move.purchase_line_id.is_line_split and move.purchase_line_id.original_line_id:
                    # check if the original PO line can be set to done
                    not_done_moves = self.pool.get('stock.move').search(cr, uid, [
                        ('purchase_line_id', '=', move.purchase_line_id.original_line_id.id),
                        ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                        ('picking_id.type', '=', 'in'),
                    ], context=context)
                    if not not_done_moves:
                        # all in lines processed or will be processed for this po line
                        wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.original_line_id.id, 'done', cr)

                self.pool.get('purchase.order.line').update_fo_lines(cr, uid, [move.purchase_line_id.id], context=context)

            elif move.sale_line_id and (pick_type == 'internal' or (pick_type == 'out' and subtype_ok)):
                resource = move.has_to_be_resourced or move.picking_id.has_to_be_resourced or False
                diff_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.sale_line_id.product_uom.id)
                if diff_qty:
                    if move.id not in context.get('not_resource_move', []):
                        has_linked_pol = self.pool.get('purchase.order.line').search_exist(cr, uid, [('linked_sol_id', '=', move.sale_line_id.id)], context=context)
                        if has_linked_pol:
                            context['sol_done_instead_of_cancel'] = True
                        sol_obj.update_or_cancel_line(cr, uid, move.sale_line_id.id, diff_qty, resource=resource, context=context)
                        if has_linked_pol:
                            context.pop('sol_done_instead_of_cancel')

        self.action_done(cr, uid, move_to_done, context=context)

        # Search only non unlink move
        ids = self.search(cr, uid, [('id', 'in', ids)])
        res = super(stock_move, self).action_cancel(cr, uid, ids, context=context)
        for ptc in pick_obj.browse(cr, uid, list(pick_to_check), context=context):
            if ptc.subtype == 'picking' and ptc.state == 'draft' and not pick_obj.has_picking_ticket_in_progress(cr, uid, [ptc.id], context=context)[ptc.id] and all(m.state == 'cancel' or m.product_qty == 0.00 for m in ptc.move_lines):
                moves_to_done = self.search(cr, uid, [('picking_id', '=', ptc.id), ('product_qty', '=', 0.00), ('state', 'not in', ['done', 'cancel'])], context=context)
                if moves_to_done:
                    self.action_done(cr, uid, moves_to_done, context=context)
                ptc.action_done(context=context)

        return res

    def update_linked_documents(self, cr, uid, ids, new_id, context=None):
        '''
        Update the linked documents of a stock move to another one
        '''
        context = context or {}
        ids = isinstance(ids, (int, long)) and [ids] or ids

        for move_id in ids:
            proc_ids = self.pool.get('procurement.order').search(cr, uid, [('move_id', '=', move_id)], context=context)
            if proc_ids:
                self.pool.get('procurement.order').write(cr, uid, proc_ids, {'move_id': new_id}, context=context)

            pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('move_dest_id', '=', move_id)], context=context)
            if pol_ids:
                self.pool.get('purchase.order.line').write(cr, uid, pol_ids, {'move_dest_id': new_id}, context=context)

            move_dest_ids = self.search(cr, uid, [('move_dest_id', '=', move_id)], context=context)
            if move_dest_ids:
                self.write(cr, uid, move_dest_ids, {'move_dest_id': new_id}, context=context)

            backmove_ids = self.search(cr, uid, [('backmove_id', '=', move_id)], context=context)
            if backmove_ids:
                self.write(cr, uid, backmove_ids, {'backmove_id': new_id}, context=context)

            pack_backmove_ids = self.search(cr, uid, [('backmove_packing_id', '=', move_id)], context=context)
            if pack_backmove_ids:
                self.write(cr, uid, pack_backmove_ids, {'backmove_packing_id': new_id}, context=context)

        return True


stock_move()


class pack_family_memory(osv.osv):
    '''
    dynamic memory object for pack families
    '''
    _name = 'pack.family.memory'
    _order = 'sale_order_id, from_pack, id'

    _auto = False
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'pack_family_memory')
        cr.execute('''create or replace view pack_family_memory as (
            select
                min(m.id) as id,
                p.shipment_id as shipment_id,
                to_pack as to_pack,
                array_agg(m.id) as move_lines,
                min(from_pack) as from_pack,
                case when to_pack=0 then 0 else to_pack-min(from_pack)+1 end as num_of_packs,
                p.sale_id as sale_order_id,
                case when p.subtype = 'ppl' then p.id else p.previous_step_id end as ppl_id,
                min(m.length) as length,
                min(m.width) as width,
                min(m.height) as height,
                min(m.weight) as weight,
                min(m.state) as state,
                min(m.location_id) as location_id,
                min(m.location_dest_id) as location_dest_id,
                min(m.pack_type) as pack_type,
                p.id as draft_packing_id,
                p.description_ppl as description_ppl,
                '_name'::varchar(5) as name,
                min(pl.currency_id) as currency_id,
                sum(sol.price_unit * m.product_qty) as total_amount,
                bool_and(m.not_shipped) as not_shipped,
                ''::varchar(1) as comment
            from stock_picking p
            inner join stock_move m on m.picking_id = p.id and m.state != 'cancel' and m.product_qty > 0
            left join sale_order so on so.id = p.sale_id
            left join sale_order_line sol on sol.id = m.sale_line_id
            left join product_pricelist pl on pl.id = so.pricelist_id
            where p.shipment_id is not null
            group by p.shipment_id, p.description_ppl, to_pack, sale_id, p.subtype, p.id, p.previous_step_id
    )
    ''')

    def change_description(self, cr, uid, ids, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]

        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'msf_outgoing',
                                           'view_change_desc_wizard')
        pack_obj = self.read(cr, uid, ids, ['draft_packing_id'], context=context)
        for pack in pack_obj:
            res_id = pack['draft_packing_id'][0]
            return {
                'name': 'Change description',
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

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        compute_moves = not fields or 'move_lines' in fields
        for pf_memory in self.read(cr, uid, ids, ['num_of_packs',
                                                  'total_amount', 'weight', 'length', 'width', 'height', 'state'],
                                   context=context):
            values = {
                'amount': 0.0,
                'total_weight': 0.0,
                'total_volume': 0.0,
            }
            if compute_moves:
                values['move_lines'] = []
            num_of_packs = pf_memory['num_of_packs']
            if num_of_packs:
                values['amount'] = pf_memory['total_amount'] / num_of_packs
            values['total_weight'] = pf_memory['weight'] * num_of_packs
            values['total_volume'] = round((pf_memory['length'] * pf_memory['width'] * pf_memory['height'] * num_of_packs) / 1000.0, 4)
            values['fake_state'] = pf_memory['state']

            result[pf_memory['id']] = values

        if compute_moves and ids:
            if isinstance(ids, (int, long)):
                ids = [ids]

            cr.execute('select id, move_lines from ' + self._table + ' where id in %s', (tuple(ids),))  # not_a_user_entry
            for q_result in cr.fetchall():
                result[q_result[0]]['move_lines'] = q_result[1] or []
        return result

    _columns = {
        'name': fields.char(string='Reference', size=1024),
        'shipment_id': fields.many2one('shipment', string='Shipment'),
        'draft_packing_id': fields.many2one('stock.picking', string="Draft Packing Ref"),
        'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
        'ppl_id': fields.many2one('stock.picking', string="PPL Ref"),
        'from_pack': fields.integer(string='From p.'),
        'to_pack': fields.integer(string='To p.'),
        'pack_type': fields.many2one('pack.type', string='Pack Type'),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        # functions
        'move_lines': fields.function(_vals_get, method=True, type='one2many', relation='stock.move', string='Stock Moves', multi='get_vals',),
        'fake_state': fields.function(_vals_get, method=True, type='char', String='Fake state', multi='get_vals'),
        'state': fields.selection(selection=[
            ('draft', 'Draft'),
            ('assigned', 'Available'),
            ('stock_return', 'Returned to Stock'),
            ('ship_return', 'Returned from Shipment'),
            ('cancel', 'Cancelled'),
            ('done', 'Closed'), ], string='State'),
        'location_id': fields.many2one('stock.location', string='Src Loc.'),
        'location_dest_id': fields.many2one('stock.location', string='Dest. Loc.'),
        'total_amount': fields.float('Total Amount'),
        'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', multi='get_vals',),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'num_of_packs': fields.integer('#Packs'),
        'total_weight': fields.function(_vals_get, method=True, type='float', string='Total Weight[kg]', multi='get_vals',),
        'total_volume': fields.function(_vals_get, method=True, type='float', string=u'Total Volume[dm³]', multi='get_vals',),
        'description_ppl': fields.char('Description', size=256),
        'not_shipped': fields.boolean(string='Not shipped'),
        'comment': fields.char(string='Comment', size=1024)
    }

    _defaults = {
        'shipment_id': False,
        'draft_packing_id': False,
    }

pack_family_memory()


class procurement_order(osv.osv):
    '''
    procurement order workflow
    '''
    _inherit = 'procurement.order'

    def _hook_check_mts_on_message(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the _check_make_to_stock_product method from procurement>procurement.py>procurement.order

        - allow to modify the message written back to procurement order
        '''
        message = super(procurement_order, self)._hook_check_mts_on_message(cr, uid, context=context, *args, **kwargs)
        procurement = kwargs['procurement']
        if procurement.move_id.picking_id.state == 'draft' and procurement.move_id.picking_id.subtype == 'picking':
            message = _("Shipment Process in Progress.")
        return message

procurement_order()
