# -*- coding: utf-8 -*-

from datetime import datetime
import time

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp
from mx import DateTime
from dateutil.relativedelta import relativedelta
from lxml import etree

class stock_production_lot(osv.osv):
    _name = 'stock.production.lot'
    _description = 'Production lot'

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if context is None:
            context = {}

        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref', 'life_date'], context)
        res = []
        if context.get('with_expiry'):
            user_obj = self.pool.get('res.users')
            lang_obj = self.pool.get('res.lang')
            user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
            lang_id = lang_obj.search(cr, uid, [('code','=',user_lang)])
            date_format = lang_id and lang_obj.read(cr, uid, lang_id[0], ['date_format'], context=context)['date_format'] or '%m/%d/%Y'

        for record in reads:
            if context.get('with_expiry') and record['life_date']:
                name = '%s - %s'%(record['name'], DateTime.strptime(record['life_date'],'%Y-%m-%d').strftime(date_format).decode('utf-8'))
            else:
                name = record['name']
            res.append((record['id'], name))
        return res


    def _get_stock(self, cr, uid, ids, field_name, arg, context=None):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        self._parse_context_location_id(cr, uid, context=context)
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')],
                                                               order='NO_ORDER', context=context)
        else:
            locations = context['location_id'] or []

        if isinstance(locations, (int, long)):
            locations = [locations]

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}.fromkeys(ids, 0.0)
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots
                where
                    location_id IN %s and prodlot_id IN %s group by prodlot_id''',(tuple(locations),tuple(ids),))
            res.update(dict(cr.fetchall()))

        return res

    def _stock_search(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of products
        @return: Ids of locations
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid,
                                                               [('usage', '=', 'internal')], order='NO_ORDER', context=context)
        else:
            locations = context['location_id'] or []

        if isinstance(locations, (int, long)):
            locations = [locations]

        ids = [('id', 'in', [])]
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots
                where
                    location_id IN %s group by prodlot_id
                having  sum(qty) '''+ str(args[0][1]) + str(args[0][2]),(tuple(locations),))  # not_a_user_entry
            res = cr.fetchall()
            ids = [('id', 'in', map(lambda x: x[0], res))]
        return ids

    def remove_flag(self, flag, _list):
        '''
        if we do not remove the flag, we fall into an infinite loop
        '''
        args2 = []
        for arg in _list:
            if arg[0] != flag:
                args2.append(arg)
        return args2

    def search_check_type(self, cr, uid, obj, name, args, context=None):
        '''
        modify the query to take the type of prodlot into account according to product's attributes
        'Batch Number mandatory' and 'Expiry Date Mandatory'

        if batch management: display only 'standard' lot
        if expiry and not batch management: display only 'internal' lot
        else: display normally
        '''
        product_obj = self.pool.get('product.product')
        product_id = context.get('product_id', False)

        # remove flag avoid infinite loop
        args = self.remove_flag('check_type', args)

        if not product_id:
            return args

        # check the product
        product = product_obj.browse(cr, uid, product_id, context=context)

        if product.batch_management:
            # standard lots
            args.append(('type', '=', 'standard'))
        elif product.perishable:
            # internal lots
            args.append(('type', '=', 'internal'))

        return args

    def _get_false(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids,(long, int)):
            ids = [ids]

        result = {}
        for id in ids:
            result[id] = False
        return result

    def _stock_search_virtual(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of products
        @return: Ids of locations
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
        else:
            locations = context['location_id'] and [context['location_id']] or []

        ids = [('id', 'in', [])]
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots_virtual
                where
                    location_id IN %s group by prodlot_id
                having  sum(qty) '''+ str(args[0][1]) + str(args[0][2]),(tuple(locations),))  # not_a_user_entry
            res = cr.fetchall()
            ids = [('id', 'in', map(lambda x: x[0], res))]
        return ids

    def _parse_context_location_id(self, cr, uid, context=None):
        if context:
            location_id = context.get('location_id', False)
            if location_id:
                if isinstance(location_id, (str, unicode)):
                    location_id = [int(id) for id in location_id.split(',')]

                if context.get('location_dive', False):
                    new_location_ids = []
                    self._location_dive(cr, uid, location_id,
                                        result_ids=new_location_ids, context=context)
                    location_id = new_location_ids

                context['location_id'] = location_id

    def _location_dive(self, cr, uid, parent_location_ids, result_ids=None,
                       context=None):
        result_ids += [id for id in parent_location_ids if id not in result_ids]
        for r in self.pool.get('stock.location').read(cr, uid,
                                                      parent_location_ids, ['child_ids'], context=context):
            if r['child_ids']:
                self._location_dive(cr, uid, r['child_ids'],
                                    result_ids=result_ids, context=context)

    def _get_stock_virtual(self, cr, uid, ids, field_name, arg, context=None):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        self._parse_context_location_id(cr, uid, context=context)

        if isinstance(ids, (int, long)):
            ids = [ids]

        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
        else:
            locations = context['location_id'] or []

        if isinstance(locations, (int, long)):
            locations = [locations]

        res = {}.fromkeys(ids, 0.0)
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots_virtual
                where
                    location_id IN %s and prodlot_id IN %s group by prodlot_id''',(tuple(locations),tuple(ids),))
            res.update(dict(cr.fetchall()))

        return res

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for KC/SSL/DG/NP products
        '''
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False})

        for obj in self.browse(cr, uid, ids, context=context):
            # keep cool
            result[obj.id]['kc_check'] = obj.product_id.kc_txt
            # ssl
            result[obj.id]['ssl_check'] = obj.product_id.ssl_txt
            # dangerous goods
            result[obj.id]['dg_check'] = obj.product_id.dg_txt
            # narcotic
            result[obj.id]['np_check'] = obj.product_id.cs_txt
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True

        return result


    def _get_delete_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns if the batch is deletable
        '''
        res = {}
        for batch_id in ids:
            res[batch_id] = True
            move_ids = self.pool.get('stock.move').search(cr, uid, [('prodlot_id', '=', batch_id)], context=context)
            if move_ids:
                res[batch_id] = False

        return res

    def _is_expired(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if the lot is expired
        '''
        res = {}
        context = context is None and {} or context

        if isinstance(ids, (int, long)):
            ids = [ids]

        for batch in self.read(cr, uid, ids, ['life_date'], context=context):
            res[batch['id']] = False
            if batch['life_date'] < time.strftime('%Y-%m-%d'):
                res[batch['id']] = True

        return res

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for id in ids:
            res[id] = True

        return res

    def _src_product(self, cr, uid, obj, name, args, context=None):
        res = []

        for arg in args:
            if arg[0] == 'src_product_id':
                if arg[2]:
                    res.append(('product_id', arg[1], arg[2]))

        return res

    def _get_has_stock_move(self, cr, uid, ids, field_name, arg, context=None):
        if isinstance(ids,(long, int)):
            ids = [ids]
        if context is None:
            context = {}

        res = {}
        for _id in ids:
            res[_id] = self.pool.get('stock.move').search(cr, uid, [('prodlot_id', '=', _id)], limit=1, context=context) and True or False

        return res

    def _get_stock_location_id(self, cr, uid, ids, field_name, arg, context=None):
        # TODO remove if location name set in title
        if context is None:
            context = {}

        res = {}
        for _id in ids:
            res[_id] = context['location_id'] if isinstance(context.get('location_id'), (int, long)) else False

        return res

    _columns = {
        'name': fields.char('Batch Number', size=1024, required=True, help="Unique batch number, will be displayed as: PREFIX/SERIAL [INT_REF]"),
        'ref': fields.char('Internal Reference', size=256, help="Internal reference number in case it differs from the manufacturer's serial number"),
        'prefix': fields.char('Prefix', size=64, help="Optional prefix to prepend when displaying this serial number: PREFIX/SERIAL [INT_REF]"),
        'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('type', '<>', 'service')]),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', readonly=1, write_relate=False, string='UoM'),
        'date': fields.datetime('Auto Creation Date', required=True),
        'revisions': fields.one2many('stock.production.lot.revision', 'lot_id', 'Revisions'),
        'company_id': fields.many2one('res.company', 'Company', select=True),
        'move_ids': fields.one2many('stock.move', 'prodlot_id', 'Moves for this production lot', readonly=True),
        # batch recall
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=False),
        'partner_name': fields.char('Partner', size=128),
        'xmlid_name': fields.char('XML Code, hidden field', size=128), # UF-2148, this field is used only for xml_id
        # specific rules
        'check_type': fields.function(_get_false, fnct_search=search_check_type, string='Check Type', type="boolean", readonly=True, method=True),
        'has_stock_move': fields.function(_get_has_stock_move, string='Has stock move', type="boolean", readonly=True, method=True),
        # readonly is True, the user is only allowed to create standard lots - internal lots are system-created
        'type': fields.selection([('standard', 'Standard'),('internal', 'Internal'),], string="Type", readonly=True),
        'sequence_id': fields.many2one('ir.sequence', 'Batch Sequence', required=True,),
        'stock_virtual': fields.function(_get_stock_virtual, method=True, type="float", string="Available Stock", select=True,
                                         help="Current available quantity of products with this Batch Numbre Number in company warehouses",
                                         digits_compute=dp.get_precision('Product UoM'), readonly=True,
                                         fnct_search=_stock_search_virtual, related_uom='uom_id'),
        'stock_available': fields.function(_get_stock, fnct_search=_stock_search, method=True, type="float", string="Real Stock", select=True,
                                           help="Current real quantity of products with this Batch Number in company warehouses",
                                           digits_compute=dp.get_precision('Product UoM'), related_uom='uom_id'),
        'src_product_id': fields.function(_get_dummy, fnct_search=_src_product, method=True, type="boolean", string="By product"),
        'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='char', size=8, readonly=True, multi="m"),
        'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='char', size=8, readonly=True, multi="m"),
        'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='char', size=8, readonly=True, multi="m"),
        'np_check': fields.function(_get_checks_all, method=True, string='CS', type='char', size=8, readonly=True, multi="m"),
        'lot_check': fields.function(_get_checks_all, method=True, string='BN', type='boolean', readonly=True, multi="m"),
        'exp_check': fields.function(_get_checks_all, method=True, string='ED', type='boolean', readonly=True, multi="m"),
        'delete_ok': fields.function(_get_delete_ok, method=True, string='Possible deletion ?', type='boolean', readonly=True),
        'is_expired': fields.function(_is_expired, method=True, string='Expired ?', type='boolean', store=False, readonly=True),
        'life_date': fields.date('Expiry Date', help='The date on which the lot may become dangerous and should not be consumed.', required=True),
        'use_date': fields.date('Best before Date', help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.date('Removal Date', help='The date on which the lot should be removed.'),
        'alert_date': fields.date('Alert Date', help="The date on which an alert should be notified about the production lot."),
        'comment': fields.char('Comment', size=100),
        'stock_location_id': fields.function(_get_stock_location_id, method=True, type='many2one', relation='stock.location', string='Location of Stock Level'),
    }

    def _get_date(dtype):
        """Return a function to compute the limit date for this type"""
        def calc_date(self, cr, uid, context=None):
            """Compute the limit date for a given date"""
            if context is None:
                context = {}
            if not context.get('product_id', False):
                date = False
            else:
                product = self.pool.get('product.product').browse(
                    cr, uid, context['product_id'])
                duration = getattr(product, dtype)
                # set date to False when no expiry time specified on the product
                date = duration and (datetime.datetime.today() + relativedelta(months=duration))
            return date and date.strftime('%Y-%m-%d') or False
        return calc_date

    _defaults = {
        'date':  lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'product_id': lambda x, y, z, c: c.get('product_id', False),
        'type': 'standard',
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'stock.production.lot', context=c),
        'name': False,
        'life_date': False,
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }

    def _check_batch_type_integrity(self, cr, uid, ids, context=None):
        '''
        Check if the type of the batch is consistent with the product attributes
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.type == 'standard' and not obj.product_id.batch_management:
                return False

        return True

    def _check_perishable_type_integrity(self, cr, uid, ids, context=None):
        '''
        Check if the type of the batch is consistent with the product attributes
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.type == 'internal' and (obj.product_id.batch_management or not obj.product_id.perishable):
                return False

        return True

    _sql_constraints = [
        ('name_ref_uniq', 'unique (name, ref)', 'The combination of serial number and internal reference must be unique !'),
        ('batch_name_uniq', 'unique(name, product_id, life_date)', 'Batch name must be unique per product and expiry date!'),
    ]

    _constraints = [
        (_check_batch_type_integrity, 'You can\'t create a standard batch number for a product which is not batch mandatory. If the product is perishable, the system will create automatically an internal batch number on reception/inventory.', ['Type', 'Product']),
        (_check_perishable_type_integrity, 'You can\'t create an internal Batch Number for a product which is batch managed or which is not perishable. If the product is batch managed, please create a standard batch number.', ['Type', 'Product']),
    ]

    def _auto_init(self, cr, context=None):
        res = super(stock_production_lot, self)._auto_init(cr, context)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'ed_lot_life_date_uniq_index'")
        if not cr.fetchone():
            cr.execute("CREATE UNIQUE INDEX ed_lot_life_date_uniq_index ON stock_production_lot (life_date, product_id, NULLIF(type, 'standard'))")
        return res

    def unlink(self, cr, uid, ids, context=None):
        '''
        Remove the batch
        '''
        for batch in self.browse(cr, uid, ids, context=context):
            if not batch.delete_ok:
                raise osv.except_osv(_('Error'), _('You cannot remove a batch number which has stock !'))

        return super(stock_production_lot, self).unlink(cr, uid, ids, context=context)

    def action_traceability(self, cr, uid, ids, context=None):
        """ It traces the information of a product
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        @return: A dictionary of values
        """
        value = self.pool.get('action.traceability').action_traceability(cr,uid,ids,context)
        return value

    def get_or_create_prodlot(self, cr, uid, name, expiry_date, product_id, context=None):
        """
        Search corresponding Batch using name, product and expiry date, or create it
        """
        if context is None:
            context = {}

        # Double check to find the corresponding batch
        lot_ids = self.search(cr, uid, [
            ('name', '=', name),
            ('life_date', '=', expiry_date),
            ('product_id', '=', product_id),
        ], context=context)

        # No batch found, create a new one
        if not lot_ids:
            lot_id = self.create(cr, uid, {'name': name, 'product_id': product_id, 'life_date': expiry_date}, context)
        else:
            lot_id = lot_ids[0]

        return lot_id

# batch recall
    # UF-1617: Handle the instance in the batch number object
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'partner_name': False,
        })
        lot_name = self.read(cr, uid, id, ['name'])['name']
        default.update(name='%s (copy)'%lot_name, date=time.strftime('%Y-%m-%d'))
        return super(stock_production_lot, self).copy(cr, uid, id, default, context=context)

    # UF-1617: Handle the instance in the batch number object
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        do not copy asset events
        '''
        if not default:
            default = {}
        default.update({
            'partner_name': False,
            'revisions': [],
        })
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)

    def _get_or_create_lot(self, cr, uid, name, expiry_date, product_id, context=None):
        dom = [
            ('life_date', '=', expiry_date),
            ('product_id', '=', product_id),
        ]
        if not name:
            dom += [('type', '=', 'internal')]
        else:
            dom += [
                ('type', '=', 'standard'),
                ('name', '=', name)
            ]

        lot_ids = self.search(cr, uid, dom, context=context)
        if lot_ids:
            return lot_ids[0]

        vals = {
            'product_id': product_id,
            'life_date': expiry_date,
        }
        if not name:
            vals['type'] = 'internal'
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial')
        else:
            vals['type'] = 'standard'
            vals['name'] = name

        return self.create(cr, uid, vals, context=context)

    def _get_prodlot_from_expiry_date(self, cr, uid, expiry_date, product_id, comment=None, context=None):
        """
        Search if an internal batch exists in the system with this expiry date.
        If no, create the batch.
        """
        # Objects
        seq_obj = self.pool.get('ir.sequence')

        # Double check to find the corresponding batch
        lot_ids = self.search(cr, uid, [
            ('life_date', '=', expiry_date),
            ('type', '=', 'internal'),
            ('product_id', '=', product_id),
        ], context=context)

        # No batch found, create a new one
        if not lot_ids:
            seq_ed = seq_obj.get(cr, uid, 'stock.lot.serial')
            vals = {
                'product_id': product_id,
                'life_date': expiry_date,
                'name': seq_ed,
                'type': 'internal',
            }
            if comment is not None:
                vals['comment'] = comment
            lot_id = self.create(cr, uid, vals, context)
        else:
            lot_id = lot_ids[0]
            if comment is not None:
                self.write(cr, uid, lot_id, {'comment': comment}, context=context)

        return lot_id

# specific rules
    def create(self, cr, uid, vals, context=None):
        '''
        create the sequence for the version management
        '''
        if context is None:
            context = {}

        sequence = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'sequence_id': sequence,})

        newid = super(stock_production_lot, self).create(cr, uid, vals, context=context)
        obj = self.browse(cr, uid, newid, context=context)
        towrite = []
        for f in ('life_date', 'use_date', 'removal_date', 'alert_date'):
            if not getattr(obj, f):
                towrite.append(f)
        if context is None:
            context = {}
        context['product_id'] = obj.product_id.id
        self.write(cr, uid, [obj.id], self.default_get(cr, uid, towrite, context=context))
        return newid

    def write(self, cr, uid, ids, vals, context=None):
        '''
        update the sequence for the version management
        '''
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        revision_obj = self.pool.get('stock.production.lot.revision')

        for lot in self.browse(cr, uid, ids, context=context):
            # create revision object for each lot
            version_number = lot.sequence_id.get_id(code_or_id='id', context=context)
            values = {'name': 'Auto Revision Logging',
                      'description': 'The batch number has been modified, this revision log has been created automatically.',
                      'date': time.strftime('%Y-%m-%d'),
                      'indice': version_number,
                      'author_id': uid,
                      'lot_id': lot.id,}
            revision_obj.create(cr, uid, values, context=context)

        return super(stock_production_lot, self).write(cr, uid, ids, vals, context=context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have those from account_statement_from_invoice_lines (in case where account_statement_from_invoice is used)
        """
        if context is None:
            context = {}

        # warehouse wizards or inventory screen
        label = False
        if view_type == 'tree':
            if (context.get('expiry_date_check', False) and not context.get('batch_number_check', False)) or context.get('hidden_perishable_mandatory', False):
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'specific_rules', 'view_production_lot_expiry_date_tree')
                if view:
                    view_id = view[1]
            if context.get('location_id') and isinstance(context['location_id'], (int, long)):
                label = self.pool.get('stock.location').read(cr, uid, context['location_id'], ['name'], context=context)['name']

        result = super(stock_production_lot, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if label:
            root = etree.fromstring(result['arch'])
            root.set('string', '%s %s %s' % (root.get('string'), _('Location: '), label))
            result['arch'] = etree.tostring(root)
        return result

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Batch number'
        code = 'stock.production.lot'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)


stock_production_lot()


class stock_production_lot_revision(osv.osv):
    _name = 'stock.production.lot.revision'
    _description = 'Production lot revisions'
    _order = 'indice desc'

    _columns = {
        'name': fields.char('Revision Name', size=64, required=True),
        'description': fields.text('Description'),
        'date': fields.date('Revision Date'),
        'indice': fields.char('Revision Number', size=16),
        'author_id': fields.many2one('res.users', 'Author'),
        'lot_id': fields.many2one('stock.production.lot', 'Production lot', select=True, ondelete='cascade'),
        'company_id': fields.related('lot_id','company_id',type='many2one',relation='res.company',string='Company', store=True, readonly=True),
    }

    _defaults = {
        'author_id': lambda x, y, z, c: z,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

stock_production_lot_revision()


