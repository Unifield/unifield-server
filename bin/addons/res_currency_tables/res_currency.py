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

from tools.translate import _

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
        return super(res_currency, self).search(cr, uid, args, offset, limit,
                                                order, context, count=count)

    def compute(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, context=None):
        if context is None:
            context={}
        if context.get('currency_table_id', False):
            # A currency table is set, retrieve the correct currency ids
            # UTP-894: use currency table rate or default rate if currency not in currency table
            new_from_currency_id = self._get_table_currency(cr, uid, from_currency_id, context['currency_table_id'], context=context)
            if new_from_currency_id:
                from_currency_id = new_from_currency_id
            new_to_currency_id = self._get_table_currency(cr, uid, to_currency_id, context['currency_table_id'], context=context)
            if new_to_currency_id:
                to_currency_id = new_to_currency_id
        return super(res_currency, self).compute(cr, uid, from_currency_id, to_currency_id, from_amount, round, context=context)

    def create_associated_pricelist(self, cr, uid, currency_id, context=None):
        '''
        Create purchase and sale pricelists according to the currency
        '''

        if context is None:
            context = {}

        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')
        item_obj = self.pool.get('product.pricelist.item')

        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        currency = self.browse(cr, uid, currency_id, context=context)

        # Create the sale pricelist
        sale_price_id = pricelist_obj.create(cr, uid, {'currency_id': currency.id,
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
                                  'min_quantity': 0.00}, context=context)

        # Create the purchase pricelist
        purchase_price_id = pricelist_obj.create(cr, uid, {'currency_id': currency.id,
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
                                  'min_quantity': 0.00}, context=context)

        if context.get('sync_update_execution'):
            # new currency created by sync
            # create pricelist xmlid
            pricelist_obj.get_sd_ref(cr, uid, [sale_price_id, purchase_price_id], context=context)

        return [sale_price_id, purchase_price_id]

    def create(self, cr, uid, values, context=None):
        '''
        Create automatically a purchase and a sales pricelist on
        currency creation
        '''
        res = super(res_currency, self).create(cr, uid, values, context=context)
        # Create the corresponding pricelists (only for non currency that have a currency_table)
        if not values.get('currency_table_id', False):
            self.create_associated_pricelist(cr, uid, res, context=context)

            # Check if currencies has no associated pricelists
            cr.execute('SELECT id FROM res_currency WHERE id NOT IN (SELECT currency_id FROM product_pricelist) AND currency_table_id IS NULL')
            curr_ids = cr.fetchall()
            for cur_id in curr_ids:
                self.create_associated_pricelist(cr, uid, cur_id[0], context=context)

        return res

    def write(self, cr, uid, ids, values, context=None):
        '''
        Active/De-active pricelists according to activation/de-activation of the currency
        '''
        if not ids:
            return True
        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'active' in values and not values.get('currency_table_id', False):
            if values['active'] == False:
                self.check_in_use(cr, uid, ids, 'de-activate', context=context)
            # Get all pricelists and versions for the given currency
            pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id', 'in', ids), ('active', 'in', ['t', 'f'])], context=context)
            if not pricelist_ids:
                to_create = self.search(cr, uid,
                                        [('currency_table_id', '=', False),
                                         ('id', 'in', ids),
                                            ('active', 'in', ['t', 'f'])], context=context)
                for cur_id in to_create:
                    pricelist_ids = self.create_associated_pricelist(cr, uid, cur_id, context=context)
            version_ids = version_obj.search(cr, uid, [('pricelist_id', 'in', pricelist_ids), ('active', 'in', ['t', 'f'])], context=context)
            # Update the pricelists and versions
            pricelist_obj.write(cr, uid, pricelist_ids, {'active': values['active']}, context=context)
            version_obj.write(cr, uid, version_ids, {'active': values['active']}, context=context)

        return super(res_currency, self).write(cr, uid, ids, values, context=context)

    def check_in_use(self, cr, uid, ids, keyword='delete', context=None):
        '''
        Check if the currency is currently in used in the system
        '''
        pricelist_obj = self.pool.get('product.pricelist')
        purchase_obj = self.pool.get('purchase.order')
        sale_obj = self.pool.get('sale.order')
        property_obj = self.pool.get('ir.property')
        acc_inv_obj = self.pool.get('account.invoice')
        aml_obj = self.pool.get('account.move.line')
        comm_voucher_obj = self.pool.get('account.commitment')
        hq_entry_obj = self.pool.get('hq.entries')
        payroll_obj = self.pool.get('hr.payroll.msf')
        reg_obj = self.pool.get('account.bank.statement')
        recurring_obj = self.pool.get('account.subscription')
        accrual_line_obj = self.pool.get('msf.accrual.line')
        keyword = _(keyword)

        if isinstance(ids, (int, long)):
            ids = [ids]

        pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id', 'in', ids), ('active', 'in', ['t', 'f'])],
                                             order='NO_ORDER', context=context)
        if pricelist_ids:
            # Get all documents which disallow the deletion of the currency
            # Raise an error if the currency is used in a transaction that isn't closed/paid/posted

            # Check on POs
            if purchase_obj.search_exist(cr, uid, [('pricelist_id', 'in', pricelist_ids), ('state', 'not in', ['done', 'cancel'])],
                                         context=context):
                raise osv.except_osv(_('Currency currently used!'), _(
                    "The currency you want to %s is used in at least one "
                    "Purchase Order which isn't Closed.") % keyword)

            # Check on FOs
            if sale_obj.search_exist(cr, uid, [('pricelist_id', 'in', pricelist_ids), ('state', 'not in', ['done', 'cancel'])],
                                     context=context):
                raise osv.except_osv(_('Currency currently used!'), _(
                    "The currency you want to %s is used in at least one "
                    "Field Order which isn't Closed.") % keyword)

            # Check on Partner (forms)
            value_reference = ['product.pricelist,%s' % x for x in pricelist_ids]
            property_ids = property_obj.search(cr, uid, ['|', ('name', '=', 'property_product_pricelist'),
                                                         ('name', '=', 'property_product_pricelist_purchase'),
                                                         ('value_reference', 'in', value_reference)], order='NO_ORDER', context=context)
            for prop in property_obj.browse(cr, uid, property_ids, fields_to_fetch=['res_id'], context=context):
                if prop.res_id and prop.res_id._table_name == 'res.partner' and prop.res_id.active:
                    raise osv.except_osv(_('Currency currently used!'), _('The currency you want to %s is used '
                                                                          'in at least one active partner form.') % keyword)

        # Check on account.invoice
        if acc_inv_obj.search_exist(cr, uid, [('currency_id', 'in', ids), ('state', 'not in', ['paid', 'cancel'])], context=context):
            raise osv.except_osv(_('Currency currently used!'), _('The currency you want to %s is used in at least '
                                                                  'one document in Draft or Open state.') % keyword)

        # Check on Journal Items
        if aml_obj.search_exist(cr, uid, ['|',
                                          ('currency_id', 'in', ids),
                                          ('functional_currency_id', 'in', ids),
                                          ('move_state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Currency currently used!'), _('The currency you want to %s is used in at least '
                                                                  'one Journal Item in Unposted state.') % keyword)
        # Check on Commitment Vouchers
        if comm_voucher_obj.search_exist(cr, uid, [('currency_id', 'in', ids), ('state', '!=', 'done')], context=context):
            raise osv.except_osv(_('Currency currently used!'), _("The currency you want to %s is used in at least "
                                                                  "one Commitment Voucher which isn't Done.") % keyword)
        # Check on HQ Entries
        if hq_entry_obj.search_exist(cr, uid, [('currency_id', 'in', ids), ('user_validated', '=', False)], context=context):
            raise osv.except_osv(_('Currency currently used!'), _("The currency you want to %s is used in at least "
                                                                  "one HQ Entry which isn't validated.") % keyword)

        # Check on HR Payrolls
        if payroll_obj.search_exist(cr, uid, [('currency_id', 'in', ids), ('state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Currency currently used!'), _("The currency you want to %s is used in at least "
                                                                  "one Payroll Entry which isn't validated.") % keyword)

        # Check on Registers
        if reg_obj.search_exist(cr, uid, [('journal_id.currency', 'in', ids), ('state', 'in', ['draft', 'open'])], context=context):
            raise osv.except_osv(_('Currency currently used!'),
                                 _("The currency you want to %s is used in at least "
                                   "one Register in Draft or Open state.") % keyword)

        # Check on Recurring Entries
        if recurring_obj.search_exist(cr, uid, [('model_id.currency_id', 'in', ids), ('state', '!=', 'done')], context=context):
            raise osv.except_osv(_('Currency currently used!'),
                                 _("The currency you want to %s is used in at least "
                                   "one Recurring Entry having a state not Done.") % keyword)

        # Check on Accrual Lines
        if accrual_line_obj.search_exist(cr, uid,
                                         ['|', ('currency_id', 'in', ids), ('functional_currency_id', 'in', ids),
                                          ('state', 'in', ['draft', 'partially_posted'])], context=context):
            raise osv.except_osv(_('Currency currently used!'),
                                 _("The currency you want to %s is used in at least "
                                   "one Draft or Partially Posted Accrual Line.") % keyword)

        return pricelist_ids

    def unlink(self, cr, uid, ids, context=None):
        '''
        Unlink the pricelist associated to the currency
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Search for move lines with this currency. If those exists,
        # exception.
        move_line_ids = self.pool.get('account.move.line').search(cr, uid, [('|'),
                                                                            ('currency_id','in',ids),
                                                                            ('functional_currency_id', 'in', ids)], context=context)
        if len(move_line_ids) > 0:
            raise osv.except_osv(_('Currency currently used!'), _('The currency cannot be deleted as one or more journal items are currently using it!'))

        pricelist_obj = self.pool.get('product.pricelist')

        # If no error, unlink pricelists
        for p_list in self.check_in_use(cr, uid, ids, 'delete', context=context):
            pricelist_obj.unlink(cr, uid, p_list, context=context)
        return super(res_currency, self).unlink(cr, uid, ids, context=context)

#        remove this block because it has been moved to the sync module
#    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
#        currency = self.browse(cr, uid, res_id)
#        table_name = currency.currency_table_id and currency.currency_table_id.name or ''
#        return currency.name + table_name

res_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
