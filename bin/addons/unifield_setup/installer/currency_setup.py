# -*- coding: utf-8 -*-
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
from tools.translate import _


class currency_setup(osv.osv_memory):
    _name = 'currency.setup'
    _inherit = 'res.config'

    _columns = {
        'functional_id': fields.selection([('eur', 'EUR'), ('chf', 'CHF')], string='Functional currency',
                                          required=True),
        'esc_id': fields.many2one('res.currency', string="ESC Currency", readonly=True),
        'section_id': fields.selection([('eur', 'EUR'), ('chf', 'CHF')], string='Section currency',
                                       readonly=True),
        'second_time': fields.boolean('Config. Wizard launched for the second time'),
    }

    _defaults = {
        'second_time': lambda *a: False,
    }

    def functional_on_change(self, cr, uid, ids, currency_id, context=None):
        return {'value': {'section_id': currency_id}}

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        if context is None:
            context = {}
        '''
        Display the default value for delivery process
        '''
        res = super(currency_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        esc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'EUR')[1]

        if company_id.currency_id.id == esc_id:
            res['functional_id'] = 'eur'
        else:
            res['functional_id'] = 'chf'
        res['second_time'] = company_id and company_id.second_time or False
        res['esc_id'] = esc_id
        res['section_id'] = res['functional_id']
        return res

    def execute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['from_setup'] = True
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)

        if payload.functional_id == 'eur':
            cur_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'EUR')[1]
        else:
            cur_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'CHF')[1]

        if not self.pool.get('res.currency').read(cr, uid, cur_id, ['active'], context=context)['active']:
            self.pool.get('res.currency').write(cr, uid, cur_id, {'active': True}, context=context)

        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id

        if not payload.second_time:
            self.pool.get('res.company').write(cr, uid, [company_id], {'currency_id': cur_id, 'second_time': True}, context=context)
        else:
            self.pool.get('res.company').write(cr, uid, [company_id], {'currency_id': cur_id,}, context=context)

        # Search the sale and purchase pricelists for this currency
        sale_price_id = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'sale'), ('currency_id', '=', cur_id)])
        if not sale_price_id:
            raise osv.except_osv(_('Error'), _('No pricelist found for this currency !'))

        purchase_price_id = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'purchase'), ('currency_id', '=', cur_id)])
        if not purchase_price_id:
            raise osv.except_osv(_('Error'), _('No pricelist found for this currency !'))

        # Change the currencies on all internal partners
        partner_ids = self.pool.get('res.partner').search(cr, uid, [('partner_type', 'in', ['internal', 'intermission']), ('active', 'in', ['t', 'f'])])
        self.pool.get('res.partner').write(cr, uid, partner_ids, {'property_product_pricelist': sale_price_id[0],
                                                                  'property_product_pricelist_purchase': purchase_price_id[0]})

        # Modify the currency on some already created objects
        # product_price_type
        price_type_ids = self.pool.get('product.price.type').search(cr, uid, [('currency_id', '=', 1)])
        self.pool.get('product.price.type').write(cr, uid, price_type_ids, {'currency_id': cur_id})

        # account.analytic.account
        analytic_ids = self.pool.get('account.analytic.account').search(cr, uid, [('currency_id', '=', 1)])
        # use a for to avoid a recursive account error
        for analytic_id in analytic_ids:
            self.pool.get('account.analytic.account').write(cr, uid, [analytic_id], {'currency_id': cur_id}, context={'lang': 'en_MF'})

        # product.product
        # UF-1766 : Pass out the OpenObject framework to gain time on currency change with a big amount of products
        cr.execute('UPDATE product_product SET currency_id = %s, field_currency_id = %s', (cur_id, cur_id))
#        product_ids = self.pool.get('product.product').search(cr, uid, [('currency_id', '=', 1)])
#        product2_ids = self.pool.get('product.product').search(cr, uid, [('field_currency_id', '=', 1)])
#        self.pool.get('product.product').write(cr, uid, product_ids, {'currency_id': cur_id})
#        self.pool.get('product.product').write(cr, uid, product2_ids, {'field_currency_id': cur_id})

        # account.model
        model_ids = self.pool.get('account.model').search(cr, uid, [('currency_id', '=', 1)])
        self.pool.get('account.model').write(cr, uid, model_ids, {'currency_id': cur_id})

        # account.mcdb
        mcdb_ids = self.pool.get('account.mcdb').search(cr, uid, [('currency_id', '=', 1)])
        self.pool.get('account.mcdb').write(cr, uid, mcdb_ids, {'currency_id': cur_id})

currency_setup()
