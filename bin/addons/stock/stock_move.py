# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

from osv import fields, osv
from tools.translate import _
from tools.misc import _get_std_mml_status
import netsvc
import decimal_precision as dp
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from kit import KIT_CREATION_STATE
from msf_outgoing import INTEGRITY_STATUS_SELECTION


class stock_move(osv.osv):

    _name = "stock.move"
    _description = "Stock Move"
    _order = 'line_number, date_expected desc, id'
    _log_create = False

    KIT_SELECTION = [
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('confirmed', 'Not Available'),
        ('assigned', 'Available'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled'),
    ]
    def _auto_init(self, cursor, context=None):
        res = super(stock_move, self)._auto_init(cursor, context=context)
        cursor.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'stock_move_location_id_location_dest_id_product_id_state\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX stock_move_location_id_location_dest_id_product_id_state ON stock_move (location_id, location_dest_id, product_id, state)')
        return res


    def name_get(self, cr, uid, ids, context=None):
        res = []
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'line_number', 'location_id', 'location_dest_id'], context=context):
            if context.get('display_move_line'):
                prefix = '#%s %s' % (line.line_number, line.product_id.code or '/')
            else:
                prefix = line.product_id.code or '/'
            res.append((line.id, '%s: %s > %s' % (prefix, line.location_id.name, line.location_dest_id.name)))
        return res

    def _get_picking_ids(self, cr, uid, ids, context=None):
        res = []
        picking_ids = self.pool.get('stock.picking').browse(cr, uid, ids, context=context)
        for pick in picking_ids:
            res += self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', pick.id)])
        return res

    def _get_lot_ids(self, cr, uid, ids, context=None):
        res = []
        lot_ids = self.pool.get('stock.production.lot').browse(cr, uid, ids, context=context)
        for lot in lot_ids:
            res += self.pool.get('stock.move').search(cr, uid, [('prodlot_id', '=', lot.id)])
        return res

    def _get_allocation_setup(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the Unifield configuration value
        '''
        res = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        for order in ids:
            res[order] = setup.allocation_setup
        return res

    def _get_parent_doc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the shipment id if exist or the picking id
        '''
        res = {}

        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = False
            if move.picking_id:
                res[move.id] = move.picking_id.name
                if move.picking_id.shipment_id:
                    res[move.id] = move.picking_id.shipment_id.name

        return res

    def _search_order(self, cr, uid, obj, name, args, context=None):
        if not len(args):
            return []
        matching_fields = {'order_priority': 'priority', 'order_category': 'categ'}
        sale_obj = self.pool.get('sale.order')
        purch_obj = self.pool.get('purchase.order')

        search_args = []
        for arg in args:
            search_args.append((matching_fields.get(arg[0], arg[0]), arg[1], arg[2]))

        # copy search_args, because it's modified by sale_obj.search
        sale_args = search_args[:]
        sale_args.append(('procurement_request', 'in', ['t', 'f']))
        sale_ids = sale_obj.search(cr, uid, sale_args, limit=0)
        purch_ids = purch_obj.search(cr, uid, search_args, limit=0)

        newrgs = []
        if sale_ids:
            newrgs.append(('sale_ref_id', 'in', sale_ids))
        if purch_ids:
            newrgs.append(('purchase_ref_id', 'in', purch_ids))

        if not newrgs:
            return [('id', '=', 0)]

        if len(newrgs) > 1:
            newrgs.insert(0, '|')

        return newrgs

    def _get_order_information(self, cr, uid, ids, fields_name, arg, context=None):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}

        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = {'order_priority': False,
                            'order_category': False,
                            'order_type': False}
            order = False

            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id

            if order:
                res[move.id] = {}
                if 'order_priority' in fields_name:
                    res[move.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[move.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[move.id]['order_type'] = order.order_type

        return res

    def _vals_get_kit_creation(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # objects
        item_obj = self.pool.get('composition.item')
        result = {}
        product_ids = set()
        read_result = self.read(cr, uid, ids, ['product_id', 'product_qty',
                                               'state', 'lot_check',
                                               'exp_check',
                                               'kit_creation_id_stock_move',], context=context)

        for read_dict in read_result:
            product_ids.add(read_dict['product_id'][0])

        product_list_dict = self.pool.get('product.product').read(cr, uid,
                                                                  list(product_ids),
                                                                  ['perishable',
                                                                   'type',
                                                                   'subtype',],
                                                                  context=context)
        product_dict = dict([(x['id'], x) for x in product_list_dict])

        for stock_move_dict in read_result:
            stock_move_id = stock_move_dict['id']
            product_id = stock_move_dict['product_id'][0]
            product = product_dict[product_id]
            assigned_qty = 0.0

            # if the product is perishable (or batch management), we gather assigned qty from kit items
            if product['perishable']:
                item_ids = item_obj.search(cr, uid, [('item_stock_move_id', '=', stock_move_id)], context=context)
                if item_ids:
                    data = item_obj.read(cr, uid, item_ids, ['item_qty'], context=context)
                    for value in data:
                        assigned_qty += value['item_qty']

            # when the state is assigned or done, the assigned qty is set to product_qty
            elif stock_move_dict['state'] in ['assigned', 'done']:
                assigned_qty = stock_move_dict['product_qty']

            hidden_asset_check = False
            if product['type'] == 'product' and product['subtype'] == 'asset':
                hidden_asset_check = True

            hidden_creation_state = False
            hidden_creation_qty_stock_move = 0
            if stock_move_dict['kit_creation_id_stock_move']:
                kit_creation = self.pool.get('kit.creation').read(cr, uid,
                                                                  stock_move_dict['kit_creation_id_stock_move'][0],
                                                                  ['state', 'qty_kit_creation'], context=context)
                hidden_creation_state = kit_creation['state']
                hidden_creation_qty_stock_move = kit_creation['qty_kit_creation']

            result[stock_move_id] = {
                'assigned_qty_stock_move': assigned_qty,
                'hidden_state': stock_move_dict['state'],
                'hidden_prodlot_id': stock_move_dict['lot_check'],
                'hidden_exp_check': stock_move_dict['exp_check'],
                'hidden_asset_check': hidden_asset_check,
                'hidden_creation_state': hidden_creation_state,
                'hidden_creation_qty_stock_move': hidden_creation_qty_stock_move,
            }

        return result

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for CC/SSL/DG/NP products
        '''
        # objects
        kit_obj = self.pool.get('composition.kit')

        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False})
        product_ids = set()
        read_result = self.read(cr, uid, ids, ['product_id', 'prodlot_id'], context=context)
        for read_dict in read_result:
            product_ids.add(read_dict['product_id'][0])

        product_list_dict = self.pool.get('product.product').read(cr, uid,
                                                                  list(product_ids),
                                                                  ['is_kc',
                                                                   'ssl_txt',
                                                                   'dg_txt',
                                                                   'cs_txt',
                                                                   'batch_management',
                                                                   'perishable',
                                                                   'type',
                                                                   'subtype',],
                                                                  context=context)
        product_dict = dict([(x['id'], x) for x in product_list_dict])

        for stock_move_dict in read_result:
            stock_move_id = stock_move_dict['id']
            product_id = stock_move_dict['product_id'][0]
            product = product_dict[product_id]
            # cold chain
            result[stock_move_id]['kc_check'] = product['is_kc'] and 'X' or ''
            # ssl
            result[stock_move_id]['ssl_check'] = product['ssl_txt']
            # dangerous goods
            result[stock_move_id]['dg_check'] = product['dg_txt']
            # narcotic
            result[stock_move_id]['np_check'] = product['cs_txt']
            # lot management
            if product['batch_management']:
                result[stock_move_id]['lot_check'] = True
            # expiry date management
            if product['perishable']:
                result[stock_move_id]['exp_check'] = True
            # contains a kit and allow the creation of a new composition LIst
            # will be false if the kit is batch management and a composition list already uses this batch number
            # only one composition list can  use a given batch number for a given product
            if product['type'] == 'product' and product['subtype'] == 'kit':
                if stock_move_dict['prodlot_id']:
                    # search if composition list already use this batch number
                    kit_ids = kit_obj.search(cr, uid, [('composition_lot_id', '=', stock_move_dict['prodlot_id'][0])], context=context)
                    if not kit_ids:
                        result[stock_move_id]['kit_check'] = True
                else:
                    # not batch management, we can create as many composition list as we want
                    result[stock_move_id]['kit_check'] = True
        return result

    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'CC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''

        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id:
                if move.product_id.is_kc:
                    result[move.id] += move.product_id.is_kc and _('CC') or ''
                if move.product_id.dg_txt:
                    if result[move.id]:
                        result[move.id] += ' / '
                    result[move.id] += move.product_id.is_dg and _('DG') or '%s ?'%_('DG')

        return result

    def _get_product_type(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for move in self.browse(cr, uid, ids, fields_to_fetch=['product_id'], context=context):
            res[move.id] = move.product_id.type

        return res

    def _get_product_type_selection(self, cr, uid, context=None):
        return self.pool.get('product.template').PRODUCT_TYPE

    def _get_pick_shipment_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Link the shipment where a stock move is to this stock move
        """
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]

        if context is None:
            context = {}

        picking_ids = self.pool.get('stock.picking').search(cr, uid, [('id', 'in', ids), ('shipment_id', '!=', False)], order='NO_ORDER', context=context)
        return self.pool.get('stock.move').search(cr, uid, [('picking_id', 'in', picking_ids)], order='NO_ORDER', context=context)

    def _product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        facade for product_available function from product (stock)
        '''
        # get the corresponding product ids
        result = {}
        for d in self.read(cr, uid, ids, ['product_id'], context):
            result[d['id']] = d['product_id'][0]

        # get the virtual stock identified by product ids
        virtual = self.pool.get('product.product')._product_available(cr, uid, list(result.values()), field_names, arg, context)

        # replace product ids by corresponding stock move id
        result = dict([move_id, virtual[result[move_id]]] for move_id in list(result.keys()))
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
                                           ['dg_txt', 'is_kc', 'cs_txt'], context=context)
            result[move['id']]['is_dangerous_good'] = move['product_id'] and product['dg_txt'] or ''
            # cold chain
            result[move['id']]['is_keep_cool'] = move['product_id'] and product['is_kc'] and 'X' or ''
            # narcotic
            result[move['id']]['is_narcotic'] = move['product_id'] and product['cs_txt'] or ''
        return result

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        get functional values
        '''
        result = {}
        uom_obj = self.pool.get('product.uom')
        ftf = ['sale_line_id', 'product_uom', 'to_pack', 'from_pack', 'product_qty', 'pick_shipment_id', 'picking_id',
               'state', 'not_shipped']
        for move in self.read(cr, uid, ids, ftf, context=context):
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
            if move['product_uom']:
                uom_rounding = uom_obj.read(cr, uid, move['product_uom'][0], ['rounding'], context=context)['rounding']
                result[move['id']]['product_uom_rounding_is_pce'] = uom_rounding == 1
            # Give the Returned state to the Shipment's lines popup lines if the pack.family.memory is Returned
            ship_influenced_state = move['state']
            if move['pick_shipment_id'] and move['picking_id'] and move['not_shipped']:
                ship_influenced_state = 'returned'
            result[move['id']]['ship_influenced_state'] = ship_influenced_state

        return result

    def _get_picking_with_sysint_name(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['picking_id', 'linked_incoming_move'], context=context):
            if x.linked_incoming_move:
                res[x.id] = '%s [%s]' % (x.linked_incoming_move.picking_id.name, x.picking_id.name)
            else:
                res[x.id] = x.picking_id.name
        return res


    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'priority': fields.selection([('0', 'Not urgent'), ('1', 'Urgent')], 'Priority'),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'date': fields.datetime('Actual Receipt Date', required=True, select=True, help="Move date: scheduled date until move is done, then date of actual move processing", readonly=True),
        'date_expected': fields.datetime('Scheduled Date', states={'done': [('readonly', True)]},required=True, select=True, help="Scheduled date for the processing of this move"),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True, domain=[('type','<>','service')],states={'done': [('readonly', True)]}),

        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM'), required=True,states={'done': [('readonly', True)]}, related_uom='product_uom'),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure', required=True,states={'done': [('readonly', True)]}),
        'product_uos_qty': fields.float('Quantity (UOS)', digits_compute=dp.get_precision('Product UoM'), states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, related_uom='product_uos_qty'),
        'product_uos': fields.many2one('product.uom', 'Product UOS', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'product_packaging': fields.many2one('product.packaging', 'Packaging', help="It specifies attributes of packaging like type, quantity of packaging,etc."),
        'product_uom_rounding': fields.related('product_uom', 'rounding', type='float', string="UoM Rounding", digits_compute=dp.get_precision('Product UoM'), store=False, write_relate=False),
        'product_uom_rounding_is_pce': fields.function(_vals_get, method=True, type='boolean', string="UoM Rounding is PCE", multi='get_vals', store=False, readonly=True),

        'location_id': fields.many2one('stock.location', 'Source Location', required=True, select=True,states={'done': [('readonly', True)]}, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', required=True,states={'done': [('readonly', True)]}, select=True, help="Location where the system will stock the finished products."),
        'address_id': fields.many2one('res.partner.address', 'Destination Address', help="Optional address where goods are to be delivered, specifically used for allotment"),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', states={'done': [('readonly', True)]}, select=True, help="Batch number is used to put a serial number on the production"),
        'old_lot_info': fields.text('Old BN/ED info', readonly=True, help="Old BN in case of attr. switch"),
        'tracking_id': fields.many2one('stock.tracking', 'Pack', select=True, states={'done': [('readonly', True)]}, help="Logistical shipping unit: pallet, box, pack ..."),

        'auto_validate': fields.boolean('Auto Validate'),

        'move_dest_id': fields.many2one('stock.move', 'Destination Move', help="Optional: next stock move when chaining them", select=True),
        'move_history_ids': fields.many2many('stock.move', 'stock_move_history_ids', 'parent_id', 'child_id', 'Move History (child moves)'),
        'move_history_ids2': fields.many2many('stock.move', 'stock_move_history_ids', 'child_id', 'parent_id', 'Move History (parent moves)'),
        'picking_id': fields.many2one('stock.picking', 'Reference', select=True,states={'done': [('readonly', True)]}),
        'note': fields.text('Notes'),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
                                  help='When the stock move is created it is in the \'Draft\' state.\n After that, it is set to \'Not Available\' state if the scheduler did not find the products.\n When products are reserved it is set to \'Available\'.\n When the picking is done the state is \'Done\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Account'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'price_currency_id': fields.many2one('res.currency', 'Currency for average price', help="Technical field used to record the currency chosen by the user during a picking confirmation (when average price costing method is used)"),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'partner_id': fields.related('picking_id','address_id','partner_id',type='many2one', relation="res.partner", string="Partner", store=True, select=True, write_relate=False),
        'backorder_id': fields.related('picking_id','backorder_id',type='many2one', relation="stock.picking", string="Back Order", select=True, write_relate=False),
        'origin': fields.related('picking_id','origin',type='char', size=512, relation="stock.picking", string="Origin", store=True, write_relate=False),

        # used for colors in tree views:
        'scrapped': fields.related('location_dest_id','scrap_location',type='boolean',relation='stock.location',string='Scrapped', readonly=True),

        'qty_to_process': fields.float('Qty to Process', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom'),
        'qty_processed': fields.float('Qty Processed', help="Main pick, resgister sum of qties processed"),
        'confirmed_qty': fields.float('Confirmed Quantity', digits_compute=dp.get_precision('Product UoM'), readonly=True, related_uom='product_uom', help="Quantity saved during the IN move's confirmation"),
        'type': fields.related('picking_id', 'type', string='Type', type='selection',
                               selection = [('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], readonly=True,
                               store = {
                                   'stock.picking': (_get_picking_ids, ['type'], 20),
                                   'stock.move': (lambda self, cr, uid, ids, c=None: ids, ['picking_id'], 20),
                               }
                               ),
        'expired_date': fields.related('prodlot_id', 'life_date', string='Expiry Date', type='date', readonly=True,
                                       store={
                                           'stock.production.lot': (_get_lot_ids, ['life_date'], 20),
                                           'stock.move': (lambda self, cr, uid, ids, c=None: ids, ['prodlot_id'], 20),
                                       }
                                       ),
        'line_number': fields.integer(string='Line', required=True),
        'change_reason': fields.char(string='Change Reason', size=1024, readonly=True),
        'in_out_updated': fields.boolean(string='IN update OUT'),
        'original_qty_partial': fields.float(string='Original Qty for Partial process - only for sync and partial processed line', required=False, digits_compute=dp.get_precision('Product UoM')),
        'pack_info_id': fields.many2one('wizard.import.in.pack.simulation.screen', 'Pack Info'),
        'asset_id': fields.many2one('product.asset', 'Asset'),
        'subtype': fields.char(string='Product Subtype', size=128),
        'move_cross_docking_ok': fields.boolean('Cross docking'),
        'direct_incoming': fields.boolean('Direct incoming'),
        'allocation_setup': fields.function(_get_allocation_setup, type='selection',
                                            selection=[('allocated', 'Allocated'),
                                                       ('unallocated', 'Unallocated'),
                                                       ('mixed', 'Mixed')], string='Allocated setup', method=True, store=False),
        'purchase_line_id': fields.many2one('purchase.order.line', 'Purchase Order Line', ondelete='set null', select=True, readonly=True),
        # picking.subtype is known later in msf_ourgoing module: so do not migrate
        'picking_subtype': fields.related('picking_id', 'subtype', string='Picking Subtype', type='char', size=64, write_relate=False, store=True, _fnct_migrate=lambda *a: True),
        'parent_doc_id': fields.function(_get_parent_doc, method=True, type='char', string='Picking', readonly=True),

        'order_priority': fields.function(_get_order_information, method=True, string='Priority', type='selection',
                                          selection=ORDER_PRIORITY, multi='move_order', fnct_search=_search_order),
        'order_category': fields.function(_get_order_information, method=True, string='Category', type='selection',
                                          selection=ORDER_CATEGORY, multi='move_order', fnct_search=_search_order),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection',
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                                 ('loan_return', 'Loan Return'), ('in_kind', 'In Kind Donation'),
                                                 ('purchase_list', 'Purchase List'), ('direct', 'Direct Purchase Order')],
                                      multi='move_order', fnct_search=_search_order),
        'sale_ref_id': fields.related('sale_line_id', 'order_id', type='many2one', relation='sale.order', string='Sale', readonly=True),
        'purchase_ref_id': fields.related('purchase_line_id', 'order_id', type='many2one', relation='purchase.order', string='Purchase', readonly=True),
        'init_inv_ids': fields.many2many('initial.stock.inventory', 'initial_stock_inventory_move_rel', 'move_id', 'inventory_id', 'Created Moves'),

        'kit_creation_id_stock_move': fields.many2one('kit.creation', string='Kit Creation', readonly=True),
        'to_consume_id_stock_move': fields.many2one('kit.creation.to.consume', string='To Consume Line', readonly=True),# link to to consume line - is not deleted anymore ! but colored
        'original_from_process_stock_move': fields.boolean(string='Original', readonly=True),
        'hidden_state': fields.function(_vals_get_kit_creation, method=True, type='selection', selection=KIT_SELECTION, string='Hidden State', multi='get_vals_kit_creation', store=False, readonly=True),
        'hidden_prodlot_id': fields.function(_vals_get_kit_creation, method=True, type='boolean', string='Hidden Prodlot', multi='get_vals_kit_creation', store=False, readonly=True),
        'hidden_exp_check': fields.function(_vals_get_kit_creation, method=True, type='boolean', string='Hidden Expiry Check', multi='get_vals_kit_creation', store=False, readonly=True),
        'hidden_asset_check': fields.function(_vals_get_kit_creation, method=True, type='boolean', string='Hidden Asset Check', multi='get_vals_kit_creation', store=False, readonly=True),
        'hidden_creation_state': fields.function(_vals_get_kit_creation, method=True, type='selection', selection=KIT_CREATION_STATE, string='Hidden Creation State', multi='get_vals_kit_creation', store=False, readonly=True),
        'assigned_qty_stock_move': fields.function(_vals_get_kit_creation, method=True, type='float', string='Assigned Qty', multi='get_vals_kit_creation', store=False, readonly=True),
        'hidden_creation_qty_stock_move': fields.function(_vals_get_kit_creation, method=True, type='float', string='Hidden Creation Qty', multi='get_vals_kit_creation', store=False, readonly=True),
        'kol_lot_manual': fields.boolean(string='The batch is set manually'),

        # specific rule
        'kc_dg': fields.function(_kc_dg, method=True, string='CC/DG', type='char'),
        'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
        'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
        'kc_check': fields.function(_get_checks_all, method=True, string='CC', type='char', size=8, readonly=True, multi="m"),
        'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='char', size=8, readonly=True, multi="m"),
        'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='char', size=8, readonly=True, multi="m"),
        'np_check': fields.function(_get_checks_all, method=True, string='CS', type='char', size=8, readonly=True, multi="m"),
        'lot_check': fields.function(_get_checks_all, method=True, string='BN', type='boolean', readonly=True, multi="m"),
        'exp_check': fields.function(_get_checks_all, method=True, string='ED', type='boolean', readonly=True, multi="m"),
        'kit_check': fields.function(_get_checks_all, method=True, string='Kit', type='boolean', readonly=True, multi="m"),

        # reason types
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
        'comment': fields.char(size=300, string='Comment'),
        'product_type': fields.function(_get_product_type, method=True, type='selection', selection=_get_product_type_selection, string='Product type',
                                        store={'stock.move': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 20), }),
        'not_chained': fields.boolean(string='Not chained', help='If checked, the chaining move will not be run.'),
        'sale_line_id': fields.many2one('sale.order.line', 'Sales Order Line', ondelete='set null', select=True, readonly=True),

        # msf_outgoing
        'from_pack': fields.integer(string='From p.'),
        'to_pack': fields.integer(string='To p.'),
        'parcel_comment': fields.char(string='Parcel Comment', size=256),
        'ppl_returned_ok': fields.boolean(string='Has been returned ?', readonly=True, internal=True),
        'integrity_error': fields.selection(INTEGRITY_STATUS_SELECTION, 'Error', readonly=True),
        'pack_type': fields.many2one('pack.type', string='Pack Type'),
        'length': fields.float(digits=(16, 2), string='Length [cm]'),
        'width': fields.float(digits=(16, 2), string='Width [cm]'),
        'height': fields.float(digits=(16, 2), string='Height [cm]'),
        'weight': fields.float(digits=(16, 2), string='Weight p.p [kg]'),
        'initial_location': fields.many2one('stock.location', string='Initial Picking Location'),
        # relation to the corresponding move from draft **picking** ticket object
        'backmove_id': fields.many2one('stock.move', string='Corresponding move of previous step'),
        # relation to the corresponding move from draft **packing** ticket object
        'backmove_packing_id': fields.many2one('stock.move', string='Corresponding move of previous step in draft packing'),
        'virtual_available': fields.function(_product_available, method=True, type='float', string='Virtual Stock', help="Future stock for this product according to the selected locations or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming.", multi='qty_available', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom'),
        'qty_per_pack': fields.function(_get_qty_per_pack, method=True, type='float', string='Qty p.p'),
        'total_amount': fields.function(_vals_get, method=True, type='float', string='Total Amount', digits_compute=dp.get_precision('Picking Price'), multi='get_vals',),
        'amount': fields.function(_vals_get, method=True, type='float', string='Pack Amount', digits_compute=dp.get_precision('Picking Price'), multi='get_vals',),
        'num_of_packs': fields.function(_get_num_of_pack, method=True, type='integer', string='#Packs'),  # old_multi get_vals
        'currency_id': fields.function(_vals_get, method=True, type='many2one', relation='res.currency', string='Currency', multi='get_vals',),
        'is_dangerous_good': fields.function(_get_danger, method=True, type='char', size=8, string='Dangerous Good', multi='get_danger'),
        'is_keep_cool': fields.function(_get_danger, method=True, type='char', size=8, string='Cold Chain', multi='get_danger',),
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
        'ship_influenced_state': fields.function(_vals_get, method=True, store=False, string='State', type='selection',
                                                 selection=[('draft', 'Draft'), ('waiting', 'Waiting'),
                                                            ('confirmed', 'Not Available'), ('assigned', 'Available'),
                                                            ('done', 'Closed'), ('cancel', 'Cancelled'),
                                                            ('returned', 'Returned')], readonly=True, multi='get_vals'),
        'from_manage_expired_move': fields.related('picking_id', 'from_manage_expired', string='Manage Expired', type='boolean', readonly=True),
        'location_virtual_id': fields.many2one('stock.location', string='Virtual location'),
        'location_output_id': fields.many2one('stock.location', string='Output location'),
        'invoice_line_id': fields.many2one('account.invoice.line', string='Invoice line'),
        'pt_created': fields.boolean(string='PT created'),
        'not_shipped': fields.boolean(string='Not shipped'),
        'old_out_location_dest_id': fields.many2one('stock.location', string='Old OUT dest location', help='Usefull in case of OUT converted to PICK and converted back to OUT'),
        'ppl_wizard_id': fields.many2one('ppl.family.processor', 'PPL processor', ondelete='set null', readonly=1, internal=1),
        'selected_number': fields.integer('Nb. Parcels to Ship'),
        'volume_set': fields.boolean('Volume set at PLL stage', readonly=1),
        'weight_set': fields.boolean('Weight set at PLL stage', readonly=1),
        'picking_with_sysint_name': fields.function(_get_picking_with_sysint_name, method=1, string='Picking IN [SYS-INT] name', type='char'),
        'included_in_mission_stock': fields.boolean('Stock move used to compute MSRL', internal=1, select=1),
        'in_forced': fields.boolean('IN line forced'),

        'mml_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MML', multi='mml'),
        'msl_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MSL', multi='mml'),

    }

    def _check_asset(self, cr, uid, ids, context=None):
        """ Checks if asset is assigned to stock move or not.
        @return: True or False
        """
        return True

    def _check_constaints_service(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        if ids:
            cr.execute("""select
                count(pick.type = 'in' and t.type in ('service_recep', 'service') and not dest.service_location and not dest.cross_docking_location_ok and not pick.sync_dpo_in or NULL),
                count(pick.type = 'internal' and not src.cross_docking_location_ok and t.type in ('service_recep', 'service') or NULL),
                count(pick.type = 'internal' and not dest.service_location and t.type in ('service_recep', 'service') or NULL),
                count(t.type in ('service_recep', 'service') and pick.type = 'out' and pick.subtype in ('standard', 'picking') and not src.cross_docking_location_ok and not pick.dpo_out or NULL),
                count(t.type not in ('service_recep', 'service') and (dest.service_location or src.service_location ) or NULL)
                from stock_move m
                left join stock_picking pick on m.picking_id = pick.id
                left join product_product p on m.product_id = p.id
                left join product_template t on p.product_tmpl_id = t.id
                left join stock_location src on m.location_id = src.id
                left join stock_location dest on m.location_dest_id = dest.id
            where m.id in %s""", (tuple(ids),))
            for res in cr.fetchall():
                if res[0]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Service or Cross Docking Location as Destination Location.'))
                if res[1]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Cross Docking Location as Source Location.'))
                if res[2]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Service Location as Destination Location.'))
                if res[3]:
                    raise osv.except_osv(_('Error'), _('Service Products must have Cross Docking Location as Source Location.'))
                if res[4]:
                    raise osv.except_osv(_('Error'), _('Service Location cannot be used for non Service Products.'))
        return True

    def _check_tracking(self, cr, uid, ids, context=None):
        """
        check for batch management
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done' and move.location_id.id != move.location_dest_id.id:
                if move.product_id.batch_management:
                    if not move.prodlot_id and move.product_qty and not self.is_out_move_linked_to_dpo(cr, uid, move.id, context=context):
                        raise osv.except_osv(_('Error!'),  _('You must assign a Batch Number for this product (Batch Number Mandatory).'))
                if move.product_id.perishable:
                    if not move.prodlot_id and move.product_qty and not self.is_out_move_linked_to_dpo(cr, uid, move.id, context=context):
                        raise osv.except_osv(_('Error!'),  _('You must assign an Expiry Date for this product (Expiry Date Mandatory).'))
            if move.prodlot_id:
                if not move.product_id.perishable and not move.product_id.batch_management:
                    raise osv.except_osv(_('Error!'),  _('The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory.'))
                if move.prodlot_id.type == 'internal' and move.product_id.batch_management:
                    raise osv.except_osv(_('Error!'),  _('The selected product is Batch Number Mandatory while the selected Batch number corresponds to Expiry Date Mandatory.'))
                if move.prodlot_id.type == 'standard' and not move.product_id.batch_management and move.product_id.perishable:
                    raise osv.except_osv(_('Error!'),  _('The selected product is Expiry Date Mandatory while the selected Batch number corresponds to Batch Number Mandatory.'))
            if not move.prodlot_id and move.product_qty and \
               (move.state == 'done' and \
                    ( \
                        (move.product_id.track_production and move.location_id.usage == 'production') or \
                        (move.product_id.track_production and move.location_dest_id.usage == 'production') or \
                        (move.product_id.track_incoming and move.location_id.usage == 'supplier' and move.location_id.id != move.location_dest_id.id) or   # dpo sync from proj to coo
                        (move.product_id.track_outgoing and move.location_dest_id.usage == 'customer') \
                    )):
                raise osv.except_osv(_('Error!'),  _('You must assign a batch number for this product.'))

        return True

    def _check_reason_type(self, cr, uid, ids, context=None):
        """
        Do not permit user to create/write an OUT from scratch with some reason types:
         - GOODS RETURN UNIT
         - GOODS REPLACEMENT
         - OTHER
        Only permet user to create/write a non-claim IN move from scratch with some reason types:
         - EXTERNAL SUPPLY
         - INTERNAL SUPPLY
         - RETURN FROM UNIT
         - LOSS
         - SCRAP
        """
        data_obj = self.pool.get('ir.model.data')
        res = True
        try:
            rt_replacement_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_replacement')[1]
            rt_other_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
            rt_return_unit_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]
            int_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1]
            ext_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
            loss_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            scrp_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
        except ValueError:
            rt_replacement_id = 0
            rt_other_id = 0
            rt_return_unit_id = 0
            int_rt_id = 0
            ext_rt_id = 0
            loss_rt_id = 0
            scrp_rt_id = 0

        for sm in self.read(cr, uid, ids, ['reason_type_id', 'picking_id']):
            if sm['reason_type_id'] and sm['picking_id']:
                pick = self.pool.get('stock.picking').read(cr, uid, sm['picking_id'][0], ['purchase_id', 'sale_id', 'type', 'claim'], context=context)
                if not pick['purchase_id'] and not pick['sale_id'] \
                        and ((pick['type'] == 'in' and not pick['claim']
                              and sm['reason_type_id'][0] not in [int_rt_id, ext_rt_id, rt_return_unit_id, loss_rt_id, scrp_rt_id])
                             or (pick['type'] == 'out' and sm['reason_type_id'][0] in [rt_replacement_id, rt_return_unit_id, rt_other_id])):
                    return False
        return res

    def _invalid_reason_type_msg(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        doc = _('a document')
        if context.get('picking_type'):
            if context['picking_type'] == 'incoming_shipment':
                doc = _('an IN')
            elif context['picking_type'] == 'delivery_order':
                doc = _('an OUT')
        msg = _('Wrong reason type for %s created from scratch.') % (doc,)

        return msg


    _constraints = [
        (_check_constaints_service, 'You cannot select Service Location as Source Location.', []),
        (_check_tracking, 'You must assign a batch number for this product.', ['prodlot_id']),
        (_check_reason_type, _invalid_reason_type_msg, ['reason_type_id', ]),
    ]

    _defaults = {
        'location_id': lambda self, cr, uid, c: self._default_location_source(cr, uid, context=c),
        'location_dest_id': lambda self, cr, uid, c: self._default_location_destination(cr, uid, context=c),
        'state': 'draft',
        'priority': '1',
        'product_qty': 1.0,
        'scrapped' :  False,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.move', context=c),
        'date_expected': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'line_number': 0,
        'in_out_updated': False,
        'original_qty_partial': -1,
        'direct_incoming': False,
        'to_consume_id_stock_move': False,
        'original_from_process_stock_move': False,
        'reason_type_id': lambda obj, cr, uid, context = {}: context.get('reason_type_id', False) and context.get('reason_type_id') or False,
        'not_chained': lambda *a: False,
        'integrity_error': 'empty',
        'included_in_mission_stock': False,
        'in_forced': False,
        'confirmed_qty': 0.0,
        'mml_status': 'na',
        'msl_status': 'na',
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """ To get default values for the object:
        If cross docking is checked on the purchase order, we set "cross docking" to the destination location
        else we keep the default values i.e. "Input"
        """
        default_data = super(stock_move, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        default_data.update({'allocation_setup': setup.allocation_setup})
        if context is None:
            context = {}
        purchase_id = context.get('purchase_id', [])
        if not purchase_id:
            return default_data
        purchase_browse = self.pool.get('purchase.order').browse(cr, uid, purchase_id, context=context)
        # If the purchase order linked has the option cross docking then the new created
        #stock move should have the destination location to cross docking
        if purchase_browse.cross_docking_ok:
            default_data.update({'location_dest_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})
        default_data['date'] = default_data['date_expected'] = context.get('date_expected', time.strftime('%Y-%m-%d %H:%M:%S'))

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
            default_data.update({'location_output_id': warehouse_obj.read(cr, uid,
                                                                          warehouse_id, ['lot_output_id'], context=context)['lot_output_id'][0]})

        loc_virtual_ids = self.pool.get('stock.location').search(cr, uid, [('name', '=', 'Virtual Locations')])
        loc_virtual_id = len(loc_virtual_ids) > 0 and loc_virtual_ids[0] or False
        default_data.update({'location_virtual_id': loc_virtual_id})

        if 'type' in context and context.get('type', False) == 'out':
            loc_stock_id = warehouse_obj.read(cr, uid,
                                              warehouse_id, ['lot_stock_id'], context=context)['lot_stock_id'][0]
            default_data.update({'location_id': loc_stock_id})

        if 'subtype' in context and context.get('subtype', False) == 'picking':
            loc_packing_id = warehouse_obj.read(cr, uid, warehouse_id,
                                                ['lot_packing_id'], context=context)['lot_packing_id'][0]
            default_data.update({'location_dest_id': loc_packing_id})
        elif 'subtype' in context and context.get('subtype', False) == 'standard' and not auto_company:
            loc_output_id = warehouse_obj.read(cr, uid, warehouse_id,
                                               ['lot_output_id'], context=context)['lot_output_id'][0]
            default_data.update({'location_dest_id': loc_output_id})


        return default_data

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Take into account all stock_picking with reason_type_id is a children
        '''

        new_args = []

        for arg in args:
            if arg[0] == 'reason_type_id' and arg[1] in ('=', 'in'):
                new_arg = (arg[0], 'child_of', arg[2])
            else:
                new_arg = arg
            new_args.append(new_arg)

        return super(stock_move, self).search(cr, uid, new_args, offset=offset,
                                              limit=limit, order=order, context=context, count=count)


    def _default_location_destination(self, cr, uid, context=None):
        """ Gets default address of partner for destination location
        @return: Address id or False
        """
        if context is None:
            context = {}
        if context.get('move_line', []):
            if context['move_line'][0]:
                if isinstance(context['move_line'][0], (tuple, list)):
                    return context['move_line'][0][2] and context['move_line'][0][2].get('location_dest_id',False)
                else:
                    move_list = self.pool.get('stock.move').read(cr, uid, context['move_line'][0], ['location_dest_id'])
                    return move_list and move_list['location_dest_id'][0] or False
        if context.get('address_out_id', False):
            property_out = self.pool.get('res.partner.address').browse(cr, uid, context['address_out_id'], context).partner_id.property_stock_customer
            return property_out and property_out.id or False
        return False

    def _default_location_source(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        if context is None:
            context = {}

        if context.get('ext_cu', False):
            return context['ext_cu']

        if context.get('move_line', []):
            try:
                return context['move_line'][0][2]['location_id']
            except:
                pass
        if context.get('address_in_id', False):
            part_obj_add = self.pool.get('res.partner.address').browse(cr, uid, context['address_in_id'], context=context)
            if part_obj_add.partner_id:
                return part_obj_add.partner_id.property_stock_supplier.id
        return False

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context= {}
        if vals.get('from_pack') or vals.get('to_pack'):
            vals['integrity_error'] = 'empty'
        vals.update({
            'to_correct_ok': False,
            'text_error': False,
        })
        if 'date_expected' in vals and not context.get('chained'):
            # TODO JFB RR: check method executed 2X
            sys_int_ids = self.search(cr, uid, [('linked_incoming_move', 'in', ids)], context=context)
            if sys_int_ids:
                chained_ctx = context.copy()
                chained_ctx['chained'] = True
                self.write(cr, uid, sys_int_ids, {'date_expected': vals['date_expected']}, context=chained_ctx)
            else:
                # get all pol ids linked to internal, intersection, mission partners
                cr.execute('''
                    select sol.id
                        from purchase_order_line pol
                            cross join sale_order_line sol
                            cross join sale_order so
                            cross join stock_move m
                        where
                            sol.id = pol.sale_order_line_id and
                            so.id = sol.order_id and
                            m.purchase_line_id = pol.id and
                            so.partner_type in ('internal', 'section', 'intermission') and
                            m.type = 'in' and
                            m.date_expected != %s and
                            m.id in %s and
                            sol.state = 'confirmed' and
                            so.procurement_request = 'f'
                ''', (vals['date_expected'], tuple(ids)))
                for x in cr.fetchall():
                    self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', x[0], {},
                                                                                          'purchase.order.line.update_date_expected', False, check_identifier=False, context=context, extra_arg={'date_expected': vals['date_expected']}, force_domain=True)

        return  super(stock_move, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        prod_obj = self.pool.get('product.product')

        default = default.copy()
        if 'in_forced' not in default:
            default['in_forced'] = False
        if 'qty_processed' not in default:
            default['qty_processed'] = 0
        if default.get('picking_id') and 'reason_type_id' not in default:
            pick = self.pool.get('stock.picking').browse(cr, uid, default.get('picking_id'), context=context)
            default['reason_type_id'] = pick.reason_type_id.id
        if 'pt_created' not in default:
            default['pt_created'] = False
        if 'integrity_error' not in default:
            default['integrity_error'] = 'empty'
        if not context.get('from_button'):
            default['composition_list_id'] = False
        default['included_in_mission_stock'] = False

        new_id = super(stock_move, self).copy(cr, uid, id, default, context=context)
        if 'product_id' in default:  # Check constraints on lines
            move = self.browse(cr, uid, new_id, fields_to_fetch=['type', 'picking_id', 'location_dest_id', 'product_id'], context=context)
            if move.type == 'in':
                prod_obj._get_restriction_error(cr, uid, [move.product_id.id], {'location_dest_id': move.location_dest_id.id, 'obj_type': 'in', 'partner_type':  move.picking_id.partner_id.partner_type},
                                                context=context)
            elif move.type == 'out' and move.product_id.state.code == 'forbidden':
                check_vals = {'location_dest_id': move.location_dest_id.id, 'move': move}
                prod_obj._get_restriction_error(cr, uid, [move.product_id.id], check_vals, context=context)

        return new_id

    def copy_data(self, cr, uid, id, defaults=None, context=None):
        '''
        If the line_number is not in the defaults, we set it to False.
        If we are on an Incoming Shipment: we reset purchase_line_id field
        and we set the location_dest_id to INPUT.
        '''
        if defaults is None:
            defaults = {}
        if context is None:
            context = {}

        data_obj = self.pool.get('ir.model.data')

        defaults['procurements'] = []
        defaults['original_from_process_stock_move'] = False
        defaults['included_in_mission_stock'] = False
        if 'in_forced' not in defaults:
            defaults['in_forced'] = False

        # we set line_number, so it will not be copied in copy_data - keepLineNumber - the original Line Number will be kept
        if 'line_number' not in defaults and not context.get('keepLineNumber', False):
            defaults.update({'line_number': False})

        if 'pack_info_id' not in defaults:
            defaults['pack_info_id'] = False

        if context.get('subtype') != 'in' or (context.get('from_button') and context.get('web_copy')):
            defaults['confirmed_qty'] = 0

        if context.get('from_button') and context.get('web_copy'):
            if context.get('picking_type') == 'delivery_order':
                defaults['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
            elif context.get('picking_type') == 'incoming_shipment':
                defaults['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]

        # the tag 'from_button' was added in the web client (openerp/controllers/form.py in the method duplicate) on purpose
        if context.get('from_button'):
            # UF-1797: when we duplicate a doc we delete the link with the poline
            if 'purchase_line_id' not in defaults and not context.get('keepPoLine', False):
                defaults.update(purchase_line_id=False)
            if context.get('web_copy', False):
                if 'sale_line_id' not in defaults:
                    defaults.update(sale_line_id=False)
                defaults['composition_list_id'] = False
            if context.get('subtype', False) == 'incoming':
                # we reset the location_dest_id to 'INPUT' for the 'incoming shipment'
                input_loc = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
                defaults.update(location_dest_id=input_loc)
        else:
            defaults['composition_list_id'] = False

        return super(stock_move, self).copy_data(cr, uid, id, defaults, context=context)

    def onchange_lot_processor(self, cr, uid, ids, lot_id, qty, location_id, uom_id, context=None):
        ret = self.pool.get('stock.move.processor').change_lot(cr, uid, ids, lot_id, qty, location_id, uom_id, context)
        if 'expiry_date' in ret.get('value', {}):
            ret['value']['expired_date'] = ret['value']['expiry_date']
        return ret

    def onchange_expiry_processor(self, cr, uid, ids, expiry_date=False, product_id=False, type_check=False, context=None):
        ret = self.pool.get('stock.move.processor').change_expiry(cr, uid, ids, expiry_date, product_id, type_check, context)
        if 'expiry_date' in ret.get('value', {}):
            ret['value']['expired_date'] = ret['value']['expiry_date']
        return ret

    def onchange_qty_to_process(self, cr, uid, ids, qty_to_process, product_qty, uom_id, context=None):
        if qty_to_process > product_qty:
            return {
                'value': {'qty_to_process': 0},
                'warning': {
                    'title': _('Warning'),
                    'message': _("Processing Qty can't be larger than move qty.")
                }
            }
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty_to_process, fields_q=['qty_to_process'], context=context)

    def onchange_lot_id(self, cr, uid, ids, prodlot_id=False, product_qty=False,
                        loc_id=False, product_id=False, uom_id=False, context=None):
        """ On change of production lot gives a warning message.
        @param prodlot_id: Changed production lot id
        @param product_qty: Quantity of product
        @param loc_id: Location id
        @param product_id: Product id
        @return: Warning message
        """
        if not prodlot_id or not loc_id:
            return {}
        ctx = context and context.copy() or {}
        ctx['location_id'] = loc_id
        ctx.update({'raise-exception': True})

        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')


        product_uom = product_obj.browse(cr, uid, product_id, fields_to_fetch=['uom_id'], context=ctx).uom_id
        prodlot = self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, fields_to_fetch=['stock_available'],  context=ctx)
        location = self.pool.get('stock.location').browse(cr, uid, loc_id, context=ctx)
        uom = uom_obj.browse(cr, uid, uom_id, context=ctx)
        amount_actual = uom_obj._compute_qty_obj(cr, uid, product_uom, prodlot.stock_available, uom, context=ctx)
        warning = {}
        if (location.usage == 'internal') and (product_qty > (amount_actual or 0.0)):
            warning = {
                'title': _('Insufficient Stock in Lot !'),
                'message': _('You are moving %.2f %s products but only %.2f %s available in this lot.') % (product_qty, uom.name, amount_actual, uom.name)
            }
        return {'warning': warning}

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty,
                          product_uom, product_uos):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_qty: Changed Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'value' : {'product_uos_qty': 0.00}
        }

        if (not product_id) or (product_qty <=0.0):
            return result

        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, product_qty, ['product_qty', 'product_uos_qty'], result)

    def onchange_uos_quantity(self, cr, uid, ids, product_id, product_uos_qty,
                              product_uos, product_uom):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_uos_qty: Changed UoS Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_qty': 0.00
        }

        if (not product_id) or (product_uos_qty <=0.0):
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_qty'] = product_uos_qty / uos_coeff['uos_coeff']
        else:
            result['product_qty'] = product_uos_qty

        return {'value': result}

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, address_id=False, parent_type=False, purchase_line_id=False, out=False, context=None):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_id: Destination location id
        @param address_id: Address id of partner
        @return: Dictionary of values
        """

        result = {
            'value': {
                'product_type': False,
                'hidden_batch_management_mandatory': False,
                'hidden_perishable_mandatory': False,
                'prodlot_id': False,
                'expired_date': False,
                'expiry_date': False,
            },
            'warning': {}}
        if not prod_id:
            if parent_type == 'in':
                result['value']['location_dest_id'] = False
            elif parent_type == 'out':
                result['value']['location_id'] = False
            else:
                result['value']['location_dest_id'] = False
                result['value']['location_id'] = False
            return result

        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')


        product = prod_obj.browse(cr, uid, [prod_id], context=context)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result['value'] = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'subtype': product.product_tmpl_id.subtype,
            'asset_id': False,
            'lot_check': product.batch_management,
            'exp_check': product.perishable,
            'product_qty': 0,
            'product_uos_qty': 0,
            'product_type': product.type,
        }
        if product.batch_management:
            result['value']['hidden_batch_management_mandatory'] = True
        elif product.perishable:
            result['value']['hidden_perishable_mandatory'] = True
        if not ids:
            result['value']['name'] = product.partner_ref
        if loc_id:
            result['value']['location_id'] = loc_id
        if loc_dest_id:
            result['value']['location_dest_id'] = loc_dest_id

        if parent_type and parent_type == 'internal' and loc_dest_id:
            # Test the compatibility of the product with the location
            result, test = self.pool.get('product.product')._on_change_restriction_error(cr, uid, prod_id, field_name='product_id', values=result, vals={'location_id': loc_dest_id}, context=context)
            if test:
                return result
        elif parent_type in ('in', 'out'):
            # Test the compatibility of the product with a stock move
            result, test = prod_obj._on_change_restriction_error(cr, uid, prod_id, field_name='product_id', values=result, vals={'constraints': ['picking']})

        if product.batch_management:
            result['warning'] = {'title': _('Info'), 'message': _('The selected product is Batch Management.')}
        elif product.perishable:
            result['warning'] = {'title': _('Info'), 'message': _('The selected product is Perishable.')}


        location_id = loc_id and location_obj.browse(cr, uid, loc_id) or False
        location_dest_id = loc_dest_id and location_obj.browse(cr, uid, loc_dest_id) or False
        service_loc = location_obj.get_service_location(cr, uid)
        non_stockable_loc = location_obj.search(cr, uid, [('non_stockable_ok', '=', True)])
        if non_stockable_loc:
            non_stockable_loc = non_stockable_loc[0]
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        input_id = location_obj.search(cr, uid, [('input_ok', '=', True)])
        if input_id:
            input_id = input_id[0]
        po = purchase_line_id and self.pool.get('purchase.order.line').browse(cr, uid, purchase_line_id) or False
        cd = po and po.order_id.cross_docking_ok or False
        packing_ids = []
        stock_ids = []

        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
            packing_ids.append(wh.lot_packing_id.id)
            stock_ids.append(wh.lot_stock_id.id)


        if product.type and parent_type == 'in':
            # Set service location as destination for service products
            if product.type in ('service_recep', 'service'):
                if service_loc:
                    result['value'].update(location_dest_id=service_loc)
            # Set cross-docking as destination for non-stockable with cross-docking context
            elif product.type == 'consu' and cd and loc_dest_id not in (id_cross, service_loc):
                result['value'].update(location_dest_id=id_cross)
            # Set non-stockable as destination for non-stockable without cross-docking context
            elif product.type == 'consu' and not cd and loc_dest_id not in (id_cross, service_loc):
                result['value'].update(location_dest_id=non_stockable_loc)
            # Set input for standard products
            elif product.type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                result['value'].update(location_dest_id=input_id)
        elif product.type and parent_type == 'internal':
            # Source location
            # Only cross-docking is available for Internal move for non-stockable products
            if product.type == 'consu' and not (loc_id and (location_id.cross_docking_location_ok or location_id.quarantine_location)):
                result['value'].update(location_id=id_cross)
            elif product.type == 'product' and not (loc_id and (location_id.usage == 'internal' or location_dest_id.virtual_ok)):
                result['value'].update(location_id=stock_ids and stock_ids[0] or False)
            elif product.type == 'service_recep':
                result['value'].update(location_id=id_cross)
            # Destination location
            if product.type == 'consu' and not (loc_dest_id and (location_dest_id.usage == 'inventory' or location_dest_id.destruction_location or location_dest_id.quarantine_location)):
                result['value'].update(location_dest_id=non_stockable_loc)
            elif product.type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                result['value'].update(location_dest_id=False)
            elif product.type == 'service_recep':
                result['value'].update(location_dest_id=service_loc)
        # Case when outgoing delivery or picking ticket
        elif product.type and parent_type == 'out':
            # Source location
            # Only cross-docking is available for Outgoing moves for non-stockable products
            if product.type == 'consu' and not (loc_id and location_id.cross_docking_location_ok):
                result['value'].update(location_id=id_cross)
            elif product.type == 'product' and not (loc_id and (location_id.usage == 'internal' or not location_id.quarantine_location or not location_id.output_ok or not location_id.input_ok)):
                result['value'].update(location_id=stock_ids and stock_ids[0] or False)
            elif product.type == 'service_recep':
                result['value'].update(location_id=id_cross)
            # Destinatio location
            if product.type == 'consu' and not (loc_dest_id and (location_dest_id.output_ok or location_dest_id.usage == 'customer')):
                # If we are not in Picking ticket and the dest. loc. is not output or customer, unset the dest.
                if loc_id and loc_id not in packing_ids:
                    result['value'].update(location_dest_id=False)

        return result

    def _create_chained_picking_move_values_hook(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking

        - allow to modify the data for chained move creation
        '''
        if context is None:
            context = {}
        move_data = kwargs['move_data']
        # set the line number from original stock move
        move = kwargs['move']
        move_data.update({'line_number': move.line_number})
        return move_data


    def _create_chained_picking_internal_request(self, cr, uid, context=None, *args, **kwargs):
        '''
        Overrided in delivery_mechanism to create an OUT instead of or in plus of the INT at reception
        '''
        pickid = kwargs['picking']
        picking_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        if not kwargs.get('return_goods'):
            wf_service.trg_validate(uid, 'stock.picking', pickid, 'button_confirm', cr)
            wf_service.trg_validate(uid, 'stock.picking', pickid, 'action_assign', cr)
            # Make the stock moves available
            picking_obj.action_assign(cr, uid, [pickid], assign_expired=True, context=context)
        picking_obj.log_picking(cr, uid, [pickid], context=context)
        return

    def create_chained_picking(self, cr, uid, moves, return_goods=None, context=None):
        res_obj = self.pool.get('res.company')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        new_moves = []
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        if return_goods:
            return []

        for picking, todo in list(self._chain_compute(cr, uid, moves, context=context).items()):
            ptype = todo[0][1][5] and todo[0][1][5] or location_obj.picking_type_get(cr, uid, todo[0][0].location_dest_id, todo[0][1][0])
            if picking:
                # name of new picking according to its type
                new_pick_name = seq_obj.get(cr, uid, 'stock.picking.' + ptype)
                pickid = self._create_chained_picking(cr, uid, new_pick_name, picking, ptype, todo, context=context)

                # Need to check name of old picking because it always considers picking as "OUT" when created from Sale Order
                old_ptype = location_obj.picking_type_get(cr, uid, picking.move_lines[0].location_id, picking.move_lines[0].location_dest_id)
                picking_vals = {}
                if old_ptype != picking.type and not picking.claim:
                    picking_vals['name'] = seq_obj.get(cr, uid, 'stock.picking.' + old_ptype)
                if ptype == 'internal':
                    picking_vals['associate_pick_name'] = new_pick_name  # save the INT name into this original IN
                if picking_vals:
                    picking_obj.write(cr, uid, [picking.id], picking_vals, context=context)
            else:
                pickid = False
            for move, (loc, dummy, delay, dummy, company_id, ptype) in todo:
                location_dest_id = self._get_location_for_internal_request(cr, uid, context=context, move=move)
                if not location_dest_id:
                    location_dest_id = loc.id
                move_data = {'location_id': move.location_dest_id.id,
                             'location_dest_id': location_dest_id,
                             'date_moved': time.strftime('%Y-%m-%d'),
                             'picking_id': pickid,
                             'state': 'waiting',
                             'company_id': company_id or res_obj._company_default_get(cr, uid, 'stock.company', context=context),
                             'move_history_ids': [],
                             'date': (datetime.strptime(move.date, '%Y-%m-%d %H:%M:%S') + relativedelta(days=delay or 0)).strftime('%Y-%m-%d'),
                             'move_history_ids2': [],
                             }
                move_data = self._create_chained_picking_move_values_hook(cr, uid, context=context, move_data=move_data, move=move)
                new_id = move_obj.copy(cr, uid, move.id, move_data)
                move_obj.write(cr, uid, [move.id], {
                    'move_dest_id': new_id,
                    'move_history_ids': [(4, new_id)]
                })
                # UF-2424: If it's an internal move, just remove the asset_id
                if ptype == 'internal' and move.product_id.subtype == 'asset':
                    move_obj.write(cr, uid, [new_id], {'asset_id': False})

                new_moves.append(self.browse(cr, uid, [new_id])[0])
            if pickid:
                self._create_chained_picking_internal_request(cr, uid, context=context, picking=pickid, return_goods=return_goods)
        if new_moves:
            new_moves += self.create_chained_picking(cr, uid, new_moves, context)
        return new_moves

    def prepare_action_confirm(self, cr, uid, ids, context=None):
        '''
        split in smaller methods to ease the reusing of the code in other parts
        '''
        moves = self.browse(cr, uid, ids, context=context)
        ctx = context.copy()
        ctx.update({'action_confirm': True})
        self.create_chained_picking(cr, uid, moves, context=ctx)

    def action_confirm(self, cr, uid, ids, context=None, vals=None):
        """ Confirms stock move.
        @return: List of ids.
        """
        if not context:
            context = {}
        if vals is None:
            vals = {}
        if isinstance(ids, int):
            ids = [ids]

        # check qty > 0 or raise
        self.check_product_quantity(cr, uid, ids, context=context)

        for move in self.browse(cr, uid, ids, fields_to_fetch=['picking_id', 'product_qty', 'confirmed_qty'], context=context):
            if context.get('picking_type') == 'incoming_shipment' and not move.picking_id.partner_id and \
                    not move.picking_id.ext_cu:
                raise osv.except_osv(_('Error'), _('You can not process an IN with neither Partner or Ext. C.U.'))
            if context.get('picking_type') == 'delivery_order' and not move.picking_id.partner_id:
                raise osv.except_osv(_('Error'), _('You can not process an OUT without a Partner'))
            l_vals = vals
            l_vals.update({'state': 'confirmed', 'already_confirmed': True})
            if move.picking_id.type == 'in' and not move.picking_id.purchase_id and move.product_qty and \
                    not move.confirmed_qty:
                l_vals.update({'confirmed_qty': move.product_qty})
            self.write(cr, uid, move.id, vals)
        self.prepare_action_confirm(cr, uid, ids, context=context)
        return []

    def action_assign(self, cr, uid, ids, lefo=False, assign_expired=False, context=None):
        """ Changes state to confirmed or waiting.
        @return: List of values
        """
        if context is None:
            context = {}

        todo = []
        for move in self.browse(cr, uid, ids, fields_to_fetch=['state', 'already_confirmed']):
            if not move.already_confirmed:
                self.action_confirm(cr, uid, [move.id])
            if move.state in ('confirmed', 'waiting'):
                todo.append(move.id)
        res = self.check_assign(cr, uid, todo, lefo=lefo, assign_expired=assign_expired)
        return res

    def force_assign_manual(self, cr, uid, ids, context=None):
        return self.force_assign(cr, uid, ids, context, manual=True)

    def force_assign(self, cr, uid, ids, context=None, manual=False):
        """ Changes the state to assigned.
        @return: True
        """

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        ir_data = self.pool.get('ir.model.data')
        product_tbd = ir_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        stock_loc_id = ir_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        log_loc_id = ir_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        med_loc_id = ir_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]

        ftf = ['product_id', 'from_wkf_line', 'picking_id', 'line_number', 'product_qty', 'qty_to_process', 'location_id']
        for move in self.browse(cr, uid, ids, fields_to_fetch=ftf, context=context):
            if move.product_id.id == product_tbd and move.from_wkf_line:
                ids.pop(ids.index(move.id))
            else:
                pick = move.picking_id or False
                self.infolog(cr, uid, 'Force availability run on stock move #%s (id:%s) of picking id:%s (%s)' % (
                    move.line_number, move.id, pick and pick.id or False, pick and pick.name or False,
                ))
                to_write = {'state': 'assigned'}
                # Set the source to LOG or MED depending on the product's Nomenclature
                if move.location_id.id == stock_loc_id and move.product_id.nomen_manda_0.name in ['LOG', 'MED']:
                    if move.product_id.nomen_manda_0.name == 'LOG':
                        to_write['location_id'] = log_loc_id
                    if move.product_id.nomen_manda_0.name == 'MED':
                        to_write['location_id'] = med_loc_id
                if not manual or not move.qty_to_process:
                    to_write['qty_to_process'] = move.product_qty
                self.write(cr, uid, [move.id], to_write)
        return True

    def cancel_assign(self, cr, uid, ids, context=None):
        """ Changes the state to confirmed.
        @return: True
        """
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        res = []
        fields_to_read = ['picking_id', 'product_id', 'product_uom', 'location_id',
                          'product_qty', 'product_uos_qty', 'location_dest_id', 'state',
                          'prodlot_id', 'asset_id', 'composition_list_id', 'line_number', 'in_out_updated', 'sale_line_id']

        qty_data = {}
        for move_data in self.read(cr, uid, ids, fields_to_read, context=context):
            if move_data['state'] != 'assigned':
                continue
            self.write(cr, uid, move_data['id'], {'qty_to_process': 0, 'state': 'confirmed', 'prodlot_id': False, 'expired_date': False})
            search_domain = [('state', '=', 'confirmed'), ('id', '!=', move_data['id'])]
            picking_id = move_data['picking_id'] and move_data['picking_id'][0] or False

            for f in fields_to_read:
                if f in ('product_qty', 'product_uos_qty'):
                    continue
                d = move_data[f]
                if isinstance(move_data[f], tuple):
                    d = move_data[f][0]
                search_domain.append((f, '=', d))

            move_ids = self.search(cr, uid, search_domain, context=context)
            if move_ids:
                move = self.read(cr, uid, move_ids[0], ['product_qty', 'product_uos_qty'], context=context)
                res.append(move['id'])
                if move_data['id'] not in qty_data:
                    qty_data[move['id']] = {
                        'product_qty': move['product_qty'] + move_data['product_qty'],
                        'product_uos_qty': move['product_uos_qty'] + move_data['product_uos_qty'],
                    }
                else:
                    qty_data[move['id']] = {
                        'product_qty': move['product_qty'] + qty_data[move_data['id']]['product_qty'],
                        'product_uos_qty': move['product_uos_qty'] + qty_data[move_data['id']]['product_uos_qty'],
                    }

                self.write(cr, uid, [move['id']], qty_data[move['id']].copy(), context=context)

                pol_ids = self.pool.get('purchase.order.line').search(cr, uid,
                                                                      [('move_dest_id', '=', move_data['id'])],
                                                                      order='NO_ORDER', context=context)
                if pol_ids:
                    self.pool.get('purchase.order.line').write(cr, uid, pol_ids, {'move_dest_id': move['id']}, context=context)

                move_dest_ids = self.search(cr, uid, [('move_dest_id', '=',
                                                       move_data['id'])], order='NO_ORDER', context=context)
                if move_dest_ids:
                    self.write(cr, uid, move_dest_ids, {'move_dest_id': move['id']}, context=context)

                backmove_ids = self.search(cr, uid, [('backmove_id', '=',
                                                      move_data['id'])], order='NO_ORDER', context=context)
                if backmove_ids:
                    self.write(cr, uid, backmove_ids, {'backmove_id': move['id']}, context=context)

                pack_backmove_ids = self.search(cr, uid,
                                                [('backmove_packing_id', '=', move_data['id'])],
                                                order='NO_ORDER', context=context)
                if pack_backmove_ids:
                    self.write(cr, uid, pack_backmove_ids, {'backmove_packing_id': move['id']}, context=context)

                #self.write(cr, uid, [move_data['id']], {'state': 'draft'}, context=context)
                self.unlink(cr, uid, move_data['id'], context=context, force=True)

            self.infolog(cr, uid, 'Cancel availability run on stock move #%s (id:%s) of picking id:%s (%s)' % (
                move_data['line_number'],
                move_data['id'],
                picking_id,
                move_data['picking_id'] and move_data['picking_id'][1] or '',
            ))

        return res

    #
    # Duplicate stock.move
    #
    def check_assign(self, cr, uid, ids, lefo=False, assign_expired=False, context=None):
        """ Checks the product type and accordingly writes the state.
        @return: No. of moves done
        """
        done = []
        move_to_assign = []
        count = 0
        pickings = {}
        if context is None:
            context = {}

        for move in self.browse(cr, uid, ids, context=context):
            if move.location_id.usage == 'supplier' or (move.location_id.usage == 'customer' and move.location_id.location_category == 'consumption_unit'):
                if move.state in ('confirmed', 'waiting'):
                    if move.location_id.id == move.location_dest_id.id:
                        done.append(move.id)
                    else:
                        move_to_assign.append(move.id)
                pickings.setdefault(move.picking_id.id, 0)
                pickings[move.picking_id.id] += 1
                continue
            if move.state in ('confirmed', 'waiting'):
                bn_needed =  move.product_id.perishable
                # Important: we must pass lock=True to _product_reserve() to avoid race conditions and double reservations
                prod_lot = False
                if bn_needed and move.prodlot_id:
                    prod_lot = move.prodlot_id.id
                res = self.pool.get('stock.location')._product_reserve_lot(cr, uid, [move.location_id.id], move.product_id.id,  move.product_qty, move.product_uom.id, lock=True, prod_lot=prod_lot, lefo=lefo, assign_expired=assign_expired)
                if res:
                    if move.location_id.id == move.location_dest_id.id:
                        state = 'done'
                        done.append(move.id)
                    else:
                        state = 'assigned'
                        move_to_assign.append(move.id)

                    pickings.setdefault(move.picking_id.id, 0)
                    pickings[move.picking_id.id] += 1
                    r = res.pop(0)
                    prodlot_id = None
                    expired_date = None
                    if bn_needed:
                        prodlot_id = r[3] or None
                        expired_date = r[2] or None
                    cr.execute("update stock_move set location_id=%s, product_qty=%s, product_uos_qty=%s, prodlot_id=%s, expired_date=%s, state=%s, qty_to_process=%s where id=%s", (r[1], r[0], r[0] * move.product_id.uos_coeff, prodlot_id, expired_date, state, r[0], move.id))
                    while res:
                        r = res.pop(0)
                        prodlot_id = False
                        expired_date = False
                        if bn_needed and r[1]:
                            prodlot_id = r[3]
                            expired_date = r[2]
                        if r[1]:
                            if r[1] == move.location_dest_id.id:
                                state = 'done'
                                qty_to_process = r[0]
                            else:
                                state = 'assigned'
                                qty_to_process = r[0]
                        else:
                            state = 'confirmed'
                            qty_to_process = 0

                        self.copy(cr, uid, move.id, {'qty_to_process': qty_to_process, 'line_number': move.line_number, 'product_qty': r[0], 'product_uos_qty': r[0] * move.product_id.uos_coeff, 'location_id': r[1] or move.location_id.id, 'prodlot_id': prodlot_id, 'expired_date': expired_date, 'state': state})

        if done:
            cr.execute('update stock_move set qty_to_process=product_qty where id in %s', (tuple(done),))
            self.write(cr, uid, done, {'state': 'done'})
        if move_to_assign:
            cr.execute('update stock_move set qty_to_process=product_qty where id in %s', (tuple(move_to_assign),))
            self.write(cr, uid, move_to_assign, {'state': 'assigned'})

        count = 0
        for pick_id in pickings:
            count += pickings[pick_id]
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return count

    def setlast_tracking(self, cr, uid, ids, context=None):
        tracking_obj = self.pool.get('stock.tracking')
        picking = self.browse(cr, uid, ids, context=context)[0].picking_id
        if picking:
            last_track = [line.tracking_id.id for line in picking.move_lines if line.tracking_id]
            if not last_track:
                last_track = tracking_obj.create(cr, uid, {}, context=context)
            else:
                last_track.sort()
                last_track = last_track[-1]
            self.write(cr, uid, ids, {'tracking_id': last_track})
        return True

    def _hook_move_cancel_state(self, cr, uid, *args, **kwargs):
        '''
        Change the state of the chained move
        '''
        if kwargs.get('context'):
            kwargs['context'].update({'call_unlink': True})
        return {'state': 'cancel'}, kwargs.get('context', {})

    #
    # Cancel move => cancel others move and pickings
    #
    def action_cancel(self, cr, uid, ids, context=None):
        '''
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
        sol_ids_to_check = {}
        pickings = {}

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
                if move.qty_processed and not move.product_qty and move.state == 'assigned':
                    continue
                if move.qty_processed and move.state not in ('done', 'cancel'):
                    # remaining qty cancelled in draft pick, sotck.move will be in Cancel state, create a assinged stock.move to display the qty already processed
                    ctx_copy = context.copy()
                    ctx_copy['keepLineNumber'] = True
                    self.copy(cr, uid, move.id, {'product_uos_qty': 0, 'product_qty': 0, 'state': 'assigned', 'qty_processed': move.qty_processed, 'qty_to_process': move.qty_processed} , context=ctx_copy)

                pick_obj._create_sync_message_for_field_order(cr, uid, move.picking_id, context=context)

            if pick_type == 'in' and move.purchase_line_id:
                # cancel the linked PO line partially or fully:
                resource = move.has_to_be_resourced or move.picking_id.has_to_be_resourced or context.get('do_resource', False)
                pol_info = self.pool.get('purchase.order.line').read(cr, uid, move.purchase_line_id.id, ['product_qty', 'in_qty_remaining', 'max_qty_cancellable']) # because value in move.purchase_line_id.product_qty has changed since
                pol_product_qty = pol_info['product_qty']
                partially_cancelled = False
                qty_to_cancel = move.product_qty
                if move.product_uom.id != move.purchase_line_id.product_uom.id:
                    qty_to_cancel = self.pool.get('product.uom')._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.purchase_line_id.product_uom.id)
                if move.purchase_line_id.order_id.order_type != 'direct':
                    # do not cancel extra IN qty on po line
                    qty_to_cancel = qty_to_cancel - pol_info['max_qty_cancellable']
                    if  qty_to_cancel <= 0.001:
                        # nothing to do: extra qty cancelled
                        continue
                if pol_product_qty - qty_to_cancel > 0.001:
                    new_line = self.pool.get('purchase.order.line').cancel_partial_qty(cr, uid, [move.purchase_line_id.id], cancel_qty=qty_to_cancel, resource=resource, context=context)
                    self.write(cr, uid, [move.id], {'purchase_line_id': new_line}, context=context)
                    partially_cancelled = True
                    if move.purchase_line_id.order_id.order_type == 'direct' and abs(pol_info['in_qty_remaining']) < 0.001:
                        wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.id, 'done', cr)
                else:
                    if move.product_qty != 0.00:
                        pickings[move.picking_id.id] = True
                        self.write(cr, uid, move.id, {'state': 'cancel'}, context=context)
                    signal = 'cancel_r' if resource else 'cancel'
                    wf_service.trg_validate(uid, 'purchase.order.line', move.purchase_line_id.id, signal, cr)
                if move.purchase_line_id.order_id.order_type == 'direct':
                    continue
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
                self.decrement_sys_init(cr, uid, move.product_qty, pol_id=move.purchase_line_id and move.purchase_line_id.id or False, context=context)

            elif move.sale_line_id and (pick_type == 'internal' or (pick_type == 'out' and subtype_ok)):
                sol_ids_to_check[move.sale_line_id.id] = True
                resource = move.has_to_be_resourced or move.picking_id.has_to_be_resourced or False
                diff_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.sale_line_id.product_uom.id)
                if diff_qty:
                    if move.id not in context.get('not_resource_move', []):
                        has_linked_pol = self.pool.get('purchase.order.line').search_exist(cr, uid, [('linked_sol_id', '=', move.sale_line_id.id)], context=context)
                        if has_linked_pol:
                            context['sol_done_instead_of_cancel'] = True
                        sol_obj.update_or_cancel_line(cr, uid, move.sale_line_id.id, diff_qty, resource=resource, cancel_move=move.id, context=context)
                        if has_linked_pol:
                            context.pop('sol_done_instead_of_cancel')

            # Remove all KCL references from the OUT process wizard lines linked to the move
            if move.product_id.subtype == 'kit':
                out_m_proc_obj = self.pool.get('outgoing.delivery.move.processor')
                out_m_proc_ids = out_m_proc_obj.search(cr, uid, [('move_id', '=', move.id), ('composition_list_id', '!=', False)], context=context)
                if out_m_proc_ids:
                    out_m_proc_obj.write(cr, uid, out_m_proc_ids, {'composition_list_id': False}, context=context)

        self.action_done(cr, uid, move_to_done, context=context)

        # Search only non unlink move
        ids = self.search(cr, uid, [('id', 'in', ids)])

        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('confirmed', 'waiting', 'assigned', 'draft'):
                if move.picking_id:
                    pickings[move.picking_id.id] = True
            if move.move_dest_id and move.move_dest_id.state == 'waiting':
                state, c = self._hook_move_cancel_state(cr, uid, context=context)
                context.update(c)
                self.write(cr, uid, [move.move_dest_id.id], state)
                if context.get('call_unlink',False) and move.move_dest_id.picking_id:
                    wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)

        self.write(cr, uid, list(set(ids) - set(move_to_done)), {'state': 'cancel', 'move_dest_id': False})

        if not context.get('call_unlink',False):
            picking_to_write = []
            for pick in pick_obj.read(cr, uid, list(pickings.keys()), ['move_lines']):
                # if all movement are in cancel state:
                if not self.search_exist(cr, uid, [('id', 'in', pick['move_lines']), ('state', '!=', 'cancel'),]):
                    picking_to_write.append(pick['id'])
            if picking_to_write:
                pick_obj.write(cr, uid, picking_to_write, {'state': 'cancel'})

        for id in ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)

        # cancel remaining qty on OUT must close the IR/FO line
        for sol_id in  list(sol_ids_to_check.keys()):
            wf_service.trg_write(uid, 'sale.order.line', sol_id, cr)

        for ptc in pick_obj.browse(cr, uid, list(pick_to_check), context=context):
            if ptc.subtype == 'picking' and ptc.state == 'draft' and not pick_obj.has_picking_ticket_in_progress(cr, uid, [ptc.id], context=context)[ptc.id] and all(m.state == 'cancel' or m.product_qty == 0.00 for m in ptc.move_lines):
                moves_to_done = self.search(cr, uid, [('picking_id', '=', ptc.id), ('product_qty', '=', 0.00), ('state', 'not in', ['done', 'cancel'])], context=context)
                if moves_to_done:
                    self.action_done(cr, uid, moves_to_done, context=context)
                ptc.action_done(context=context)


        return True

    def decrement_sys_init(self, cr, uid, qty, pol_id, context=None):
        if not pol_id:
            return False

        if qty == 'all':
            query = 'LEAST(product_qty, %s)'
            qty = 0
        else:
            query = 'GREATEST(0, product_qty - %s)'
        cr.execute('''
            update stock_move as m set product_qty = ''' +query+ '''
            from stock_picking p where
                m.purchase_line_id=%s and
                p.id = m.picking_id and
                p.type = 'internal' and
                p.subtype = 'sysint' and
                m.state != 'cancel'
            returning m.id, m.product_qty
        ''', (qty, pol_id)) # not_a_user_entry
        for x in cr.fetchall():
            if not x[1]:
                self.action_cancel(cr, uid, x[0], context=context)
        return True

    def _get_accounting_data_for_valuation(self, cr, uid, move, context=None):
        """
        Return the accounts and journal to use to post Journal Entries for the real-time
        valuation of the move.

        :param context: context dictionary that can explicitly mention the company to consider via the 'force_company' key
        :raise: osv.except_osv() is any mandatory account or journal is not defined.
        """
        product_obj=self.pool.get('product.product')
        accounts = product_obj.get_product_accounts(cr, uid, move.product_id.id, context)
        if move.location_id.valuation_out_account_id:
            acc_src = move.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts['stock_account_input']

        if move.location_dest_id.valuation_in_account_id:
            acc_dest = move.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts['stock_account_output']

        acc_variation = accounts.get('property_stock_variation', False)
        journal_id = accounts['stock_journal']

        if acc_dest == acc_variation:
            raise osv.except_osv(_('Error!'),  _('Can not create Journal Entry, Output Account defined on this product and Variant account on category of this product are same.'))

        if acc_src == acc_variation:
            raise osv.except_osv(_('Error!'),  _('Can not create Journal Entry, Input Account defined on this product and Variant account on category of this product are same.'))

        if not acc_src:
            raise osv.except_osv(_('Error!'),  _('There is no stock input account defined for this product or its category: "%s" (id: %d)') % \
                                 (move.product_id.name, move.product_id.id,))
        if not acc_dest:
            raise osv.except_osv(_('Error!'),  _('There is no stock output account defined for this product or its category: "%s" (id: %d)') % \
                                 (move.product_id.name, move.product_id.id,))
        if not journal_id:
            raise osv.except_osv(_('Error!'), _('There is no journal defined on the product category: "%s" (id: %d)') % \
                                 (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        if not acc_variation:
            raise osv.except_osv(_('Error!'), _('There is no inventory variation account defined on the product category: "%s" (id: %d)') % \
                                 (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        return journal_id, acc_src, acc_dest, acc_variation

    def _hook_action_done_update_out_move_check(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        choose if the corresponding out stock move must be updated
        '''
        move = kwargs['move']
        result = move.move_dest_id.id and (move.state != 'done')
        return result

    def action_done(self, cr, uid, ids, return_goods=None, context=None):
        """ Makes the move done and if all moves are done, it will finish the picking.
        @return:
        """
        picking_ids = []
        move_ids = []
        wf_service = netsvc.LocalService("workflow")
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        todo = self.search(cr, uid,
                           [('id', 'in', ids),
                            ('state', '=', 'draft')],
                           order='NO_ORDER', context=context)
        if todo:
            self.action_confirm(cr, uid, todo, context=context)
            todo = []

        move_ids = self.search(cr, uid,
                               [('id', 'in', ids),
                                ('state', 'not in', ('done', 'cancel'))],
                               order='NO_ORDER', context=context)

        for move in self.browse(cr, uid, move_ids, context=context):
            vals = {}
            if move.picking_id:
                picking_ids.append(move.picking_id.id)
                if move.type == 'out':
                    vals.update({'reason_type_id': move.picking_id.reason_type_id.id})
                    # Close the linked KCL when the Shipment processes the PACK
                    if move.picking_subtype == 'packing' and move.subtype == 'kit' and move.composition_list_id:
                        self.pool.get('composition.kit').close_kit(cr, uid, [move.composition_list_id.id], self._name, context=context)
            if self._hook_action_done_update_out_move_check(cr, uid, ids, context=context, move=move,):
                vals.update({'move_history_ids': [(4, move.move_dest_id.id)]})
                #cr.execute('insert into stock_move_history_ids (parent_id,child_id) values (%s,%s)', (move.id, move.move_dest_id.id))
                if move.move_dest_id.state in ('waiting', 'confirmed'):
                    if move.prodlot_id.id and move.product_id.id == move.move_dest_id.product_id.id:
                        self.write(cr, uid, [move.move_dest_id.id], {'prodlot_id':move.prodlot_id.id})
                    self.force_assign(cr, uid, [move.move_dest_id.id], context=context)
                    if move.move_dest_id.picking_id:
                        wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                    if move.move_dest_id.auto_validate:
                        self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            if vals:
                self.write(cr, uid, [move.id], vals)
            if move.state not in ('confirmed', 'done', 'assigned'):
                todo.append(move.id)

        if todo:
            self.action_confirm(cr, uid, todo, context=context)

        if move_ids:
            self.write(cr, uid, move_ids, {'state': 'done', 'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
            wf_service.trg_trigger(uid, 'stock.move', move_ids, cr)

        pick_id_to_write = set()
        for pick in self.pool.get('stock.picking').read(cr, uid, picking_ids,
                                                        ['state', 'type'], context=context):
            wf_service.trg_write(uid, 'stock.picking', pick['id'], cr)
            ##### UF-2378 For some reason, the RW code from OpenERP kept the IN always in Available, even its lines are closed!!!
            if pick['state'] != 'done' and pick['type'] == 'in':
                pick_id_to_write.add(pick['id'])
        if pick_id_to_write:
            self.pool.get('stock.picking').write(cr, uid, list(pick_id_to_write),
                                                 {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

        moves = self.browse(cr, uid, move_ids, context=context)
        self.create_chained_picking(cr, uid, moves, return_goods, context)

        return True


    def unlink(self, cr, uid, ids, context=None, force=False):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        tools_obj = self.pool.get('sequence.tools')
        if not context.get('skipResequencing', False):
            # re sequencing only happen if purchase order is draft (behavior 1)
            draft_not_wkf_ids = self.allow_resequencing(cr, uid, ids, context=context)
            tools_obj.reorder_sequence_number_from_unlink(
                cr,
                uid,
                draft_not_wkf_ids,
                'stock.picking',
                'move_sequence_id',
                'stock.move',
                'picking_id',
                'line_number',
                context=context,
            )

        ctx = context.copy()
        for move in self.read(cr, uid, ids, ['state'], context=context):
            if move['state'] != 'draft' and not ctx.get('call_unlink',False)\
                    and not ctx.get('sync_update_execution')\
                    and not force:
                raise osv.except_osv(_('UserError'),
                                     _('You can only delete draft moves.'))
        return super(stock_move, self).unlink(cr, uid, ids, context=ctx)

    def allow_resequencing(self, cr, uid, ids, context=None):
        '''
        define if a resequencing has to be performed or not

        return the list of ids for which resequencing will can be performed

        linked to Picking + Picking draft + not linked to Po/Fo
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')

        resequencing_ids = [x.id for x in self.browse(cr, uid, ids, context=context)
                            if x.picking_id and pick_obj.allow_resequencing(cr, uid, x.picking_id, context=context)]
        return resequencing_ids

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
        Get the requestor_location_id in case of IR to update the location_dest_id of each move
        '''
        location_dest_id = False
        move = kwargs['move']
        linked_sol = move.purchase_line_id.linked_sol_id or False
        if linked_sol and linked_sol.order_id.procurement_request and linked_sol.order_id.location_requestor_id.usage != 'customer':
            location_dest_id = linked_sol.order_id.location_requestor_id.id

        return location_dest_id

    def _create_lot(self, cr, uid, ids, product_id, prefix=False):
        """ Creates production lot
        @return: Production lot id
        """
        prodlot_obj = self.pool.get('stock.production.lot')
        prodlot_id = prodlot_obj.create(cr, uid, {'prefix': prefix, 'product_id': product_id})
        return prodlot_id


    def open_split_wizard(self, cr, uid, ids, context=None):
        """
        Open the split line wizard: the user can select the quantity for the new move
        """
        wiz_obj = self.pool.get('split.move.processor')

        if isinstance(ids, int):
            ids = [ids]

        line = self.browse(cr, uid, ids[0], fields_to_fetch=['product_uom', 'product_qty'], context=context)
        split_wiz_id = wiz_obj.create(cr, uid, {
            'processor_line_id': ids[0],
            'processor_type': self._name,
            'uom_id': line.product_uom.id,
            'quantity': line.product_qty,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'nodestroy': True,
            'target': 'new',
            'res_id': split_wiz_id,
            'context': context,
        }


    def split(self, cr, uid, id, quantity, uom_id, context=None):
        if context is None:
            context = {}
        keepLineNumber = context.get('keepLineNumber')
        context['keepLineNumber'] = True
        init_data = self.browse(cr, uid, id, fields_to_fetch=['product_qty', 'state', 'qty_to_process', 'pt_created'], context=context)
        if quantity <= 0:
            raise osv.except_osv(_('Warning'), _('Selected quantity must be greater than 0 !'))
        if quantity >= init_data.product_qty:
            raise osv.except_osv(_('Warning'), _('Qty to split %s is more or equal to original qty %s') % (quantity, init_data.product_qty))

        copy_data = {'product_qty': quantity, 'product_uos_qty': quantity, 'state': init_data.state, 'qty_to_process': 0, 'pt_created': init_data.pt_created}
        new_id = self.copy(cr, uid, id, copy_data, context=context)
        new_qty = init_data.product_qty - quantity
        new_data = {'product_qty': new_qty, 'product_uos_qty': new_qty}
        if init_data.qty_to_process > new_qty:
            new_data['qty_to_process'] = new_qty

        self.write(cr, uid, id, new_data, context=context)
        context['keepLineNumber'] = keepLineNumber
        return new_id

    def get_mirror_move(self, cr, uid, ids, data_back, context=None):
        '''
        return a dictionary with IN for OUT and OUT for IN, if exists, False otherwise

        only one mirror object should exist for each object (to check)
        return objects which are not done

        same sale_line_id/purchase_line_id - same product - same quantity

        IN: move -> po line -> procurement -> so line -> move
        OUT: move -> so line -> procurement -> po line -> move

        I dont use move.move_dest_id because of back orders both on OUT and IN sides
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # objects
        res = {}
        for obj in self.browse(cr, uid, ids, context=context,
                               fields_to_fetch=['picking_id', 'purchase_line_id', 'id', 'sale_line_id']):
            res[obj.id] = {'move_id': False, 'picking_id': False, 'picking_version': 0, 'quantity': 0, 'moves': []}
            if obj.picking_id and obj.picking_id.type == 'in':
                move_ids = False
                # we are looking for corresponding OUT move from sale order line
                if obj.purchase_line_id and obj.purchase_line_id.linked_sol_id:
                    # find the corresponding OUT move
                    move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']),
                                                     ('state', 'in', ('assigned', 'confirmed')),
                                                     ('sale_line_id', '=', obj.purchase_line_id.linked_sol_id.id),
                                                     ('in_out_updated', '=', False),
                                                     ('picking_id.type', '=', 'out'),
                                                     ('processed_stock_move', '=', False),
                                                     ], order="state desc", context=context)
                elif obj.sale_line_id and ('replacement' in obj.picking_id.name or 'missing' in obj.picking_id.name):
                    # find the corresponding OUT move if SO line id
                    move_ids = self.search(cr, uid, [('product_id', '=', data_back['product_id']),
                                                     ('state', 'in', ('assigned', 'confirmed')),
                                                     ('sale_line_id', '=', obj.sale_line_id.id),
                                                     ('in_out_updated', '=', False),
                                                     ('picking_id.type', '=', 'out'),
                                                     ('processed_stock_move', '=', False),
                                                     ], order="state desc", context=context)

                if move_ids:
                    # list of matching out moves
                    integrity_check = []
                    for move in self.browse(cr, uid, move_ids, context=context):
                        pick = move.picking_id
                        cond1 = move.picking_id.subtype == 'standard'
                        cond2 = move.product_qty != 0.00 and pick.subtype == 'picking' and (not pick.backorder_id or pick.backorder_id.subtype == 'standard') and pick.state == 'draft'
                        # move from draft picking or standard picking
                        if cond2 or cond1:
                            integrity_check.append(move)
                    # return the first one matching
                    if integrity_check:
                        if all([not move.processed_stock_move for move in integrity_check]):
                            # the out stock moves (draft picking or std out) have not yet been processed, we can therefore update them
                            res[obj.id].update({
                                'move_id': integrity_check[0].id,
                                'moves': integrity_check,
                                'picking_id': integrity_check[0].picking_id.id,
                                'picking_version': integrity_check[0].picking_id.update_version_from_in_stock_picking,
                                'quantity': integrity_check[0].product_qty,
                            })
                        else:
                            # the corresponding OUT move have been processed completely or partially,, we do not update the OUT
                            msg_log = _('The Stock Move %s from %s has already been processed and is '
                                        'therefore not updated.') % (integrity_check[0].name, integrity_check[0].picking_id.name)
                            self.log(cr, uid, integrity_check[0].id, msg_log)

            else:
                # we are looking for corresponding IN from on_order purchase order
                assert False, 'This method is not implemented for OUT or Internal moves'

        return res

    def create_data_back(self, move):
        '''
        build data_back dictionary
        '''
        res = {'id': move.id,
               'name': move.product_id.partner_ref,
               'product_id': move.product_id.id,
               'product_uom': move.product_uom.id,
               'product_qty': move.product_qty,
               'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
               'asset_id': move.asset_id and move.asset_id.id or False,
               'expired_date': move.expired_date or False,
               'location_dest_id': move.location_dest_id.id,
               'move_cross_docking_ok': move.move_cross_docking_ok,
               }
        return res

    def button_cross_docking(self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to cross docking
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Check the allocation setup
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if setup.allocation_setup == 'unallocated':
            raise osv.except_osv(_('Error'), _("""You cannot made moves from/to Cross-docking locations
            when the Allocated stocks configuration is set to \'Unallocated\'."""))
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ['done', 'cancel']:
                todo.append(move.id)
                self.infolog(cr, uid, "The source location of the stock move id:%s has been changed to cross-docking location" % (move.id))
        ret = True
        if todo:
            ret = self.write(cr, uid, todo, {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)

            # we cancel availability
            new_todo = self.cancel_assign(cr, uid, todo, context=context)
            if new_todo:
                todo = new_todo
            # we rechech availability
            self.action_assign(cr, uid, todo, context=context)
        return ret

    def button_stock(self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to stock
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ['done', 'cancel']:
                '''
                Specific rules for non-stockable products:
                   * if the move is an outgoing delivery, picked them from cross-docking
                   * else picked them from the non-stockable location
                '''
                if move.product_id.type in ('consu', 'service_recep'):
                    if move.picking_id.type == 'out':
                        id_loc_s = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
                    elif move.product_id.type == 'consu':
                        id_loc_s = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
                    else:
                        id_loc_s = self.pool.get('stock.location').get_service_location(cr, uid)
                    self.write(cr, uid, move.id, {'location_id': id_loc_s, 'move_cross_docking_ok': False}, context=context)
                else:
                    self.write(cr, uid, move.id, {'location_id': move.picking_id.warehouse_id.lot_stock_id.id,
                                                  'move_cross_docking_ok': False}, context=context)
                todo.append(move.id)
                self.infolog(cr, uid, "The source location of the stock move id:%s has been changed to stock location" % (move.id))
            # below we cancel availability to recheck it

        if todo:
            # we cancel availability
            new_todo = self.cancel_assign(cr, uid, todo, context=context)
            if new_todo:
                todo = new_todo
            # we research availability
            self.action_assign(cr, uid, todo)
        return True

# KIT CREATION
    def assign_to_kit(self, cr, uid, ids, context=None):
        '''
        open the assign to kit wizard
        '''
        if context is None:
            context = {}
        # data
        name = _("Assign to Kit")
        model = 'assign.to.kit'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context))
        return res

    def kol_prodlot_change(self, cr, uid, ids, prodlot_id, context=None):
        '''
        Set a new attribute on stock move if the prodolt is change manually in the Kit order creation
        '''
        if prodlot_id:
            return {'value': {'kol_lot_manual': True}}

        return {'value': {'kol_lot_manual': False}}

    def automatic_assignment(self, cr, uid, ids, context=None):
        '''
        automatic assignment of products to generated kits

        + a_sum = compute sum of assigned qty
        + left = compute available qty not assigned (available - a_sum)
        + for each line we update assigned qty if needed
          + assigned < required
            + needed = required - assigned
            + needed <= left:
              + assigned = assigned + needed
              + left = left - needed
            + needed > left:
              + assigned = assigned + left
              + left = 0.0
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # create corresponding wizard object (containing processing logic)
        res = self.assign_to_kit(cr, uid, ids, context=context)
        # objects
        wiz_obj = self.pool.get(res['res_model'])
        # perform auto assignment
        wiz_obj.automatic_assignment(cr, uid, [res['res_id']], context=res['context'])
        # process the wizard
        return wiz_obj.do_assign_to_kit(cr, uid, [res['res_id']], context=res['context'])

    def validate_assign(self, cr, uid, ids, context=None):
        '''
        set the state to done, so the move can be assigned to a kit
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        kit_creation_id = False
        for move in self.browse(cr, uid, ids, context=context):
            kit_creation_id = move.kit_creation_id_stock_move.id
            if move.state == 'assigned':
                if move.product_id.perishable:
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
                    av_qty = self.pool.get('stock.production.lot').read(cr, uid, move.prodlot_id.id, ['stock_available'], context={'location_id': move.location_id.id})['stock_available']
                    if qty > av_qty:
                        raise osv.except_osv(_('Warning !'), _('Product %s, BN: %s not enough stock to process quantity %s %s (stock level: %s)') % ( move.product_id.default_code, move.prodlot_id.name, qty, move.product_id.uom_id.name, av_qty))

                self.write(cr, uid, [move.id], {'state': 'done'}, context=context)

            # we assign automatically
            self.automatic_assignment(cr, uid, [move.id], context=context)

        # refresh the vue so the completed flag is updated and Confirm Kitting button possibly appears
        data_obj = self.pool.get('ir.model.data')
        view_id = False
        try:
            view_id = data_obj.get_object_reference(cr, uid, 'kit', 'view_kit_creation_form')
        except:
            pass
        view_id = view_id and view_id[1] or False
        return {'view_mode': 'form,tree',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'kit.creation',
                'res_id': kit_creation_id,
                'type': 'ir.actions.act_window',
                'target': 'crush',
                }

    def split_stock_move(self, cr, uid, ids, context=None):
        '''
        open the wizard to split stock move
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}

        wiz_obj = self.pool.get('wizard')
        # data
        name = _("Split move")
        model = 'split.move'
        step = 'create'
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)

# sepcfici rules
    def onchange_uom(self, cr, uid, ids, product_uom, product_qty):
        '''
        Check the rounding of the qty according to the UoM
        '''
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, product_qty, ['product_qty', 'product_uos_qty'])

    def is_out_move_linked_to_dpo(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        move = self.browse(cr, uid, ids[0], context=context)
        if move.sale_line_id:
            pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', move.sale_line_id.id)], context=context)
            for pol in self.pool.get('purchase.order.line').browse(cr, uid, pol_ids, context=context):
                if pol.order_id.order_type == 'direct':
                    return True

        return False

# reason types
    def location_src_change(self, cr, uid, ids, location_id, context=None):
        '''
        Tries to define a reason type for the move according to the source location
        '''
        vals = {}

        if location_id:
            loc_id = self.pool.get('stock.location').browse(cr, uid, location_id, context=context)
            if loc_id.usage == 'inventory':
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

        return {'value': vals}

    def location_dest_change(self, cr, uid, ids, location_dest_id, picking_id, product_id=False, context=None):
        '''
        Tries to define a reason type for the move according to the destination location
        '''
        data_obj = self.pool.get('ir.model.data')
        vals = {}

        if location_dest_id:
            dest_id = self.pool.get('stock.location').browse(cr, uid, location_dest_id, context=context)
            if dest_id.usage == 'inventory':
                vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            elif dest_id.scrap_location:
                vals['reason_type_id'] = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
            elif picking_id:  # Header RT
                vals['reason_type_id'] = self.pool.get('stock.picking').read(cr, uid, picking_id, ['reason_type_id'],
                                                                             context=context)['reason_type_id'][0]

            if product_id:
                # Test the compatibility of the product with the location
                vals, test = self.pool.get('product.product')._on_change_restriction_error(cr, uid, product_id, field_name='location_dest_id', values={'value': vals}, vals={'location_id': location_dest_id})
                if test:
                    return vals

        return {'value': vals}

    def update_linked_documents(self, cr, uid, ids, new_id, context=None):
        '''
        Update the linked documents of a stock move to another one
        '''
        context = context or {}
        ids = isinstance(ids, int) and [ids] or ids

        for move_id in ids:
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


    def change_from_to_pack(self, cr, uid, from_p, to_p, context=None):
        return {
            'value': {'integrity_error': 'empty'}
        }

    def open_in_form(self, cr, uid, ids, context=None):
        move = self.browse(cr, uid, ids[0], fields_to_fetch=['picking_id', 'linked_incoming_move'], context=context)

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'stock.action_picking_tree4', ['form', 'tree'], new_tab=True, context=context)
        res['keep_open'] = True
        res['res_id'] = move.linked_incoming_move and move.linked_incoming_move.picking_id.id or move.picking_id.id
        return res

stock_move()

