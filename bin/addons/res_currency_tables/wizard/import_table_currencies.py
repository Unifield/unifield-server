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

import datetime
import base64
import StringIO
import csv

class import_table_currencies(osv.osv_memory):
    _name = "import.table.currencies"
    
    _columns = {
        'rate_date': fields.date('Date for the uploaded rates', required=True),
        'import_file': fields.binary("CSV File", required=True),
    }
    
    _defaults = {
        'rate_date': lambda *a: datetime.datetime.today().strftime('%Y-%m-%d')
    }
    
    def import_table_rates(self, cr, uid, ids, context=None):
        # UTP-894 get company currency code
        comp_ccy_code = False
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            comp_ccy_id = user[0].company_id.currency_id.id
            if comp_ccy_id:
                comp_ccy_name = self.pool.get('res.currency').name_get(cr, uid, [comp_ccy_id], context=context)
                if comp_ccy_name:
                    comp_ccy_code = comp_ccy_name[0][1]
                                        
        if context is None:
            context = {}
        currency_obj = self.pool.get('res.currency')
        currency_rate_obj = self.pool.get('res.currency.rate')
        
        if 'active_id' in context:
            for wizard in self.browse(cr, uid, ids, context=context):
                if not wizard.import_file:
                    raise osv.except_osv(_('Warning'),
                        _('Please browse a csv file.'))
                import_file = base64.decodestring(wizard.import_file)
                import_string = StringIO.StringIO(import_file)
                import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))
                if not import_data:
                    raise osv.except_osv(_('Warning'), _('File is empty.'))
                    
                if comp_ccy_code:
                    # UTP-894 pre-check: currency table MUST contain company/reference currency
                    ccy_codes = [line[0] for line in import_data]
                    if comp_ccy_code not in ccy_codes:
                        raise osv.except_osv(_('Error'), _('The reference currency %s is not defined in the table to import!') % comp_ccy_code)
                    
                for line in import_data:
                    if len(line) > 0 and len(line[0]) == 3:
                        # we have a currency ISO code; search it and its rates in the table first
                        # update context with active_test = False; otherwise, non-set currencies
                        context.update({'active_test': False})
                        currency_ids = currency_obj.search(cr, uid, [('currency_table_id', '=', context['active_id']),('name', '=', line[0])], context=context)
                        if len(currency_ids) == 0:
                            # No currency found in the table. Create it from the main one
                            main_currency_ids = currency_obj.search(cr, uid, [('currency_table_id', '=', False),('name', '=', line[0])], context=context)
                            if len(main_currency_ids) > 0:
                                # create currency from main one
                                main_currency = currency_obj.browse(cr, uid, main_currency_ids[0], context=context)
                                currency_vals = {'name': main_currency.name,
                                                 'currency_name': main_currency.currency_name,
                                                 'symbol': main_currency.symbol,
                                                 'accuracy': main_currency.accuracy,
                                                 'rounding': main_currency.rounding,
                                                 'company_id': main_currency.company_id.id,
                                                 'date': main_currency.date,
                                                 'base': main_currency.base,
                                                 'currency_table_id': context['active_id'],
                                                 'reference_currency_id': main_currency.id,
                                                 'active': False
                                                }
                                # update currency_ids for below
                                currency_ids = [currency_obj.create(cr, uid, currency_vals, context=context)]
                            else:
                                # Currency doesn't exist in main table
                                raise osv.except_osv(_('Error'), _('The currency %s is not defined in the main set!') % line[0])
                                break
                        currency_rates = currency_rate_obj.search(cr, uid, [('currency_id', '=', currency_ids[0]), ('name', '=', wizard.rate_date)], context=context)
                        if len(currency_rates) > 0:
                            # A rate exists for this date; we update it
                            currency_rate_obj.write(cr, uid, currency_rates, {'name': wizard.rate_date,
                                                                              'rate': float(line[1])}, context=context)
                        else:
                            # No rate for this date: create it
                            currency_rate_obj.create(cr, uid, {'name': wizard.rate_date,
                                                               'rate': float(line[1]),
                                                               'currency_id': currency_ids[0]})
                        # Now that there is a rate, update currency as active
                        currency_obj.write(cr, uid, currency_ids, {'active': True}, context=context)
        
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.import.currencies',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context
        }
    
import_table_currencies()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
