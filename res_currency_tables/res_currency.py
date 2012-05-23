# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import fields, osv

class res_currency(osv.osv):
    _inherit = 'res.currency'
    _name = 'res.currency'

    _columns = {
        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table', ondelete='cascade'),
        'reference_currency_id': fields.many2one('res.currency', 'Reference Currency', ondelete='cascade'),
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name, currency_table_id)', 'The currency name exists already in the system!')
    ]
    
    def _get_table_currency(self, cr, uid, currency_id, table_id, context=None):
        source_currency = self.browse(cr, uid, currency_id, context=context)
        if not source_currency.reference_currency_id or not source_currency.currency_table_id :
            # "Real" currency; the one from the table is retrieved
            res = self.search(cr, uid, [('currency_table_id', '=', table_id), ('reference_currency_id', '=', currency_id)], context=context)
            if len(res) > 0:
                return res[0]
            else:
                return False
        elif source_currency.currency_table_id.id != table_id:
            # Reference currency defined, not the wanted table
            res = self.search(cr, uid, [('currency_table_id', '=', table_id), ('reference_currency_id', '=', source_currency.reference_currency_id.id)], context=context)
            if len(res) > 0:
                return res[0]
            else:
                return False
        else:
            # already ok
            return currency_id
    
    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        # add argument to discard table currencies by default
        table_in_args = False
        if args is None:
            args = []
        for a in args:
            if a[0] == 'currency_table_id':
                table_in_args = True
        if not table_in_args:
            args.insert(0, ('currency_table_id', '=', False))
        return super(res_currency, self).search(cr, uid, args, offset, limit, order, context, count=count)
    
    def compute(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, context=None):
        if context is None:
            context={}
        if context.get('currency_table_id', False):
            # A currency table is set, retrieve the correct currency ids
            new_from_currency_id = self._get_table_currency(cr, uid, from_currency_id, context['currency_table_id'], context=context)
            new_to_currency_id = self._get_table_currency(cr, uid, to_currency_id, context['currency_table_id'], context=context)
            # only use new currencies if both are defined in the table
            if new_from_currency_id and new_to_currency_id:
                return super(res_currency, self).compute(cr, uid, new_from_currency_id, new_to_currency_id, from_amount, round, context=context)
        # Fallback case if no currency table or one currency not defined in the table
        return super(res_currency, self).compute(cr, uid, from_currency_id, to_currency_id, from_amount, round, context=context)
    
    def create_associated_pricelist(self, cr, uid, currency_id, context=None):
        '''
        Create purchase and sale pricelists according to the currency
        '''
        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')
        item_obj = self.pool.get('product.pricelist.item')
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        currency = self.browse(cr, uid, currency_id, context=context)
        
        # Create the sale pricelist
        sale_price_id = pricelist_obj.create(cr, uid, {'currency_id': currency_id, 
                                                       'name': currency.name, 
                                                       'active': currency.active,
                                                       'type': 'sale',
                                                       'company_id': company_id}, context=context)
        
        # Create the sale pricelist version
        sale_version_id = version_obj.create(cr, uid, {'pricelist_id': sale_price_id,
                                                       'name': 'Default Sale %s Version' % currency.name,
                                                       'active': currency.active}, context=context)
        
        # Create the sale pricelist item
        item_obj.create(cr, uid, {'price_version_id': sale_version_id,
                                  'name': 'Default Sale %s Line' % currency.name,
                                  'base': 1,
                                  'min_qunatity': 0.00}, context=context)
        
        # Create the purchase pricelist
        purchase_price_id = pricelist_obj.create(cr, uid, {'currency_id': currency_id, 
                                                           'name': currency.name, 
                                                           'active': currency.active,
                                                           'type': 'purchase',
                                                           'company_id': company_id}, context=context)
        
        # Create the sale pricelist version
        purchase_version_id = version_obj.create(cr, uid, {'pricelist_id': purchase_price_id,
                                                           'name': 'Default Purchase %s Version' % currency.name,
                                                           'active': currency.active}, context=context)
        
        # Create the sale pricelist item
        item_obj.create(cr, uid, {'price_version_id': purchase_version_id,
                                  'name': 'Default Purchase %s Line' % currency.name,
                                  'base': -2,
                                  'min_qunatity': 0.00}, context=context)
        
        return True
    
    def create(self, cr, uid, values, context=None):
        '''
        Create automatically a purchase and a sales pricelist on
        currency creation
        '''    
        res = super(res_currency, self).create(cr, uid, values, context=context)
        
        # Create the corresponding pricelists
        self.create_associated_pricelist(cr, uid, res, context=context)
        
        # Check if currencies has no associated pricelists
        cr.execute('SELECT id FROM res_currency WHERE id NOT IN (SELECT currency_id FROM product_pricelist)')
        curr_ids = cr.fetchall()
        for cur_id in curr_ids:
            self.create_associated_pricelist(cr, uid, cur_id[0], context=context)
        
        return res
    
    def write(self, cr, uid, ids, values, context=None):
        '''
        Active/De-active pricelists according to activation/de-activation of the currency
        '''
        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        if 'active' in values:
            # Get all pricelists and versions for the given currency
            pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id', 'in', ids)], context=context)
            version_ids = version_obj.search(cr, uid, [('pricelist_id', 'in', pricelist_ids)], context=context)
            # Update the pricelists and versions
            pricelist_obj.write(cr, uid, pricelist_ids, {'active': values['active']}, context=context)
            version_obj.write(cr, uid, version_ids, {'active': values['active']}, context=context)
        
        return super(res_currency, self).write(cr, uid, ids, values, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        Unlink the pricelist associated to the currency 
        '''
        pricelist_obj = self.pool.get('product.pricelist')
        purchase_obj = self.pool.get('purchase.order')
        sale_obj = self.pool.get('sale.order')
        partner_obj = self.pool.get('res.partner')
        
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id', 'in', ids)], context=context)
        if pricelist_ids:
            # Get all documents which disallow the deletion of the currency
            purchase_ids = purchase_obj.search(cr, uid, [('pricelist_id', 'in', pricelist_ids)], context=context)
            sale_ids = sale_obj.search(cr, uid, [('pricelist_id', 'in', pricelist_ids)], context=context)
            partner_ids = partner_obj.search(cr, uid, ['|', ('property_product_pricelist', 'in', pricelist_ids),
                                                       ('property_product_pricelist_purchase', 'in', pricelist_ids)], context=context)
    
            # Raise an error if the currency is used on partner form        
            if partner_ids:
                raise osv.except_osv(_('Currency currently used !'), _('The currency you want to remove is currently used on at least one partner form.'))
            
            # Raise an error if the currency is used on sale or purchase order
            if purchase_ids or sale_ids:
                raise osv.except_osv(_('Currency currently used !'), _('The currency you want to remove is currently used on at least one sale order or purchase order.'))
        
        for cur_id in ids:
            res = super(res_currency, self).unlink(cr, uid, cur_id, context=context)
            
        return res   
            
res_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
