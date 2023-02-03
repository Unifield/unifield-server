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
from account_override import ACCOUNT_RESTRICTED_AREA
from msf_field_access_rights.osv_override import _get_instance_level
import time
from tools.translate import _
from lxml import etree
from msf_field_access_rights.osv_override import _record_matches_domain

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
        if context is None:
            context = {}

        partner_price = self.pool.get('pricelist.partnerinfo')
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long, )):
            ids = [ids]

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
                # now is used, OST partner view
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
                    res[partner.id] = {'price_currency': currency,
                                       'price_unit': price,
                                       'valide_until_date': info_price.valid_till}

        return res


    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VA management is set to True
        '''
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long, )):
            ids = [ids]

        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid,).vat_ok
        for id in ids:
            res[id] = vat_ok

        return res

    def _get_is_instance(self, cr, uid, ids, field_name, args, context=None):
        """ return the instance's partner id """
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long, )):
            ids = [ids]

        partner_id = False
        user = self.pool.get('res.users').browse(cr, uid, [uid],
                                                 context=context)[0]
        if user and user.company_id and user.company_id.partner_id:
            partner_id = user.company_id.partner_id.id

        for id in ids:
            res[id] = partner_id and id == partner_id or False
        return res

    def _get_is_instance_search(self, cr, uid, ids, field_name, args,
                                context=None):
        """ search the instance's partner id """
        partner_id = False
        user = self.pool.get('res.users').browse(cr, uid, [uid],
                                                 context=context)[0]
        if user and user.company_id and user.company_id.partner_id:
            partner_id = user.company_id.partner_id.id
        return partner_id and [('id', '=', partner_id)] or []

    def _get_is_coordo(self, cr, uid, ids, field_name, args, context=None):
        """ return True if the instance's level is coordo """
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long,)):
            ids = [ids]

        for id in ids:
            res[id] = False

        inst_level = _get_instance_level(self, cr, uid)
        if inst_level != 'coordo':
            return res

        inst_partner_id = self.search(cr, uid, [('is_instance', '=', True)], context=context)
        if inst_partner_id and inst_partner_id[0] in ids:
            res[inst_partner_id[0]] = True

        return res

    def _get_is_coordo_search(self, cr, uid, ids, field_name, args,
                              context=None):
        """ return partner which are coordination and current company partner """
        a = args[0]
        if _get_instance_level(self, cr, uid) != 'coordo':
            if a[1] in ('=', 'in'):
                if a[2] in ('True', 'true', True, 1, 't'):
                    return [('id', 'in', [])]
                elif a[2] in ('False', 'false', False, 0, 'f'):
                    return []
            elif a[1] in ('<>', '!=', 'not in'):
                if a[2] in ('True', 'true', True, 1, 't'):
                    return []
                elif a[2] in ('False', 'false', False, 0, 'f'):
                    return [('id', 'in', [])]
            else:
                return []

        if a[1] in ('=', 'in'):
            if a[2] in ('True', 'true', True, 1, 't'):
                operator = 'in'
            elif a[2] in ('False', 'false', False, 0, 'f'):
                operator = 'not in'
        elif a[1] in ('<>', '!=', 'not in'):
            if a[2] in ('True', 'true', True, 1, 't'):
                operator = 'not in'
            elif a[2] in ('False', 'false', False, 0, 'f'):
                operator = 'in'
        else:
            return []

        return [('id', operator, self.search(cr, uid, [('is_instance', '=', True)], context=context))]

    _columns = {
        'manufacturer': fields.boolean(string='Manufacturer', help='Check this box if the partner is a manufacturer'),
        'partner_type': fields.selection(PARTNER_TYPE, string='Partner type', required=True),
        'split_po': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
            ],
            string='Split PO ?',
        ),
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
        'property_stock_customer': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string='Customer Location',
            method=True,
            view_load=True,
            required=True,
            help="This stock location will be used, instead of the default one, as the destination location for goods you send to this partner.",
        ),
        'property_stock_supplier': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string='Supplier Location',
            method=True,
            view_load=True,
            required=True,
            help="This stock location will be used, instead of the default one, as the source location for goods you receive from the current partner.",
        ),
        'price_unit': fields.function(_get_price_info, method=True, type='float', string='Unit price', multi='info'),
        'valide_until_date' : fields.function(_get_price_info, method=True, type='char', string='Valid until date', multi='info'),
        'price_currency': fields.function(_get_price_info, method=True, type='many2one', relation='res.currency', string='Currency', multi='info'),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'is_instance': fields.function(_get_is_instance, fnct_search=_get_is_instance_search, method=True, type='boolean', string='Is current instance partner id'),
        'transporter': fields.boolean(string='Transporter'),
        'is_coordo': fields.function(
            _get_is_coordo,
            fnct_search=_get_is_coordo_search,
            method=True,
            type='boolean',
            string='Is a coordination ?',
        ),
        'locally_created': fields.boolean('Locally Created', help='Partner Created on this instance', readonly=1),
        'instance_creator': fields.char('Instance Creator', size=64, readonly=1),
    }

    _defaults = {
        'locally_created': lambda *a: True,
        'manufacturer': lambda *a: False,
        'transporter': lambda *a: False,
        'partner_type': lambda *a: 'external',
        'split_po': lambda *a: False,
        'vat_ok': lambda obj, cr, uid, c: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'instance_creator': lambda obj, cr, uid, c: obj._get_instance_creator(cr, uid, c),
    }

    def _get_instance_creator(self, cr, uid, context=None):
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            entity_obj = self.pool.get('sync.client.entity')
            if entity_obj:
                return entity_obj.get_entity(cr, uid).name
        return False

    def update_exported_fields(self, cr, uid, fields):
        res = super(res_partner, self).update_exported_fields(cr, uid, fields)
        if res:
            res.append(['instance_creator', _('Instance Creator')])
        return res

    def check_pricelists_vals(self, cr, uid, vals, context=None):
        """
        Put the good pricelist on the good field
        """
        pricelist_obj = self.pool.get('product.pricelist')
        pppp_id = vals.get('property_product_pricelist_purchase', False)
        ppp_id = vals.get('property_product_pricelist', False)

        if pppp_id:
            pppp = pricelist_obj.browse(cr, uid, pppp_id, context=context)
            if pppp.type != 'purchase':
                purchase_pricelists = pricelist_obj.search(cr, uid, [
                    ('currency_id', '=', pppp.currency_id.id),
                    ('type', '=', 'purchase'),
                ], context=context)
                if purchase_pricelists:
                    vals['property_product_pricelist_purchase'] = purchase_pricelists[0]

        if ppp_id:
            ppp = pricelist_obj.browse(cr, uid, ppp_id, context=context)
            if ppp.type != 'sale':
                sale_pricelists = pricelist_obj.search(cr, uid, [
                    ('currency_id', '=', ppp.currency_id.id),
                    ('type', '=', 'sale'),
                ], context=context)
                if sale_pricelists:
                    vals['property_product_pricelist'] = sale_pricelists[0]

        return vals

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted partner is not a system one
        """
        property_obj = self.pool.get('ir.property')


        #US-1344: treat deletion of partner
        address_obj = self.pool.get('res.partner.address')
        address_ids = address_obj.search(cr, uid, [('partner_id', 'in', ids)])

        res = super(res_partner, self).unlink(cr, uid, ids, context=context)
        ir_model_data_obj = self.pool.get('ir.model.data')

        address_obj.unlink(cr, uid, address_ids, context)

        # delete the related fields.properties
        property_fields = ['property_account_receivable', 'property_account_payable', 'property_product_pricelist',
                           'property_product_pricelist_purchase', 'property_stock_supplier',
                           'property_stock_customer', 'property_account_position', 'property_payment_term']
        res_ids = []
        for partner_id in ids:
            res_id = 'res.partner,%s' % partner_id
            res_ids.append(res_id)
        property_domain = [('name', 'in', property_fields), ('res_id', 'in', res_ids)]
        property_ids = property_obj.search(cr, uid, property_domain, order='NO_ORDER', context=context)
        property_obj.unlink(cr, uid, property_ids, context=context)

        mdids = ir_model_data_obj.search(cr, 1, [('model', '=', 'res.partner'), ('res_id', 'in', ids)])
        ir_model_data_obj.unlink(cr, uid, mdids, context)
        return res

    def _check_main_partner(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        bro_uid = self.pool.get('res.users').browse(cr,uid,uid)

        bro = bro_uid.company_id
        res =  bro and bro.partner_id and bro.partner_id.id

        if res in ids:
            for obj in self.browse(cr, uid, [res], context=context):

                if obj.customer:
                    raise osv.except_osv(_('Warning !'), _('This partner can not be checked as customer'))

                if obj.supplier:
                    raise osv.except_osv(_('Warning !'), _('This partner can not be checked as supplier'))

        return True

    def check_partner_name_is_not_instance_name(self, cr, uid, ids, context=None):
        '''
        verify that the name of the partner is not used by another partner
        of partner_type ('section', 'intermission')
        Except if the partner name is equal to the partner related to the
        current instance.
        Return False if the name already exists
        '''
        if context is None:
            context = {}

        # check if the current partner name is equal to the current instance name
        user_obj = self.pool.get('res.users')
        partner_id, partner_name = user_obj.get_current_company_partner_id(cr, uid)

        # remove partner which have same name than the current instance
        read_result = self.read(cr, uid, ids, ['name', 'partner_type'], context=context)
        read_result = [(x['id'], x['name'], x['partner_type']) for x in read_result if x['name'] != partner_name]

        for partner_id, partner_name, partner_type in read_result:

            # US-3166: the constraint do not apply to the internal partners
            if partner_type == 'internal':
                continue

            # check the current name is not already used by another section or
            # intermission partner
            name_exists = self.search_exist(cr, uid, [
                ('id', '!=', partner_id),
                ('name', '=', partner_name),
                ('active', 'in', ('t', 'f')),
                ('partner_type', 'in', ('section', 'intermission'))], context=context)
            if name_exists:
                return False
        return True

    _constraints = [
        (check_partner_name_is_not_instance_name,
            "You can't define a partner name with the name of an existing Intermission/Intersection instance name.",
            ['name'])
    ]

    def transporter_ticked(self, cr, uid, ids, transporter, context=None):
        """
        If the transporter box is ticked, automatically ticked the supplier
        box.
        """
        if transporter:
            return {'value': {'supplier': True}}
        return {}

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
        absl_obj = self.pool.get('account.bank.statement.line') # for register lines
        aml_obj = self.pool.get('account.move.line')

        # ids list (the domain are the same as the one used for the action window of the menus)
        purchase_ids = purchase_obj.search(cr, uid,
                                           [('rfq_ok', '=', False), ('partner_id', '=', ids[0]), ('state', 'not in', ['done', 'cancel'])],
                                           context=context.update({'purchase_order': True}))
        rfq_ids = purchase_obj.search(cr, uid,
                                      [('rfq_ok', '=', True), ('partner_id', '=', ids[0]), ('rfq_state', 'not in', ['done', 'cancel'])],
                                      context=context.update({'request_for_quotation': True}))
        sale_ids = sale_obj.search(cr, uid,
                                   [('procurement_request', '=', False), ('partner_id', '=', ids[0]), ('state', 'not in', ['done', 'cancel'])],
                                   context=context)

        intermission_vouch_in_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'ivi'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        intermission_vouch_out_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'ivo'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        donation_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'donation'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        supp_invoice_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'si'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        sr_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'sr'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        isi_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'isi'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        isr_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'isr'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        str_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'str'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        cust_refunds_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'cr'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        debit_note_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'dn'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        stock_transfer_vouch_ids = account_invoice_obj.search(cr, uid, [
            ('doc_type', '=', 'stv'), ('partner_id', '=', ids[0]), ('state', 'in', ['draft'])
        ])

        incoming_ship_ids = pick_obj.search(cr, uid, [
            ('state', 'not in', ['done', 'cancel']), ('type', '=', 'in'), ('subtype', '=', 'standard'),
            '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
        ], context = context.update({
            'contact_display': 'partner_address', 'subtype': 'in', 'picking_type': 'incoming_shipment', 'search_default_available':1
        }))
        out_ids = pick_obj.search(cr, uid, [
            ('state', 'not in', ['done', 'delivered', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'standard'),
            '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
        ], context = context.update({
            'contact_display': 'partner_address', 'search_default_available': 1,'picking_type': 'delivery_order', 'subtype': 'standard'
        }))
        pick_ids = pick_obj.search(cr, uid, [
            ('state', 'not in', ['done', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'picking'),
            '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
        ], context = context.update({
            'picking_screen':True, 'picking_type': 'picking_ticket', 'test':True, 'search_default_not_empty':1
        }))
        ppl_ids = pick_obj.search(cr, uid, [
            ('state', 'not in', ['done', 'cancel']), ('type', '=', 'out'), ('subtype', '=', 'ppl'),
            '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])
        ], context=context.update({
            'contact_display': 'partner_address', 'ppl_screen':True, 'picking_type': 'picking_ticket', 'search_default_available':1
        }))
        tender_ids = [tend for tend in tender_obj.search(cr, uid, [('state', '=', 'comparison')]) if ids[0] in tender_obj.read(cr, uid, tend, ['supplier_ids'])['supplier_ids']]
        com_vouch_ids = com_vouch_obj.search(cr, uid, [('partner_id', '=', ids[0]), ('state', '!=', 'done')], context=context)
        ship_ids = ship_obj.search(cr, uid,
                                   [('state', 'not in', ['done', 'delivered']), '|', ('partner_id', '=', ids[0]), ('partner_id2', '=', ids[0])],
                                   context=context)
        absl_ids = absl_obj.search(cr, uid, [('state', 'in', ['draft', 'temp']), ('partner_id', '=', ids[0])], context=context)
        aml_ids = aml_obj.search(cr, uid, [('partner_id', '=', ids[0]), ('reconcile_id', '=', False), ('account_id.reconcile', '=', True)])

        return ', '.join([
            po['name']+_(' (Purchase)') for po in purchase_obj.read(cr, uid, purchase_ids, ['name'], context) if po['name']]
            +[rfq['name']+_(' (RfQ)') for rfq in purchase_obj.read(cr, uid, rfq_ids, ['name'], context) if rfq['name']]
            +[so['name']+_(' (Field Order)') for so in sale_obj.read(cr, uid, sale_ids, ['name'], context) if so['name']]
            +(intermission_vouch_in_ids and [_('%s Intermission Voucher IN') % (len(intermission_vouch_in_ids),)] or [])
            +(intermission_vouch_out_ids and [_('%s Intermission Voucher OUT') % (len(intermission_vouch_out_ids),)] or [])
            +(donation_ids and [_('%s Donation(s)') % (len(donation_ids),)] or [])
            +(supp_invoice_ids and [_('%s Supplier Invoice(s)') % (len(supp_invoice_ids), )] or [])
            + (sr_ids and [_('%s Supplier Refund(s)') % (len(sr_ids),)] or [])
            + (isi_ids and [_('%s Intersection Supplier Invoice(s)') % (len(isi_ids),)] or [])
            + (isr_ids and [_('%s Intersection Supplier Refund(s)') % (len(isr_ids),)] or [])
            + (str_ids and [_('%s Stock Transfer Refund(s)') % (len(str_ids),)] or [])
            +(cust_refunds_ids and [_('%s Customer Refund(s)') % (len(cust_refunds_ids), )] or [])
            +(debit_note_ids and [_('%s Debit Note(s)') % (len(debit_note_ids), )] or [])
            +(stock_transfer_vouch_ids and [_('%s Stock Transfer Voucher(s)') % (len(stock_transfer_vouch_ids),)] or [])
            +[inc_ship['name']+_(' (Incoming Shipment)') for inc_ship in pick_obj.read(cr, uid, incoming_ship_ids, ['name'], context) if inc_ship['name']]
            +[out['name']+_(' (OUT)') for out in pick_obj.read(cr, uid, out_ids, ['name'], context) if out['name']]
            +[pick['name']+_(' (PICK)') for pick in pick_obj.read(cr, uid, pick_ids, ['name'], context) if pick['name']]
            +[ppl['name']+_(' (PPL)') for ppl in pick_obj.read(cr, uid, ppl_ids, ['name'], context) if ppl['name']]
            +[tend['name']+_(' (Tender)') for tend in tender_obj.read(cr, uid, tender_ids, ['name'], context) if tend['name']]
            +[com_vouch['name']+_(' (Commitment Voucher)') for com_vouch in com_vouch_obj.read(cr, uid, com_vouch_ids, ['name'], context) if com_vouch['name']]
            +[ship['name']+_(' (Shipment)') for ship in ship_obj.read(cr, uid, ship_ids, ['name'], context) if ship['name']]
            # Note: DI are seen at register level
            +[absl.name + '(' + absl.statement_id.name + _(' Register)') for absl in absl_obj.browse(cr, uid, absl_ids, context) if absl.name and absl.statement_id and absl.statement_id.name]
            +[_('%s (Journal Item)') % (aml['move_id'] and aml['move_id'][1] or '') for aml in aml_obj.read(cr, uid, aml_ids, ['move_id'])]
        )

    def check_partner_unicity(self, cr, uid, partner_id, context=None):
        """
        If the partner name is already used, check that the city is not empty AND not used by another partner with the
        same name. Checks are case insensitive, done with active and inactive External partners, and NOT done at synchro time.
        """

        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            address_obj = self.pool.get('res.partner.address')
            partner = self.browse(cr, uid, partner_id, fields_to_fetch=['partner_type', 'name', 'city'], context=context)
            if partner.partner_type == 'external':
                city = partner.city or ''  # city of the first address created for this partner
                partner_domain = [('id', '!=', partner_id), ('name', '=ilike', partner.name),
                                  ('partner_type', '=', 'external'), ('active', 'in', ['t', 'f'])]
                duplicate_partner_ids = self.search(cr, uid, partner_domain, order='NO_ORDER', context=context)
                if duplicate_partner_ids:
                    address_ids = address_obj.search(cr, uid, [('partner_id', 'in', duplicate_partner_ids)],
                                                     context=context, order='NO_ORDER')
                    if not city or address_obj.search_exist(cr, uid, [('id', 'in', address_ids),
                                                                      ('city', '=ilike', city)], context=context):
                        raise osv.except_osv(_('Warning'),
                                             _("The partner can't be saved because already exists under the same name for "
                                               "the same city. Please change the partner name or city or use the existing partner."))

    def _check_default_accounts(self, cr, uid, vals, context=None):
        """
        Checks if the property_account_receivable and property_account_payable in vals are allowed based on the domains
        stored in ACCOUNT_RESTRICTED_AREA. If not raises a warning.
        """
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            account_obj = self.pool.get('account.account')
            if vals.get('property_account_receivable'):
                receivable_domain = [('id', '=', vals['property_account_receivable'])]
                receivable_domain.extend(ACCOUNT_RESTRICTED_AREA['partner_receivable'])
                if not account_obj.search_exist(cr, uid, receivable_domain, context=context):
                    receivable_acc = account_obj.browse(cr, uid, vals['property_account_receivable'], fields_to_fetch=['code', 'name'], context=context)
                    raise osv.except_osv(_('Error'), _('The account %s - %s cannot be used as Account Receivable.') % (receivable_acc.code, receivable_acc.name))
            if vals.get('property_account_payable'):
                payable_domain = [('id', '=', vals['property_account_payable'])]
                payable_domain.extend(ACCOUNT_RESTRICTED_AREA['partner_payable'])
                if not account_obj.search_exist(cr, uid, payable_domain, context=context):
                    payable_acc = account_obj.browse(cr, uid, vals['property_account_payable'], fields_to_fetch=['code', 'name'], context=context)
                    raise osv.except_osv(_('Error'), _('The account %s - %s cannot be used as Account Payable.') % (payable_acc.code, payable_acc.name))

    def check_same_pricelist(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if context.get('sync_update_execution'):
            return True

        curr_obj = self.pool.get('res.currency')
        section_curr = curr_obj.search(cr, uid, [('is_section_currency', '=', True)])
        curr_id = self.pool.get('res.users').browse(cr, uid, uid,fields_to_fetch=['company_id'], context=context).company_id.currency_id.id

        for x in self.browse(cr, uid, ids, fields_to_fetch=['property_product_pricelist_purchase', 'property_product_pricelist', 'name', 'partner_type'], context=context):
            ko_cur = False
            if x.partner_type == 'section' and x.property_product_pricelist_purchase and x.property_product_pricelist_purchase.currency_id.id not in section_curr:
                ko_cur = x.property_product_pricelist_purchase.currency_id.name
            elif  x.partner_type == 'section' and x.property_product_pricelist and x.property_product_pricelist.currency_id.id not in section_curr:
                ko_cur = x.property_product_pricelist.currency_id.name
            elif x.partner_type == 'intermission' and x.property_product_pricelist_purchase and x.property_product_pricelist_purchase.currency_id.id != curr_id:
                ko_cur = x.property_product_pricelist_purchase.currency_id.name
            elif x.partner_type == 'intermission' and x.property_product_pricelist and x.property_product_pricelist.currency_id.id != curr_id:
                ko_cur = x.property_product_pricelist.currency_id.name

            if ko_cur:
                raise osv.except_osv(_('Warning'),
                                     _('Partner %s (%s): you can not use %s currency') % (x.name, x.partner_type, ko_cur))

            if x.property_product_pricelist_purchase and x.property_product_pricelist and x.property_product_pricelist_purchase.currency_id.id != x.property_product_pricelist.currency_id.id:
                raise osv.except_osv(_('Warning'),
                                     _('Partner %s : Purchase Default Currency (%s) and Field Orders Default Currency (%s) must be the same') % (x.name, x.property_product_pricelist_purchase.currency_id.name, x.property_product_pricelist.currency_id.name)
                                     )

        return True

    def _check_existing_tax_partner(self, cr, uid, ids, context=None):
        """
        Raises an error in case the partner has been used in a tax (to be used when trying to de-activate partners)
        """
        if context is None:
            context = {}
        tax_obj = self.pool.get('account.tax')
        inv_obj = self.pool.get('account.invoice')
        inv_tax_obj = self.pool.get('account.invoice.tax')
        if tax_obj.search_exist(cr, uid, [('partner_id', 'in', ids)], context=context):
            raise osv.except_osv(_('Warning'),
                                 _("Impossible to deactivate a partner used for a tax."))
        # use case: partner linked to a tax, related tax lines generated and partner removed from the tax
        # Note that only draft account.invoices need to be checked as other ones have generated JIs (so are already checked)
        draft_invoice_ids = inv_obj.search(cr, uid, [('state', '=', 'draft')], order='NO_ORDER', context=context)
        if draft_invoice_ids:
            if inv_tax_obj.search_exist(cr, uid, [('partner_id', 'in', ids), ('invoice_id', 'in', draft_invoice_ids)], context=context):
                raise osv.except_osv(_('Warning'),
                                     _("Impossible to deactivate a partner used in the tax line of an invoice."))

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        vals = self.check_pricelists_vals(cr, uid, vals, context=context)
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}

        #US-126: when it's an update from the sync, then just remove the forced 'active' parameter
        if context.get('sync_update_execution', False):
            for to_remove in ['active', 'po_by_project', 'manufacturer', 'transporter']:
                if to_remove in vals:
                    del vals[to_remove]

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
            # UTP-1214: only show error message if it is really a "deactivate partner" action, if not, just ignore
            oldValue = self.read(cr, uid, ids[0], ['active'], context=context)['active']
            if oldValue == True: # from active to inactive ---> check if any ref to it
                objects_linked_to_partner = self.get_objects_for_partner(cr, uid, ids, context)
                if objects_linked_to_partner:
                    raise osv.except_osv(_('Warning'),
                                         _("""The following documents linked to the partner need to be closed before deactivating the partner: %s"""
                                           ) % (objects_linked_to_partner))
                self._check_existing_tax_partner(cr, uid, ids, context=context)

        if vals.get('name'):
            vals['name'] = vals['name'].replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').strip()

        if vals.get('active') and vals.get('partner_type') == 'intermission' and vals.get('name') \
                and self.search(cr, uid, [('id', '!=', ids[0]), ('name', '=ilike', vals['name']), ('partner_type', '=', 'internal')], context=context):
            raise osv.except_osv(_('Error'), _("There is already an Internal Partner with the name '%s'. The Intermission Partner could not be modified and activated") % (vals['name'],))

        ret = super(res_partner, self).write(cr, uid, ids, vals, context=context)
        self.check_same_pricelist(cr, uid, ids, context=context)
        return ret

    def need_to_push(self, cr, uid, ids, touched_fields=None, field='sync_date', empty_ids=False, context=None):
        '''
            bo_py_poject field must not trigger an sync update
        '''
        ignore = ['po_by_project', 'manufacturer', 'transporter']
        if touched_fields and set(ignore).intersection(touched_fields):
            touched_fields = [x for x in touched_fields if x not in ignore]
        return super(res_partner, self).need_to_push(cr, uid, ids, touched_fields=touched_fields, field=field, empty_ids=empty_ids, context=context)

    def create(self, cr, uid, vals, context=None):
        fields_to_create = vals.keys()

        if context is None:
            context = {}
        vals = self.check_pricelists_vals(cr, uid, vals, context=context)
        self._check_default_accounts(cr, uid, vals, context=context)
        if 'partner_type' in vals and vals['partner_type'] in ('internal', 'section', 'esc', 'intermission'):
            msf_customer = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
            msf_supplier = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_suppliers')
            if msf_customer and not 'property_stock_customer' in vals:
                vals['property_stock_customer'] = msf_customer[1]
            if msf_supplier and not 'property_stock_supplier' in vals:
                vals['property_stock_supplier'] = msf_supplier[1]

            if vals.get('partner_type') == 'esc':
                eur_cur = self.pool.get('res.currency').search(cr, uid, [('name', '=', 'EUR')], context=context)
                if eur_cur:
                    pl_ids = self.pool.get('product.pricelist').search(cr, uid, [('currency_id', 'in', eur_cur)], context=context)
                    for pl in self.pool.get('product.pricelist').browse(cr, uid, pl_ids, context=context):
                        if pl.type == 'sale':
                            vals['property_product_pricelist'] = pl.id
                        elif pl.type == 'purchase':
                            vals['property_product_pricelist_purchase'] = pl.id

        if not context.get('sync_update_execution') and not vals.get('address'):
            vals['address'] = [(0, 0, {'function': False, 'city': False, 'fax': False, 'name': False, 'zip': False, 'title': False, 'mobile': False, 'street2': False, 'country_id': False, 'phone': False, 'street': False, 'active': True, 'state_id': False, 'type': False, 'email': False})]

        if vals.get('name'):
            vals['name'] = vals['name'].replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').strip()

        if vals.get('active') and vals.get('partner_type') == 'intermission' and vals.get('name') \
                and self.search(cr, uid, [('name', '=ilike', vals['name']), ('partner_type', '=', 'internal')], context=context):
            raise osv.except_osv(_('Error'), _("There is already an Internal Partner with the name '%s'. The Intermission Partner could not be created and activated") % (vals['name'],))

        new_id = super(res_partner, self).create(cr, uid, vals, context=context)
        self.check_partner_unicity(cr, uid, partner_id=new_id, context=context)
        self.check_same_pricelist(cr, uid, [new_id], context=context)
        # US-3945: checking user's rights
        if not context.get('sync_update_execution') and uid != 1:
            instance_level = _get_instance_level(self, cr, uid)

            if instance_level:  # get rules for this model, instance and user
                model_name = self._name
                groups = self.pool.get('res.users').read(cr, 1, uid, ['groups_id'], context=context)['groups_id']

                rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
                if not rules_pool:
                    return new_id

                rules_search = rules_pool.search(cr, 1, ['&', ('model_name', '=', model_name),
                                                         ('instance_level', '=', instance_level), '|',
                                                         ('group_ids', 'in', groups), ('group_ids', '=', False)])

                # do we have rules that apply to this user and model?
                if rules_search:
                    # for each rule, check the record against the rule domain.
                    rules_to_check = []
                    for rule in rules_pool.read(cr, uid, rules_search, ['domain_text']):
                        dom = rule['domain_text']
                        if isinstance(dom, (str, unicode)):
                            dom = eval(rule['domain_text'])
                            if not isinstance(dom, bool) and dom:
                                dom = ['&', ('active','in', ['t', 'f'])] + dom

                        if _record_matches_domain(self, cr, new_id, dom):
                            rules_to_check.append(rule['id'])
                    if rules_to_check:
                        # get the fields with write_access=False
                        cr.execute("""SELECT DISTINCT field_name
                              FROM msf_field_access_rights_field_access_rule_line
                              WHERE write_access='f' AND
                              field_access_rule in %s AND
                              field_name in %s
                              limit 1
                        """, (tuple(rules_to_check), tuple(fields_to_create)))

                        x = cr.fetchone()
                        if x:
                            # throw access denied error
                            raise osv.except_osv(_('Access Denied'),
                                                 _('You do not have access to the field (%s). If you did not edit this field, please let an OpenERP administrator know about this error message, and the field name.') % (x[0], )
                                                 )

        return new_id


    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        Erase some unused data copied from the original object, which sometime could become dangerous, as in UF-1631/1632,
        when duplicating a new partner (by button duplicate), or company, it creates duplicated currencies
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        fields_to_reset = ['ref_companies', 'instance_creator'] # reset this value, otherwise the content of the field triggers the creation of a new company
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)

        if 'locally_created' not in default:
            default['locally_created'] = True

        res = super(res_partner, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res

    def on_change_active(self, cr, uid, ids, active, name, partner_type, context=None):
        """
        [utp-315] avoid deactivating partner that have still open document linked to them.
        """
        # some verifications
        if not ids:
            return {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # UF-2463: If the partner is not saved into the system yet, just ignore this check
        if not active:
            if context is None:
                context = {}

            objects_linked_to_partner = self.get_objects_for_partner(cr, uid, ids, context)
            if objects_linked_to_partner:
                return {'value': {'active': True},
                        'warning': {'title': _('Error'),
                                    'message': _("Some documents linked to this partner need to be closed or cancelled before deactivating the partner: %s"
                                                 ) % (objects_linked_to_partner,)}}
        else:
            if partner_type == 'intermission' and self.search(cr, uid, [('id', '!=', ids[0]), ('name', '=ilike', name), ('partner_type', '=', 'internal')], context=context):
                return {
                    'value': {'active': False},
                    'warning': {
                        'title': _('Error'),
                        'message': _("There is already an Internal Partner with the name '%s'. The Intermission Partner could not be activated") % (name,)
                    }
                }
            # US-49 check that activated partner is not using a not active CCY
            check_pricelist_ids = []
            fields_pricelist = [
                'property_product_pricelist_purchase',
                'property_product_pricelist'
            ]
            check_ccy_ids = []
            for r in self.read(cr, uid, ids, fields_pricelist,
                               context=context):
                for f in fields_pricelist:
                    if r[f] and r[f][0] not in check_pricelist_ids:
                        check_pricelist_ids.append(r[f][0])
            if check_pricelist_ids:
                for cpl_r in self.pool.get('product.pricelist').read(cr,
                                                                     uid, check_pricelist_ids, ['currency_id'],
                                                                     context=context):
                    if cpl_r['currency_id'] and \
                            cpl_r['currency_id'][0] not in check_ccy_ids:
                        check_ccy_ids.append(cpl_r['currency_id'][0])
                if check_ccy_ids:
                    count = self.pool.get('res.currency').search(cr, uid, [
                        ('active', '!=', True),
                        ('id', 'in', check_ccy_ids),
                    ], count=True, context=context)
                    if count:
                        return {
                            'value': {'active': False},
                            'warning': {
                                'title': _('Error'),
                                'message': _('PO or FO currency is not active'),
                            }
                        }
        return {}

    def on_change_partner_type(self, cr, uid, ids, partner_type, sale_pricelist, purchase_pricelist):
        '''
        Change the procurement method according to the partner type
        '''
        price_obj = self.pool.get('product.pricelist')

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

        if partner_type and partner_type == 'esc':
            r['zone'] = 'international'

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

        # To get the correct offset
        args_in_product = args[:]  # copy the list by slicing
        args_in_product.append(('in_product', '=', True))
        if offset > 0:
            nb_res_in_prod = super(res_partner, self).search(cr, uid, args_in_product, None, limit, order,
                                                             context=context, count=True)
            offset -= nb_res_in_prod
            offset = offset > 0 and offset or 0

        # Get all supplier
        tmp_res = super(res_partner, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
        if not context.get('product_id', False) or 'choose_supplier' not in context or count:
            return tmp_res
        else:
            # Get all supplier in product form
            res_in_prod = super(res_partner, self).search(cr, uid, args_in_product, offset, limit, order,
                                                          context=context, count=count)
            new_res = []

            # Sort suppliers by sequence in product form
            if 'product_id' in context:
                supinfo_ids = supinfo_obj.search(cr, uid, [('name', 'in', res_in_prod), ('product_product_ids', '=', context.get('product_id'))], order='sequence')

                for result in supinfo_obj.read(cr, uid, supinfo_ids, ['name']):
                    try:
                        tmp_res.remove(result['name'][0])
                    except:
                        try:
                            tmp_res.pop()
                        except:
                            pass
                    finally:
                        new_res.append(result['name'][0])

            #return new_res  # comment this line to have all suppliers (with suppliers in product form at the top of the list)

            new_res.extend(tmp_res)

            return new_res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Show the button "Show inactive" in the partner search view only when we have in the context {'show_button_show_inactive':1}.
        """
        if not context:
            context = {}
        view = super(res_partner, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'search':
            if not context or not context.get('show_button_show_inactive', False):
                tree = etree.fromstring(view['arch'])
                fields = tree.xpath('//filter[@name="inactive"]|//filter[@name="active"]')
                for field in fields:
                    field.set('invisible', "1")
                view['arch'] = etree.tostring(tree)
        return view

res_partner()


class res_partner_address(osv.osv):
    _inherit = 'res.partner.address'

    _columns = {
        'office_name': fields.char(
            string='Office name',
            size=128,
        ),
    }

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted address is not a system one
        """
        res = super(res_partner_address, self).unlink(cr, uid, ids, context=context)

        #US-1344: treat deletion of partner
        ir_model_data_obj = self.pool.get('ir.model.data')
        mdids = ir_model_data_obj.search(cr, 1, [('model', '=', 'res.partner.address'), ('res_id', 'in', ids)])
        ir_model_data_obj.unlink(cr, uid, mdids, context)
        return res

    def create(self, cr, uid, vals, context=None):
        '''
        Remove empty addresses if exist and create the new one
        '''

        if vals.get('partner_id'):
            domain_dict = {
                'partner_id': vals.get('partner_id'),
                'function': False,
                'city': False,
                'fax': False,
                'name': False,
                'zip': False,
                'title': False,
                'mobile': False,
                'street2': False,
                'country_id': False,
                'phone': False,
                'street': False,
                'active': True,
                'state_id': False,
                'type': False,
                'email': False,
            }
            domain = [(k, '=', v) for k, v in domain_dict.iteritems()]
            addr_ids = self.search(cr, uid, domain, context=context)
            if addr_ids:
                if not self.is_linked(cr, uid, addr_ids):
                    self.unlink(cr, uid, addr_ids, context=context)
                else:
                    self.write(cr, uid, addr_ids, {'active': False}, context=context)

        return super(res_partner_address, self).create(cr, uid, vals, context=context)

res_partner_address()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

