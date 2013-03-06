#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from osv import osv
from osv import fields
from msf_partner import PARTNER_TYPE
import time
from tools.translate import _


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    def search_in_product(self, cr, uid, obj, name, args, context=None):
        '''
        Search function of related field 'in_product'
        '''
        if not len(args):
            return []
        if context is None:
            context = {}
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            return []

        supinfo_obj = self.pool.get('product.supplierinfo')
        sup_obj = self.pool.get('res.partner')
        res = []

        info_ids = supinfo_obj.search(cr, uid, [('product_product_ids', '=', context.get('product_id'))])
        info = supinfo_obj.read(cr, uid, info_ids, ['name'])

        sup_in = [x['name'] for x in info]
        
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    res = sup_in
            else:
                    res = sup_obj.search(cr, uid, [('id', 'not in', sup_in)])
        
        if not res:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in res])]
        
    
    def _set_in_product(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns according to the context if the partner is in product form
        '''
        if context is None:
            context = {}
        res = {}
        
        product_obj = self.pool.get('product.product')
        
        # If we aren't in the context of choose supplier on procurement list
        if not context.get('product_id', False) or 'choose_supplier' not in context:
            for i in ids:
                res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}
        else:
            product = product_obj.browse(cr, uid, context.get('product_id'))
            seller_ids = []
            seller_info = {}
            # Get all suppliers defined on product form
            for s in product.seller_ids:
                seller_ids.append(s.name.id)
                seller_info.update({s.name.id: {'min_qty': s.min_qty, 'delay': s.delay}})
            # Check if the partner is in product form
            for i in ids:
                if i in seller_ids:
                    res[i] = {'in_product': True, 'min_qty': '%s' %seller_info[i]['min_qty'], 'delay': '%s' %seller_info[i]['delay']}
                else:
                    res[i] = {'in_product': False, 'min_qty': 'N/A', 'delay': 'N/A'}

        return res
    
    def _get_price_info(self, cr, uid, ids, fiedl_name, args, context=None):
        '''
        Returns information from product supplierinfo if product_id is in context
        '''
        if not context:
            context = {}
            
        partner_price = self.pool.get('pricelist.partnerinfo')
        res = {}
        
        for id in ids:
            res[id] = {'price_currency': False,
                       'price_unit': 0.00,
                       'valide_until_date': False}
            
        if context.get('product_id'):
            for partner in self.browse(cr, uid, ids, context=context):
                product = self.pool.get('product.product').browse(cr, uid, context.get('product_id'), context=context)
                uom = context.get('uom', product.uom_id.id)
                pricelist = partner.property_product_pricelist_purchase
                context.update({'uom': uom})
                price_list = self.pool.get('product.product')._get_partner_info_price(cr, uid, product, partner.id, context.get('product_qty', 1.00), pricelist.currency_id.id, time.strftime('%Y-%m-%d'), uom, context=context)
                if not price_list:
                    func_currency_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
                    price = self.pool.get('res.currency').compute(cr, uid, func_currency_id, pricelist.currency_id.id, product.standard_price, round=False, context=context)
                    res[partner.id] = {'price_currency': pricelist.currency_id.id,
                                       'price_unit': price,
                                       'valide_until_date': False}
                else:
                    info_price = partner_price.browse(cr, uid, price_list[0], context=context)
                    partner_currency_id = pricelist.currency_id.id
                    price = self.pool.get('res.currency').compute(cr, uid, info_price.currency_id.id, partner_currency_id, info_price.price, round=False, context=context)
                    currency = partner_currency_id
                    # Uncomment the following 2 lines if you want the price in currency of the pricelist.partnerinfo instead of partner default currency
#                    currency = info_price.currency_id.id
#                    price = info_price.price
                    res[partner.id] = {'price_currency': currency,
                                       'price_unit': price,
                                       'valide_until_date': info_price.valid_till}
            
        return res

## QT : Remove _get_price_unit

## QT : Remove _get_valide_until_date 

    _columns = {
        'manufacturer': fields.boolean(string='Manufacturer', help='Check this box if the partner is a manufacturer'),
        'partner_type': fields.selection(PARTNER_TYPE, string='Partner type', required=True),
        'in_product': fields.function(_set_in_product, fnct_search=search_in_product, string='In product', type="boolean", readonly=True, method=True, multi='in_product'),
        'min_qty': fields.function(_set_in_product, string='Min. Qty', type='char', readonly=True, method=True, multi='in_product'),
        'delay': fields.function(_set_in_product, string='Delivery Lead time', type='char', readonly=True, method=True, multi='in_product'),
        'property_product_pricelist_purchase': fields.property(
          'product.pricelist',
          type='many2one', 
          relation='product.pricelist', 
          domain=[('type','=','purchase')],
          string="Purchase default currency", 
          method=True,
          view_load=True,
          required=True,
          help="This currency will be used, instead of the default one, for purchases from the current partner"),
        'property_product_pricelist': fields.property(
            'product.pricelist',
            type='many2one', 
            relation='product.pricelist', 
            domain=[('type','=','sale')],
            string="Field orders default currency", 
            method=True,
            view_load=True,
            required=True,
            help="This currency will be used, instead of the default one, for field orders to the current partner"),
        'price_unit': fields.function(_get_price_info, method=True, type='float', string='Unit price', multi='info'),
        'valide_until_date' : fields.function(_get_price_info, method=True, type='char', string='Valid until date', multi='info'),
        'price_currency': fields.function(_get_price_info, method=True, type='many2one', relation='res.currency', string='Currency', multi='info'),
    }

    _defaults = {
        'manufacturer': lambda *a: False,
        'partner_type': lambda *a: 'external',
    }


    def _check_main_partner(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        bro_uid = self.pool.get('res.users').browse(cr,uid,uid)

        bro = bro_uid.company_id
        res =  bro and bro.partner_id and bro.partner_id.id
        cur =  bro and bro.currency_id and bro.currency_id.id

        po_def_cur = self.pool.get('product.pricelist').browse(cr,uid,vals.get('property_product_pricelist_purchase'))
        fo_def_cur = self.pool.get('product.pricelist').browse(cr,uid,vals.get('property_product_pricelist'))

        if res in ids:
            for obj in self.browse(cr, uid, [res], context=context):

                if context.get('from_setup') and bro.second_time and po_def_cur and po_def_cur.currency_id and po_def_cur.currency_id.id != cur:
                    raise osv.except_osv(_('Warning !'), _('You can not change the Purchase Default Currency of this partner anymore'))

                if not context.get('from_setup') and po_def_cur and po_def_cur.currency_id and po_def_cur.currency_id.id != cur:
                    raise osv.except_osv(_('Warning !'), _('You can not change the Purchase Default Currency of this partner'))

                if context.get('from_setup') and bro.second_time and fo_def_cur and fo_def_cur.currency_id and fo_def_cur.currency_id.id != cur:
                    raise osv.except_osv(_('Warning !'), _('You can not change the Field Orders Default Currency of this partner anymore'))

                if not context.get('from_setup') and fo_def_cur and fo_def_cur.currency_id and fo_def_cur.currency_id.id != cur:
                    raise osv.except_osv(_('Warning !'), _('You can not change the Field Orders Default Currency of this partner'))

                if obj.customer:
                    raise osv.except_osv(_('Warning !'), _('This partner can not be checked as customer'))

                if obj.supplier:
                    raise osv.except_osv(_('Warning !'), _('This partner can not be checked as supplier'))

        return True

    _constraints = [
    ]

    def get_objects_for_partner(self, cr, uid, ids, context):
        """
        According to partner's ids: 
        return the most important objects linked to him that are not closed or opened
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        #objects
        purchase_obj = self.pool.get('purchase.order')
        sale_obj = self.pool.get('sale.order')
        account_invoice_obj = self.pool.get('account.invoice') # for Supplier invoice/ Debit Note
        pick_obj = self.pool.get('stock.picking') # for PICK/ PACK/ PPL/ INCOMING SHIPMENT/ DELIVERY
        tender_obj = self.pool.get('tender')
        com_vouch_obj = self.pool.get('account.commitment')# for commitment voucher
        ship_obj = self.pool.get('shipment')

        # ids list (the domain are the same as the one used for the action window of the menus)
        purchase_ids = purchase_obj.search(cr, uid, [('rfq_ok', '=', False), ('partner_id', '=', ids[0]), ('state', 'not in', ['done', 'cancel'])], context=context.update({'purchase_order': True}))
        rfq_ids = purchase_obj.search(cr, uid, [('rfq_ok', '=', True), ('partner_id', '=', ids[0]), ('state', 'not in', ['done', 'cancel'])], context=context.update({'request_for_quotation': True}))
        sale_ids = sale_obj.search(cr, uid, [('procurement_request', '=', False), ('partner_id', '=', ids[0]), ('state', 'not in', ['done', 'cancel'])], context=context)
        intermission_vouch_in_ids = account_invoice_obj.search(cr, uid, [('type','=','in_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('is_intermission', '=', True), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                                         ], context = context.update({'type':'in_invoice', 'journal_type': 'intermission'}))
        nb_intermission_vouch_in_ids = len(intermission_vouch_in_ids)
        intermission_vouch_out_ids = account_invoice_obj.search(cr, uid, [('type','=','out_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('is_intermission', '=', True), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                                         ], context = context.update({'type':'out_invoice', 'journal_type': 'intermission'}))
        nb_intermission_vouch_out_ids = len(intermission_vouch_out_ids)
        donation_ids = account_invoice_obj.search(cr, uid, [('type','=','in_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', True), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                           ], context = context.update({'type':'in_invoice', 'journal_type': 'inkind'}))
        supp_invoice_ids = account_invoice_obj.search(cr, uid, [('type','=','in_invoice'), ('register_line_ids', '=', False), ('is_inkind_donation', '=', False), ('is_debit_note', "=", False), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                               ], context = context.update({'type':'in_invoice', 'journal_type': 'purchase'}))
        nb_supp_invoice_ids = len(supp_invoice_ids)
        cust_refunds_ids = account_invoice_obj.search(cr, uid, [('type','=','out_refund'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                               ], context = context.update({'type':'out_refund', 'journal_type': 'sale_refund'}))
        nb_cust_refunds_ids = len(cust_refunds_ids)
        debit_note_ids = account_invoice_obj.search(cr, uid, [('type','=','out_invoice'), ('is_debit_note', '!=', False), ('is_inkind_donation', '=', False), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                              ], context = context.update({'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True}))
        nb_debit_note_ids = len(debit_note_ids)
        stock_transfer_vouch_ids = account_invoice_obj.search(cr, uid, [('type','=','out_invoice'), ('is_debit_note', '=', False), ('is_inkind_donation', '=', False), ('partner_id', '=', ids[0]), ('state', 'in', ['draft', 'open'])
                                                                        ], context = context.update({'type':'out_invoice', 'journal_type': 'sale'}))
        incoming_ship_ids = pick_obj.search(cr, uid, [('state', 'not in', ['done', 'cancel']), ('type', '=', 'in'), ('subtype', '=', 'standard'), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
                                                      ], context = context.update({'contact_display': 'partner_address', 'subtype': 'in', 'picking_type': 'incoming_shipment', 'search_default_available':1}))
        out_ids = pick_obj.search(cr, uid, [('state', 'not in', ['done', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'standard'), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
                                            ], context = context.update({'contact_display': 'partner_address', 'search_default_available': 1,'picking_type': 'delivery_order', 'subtype': 'standard'}))
        pick_ids = pick_obj.search(cr, uid, [('state', 'not in', ['done', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'picking'), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
                                             ], context = context.update({'picking_screen':True, 'picking_type': 'picking_ticket', 'test':True, 'search_default_not_empty':1}))
        ppl_ids = pick_obj.search(cr, uid, [('state', 'not in', ['done', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'ppl'), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
                                            ], context=context.update({'contact_display': 'partner_address', 'ppl_screen':True, 'picking_type': 'picking_ticket', 'search_default_available':1}))
        tender_ids = [tend for tend in tender_obj.search(cr, uid, [('state', '=', 'comparison')]) if ids[0] in tender_obj.read(cr, uid, tend, ['supplier_ids'])['supplier_ids']]
        com_vouch_ids = com_vouch_obj.search(cr, uid, [('partner_id', '=', ids[0]), ('state', '!=', 'done')], context=context)
        ship_ids = ship_obj.search(cr, uid,  [('state', 'not in', ['done', 'delivered']), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])], context=context)
        
        return ', '.join([po['name']+_(' (Purchase)') for po in purchase_obj.read(cr, uid, purchase_ids, ['name'], context) if po['name']]
                         +[rfq['name']+_(' (RfQ)') for rfq in purchase_obj.read(cr, uid, rfq_ids, ['name'], context) if rfq['name']]
                         +[so['name']+_(' (Field Order)') for so in sale_obj.read(cr, uid, sale_ids, ['name'], context) if so['name']]
                         +([int_vouch_in['number']+_(' (Intermission Voucher IN)') for int_vouch_in in account_invoice_obj.read(cr, uid, intermission_vouch_in_ids, ['number'], context) if int_vouch_in['number']]\
                         or intermission_vouch_in_ids and [str(nb_intermission_vouch_in_ids)+_(' (Number of Intermission Voucher IN)')])
                         +([int_vouch_out['number']+_(' (Intermission Voucher OUT)') for int_vouch_out in account_invoice_obj.read(cr, uid, intermission_vouch_out_ids, ['number'], context) if int_vouch_out['number']]\
                         or intermission_vouch_out_ids and [str(nb_intermission_vouch_out_ids)+_(' (Number of Intermission Voucher OUT)')])
                         +[donation['name']+_(' (Donation)') for donation in account_invoice_obj.read(cr, uid, donation_ids, ['name'], context) if donation['name']]
                         +([supp_invoice['number']+_(' (Supplier Invoice)') for supp_invoice in account_invoice_obj.read(cr, uid, supp_invoice_ids, ['number'], context) if supp_invoice['number']]\
                         or supp_invoice_ids and [str(nb_supp_invoice_ids)+_(' (Number of Supplier Invoice)')])
                         +([cust_refunds['number']+_(' (Customer Refunds)') for cust_refunds in account_invoice_obj.read(cr, uid, cust_refunds_ids, ['number'], context) if cust_refunds['number']]\
                         or cust_refunds_ids and [str(nb_cust_refunds_ids)+_(' (Number of Customer Refunds)')])
                         +[debit_note['number']+_(' (Debit Note)') for debit_note in account_invoice_obj.read(cr, uid, debit_note_ids, ['number'], context) if debit_note['number']]
                         +[st_transf_vouch['number']+_(' (Stock Transfer Voucher)') for st_transf_vouch in account_invoice_obj.read(cr, uid, stock_transfer_vouch_ids, ['number',], context) if st_transf_vouch['number']]
                         +[inc_ship['name']+_(' (Incoming Shipment)') for inc_ship in pick_obj.read(cr, uid, incoming_ship_ids, ['name'], context) if inc_ship['name']]
                         +[out['name']+_(' (OUT)') for out in pick_obj.read(cr, uid, out_ids, ['name'], context) if out['name']]
                         +[pick['name']+_(' (PICK)') for pick in pick_obj.read(cr, uid, pick_ids, ['name'], context) if pick['name']]
                         +[ppl['name']+_(' (PPL)') for ppl in pick_obj.read(cr, uid, ppl_ids, ['name'], context) if ppl['name']]
                         +[tend['name']+_(' (Tender)') for tend in tender_obj.read(cr, uid, tender_ids, ['name'], context) if tend['name']]
                         +[com_vouch['name']+_(' (Commitment Voucher)') for com_vouch in com_vouch_obj.read(cr, uid, com_vouch_ids, ['name'], context) if com_vouch['name']]
                         +[ship['name']+_(' (Shipment)') for ship in ship_obj.read(cr, uid, ship_ids, ['name'], context) if ship['name']]
                         )

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        
        self._check_main_partner(cr, uid, ids, vals, context=context)
        bro_uid = self.pool.get('res.users').browse(cr,uid,uid)
        bro = bro_uid.company_id
        res =  bro and bro.partner_id and bro.partner_id.id

        # Avoid the modification of the main partner linked to the company
        if not context.get('from_config') and res and res in ids:
            for field in ['name', 'partner_type', 'customer', 'supplier']:
                if field in vals:
                    del vals[field]
        # [utp-315] avoid deactivating partner that have still open document linked to them
        if 'active' in vals and vals.get('active') == False:
            objects_linked_to_partner = self.get_objects_for_partner(cr, uid, ids, context)
            if objects_linked_to_partner:
                raise osv.except_osv(_('Warning'),
                                     _("""The following documents linked to the partner need to be closed before deactivating the partner: %s"""
                                       ) % (objects_linked_to_partner))
        return super(res_partner, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if 'partner_type' in vals and vals['partner_type'] in ('internal', 'section', 'esc', 'intermission'):
            msf_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
            msf_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')
            if msf_customer and not 'property_stock_customer' in vals:
                vals['property_stock_customer'] = msf_customer[1]
            if msf_supplier and not 'property_stock_supplier' in vals:
                vals['property_stock_supplier'] = msf_supplier[1]
        return super(res_partner, self).create(cr, uid, vals, context=context)
    
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        Erase some unused data copied from the original object, which sometime could become dangerous, as in UF-1631/1632, 
        when duplicating a new partner (by button duplicate), or company, it creates duplicated currencies
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        fields_to_reset = ['ref_companies'] # reset this value, otherwise the content of the field triggers the creation of a new company
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        res = super(res_partner, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res

    def on_change_active(self, cr, uid, ids, active, context=None):
        """
        [utp-315] avoid deactivating partner that have still open document linked to them.
        """
        if not active:
            # some verifications
            if isinstance(ids, (int, long)):
                ids = [ids]
            if context is None:
                context = {}
            
            objects_linked_to_partner = self.get_objects_for_partner(cr, uid, ids, context)
            if objects_linked_to_partner:
                return {'value': {'active': True}, 
                        'warning': {'title': _('Error'), 
                                    'message': _("Some documents linked to this partner needs to be closed or canceled before deactivating the partner: %s"
                                                ) % (objects_linked_to_partner,)}}
        return {}

    def on_change_partner_type(self, cr, uid, ids, partner_type, sale_pricelist, purchase_pricelist):
        '''
        Change the procurement method according to the partner type
        '''
        price_obj = self.pool.get('product.pricelist')
        cur_obj = self.pool.get('res.currency')
        user_obj = self.pool.get('res.users')
        
        r = {'po_by_project': 'project'}
        
        if not partner_type or partner_type in ('external', 'internal'):
            r.update({'po_by_project': 'all'})
        
        sale_authorized_price = price_obj.search(cr, uid, [('type', '=', 'sale'), ('in_search', '=', partner_type)])
        if sale_authorized_price and sale_pricelist not in sale_authorized_price:
            r.update({'property_product_pricelist': sale_authorized_price[0]})
            
        purchase_authorized_price = price_obj.search(cr, uid, [('type', '=', 'purchase'), ('in_search', '=', partner_type)])
        if purchase_authorized_price and purchase_pricelist not in purchase_authorized_price:
            r.update({'property_product_pricelist_purchase': purchase_authorized_price[0]})
        
        if partner_type and partner_type in ('internal', 'section', 'esc', 'intermission'):
            msf_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
            if msf_customer:
                r.update({'property_stock_customer': msf_customer[1]})
            msf_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')
            if msf_supplier:
                r.update({'property_stock_supplier': msf_supplier[1]})
        else:
            other_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_customers')
            if other_customer:
                r.update({'property_stock_customer': other_customer[1]})
            other_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')
            if other_supplier:
                r.update({'property_stock_supplier': other_supplier[1]}) 
        
        return {'value': r}
    
    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Sort suppliers to have all suppliers in product form at the top of the list
        '''
        supinfo_obj = self.pool.get('product.supplierinfo')
        if context is None:
            context = {}
        if args is None:
            args = []
        
        # Get all supplier
        tmp_res = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
        if not context.get('product_id', False) or 'choose_supplier' not in context or count:
            return tmp_res
        else:
            # Get all supplier in product form
            args.append(('in_product', '=', True))
            res_in_prod = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
            new_res = []

            # Sort suppliers by sequence in product form
            if 'product_id' in context:
                supinfo_ids = supinfo_obj.search(cr, uid, [('name', 'in', res_in_prod), ('product_product_ids', '=', context.get('product_id'))], order='sequence')
            
                for result in supinfo_obj.read(cr, uid, supinfo_ids, ['name']):
                    try:
                        tmp_res.remove(result['name'][0])
                        new_res.append(result['name'][0])
                    except:
                        pass

            #return new_res  # comment this line to have all suppliers (with suppliers in product form at the top of the list)

            new_res.extend(tmp_res)
            
            return new_res

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

