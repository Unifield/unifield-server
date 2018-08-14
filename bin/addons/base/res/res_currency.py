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

class res_currency(osv.osv):
    def _current_rate(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        if 'date' in context:
            date = context['date']
        else:
            date = time.strftime('%Y-%m-%d')
        date = date or time.strftime('%Y-%m-%d')
        for id in ids:
            cr.execute("SELECT currency_id, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(id, date))
            if cr.rowcount:
                id, rate = cr.fetchall()[0]
                res[id] = rate
            else:
                res[id] = 0
        return res
    _name = "res.currency"
    _description = "Currency"
    _columns = {
        # Note: 'code' column was removed as of v6.0, the 'name' should now hold the ISO code.
        'name': fields.char('Currency', size=32, required=True, help="Currency Code (ISO 4217)"),
        'symbol': fields.char('Symbol', size=3, help="Currency sign, to be used when printing amounts"),
        'rate': fields.function(_current_rate, method=True, string='Current Rate', digits=(12,6),
                                help='The rate of the currency to the currency of rate 1'),
        'rate_ids': fields.one2many('res.currency.rate', 'currency_id', 'Rates'),
        'accuracy': fields.integer('Computational Accuracy'),
        'rounding': fields.float('Rounding factor', digits=(12,6)),
        'active': fields.boolean('Active'),
        'company_id':fields.many2one('res.company', 'Company'),
        'base': fields.boolean('Base'),
        'currency_name': fields.char('Currency Name', size=64, required=True, translate=1),
    }
    _defaults = {
        'active': lambda *a: 1,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'res.currency', context=c)
    }
    _order = "name"

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
        if from_currency['rate'] == 0 or to_currency['rate'] == 0:
            date = context.get('date', time.strftime('%Y-%m-%d'))
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
                                                 _("All dates should be equal for all lines in file %s." % file_to_import))
                line_number += 1

            # check that this date is a real date
            try:
                date = datetime.datetime.strptime(date, '%d/%m/%Y')
                date = date.strftime('%Y-%m-%d')
            except:
                date = None

            if not date:
                raise osv.except_osv(_('Error'), _("A 'Date' column is needed for each line of %s in this format: '18/10/2016'." % file_to_import))

        import_obj = self.pool.get('import.currencies')
        import_id = import_obj.create(cr, uid, {
            'rate_date': date,
            'import_file': base64.encodestring(open(file_to_import, 'r').read()),
        })
        processed, rejected, headers = import_obj.import_rates(cr, uid, [import_id], auto_import=True)
        return processed, rejected, headers

res_currency()

class res_currency_rate(osv.osv):
    _name = "res.currency.rate"
    _description = "Currency Rate"
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

