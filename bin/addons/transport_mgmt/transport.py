# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
import time
#import decimal_precision as dp
from tools.translate import _
from tools.misc import get_fake

class transport_order_fees(osv.osv):
    _name = 'transport.order.fees'
    _description = 'Fees'

    _order = 'name, id'

    _columns = {
        'name': fields.selection([
            ('customes_clearance', 'Customs Clearance Fees'),
            ('preclearance_cargo', 'Preclearance fees per cargo'),
            ('direct', 'Direct Taxes / Duties per cargo'),
            ('indirect', 'Other indirect taxes / fess per cargo'),
            ('handling', 'Handling Fees'),
            ('bonded_wh', 'Customs Bonded (warehousing) fees per cargo'),
            ('bonded_ex_wh', 'Customs Bonded (ex-warehousing) fees per cargo'),
            ('bonded_storage', 'Bonded storage fees'),
            ('storage', 'Storage Fees'),
        ], 'Type', add_empty=True, required=1),
        'value': fields.float('Cost', decimal=(16,2), required=1),
        'currency_id': fields.many2one('res.currency', 'Currency', required=1, domain=[('active', '=', True)]),
        'details': fields.char('Details', size=512),
        'validated': fields.boolean('Validated', readonly=1),
        'transport_out_id': fields.many2one('transport.order.out', 'OTO', select=1),
        'transport_in_id': fields.many2one('transport.order.in', 'OTO', select=1),
    }

    _default = {
        'validated': False,
    }

    def button_validate_fees(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'validated': True}, context=context)
        return True

transport_order_fees()

class transport_order_step(osv.osv):
    _name = 'transport.order.step'
    _description = 'Steps'

    _order = 'name desc, id'

    _columns = {
        'name': fields.date('Date', required=1),
        'step_id': fields.many2one('transport.step', 'Step', required=1),
        'transport_out_id': fields.many2one('transport.order.out', 'OTO', select=1),
        'transport_in_id': fields.many2one('transport.order.in', 'OTO', select=1),
    }

transport_order_step()



class transport_order(osv.osv):
    _name = 'transport.order'
    _description = 'Transport'
    _order = 'id desc'

    def _get_total(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for _id in ids:
            res[_id] = {
                'cargo_weight': 0,
                'cargo_volume': 0,
                'cargo_parcels': 0,
            }
        return res

    _columns = {
        'name': fields.char('Reference', size=64, required=True, select=True, readonly=True, copy=False),
        'original_cargo_ref': fields.char('Original Cargo ref', size=256, select=True),
        'shipment_type': fields.selection([('in', 'Inbound'), ('out', 'Outbound')], 'Shipment Type', required=True, readonly=True),
        'shipment_flow': fields.selection([('single', 'Single'), ('multi', 'Multileg')], 'Shipment Flow'),
        'zone_type': fields.selection([('int', 'International'), ('regional', 'Regional'),('local', 'Local')], 'Zone Type', required=True, add_empty=True),
        'cargo_category': fields.selection([('medical', 'Medical'), ('log', 'Logistic'), ('service', 'Service'), ('mixed', 'Mixed')], 'Cargo Type', required=True, add_empty=True),
        'creation_date': fields.date('Creation Date'),
        'ship_ref': fields.char('Ship Reference', size=256, select=True),
        #'linked_transport_id': # TODO m2o vs free text
        'details': fields.char('Details', size=1024),
        'notes': fields.text('Notes'),


        'transport_partner_id': fields.many2one('res.partner', 'Transporter', domain=[('transporter', '=', True)], select=1, ondelete='restrict'),
        'transport_mode': fields.selection([('air', 'Air'), ('air_charter', 'Air Charter'), ('sea', 'Sea'), ('road', 'Road'), ('msf_vehicle', 'MSF Vehicle'), ('train', 'Train'), ('boat', 'Boat'), ('hand','Hand carry')], 'Transport Mode'),

        'transit_departure_date': fields.date('Transit Location Date of Departure'),
        'transit_arrival_planned_date': fields.date('Transit Location Planned Arrival Date'),

        'post_transport_partner_id': fields.many2one('res.partner', 'Post Transit Transporter', domain=[('transporter', '=', True)], select=1, ondelete='restrict'),
        'post_transport_mode': fields.selection([('air', 'Air'), ('air_charter', 'Air Charter'), ('sea', 'Sea'), ('road', 'Road'), ('msf_vehicle', 'MSF Vehicle'), ('train', 'Train'), ('boat', 'Boat'), ('hand','Hand carry')], 'Post Transit Transport Mode'),

        'post2_transport_partner_id': fields.many2one('res.partner', 'Post Transit 2nd Transporter', domain=[('transporter', '=', True)], select=1, ondelete='restrict'),
        'post2_transport_mode': fields.selection([('air', 'Air'), ('air_charter', 'Air Charter'), ('sea', 'Sea'), ('road', 'Road'), ('msf_vehicle', 'MSF Vehicle'), ('train', 'Train'), ('boat', 'Boat'), ('hand','Hand carry')], 'Post Transit 2nd Transport Mode'),

        'transport_po_id': fields.many2one('purchase.order', 'Transport PO', domain=[('categ', '=', 'transport')]),

        'supplier_partner_id': fields.many2one('res.partner', 'Supplier Partner', domain=[('supplier', '=', True)], select=1, ondelete='restrict'),
        'supplier_address_id': fields.many2one('res.partner.address', 'Supplier Address', select=1, ondelete='restrict'),

        'transit_partner_id': fields.many2one('res.partner', 'Ships Via', select=1, ondelete='restrict', left='JOIN'),
        'transit_address_id': fields.many2one('res.partner.address', ' Transit Address', select=1, ondelete='restrict'),

        'customer_partner_id': fields.many2one('res.partner', 'Customer Partner', domain=[('customer', '=', True)], select=1, ondelete='restrict', left='JOIN'),
        'customer_address_id': fields.many2one('res.partner.address', 'Customer Address', select=1, ondelete='restrict'),

        'departure_date': fields.date('Date of Departure'),
        'arrival_planned_date': fields.date('Planned Arrival Date'),
        'incoterm_type': fields.many2one('stock.incoterms', 'Incoterm Type', widget='selection'),
        'incoterm_location': fields.char('Incoterm Location', size=128), # TODO m2o
        'notify_partner_id': fields.many2one('res.partner', 'Notify Partner'), # TODO ondelete

        'customs_regime': fields.selection([
            ('import', 'Import'),
            ('export', 'Export'),
            ('transit', 'Tansit'),
            ('domestic', 'Domestci'),
            ('reexport', 'Re-Export'),
            ('bondedwh', 'Bonded Warehouse'),
            ('temp', 'Temporary Importation'),
        ], 'Customs Regime'),

        'cargo_weight': fields.function(lambda self, *a: self._get_total(*a), type='float', method=True, string='Total Cargo Weight [kg]', multi='_total'),
        'cargo_volume': fields.function(lambda self, *a: self._get_total(*a), type='float', method=True, string='Total Cargo Volume [dm3]', multi='_total'),
        'cargo_parcels':  fields.function(lambda self, *a: self._get_total(*a), type='integer', method=True, string='Total Number of Parcels', multi='_total'),
        'container_type': fields.selection([('dry', 'Dry'), ('reefer', 'Reefer')], 'Container Type'),
        'container_size': fields.selection([('20ft', '20 ft'), ('40ft', '40 ft')], 'Container Size'),
        'truck_payload': fields.selection([('1-3T', '1-3 tons'), ('3-6T', '3-6 tons'), ('6-9T', '6-9 tons'), ('9-12T', '9-12 tons'), ('12-24T', '12-24 tons'), ('24-30T', '24-30 tons')], 'Truck Payload'),

        'manifest_link': fields.char('Freight Manifest Link', size=1024),
        'packing_link': fields.char('Packing List Link', size=1024),
        'invoice_link': fields.char('Invoice Link', size=1024),
        'donation_link': fields.char('Donation Certificate Link', size=1024),
    }

    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def change_line(self, cr, uid, ids, context=None):
        if not ids:
            return {}
        d = self.read(cr, uid, ids[0], ['cargo_weight', 'cargo_volume', 'cargo_parcels'], context=context)
        del d['id']
        return {'value': d}

    def _check_addresses(self, cr, uid, ids):
        if ids:
            cr.execute('''
                select t.name,
                    t.supplier_partner_id is null and t.supplier_address_id is not null or t.supplier_partner_id is not null and sa.id is not null and t.supplier_partner_id != coalesce(sa.partner_id, 0),
                    t.transit_partner_id is null and t.transit_address_id is not null or t.transit_partner_id is not null and t.id is not null and t.transit_partner_id != coalesce(ta.partner_id, 0),
                    t.customer_partner_id is null and t.customer_address_id is not null or t.customer_partner_id is not null and ca.id is not null and t.customer_partner_id != coalesce(ca.partner_id, 0)
                from
                    ''' + self._table + ''' t
                left join res_partner_address sa on t.supplier_address_id = sa.id
                left join res_partner_address ta on t.transit_address_id = ta.id
                left join res_partner_address ca on t.customer_address_id = ta.id
                where
                    t.id in %s and (
                        t.supplier_partner_id is null and t.supplier_address_id is not null
                        or
                        t.transit_partner_id is null and t.transit_address_id is not null
                        or
                        t.customer_partner_id is null and t.customer_address_id is not null
                        or
                        t.supplier_partner_id is not null and sa.id is not null and t.supplier_partner_id != coalesce(sa.partner_id, 0)
                        or
                        t.transit_partner_id is not null and ta.id is not null and t.transit_partner_id != coalesce(ta.partner_id, 0)
                        or
                        t.customer_partner_id is not null and ca.id is not null and t.customer_partner_id != coalesce(ca.partner_id, 0)
                    ) ''', (tuple(ids), ))  # not_a_user_entry
            for x in cr.fetchall():
                unmacth = []
                if x[1]:
                    unmacth.append(_('Supplier'))
                if x[2]:
                    unmacth.append(_('Transit'))
                if x[3]:
                    unmacth.append(_('Customer'))
                raise osv.except_osv(_('Warning'), _('%s inconsistent %s address: partner and address do not match') % (x[0], ', '.join(unmacth)))

        return True

    _constraints = [
        (_check_addresses, 'Adress Error', [])
    ]

    def _clean_fields(self, cr, uid, vals, context=None):
        if not vals:
            return
        if 'transit_partner_id' in vals and not vals['transit_partner_id']:
            vals.update({
                'transit_departure_date': False,
                'transit_arrival_planned_date': False,
                'post_transport_partner_id': False,
                'post_transport_mode': False,
                'post2_transport_partner_id': False,
                'post2_transport_mode': False,
            })

    def create(self, cr, uid, vals, context=None):
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, self._name)
        self._clean_fields(cr, uid, vals, context=context)
        return super(transport_order, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        self._clean_fields(cr, uid, vals, context=context)
        return super(transport_order, self).write(cr, uid, ids, vals, context=context)

    def change_partner(self, cr, uid, id, field, partner_id, address_id, context=None):
        if not partner_id:
            return {'value': {'%s_address_id'%field: False}}
        if address_id and self.pool.get('res.partner.address').search_exists(cr, uid, [('id', '=', address_id), ('partner_id', '=', partner_id)]):
            return {}
        address_id = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['default']).get('default')
        return {'value': {'%s_address_id'%field: address_id}}


transport_order()

class transport_order_in(osv.osv):
    _inherit = 'transport.order'
    _name = 'transport.order.in'
    _table = 'transport_order_in'
    _description = 'Inbound Transport Order'
    _trace = True

    def generate_closure_sync_message(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        cr.execute('''
            select ito.id from transport_order_in ito
                where
                    ito.from_sync = 't' and
                    ito.id in %s and
                    not exists(select ito2.id from transport_order_in ito2 where ito2.id = ito.id and ito2.sync_ref = ito2.sync_ref and state not in ('closed', 'done'))
            ''', (tuple(ids), ))
        for _id in cr.fetchall():
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'transport.order.in', _id[0], {},
                                                                                  'transport.order.out.closed_by_sync', False, check_identifier=False, context=context, force_domain=True)

    def create_by_sync(self, cr, uid, source, line_info, context=None):
        from sync_common import xmlid_to_sdref

        so_po_common = self.pool.get('so.po.common')
        partner_obj = self.pool.get('res.partner')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context=context)

        partner_instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id

        internal_source = partner_obj.search_exists(cr, uid, [('id', '=', partner_id), ('partner_type', '=', 'internal')], context=context)

        info = line_info.to_dict()
        ito_data = {
            'supplier_partner_id': partner_id,
            'supplier_address_id': address_id,
            'from_sync': True,
            'sync_ref': info.get('name'),
            'state': 'transit',
        }

        if info.get('transport_partner_id'):
            transport_id = False
            if internal_source:
                transport_id = partner_obj.find_sd_ref(cr, uid, xmlid_to_sdref(info['transport_partner_id']['id']), context=context)
            if not transport_id:
                t_ids = partner_obj.search(cr, uid, [('name', '=', info['transport_partner_id']['name']), ('active', 'in', ['t', 'f'])], context=context)
                if t_ids:
                    transport_id = t_ids[0]
            if transport_id:
                ito_data['transport_partner_id'] = transport_id

        if info.get('next_partner_type') == 'via':
            ito_data['transit_partner_id'] = partner_instance_id
            if info.get('customer_partner_id'):
                customer_id = False
                customer_address_id = False
                if internal_source:
                    customer_id = partner_obj.find_sd_ref(cr, uid, xmlid_to_sdref(info['customer_partner_id']['id']), context=context)
                if not customer_id:
                    c_ids = partner_obj.search(cr, uid, [('name', '=', info['customer_partner_id']['name']), ('active', 'in', ['t', 'f'])], context=context)
                    if c_ids:
                        customer_id = c_ids[0]
                if customer_id:
                    customer_address_id = so_po_common.get_partner_address_id(cr, uid, customer_id, context=context)
                    ito_data.update({'customer_partner_id':customer_id, 'customer_address_id': customer_address_id})

        if info.get('next_partner_type') == 'customer':
            ito_data['customer_partner_id'] = partner_instance_id
            if info.get('transit_partner_id'):
                transit_id = False
                transit_address_id = False

                if internal_source:
                    transit_id = partner_obj.find_sd_ref(cr, uid, xmlid_to_sdref(info['transit_partner_id']['id']), context=context)
                if not transit_id:
                    t_ids = partner_obj.search(cr, uid, [('name', '=', info['transit_partner_id']['name']), ('active', 'in', ['t', 'f'])], context=context)
                    if t_ids:
                        transit_id = t_ids[0]
                if transit_id:
                    transit_address_id = so_po_common.get_partner_address_id(cr, uid, transit_id, context=context)
                    ito_data.update({'transit_partner_id': transit_id, 'transit_address_id': transit_address_id})

        for x in ['post_transport_partner_id', 'post2_transport_partner_id']:
            transp_value = False
            if info.get(x):
                if internal_source:
                    transp_value = partner_obj.find_sd_ref(cr, uid, xmlid_to_sdref(info[x]['id']), context=context)
                if not transp_value:
                    t_ids = partner_obj.search(cr, uid, [('name', '=', info[x]['name']), ('active', 'in', ['t', 'f'])], context=context)
                    if t_ids:
                        transp_value = t_ids[0]
                if transp_value:
                    ito_data.update({x: transp_value})

        if info.get('incoterm_type') and info.get('incoterm_type').get('code'):
            incoterm_ids = self.pool.get('stock.incoterms').search(cr, uid, [('code', '=', info['incoterm_type']['code'])], context=context)
            if incoterm_ids:
                ito_data['incoterm_type'] = incoterm_ids[0]

        for field in ['original_cargo_ref', 'shipment_flow', 'zone_type', 'cargo_category', 'ship_ref', 'details', 'transport_mode', 'departure_date', 'arrival_planned_date', 'incoterm_location', 'container_type', 'container_size', 'truck_payload', 'transit_departure_date', 'transit_arrival_planned_date', 'post_transport_mode', 'post2_transport_mode']:
            ito_data[field] = info.get(field, False)

        ito_data['line_ids'] = []
        if info.get('line_ids'):
            for line in info['line_ids']:
                ito_line_info = {}
                if line.get('shipment_id') and line.get('shipment_id').get('name'):
                    in_ref = '%s.%s' % (source, line['shipment_id']['name'])
                    in_ids = self.pool.get('stock.picking').search(cr, uid, [('shipment_ref', '=', in_ref), ('type', '=', 'in')], context=context)
                    if in_ids:
                        ito_line_info['incoming_id'] = in_ids[0]
                    ito_line_info['description'] = in_ref
                else:
                    ito_line_info['description'] = line.get('description')
                for f in ['parcels_nb', 'volume', 'weight', 'amount', 'comment', 'kc', 'dg', 'cs']:
                    ito_line_info[f] = line.get(f)

                ito_data['line_ids'].append((0, 0, ito_line_info))
        ito_io = self.create(cr, uid, ito_data, context=context)

        ito = self.read(cr, uid, ito_io, ['name'], context=context)
        return 'ITO %s created' % (ito['name'], )

    def _get_total(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        res = super(transport_order_in, self)._get_total(cr, uid, ids, field_name, args, context=context)
        cr.execute('''
            select
                ito.id,
                sum(line.parcels_nb),
                sum(line.weight),
                sum(line.volume)
            from
                transport_order_in ito, transport_order_in_line line
            where
                ito.id = line.transport_id and
                ito.id in %s
            group by ito.id
            ''', (tuple(ids), ))
        for x in cr.fetchall():
            res[x[0]] = {
                'cargo_parcels': res[x[0]]['cargo_parcels'] + (x[1] or 0),
                'cargo_weight': res[x[0]]['cargo_weight'] + (x[2] or 0),
                'cargo_volume': res[x[0]]['cargo_volume'] + (x[3] or 0),
            }

        return res


    def _search_incoming_ids(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[0] == 'incoming_ids':
                dom.append(('line_ids.incoming_id.name', arg[1], arg[2]))
            else:
                dom.append(arg)
        return dom

    def _get_incoming_ids(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for _id in ids:
            ret[_id] = ""
        cr.execute('''
            select
                l.transport_id, array_agg(distinct(p.name))
            from
                transport_order_in_line l, stock_picking p
            where
                l.incoming_id = p.id and
                l.transport_id in %s
            group by l.transport_id''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = ','.join(x[1])
        return ret



    _columns = {
        'line_ids': fields.one2many('transport.order.in.line', 'transport_id', 'Lines', copy=False),
        'incoming_ids': fields.function(_get_incoming_ids, fnct_search=_search_incoming_ids, method=True, type='char', string='Incoming Shipment Reference'),
        'state': fields.selection([
            ('planned', 'Planned'),
            ('preclearance', 'Under Preclearance'),
            ('transit', 'In Transit'),
            ('border', 'At Border Point'),
            ('customs', 'Customs Cleared'),
            ('warehouse', 'At Warehouse'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=1, copy=False),
        'transport_fees_ids': fields.one2many('transport.order.fees', 'transport_in_id', 'Fees', copy=False),
        'transport_step_ids': fields.one2many('transport.order.step', 'transport_in_id', 'Steps', copy=False),
        'parent_ito_id': fields.many2one('transport.order.in', 'Backorder of', readonly=True, copy=False),
        'oto_created': fields.boolean('Corresponding OTO created', readonly=True, copy=False),
        'oto_id': fields.many2one('transport.order.out', 'OTO', readonly=True, copy=False),
        'from_sync': fields.boolean('From sync', readonly=True, copy=False),
        'sync_ref': fields.char('OTO Reference', size=64, readonly=True, copy=False, select=1),
    }
    _defaults = {
        'shipment_type': 'in',
        'state': 'planned',
        'oto_created': False,
        'from_sync': False,
    }

    def write(self, cr, uid, ids, vals, context=None):
        ret = super(transport_order_in, self).write(cr, uid, ids, vals, context=context)
        if vals and vals.get('state') in ['closed', 'cancel']:
            self.generate_closure_sync_message(cr, uid, ids, context=context)
        return ret


    def _check_partner_consistency(self, cr, uid, ids, context=None):
        # to check at doc validation
        errors = _check_partner_consistency_in(self,cr, uid, ids, context)
        if errors:
            raise osv.except_osv(_('Warning'), _('%s supplier %s is not consistent with %s') % (errors[0][0], errors[0][1], errors[0][2]))
        return True

    def _process_step(self, cr, uid, ids, current_step, context=None):
        to_process_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', current_step)], context=context)
        if to_process_ids:
            all_st = [x[0] for x in self._columns['state'].selection]
            next_st = all_st[all_st.index(current_step)+1]
            self.write(cr, uid, to_process_ids, {'state': next_st}, context=context)
        return True

    def button_process(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'planned', context=context)

    def copy_all(self, cr, uid, ids, context=None):
        to_process_ids = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['planned', 'warehouse'])], context=context)
        if not to_process_ids:
            return False

        cr.execute('''
            update transport_order_in_line set
                process_parcels_nb=parcels_nb,
                process_volume=volume,
                process_weight=weight,
                process_kc=kc,
                process_dg=dg,
                process_cs=cs,
                process_amount=amount
            where
                transport_id = %s ''', (to_process_ids[0], )
                   )

        return to_process_ids[0]

    def uncopy_all(self, cr, uid, ids, context=None):
        to_process_ids = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['planned', 'warehouse'])], context=context)
        if not to_process_ids:
            return False

        cr.execute('''
            update transport_order_in_line set
                process_parcels_nb=0,
                process_volume=null,
                process_weight=null,
                process_kc=kc,
                process_dg=dg,
                process_cs=cs,
                process_amount=0,
            where
                transport_id = %s ''', (to_process_ids[0], )
                   )

        return to_process_ids[0]

    def button_wizard_cancel(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

    def button_partial_reception(self, cr, uid, ids, context=None):
        return self.button_process_lines(cr, uid, ids, context=None)

    def button_process_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        new_id = self.copy_all(cr, uid, ids, context=context)
        if not new_id:
            return True

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'transport_mgmt', 'transport_order_in_partial')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'transport.order.in',
            'res_id': new_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'view_id': [view_id[1]],
        }

    def button_dispatch(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'preclearance', context=context)

    def button_arrive(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'transit', context=context)

    def button_clear_customs(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'border', context=context)

    def button_delivery(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'customs', context=context)

    def button_reception(self, cr, uid, ids, context=None):
        return self._process_step(cr, uid, ids, 'warehouse', context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def button_wizard_process(self, cr, uid, ids, context=None):
        to_dup = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['planned', 'warehouse'])], context=context)

        if not to_dup:
            return True

        back_id = False
        remaining_lines = []
        updated_lines = []

        lines_id = self.pool.get('transport.order.in.line').search(cr, uid, [('transport_id', 'in', to_dup), ('process_parcels_nb', '>', 0)], context=context)
        if not lines_id:
            return True


        ito = self.browse(cr, uid, ids[0], fields_to_fetch=['line_ids'], context=context)

        # new ITO with remaining
        cr.execute("select exists(select id from transport_order_in_line where transport_id = %s and process_parcels_nb < parcels_nb)", (ito.id,))
        if cr.fetchone()[0]:
            back_id = self.copy(cr, uid, ito.id, {'parent_ito_id': ito.id, 'from_sync': ito.from_sync, 'sync_ref': ito.sync_ref, 'state': ito.state},context=context)

        for line in ito.line_ids:
            if back_id:
                if not line['process_parcels_nb']:
                    remaining_lines.append((4, line.id))
                else:
                    if line['process_parcels_nb'] < line['parcels_nb']:
                        remaining_lines.append((0, 0, {
                            'incoming_id': line.incoming_id and line.incoming_id.id or False,
                            'description': line.description,
                            'parcels_nb': line.parcels_nb - line.process_parcels_nb,
                            'volume': line.volume - line.process_volume,
                            'weight': line.weight - line.process_weight,
                            'kc': line.kc,
                            'dg': line.dg,
                            'cs': line.cs,
                            'amount': max(0, line.amount - line.process_amount),
                            'comment': line.comment,
                        }))

                    updated_lines.append((1, line.id,{
                        'parcels_nb': line.process_parcels_nb,
                        'volume': line.process_volume,
                        'weight':line.process_weight,
                        'kc': line.process_kc,
                        'dg': line.process_dg,
                        'cs': line.process_cs,
                        'amount': line.process_amount
                    }))

        if remaining_lines:
            self.write(cr, uid, back_id, {'line_ids': remaining_lines}, context=context)
            ito_name = self.read(cr, uid, back_id, ['name'], context=context)['name']
            self.log(cr, uid, back_id, _('Backorder ITO %s created') % (ito_name), context=context)

        if ito.state == 'planned':
            new_state = 'preclearance'
        else:
            new_state = 'closed'

        self.write(cr, uid, to_dup[0], {'line_ids': updated_lines, 'state': new_state}, context=context)
        return {'type': 'ir.actions.act_window_close'}


    def button_create_oto(self, cr, uid, ids, context=None):
        to_dup = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'closed'), ('oto_created', '=', False)], context=context)
        if to_dup:
            for x in self.read(cr, uid, ids, context=context):
                data = {}
                for to_copy_flat in [
                    'original_cargo_ref', 'shipment_flow',
                    'zone_type', 'cargo_category', 'ship_ref',
                    'incoterm_location', 'details'
                ]:
                    data[to_copy_flat] = x[to_copy_flat]

                for to_copy_rel in [
                    'notify_partner_id', 'incoterm_type',
                    'customer_partner_id', 'customer_address_id'
                ]:
                    if x[to_copy_rel]:
                        data[to_copy_rel] = x[to_copy_rel][0]

                data.update({
                    'shipment_type': 'out',
                    'supplier_partner_id': self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id,
                    'line_ids': [],
                })

                for line in self.pool.get('transport.order.in.line').read(cr, uid, x['line_ids'], [
                    'description', 'parcels_nb', 'volume', 'weight', 'amount', 'comment', 'kc', 'dg', 'cs'
                ], context=context):
                    del line['id']
                    data['line_ids'].append((0, 0, line))

                new_id = self.pool.get('transport.order.out').create(cr, uid, data, context=context)
                self.write(cr, uid, x['id'], {'oto_created': True, 'oto_id': new_id}, context=context)
                oto_name = self.pool.get('transport.order.out').read(cr, uid, new_id, ['name'], context=context)['name']
                self.pool.get('transport.order.out').log(cr, uid, new_id, _('OTO %s created') % (oto_name), action_xmlid='transport_mgmt.transport_order_out_action')

        return True

transport_order_in()

class transport_order_out(osv.osv):
    _inherit = 'transport.order'
    _name = 'transport.order.out'
    _table = 'transport_order_out'
    _description = 'Outbound Transport Order'
    _trace = True

    def closed_by_sync(self, cr, uid, source, line_info, context=None):
        info = line_info.to_dict()
        oto_ids = self.search(cr, uid, [('state', '=', 'dispatched'), ('name', '=', info.get('sync_ref')), ('next_partner_id.name', '=', source)], context=context)
        if oto_ids:
            self.write(cr, uid, oto_ids, {'state': 'closed'}, context=context)
            return 'OTO closed'

        return 'Message ignored'

    def _get_total(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        res = super(transport_order_out, self)._get_total(cr, uid, ids, field_name, args, context=context)

        cr.execute('''
            select
                oto.id,
                sum(pack.to_pack - pack.from_pack + 1),
                sum(pack.weight * (pack.to_pack - pack.from_pack + 1)),
                sum(pack.length * pack.width * pack.height * (pack.to_pack - pack.from_pack + 1) / 1000.0)
            from
                transport_order_out oto
                inner join transport_order_out_line line on oto.id = line.transport_id
                inner join shipment ship on line.shipment_id = ship.id
                left join pack_family_memory pack on pack.state not in ('returned', 'cancel') and pack.shipment_id = ship.id and (line.is_split and pack.oto_line_id = line.id or not line.is_split)
            where
                oto.id in %s and
                oto.state = 'planned'
            group by oto.id''', (tuple(ids), ))

        for x in cr.fetchall():
            res[x[0]] = {
                'cargo_parcels': x[1] or 0,
                'cargo_weight': x[2] or 0,
                'cargo_volume': x[3] or 0,
            }

        cr.execute('''
            select
                oto.id,
                sum(add.nb_parcels),
                sum(add.weight),
                sum(add.volume)
            from
                transport_order_out oto
                inner join transport_order_out_line line on oto.id = line.transport_id
                inner join shipment ship on line.shipment_id = ship.id
                left join shipment_additionalitems add on add.shipment_id = ship.id and (line.is_split and add.oto_line_id = line.id or not line.is_split)
            where
                oto.id in %s and
                oto.state = 'planned'
            group by oto.id''', (tuple(ids), ))

        for x in cr.fetchall():
            res[x[0]] = {
                'cargo_parcels': res[x[0]]['cargo_parcels'] + (x[1] or 0),
                'cargo_weight': res[x[0]]['cargo_weight'] + (x[2] or 0),
                'cargo_volume': res[x[0]]['cargo_volume'] + (x[3] or 0),
            }

        cr.execute('''
            select
                oto.id,
                sum(line.parcels_nb),
                sum(line.weight),
                sum(line.volume)
            from
                transport_order_out oto, transport_order_out_line line
            where
                oto.id = line.transport_id and
                (line.shipment_id is null or oto.state != 'planned') and
                oto.id in %s
            group by oto.id
            ''', (tuple(ids), ))
        for x in cr.fetchall():
            res[x[0]] = {
                'cargo_parcels': res[x[0]]['cargo_parcels'] + (x[1] or 0),
                'cargo_weight': res[x[0]]['cargo_weight'] + (x[2] or 0),
                'cargo_volume': res[x[0]]['cargo_volume'] + (x[3] or 0),
            }

        return res

    def _search_shipment_ids(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[0] == 'shipment_ids':
                dom.append(('line_ids.shipment_id.name', arg[1], arg[2]))
            else:
                dom.append(arg)
        return dom

    def _get_shipment_ids(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for _id in ids:
            ret[_id] = ""
        cr.execute('''
            select
                l.transport_id, array_agg(distinct(p.name))
            from
                transport_order_out_line l, shipment p
            where
                l.shipment_id = p.id and
                l.transport_id in %s
            group by l.transport_id''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = ','.join(x[1])
        return ret

    _columns = {
        'line_ids': fields.one2many('transport.order.out.line', 'transport_id', 'Lines', copy=False),
        'shipment_ids': fields.function(_get_shipment_ids, fnct_search=_search_shipment_ids, method=True, type='char', string='Shipment Reference'),
        'state': fields.selection([
            ('planned', 'Planned'),
            ('dispatched', 'Dispatched'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=1, copy=False),
        'transport_fees_ids': fields.one2many('transport.order.fees', 'transport_out_id', 'Fees', copy=False),
        'transport_step_ids': fields.one2many('transport.order.step', 'transport_out_id', 'Steps', copy=False),
        'parent_oto_id': fields.many2one('transport.order.out', 'Backorder of', readonly=True, copy=False),
        'next_partner_id': fields.many2one('res.partner', 'Sync to', readonly=True, copy=False),
        'next_partner_type': fields.selection([('via', 'via'), ('customer', 'customer')], 'Next partner type', readonly=True, copy=False),
    }
    _defaults = {
        'shipment_type': 'out',
        'state': 'planned',
        'supplier_partner_id': lambda self, cr, uid, *a: self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id,
    }

    def button_dispatch(self, cr, uid, ids, context=None):
        ship_ids = self.pool.get('transport.order.out.line').search(cr, uid, [('transport_id', 'in', ids), ('transport_id.state', '=', 'planned'), '|', ('shipment_id', '=', False), ('shipment_id.state', 'in', ['done', 'delivered'])])
        if not ship_ids:
            raise osv.except_osv(_('Warning'), _('OTO lines linked to a Shipment can be dispatched only if the shipment state is Dispatched or Received'))

        line_obj = self.pool.get('transport.order.out.line')

        to_update = line_obj.search(cr, uid, [('transport_id', 'in', ids), ('shipment_id', '!=', False)], context=context)
        if to_update:
            for _id, vals in line_obj._get_shipment_data(cr, uid, to_update, context=context).items():
                line_obj.write(cr, uid, _id, vals, context=context)

        for oto in self.browse(cr, uid, ids, context=context):
            data = {'state': 'dispatched'}
            if oto.transit_partner_id and oto.transit_partner_id.partner_type in ('internal', 'section', 'intermission'):
                data['next_partner_id'] = oto.transit_partner_id.id
                data['next_partner_type'] = 'via'
            elif oto.customer_partner_id and oto.customer_partner_id.partner_type in ('internal', 'section', 'intermission'):
                data['next_partner_id'] = oto.customer_partner_id.id
                data['next_partner_type'] = 'customer'

            if data.get('next_partner_id'):
                partner_instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id
                if data['next_partner_id'] == partner_instance_id:
                    if data['next_partner_type'] == 'via':
                        field_label = _('Ships Via')
                    else:
                        field_label = _('Customer Partner')
                    raise osv.except_osv(_('Warning'), _('You cannot dispatch an OTO to yourself, please change the %s value') % (field_label, ))

            self.write(cr, uid, oto.id, data, context=context)

        return True

    def force_button_validate(self, cr, uid, ids, context=None):
        self.button_validate(cr, uid, ids, context=context, display_warning=False)
        return {'type': 'ir.actions.act_window_close'}

    def button_validate(self, cr, uid, ids, context=None, display_warning=True):
        to_val_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'dispatched')], context=context)
        if not to_val_ids:
            return True

        sync_type = ['internal', 'section', 'intermission']
        if display_warning and self.search_exists(cr, uid, [('id', 'in', to_val_ids), '|', ('customer_partner_id.partner_type', 'in', sync_type), ('customer_partner_id.partner_type', 'in', sync_type)], context=context):
            msg = self.pool.get('message.action').create(cr, uid, {
                'title':  _('Warning'),
                'message': '<h3>%s</h3>' % (_("You're about to close an OTO that is synchronized and should be consequently closed by the other instance. Are you sure you want to force the closure at your level ? "), ),
                'yes_action': lambda cr, uid, context: self.force_button_validate(cr, uid, ids, context=context),
                'yes_label': _('Process Anyway'),
                'no_label': _('Close window'),
            }, context=context)
            return self.pool.get('message.action').pop_up(cr, uid, [msg], context=context)

        self.write(cr, uid, ids, {'state': 'closed'}, context=context)
        return True


    def button_cancel(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('transport.order.out.line')
        line_ids = line_obj.search(cr, uid, [('transport_id', 'in', ids)], context=context)
        if line_ids:
            line_obj.write(cr, uid, line_ids, {'is_split': True}, context=context)
            cr.execute("update pack_family_memory set oto_line_id=null where oto_line_id in %s", (tuple(line_ids), ))
            cr.execute("update shipment_additionalitems set oto_line_id=null where oto_line_id in %s", (tuple(line_ids), ))
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

        return True


transport_order_out()

class transport_order_line(osv.osv):
    _name = 'transport.order.line'
    _description = 'Transport Line'
    _rec_name = 'description'

    _columns = {
        #'transport_id': fields.many2one('transport_id', # TODO inherit ??

        'description': fields.char('Description', size=256),
        'parcels_nb': fields.integer_null('Number of Parcels'),
        'volume': fields.float_null('Volume [dm3]', digits=(16,2)),
        'weight': fields.float_null('Weight [kg]', digits=(16,2)),
        'amount': fields.float_null('Value', digits=(16,2)),
        'comment': fields.char('Comment', size=1024),
        # TODO currency ?
        # TODO state
        'kc': fields.boolean('CC', help='Cold Chain'),
        'dg': fields.boolean('DG', help='Dangerous Good'),
        'cs': fields.boolean('CS', help='Controlled Substance'),
    }

    _defaults = {
    }


transport_order_line()


def _check_partner_consistency_in(self, cr, uid, ids, context=None):
    if self._name == 'transport.order.in.line':
        cond = ' l.id in %s '
    else:
        cond = ' t.id in %s '
    if ids:
        cr.execute('''
            select t.name, part.name, array_agg(p.name)
            from
                transport_order_in t
            inner join res_partner part on part.id = t.supplier_partner_id
            inner join transport_order_in_line l on l.transport_id = t.id
            inner join stock_picking p on p.id = l.incoming_id
            where
                p.partner_id != t.supplier_partner_id and
            ''' + cond + '''
            group by t.name, part.name''', (tuple(ids), )) # not_a_user_entry
        return [(x[0], x[1], ','.join(x[2])) for x in cr.fetchall()]
    return []

class transport_order_in_line(osv.osv):
    _inherit = 'transport.order.line'
    _name = 'transport.order.in.line'
    _table = 'transport_order_in_line'
    _trace = True

    _columns = {
        'transport_id': fields.many2one('transport.order.in', 'Transport', required=True, select=True, join=True, ondelete='cascade'),
        'incoming_id': fields.many2one('stock.picking', 'Incoming', select=1, domain=[('type', '=', 'in')], join='LEFT'),

        'process_parcels_nb': fields.integer_null('Number of Parcels'),
        'process_volume': fields.float_null('Volume [dm3]', digits=(16,2)),
        'process_weight': fields.float_null('Weight [kg]', digits=(16,2)),
        'process_amount': fields.float('Value', digits=(16,2)),
        'process_kc': fields.boolean('CC'),
        'process_dg': fields.boolean('DG'),
        'process_cs': fields.boolean('CS'),
    }
    def create(self, cr, uid, vals, context=None):
        return super(transport_order_in_line, self).create(cr, uid, vals, context=context)

    def change_incoming(self, cr, uid, id, incoming_id, context=None):
        if incoming_id:
            cr.execute('''
                select pick.details, bool_or(is_kc), bool_or(dangerous_goods='True'), bool_or(cs_txt='X'), sum(m.price_unit * m.product_qty / rate.rate)
                from
                    stock_picking pick
                    left join stock_move m on m.picking_id = pick.id
                    left join product_product p on p.id = m.product_id
                    left join lateral (
                        select rate.rate, rate.name as fx_date from
                            res_currency_rate rate
                        where
                            rate.name <= coalesce(pick.physical_reception_date, pick.min_date) and
                            rate.currency_id = m.price_currency_id
                            order by rate.name desc, id desc
                        limit 1
                    ) rate on true
                where
                    pick.id = %s
                group by pick.id''', (incoming_id, ))
            x = cr.fetchone()
            return {
                'value': {
                    'description': x[0],
                    'kc': x[1],
                    'dg': x[2],
                    'cs': x[3],
                    'amount': x[4],
                }
            }
        return {}

    def change_nb_parcels(self, cr, uid, id, original_nb, new_nb, volume, weight, amount):
        if original_nb and new_nb:
            if new_nb > original_nb:
                return {
                    'warning': {'message': _('Number of parcels cannot be greater than original nb. parcels (%d)') % original_nb},
                    'value': {'process_parcels_nb': original_nb},
                }
            return {
                'value': {
                    'process_volume': round(volume / original_nb * new_nb, 2),
                    'process_weight': round(weight / original_nb * new_nb, 2),
                    'process_amount': round(amount / original_nb * new_nb, 2),
                }
            }
        return {}

    #def _check_partner_consistency(self, cr, uid, ids, context=None):
    #    errors = _check_partner_consistency_in(self,cr, uid, ids, context)
    #    if errors:
    #        raise osv.except_osv(_('Warning'), _('%s supplier %s is not consistent with %s') % (errors[0][0], errors[0][1], errors[0][2]))
    #    return True

    #_constraints = [
    #    (_check_partner_consistency, 'Supplier must be the same on all lines and on header', [])
    #]
transport_order_in_line()

class transport_order_out_line(osv.osv):
    _inherit = 'transport.order.line'
    _name = 'transport.order.out.line'
    _table = 'transport_order_out_line'
    _trace = True

    _columns = {
        'transport_id': fields.many2one('transport.order.out', 'Transport', required=True, select=True, join=True, ondelete='cascade'),
        'shipment_id': fields.many2one('shipment', 'Shipment', select=1, domain=[('parent_id', '!=', False)], join='LEFT'),
        'shipment_state': fields.related('shipment_id', 'state', type='selection', string='Shipment State', selection=[('draft', 'Draft'),
                                                                                                                       ('shipped', 'Ready to ship'),
                                                                                                                       ('done', 'Dispatched'),
                                                                                                                       ('delivered', 'Received'),
                                                                                                                       ('cancel', 'Returned')]),
        'is_split': fields.boolean('Split', readonly=True, copy=False),
        'pack_family_ids': fields.one2many('pack.family.memory', 'oto_line_id', 'Pack Family', copy=False),
        'item_ids': fields.one2many('shipment.additionalitems', 'oto_line_id', 'Additional Item', copy=False),
    }

    _defaults = {
    }
    def write(self, cr, uid, ids, values, context=None):
        ret = super(transport_order_out_line, self).write(cr, uid, ids, values, context=context)

        if isinstance(ids, int):
            ids = [ids]
        if ids:
            cr.execute('''
                update pack_family_memory pf set oto_line_id = NULL
                from transport_order_out_line tl
                where
                    pf.oto_line_id in %s and
                    tl.id = pf.oto_line_id and
                    tl.shipment_id != pf.shipment_id ''', (tuple(ids), ))
            cr.execute('''
                update shipment_additionalitems add set oto_line_id = NULL
                from transport_order_out_line tl
                where
                    add.oto_line_id in %s and
                    tl.id = add.oto_line_id and
                    tl.shipment_id != add.shipment_id ''', (tuple(ids), ))
        return ret


    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        frozen_fields = ['kc', 'dg', 'cs', 'parcels_nb', 'volume', 'weight']
        if not fields:
            fields = []

        single = False
        if isinstance(ids, int):
            single = True
            ids = [ids]

        ship_data = {}
        if not fields or set(fields).intersection(frozen_fields):
            to_compute_ids = self.search(cr, uid, [('id', 'in', ids),('transport_id.state', '=', 'planned'), ('shipment_id', '!=', False)])
            if to_compute_ids:
                ship_data = self._get_shipment_data(cr, uid, to_compute_ids,  context=context)


        d = super(transport_order_out_line, self).read(cr, uid, ids, fields, context, load)
        if ship_data:
            for x in d:
                if ship_data.get(x['id']):
                    x.update(ship_data[x['id']])

        if single:
            d = d[0]
        return d

    def _get_shipment_data(self, cr, uid, ids, context=None):
        res = {}
        if ids:
            cr.execute('''
                select
                    line.id,
                    ship.id,
                    ship.in_ref,
                    bool_or(p.is_kc),
                    bool_or(p.dangerous_goods='True'),
                    bool_or(p.cs_txt='X'),
                    sum(pack.to_pack - pack.from_pack + 1),
                    sum(pack.weight * (pack.to_pack - pack.from_pack + 1)),
                    sum(pack.length * pack.width * pack.height * (pack.to_pack - pack.from_pack + 1) / 1000.0),
                    sum(m.price_unit * m.product_qty / rate.rate)
                from
                    transport_order_out_line line
                    inner join shipment ship on line.shipment_id = ship.id
                    left join pack_family_memory pack on pack.state not in ('returned', 'cancel') and pack.shipment_id = ship.id and (line.is_split and pack.oto_line_id = line.id or not line.is_split)
                    left join stock_move m on pack.id = m.shipment_line_id
                    left join product_product p on p.id = m.product_id
                    left join lateral (
                        select rate.rate, rate.name as fx_date from
                            res_currency_rate rate
                        where
                            rate.name <= ship.shipment_actual_date and
                            rate.currency_id = m.price_currency_id
                            order by rate.name desc, id desc
                        limit 1
                    ) rate on true

                where
                    line.id in %s
                group by line.id, ship.id''', (tuple(ids), ))
            for x in cr.fetchall():
                res[x[0]] = {
                    'description': x[2] or False,
                    'kc': x[3] or False,
                    'dg': x[4] or False,
                    'cs': x[5] or False,
                    'parcels_nb': x[6] or False,
                    'weight': x[7] or False,
                    'volume': x[8] or False,
                    'amount': x[9] and round(x[9], 2) or False,
                }

            cr.execute('''
                select
                    line.id,
                    bool_or(add.kc),
                    bool_or(add.dg),
                    bool_or(add.cs),
                    sum(add.nb_parcels),
                    sum(add.weight),
                    sum(add.volume),
                    sum(value)
                from
                    transport_order_out_line line
                    inner join shipment ship on line.shipment_id = ship.id
                    left join shipment_additionalitems add on add.shipment_id = ship.id and (line.is_split and add.oto_line_id = line.id or not line.is_split)
                where
                    line.id in %s
                group by line.id''', (tuple(ids), ))
            for x in cr.fetchall():
                res[x[0]] = {
                    'kc': res[x[0]]['kc'] or x[1] or False,
                    'dg': res[x[0]]['dg'] or x[2] or False,
                    'cs': res[x[0]]['cs'] or x[3] or False,
                    'parcels_nb': (res[x[0]]['parcels_nb'] + (x[4] or False)) or False,
                    'weight': (res[x[0]]['weight'] + (x[5] or False)) or False,
                    'volume': (res[x[0]]['volume'] + (x[6] or False)) or False,
                    'amount':(res[x[0]]['amount'] + (x[7] and round(x[7], 2) or False)) or False,
                }

        return res

    def change_shipment_id(self, cr, uid, id, shipment_id, context=None):
        if shipment_id:
            cr.execute('''
                select ship.in_ref, bool_or(p.is_kc), bool_or(p.dangerous_goods='True'), bool_or(p.cs_txt='X')
                from
                    shipment ship
                    left join stock_picking pick on pick.shipment_id = ship.id
                    left join stock_move m on m.picking_id = pick.id
                    left join product_product p on p.id = m.product_id
                where
                    ship.id = %s
                group by ship.id''', (shipment_id, ))
            x = cr.fetchone()
            ship_info = self.pool.get('shipment').read(cr, uid, shipment_id, ['num_of_packs', 'total_volume', 'total_weight', 'state', 'total_amount', 'currency_id', 'shipment_actual_date'])
            if ship_info['total_amount'] and ship_info['currency_id']:
                comp_currency = self.pool.get('res.users').get_company_currency_id(cr, uid)
                ship_info['total_amount'] = round(self.pool.get('res.currency').compute(cr, uid, ship_info['currency_id'][0], comp_currency, ship_info['total_amount'], context={'currency_date': ship_info['shipment_actual_date']}), 2)
            return {
                'value': {
                    'description': x[0],
                    'kc': x[1],
                    'dg': x[2],
                    'cs': x[3],
                    'parcels_nb': ship_info['num_of_packs'],
                    'volume': ship_info['total_volume'],
                    'weight': ship_info['total_weight'],
                    'state': ship_info['state'],
                    'amount': ship_info['total_amount'],
                }
            }
        return {}

    def button_split(self, cr, uid, ids, context=None):
        if not self.search_exists(cr, uid, [('id', '=', ids[0]), ('shipment_id', '!=', False), ('shipment_id.state', 'in', ['done', 'delivered'])]):
            raise osv.exceot_osv(_('Warning'), _('You cannot split this line due to the Shipment state'))

        doc = self.browse(cr, uid, ids[0], context=context)

        if doc.is_split:
            cond = [('oto_line_id', '=', doc.id)]
        else:
            cond = ['|', ('oto_line_id', '=', doc.id), ('oto_line_id', '=', False)]

        pack_ids = self.pool.get('pack.family.memory').search(cr, uid,  cond + [('shipment_id', '=', doc.shipment_id.id), ('state', 'not in', ['returned', 'cancel'])], context=context)
        if pack_ids:
            self.pool.get('pack.family.memory').write(cr, uid, pack_ids, {'oto_line_id': doc.id}, context=context)

        item_ids = self.pool.get('shipment.additionalitems').search(cr, uid, cond + [('shipment_id', '=', doc.shipment_id.id)], context=context)
        if item_ids:
            self.pool.get('shipment.additionalitems').write(cr, uid, item_ids, {'oto_line_id': doc.id}, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'transport_mgmt', 'transport_order_out_line_form_split')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'transport.order.out.line',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'view_id': [view_id[1]],
        }

    def split_oto(self, cr, uid, ids, context=None):
        #'button_selected_ids': {'pack_family_ids': [], 'item_ids': []}}
        if context is None:
            context = {}
        if not context.get('button_selected_ids') or not context['button_selected_ids'].get('pack_family_ids') and not context['button_selected_ids'].get('item_ids'):
            # nothing selected
            return {'type': 'ir.actions.act_window_close'}

        line = self.browse(cr, uid, ids[0], context=context)
        new_oto_id = self.pool.get('transport.order.out').copy(cr, uid, line.transport_id.id, {'line_ids': [], 'parent_oto_id': line.transport_id.id}, context=context)
        pack_ids = self.pool.get('pack.family.memory').search(cr, uid, [('oto_line_id', '=', line.id)], context=context)
        add_ids = self.pool.get('shipment.additionalitems').search(cr, uid, [('oto_line_id', '=', line.id)], context=context)
        if len(add_ids) == len(context['button_selected_ids']['item_ids']) and len(pack_ids) == len(context['button_selected_ids']['pack_family_ids']):
            self.write(cr, uid, line.id, {'transport_id': new_oto_id}, context=context)
        else:
            new_line_id = self.copy(cr, uid, line.id, {'transport_id': new_oto_id, 'pack_family_ids': [], 'item_ids': [], 'is_split': True}, context=context)
            self.write(cr, uid, line.id, {'is_split': True}, context=context)
            self.pool.get('pack.family.memory').write(cr, uid, context['button_selected_ids']['pack_family_ids'], {'oto_line_id': new_line_id}, context=context)
            self.pool.get('shipment.additionalitems').write(cr, uid, context['button_selected_ids']['item_ids'], {'oto_line_id': new_line_id}, context=context)
        return {'type': 'ir.actions.act_window_close'}

transport_order_out_line()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def _search_ito_line_domain(self, cr, uid, obj, name, args, context=None):
        domain = [('type', '=', 'in')]
        if args and args[0] and args[0][0] == 'ito_line_domain':
            if args[0][2] and isinstance(args[0][2], list):
                if args[0][2][0]:
                    # supplier is set
                    domain.append(('partner_id', '=', args[0][2][0]))
                elif args[0][2][1] and isinstance(args[0][2][1], int):
                    # only list IN with same partner
                    cr.execute('''
                        select
                            p.partner_id
                        from
                            stock_picking p,  transport_order_in_line l
                        where
                            l.incoming_id = p.id and
                            l.transport_id = %s
                        group by p.partner_id
                    ''', (args[0][2][1], ))
                    list_p = [x[0] for x in cr.fetchall()]
                    if len(list_p) > 1:
                        raise osv.except_osv(_('Warning'), _('You cannot mix partners on the same document, please review INs on existing lines'))
                    if list_p:
                        domain.append(('partner_id', '=', list_p[0]))
        return domain

    _columns = {
        'ito_line_domain': fields.function(get_fake, fnct_search=_search_ito_line_domain, method=True, type='boolean', string='Display IN compatible with ITO'),
    }

stock_picking()

class shipment(osv.osv):
    _inherit = 'shipment'

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        add_group_by = False
        for x in domain:
            if x[0] == 'oto_line_domain':
                add_group_by = True
        ret = super(shipment, self)._where_calc(cr, uid, domain, active_test=active_test, context=context)

        if add_group_by:
            ret.having_group_by = ' GROUP BY "shipment"."id" '
        return ret

    def _search_oto_line_domain(self, cr, uid, obj, name, args, context=None):
        #domain = [
        #    '&', ('parent_id', '!=', False) , '|',  ('oto_line_ids.id', '=', False), '&', ('oto_line_ids.is_split', '=', True), '|', ('pack_family_memory_ids.oto_line_id', '=', False), ('additional_items_ids.oto_line_id', '=', False)
        #]
        domain = [
            '&', ('parent_id', '!=', False) , '|', ('oto_line_ids.id', '=', False) , '&', ('oto_line_ids.is_split', '=', True), '|', ('pack_family_memory_ids.oto_line_id', '=', False), '&', ('additional_items_ids.id', '!=', False ), ('additional_items_ids.oto_line_id', '=', False)
        ]
        if args and args[0] and args[0][0] == 'oto_line_domain':
            if args[0][2] and isinstance(args[0][2], list):
                if args[0][2][0]:
                    # supplier is set
                    domain.append(('partner_id2', 'in', args[0][2][0]))
                elif args[0][2][1] and isinstance(args[0][2][1], int):
                    # only list IN with same partner
                    cr.execute('''
                        select
                            s.partner_id2
                        from
                            shipment s, transport_order_out_line l
                        where
                            l.shipment_id = s.id and
                            l.transport_id = %s
                        group by s.partner_id2
                    ''', (args[0][2][1], ))
                    list_p = [x[0] for x in cr.fetchall()]
                    if len(list_p) > 1:
                        raise osv.except_osv(_('Warning'), _('You cannot mix partners on the same document, please review Shipments on existing lines'))
                    if list_p:
                        domain.append(('partner_id2', '=', list_p[0]))
        print(domain)
        return domain

    _columns = {
        'oto_line_domain': fields.function(get_fake, fnct_search=_search_oto_line_domain, method=True, type='boolean', string='Display Shipments compatible with OTO'),
    }

shipment()


class transport_step(osv.osv):
    _name = 'transport.step'
    _description = 'Transport Steps'
    _order = 'name, id'
    _columns = {
        'name': fields.char('Name', size=64, select=1, required=1),
    }

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Name exists')
    ]
transport_step()

