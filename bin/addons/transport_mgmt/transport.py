# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
import time
#import decimal_precision as dp
from tools.translate import _
from tools.misc import get_fake

class transport_order(osv.osv):
    _name = 'transport.order'
    _description = 'Transport'
    _order = 'id desc'

    _columns = {
        'name': fields.char('Reference', size=64, required=True, select=True, readonly=True),
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
        'transport_po_id': fields.many2one('purchase.order', 'Transport PO', domain=[('categ', '=', 'transport')]),

        'supplier_partner_id': fields.many2one('res.partner', 'Supplier Partner', domain=[('supplier', '=', True)], select=1, ondelete='restrict'),
        'supplier_address_id': fields.many2one('res.partner.address', 'Supplier Address', select=1, ondelete='restrict'),

        'transit_partner_id': fields.many2one('res.partner', 'Ships Via', select=1, ondelete='restrict'),
        'transit_address_id': fields.many2one('res.partner.address', ' Transit Address', select=1, ondelete='restrict'),

        'customer_partner_id': fields.many2one('res.partner', 'Customer Partner', domain=[('customer', '=', True)], select=1, ondelete='restrict'),
        'customer_address_id': fields.many2one('res.partner.address', 'Customer Address', select=1, ondelete='restrict'),

        'departure_date': fields.date('Date of Departure'),
        'arrival_planned_date': fields.date('Planned Arrival Date'),
        'incoterm_type': fields.many2one('stock.incoterms', 'Incoterm Type', widget='selection'),
        'incoterm_location': fields.char('Incoterm Location', size=128), # TODO m2o
        'notify_partner_id': fields.many2one('res.partner', 'Notify Partner'), # TODO ondelete

    }

    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

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
                        t.transit_partner_id is not null and t.id is not null and t.transit_partner_id != coalesce(ta.partner_id, 0)
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
    def create(self, cr, uid, vals, context=None):
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, self._name)
        return super(transport_order, self).create(cr, uid, vals, context=context)

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

    def _search_incoming_search(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[0] == 'incoming_search':
                dom.append(('line_ids.incoming_id.name', arg[1], arg[2]))
            else:
                dom.append(arg)
        return dom

    _columns = {
        'line_ids': fields.one2many('transport.order.in.line', 'transport_id', 'Lines'),
        'incoming_search': fields.function(get_fake, fnct_search=_search_incoming_search, method=True, type='char', string='Incoming Shipment Reference'),
        'state': fields.selection([
            ('planned', 'Planned'),
            ('preclearance', 'Under Preclearance'),
            ('transit', 'In Transit'),
            ('border', 'At Border Point'),
            ('customs', 'Customs Cleared'),
            ('warehouse', 'At Warehouse'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=1)
    }
    _defaults = {
        'shipment_type': 'in',
        'state': 'planned',
    }

    #def write(self, cr, uid, ids, vals, context=None):
    #    return super(transport_order_in, self).write(cr, uid, ids, vals, context=context)

    def _check_partner_consistency(self, cr, uid, ids, context=None):
        # to check at doc validation
        errors = _check_partner_consistency_in(self,cr, uid, ids, context)
        if errors:
            raise osv.except_osv(_('Warning'), _('%s supplier %s is not consistent with %s') % (errors[0][0], errors[0][1], errors[0][2]))
        return True

transport_order_in()

class transport_order_out(osv.osv):
    _inherit = 'transport.order'
    _name = 'transport.order.out'
    _table = 'transport_order_out'
    _description = 'Outbound Transport Order'

    def _search_shipment_search(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[0] == 'shipment_search':
                dom.append(('line_ids.shipment_id.name', arg[1], arg[2]))
            else:
                dom.append(arg)
        return dom

    _columns = {
        'line_ids': fields.one2many('transport.order.out.line', 'transport_id', 'Lines'),
        'shipment_search': fields.function(get_fake, fnct_search=_search_shipment_search, method=True, type='char', string='Shipment Reference'),
        'state': fields.selection([
            ('planned', 'Planned'),
            ('dispatched', 'Dispatched'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=1)

    }
    _defaults = {
        'shipment_type': 'out',
        'state': 'planned',
    }
transport_order_out()

class transport_order_line(osv.osv):
    _name = 'transport.order.line'
    _description = 'Transport Line'

    _columns = {
        #'transport_id': fields.many2one('transport_id', # TODO inherit ??

        'description': fields.char('Description', size=256),
        'parcels_nb': fields.integer_null('Number of Parcels', required=1),
        'volume': fields.float_null('Volume', digits=(16,2)),
        'weight': fields.float_null('Weight', digits=(16,2)),
        'amount': fields.float_null('Value', digits=(16,2)),
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
    _columns = {
        'transport_id': fields.many2one('transport.order.in', 'Transport', required=True, select=True, join=True),
        'incoming_id': fields.many2one('stock.picking', 'Incoming', select=1, domain=[('type', '=', 'in')], join='LEFT'),
    }
    def create(self, cr, uid, vals, context=None):
        print(vals)
        return super(transport_order_in_line, self).create(cr, uid, vals, context=context)

    def change_incoming(self, cr, uid, id, incoming_id, context=None):
        if incoming_id:
            print(incoming_id)
            cr.execute('''
                select pick.details, bool_or(is_kc), bool_or(dangerous_goods='True'), bool_or(cs_txt='X')
                from
                    stock_picking pick
                    left join stock_move m on m.picking_id = pick.id
                    left join product_product p on p.id = m.product_id
                where
                    pick.id = %s
                group by pick.id''', (incoming_id, ))
            x = cr.fetchone()
            return {
                'value': {
                    'description': x[0],
                    'kc': x[1],
                    'dg': x[2],
                    'cs': x[3]
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
    _columns = {
        'transport_id': fields.many2one('transport.order.out', 'Transport', required=True, select=True, join=True),
        'shipment_id': fields.many2one('shipment', 'Shipment', select=1, domain=[('parent_id', '!=', False)], join='LEFT'),
    }

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
            ship_info = self.pool.get('shipment').read(cr, uid, shipment_id, ['num_of_packs', 'total_volume', 'total_weight'])
            return {
                'value': {
                    'description': x[0],
                    'kc': x[1],
                    'dg': x[2],
                    'cs': x[3],
                    'parcels_nb': ship_info['num_of_packs'],
                    'volume': ship_info['total_volume'],
                    'weight': ship_info['total_weight'],
                }
            }
        return {}
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

    def _search_oto_line_domain(self, cr, uid, obj, name, args, context=None):
        domain = [('parent_id', '!=', False)]
        if args and args[0] and args[0][0] == 'oto_line_domain':
            if args[0][2] and isinstance(args[0][2], list):
                if args[0][2][0]:
                    # supplier is set
                    domain.append(('partner_id2', '=', args[0][2][0]))
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
