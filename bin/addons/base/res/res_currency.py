# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
import time
import datetime
import csv
from osv import fields, osv
from tools.translate import _

class res_currency_table(osv.osv):
    _name = 'res.currency.table'
    _trace = True

    _columns = {
        'name': fields.char('Currency table name', size=64, required=True),
        'code': fields.char('Currency table code', size=16, required=True),
        'currency_ids': fields.one2many('res.currency', 'currency_table_id', 'Currencies', domain=[('active','in',['t','f'])]),
        'state': fields.selection([('draft','Draft'),
                                   ('valid','Valid'),
                                   ('closed', 'Closed')], 'State', required=True),
    }

    _defaults = {
        'state': 'draft',
    }

    def validate(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        # just get one table
        if not isinstance(ids, (int, long)):
            ids = ids[0]
        table = self.browse(cr, uid, ids, context=context)
        for currency in table.currency_ids:
            if currency.rate == 0.0:
                raise osv.except_osv(_('Error'), _('A currency has an invalid rate! Please set a rate before validation.'))

        return self.write(cr, uid, ids, {'state': 'valid'}, context=context)

    def closed(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'closed'}, context=context)

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context={}
        for table in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', table.name),('code', '=ilike', table.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between currency tables!', ['code', 'name']),
    ]

res_currency_table()

class res_currency(osv.osv):
    _name = "res.currency"
    _description = "Currency"
    _trace = True
    _order = "name"

    def _check_unicity_currency_name(self, cr, uid, ids, context=None):
        """
        Check that no currency have the same name and the same currency_table_id.
        Check is non case-sensitive.
        """
        if not context:
            context = {}
        for c in self.browse(cr, uid, ids):
            if not c.currency_name:
                continue
            sql = """SELECT id, name
            FROM res_currency
            WHERE currency_name ilike %s"""
            if c.currency_table_id:
                sql += """\nAND currency_table_id in %s"""
                cr.execute(sql, (c.currency_name, tuple([c.currency_table_id.id])))
            else:
                sql += """\nAND currency_table_id is Null"""
                cr.execute(sql, (c.currency_name,))
            bad_ids = cr.fetchall()
            if bad_ids and len(bad_ids) > 1:
                return False
        return True

    def _check_unicity_name(self, cr, uid, ids, context=None):
        """
        Check that no currency is the same and have the same currency_table_id.
        Check is non case-sensitive.
        """
        if not context:
            context = {}
        for c in self.browse(cr, uid, ids):
            if not c.name:
                continue
            sql = """SELECT id, name
            FROM res_currency
            WHERE name ilike %s"""
            if c.currency_table_id:
                sql += """\nAND currency_table_id in %s"""
                cr.execute(sql, (c.name, tuple([c.currency_table_id.id])))
            else:
                sql += """\nAND currency_table_id is Null"""
                cr.execute(sql, (c.name,))
            bad_ids = cr.fetchall()
            if bad_ids and len(bad_ids) > 1:
                return False
        return True

    def _verify_rate(self, cr, uid, ids, context=None):
        """
        Verify that a currency set to active has a non-zero rate.
        """
        for currency in self.browse(cr, uid, ids, context=context):
            if not currency.rate_ids and currency.active:
                return False
        return True

    def _current_date_rate(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        date = context.get('currency_date') or time.strftime('%Y-%m-%d')
        for id in ids:
            cr.execute("SELECT currency_id, name, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(id, date))
            if cr.rowcount:
                id, curr_date, rate = cr.fetchall()[0]
                res[id] = {'date': curr_date, 'rate': rate}
            else:
                res[id] = {'date': False, 'rate': 0}
        return res

    def _get_in_search(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True
        return res

    def _search_in_search(self, cr, uid, obj, name, args, context=None):
        '''
        Returns currency according to partner type
        '''
        user_obj = self.pool.get('res.users')
        price_obj = self.pool.get('product.pricelist')
        dom = []

        for arg in args:
            if arg[0] == 'is_po_functional':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error !'), _('Bad operator !'))
                else:
                    func_currency_id = user_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id
                    po_currency_id = price_obj.browse(cr, uid, arg[2]).currency_id.id
                    dom.append(('id', 'in', [func_currency_id, po_currency_id]))
        return dom

    def _get_partner_currency(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True

        return res

    def _src_partner_currency(self, cr, uid, obj, name, args, context=None):
        '''
        Returns currencies according to partner type
        '''
        user_obj = self.pool.get('res.users')
        dom = []

        for arg in args:
            if arg[0] == 'partner_currency':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error !'), _('Bad operator !'))
                elif arg[2]:
                    partner = self.pool.get('res.partner').browse(cr, uid, arg[2], context=context)
                    if partner.partner_type in ('internal', 'intermission'):
                        func_currency_id = user_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id
                        dom.append(('id', '=', func_currency_id))
                    elif partner.partner_type == 'section':
                        dom.append(('is_section_currency', '=', True))
                    elif partner.partner_type == 'esc':
                        dom.append(('is_esc_currency', '=', True))

        return dom

    _columns = {
        # Note: 'code' column was removed as of v6.0, the 'name' should now hold the ISO code.
        'name': fields.char('Currency', size=32, required=True, help="Currency Code (ISO 4217)"),
        'symbol': fields.char('Symbol', size=3, help="Currency sign, to be used when printing amounts"),
        'rate': fields.function(_current_date_rate, method=True, string='Current Rate', digits=(12,6),
                                help='The rate of the currency to the functional currency',  multi='_date_rate'),
        'date': fields.function(_current_date_rate, method=True, string='Validity From', type='date', multi='_date_rate'),
        'rate_ids': fields.one2many('res.currency.rate', 'currency_id', 'Rates'),
        'accuracy': fields.integer('Computational Accuracy'),
        'rounding': fields.float('Rounding factor', digits=(12,6)),
        'active': fields.boolean('Active'),
        'company_id':fields.many2one('res.company', 'Company'),
        'base': fields.boolean('Base'),
        'currency_name': fields.char('Currency Name', size=64, required=True, translate=1),

        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table', ondelete='cascade'),
        'reference_currency_id': fields.many2one('res.currency', 'Reference Currency', ondelete='cascade'),
        'is_section_currency': fields.boolean(string='Functional currency',
                                              help='If this box is checked, this currency is used as a functional currency for at least one section in MSF.'),
        'is_esc_currency': fields.boolean(string='ESC currency',
                                          help='If this box is checked, this currency is used as a currency for at least one ESC.'),
        'is_po_functional': fields.function(_get_in_search, fnct_search=_search_in_search, method=True,
                                            type='boolean', string='transport PO currencies'),
        'partner_currency': fields.function(_get_partner_currency, fnct_search=_src_partner_currency, type='boolean', method=True,
                                            string='Partner currency', store=False, help='Only technically to filter currencies according to partner type'),
    }
    _defaults = {
        'active': lambda *a: 0,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'res.currency', context=c),
        'accuracy': 4,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name, currency_table_id)', 'The currency name exists already in the system!')
    ]

    _constraints = [
        (_verify_rate, "No rate is set. Please set one before activating the currency. ", ['active', 'rate_ids']),
        (_check_unicity_currency_name, "Another currency have the same name.", ['currency_name']),
        (_check_unicity_name, "Same currency exists", ['name']),
    ]

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        select = ids
        if isinstance(ids, (int, long)):
            select = [select]
        res = super(osv.osv, self).read(cr, user, select, fields, context, load)
        for r in res:
            if r.__contains__('rate_ids'):
                rates=r['rate_ids']
                if rates:
                    currency_rate_obj=  self.pool.get('res.currency.rate')
                    currency_date = currency_rate_obj.read(cr,user,rates[0],['name'])['name']
                    r['date'] = currency_date
        if isinstance(ids, (int, long)):
            return res and res[0] or False
        return res

    def create(self, cr, uid, values, context=None):
        '''
        Create automatically a purchase and a sales pricelist on
        currency creation
        '''
        res = super(res_currency, self).create(cr, uid, values, context=context)
        # Create the corresponding pricelists (only for non currency that have a currency_table)
        if not values.get('currency_table_id', False) and self.pool.get('product.pricelist'):
            self.create_associated_pricelist(cr, uid, res, context=context)

            # Check if currencies has no associated pricelists
            cr.execute('SELECT id FROM res_currency WHERE id NOT IN (SELECT currency_id FROM product_pricelist) AND currency_table_id IS NULL')
            curr_ids = cr.fetchall()
            for cur_id in curr_ids:
                self.create_associated_pricelist(cr, uid, cur_id[0], context=context)

        return res

    def open_currency_tc(self, cr, uid, ids, context=None):
        """
        Opens the Track Changes of the currency in a new tab.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        tc_sql = """
            SELECT id FROM audittrail_log_line 
            WHERE res_id = %s
            AND object_id = (SELECT id FROM ir_model WHERE model='res.currency' LIMIT 1);
        """
        cr.execute(tc_sql, (tuple(ids),))
        tc_ids = [x for x, in cr.fetchall()]
        search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_audittrail', 'view_audittrail_log_line_search')
        search_view_id = search_view_id and search_view_id[1] or False
        return {
            'name': _('Track changes'),
            'type': 'ir.actions.act_window',
            'res_model': 'audittrail.log.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'search_view_id': [search_view_id],
            'context': context,
            'domain': [('id', 'in', tc_ids)],
            'target': 'current',
        }

    def write(self, cr, uid, ids, values, context=None):
        '''
        Active/De-active pricelists according to activation/de-activation of the currency
        '''
        if not ids:
            return True

        property_obj = self.pool.get('ir.property')
        partner_obj = self.pool.get('res.partner')
        pricelist_obj = self.pool.get('product.pricelist')
        version_obj = self.pool.get('product.pricelist.version')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Check if Inter-section partners used one of these currencies
        if 'is_section_currency' in values and not values['is_section_currency']:
            pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id',
                                                            'in', ids)], order='NO_ORDER', context=context)
            partner_ids = partner_obj.search(cr, uid, [('partner_type', '=',
                                                        'section')], order='NO_ORDER', context=context)
            value_reference = ['product.pricelist,%s' % x for x in pricelist_ids]
            res_reference = ['res.partner,%s' % x for x in partner_ids]
            property_ids = []
            if value_reference and res_reference:
                property_ids = property_obj.search(cr, uid, [('res_id', 'in', res_reference),
                                                             ('value_reference', 'in', value_reference),
                                                             '|', ('name', '=', 'property_product_pricelist'),
                                                             ('name', '=', 'property_product_pricelist_purchase'),], context=context)
            if property_ids:
                properties = property_obj.browse(cr, uid, property_ids, context=context)
                partner_list = ' / '.join(x.res_id.name for x in properties)
                raise osv.except_osv(_('Error !'),
                                     _('You cannot uncheck the Section checkbox because this currency is used on these \'Inter-section\' partners : \
                                      %s') % (partner_list,))

        # Check if ESC partners used one of these currencies
        if 'is_esc_currency' in values and not values['is_esc_currency']:
            pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id',
                                                            'in', ids)], order='NO_ORDER', context=context)
            partner_ids = partner_obj.search(cr, uid, [('partner_type', '=',
                                                        'esc')], order='NO_ORDER', context=context)
            value_reference = ['product.pricelist,%s' % x for x in pricelist_ids]
            res_reference = ['res.partner,%s' % x for x in partner_ids]
            property_ids = []
            if value_reference and res_reference:
                property_ids = property_obj.search(cr, uid, [('res_id', 'in', res_reference),
                                                             ('value_reference', 'in', value_reference),
                                                             '|', ('name', '=', 'property_product_pricelist'),
                                                             ('name', '=', 'property_product_pricelist_purchase'),], context=context)
            if property_ids:
                properties = property_obj.browse(cr, uid, property_ids, context=context)
                partner_list = ' / '.join(x.res_id.name for x in properties)
                raise osv.except_osv(_('Error !'),
                                     _('You cannot uncheck the ESC checkbox because this currency is used on these \'ESC\' partners : \
                                      %s') % partner_list)

        if 'active' in values and not values.get('currency_table_id', False) and pricelist_obj:
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

    def unlink(self, cr, uid, ids, context=None):
        '''
        Unlink the pricelist associated to the currency
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Search for move lines with this currency. If those exists,
        # exception.
        if self.pool.get('account.move.line').search_exist(cr, uid, [('|'), ('currency_id','in',ids), ('functional_currency_id', 'in', ids)], context=context):
            raise osv.except_osv(_('Currency currently used!'), _('The currency cannot be deleted as one or more journal items are currently using it!'))

        pricelist_obj = self.pool.get('product.pricelist')

        # If no error, unlink pricelists
        for p_list in self.check_in_use(cr, uid, ids, 'delete', context=context):
            pricelist_obj.unlink(cr, uid, p_list, context=context)
        return super(res_currency, self).unlink(cr, uid, ids, context=context)

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

    def round(self, cr, uid, rounding, amount):
        if rounding == 0:
            return 0.0
        else:
            # /!\ First member below must be rounded to full unit!
            # Do not pass a rounding digits value to round()
            return round(amount / rounding) * rounding

    def is_zero(self, cr, uid, currency, amount):
        return abs(self.round(cr, uid, currency.rounding, amount)) < currency.rounding

    def _get_conversion_rate(self, cr, uid, from_currency, to_currency, context=None):
        if context is None:
            context = {}

        if 'revaluation' in context:
            if from_currency['rate'] == 0.0:
                date = context.get('currency_date', time.strftime('%Y-%m-%d'))
                raise osv.except_osv(_('Error'),
                                     _('No rate found \n'
                                       'for the currency: %s \n'
                                       'at the date: %s') %
                                     (from_currency['name'], date))
            return 1.0 / from_currency['rate']

        account = context.get('res.currency.compute.account')
        account_invert = context.get('res.currency.compute.account_invert')
        if account and account.currency_mode == 'average' and account.currency_id:
            query = self.pool.get('account.move.line')._query_get(cr, uid, context=context)
            cr.execute('''select sum(debit-credit),sum(amount_currency) from account_move_line l
                where l.currency_id=%%s and l.account_id=%%s and %s''' % query, (account.currency_id.id,account.id,))  # not_a_user_entry
            tot1, tot2 = cr.fetchone()
            if tot2 and not account_invert:
                return float(tot1)/float(tot2)
            if tot1 and account_invert:
                return float(tot2)/float(tot1)

        if from_currency['rate'] == 0 or to_currency['rate'] == 0:
            date = context.get('currency_date', time.strftime('%Y-%m-%d'))
            if from_currency['rate'] == 0:
                currency_name = from_currency['name']
            else:
                currency_name = to_currency['name']
            if 'currency_table_id' in context:
                rct_obj = self.pool.get('res.currency.table')
                rct_browse = rct_obj.browse(cr, uid, context['currency_table_id'])
                raise osv.except_osv(_('Error'), _('Report can not be edited due to missing FX rates in specific currency table %s') % rct_browse.name)
            else:
                raise osv.except_osv(_('Error'), _('No rate found \n' \
                                                   'for the currency: %s \n' \
                                                   'at the date: %s') % (currency_name, date))
        return to_currency['rate']/from_currency['rate']

    def compute(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, context=None):
        if context is None:
            context = {}

        if context.get('currency_table_id', False):
            # A currency table is set, retrieve the correct currency ids
            # UTP-894: use currency table rate or default rate if currency not in currency table
            new_from_currency_id = self._get_table_currency(cr, uid, from_currency_id, context['currency_table_id'], context=context)
            if new_from_currency_id:
                from_currency_id = new_from_currency_id
            new_to_currency_id = self._get_table_currency(cr, uid, to_currency_id, context['currency_table_id'], context=context)
            if new_to_currency_id:
                to_currency_id = new_to_currency_id

        if not from_currency_id:
            from_currency_id = to_currency_id
        if not to_currency_id:
            to_currency_id = from_currency_id
        from_currency = self.read(cr, uid, from_currency_id, ['rounding', 'name', 'rate'], context=context)
        to_currency = self.read(cr, uid, to_currency_id, ['rounding', 'name', 'rate'], context=context)
        if to_currency_id == from_currency_id:
            if round:
                return self.round(cr, uid, to_currency['rounding'], from_amount)
            else:
                return from_amount
        else:
            rate = self._get_conversion_rate(cr, uid, from_currency, to_currency, context=context)
            if round:
                return self.round(cr, uid, to_currency['rounding'], from_amount * rate)
            else:
                return (from_amount * rate)

    def name_search(self, cr, uid, name, args=[], operator='ilike', context={}, limit=100):
        args = args[:]
        if name:
            args += [('name', operator, name)]
        ids = self.search(cr, uid, args, limit=limit)
        res = self.name_get(cr, uid, ids, context)
        return res

    def auto_import(self, cr, uid, file_to_import, context=None):
        import base64
        processed = []
        rejected = []
        headers = []
        date = None

        # check all lines have the same date
        with open(file_to_import, 'r') as csv_file:
            line_list = list(csv.reader(csv_file, quoting=csv.QUOTE_ALL,
                                        delimiter=','))
            line_number = 0
            headers = None
            for line in line_list:
                if line_number == 0:
                    headers = line
                    assert(line[0] == 'Date'), _('Date column is mandatory for auto import.')
                else:
                    if line and line[0]:
                        if date is None:
                            date = line[0]
                        elif line[0] != date:
                            raise osv.except_osv(_('Error'),
                                                 _("All dates should be equal for all lines in file %s.") % file_to_import)
                line_number += 1

            # check that this date is a real date
            try:
                date = datetime.datetime.strptime(date, '%d/%m/%Y')
                date = date.strftime('%Y-%m-%d')
            except:
                date = None

            if not date:
                raise osv.except_osv(_('Error'), _("A 'Date' column is needed for each line of %s in this format: '18/10/2016'.") % file_to_import)

        import_obj = self.pool.get('import.currencies')
        import_id = import_obj.create(cr, uid, {
            'rate_date': date,
            'import_file': base64.encodestring(open(file_to_import, 'r').read()),
        })
        processed, rejected, headers = import_obj.import_rates(cr, uid, [import_id], auto_import=True)
        return processed, rejected, headers

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
                # ensure that the partner referenced in ir_property exists before checking if he is active
                if prop.res_id and prop.res_id._table_name == 'res.partner' and hasattr(prop.res_id, 'active') and \
                        getattr(prop.res_id, 'active') or False:
                    raise osv.except_osv(_('Currency currently used!'), _('The currency you want to %s is used '
                                                                          'in at least one active partner form.') % keyword)

        # Check on account.invoice
        if acc_inv_obj.search_exist(cr, uid, [('currency_id', 'in', ids), ('state', 'not in', ['paid', 'inv_close', 'cancel'])], context=context):
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
                                          ('state', 'in', ['draft', 'running'])], context=context):
            raise osv.except_osv(_('Currency currently used!'),
                                 _("The currency you want to %s is used in at least "
                                   "one Draft or Running Accrual.") % keyword)

        return pricelist_ids

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


res_currency()

class res_currency_rate(osv.osv):
    _name = "res.currency.rate"
    _description = "Currency Rate"
    _trace = True
    _columns = {
        'name': fields.date('Date', required=True, select=True),
        'rate': fields.float('Rate', digits=(12,6), required=True,
                             help='The rate of the currency to the currency of rate 1'),
        'currency_id': fields.many2one('res.currency', 'Currency', readonly=True),
    }
    _defaults = {
        'name': lambda *a: time.strftime('%Y-%m-%d'),
    }
    _order = "name desc"
res_currency_rate()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

