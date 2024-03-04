# -*- coding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import netsvc
from osv import osv, fields
from tools.translate import _
from tools.misc import _get_std_mml_status
import decimal_precision as dp
from . import PURCHASE_ORDER_STATE_SELECTION
from . import PURCHASE_ORDER_LINE_STATE_SELECTION
from . import PURCHASE_ORDER_LINE_DISPLAY_STATE_SELECTION
from . import ORDER_TYPES_SELECTION
from msf_partner import PARTNER_TYPE
from lxml import etree


class purchase_order_line(osv.osv):
    _table = 'purchase_order_line'
    _name = 'purchase.order.line'
    _description = 'Purchase Order Line'

    _max_qty = 10**10
    _max_amount = 10**10
    _max_msg = _('The Total amount of the line is more than 10 digits. Please check that the Qty and Unit price are correct to avoid loss of exact information')

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if context.get('from_mismatch'):
            for arg in args:
                if arg[0] == 'order_id' and arg[2]:
                    self._compute_catalog_mismatch(cr, uid, order_id=arg[2], context=context)
        return super(purchase_order_line, self).search( cr, uid, args, offset, limit, order, context, count)

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''

        if context is None:
            context = {}
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        if vat_ok and 'purchase_id' in context:
            vat_ok = not self.pool.get('account.invoice.tax').search_exists(cr, uid, [('purchase_id', '=', context['purchase_id'])], context=context)

        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        if context.get('rfq_ok') and view_type == 'form':
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'rfq_line_form')[1]
        view = super(purchase_order_line, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            form = etree.fromstring(view['arch'])
            if context.get('partner_type', False) in ['internal', 'intermission', 'section'] and context.get('purchase_id')\
                    and self.pool.get('purchase.order').read(cr, uid, context['purchase_id'], context=context)['state'] in ['validated', 'validated_p']:
                form.attrib.update({'hide_new_button': '1'})
            if context.get('from_tab') != 1:
                for tag in form.xpath('//page[@name="nomenselection"]'):
                    tag.getparent().remove(tag)
                nb = form.xpath('//notebook')
                if nb:
                    nb[0].tag = 'empty'
            view['arch'] = etree.tostring(form, encoding='unicode')
        return view

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
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret

    def _get_fake_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, fields_to_fetch=['linked_sol_id'], context=context):
            if not pol.linked_sol_id:
                original_instance = self.pool.get('res.company')._get_instance_record(cr, uid).instance
            elif pol.linked_sol_id.original_instance:
                original_instance = pol.linked_sol_id.original_instance
            elif pol.linked_sol_id.order_id.partner_type in ('esc', 'external'):
                # FO FS to Ext
                original_instance = self.pool.get('res.company')._get_instance_record(cr, uid).instance
            else:
                # IR or FO from scratch to instance
                original_instance = pol.linked_sol_id.order_id.partner_id.name


            res[pol.id] = {
                'customer_ref': pol.linked_sol_id and pol.linked_sol_id.order_id.client_order_ref or False,
                'ir_name_for_sync': pol.linked_sol_id and pol.linked_sol_id.order_id.name or '',
                'original_instance': original_instance,
            }

        return res

    def _get_customer_name(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            return {}

        cr.execute('''
            select
                pol.id, p.name
            from
                purchase_order_line pol
            left join sale_order_line sol on pol.linked_sol_id = sol.id
            left join sale_order so on sol.order_id = so.id
            left join res_partner p on so.partner_id = p.id
            where
                pol.id in %s
        ''', (tuple(ids),))

        return dict(cr.fetchall())

    def _get_state_to_display(self, cr, uid, ids, field_name, args, context=None):
        '''
        return the purchase.order.line state to display
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            # if PO line has been created from ressourced process, then we display the state as 'Resourced-XXX' (excepted for 'done' status)
            if (pol.resourced_original_line or pol.set_as_resourced) and pol.state not in ['done', 'cancel', 'cancel_r']:
                if pol.state.startswith('validated'):
                    res[pol.id] = 'resourced_v'
                elif pol.state.startswith('sourced'):
                    if pol.state == 'sourced_v':
                        res[pol.id] = 'resourced_pv'
                    #elif pol.state == 'sourced_sy':
                    #    res[pol.id] = 'Resourced-sy'
                    else:
                        # debatable
                        res[pol.id] = 'resourced_s'
                elif pol.state.startswith('confirmed'):
                    res[pol.id] = 'resourced_c'
                else: # draft + unexpected PO line state
                    res[pol.id] = 'resourced_d'
            else: # state_to_display == state
                res[pol.id] = pol.state

        return res


    def _get_display_resourced_orig_line(self, cr, uid, ids, field_name, args, context=None):
        '''
        return the original PO line (from which the current one has been resourced) formatted as wanted
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for pol in self.browse(cr, uid, ids, context=context):
            res[pol.id] = False
            if pol.resourced_original_line:
                res[pol.id] = '%s' % (pol.resourced_original_line.line_number)

        return res

    def _get_stock_take_date(self, cr, uid, context=None):
        '''
            Returns stock take date
        '''
        if context is None:
            context = {}
        order_obj = self.pool.get('purchase.order')
        res = False

        if context.get('purchase_id', False):
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            res = po.stock_take_date

        return res

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
        order_obj = self.pool.get('purchase.order')
        res = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')

        if context.get('purchase_id', False):
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            res = po.delivery_requested_date
        return res

    def _check_changed(self, cr, uid, ids, name, arg, context=None):
        '''
        Check if an original value has been changed
        '''
        if context is None:
            context = {}
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            changed = False
            if line.modification_comment or line.created_by_sync or line.cancelled_by_sync \
                    or (line.original_qty and line.product_qty != line.original_qty) \
                    or (line.original_product and line.product_id and line.product_id.id != line.original_product.id):
                changed = True

            res[line.id] = changed
        return res

    def _get_default_state(self, cr, uid, context=None):
        '''
        default value for state fields.related

        why, beacause if we try to pass state in the context,
        the context is simply reset without any values specified...
        '''
        if context is None:
            context = {}
        if context.get('purchase_id', False):
            order_obj = self.pool.get('purchase.order')
            po = order_obj.browse(cr, uid, context.get('purchase_id'), context=context)
            return po.state

        return False

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for line in self.read(cr, uid, ids, ['analytic_distribution_id']):
            if line['analytic_distribution_id']:
                res[line['id']] = False
            else:
                res[line['id']] = True
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the purchase line, then "valid"
         - if no distribution, take a tour of purchase distribution, if compatible, then "valid"
         - if no distribution on purchase line and purchase, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        ana_dist_obj = self.pool.get('analytic.distribution')
        order_dict = {}
        order_obj = self.pool.get('purchase.order')
        for line in self.read(cr, uid, ids,
                              ['order_id', 'analytic_distribution_id', 'account_4_distribution'], context=context):
            order_id = line['order_id'] and line['order_id'][0] or False
            order = None
            if order_id:
                if order_id in order_dict:
                    order = order_dict[order_id]
                else:
                    order = order_obj.read(cr, uid, order_id, ['analytic_distribution_id'], context=context)
                    order_dict[order_id] = order
            if order and not order['analytic_distribution_id'] and not line['analytic_distribution_id']:
                res[line['id']] = 'none'
            else:
                po_distrib_id = order_id and order['analytic_distribution_id'] and order['analytic_distribution_id'][0] or False
                distrib_id = line['analytic_distribution_id'] and line['analytic_distribution_id'][0] or False
                account_id = line['account_4_distribution'] and line['account_4_distribution'][0] or False
                if not account_id:
                    res[line['id']] = 'invalid'
                    continue
                res[line['id']] = ana_dist_obj._get_distribution_state(cr, uid, distrib_id, po_distrib_id, account_id)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        get_sel = self.pool.get('ir.model.fields').get_selection
        for pol in self.read(cr, uid, ids, ['analytic_distribution_state', 'have_analytic_distribution_from_header']):
            d_state = get_sel(cr, uid, self._name, 'analytic_distribution_state', pol['analytic_distribution_state'], context)
            res[pol['id']] = "%s%s"%(d_state, pol['have_analytic_distribution_from_header'] and _(" (from header)") or "")
        return res

    def get_distribution_account(self, cr, uid, product_record, nomen_record, po_type, product_cache=None, categ_cache=None, context=None):
        if product_cache is None:
            product_cache = {}
        if categ_cache is None:
            categ_cache = {}

        a = False
        # To my mind there is 4 cases for a PO line (because of 2 criteria that affect account: "PO is inkind or not" and "line have a product or a nomenclature"):
        # - PO is an inkind donation AND PO line have a product: take donation expense account on product OR on product category, else raise an error
        # - PO is NOT inkind and PO line have a product: take product expense account OR category expense account
        # - PO is inkind but not PO Line product => this should not happens ! Should be raise an error but return False (if not we could'nt write a PO line)
        # - other case: take expense account on family that's attached to nomenclature
        if product_record and po_type =='in_kind':
            a = product_record.donation_expense_account and product_record.donation_expense_account.id or False
            if not a:
                a = product_record.categ_id.donation_expense_account and product_record.categ_id.donation_expense_account.id or False
        elif product_record:
            if product_record.product_tmpl_id in product_cache:
                a = product_cache[product_record.product_tmpl_id]
            else:
                a = product_record.product_tmpl_id.property_account_expense.id or False
                product_cache[product_record.product_tmpl_id] = a
            if not a:
                if product_record.categ_id in categ_cache:
                    a = categ_cache[product_record.categ_id]
                else:
                    a = product_record.categ_id.property_account_expense_categ.id or False
                    categ_cache[product_record.categ_id] = a
        else:
            a = nomen_record and nomen_record.category_id and nomen_record.category_id.property_account_expense_categ and nomen_record.category_id.property_account_expense_categ.id or False
        return a

    def _get_distribution_account(self, cr, uid, ids, name, arg, context=None):
        """
        Get account for given lines regarding:
        - product expense account if product_id
        - product category expense account if product_id but no product expense account
        - product category expense account if no product_id (come from family's product category link)
        """
        # Some verifications
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        product_tmpl_dict = {}
        categ_dict = {}
        for line in self.browse(cr, uid, ids):
            # Prepare some values
            res[line.id] = self.get_distribution_account(cr, uid, line.product_id, line.nomen_manda_2, line.order_id.order_type, product_cache=product_tmpl_dict, categ_cache=categ_dict, context=None)
        return res

    def _get_product_info(self, cr, uid, ids, field_name=None, arg=None, context=None):
        ret = {}
        for x in ids:
            ret[x] = {'heat_sensitive_item': False, 'cold_chain': False, 'controlled_substance': False, 'justification_code_id': False}


        ctrl_sub = dict(self.pool.get('product.product').fields_get(cr, uid, ['controlled_substance'], context=context).get('controlled_substance', {}).get('selection', []))
        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id'], context=context):
            ret[x.id] = {
                'heat_sensitive_item': x.product_id.heat_sensitive_item and x.product_id.heat_sensitive_item.code == 'yes' or False,
                'cold_chain': x.product_id.cold_chain and x.product_id.cold_chain.name or False,
                'controlled_substance': ctrl_sub.get(x.product_id.controlled_substance, False),
                'justification_code_id': x.product_id.justification_code_id and x.product_id.justification_code_id.code or False,
            }

        return ret

    def _in_qty_remaining(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            compute po qty - sum(IN cancel / cancel_r / done)
              in_qty_remaining: used for dpo (IN is not created when pol is confiremd
              regular_qty_remaining: used for regular flow
              regular_qty_available
        """
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')

        res = {}
        for pol in self.browse(cr, uid, ids, fields_to_fetch=['product_qty', 'product_uom', 'order_id'], context=context):
            move_processed_ids = move_obj.search(cr, uid, [('purchase_line_id', '=', pol.id), ('type', '=', 'in'), ('state', 'in', ['cancel', 'cancel_r', 'done'])], context=context)
            qty = pol.product_qty
            regular_qty_remaining = qty # already processed
            for move_processed in move_obj.browse(cr, uid, move_processed_ids, fields_to_fetch=['product_qty', 'product_uom', 'state'], context=context):
                move_qty = move_processed['product_qty']
                if move_processed.product_uom.id != pol.product_uom.id:
                    move_qty = uom_obj._compute_qty(cr, uid, move_processed.product_uom.id, move_processed['product_qty'], pol.product_uom.id)
                qty -= move_qty
                if move_processed['state'] == 'done':
                    regular_qty_remaining -= move_qty
            res[pol.id] = {'in_qty_remaining': qty}

            if context.get('sync_message_execution'):
                in_shipped_ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', '=', pol.order_id.id), ('state', '=', 'shipped')], context=context)
                if in_shipped_ids:
                    remaining_in_ids = move_obj.search(cr, uid, [('purchase_line_id', '=', pol.id), ('picking_id', 'in', in_shipped_ids), ('type', '=', 'in'), ('state', 'in', ['assigned', 'confirm'])], context=context)
                    for move_remaining in move_obj.browse(cr, uid, remaining_in_ids, fields_to_fetch=['product_qty', 'product_uom'], context=context):
                        if move_remaining.product_uom.id != pol.product_uom.id:
                            regular_qty_remaining -= uom_obj._compute_qty(cr, uid, move_remaining.product_uom.id, move_remaining.product_qty, pol.product_uom.id)
                        else:
                            regular_qty_remaining -= move_remaining.product_qty

            remaining_in_ids = move_obj.search(cr, uid, [('purchase_line_id', '=', pol.id), ('type', '=', 'in'), ('state', 'in', ['assigned', 'confirm'])], context=context)
            max_qty_cancellable = -regular_qty_remaining
            for move_remaining in move_obj.browse(cr, uid, remaining_in_ids, fields_to_fetch=['product_qty', 'product_uom'], context=context):
                if move_remaining.product_uom.id != pol.product_uom.id:
                    max_qty_cancellable += uom_obj._compute_qty(cr, uid, move_remaining.product_uom.id, move_remaining['product_qty'], pol.product_uom.id)
                else:
                    max_qty_cancellable += move_remaining['product_qty']

            res[pol.id]['regular_qty_remaining'] = regular_qty_remaining
            res[pol.id]['max_qty_cancellable'] = max_qty_cancellable
        return res


    def _compute_catalog_mismatch(self, cr, uid, order_id=None, pol_id=None, context=None):
        if order_id and pol_id or (not order_id and not pol_id):
            raise osv.except_osv(_('Error'), _('_compute_catalog_mismatch must be called with either order_id or pol_id set'))
        if order_id:
            cond = 'pol1.order_id in %s'
            if isinstance(order_id, int):
                order_id = [order_id]
            args = (tuple(order_id), )
        if pol_id:
            cond = 'pol1.id in %s'
            if isinstance(pol_id, int):
                pol_id = [pol_id]
            args = (tuple(pol_id), )
        print('Compute _compute_catalog_mismatch', args)
        cr.execute("""
            update purchase_order_line pol1 set catalog_mismatch=
                    case
                        when catl.catalogue_id is null then ''
                        when catl.id is null then 'na'
                        when abs(pol.price_unit - catl.cat_unit_price * coalesce(po_rate.rate,1) / coalesce(cat_rate.rate, 1)) > 0.0001 and (catl.soq_rounding=0 or pol.product_qty%%catl.soq_rounding=0) then 'price'
                        when abs(pol.price_unit - catl.cat_unit_price * coalesce(po_rate.rate,1) / coalesce(cat_rate.rate, 1)) > 0.0001 and catl.soq_rounding!=0 and pol.product_qty%%catl.soq_rounding!=0 then 'price_soq'
                        when catl.soq_rounding!=0 and pol.product_qty%%catl.soq_rounding!=0 then  'soq'
                        else 'conform'
                    end
            from purchase_order_line pol
                left join purchase_order po on po.id = pol.order_id
                left join product_pricelist curr_pricelist on curr_pricelist.id = po.pricelist_id
                left join lateral (
                    select
                        cat.id as catalogue_id, cat_line.id, cat.currency_id as cat_currency_id, cat_line.unit_price as cat_unit_price, cat_line.rounding as soq_rounding
                    from
                        supplier_catalogue cat
                        left join supplier_catalogue_line cat_line on cat_line.catalogue_id = cat.id and cat_line.product_id = pol.product_id and cat_line.line_uom_id = pol.product_uom
                    where
                        cat.partner_id = po.partner_id and
                        cat.active = 't' and
                        cat.state = 'confirmed' and
                        cat.period_from < NOW() and
                        (cat.period_to is null or cat.period_to > NOW()) and
                        coalesce(cat_line.min_qty,0) <= pol.product_qty
                    order by
                        cat.currency_id = curr_pricelist.currency_id, cat_line.min_qty desc, cat_line.id desc
                    limit 1
                ) catl on true
                left join lateral (
                    select
                        rate
                    from
                        res_currency_rate
                    where
                        currency_id = curr_pricelist.currency_id and
                        name <= NOW()
                    order by
                        name desc
                    limit 1
                ) po_rate on true
                left join lateral (
                    select
                        rate
                    from
                        res_currency_rate
                    where
                        currency_id = catl.cat_currency_id and
                        name <= NOW()
                    order by
                        name desc
                    limit 1
                ) cat_rate on true
            where
                """ + cond + """ and
                pol1.id = pol.id and
                pol.product_id is not null and
                pol.state not in ('confirmed', 'done', 'cancel', 'cancel_r')
        """, args) # not_a_user_entry

    _columns = {
        'block_resourced_line_creation': fields.boolean(string='Block resourced line creation', help='Set as true to block resourced line creation in case of cancelled-r line'),
        'set_as_sourced_n': fields.boolean(string='Set as Sourced-n', help='Line has been created further and has to be created back in preceding documents'),
        'set_as_validated_n': fields.boolean(string='Created when PO validated', help='Usefull for workflow transition to set the validated-n state'),
        'set_as_resourced': fields.boolean(string='Force resourced state'),
        'is_line_split': fields.boolean(string='This line is a split line?'),
        'original_line_id': fields.many2one('purchase.order.line', string='Original line', help='ID of the original line before split'),
        'linked_sol_id': fields.many2one('sale.order.line', string='Linked FO line', help='Linked Sale Order line in case of PO line from sourcing', readonly=True, select=1),
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
                                        string="Customer ref.", multi='custo_ref_ir_name'),
        'customer_name': fields.function(_get_customer_name, method=True, type='text', string='Customer Name'),
        'name': fields.char('Description', size=256, required=True),
        'product_qty': fields.float('Quantity', required=True, digits=(16, 2), related_uom='product_uom'),
        'taxes_id': fields.many2many('account.tax', 'purchase_order_taxe', 'ord_id', 'tax_id', 'Taxes'),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True, select=True),
        'product_id': fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', True)],
                                      change_default=True, select=True),
        'move_ids': fields.one2many('stock.move', 'purchase_line_id', 'Reservation', readonly=True,
                                    ondelete='set null'),
        'move_dest_id': fields.many2one('stock.move', 'Reservation Destination', ondelete='set null', select=True),
        'location_dest_id': fields.many2one('stock.location', 'Final Destination of move', ondelete='set null', select=True),
        'reception_dest_id': fields.many2one('stock.location', string='Line Destination', ondelete='set null', select=True),
        'price_unit': fields.float('Unit Price', required=True,
                                   digits_compute=dp.get_precision('Purchase Price Computation'), en_thousand_sep=False),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False,
                                  readonly=True),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal',
                                          digits_compute=dp.get_precision('Purchase Price')),
        'notes': fields.text('Notes'),
        'order_id': fields.many2one('purchase.order', 'Order Reference', select=True, required=True,
                                    ondelete='cascade', join=True),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic Account'),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, readonly=True),
        'state': fields.selection(PURCHASE_ORDER_LINE_STATE_SELECTION, 'State', required=True, readonly=True, select=1,
                                  help=' * The \'Draft\' state is set automatically when purchase order in draft state. \
                                       \n* The \'Confirmed\' state is set automatically as confirm when purchase order in confirm state. \
                                       \n* The \'Done\' state is set automatically when purchase order is set as done. \
                                       \n* The \'Cancelled\' state is set automatically when user cancel purchase order.'),
        'state_to_display': fields.function(_get_state_to_display, string='State', type='selection', selection=PURCHASE_ORDER_LINE_DISPLAY_STATE_SELECTION, method=True, readonly=True,
                                            help=' * The \'Draft\' state is set automatically when purchase order in draft state. \
               \n* The \'Confirmed\' state is set automatically as confirm when purchase order in confirm state. \
               \n* The \'Done\' state is set automatically when purchase order is set as done. \
               \n* The \'Cancelled\' state is set automatically when user cancel purchase order.'
                                            ),
        'resourced_original_line': fields.many2one('purchase.order.line', 'Original line', readonly=True, help='Original line from which the current one has been cancel and ressourced'),
        'display_resourced_orig_line': fields.function(_get_display_resourced_orig_line, method=True, type='char', readonly=True, string='Original PO line', help='Original line from which the current one has been cancel and ressourced'),
        'invoice_lines': fields.many2many('account.invoice.line', 'purchase_order_line_invoice_rel', 'order_line_id',
                                          'invoice_id', 'Invoice Lines', readonly=True),
        'invoiced': fields.boolean('Invoiced', readonly=True),
        'partner_id': fields.related('order_id','partner_id',string='Partner',readonly=True,type="many2one", relation="res.partner", store=True),
        'date_order': fields.related('order_id','date_order',string='Order Date',readonly=True,type="date"),
        'stock_take_date': fields.date(string='Date of Stock Take', required=False),
        'date_planned': fields.date(string='Requested DD', required=True, select=True,
                                    help='Header level dates has to be populated by default with the possibility of manual updates'),
        'esti_dd': fields.date(string='Estimated DD', select=True,
                               help='Header level dates has to be populated by default with the possibility of manual updates'),
        'confirmed_delivery_date': fields.date(string='Confirmed DD',
                                               help='Header level dates has to be populated by default with the possibility of manual updates.'),
        # not replacing the po_state from sale_followup - should ?
        'po_state_stored': fields.related('order_id', 'state', type='selection', selection=PURCHASE_ORDER_STATE_SELECTION, string='Po State', readonly=True,),
        'po_partner_type_stored': fields.related('order_id', 'partner_type', type='selection', selection=PARTNER_TYPE, string='Po Partner Type', readonly=True,),
        'po_order_type': fields.related('order_id', 'order_type', type='selection', selection=ORDER_TYPES_SELECTION, string='Po Order Type', readonly=True, write_relate=False),
        'original_product': fields.many2one('product.product', 'Original Product'),
        'original_qty': fields.float('Original Qty', related_uom='original_uom'),
        'original_price': fields.float('Original Price', digits_compute=dp.get_precision('Purchase Price Computation')),
        'original_uom': fields.many2one('product.uom', 'Original UoM'),
        'original_currency_id': fields.many2one('res.currency', 'Original Currency'),
        'modification_comment': fields.char('Modification Comment', size=1024),
        'original_changed': fields.function(_check_changed, method=True, string='Changed', type='boolean'),
        'from_synchro_return_goods': fields.boolean(string='PO Line created by synch of IN replacement/missing'),
        'esc_confirmed': fields.boolean(string='ESC confirmed'),
        'created_by_sync': fields.boolean(string='Created by Synchronisation'),
        'cancelled_by_sync': fields.boolean(string='Cancelled by Synchronisation'),

        # finance
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', string='Header Distrib.?'),
        # for CV in version 1
        'commitment_line_ids': fields.many2many('account.commitment.line', 'purchase_line_commitment_rel', 'purchase_id', 'commitment_id',
                                                string="Commitment Voucher Lines (deprecated)", readonly=True),
        # for CV starting from version 2
        # note: cv_line_ids is a o2m because of the related m2o on CV lines but it should only contain one CV line
        'cv_line_ids': fields.one2many('account.commitment.line', 'po_line_id', string="Commitment Voucher Lines"),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30, string="Distribution"),
        'account_4_distribution': fields.function(_get_distribution_account, method=True, type='many2one', relation="account.account", string="Account for analytical distribution", readonly=True),
        'created_by_vi_import': fields.boolean('Line created by VI PO import'),

        'heat_sensitive_item': fields.function(_get_product_info, type='boolean', string='Temperature sensitive item', multi='product_info', method=True),
        'cold_chain': fields.function(_get_product_info, type='char', string='Cold Chain', multi='product_info', method=True),
        'controlled_substance': fields.function(_get_product_info, type='char', string='Controlled Substance', multi='product_info', method=True),
        'justification_code_id': fields.function(_get_product_info, type='char', string='Justification Code', multi='product_info', method=True),
        'create_date': fields.date('Creation date', readonly=True),
        'validation_date': fields.date('Validation Date', readonly=True),
        'confirmation_date': fields.date('Confirmation Date', readonly=True),
        'closed_date': fields.date('Closed Date', readonly=True),
        'ir_name_for_sync': fields.function(_get_customer_ref, type='char', size=64, string='IR/FO name to put on PO line after sync', multi='custo_ref_ir_name', method=1),
        'in_qty_remaining': fields.function(_in_qty_remaining, type='float', string='Qty remaining on IN', method=1, multi='in_remain'),
        'regular_qty_remaining': fields.function(_in_qty_remaining, type='float', string='Total PO qty - already processed', method=1, multi='in_remain'),
        'max_qty_cancellable': fields.function(_in_qty_remaining, type='float', string='Total PO qty - already processed + assign qty + confirm qty', method=1, multi='in_remain'),
        'from_dpo_line_id': fields.integer('DPO line id on the remote', internal=1),
        'from_dpo_id': fields.integer('DPO id on the remote', internal=1),
        'from_dpo_esc': fields.boolean('Line sourced to ESC DPO', internal=1),
        'dates_modified': fields.boolean('EDD/CDD modified on validated line', internal=1),
        'loan_line_id': fields.many2one('sale.order.line', string='Linked loan line', readonly=True),
        'original_instance': fields.function(_get_customer_ref, method=True, type='char', string='Original Instance', multi='custo_ref_ir_name'),

        'mml_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MML', multi='mml'),
        'msl_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MSL', multi='mml'),

        'catalog_mismatch': fields.selection([('conform', 'Conform'), ('na', 'N/A'),('soq', 'SOQ') ,('price', 'Unit Price'), ('price_soq', 'Unit Price & SOQ')], 'Catalog Mismatch', size=64, readonly=1, select=1),
    }

    _defaults = {
        'set_as_sourced_n': lambda *a: False,
        'set_as_validated_n': lambda *a: False,
        'block_resourced_line_creation': lambda *a: False,
        'change_price_manually': lambda *a: False,
        'product_qty': lambda *a: 0,
        'price_unit': lambda *a: 0.00,
        'change_price_ok': lambda *a: True,
        'is_line_split': False,  # UTP-972: by default not a split line
        'from_fo': lambda self, cr, uid, c: not c.get('rfq_ok', False) and c.get('from_fo', False),
        'soq_updated': False,
        'state': lambda *args: 'draft',
        'invoiced': lambda *a: 0,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'stock_take_date': _get_stock_take_date,
        'po_state_stored': _get_default_state,
        'po_partner_type_stored': lambda obj, cr, uid, c: c and c.get('partner_type', False),
        'date_planned': _get_planned_date,
        'confirmed_delivery_date': False,
        'have_analytic_distribution_from_header': lambda *a: True,
        'created_by_vi_import': False,
        'created_by_sync': False,
        'cancelled_by_sync': False,
        'mml_status': 'na',
        'msl_status': 'na',
        'catalog_mismatch': '',
    }

    def _check_max_price(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        msg = _('The Total amount of the following lines is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed')
        error = []
        for pol in self.browse(cr, uid, ids, context=context):
            max_digits = 27
            if pol.product_qty >= 10**(max_digits-2):
                error.append('%s #%s' % (pol.order_id.name, pol.line_number))
            else:
                total_int = int(pol.product_qty * pol.price_unit)

                nb_digits_allowed = max_digits - 2

                if len(str(total_int)) > nb_digits_allowed:
                    error.append('%s #%s' % (pol.order_id.name, pol.line_number))

        if error:
            raise osv.except_osv(_('Error'), '%s: %s' % (msg, ' ,'.join(error)))

        return True

    _constraints = [
        (_check_max_price, _("The Total amount of the following lines is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed"), ['price_unit', 'product_qty']),
    ]

    def _check_stock_take_date(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Do not prevent modification during synchro
        if not context.get('from_vi_import') and not context.get('sync_update_execution') and not context.get('sync_message_execution') and 'cancel_only' not in context:
            error_lines = []
            linked_orders = []
            for pol in self.browse(cr, uid, ids, context=context):
                linked_order = pol.order_id.name
                if linked_order not in linked_orders:
                    linked_orders.append(linked_order)
                if pol.state in ['draft', 'validated', 'validated_n'] and pol.stock_take_date and \
                        pol.stock_take_date > pol.order_id.date_order:
                    error_lines.append(str(pol.line_number))
                if len(error_lines) >= 10:  # To not display too much
                    break
            if error_lines:
                raise osv.except_osv(
                    _('Error'), _('The Stock Take Date of the lines %s is not consistent! It should not be later than %s\'s creation date')
                    % (', '.join(error_lines), linked_orders and ', '.join(linked_orders) or _('the PO'))
                )

        return True

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

    def check_analytic_distribution(self, cr, uid, ids, context=None, create_missing=False):
        """
        Check analytic distribution validity for given PO line.
        Also check that partner have a donation account (is PO is in_kind)

        create_missing: deprecated, used in pre-SLL intermission push flow (US-3017)
        """
        # Objects
        ad_obj = self.pool.get('analytic.distribution')
        ccdl_obj = self.pool.get('cost.center.distribution.line')
        pol_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        po_info = {}
        for pol in self.browse(cr, uid, ids, context=context):
            po = pol.order_id
            if po.id not in po_info:
                donation_intersection = po.order_type in ['donation_exp', 'donation_st'] and po.partner_type and po.partner_type == 'section'
                if po.order_type == 'in_kind' or donation_intersection:
                    if not po.partner_id.donation_payable_account:
                        raise osv.except_osv(_('Error'), _('No donation account on this partner: %s') % (po.partner_id.name or '',))

            po_info[po.id] = True


            distrib = pol.analytic_distribution_id or po.analytic_distribution_id or False

            # Raise an error if no analytic distribution found
            if not distrib:
                # UFTP-336: For the case of a new line added from Coordo, it's a push flow, no need to check the AD! VERY SPECIAL CASE
                if po.order_type in ('loan', 'loan_return', 'donation_st', 'donation_exp', 'in_kind') or po.push_fo:
                    return True
                raise osv.except_osv(_('Warning'), _('Analytic allocation is mandatory for %s on the line %s for the product %s! It must be added manually.')
                                     % (pol.order_id.name, pol.line_number, pol.product_id and pol.product_id.default_code or pol.name or ''))

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
                line_ids_to_write = [line.id for line in ad_lines if line.partner_type != pol.order_id.partner_id.partner_type]
                ccdl_obj.write(cr, uid, line_ids_to_write, {
                    'partner_type': pol.order_id.partner_id.partner_type,
                })


            # check that the analytic accounts are active. Done at the end to use the newest AD of the pol (to re-browse)
            if po.partner_id.partner_type in ('section', 'intermission', 'internal') and \
                    ( pol.state in ('validated', 'sourced_sy', 'sourced_v') or pol.state == 'draft' and pol.created_by_sync):
                # do not check on po line confirmation from instance
                continue

            pol_ad = self.browse(cr, uid, pol.id, fields_to_fetch=['analytic_distribution_id'], context=context).analytic_distribution_id
            ad = pol_ad or po.analytic_distribution_id or False
            if ad:
                if pol_ad:
                    prefix = _("Analytic Distribution on line %s:\n") % pol.line_number
                else:
                    prefix = _("Analytic Distribution at header level:\n")
                ad_obj.check_cc_distrib_active(cr, uid, ad, prefix=prefix, from_supply=True)
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
            return {'value': {
                'price_unit': price_unit or 0.0,
                'name': name or '',
                'notes': notes or '',
                'product_uom': uom or False,
                'heat_sensitive_item': False,
                'cold_chain': False,
                'controlled_substance': False,
                'justification_code_id': False
            },
                'domain': {'product_uom': []}
            }
        res = {}
        lang = self.pool.get('res.users').browse(cr, uid, uid).context_lang
        prod = self.pool.get('product.product').browse(cr, uid, product, context={'lang': lang})
        ctrl_sub = dict(self.pool.get('product.product').fields_get(cr, uid, ['controlled_substance'], context={'lang': lang}).get('controlled_substance', {}).get('selection', []))
        value = {
            'heat_sensitive_item': prod.heat_sensitive_item and prod.heat_sensitive_item.code == 'yes' or False,
            'cold_chain': prod.cold_chain and prod.cold_chain.name or False,
            'controlled_substance': ctrl_sub.get(prod.controlled_substance, False),
            'justification_code_id': prod.justification_code_id and prod.justification_code_id.code or False,
        }

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
        dt = (datetime.now() + relativedelta(days=int(seller_delay) or 0.0)).strftime('%Y-%m-%d %H:%M:%S')

        if price:
            value['price_unit'] = price

        value.update({
            'name': prod_name,
            'taxes_id': [x.id for x in prod.supplier_taxes_id],
            'date_planned': date_planned or dt, 'notes': notes or prod.description_purchase,
            'product_qty': qty,
            'product_uom': uom,
        })
        res.update({'value': value})
        domain = {}

        taxes = self.pool.get('account.tax').browse(cr, uid, [x.id for x in prod.supplier_taxes_id])
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
        if isinstance(ids, int):
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

        order_id = vals.get('order_id')
        product_id = vals.get('product_id')
        product_uom = vals.get('product_uom')
        order = po_obj.browse(cr, uid, order_id, context=context)

        # if the PO line has been created when PO has status "validated" then new PO line gets specific state "validated-n" to mark the
        # line as non-really validated. It avoids the PO to go back in draft state.
        if order.state.startswith('validated') and not vals.get('is_line_split', False):
            vals.update({'set_as_validated_n': True})

        # Update the name attribute if a product is selected
        self._update_name_attr(cr, uid, vals, context=context)

        # If we are on a RfQ, use the last entered unit price and update other lines with this price
        if order.rfq_ok:
            vals.update({'change_price_manually': True})
        else:
            if order.po_from_fo or order.po_from_ir or vals.get('link_so_id', False):
                vals['from_fo'] = True
            else:
                # duplication of PO from fo must not set this value
                vals['from_fo'] = False
            if vals.get('product_qty', 0.00) == 0.00 and not context.get('noraise'):
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

        other_lines = self.search(cr, uid, [('order_id', '=', order_id),
                                            ('product_id', '=', product_id), ('product_uom', '=', product_uom)],
                                  limit=1, order='NO_ORDER', context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        # try to fill "link_so_id" if not in vals:
        if not vals.get('link_so_id'):
            linked_so = False
            if vals.get('linked_sol_id'):
                sol_data = self.pool.get('sale.order.line').read(cr, uid, vals.get('linked_sol_id'), ['order_id'])
                linked_so = sol_data['order_id'] and sol_data['order_id'][0] or False
                vals.update({'link_so_id': linked_so})
            elif vals.get('origin'):
                vals.update(self.update_origin_link(cr, uid, vals.get('origin'), po_obj=order, context=context))

        if (other_lines and stages and order.state != 'confirmed'):
            context.update({'change_price_ok': False})

        # if not context.get('offline_synchronization'):
        #     vals = self._update_merged_line(cr, uid, False, vals, context=dict(context, skipResequencing=True))

        vals.update({'old_price_unit': vals.get('price_unit', False)})

        if vals.get('price_unit') and not vals.get('original_price'):
            vals.update({'original_price': vals['price_unit'] or 0.00})

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

        # utp-518:we write the comment from the sale.order.line on the PO line:
        if vals.get('linked_sol_id'):
            sol_comment = self.pool.get('sale.order.line').read(cr, uid, vals.get('linked_sol_id'), ['comment'], context=context)['comment']
            vals.update({'comment': sol_comment})
            #if not product_id and not vals.get('name'):  # US-3530
            #    vals.update({'name': 'None'})

        vals['reception_dest_id'] = self.get_reception_dest(cr, uid, vals, context=context)

        # add the database Id to the sync_order_line_db_id
        po_line_id = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False):  # 'sync_order_line_db_id' not in vals or vals:
            name = order.name
            super(purchase_order_line, self).write(cr, uid, [po_line_id],
                                                   {'sync_order_line_db_id': name + "_" + str(po_line_id), },
                                                   context=context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, po_line_id, context=context)

        if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('linked_sol_id'):
            so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], context=context)
            for so_id in so_ids:
                self.pool.get('expected.sale.order.line').create(cr, 1, {
                    'order_id': so_id,
                    'po_line_id': po_line_id,
                }, context=context)

        return po_line_id

    def copy(self, cr, uid, line_id, defaults=None, context=None):
        '''
        Remove link to merged line
        '''

        if defaults is None:
            defaults = {}

        defaults.update({
            'merged_id': False,
            'sync_order_line_db_id': False,
            'linked_sol_id': False,
            'set_as_sourced_n': False,
            'set_as_validated_n': False,
            'esc_confirmed': False,
            'created_by_sync': False,
            'cancelled_by_sync': False,
            'from_dpo_line_id': False,
            'dates_modified': False,
            'catalog_mismatch': '',
        })

        return super(purchase_order_line, self).copy(cr, uid, line_id, defaults, context=context)

    def copy_data(self, cr, uid, p_id, default=None, context=None):
        """
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}


        default['from_dpo_line_id'] = False
        # do not copy canceled purchase.order.line:
        pol = self.browse(cr, uid, p_id, fields_to_fetch=['state', 'order_id', 'linked_sol_id', 'product_id'], context=context)
        if pol.state in ['cancel', 'cancel_r'] and not context.get('allow_cancelled_pol_copy', False):
            return False
        if pol.product_id:  # Check constraints on lines
            self.pool.get('product.product')._get_restriction_error(cr, uid, [pol.product_id.id],
                                                                    {'partner_id': pol.order_id.partner_id.id}, context=context)

        default.update({'state': 'draft', 'move_ids': [], 'invoiced': 0, 'invoice_lines': [], 'commitment_line_ids': [], 'cv_line_ids': [], 'dates_modified': False, 'rfq_line_state': 'draft'})

        for field in ['origin', 'move_dest_id', 'original_product', 'original_qty', 'original_price', 'original_uom', 'original_currency_id', 'modification_comment', 'sync_linked_sol', 'created_by_vi_import', 'external_ref', 'catalog_mismatch']:
            if field not in default:
                default[field] = False

        default.update({'sync_order_line_db_id': False, 'set_as_sourced_n': False, 'set_as_validated_n': False, 'linked_sol_id': False, 'link_so_id': False, 'esc_confirmed': False, 'created_by_sync': False, 'cancelled_by_sync': False, 'resourced_original_line': False, 'set_as_resourced': False})

        if not context.get('split_line'):
            default.update({'stock_take_date': False, 'loan_line_id': False})
            if 'location_dest_id' not in default:
                default['location_dest_id'] = False
            if 'reception_dest_id' not in default:
                default['reception_dest_id'] = False

        # from RfQ line to PO line: grab the linked sol if has:
        if pol.order_id.rfq_ok and context.get('generate_po_from_rfq', False):
            default.update({'linked_sol_id': pol.linked_sol_id and pol.linked_sol_id.id or False})

        if not context.get('keepDateAndDistrib'):
            if 'confirmed_delivery_date' not in default:
                default['confirmed_delivery_date'] = False
            if 'date_planned' not in default:
                default['date_planned'] = (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d')
            if 'analytic_distribution_id' not in default:
                default['analytic_distribution_id'] = False
            if 'esti_dd' not in default:
                default['esti_dd'] = False

        if default.get('analytic_distribution_id'):
            default['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, default['analytic_distribution_id'], {}, context=context)


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

        if isinstance(ids, int):
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

        if ('state' in vals and vals.get('state') != 'draft') or ('linked_sol_id' in vals and vals.get('linked_sol_id')):
            exp_sol_ids = exp_sol_obj.search(cr, uid, [('po_line_id', 'in', ids)],
                                             order='NO_ORDER', context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        # Remove SoQ updated flag in case of manual modification
        if not 'soq_updated' in vals:
            vals['soq_updated'] = False

        check_location_dest_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            new_vals = vals.copy()
            # check qty
            if vals.get('product_qty', line.product_qty) <= 0.0 and not line.order_id.rfq_ok and 'noraise' not in context and \
                    line.state != 'cancel' and context.get('button', '') != 'cancel_only_pol' and vals.get('state', '') != 'cancel':
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

            if 'product_id' in vals and line.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and line.product_id.id != vals.get('product'):
                check_location_dest_ids.append(line.id)

            # try to fill "link_so_id":
            if not line.link_so_id and not vals.get('link_so_id'):
                linked_so = False
                if vals.get('linked_sol_id', line.linked_sol_id):
                    sol_data = self.pool.get('sale.order.line').read(cr, uid, vals.get('linked_sol_id', line.linked_sol_id.id), ['order_id'])
                    linked_so = sol_data['order_id'] and sol_data['order_id'][0] or False
                    new_vals.update({'link_so_id': linked_so})
                elif vals.get('origin'):
                    new_vals.update(self.update_origin_link(cr, uid, vals.get('origin'), po_obj=line.order_id, context=context))

            if line.state in ('validated', 'validated_n', 'sourced_v', 'sourced_n') and \
                    line.linked_sol_id and \
                    not line.linked_sol_id.order_id.procurement_request and \
                    line.linked_sol_id.order_id.partner_type not in ('external', 'esc') and \
                    ('esti_dd' in vals and vals['esti_dd'] != line.esti_dd or 'confirmed_delivery_date' in vals and vals['confirmed_delivery_date'] != line.confirmed_delivery_date):
                new_vals['dates_modified'] = True

            if line.order_id and not line.order_id.rfq_ok and (line.order_id.po_from_fo or line.order_id.po_from_ir):
                new_vals['from_fo'] = True

            # if not context.get('update_merge'):
            #     new_vals.update(self._update_merged_line(cr, uid, line.id, vals, context=dict(context, skipResequencing=True, noraise=True)))

            if line.state == 'draft' and 'price_unit' in new_vals:
                new_vals['original_price'] = new_vals.get('price_unit')

            new_vals['reception_dest_id'] = self.get_reception_dest(cr, uid, new_vals, pol=line, context=context)

            res = super(purchase_order_line, self).write(cr, uid, [line.id], new_vals, context=context)

            if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('linked_sol_id', line.linked_sol_id):
                so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], order='NO_ORDER', context=context)
                for so_id in so_ids:
                    exp_sol_obj.create(cr, uid, {
                        'order_id': so_id,
                        'po_line_id': line.id,
                    }, context=context)

        for line in self.browse(cr, uid, check_location_dest_ids, context=context):
            super(purchase_order_line, self).write(cr, uid, [line.id], {'location_dest_id': self.final_location_dest(cr, uid, line, context=context)}, context=context)


        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, ids, context=context)

        # Check the selected product UoM
        if not context.get('import_in_progress', False):
            for pol_read in self.read(cr, uid, ids, ['product_id', 'product_uom']):
                if pol_read.get('product_id'):
                    product_id = pol_read['product_id'][0]
                    uom_id = pol_read['product_uom'][0]
                    self._check_product_uom(cr, uid, product_id, uom_id, context=context)

        return res

    def update_origin_link(self, cr, uid, origin, po_obj=None, context=None):
        '''
        Return the FO/IR that matches with the origin value
        '''
        tmp_proc_context = context.get('procurement_request')
        context['procurement_request'] = True
        so_ids = self.pool.get('sale.order').search(cr, uid, [
            ('name', '=', origin),
            ('state', 'not in', ['done', 'cancel']),
        ], context=context)
        context['procurement_request'] = tmp_proc_context

        if so_ids:
            if po_obj and (not po_obj.origin or origin not in po_obj.origin):
                if po_obj.origin:
                    new_po_origin = '%s:%s' % (po_obj.origin, origin)
                else:
                    new_po_origin = origin
                to_write = {'origin': new_po_origin}
                so_data = self.pool.get('sale.order').browse(cr, uid, so_ids[0], fields_to_fetch=['partner_id', 'procurement_request'], context=context)
                if not so_data.procurement_request:
                    to_write['dest_partner_ids'] = [(4, so_data.partner_id.id)]
                self.pool.get('purchase.order').write(cr, uid, [po_obj.id], to_write, context=context)
            return {'link_so_id': so_ids[0]}
        return {}

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Method to cancel a PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
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


    def unlink(self, cr, uid, ids, context=None):
        '''
        Update the merged line
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
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

        res = super(purchase_order_line, self).unlink(cr, uid, ids, context=context)

        for pol in self.read(cr, uid, ids, ['line_number'], context=context):
            self.infolog(cr, uid, "The PO/RfQ line id:%s (line number: %s) has been deleted" % (
                pol['id'], pol['name'],
            ))

        return res

    def cancel_partial_qty(self, cr, uid, ids, cancel_qty, resource=False, context=None):
        '''
        allow to cancel a PO line partially: split the line then cancel the new splitted line
        and update linked FO/IR lines if has
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        wf_service = netsvc.LocalService("workflow")

        if cancel_qty <= 0:
            return False

        for pol in self.browse(cr, uid, ids, context=context):
            # split the PO line:
            split_obj = self.pool.get('split.purchase.order.line.wizard')
            split_id = split_obj.create(cr, uid, {
                'purchase_line_id': pol.id,
                'original_qty': pol.product_qty,
                'old_line_qty': pol.product_qty - cancel_qty,
                'new_line_qty': cancel_qty,
            }, context=context)
            context.update({'return_new_line_id': True, 'keepLineNumber': True, 'cancel_only': not resource})
            new_po_line = split_obj.split_line(cr, uid, [split_id], context=context)
            context.pop('return_new_line_id')
            context.pop('keepLineNumber')

            # udpate linked FO lines if has:
            self.write(cr, uid, [new_po_line], {'origin': pol.origin}, context=context) # otherwise not able to link with FO
            pol_to_update = [pol.id]
            if pol.linked_sol_id:
                pol_to_update += [new_po_line]
            self.update_fo_lines(cr, uid, pol_to_update, context=context, qty_updated=True)

            # cancel the new split PO line:
            signal = 'cancel_r' if resource else 'cancel'
            wf_service.trg_validate(uid, 'purchase.order.line', new_po_line, signal, cr)
            context.pop('cancel_only')

        return new_po_line

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

    def check_is_service_nomen(self, cr, uid, nomen=False):
        """
        Return True if the nomenclature selected on the line is a service nomenclature
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if not nomen:
            return False

        nomen_srv = nomen_obj.search(cr, uid, [
            ('name', '=', 'SRV'),
            ('type', '=', 'mandatory'),
            ('level', '=', 0),
        ], limit=1)
        if not nomen_srv:
            return False

        return nomen_srv[0] == nomen

    msg_selected_po = _("Please ensure that you selected the correct Source document because once the line is saved you will not be able to edit this field anymore. In case of mistake, the only option will be to Cancel the line and Create a new one with the correct Source document.")

    def on_change_select_fo(self, cr, uid, ids, fo_id, product_id, po_order_type, nomen_manda_0, rfq_ok, context=None):
        '''
        Fill the origin field if a FO is selected
        '''
        if fo_id:
            fo_domain = ['name', 'sourced_references', 'state', 'order_type', 'procurement_request']
            fo = self.pool.get('sale.order').read(cr, uid, fo_id, fo_domain, context=context)
            if fo['state'] not in ['done', 'cancel']:
                if not fo['procurement_request'] and po_order_type in ['regular', 'purchase_list'] and product_id and not rfq_ok and\
                        self.pool.get('product.product').read(cr, uid, product_id, ['type'])['type'] == 'service_recep':
                    return {'warning': {'title': _('Error'),
                                        'message': _('A Service Product can not be linked to a FO on a Regular or a Purchase List PO')},
                            'value': {'origin': False}}
                elif not product_id and po_order_type in ['regular', 'purchase_list'] and not fo['procurement_request'] \
                        and not rfq_ok and self.check_is_service_nomen(cr, uid, nomen_manda_0):
                    return {'warning': {'title': _('Error'),
                                        'message': _('You can not link a Product by Nomenclature with SRV as Nomenclature Main Type to a FO on a Regular or a Purchase List PO')},
                            'value': {'origin': False}}
                elif fo['order_type'] == 'regular':
                    return {
                        'value': {
                            'origin': fo['name'],
                            'display_sync_ref': len(fo['sourced_references']) and True or False,
                        },
                        'warning': {
                            'message': _(self.msg_selected_po),
                        }
                    }
        return {}

    def on_change_origin(self, cr, uid, ids, origin, linked_sol_id=False, partner_type='external', product_id=False, po_order_type=False, rfq_ok=False, context=None):
        '''
        Check if the origin is a known FO/IR
        '''
        res = {}
        if not linked_sol_id and origin:
            sale_id = self.pool.get('sale.order').search(cr, uid, [
                ('name', '=', origin),
                ('state', 'not in', ['done', 'cancel']),
                ('procurement_request', 'in', ['t', 'f']),
                ('order_type', '=', 'regular'),
            ], limit=1, order='NO_ORDER', context=context)
            if not sale_id:
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _('The reference \'%s\' put in the Origin field doesn\'t match with a non-closed/cancelled regular FO/IR. No FO/IR line will be created for this PO line') % origin,
                }
                res['value'] = {
                    'display_sync_ref': False,
                    'instance_sync_order_ref': '',
                    'origin': '',
                }
            else:
                fo = self.pool.get('sale.order').read(cr, uid, sale_id[0], ['sourced_references', 'procurement_request'], context=context)
                if not fo['procurement_request'] and po_order_type in ['regular', 'purchase_list'] and product_id and not rfq_ok and \
                        self.pool.get('product.product').read(cr, uid, product_id, ['type'])['type'] == 'service_recep':
                    res.update({
                        'warning': {'title': _('Error'),
                                    'message': _('A Service Product can not be linked to a FO on a Regular or a Purchase List PO')},
                        'value': {'origin': False}
                    })
                else:
                    res['value'] = {
                        'display_sync_ref': len(fo['sourced_references']) and True or False,
                    }
                    res['warning'] = {'message': self.msg_selected_po}

        return res

    def on_change_instance_sync_order_ref(self, cr, uid, ids, instance_sync_order_ref, product_id, nomen_manda_0, context=None):
        if context is None:
            context = {}

        if instance_sync_order_ref:
            # Check for service product/nomenclature
            product_type = product_id and self.pool.get('product.product').read(cr, uid, product_id, ['type'], context=context)['type'] or False
            if (product_type == 'service_recep' or self.check_is_service_nomen(cr, uid, nomen_manda_0)) and \
                    'FO' in self.pool.get('sync.order.label').read(cr, uid, instance_sync_order_ref)['name']:
                return {
                    'value': {'instance_sync_order_ref': False},
                    'warning': {
                        'title': _('Warning'),
                        'message': _("You can not select a FO as Order in sync. instance if the product is Service"),
                    }
                }

        return {}

    def product_id_on_change(self, cr, uid, ids, pricelist, product, qty, uom, partner_id, date_order=False,
                             fiscal_position=False, date_planned=False, name=False, price_unit=False, notes=False,
                             state=False, old_price_unit=False, nomen_manda_0=False, comment=False, context=None,
                             categ=False, from_product=False, linked_sol_id=False, select_fo=False, po_order_type=False,
                             instance_sync_order_ref=False, rfq_ok=False):
        all_qty = qty
        partner_price = self.pool.get('pricelist.partnerinfo')
        product_obj = self.pool.get('product.product')
        if not context:
            context = {}

        # If the user modify a line, remove the old quantity for the total quantity
        if ids:
            for line_id in self.read(cr, uid, ids, ['product_qty'], context=context):
                all_qty -= line_id['product_qty']

        ir_sol = linked_sol_id and self.pool.get('sale.order.line').read(cr, uid, linked_sol_id, ['procurement_request'])['procurement_request'] or False
        ir_so = select_fo and self.pool.get('sale.order').read(cr, uid, select_fo, ['procurement_request'])['procurement_request'] or False
        if product and ((linked_sol_id and not ir_sol) or (select_fo and not ir_so)) and \
                po_order_type in ['regular', 'purchase_list'] and not rfq_ok and \
                product_obj.read(cr, uid, product, ['type'])['type'] == 'service_recep':
            return {'warning': {'title': _('Error'),
                                'message': _('You can not select a Service Product on a Regular or a Purchase List PO if the line has been sourced from a FO')},
                    'value': {'product_id': False}}

        if instance_sync_order_ref:  # Check for service product
            product_type = product and self.pool.get('product.product').read(cr, uid, product, ['type'], context=context)['type'] or False
            if product_type == 'service_recep' and 'FO' in self.pool.get('sync.order.label').read(cr, uid, instance_sync_order_ref)['name']:
                return {
                    'value': {'product_id': False},
                    'warning': {
                        'title': _('Warning'),
                        'message': _("You can not select a Service product if the Order in sync. instance is a FO"),
                    }
                }

        if product and not uom:
            uom = product_obj.read(cr, uid, product, ['uom_id'])['uom_id'][0]

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

        if qty == 0.00:
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

        # price_unit is set only if catalogue exists
        if product and not res.get('value', {}).get('price_unit', False) and all_qty != 0.00 and qty != 0.00:
            # Display a warning message if the quantity is under the minimal qty of the supplier
            currency_id = self.pool.get('product.pricelist').read(cr, uid, pricelist, ['currency_id'])['currency_id'][0]
            tmpl_id = product_obj.read(cr, uid, product, ['product_tmpl_id'])['product_tmpl_id'][0]
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
                if info_price.min_order_qty and qty < info_price.min_order_qty:
                    if qty > info_price.min_quantity:
                        res['value'].update({'old_price_unit': info_u_price, 'price_unit': info_u_price})
                    res.update({'warning': {'title': _('Warning'), 'message': _('The product unit price has been set ' \
                                                                                'for a minimal quantity of %s (the min quantity of the price list), ' \
                                                                                'it might change at the supplier confirmation.') % info_price.min_quantity}})
                if info_price.rounding and all_qty % info_price.rounding != 0:
                    message = _('A rounding value of %s UoM has been set for ' \
                                'this product, you should than modify ' \
                                'the quantity ordered to match the supplier criteria.') % info_price.rounding
                    message = '%s \n %s' % (res.get('warning', {}).get('message', ''), message)
                    res.setdefault('warning', {})
                    res['warning'].update({'message': message})

        # Set the unit price with cost price if the product has no staged pricelist
        if product:
            product_result = product_obj.read(cr, uid, product, ['uom_id', 'standard_price', 'is_ssl'])

        if product and qty != 0.00:
            res['value'].update({'comment': False, 'nomen_manda_0': False, 'nomen_manda_1': False,
                                 'nomen_manda_2': False, 'nomen_manda_3': False, 'nomen_sub_0': False,
                                 'nomen_sub_1': False, 'nomen_sub_2': False, 'nomen_sub_3': False,
                                 'nomen_sub_4': False, 'nomen_sub_5': False})
            st_uom = product_result['uom_id'][0]
            if not res.get('value', {}).get('price_unit') and (not price_unit or from_product):
                st_price = product_result['standard_price']
                st_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, st_price, round=False,
                                                                 context=context)
                st_price = self.pool.get('product.uom')._compute_price(cr, uid, st_uom, st_price, uom)
                if res.get('value', {}).get('price_unit', False) == False and (state and state == 'draft') or not state:
                    res['value'].update({'price_unit': st_price})
                elif state and state != 'draft' and old_price_unit:
                    res['value'].update({'price_unit': old_price_unit})

                if not res['value'].get('price_unit'):
                    res['value'].update({'price_unit': st_price})

        elif qty == 0.00:
            res['value'].update({'price_unit': 0.00, 'old_price_unit': 0.00})
        elif not product and not comment and not nomen_manda_0:
            res['value'].update({'price_unit': 0.00, 'product_qty': 0.00, 'product_uom': False, 'old_price_unit': 0.00})

        if state == 'draft':
            if name != res['value'].get('name', False) and res['value'].get('price_unit', False):
                res['value']['original_price'] = res['value']['price_unit']
            else:
                res['value']['original_price'] = 0.00

        if product and qty and state and state != 'draft' and old_price_unit:
            res['value'].update({'price_unit': old_price_unit})

        if 'price_unit' in res['value']:
            res['value']['old_price_unit'] = res['value']['price_unit']

        if (categ or context.get('categ')) and product:
            # Check consistency of product
            consistency_message = product_obj.check_consistency(cr, uid, product, categ or context.get('categ'), context=context)
            if consistency_message:
                res.setdefault('warning', {})
                res['warning'].setdefault('title', 'Warning')
                res['warning'].setdefault('message', '')

                res['warning']['message'] = '%s \n %s' % (
                    res.get('warning', {}).get('message', ''), consistency_message)

        if product and product_result['is_ssl']:
            warning = {
                'title': 'Short Shelf Life product',
                'message': _('Product with Short Shelf Life, check the accuracy of the order quantity, frequency and mode of transport.')
            }
            res.update(warning=warning)

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

        pol = {}
        if ids:
            pol = self.read(cr, uid, ids[0], ['product_qty'], context=context)
        if not product_id or not product_uom or not product_qty:
            self.check_digits(cr, uid, res, pol, qty=product_qty, price_unit=price_unit, context=context)
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

        self.check_digits(cr, uid, res, pol, qty=product_qty, price_unit=price_unit, context=context)
        return res

    def get_sol_ids_from_pol_ids(self, cr, uid, ids, context=None):
        '''
        input: purchase order line ids
        return: sale order line ids
        '''
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        sol_ids = set()
        for pol in self.browse(cr, uid, ids, fields_to_fetch=['linked_sol_id'], context=context):
            if pol.linked_sol_id:
                sol_ids.add(pol.linked_sol_id.id)

        return list(sol_ids)

    def open_split_wizard(self, cr, uid, ids, context=None):
        '''
        Open the wizard to split the line
        '''
        if not context:
            context = {}

        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]

        msf_pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]

        import_commitments = self.pool.get('unifield.setup.configuration').get_config(cr, uid).import_commitments
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.partner_id.partner_type == 'internal':
                return False

            if pol.order_id.partner_id.partner_type == 'esc' and import_commitments:
                return False

            if pol.order_id.order_type in ['loan', 'loan_return', 'in_kind', 'donation_st', 'donation_exp']:
                return False

            # exclude push flow (FO or FO line created first)
            if pol.order_id.push_fo or pol.set_as_sourced_n:
                return False

            commitment_voucher_id = self.pool.get('account.commitment').search(cr, uid, [('purchase_id', '=', pol.order_id.id), ('state', '=', 'draft')], context=context)
            if commitment_voucher_id:
                commitment_voucher_id = commitment_voucher_id[0]
            else: # create commitment voucher
                if not pol.confirmed_delivery_date:
                    raise osv.except_osv(_('Error'), _('Confirmed Delivery Date is a mandatory field.'))
                commitment_voucher_id = self.pool.get('purchase.order').create_commitment_voucher_from_po(cr, uid, [pol.order_id.id], cv_date=pol.confirmed_delivery_date, context=context)

            expense_account = pol.account_4_distribution and pol.account_4_distribution.id or False
            if not expense_account:
                raise osv.except_osv(_('Error'), _('There is no expense account defined for this line: %s (id:%d)') % (pol.name or '', pol.id))

            # in CV in version 1, PO lines are grouped by account_id. Else 1 PO line generates 1 CV line.
            cv_version = self.pool.get('account.commitment').read(cr, uid, commitment_voucher_id, ['version'], context=context)['version']
            cc_lines = []
            ad_header = []  # if filled in, the line itself has no AD but uses the one at header level
            if pol.analytic_distribution_id:
                cc_lines = pol.analytic_distribution_id.cost_center_lines
            elif cv_version < 2:
                # in CV in version 1, if there is no AD on the PO line, the AD at PO header level is used at CV line level
                cc_lines = pol.order_id.analytic_distribution_id.cost_center_lines
            else:
                ad_header = pol.order_id.analytic_distribution_id.cost_center_lines

            if not cc_lines and not ad_header:
                raise osv.except_osv(_('Warning'), _('Analytic allocation is mandatory for %s on the line %s for the product %s! It must be added manually.')
                                     % (pol.order_id.name, pol.line_number, pol.product_id and pol.product_id.default_code or pol.name or ''))

            new_cv_line = False
            if cv_version > 1:
                new_cv_line = True
            else:
                commit_line_id = self.pool.get('account.commitment.line').search(cr, uid,
                                                                                 [('commit_id', '=', commitment_voucher_id),
                                                                                  ('account_id', '=', expense_account)], context=context)
                if not commit_line_id:
                    new_cv_line = True
            if new_cv_line:  # create new commitment line
                if ad_header:  # the line has no AD itself, it uses the AD at header level
                    distrib_id = False
                else:
                    distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
                commit_line_vals = {
                    'commit_id': commitment_voucher_id,
                    'account_id': expense_account,
                    'amount': pol.price_subtotal,
                    'initial_amount': pol.price_subtotal,
                    'analytic_distribution_id': distrib_id,
                }
                if cv_version > 1:
                    commit_line_vals.update({'po_line_id': pol.id, 'line_number': pol.line_number, 'line_product_id': pol.product_id.id})
                else:
                    commit_line_vals.update({'purchase_order_line_ids': [(4, pol.id)], })
                commit_line_id = self.pool.get('account.commitment.line').create(cr, uid, commit_line_vals, context=context)
                if distrib_id:
                    for aline in cc_lines:
                        vals = {
                            'distribution_id': distrib_id,
                            'analytic_id': aline.analytic_id.id,
                            'currency_id': pol.order_id.currency_id.id,
                            'destination_id': aline.destination_id.id,
                            'percentage': aline.percentage,
                        }
                        self.pool.get('cost.center.distribution.line').create(cr, uid, vals, context=context)
                    self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [distrib_id], expense_account, context=context)

            else: # update existing commitment line:
                commit_line_id = commit_line_id[0]
                cv_line = self.pool.get('account.commitment.line').browse(cr, uid, commit_line_id, fields_to_fetch=['amount', 'analytic_distribution_id'], context=context)

                current_add = {}
                if cv_line.analytic_distribution_id:
                    distrib_id = cv_line.analytic_distribution_id.id
                    for fp in cv_line.analytic_distribution_id.funding_pool_lines:
                        key = (fp.analytic_id.id, fp.destination_id.id, fp.cost_center_id.id)
                        current_add.setdefault(key, 0)
                        current_add[key] += cv_line.amount * fp.percentage / 100
                    self.pool.get('analytic.distribution').write(cr, uid, distrib_id, {'funding_pool_lines': [(6, 0, [])], 'cost_center_lines': [(6, 0, [])]}, context=context)
                else:
                    distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)

                for aline in cc_lines:
                    key = (msf_pf_id, aline.destination_id.id, aline.analytic_id.id)
                    current_add.setdefault(key, 0)
                    current_add[key] += pol.price_subtotal * aline.percentage / 100

                new_amount = (cv_line.amount or 0) + pol.price_subtotal
                self.pool.get('account.commitment.line').write(cr, uid, [commit_line_id], {
                    'amount': new_amount,
                    'initial_amount': new_amount,
                    'purchase_order_line_ids': [(4, pol.id)],
                    'analytic_distribution_id': distrib_id,
                }, context=context)

                for key in current_add:
                    self.pool.get('funding.pool.distribution.line').create(cr, uid, {
                        'analytic_id': key[0],
                        'destination_id': key[1],
                        'cost_center_id': key[2],
                        'currency_id': pol.order_id.currency_id.id,
                        'distribution_id': distrib_id,
                        'percentage': (current_add[key] / new_amount) * 100,
                    }, context=context)

        return True

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        Add an entry to cancel (and resource if needed) the line when the
        PO will be confirmed
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        to_del = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['draft', 'validated_n']), ('linked_sol_id', '=', False)], context=context)
        to_cancel = self.search(cr, uid, [('id', 'in', ids), ('linked_sol_id', '!=', False), ('state', 'in', ['draft', 'validated_n', 'validated'])], context=context)
        if to_del:
            self.unlink(cr, uid, to_del, context=context)

        for to_cancel_id in to_cancel:
            wf_service.trg_validate(uid, 'purchase.order.line', to_cancel_id, 'cancel', cr)


        return True

    def dates_change(self, cr, uid, ids, requested_date, confirmed_date, context=None):
        '''
        Checks if dates are later than header dates

        deprecated
        '''
        if context is None:
            context = {}
        return {'value': {'date_planned': requested_date, }}

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a purchase order line.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # Prepare some values
        purchase_line = self.browse(cr, uid, ids[0], context=context)
        amount = purchase_line.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = purchase_line.order_id.currency_id and purchase_line.order_id.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = purchase_line.analytic_distribution_id and purchase_line.analytic_distribution_id.id
        # Get default account
        account_id = purchase_line.account_4_distribution and purchase_line.account_4_distribution.id or False
        # Check if PO is inkind
        is_inkind = False
        if purchase_line.order_id and purchase_line.order_id.order_type == 'in_kind':
            is_inkind = True
        if is_inkind and not account_id:
            raise osv.except_osv(_('Error'), _('No donation account found for this line: %s. (product: %s)') % (purchase_line.name, purchase_line.product_id and purchase_line.product_id.name or ''))
        elif not account_id:
            raise osv.except_osv(_('Error !'),
                                 _('There is no expense account defined for this product: "%s" (id:%d)') % (purchase_line.product_id.name, purchase_line.product_id.id))
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'purchase_line_id': purchase_line.id,
            'currency_id': currency or False,
            'state': 'cc',
            'account_id': account_id or False,
            'posting_date': time.strftime('%Y-%m-%d'),
            'document_date': time.strftime('%Y-%m-%d'),
            'partner_type': context.get('partner_type'),
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }


    def generate_invoice(self, cr, uid, ids, context=None):
        inv_ids = {}
        inv_line = self.pool.get('account.invoice.line')
        ana_obj = self.pool.get('analytic.distribution')

        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.id not in inv_ids:
                inv_ids[pol.order_id.id] = pol.order_id.action_invoice_get_or_create(context=context)

            all_taxes = {}
            if pol.order_id.tax_line and pol.order_id.amount_untaxed:
                percent = (pol.product_qty * pol.price_unit) / pol.order_id.amount_untaxed
                all_taxes.setdefault(inv_ids[pol.order_id.id], {})
                for tax_line in pol.order_id.tax_line:
                    key = (tax_line.account_tax_id and tax_line.account_tax_id.id or False, tax_line.account_id.id, tax_line.partner_id and tax_line.partner_id.id or False)
                    if key not in all_taxes[inv_ids[pol.order_id.id]]:
                        all_taxes[inv_ids[pol.order_id.id]][key] = {
                            'tax_line': tax_line,
                            'amount': 0,
                        }
                    all_taxes[inv_ids[pol.order_id.id]][key]['amount'] +=  tax_line.amount * percent

            if pol.product_id:
                account_id = pol.product_id.product_tmpl_id.property_account_expense.id
                if not account_id:
                    account_id = pol.product_id.categ_id.property_account_expense_categ.id
                if not account_id:
                    raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (numer:%d)') % (pol.product_id.default_code, pol.line_number))
            else:
                account_id = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category').id

            fpos = pol.order_id.fiscal_position or False
            account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, account_id)

            distrib_id = False
            if pol.analytic_distribution_id:
                distrib_id = ana_obj.copy(cr, uid, pol.analytic_distribution_id.id, {})
                ana_obj.create_funding_pool_lines(cr, uid, [distrib_id])

            inv_line.create(cr, uid, {
                'name': pol.name,
                'account_id': account_id,
                'price_unit': pol.price_unit or 0.0,
                'quantity': pol.product_qty,
                'product_id': pol.product_id.id or False,
                'uos_id': pol.product_uom.id or False,
                'invoice_line_tax_id': [(6, 0, [x.id for x in pol.taxes_id])],
                'account_analytic_id': pol.account_analytic_id.id or False,
                'order_line_id': pol.id,
                'invoice_id': inv_ids[pol.order_id.id],
                'analytic_distribution_id': distrib_id,
            }, context=context)

        self.write(cr, uid, ids, {'invoiced': True}, context=context)

        for inv_id in all_taxes:
            for key in all_taxes[inv_id]:
                tax_id = self.pool.get('account.invoice.tax').search(cr, uid, [('invoice_id', '=', inv_id), ('account_tax_id', '=', key[0]), ('account_id', '=', key[1]), ('partner_id', '=', key[2])], context=context)
                if not tax_id:
                    self.pool.get('account.invoice.tax').create(cr, uid, {
                        'invoice_id': inv_id,
                        'account_tax_id':  key[0],
                        'account_id': key[1],
                        'partner_id': key[2],
                        'name': all_taxes[inv_id][key]['tax_line'].name,
                        'amount': all_taxes[inv_id][key]['amount']}, context=context)
                else:
                    cr.execute('update account_invoice_tax set amount=amount+%s where id = %s', (all_taxes[inv_id][key]['amount'], tax_id[0]))

        self.pool.get('account.invoice').button_compute(cr, uid, list(inv_ids.values()), {'type':'in_invoice'}, set_total=True)


    def update_dates_from_pol(self, cr, uid, source, data, context=None):
        line_info = data.to_dict()
        if line_info.get('linked_sol_id', {}).get('sync_local_id') and (line_info.get('esti_dd') or line_info.get('confirmed_delivery_date')):
            pol_id = self.search(cr, uid, [('sync_linked_sol', '=', line_info['linked_sol_id']['sync_local_id'])], limit=1, context=context)
            if pol_id:
                pol_record = self.browse(cr, uid, pol_id[0], fields_to_fetch=['line_number', 'order_id', 'state'], context=context)
                if pol_record['state'] in ('sourced_v', 'sourced_n'):
                    to_write = {}
                    for date in ['confirmed_delivery_date', 'esti_dd']:
                        if line_info.get(date):
                            to_write[date] = line_info[date]
                    self.write(cr, uid, pol_id, to_write, context)
                    return "Dates updated on %s line number %s (id:%s)" % (pol_record.order_id.name, pol_record.line_number, pol_record.id)
                elif pol_record['state'] in ('confirmed', 'done', 'cancel', 'cancel_r'):
                    return "Message ignored %s line number %s (id:%s), state: %s" % (pol_record.order_id.name, pol_record.line_number, pol_record.id, pol_record['state'])
                else:
                    raise Exception("%s line number %s (id:%s), dates not updated due to wrong state: %s" % (pol_record.order_id.name, pol_record.line_number, pol_record.id, pol_record['state']))

            raise Exception("PO line not found.")

        return True

    def update_date_expected(self, cr, uid, source, data, context=None):
        line_info = data.to_dict()
        stock_move = self.pool.get('stock.move')
        if line_info.get('sync_local_id') and line_info.get('date_expected'):
            pol_id = self.search(cr, uid, [('sync_linked_sol', '=', line_info['sync_local_id'])], limit=1, context=context)
            if pol_id:
                move_id = stock_move.search(cr, uid, [('purchase_line_id', '=', pol_id), ('type', '=', 'in'), ('state', '=', 'assigned')])
                if move_id:
                    stock_move.write(cr, uid, move_id[0], {'date_expected': line_info.get('date_expected')}, context=context)
                    # to update Expected Receipt Date on picking
                    picking_id = stock_move.browse(cr, uid, move_id[0], fields_to_fetch=['picking_id']).picking_id
                    if picking_id:
                        picking_id.write({}, context=context)
        return True

    def final_location_dest(self, cr, uid, pol_obj, fo_obj=False, context=None):
        data_obj = self.pool.get('ir.model.data')

        dest = pol_obj.reception_dest_id.id

        if not pol_obj.product_id:
            return dest

        if pol_obj.product_id.type == 'service_recep' and not pol_obj.order_id.cross_docking_ok:
            # service with reception are directed to Service Location
            return self.pool.get('stock.location').get_service_location(cr, uid)

        if pol_obj.product_id.type == 'consu':
            return data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]

        fo = fo_obj or pol_obj.linked_sol_id and pol_obj.linked_sol_id.order_id or False
        if fo and fo.procurement_request and fo.location_requestor_id.usage != 'customer':
            return fo.location_requestor_id.id

        chained = self.pool.get('stock.location').chained_location_get(cr, uid, pol_obj.reception_dest_id, product=pol_obj.product_id, context=context)
        if chained:
            if chained[0].chained_location_type == 'nomenclature':
                # 1st round : Input > Stock, 2nd round Stock -> MED/LOG
                chained2 = self.pool.get('stock.location').chained_location_get(cr, uid, chained[0], product=pol_obj.product_id, context=context)
                if chained2:
                    return chained2[0].id
            return chained[0].id

        return dest

    def get_reception_dest(self, cr, uid, vals, pol=None, context=None):
        '''
        Get the location the linked IN move will be sent to during reception
        '''
        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')
        srv_id = self.pool.get('stock.location').get_service_location(cr, uid, context=context)
        input_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        cross_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        n_stock_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]

        product_type, so = False, False
        if pol:
            if 'product_id' in vals and vals.get('product_id'):
                product_type = prod_obj.read(cr, uid, vals['product_id'], ['type'], context=context)['type']
            else:
                product_type = pol.product_id.type
            if 'link_so_id' in vals and vals.get('link_so_id'):
                ftf = ['procurement_request', 'location_requestor_id']
                so = self.pool.get('sale.order').browse(cr, uid, vals['link_so_id'], fields_to_fetch=ftf, context=context)
            else:
                so = pol.linked_sol_id and pol.linked_sol_id.order_id or pol.link_so_id or False
        else:
            if 'product_id' in vals and vals.get('product_id'):
                product_type = prod_obj.read(cr, uid, vals['product_id'], ['type'], context=context)['type']
            if 'linked_sol_id' in vals and vals.get('linked_sol_id'):
                so = self.pool.get('sale.order.line').browse(cr, uid, vals['linked_sol_id'],
                                                             fields_to_fetch=['order_id'], context=context).order_id

        dest = input_id
        # please also check in delivery_mechanism/delivery_mechanism.py _get_values_from_line to set location_dest_id
        if product_type == 'service_recep':
            dest = srv_id
        elif so:
            if product_type == 'consu' and so.procurement_request:
                dest = n_stock_id
            elif not so.procurement_request or (so.procurement_request and so.location_requestor_id.usage == 'customer'):
                dest = cross_id
        elif product_type == 'consu':
            dest = n_stock_id

        return dest

    def open_po_form(self, cr, uid, ids, context=None):
        pol = self.browse(cr, uid, ids[0], fields_to_fetch=['order_id'], context=context)

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'purchase.purchase_form_action', ['form', 'tree'], new_tab=True, context=context)
        res['keep_open'] = True
        res['res_id'] = pol.order_id.id
        return res

    def get_error(self, cr, uid, ids, context=None):
        '''
        Show error message
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'purchase', 'po_line_error_message_view')[1]
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'purchase.order.line',
            'type': 'ir.actions.act_window',
            'res_id': ids[0],
            'target': 'new',
            'context': context,
            'view_id': [view_id],
        }


purchase_order_line()


class purchase_order_line_state(osv.osv):
    _name = "purchase.order.line.state"
    _description = "States of a purchase order line"

    _columns = {
        'name': fields.text(string='PO state', store=True),
        'sequence': fields.integer(string='Sequence'),
    }

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

