# -*- coding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import osv, fields
import netsvc
from tools.translate import _
import decimal_precision as dp
from purchase_override import PURCHASE_ORDER_STATE_SELECTION, PURCHASE_ORDER_LINE_STATE_SELECTION


class purchase_order_line(osv.osv):
    _table = 'purchase_order_line'
    _name = 'purchase.order.line'
    _description = 'Purchase Order Line'

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _amount_line(self, cr, uid, ids, prop, arg, context=None):
        res = {}
        cur_obj = self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        for line in self.browse(cr, uid, ids, context=context):
            taxes = tax_obj.compute_all(cr, uid, line.taxes_id, line.price_unit, line.product_qty)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur.rounding, taxes['total'])
            if line.price_unit > 0 and res[line.id] < 0.01:
                res[line.id] = 0.01
        return res

    def _get_price_change_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if the price can be changed by the user
        '''
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = True
            stages = self._get_stages_price(cr, uid, line.product_id.id, line.product_uom.id, line.order_id,
                                            context=context)
            if line.merged_id and len(
                    line.merged_id.order_line_ids) > 1 and line.order_id.state != 'confirmed' and stages and not line.order_id.rfq_ok:
                res[line.id] = False

        return res

    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret

    def _get_fake_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['id']):
            ret[pol['id']] = pol['id']
        return ret

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # default values
            result[obj.id] = {'order_state_purchase_order_line': False}
            # order_state_purchase_order_line
            if obj.order_id:
                result[obj.id].update({'order_state_purchase_order_line': obj.order_id.state})

        return result

    def _get_project_po_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the name of the PO at project side
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = dict.fromkeys(ids, '')
        for line_id in ids:
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, line_id, context=context)
            for sol in self.pool.get('sale.order.line').browse(cr, uid, sol_ids, context=context):
                if sol.order_id and sol.order_id.client_order_ref:
                    if res[line_id]:
                        res[line_id] += ' - '
                    res[line_id] += sol.order_id.client_order_ref

        return res

    def _get_link_sol_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Return the ID of the first FO line sourced by this PO line
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = dict.fromkeys(ids, False)
        for line_id in ids:
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, [line_id], context=context)
            if sol_ids:
                res[line_id] = sol_ids[0]

        return res

    def _get_customer_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the customer ref from "sale.order".client_order_ref
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            res[
                pol.id] = pol.procurement_id and pol.procurement_id.sale_id and pol.procurement_id.sale_id.client_order_ref or False

        return res

    def _get_display_state(self, cr, uid, ids, field_name, args, context=None):
        '''
        return the purchase.order.line state to display
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            # if PO line has been created from ressourced process, then we display the state as 'Resourced-XXX':
            if pol.resourced_original_line:
                if pol.state.startswith('draft'):
                    res[pol.id] = 'Resourced-d'
                elif pol.state.startswith('validated'):
                    res[pol.id] = 'Resourced-v'
                elif pol.state.startswith('sourced'):
                    if pol.state == 'sourced_v':
                        res[pol.id] = 'Resourced-pv'
                    else:
                        res[pol.id] = 'Resourced-s'
                elif pol.state.startswith('confirmed'):
                    res[pol.id] = 'Resourced-c'
            else: # case of regular PO line, we just copy the current line state:
                res[pol.id] = self.pool.get('ir.model.fields').get_browse_selection(cr, uid, pol, 'state', context=context)

        return res


    _columns = {
        'set_as_sourced_n': fields.boolean(string='Set as Sourced-n', help='Line has been created further and has to be created back in preceding documents'),
        'set_as_validated_n': fields.boolean(string='Created when PO validated', help='Usefull for workflow transition to set the validated-n state'),
        'is_line_split': fields.boolean(string='This line is a split line?'),
        'linked_sol_id': fields.many2one('sale.order.line', string='Linked FO line', help='Linked Sale Order line in case of PO line from sourcing', readonly=True),
        'sync_linked_sol': fields.char(size=256, string='Linked FO line at synchro'),
        # UTP-972: Use boolean to indicate if the line is a split line
        'merged_id': fields.many2one('purchase.order.merged.line', string='Merged line'),
        'origin': fields.char(size=512, string='Origin'),
        'link_so_id': fields.many2one('sale.order', string='Linked FO/IR', readonly=True),
        'dpo_received': fields.boolean(string='Is the IN has been received at Project side ?'),
        'change_price_ok': fields.function(_get_price_change_ok, type='boolean', method=True, string='Price changing'),
        'change_price_manually': fields.boolean(string='Update price manually'),
        # openerp bug: eval invisible in p.o use the po line state and not the po state !
        'fake_state': fields.function(_get_fake_state, type='char', method=True, string='State',
                                      help='for internal use only'),
        # openerp bug: id is not given to onchanqge call if we are into one2many view
        'fake_id': fields.function(_get_fake_id, type='integer', method=True, string='Id',
                                   help='for internal use only'),
        'old_price_unit': fields.float(string='Old price',
                                       digits_compute=dp.get_precision('Purchase Price Computation')),
        'order_state_purchase_order_line': fields.function(_vals_get, method=True, type='selection',
                                                           selection=PURCHASE_ORDER_STATE_SELECTION,
                                                           string='State of Po', multi='get_vals_purchase_override',
                                                           store=False, readonly=True),

        # This field is used to identify the FO PO line between 2 instances of the sync
        'sync_order_line_db_id': fields.text(string='Sync order line DB Id', required=False, readonly=True),
        'external_ref': fields.char(size=256, string='Ext. Ref.'),
        'project_ref': fields.char(size=256, string='Project Ref.'),
        'has_to_be_resourced': fields.boolean(string='Has to be re-sourced'),
        'select_fo': fields.many2one('sale.order', string='FO'),
        'fnct_project_ref': fields.function(_get_project_po_ref, method=True, string='Project PO',
                                            type='char', size=128, store=False),
        'from_fo': fields.boolean(string='From FO', readonly=True),
        'display_sync_ref': fields.boolean(string='Display sync. ref.'),
        'instance_sync_order_ref': fields.many2one('sync.order.label', string='Order in sync. instance'),
        'link_sol_id': fields.function(_get_link_sol_id, method=True, type='many2one', relation='sale.order.line',
                                       string='Linked FO line', store=False),
        'soq_updated': fields.boolean(string='SoQ updated', readonly=True),
        'red_color': fields.boolean(string='Red color'),
        'customer_ref': fields.function(_get_customer_ref, method=True, type="text", store=False,
                                        string="Customer ref."),
        'name': fields.char('Description', size=256, required=True),
        'product_qty': fields.float('Quantity', required=True, digits=(16, 2)),
        'date_planned': fields.date('Scheduled Date', required=True, select=True),
        'taxes_id': fields.many2many('account.tax', 'purchase_order_taxe', 'ord_id', 'tax_id', 'Taxes'),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True, select=True),
        'product_id': fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', True)],
                                      change_default=True, select=True),
        'move_ids': fields.one2many('stock.move', 'purchase_line_id', 'Reservation', readonly=True,
                                    ondelete='set null'),
        'move_dest_id': fields.many2one('stock.move', 'Reservation Destination', ondelete='set null', select=True),
        'price_unit': fields.float('Unit Price', required=True,
                                   digits_compute=dp.get_precision('Purchase Price Computation')),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False,
                                  readonly=True),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal',
                                          digits_compute=dp.get_precision('Purchase Price')),
        'notes': fields.text('Notes'),
        'order_id': fields.many2one('purchase.order', 'Order Reference', select=True, required=True,
                                    ondelete='cascade'),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic Account', ),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, readonly=True),
        'state': fields.selection(PURCHASE_ORDER_LINE_STATE_SELECTION, 'State', required=True, readonly=True,
                                  help=' * The \'Draft\' state is set automatically when purchase order in draft state. \
                                       \n* The \'Confirmed\' state is set automatically as confirm when purchase order in confirm state. \
                                       \n* The \'Done\' state is set automatically when purchase order is set as done. \
                                       \n* The \'Cancelled\' state is set automatically when user cancel purchase order.'),
        'display_state': fields.function(_get_display_state, string='State', type='text', method=True, readonly=True,
            help=' * The \'Draft\' state is set automatically when purchase order in draft state. \
               \n* The \'Confirmed\' state is set automatically as confirm when purchase order in confirm state. \
               \n* The \'Done\' state is set automatically when purchase order is set as done. \
               \n* The \'Cancelled\' state is set automatically when user cancel purchase order.'
        ),
        'resourced_original_line': fields.many2one('purchase.order.line', 'Original line', readonly=True, help='Original line from which the current one has been cancel and ressourced'),
        'invoice_lines': fields.many2many('account.invoice.line', 'purchase_order_line_invoice_rel', 'order_line_id',
                                          'invoice_id', 'Invoice Lines', readonly=True),
        'invoiced': fields.boolean('Invoiced', readonly=True),
        'partner_id': fields.related('order_id','partner_id',string='Partner',readonly=True,type="many2one", relation="res.partner", store=True),
        'date_order': fields.related('order_id','date_order',string='Order Date',readonly=True,type="date"),
    }
    _defaults = {
        'set_as_sourced_n': lambda *a: False,
        'set_as_validated_n': lambda *a: False,
        'change_price_manually': lambda *a: False,
        'product_qty': lambda *a: 0.00,
        'price_unit': lambda *a: 0.00,
        'change_price_ok': lambda *a: True,
        'is_line_split': False,  # UTP-972: by default not a split line
        'from_fo': lambda self, cr, uid, c: not c.get('rfq_ok', False) and c.get('from_fo', False),
        'soq_updated': False,
        'state': lambda *args: 'draft',
        'invoiced': lambda *a: 0,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
    }

    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            is_inkind = line.order_id and line.order_id.order_type == 'in_kind' or False
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                if is_inkind:
                    raise osv.except_osv(_('Error'), _(
                        'No destination found. An In-kind Donation account is probably missing for this line: %s.') % (
                        line.name or ''))
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok

    def check_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Check analytic distribution validity for given PO line.
        Also check that partner have a donation account (is PO is in_kind)
        """
        # Objects
        ad_obj = self.pool.get('analytic.distribution')
        ccdl_obj = self.pool.get('cost.center.distribution.line')
        pol_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, context=context):
            po = pol.order_id
            distrib = pol.analytic_distribution_id or po.analytic_distribution_id or False
            # Raise an error if no analytic distribution found
            if not distrib:
                # UFTP-336: For the case of a new line added from Coordo, it's a push flow, no need to check the AD! VERY SPECIAL CASE
                if po.order_type not in ('loan', 'donation_st', 'donation_exp', 'in_kind') and not po.push_fo:
                    raise osv.except_osv(_('Warning'),
                                         _('Analytic allocation is mandatory for this line: %s!') % (pol.name or '',))

                # UF-2031: If no distrib accepted (for loan, donation), then do not process the distrib
                return True
            elif pol.analytic_distribution_state != 'valid':
                id_ad = ad_obj.create(cr, uid, {})
                ad_lines = pol.analytic_distribution_id and pol.analytic_distribution_id.cost_center_lines or po.analytic_distribution_id.cost_center_lines
                bro_dests = self._get_destination_ok(cr, uid, [pol], context=context)
                for line in ad_lines:
                    # fetch compatible destinations then use on of them:
                    # - destination if compatible
                    # - else default destination of given account
                    if line.destination_id in bro_dests:
                        bro_dest_ok = line.destination_id
                    else:
                        bro_dest_ok = pol.account_4_distribution.default_destination_id
                    # Copy cost center line to the new distribution
                    ccdl_obj.copy(cr, uid, line.id, {
                        'distribution_id': id_ad,
                        'destination_id': bro_dest_ok.id,
                        'partner_type': po.partner_id.partner_type,
                    })
                # Write result
                pol_obj.write(cr, uid, [pol.id], {'analytic_distribution_id': id_ad})
            else:
                ad_lines = pol.analytic_distribution_id and pol.analytic_distribution_id.cost_center_lines or po.analytic_distribution_id.cost_center_lines
                line_ids_to_write = [line.id for line in ad_lines if not
                                     line.partner_type]
                ccdl_obj.write(cr, uid, line_ids_to_write, {
                    'partner_type': pol.order_id.partner_id.partner_type,
                })

        return True

    def _hook_product_id_change(self, cr, uid, *args, **kwargs):
        '''
        Override the computation of product qty to order
        '''
        prod = kwargs['product']
        partner_id = kwargs['partner_id']
        qty = kwargs['product_qty']

        product_uom_pool = self.pool.get('product.uom')

        res = {}
        for s in prod.seller_ids:
            if s.name.id == partner_id:
                seller_delay = s.delay
                if s.product_uom:
                    temp_qty = product_uom_pool._compute_qty(cr, uid, s.product_uom.id, s.min_qty,
                                                             to_uom_id=prod.uom_id.id)
                    uom = s.product_uom.id  # prod_uom_po
                temp_qty = s.min_qty  # supplier _qty assigned to temp
                if qty < temp_qty:  # If the supplier quantity is greater than entered from user, set minimal.
                    qty = temp_qty
                    res.update({'warning': {'title': _('Warning'), 'message': _(
                        'The selected supplier has a minimal quantity set to %s, you cannot purchase less.') % qty}})
        qty_in_product_uom = product_uom_pool._compute_qty(cr, uid, uom, qty, to_uom_id=prod.uom_id.id)
        return res, qty_in_product_uom, qty, seller_delay

    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
                          partner_id, date_order=False, fiscal_position=False, date_planned=False,
                          name=False, price_unit=False, notes=False):
        if not pricelist:
            raise osv.except_osv(_('No Pricelist !'), _(
                'You have to select a pricelist or a supplier in the purchase form !\nPlease set one before choosing a product.'))
        if not partner_id:
            raise osv.except_osv(_('No Partner!'), _(
                'You have to select a partner in the purchase form !\nPlease set one partner before choosing a product.'))
        if not product:
            return {'value': {'price_unit': price_unit or 0.0, 'name': name or '',
                              'notes': notes or '', 'product_uom': uom or False}, 'domain': {'product_uom': []}}
        res = {}
        prod = self.pool.get('product.product').browse(cr, uid, product)

        lang = False
        if partner_id:
            lang = self.pool.get('res.partner').read(cr, uid, partner_id, ['lang'])['lang']
        context = {'lang': lang}
        context['partner_id'] = partner_id

        prod = self.pool.get('product.product').browse(cr, uid, product, context=context)
        prod_uom_po = prod.uom_po_id.id
        if not uom:
            uom = prod_uom_po
        if not date_order:
            date_order = time.strftime('%Y-%m-%d')
        qty = qty or 1.0
        seller_delay = 0

        prod_name = self.pool.get('product.product').name_get(cr, uid, [prod.id], context=context)[0][1]

        res, qty_in_product_uom, qty, seller_delay = self._hook_product_id_change(cr, uid, product=prod,
                                                                                  partner_id=partner_id,
                                                                                  product_qty=qty, pricelist=pricelist,
                                                                                  order_date=date_order, uom_id=uom,
                                                                                  seller_delay=seller_delay, res=res,
                                                                                  context=context)

        price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
                                                             product, qty_in_product_uom or 1.0, partner_id, {
                                                                 'uom': uom,
                                                                 'date': date_order,
        })[pricelist]
        if price is False:
            warning = {
                'title': 'No valid pricelist line found !',
                'message':
                    "Couldn't find a pricelist line matching this product and quantity.\n"
                    "You have to change either the product, the quantity or the pricelist."
            }
            res.update({'warning': warning})
        dt = (datetime.now() + relativedelta(days=int(seller_delay) or 0.0)).strftime('%Y-%m-%d %H:%M:%S')

        res.update({'value': {'price_unit': price, 'name': prod_name,
                              'taxes_id': map(lambda x: x.id, prod.supplier_taxes_id),
                              'date_planned': date_planned or dt, 'notes': notes or prod.description_purchase,
                              'product_qty': qty,
                              'product_uom': uom}})
        domain = {}

        taxes = self.pool.get('account.tax').browse(cr, uid, map(lambda x: x.id, prod.supplier_taxes_id))
        fpos = fiscal_position and self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position) or False
        res['value']['taxes_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, taxes)

        res2 = self.pool.get('product.uom').read(cr, uid, [uom], ['category_id'])
        res3 = prod.uom_id.category_id.id
        domain = {'product_uom': [('category_id', '=', res2[0]['category_id'][0])]}
        if res2[0]['category_id'][0] != res3:
            raise osv.except_osv(_('Wrong Product UOM !'), _(
                'You have to select a product UOM in the same category than the purchase UOM of the product'))

        res['domain'] = domain
        return res

    def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
                           partner_id, date_order=False, fiscal_position=False, date_planned=False,
                           name=False, price_unit=False, notes=False):
        qty = 0.00
        res = self.product_id_change(cr, uid, ids, pricelist, product, qty, uom,
                                     partner_id, date_order=date_order, fiscal_position=fiscal_position,
                                     date_planned=date_planned,
                                     name=name, price_unit=price_unit, notes=notes)
        if 'product_uom' in res['value']:
            if uom and (uom != res['value']['product_uom']) and res['value']['product_uom']:
                seller_uom_name = \
                    self.pool.get('product.uom').read(cr, uid, [res['value']['product_uom']], ['name'])[0]['name']
                res.update({'warning': {'title': _('Warning'), 'message': _(
                    'The selected supplier only sells this product by %s') % seller_uom_name}})
            del res['value']['product_uom']
        if not uom:
            res['value']['price_unit'] = 0.0
        if not product:
            return res
        res['value'].update({'product_qty': 0.00})
        res.update({'warning': {}})

        return res

    # FROM PUCHASE OVV
    def link_merged_line(self, cr, uid, vals, product_id, order_id, product_qty, uom_id, price_unit=0.00, context=None):
        '''
        Check if a merged line exist. If not, create a new one and attach them to the Po line
        '''
        line_obj = self.pool.get('purchase.order.merged.line')
        if product_id:
            domain = [('product_id', '=', product_id), ('order_id', '=', order_id), ('product_uom', '=', uom_id)]
            # Search if a merged line already exist for the same product, the same order and the same UoM
            merged_ids = line_obj.search(cr, uid, domain, context=context)
        else:
            merged_ids = []

        new_vals = vals.copy()
        # Don't include taxes on merged lines
        if 'taxes_id' in new_vals:
            new_vals.pop('taxes_id')

        if not merged_ids:
            new_vals['order_id'] = order_id
            if not new_vals.get('price_unit', False):
                new_vals['price_unit'] = price_unit
            # Create a new merged line which is the same than the normal PO line except for price unit
            vals['merged_id'] = line_obj.create(cr, uid, new_vals, context=context)
        else:
            c = context.copy()
            order = self.pool.get('purchase.order').browse(cr, uid, order_id, context=context)
            stages = self._get_stages_price(cr, uid, product_id, uom_id, order, context=context)
            if order.state != 'confirmed' and stages and not order.rfq_ok:
                c.update({'change_price_ok': False})
            # Update the associated merged line
            res_merged = line_obj._update(cr, uid, merged_ids[0], False, product_qty, price_unit, context=c,
                                          no_update=False)
            vals['merged_id'] = res_merged[0]
            # Update unit price
            vals['price_unit'] = res_merged[1]

        return vals

    def _update_merged_line(self, cr, uid, line_id, vals=None, context=None):
        '''
        Update the merged line
        '''
        merged_line_obj = self.pool.get('purchase.order.merged.line')

        if not vals:
            vals = {}
        tmp_vals = vals.copy()

        # If it's an update of a line
        if vals and line_id:
            line = self.read(cr, uid, line_id,
                             ['product_uom',
                              'product_qty',
                              'product_id',
                              'merged_id',
                              'change_price_ok',
                              'price_unit',
                              'order_id', ],
                             context=context)

            # Set default values if not pass in values
            if 'product_uom' not in vals:
                tmp_vals.update({'product_uom': line['product_uom'][0]})
            if 'product_qty' not in vals:
                tmp_vals.update({'product_qty': line['product_qty']})

            line_product_id = line['product_id'] and line['product_id'][0] or False
            merged_id = line['merged_id'] and line['merged_id'][0] or False
            # If the user changed the product or the UoM or both on the PO line
            if ('product_id' in vals and line_product_id != vals['product_id']) or (
                    'product_uom' in vals and line['product_uom'][0] != vals['product_uom']):
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                change_price_ok = line['change_price_ok']
                c = context.copy()
                tmp_import_in_progress = context.get('import_in_progress')
                context['import_in_progress'] = True
                c.update({'change_price_ok': change_price_ok})
                self.write(cr, uid, line_id, {'merged_id': False}, context=context)
                if tmp_import_in_progress:
                    context.update({'import_in_progress': tmp_import_in_progress})
                else:
                    del context['import_in_progress']
                res_merged = merged_line_obj._update(cr, uid, merged_id, line['id'], -line['product_qty'],
                                                     line['price_unit'], context=c)

                # Create or update an existing merged line with the new product
                vals = self.link_merged_line(cr, uid, tmp_vals, tmp_vals.get('product_id', line_product_id),
                                             line['order_id'][0], tmp_vals.get('product_qty', line['product_qty']),
                                             tmp_vals.get('product_uom', line['product_uom'][0]),
                                             tmp_vals.get('price_unit', line['price_unit']), context=context)

            # If the quantity is changed
            elif 'product_qty' in vals and line['product_qty'] != vals['product_qty']:
                res_merged = merged_line_obj._update(cr, uid, merged_id, line['id'],
                                                     vals['product_qty'] - line['product_qty'], line['price_unit'],
                                                     context=context)
                # Update the unit price
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})

            # If the price unit is changed and the product and the UoM is not modified
            if 'price_unit' in tmp_vals and (
                    line['price_unit'] != tmp_vals['price_unit'] or vals['price_unit'] != tmp_vals[
                        'price_unit']) and not (
                    line_product_id != vals.get('product_id', False) or line['product_uom'][0] != vals.get(
                    'product_uom', False)):
                # Give 0.00 to quantity because the _update should recompute the price unit with the same quantity
                res_merged = merged_line_obj._update(cr, uid, merged_id, line['id'], 0.00, tmp_vals['price_unit'],
                                                     context=context)
                # Update the unit price
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
        # If it's a new line
        elif not line_id:
            c = context.copy()
            vals = self.link_merged_line(cr, uid, vals, vals.get('product_id'), vals['order_id'], vals['product_qty'],
                                         vals['product_uom'], vals['price_unit'], context=c)
        # If the line is removed
        elif not vals:
            line = self.read(cr, uid, line_id,
                             ['merged_id',
                              'change_price_ok',
                              'product_qty',
                              'price_unit'],
                             context=context)
            # Remove the qty from the merged line
            if line['merged_id']:
                merged_id = line['merged_id'] and line['merged_id'][0] or False
                change_price_ok = line['change_price_ok']
                c = context.copy()
                c.update({'change_price_ok': change_price_ok})
                noraise_ctx = context.copy()
                noraise_ctx.update({'noraise': True})
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                self.write(cr, uid, [line['id']], {'merged_id': False}, context=noraise_ctx)
                res_merged = merged_line_obj._update(cr, uid, merged_id, line['id'], -line['product_qty'],
                                                     line['price_unit'], context=c)

        return vals

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is restriction on lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and line.order_id.partner_id and line.order_id.state != 'done' and line.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, line.product_id.id, vals={
                                                                               'partner_id': line.order_id.partner_id.id}, context=context):
                    return False

        return True

    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description': False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            product_obj = self.pool.get('product.product').read(cr, uid, vals['product_id'], ['name', 'default_code'],
                                                                context=context)
            vals.update({'name': product_obj['name']})
            vals.update({'default_code': product_obj['default_code']})
            vals.update({'default_name': product_obj['name']})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            sale = self.pool.get('sale.order.line')
            sale._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code': False})
            vals.update({'default_name': False})

            if 'comment' in vals:
                vals.update({'name': vals['comment']})
                # clear nomenclature filter values
                # self.pool.get('product.product')._resetNomenclatureFields(vals)

    def _update_name_attr(self, cr, uid, vals, context=None):
        """Update the name attribute in `vals` if a product is selected."""
        if context is None:
            context = {}
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id'):
            product = prod_obj.read(cr, uid, vals['product_id'], ['name'], context=context)
            vals['name'] = product['name']
        elif vals.get('comment'):
            vals['name'] = vals.get('comment', False)

    def _check_product_uom(self, cr, uid, product_id, uom_id, context=None):
        """Check the product UoM."""
        if context is None:
            context = {}
        uom_tools_obj = self.pool.get('uom.tools')
        if not uom_tools_obj.check_uom(cr, uid, product_id, uom_id, context=context):
            raise osv.except_osv(
                _('Error'),
                _('You have to select a product UOM in the same '
                  'category than the purchase UOM of the product !'))

    def create(self, cr, uid, vals, context=None):
        '''
        Create or update a merged line
        '''
        if context is None:
            context = {}

        po_obj = self.pool.get('purchase.order')
        seq_pool = self.pool.get('ir.sequence')
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')

        order_id = vals.get('order_id')
        product_id = vals.get('product_id')
        product_uom = vals.get('product_uom')
        order = po_obj.browse(cr, uid, order_id, context=context)

        # if the PO line has been created when PO has status "validated" then new PO line gets specific state "validated-n" to mark the 
        # line as non-really validated. It avoids the PO to go back in draft state.
        if order.state == 'validated':
            vals.update({'set_as_validated_n': True})

        # Update the name attribute if a product is selected
        self._update_name_attr(cr, uid, vals, context=context)

        # If we are on a RfQ, use the last entered unit price and update other lines with this price
        if order.rfq_ok:
            vals.update({'change_price_manually': True})
        else:
            if order.po_from_fo or order.po_from_ir or vals.get('link_so_id', False):
                vals['from_fo'] = True
            if vals.get('product_qty', 0.00) == 0.00 and not context.get('noraise'):
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

        other_lines = self.search(cr, uid, [('order_id', '=', order_id),
                                            ('product_id', '=', product_id), ('product_uom', '=', product_uom)],
                                  limit=1, order='NO_ORDER', context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        if vals.get('origin'):
            proc = False
            if vals.get('procurement_id'):
                proc = self.pool.get('procurement.order').read(cr, uid, vals.get('procurement_id'), ['sale_id'])
            if not proc or not proc['sale_id']:
                vals.update(self.update_origin_link(cr, uid, vals.get('origin'), context=context))

        if (other_lines and stages and order.state != 'confirmed'):
            context.update({'change_price_ok': False})

        # if not context.get('offline_synchronization'):
        #     vals = self._update_merged_line(cr, uid, False, vals, context=dict(context, skipResequencing=True))

        vals.update({'old_price_unit': vals.get('price_unit', False)})

        # [imported from 'order_nomenclature']
        # Don't save filtering data
        self._relatedFields(cr, uid, vals, context)
        # [/]

        # [imported from 'order_line_number']
        # Add the corresponding line number
        #   I leave this line from QT related to purchase.order.merged.line for compatibility and safety reasons
        #   merged lines, set the line_number to 0 when calling create function
        #   the following line should *logically* be removed safely
        #   copy method should work as well, as merged line do *not* need to keep original line number with copy function (QT confirmed)
        if self._name != 'purchase.order.merged.line':
            if order_id:
                # gather the line number from the sale order sequence if not specified in vals
                # either line_number is not specified or set to False from copy, we need a new value
                if not vals.get('line_number', False):
                    # new number needed - gather the line number from the sequence
                    sequence_id = order.sequence_id.id
                    line = seq_pool.get_id(cr, uid, sequence_id, code_or_id='id', context=context)
                    vals.update({'line_number': line})
        # [/]

        # Check the selected product UoM
        if not context.get('import_in_progress', False):
            if vals.get('product_id') and vals.get('product_uom'):
                self._check_product_uom(
                    cr, uid, vals['product_id'], vals['product_uom'], context=context)

        # utp-518:we write the comment from the sale.order.line on the PO line through the procurement (only for the create!!)
        po_procurement_id = vals.get('procurement_id', False)
        if po_procurement_id and not vals.get('comment'):
            sale_id = sol_obj.search(cr, uid, [('procurement_id', '=', po_procurement_id)], context=context)
            if sale_id:
                comment_so = sol_obj.read(cr, uid, sale_id, ['comment'], context=context)[0]['comment']
                vals.update(comment=comment_so)

        # add the database Id to the sync_order_line_db_id
        po_line_id = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False):  # 'sync_order_line_db_id' not in vals or vals:
            name = order.name
            super(purchase_order_line, self).write(cr, uid, [po_line_id],
                                                   {'sync_order_line_db_id': name + "_" + str(po_line_id), },
                                                   context=context)

        if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('procurement_id'):
            so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], context=context)
            for so_id in so_ids:
                self.pool.get('expected.sale.order.line').create(cr, uid, {
                    'order_id': so_id,
                    'po_line_id': po_line_id,
                }, context=context)

        return po_line_id

    def default_get(self, cr, uid, fields, context=None):
        if not context:
            context = {}

        if context.get('purchase_id'):
            # Check validity of the purchase order. We write the order to avoid
            # the creation of a new line if one line of the order is not valid
            # according to the order category
            # Example :
            #    1/ Create a new PO with 'Other' as Order Category
            #    2/ Add a new line with a Stockable product
            #    3/ Change the Order Category of the PO to 'Service' -> A warning message is displayed
            #    4/ Try to create a new line -> The system displays a message to avoid you to create a new line
            #       while the not valid line is not modified/deleted
            #
            #   Without the write of the order, the message displayed by the system at 4/ is displayed at the saving
            #   of the new line that is not very understandable for the user
            data = {}
            if context.get('partner_id'):
                data.update({'partner_id': context.get('partner_id')})
            if context.get('categ'):
                data.update({'categ': context.get('categ')})
            self.pool.get('purchase.order').write(cr, uid, [context.get('purchase_id')], data, context=context)

        return super(purchase_order_line, self).default_get(cr, uid, fields, context=context)

    def copy(self, cr, uid, line_id, defaults={}, context=None):
        '''
        Remove link to merged line
        '''
        defaults.update({'merged_id': False, 'sync_order_line_db_id': False, 'linked_sol_id': False, 'set_as_sourced_n': False, 'set_as_validated_n': False})

        return super(purchase_order_line, self).copy(cr, uid, line_id, defaults, context=context)

    def copy_data(self, cr, uid, p_id, default=None, context=None):
        """
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}

        default.update({'state': 'draft', 'move_ids': [], 'invoiced': 0, 'invoice_lines': []})
        if 'origin' not in default:
            default.update({'origin': False})

        if 'move_dest_id' not in default:
            default.update({'move_dest_id': False})

        if 'procurement_id' not in default:
            default.update({'procurement_id': False})

        default.update({'sync_order_line_db_id': False, 'set_as_sourced_n': False, 'set_as_validated_n': False, 'linked_sol_id': False})
        return super(purchase_order_line, self).copy_data(cr, uid, p_id, default=default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update merged line
        '''
        if not ids:
            return True
        so_obj = self.pool.get('sale.order')
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = False

        # [imported from the 'analytic_distribution_supply']
        # Don't save filtering data
        self._relatedFields(cr, uid, vals, context)
        # [/]

        # Update the name attribute if a product is selected
        self._update_name_attr(cr, uid, vals, context=context)

        if 'price_unit' in vals:
            vals.update({'old_price_unit': vals.get('price_unit')})

        if ('state' in vals and vals.get('state') != 'draft') or (
                'procurement_id' in vals and vals.get('procurement_id')):
            exp_sol_ids = exp_sol_obj.search(cr, uid, [('po_line_id', 'in', ids)],
                                             order='NO_ORDER', context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        # Remove SoQ updated flag in case of manual modification
        if not 'soq_updated' in vals:
            vals['soq_updated'] = False

        for line in self.browse(cr, uid, ids, context=context):
            new_vals = vals.copy()
            # check qty
            if vals.get('product_qty', line.product_qty) <= 0.0 and \
                    not line.order_id.rfq_ok and \
                    'noraise' not in context and line.state != 'cancel':
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

            if vals.get('origin', line.origin):
                proc = False
                if vals.get('procurement_id', line.procurement_id.id):
                    proc = self.pool.get('procurement.order').browse(cr, uid,
                                                                     vals.get('procurement_id', line.procurement_id.id))
                if not proc or not proc.sale_id:
                    link_so_dict = self.update_origin_link(cr, uid, vals.get('origin', line.origin), context=context)
                    new_vals.update(link_so_dict)

            if line.order_id and not line.order_id.rfq_ok and (line.order_id.po_from_fo or line.order_id.po_from_ir):
                new_vals['from_fo'] = True

            # if not context.get('update_merge'):
            #     new_vals.update(self._update_merged_line(cr, uid, line.id, vals, context=dict(context, skipResequencing=True, noraise=True)))

            res = super(purchase_order_line, self).write(cr, uid, [line.id], new_vals, context=context)

            if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('procurement_id',
                                                                                                  line.procurement_id):
                so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], order='NO_ORDER', context=context)
                for so_id in so_ids:
                    exp_sol_obj.create(cr, uid, {
                        'order_id': so_id,
                        'po_line_id': line.id,
                    }, context=context)

        # Check the selected product UoM
        if not context.get('import_in_progress', False):
            for pol_read in self.read(cr, uid, ids, ['product_id', 'product_uom']):
                if pol_read.get('product_id'):
                    product_id = pol_read['product_id'][0]
                    uom_id = pol_read['product_uom'][0]
                    self._check_product_uom(cr, uid, product_id, uom_id, context=context)

        return res

    def update_origin_link(self, cr, uid, origin, context=None):
        '''
        Return the FO/IR that matches with the origin value
        '''
        so_obj = self.pool.get('sale.order')

        tmp_proc_context = context.get('procurement_request')
        context['procurement_request'] = True
        so_ids = so_obj.search(cr, uid, [('name', '=', origin), ('state', 'in', ['draft', 'draft_p', 'validated', 'validated_p', 'sourced', 'sourced_v'])], context=context)
        context['procurement_request'] = tmp_proc_context
        if so_ids:
            return {'link_so_id': so_ids[0]}

        return {}

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Method to cancel a PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz_id = self.pool.get('purchase.order.line.cancel.wizard').create(cr, uid, {'pol_id': ids[0]}, context=context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_line_cancel_form_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.line.cancel.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'target': 'new',
            'context': context
        }

    def cancel_sol(self, cr, uid, ids, context=None):
        '''
        Re-source the FO line
        '''
        context = context or {}
        sol_obj = self.pool.get('sale.order.line')
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj = self.pool.get('sale.order')
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]

        sol_to_update = {}
        sol_not_to_delete_ids = []
        ir_to_potentialy_cancel_ids = []
        sol_of_po_line_resourced_ids = []

        so_to_cancel_ids = []
        for line in self.read(cr, uid, ids,
                              ['origin',
                               'product_qty',
                               'product_uom',
                               'has_to_be_resourced'],
                              context=context):
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, [line['id']], context=context)

            if not sol_ids and line['origin']:
                origin_ids = so_obj.search(cr, uid, [('name', '=', line['origin'])], context=context)
                for origin in so_obj.read(cr, uid, origin_ids, ['order_line'], context=context):
                    exp_sol_ids = exp_sol_obj.search(cr, uid, [('order_id', '=', origin['id']),
                                                               ('po_line_id', '!=', line['id'])],
                                                     limit=1, order='NO_ORDER', context=context)
                    if not origin['order_line'] and not exp_sol_ids:
                        so_to_cancel_ids.extend(origin_ids)

            line_qty = line['product_qty']
            if 'pol_qty' in context and line['id'] in context['pol_qty']:
                line_qty = context['pol_qty'].get(line['id'], 0.00)

            for sol in sol_obj.browse(cr, uid, sol_ids, context=context):
                diff_qty = uom_obj._compute_qty(cr, uid, line['product_uom'][0], line_qty, sol.product_uom.id)
                # In case of the product qty of the PO line is decrease before the cancelation, check if there
                # is some other PO lines related to this FO line, then cancel the whole line.
                if 'pol_qty' not in context and sol.procurement_id:
                    pol_ids = self.search(cr, uid, [('procurement_id', '=', sol.procurement_id.id)], context=context)
                    if len(pol_ids) == 1 and pol_ids[0] == line['id']:
                        diff_qty = sol.product_uom_qty

                sol_to_update.setdefault(sol.id, 0.00)
                sol_to_update[sol.id] += diff_qty
                if line['has_to_be_resourced']:
                    sol_obj.add_resource_line(cr, uid, sol, False, diff_qty, context=context)
                    sol_of_po_line_resourced_ids.append(sol.id)
                if sol.order_id.procurement_request:
                    # UFTP-82: do not delete IR line, cancel it
                    sol_not_to_delete_ids.append(sol.id)
                    if sol.order_id.id not in ir_to_potentialy_cancel_ids:
                        ir_to_potentialy_cancel_ids.append(sol.order_id.id)

        context['pol_ids'] = ids
        # In case of cancelation and resourcing from IN cancelation
        for sol in sol_to_update:
            context['update_or_cancel_line_not_delete'] = sol in sol_not_to_delete_ids
            if context.get('update_or_cancel_line_not_delete', False) or not context.get('from_in_cancel', False):
                so_to_cancel_id = sol_obj.update_or_cancel_line(cr, uid, sol, sol_to_update[sol], context=context)
                if so_to_cancel_id:
                    so_to_cancel_ids.append(so_to_cancel_id)

        del context['pol_ids']

        if context.get('update_or_cancel_line_not_delete', False):
            del context['update_or_cancel_line_not_delete']

        # UFTP-82: IR and its PO is cancelled
        # IR cancel all lines that have to be cancelled
        # and cancel IR if all its lines cancelled
        if ir_to_potentialy_cancel_ids:
            for ir in so_obj.browse(cr, uid, ir_to_potentialy_cancel_ids, context=context):
                # new IR state:
                # we change his state to 'cancel' if at least one line cancelled
                # we change his state to 'done' if all lines cancelled and resourced
                # else NO CHANGE
                ir_new_state = 'cancel'
                lines_to_cancel_ids = []
                all_lines_resourced = True

                # check if at least one line is cancelled
                # or all lines cancel and resourced
                for irl in ir.order_line:
                    line_cancelled = False
                    if ir.is_ir_from_po_cancel and \
                            (irl.state == 'cancel' or irl.state == 'exception'):
                        # note PO sourced from IR, IR cancelled line can be in 'exception' as a 'cancelled' one
                        line_cancelled = True
                        if irl.id not in sol_of_po_line_resourced_ids:
                            all_lines_resourced = False  # one cancelled line not resourced
                        if irl.state == 'exception':
                            lines_to_cancel_ids.append(irl.id)  # to be set to cancel
                    if not line_cancelled:
                        ir_new_state = False  # no cancelled line left, then no change
                if ir_new_state and all_lines_resourced:
                    # 'state change' flaged and all line resourced, state to done
                    ir_new_state = 'done'

                if lines_to_cancel_ids:
                    sol_obj.write(cr, uid, lines_to_cancel_ids,
                                  {'state': ir_new_state if ir_new_state else 'cancel'},
                                  context=context)
                if ir_new_state:
                    so_obj.write(cr, uid, ir.id,
                                 {'state': ir_new_state}, context=context)

        return so_to_cancel_ids

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        Add an entry to cancel (and resource if needed) the line when the
        PO will be confirmed
        '''
        proc_obj = self.pool.get('procurement.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        so_to_cancel = []

        proc_ids = []
        purchase_ids = []
        line_to_cancel = []

        for line in self.read(cr, uid, ids,
                              ['procurement_id',
                               'order_id',
                               'sync_order_line_db_id'],
                              context=context):
            # Set the procurement orders to delete
            # Set the list of linked purchase orders
            if line['procurement_id']:
                proc_ids.append(line['procurement_id'][0])
            if line['order_id'][0] not in purchase_ids:
                purchase_ids.append(line['order_id'][0])

            if not self.pool.get('sale.order.line.cancel').search(cr, uid, [
                ('sync_order_line_db_id', '=', line['sync_order_line_db_id']),
            ], limit=1, order='NO_ORDER', context=context):
                so_to_cancel = self.cancel_sol(cr, uid, [line['id']], context=context)

            # we want to skip resequencing because unlink is performed on merged purchase order lines
            tmp_Resequencing = context.get('skipResequencing', False)
            context['skipResequencing'] = True
            self._update_merged_line(cr, uid, line['id'], False, context=context)
            context['skipResequencing'] = tmp_Resequencing

            line_to_cancel.append(line['id'])

        # Cancel the listed procurement orders
        proc_id_to_cancel = set()
        for proc_id in proc_ids:
            if not self.search_exist(cr, uid, [
                ('order_id.state', '!=', 'split'),
                ('id', 'not in', ids),
                ('procurement_id', '=', proc_id)],
                    context=context):
                proc_id_to_cancel.add(proc_id)
        if proc_id_to_cancel:
            proc_obj.action_cancel(cr, uid, list(proc_id_to_cancel))

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        self.unlink(cr, uid, line_to_cancel, context=context)

        return so_to_cancel

    def unlink(self, cr, uid, ids, context=None):
        '''
        Update the merged line
        '''
        po_obj = self.pool.get('purchase.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        order_ids = []
        for line in self.read(cr, uid, ids, ['id', 'order_id'], context=context):
            tmp_skip_resourcing = context.get('skipResourcing', False)
            context['skipResourcing'] = True
            # we want to skip resequencing because unlink is performed on merged purchase order lines
            self._update_merged_line(cr, uid, line['id'], False, context=context)
            context['skipResourcing'] = tmp_skip_resourcing
            if line['order_id'][0] not in order_ids:
                order_ids.append(line['order_id'][0])

        if context.get('from_del_wizard'):
            return self.ask_unlink(cr, uid, ids, context=context)

        res = super(purchase_order_line, self).unlink(cr, uid, ids, context=context)

        for pol in self.read(cr, uid, ids, ['line_number'], context=context):
            self.infolog(cr, uid, "The PO/RfQ line id:%s (line number: %s) has been deleted" % (
                pol['id'], pol['name'],
            ))

        po_obj.wkf_confirm_trigger(cr, uid, order_ids, context=context)

        return res

    def _get_stages_price(self, cr, uid, product_id, uom_id, order, context=None):
        '''
        Returns True if the product/supplier couple has more than 1 line
        '''
        suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid,
                                                                    [('name', '=', order.partner_id.id),
                                                                     ('product_id', '=', product_id)],
                                                                    order='NO_ORDER', context=context)
        if suppinfo_ids:
            pricelist = self.pool.get('pricelist.partnerinfo').search(cr, uid,
                                                                      [('currency_id', '=',
                                                                        order.pricelist_id.currency_id.id),
                                                                       ('suppinfo_id', 'in', suppinfo_ids),
                                                                       ('uom_id', '=', uom_id),
                                                                       '|', ('valid_till', '=', False),
                                                                       ('valid_till', '>=', order.date_order)],
                                                                      limit=2, order='NO_ORDER', context=context)
            if len(pricelist) > 1:
                return True

        return False

    def on_change_select_fo(self, cr, uid, ids, fo_id, context=None):
        '''
        Fill the origin field if a FO is selected
        '''
        if fo_id:
            fo = self.pool.get('sale.order').read(cr, uid, fo_id, ['name', 'sourced_references'], context=context)
            return {
                'value': {
                    'origin': fo['name'], 
                    'display_sync_ref': len(fo['sourced_references']) and True or False,
                }
            }
        return {}

    def product_id_on_change(self, cr, uid, ids, pricelist, product, qty, uom,
                             partner_id, date_order=False, fiscal_position=False, date_planned=False,
                             name=False, price_unit=False, notes=False, state=False, old_price_unit=False,
                             nomen_manda_0=False, comment=False, context=None):
        all_qty = qty
        partner_price = self.pool.get('pricelist.partnerinfo')
        product_obj = self.pool.get('product.product')

        if not context:
            context = {}

        # If the user modify a line, remove the old quantity for the total quantity
        if ids:
            for line_id in self.read(cr, uid, ids, ['product_qty'], context=context):
                all_qty -= line_id['product_qty']

        if product and not uom:
            uom = self.pool.get('product.product').read(cr, uid, product, ['uom_id'])['uom_id'][0]

        if context and context.get('purchase_id') and state == 'draft' and product:
            domain = [('product_id', '=', product),
                      ('product_uom', '=', uom),
                      ('order_id', '=', context.get('purchase_id'))]
            other_lines = self.search(cr, uid, domain, order='NO_ORDER')
            for l in self.read(cr, uid, other_lines, ['product_qty']):
                all_qty += l['product_qty']

        res = self.product_id_change(cr, uid, ids, pricelist, product, all_qty, uom,
                                     partner_id, date_order, fiscal_position,
                                     date_planned, name, price_unit, notes)

        if res.get('warning', {}).get('title', '') == 'No valid pricelist line found !' or qty == 0.00:
            res.update({'warning': {}})

        func_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        if pricelist:
            currency_id = self.pool.get('product.pricelist').read(cr, uid, pricelist, ['currency_id'])['currency_id'][0]
        else:
            currency_id = func_curr_id

        if product and partner_id:
            # Test the compatibility of the product with a the partner of the order
            res, test = product_obj._on_change_restriction_error(cr, uid, product, field_name='product_id', values=res,
                                                                 vals={'partner_id': partner_id}, context=context)
            if test:
                return res

        # Update the old price value
        res['value'].update({'product_qty': qty})
        if product and not res.get('value', {}).get('price_unit', False) and all_qty != 0.00 and qty != 0.00:
            # Display a warning message if the quantity is under the minimal qty of the supplier
            currency_id = self.pool.get('product.pricelist').read(cr, uid, pricelist, ['currency_id'])['currency_id'][0]
            tmpl_id = self.pool.get('product.product').read(cr, uid, product, ['product_tmpl_id'])['product_tmpl_id'][0]
            info_prices = []
            suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid, [('name', '=', partner_id),
                                                                                  ('product_id', '=', tmpl_id)],
                                                                        context=context)
            domain = [('uom_id', '=', uom),
                      ('suppinfo_id', 'in', suppinfo_ids),
                      '|', ('valid_from', '<=', date_order),
                      ('valid_from', '=', False),
                      '|', ('valid_till', '>=', date_order),
                      ('valid_till', '=', False)]

            domain_cur = [('currency_id', '=', currency_id)]
            domain_cur.extend(domain)

            info_prices = partner_price.search(cr, uid, domain_cur, order='sequence asc, min_quantity asc, id desc',
                                               limit=1, context=context)
            if not info_prices:
                info_prices = partner_price.search(cr, uid, domain, order='sequence asc, min_quantity asc, id desc',
                                                   limit=1, context=context)

            if info_prices:
                info_price = partner_price.browse(cr, uid, info_prices[0], context=context)
                info_u_price = self.pool.get('res.currency').compute(cr, uid, info_price.currency_id.id, currency_id,
                                                                     info_price.price, round=False, context=context)
                res['value'].update({'old_price_unit': info_u_price, 'price_unit': info_u_price})
                res.update({'warning': {'title': _('Warning'), 'message': _('The product unit price has been set ' \
                                                                            'for a minimal quantity of %s (the min quantity of the price list), ' \
                                                                            'it might change at the supplier confirmation.') % info_price.min_quantity}})
                if info_price.rounding and all_qty % info_price.rounding != 0:
                    message = _('A rounding value of %s UoM has been set for ' \
                                'this product, you should than modify ' \
                                'the quantity ordered to match the supplier criteria.') % info_price.rounding
                    message = '%s \n %s' % (res.get('warning', {}).get('message', ''), message)
                    res['warning'].update({'message': message})
            else:
                old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id,
                                                                  res['value']['price_unit'], round=False,
                                                                  context=context)
                res['value'].update({'old_price_unit': old_price})
        else:
            old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id,
                                                              res.get('value').get('price_unit'), round=False,
                                                              context=context)
            res['value'].update({'old_price_unit': old_price})

        # Set the unit price with cost price if the product has no staged pricelist
        if product and qty != 0.00:
            res['value'].update({'comment': False, 'nomen_manda_0': False, 'nomen_manda_1': False,
                                 'nomen_manda_2': False, 'nomen_manda_3': False, 'nomen_sub_0': False,
                                 'nomen_sub_1': False, 'nomen_sub_2': False, 'nomen_sub_3': False,
                                 'nomen_sub_4': False, 'nomen_sub_5': False})
            product_result = product_obj.read(cr, uid, product, ['uom_id', 'standard_price'])
            st_uom = product_result['uom_id'][0]
            st_price = product_result['standard_price']
            st_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, st_price, round=False,
                                                             context=context)
            st_price = self.pool.get('product.uom')._compute_price(cr, uid, st_uom, st_price, uom)

            if res.get('value', {}).get('price_unit', False) == False and (state and state == 'draft') or not state:
                res['value'].update({'price_unit': st_price, 'old_price_unit': st_price})
            elif state and state != 'draft' and old_price_unit:
                res['value'].update({'price_unit': old_price_unit, 'old_price_unit': old_price_unit})

            if res['value']['price_unit'] == 0.00:
                res['value'].update({'price_unit': st_price, 'old_price_unit': st_price})

        elif qty == 0.00:
            res['value'].update({'price_unit': 0.00, 'old_price_unit': 0.00})
        elif not product and not comment and not nomen_manda_0:
            res['value'].update({'price_unit': 0.00, 'product_qty': 0.00, 'product_uom': False, 'old_price_unit': 0.00})

        if context and context.get('categ') and product:
            # Check consistency of product
            consistency_message = product_obj.check_consistency(cr, uid, product, context.get('categ'), context=context)
            if consistency_message:
                res.setdefault('warning', {})
                res['warning'].setdefault('title', 'Warning')
                res['warning'].setdefault('message', '')

                res['warning']['message'] = '%s \n %s' % (
                    res.get('warning', {}).get('message', ''), consistency_message)

        return res

    def price_unit_change(self, cr, uid, ids, fake_id, price_unit, product_id,
                          product_uom, product_qty, pricelist, partner_id, date_order,
                          change_price_ok, state, old_price_unit,
                          nomen_manda_0=False, comment=False, context=None):
        '''
        Display a warning message on change price unit if there are other lines with the same product and the same uom
        '''
        res = {'value': {}}

        if context is None:
            context = {}

        if not product_id or not product_uom or not product_qty:
            return res

        order_id = context.get('purchase_id', False)
        if not order_id:
            return res

        order = self.pool.get('purchase.order').browse(cr, uid, order_id, context=context)
        other_lines = self.search(cr, uid,
                                  [('id', '!=', fake_id),
                                   ('order_id', '=', order_id),
                                   ('product_id', '=', product_id),
                                   ('product_uom', '=', product_uom)],
                                  limit=1, order='NO_ORDER', context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        if not change_price_ok or (other_lines and stages and order.state != 'confirmed' and not context.get('rfq_ok')):
            res.update({'warning': {'title': 'Error',
                                    'message': 'This product get stages prices for this supplier, you cannot change the price manually in draft state ' \
                                               'as you have multiple order lines (it is possible in "validated" state.'}})
            res['value'].update({'price_unit': old_price_unit})
        else:
            res['value'].update({'old_price_unit': price_unit})

        return res

    def get_exp_sol_ids_from_pol_ids(self, cr, uid, ids, context=None, po_line=False):
        """
        input: purchase order line ids
        return: expected sale order line ids
        """
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj = self.pool.get('sale.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if po_line and isinstance(po_line, (int, long)):
            po_line = [po_line]

        so_name = []
        for line in self.read(cr, uid, ids, ['origin'], context=context):
            if line['origin'] and line['origin'] not in so_name:
                so_name.append(line['origin'])

        so_ids = so_obj.search(cr, uid, [('name', 'in', so_name)],
                               order='NO_ORDER', context=context)
        exp_sol_domain = [('order_id', 'in', so_ids)]
        if po_line:
            exp_sol_domain.append(('po_line_id', 'not in', po_line))

        return exp_sol_obj.search(cr, uid, exp_sol_domain, context=context)

    def get_sol_ids_from_pol_ids(self, cr, uid, ids, context=None):
        '''
        input: purchase order line ids
        return: sale order line ids
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sol_ids = set()
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.linked_sol_id:
                sol_ids.add(pol.linked_sol_id.id)

        return list(sol_ids)

    def open_split_wizard(self, cr, uid, ids, context=None):
        '''
        Open the wizard to split the line
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wizard = self.pool.get('split.purchase.order.line.wizard')
        for line in self.read(cr, uid, ids, ['product_qty'], context=context):
            data = {'purchase_line_id': line['id'], 'original_qty': line['product_qty'],
                    'old_line_qty': line['product_qty']}
            wiz_id = wizard.create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'split.purchase.order.line.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context}


    def create_or_update_commitment_voucher(self, cr, uid, ids, context=None):
        '''
        Update commitment voucher with current PO lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, context=context):
            # only create CV for external and ESC partners:
            if pol.order_id.partner_id.partner_type not in ['external', 'esc']:
                return False

            commitment_voucher_id = self.pool.get('account.commitment').search(cr, uid, [('purchase_id', '=', pol.order_id.id)], context=context)
            if commitment_voucher_id:
                commitment_voucher_id = commitment_voucher_id[0]
            else: # create commitment voucher
                commitment_voucher_id = self.pool.get('purchase.order').create_commitment_voucher_from_po(cr, uid, [pol.order_id.id], context=context)
            
            # group PO line by account_id:
            expense_account = pol.account_4_distribution and pol.account_4_distribution.id or False
            if not expense_account:
                raise osv.except_osv(_('Error'), _('There is no expense account defined for this line: %s (id:%d)') % (pol.name or '', pol.id))

            commit_line_id = self.pool.get('account.commitment.line').search(cr, uid, [('commit_id', '=', commitment_voucher_id), ('account_id', '=', expense_account), ], context=context)
            if not commit_line_id: # create new commitment line:
                commit_line_id = self.pool.get('account.commitment.line').create(cr, uid, {
                    'commit_id': commitment_voucher_id,
                    'account_id': expense_account,
                    'amount': pol.price_subtotal,
                    'initial_amount': pol.price_subtotal,
                    'purchase_order_line_ids': [(4, pol.id)],
                }, context=context)
            else: # update existing commitment line:
                commit_line_id = commit_line_id[0]
                new_amount = self.pool.get('account.commitment.line').read(cr, uid, commit_line_id, ['amount'], context=context)['amount'] 
                new_amount += pol.price_subtotal
                self.pool.get('account.commitment.line').write(cr, uid, [commit_line_id], {
                    'amount': new_amount,
                    'initial_amount': new_amount,
                    'purchase_order_line_ids': [(4, pol.id)], 
                }, 
                    context=context)

            # Create analytic distribution on this commitment line
            self.pool.get('account.commitment.line').create_distribution_from_order_line(cr, uid, [pol.id], context=context)

        return True


purchase_order_line()


class purchase_order_line_state(osv.osv):
    _name = "purchase.order.line.state"
    _description = "States of a purchase order line"

    _columns = {
        'name': fields.text(string='PO state', store=True),
        'sequence': fields.integer(string='Sequence'),
    }

    _sql_constraints = [
        ('sequence_uniq', 'unique(sequence)', 'PO line state sequence must be unique !'),
    ]

    def get_less_advanced_state(self, cr, uid, ids, states, context=None):
        '''
        Return the less advanced state of gives purchase order line states
        @param states: a list of string
        '''
        if not states:
            return False

        cr.execute("""
            SELECT name
            FROM purchase_order_line_state
            WHERE name IN %s
            ORDER BY sequence;
        """, (tuple(states),))

        min_state = cr.fetchone()

        return min_state[0] if min_state else False

        
    def get_sequence(self, cr, uid, ids, state, context=None):
        '''
        return the sequence of the given state
        @param state: the state's name as a string
        '''
        if not state:
            return False

        cr.execute("""
            SELECT sequence
            FROM purchase_order_line_state
            WHERE name = %s;
        """, (state,))
        sequence = cr.fetchone()

        return sequence[0] if sequence else False


purchase_order_line_state()
