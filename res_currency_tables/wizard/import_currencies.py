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

class import_currencies(osv.osv_memory):
    _name = "import.currencies"
    
    _columns = {
        'rate_date': fields.date('Date for the uploaded rates', required=True),
        'import_file': fields.binary("CSV File", required=True),
    }
    
    _defaults = {
        'rate_date': lambda *a: datetime.datetime.today().strftime('%Y-%m-%d')
    }
    
    def _check_periods(self, cr, uid, rate_date, context=None):
        period_obj = self.pool.get('account.period')
        period_ids = period_obj.search(cr, uid, [('date_start','<=',rate_date),('date_stop','>=',rate_date)])
        if not period_ids:
            raise osv.except_osv(_('Error !'), _('No period defined for this date: %s !\nPlease create a fiscal year.')%rate_date)
        else:
            period = period_obj.browse(cr, uid, period_ids[0], context=context)
            if period.state not in ['created', 'draft']:
                raise osv.except_osv(_('Error !'), _('Period %s is closed !\nNo rates can be set for it.')%period.name)
        return
                
    def import_rates(self, cr, uid, ids, context=None):
        """
        
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        currency_obj = self.pool.get('res.currency')
        currency_rate_obj = self.pool.get('res.currency.rate')
        undefined_currencies = ""
        existing_currencies = ""
        for wizard in self.browse(cr, uid, ids, context=context):
            import_file = base64.decodestring(wizard.import_file)
            import_string = StringIO.StringIO(import_file)
            import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))
            if not import_data:
                raise osv.except_osv(_('Warning'), _('File is empty.'))
        
            self._check_periods(cr, uid, wizard.rate_date, context=context)
        
            for line in import_data:
                if len(line) > 0 and len(line[0]) == 3:
                    # we have a currency ISO code; search it and its rates
                    # update context with active_test = False; otherwise, non-set currencies
                    context.update({'active_test': False})
                    currency_ids = currency_obj.search(cr, uid, [('name', '=', line[0])], context=context)
                    if len(currency_ids) == 0:
                        raise osv.except_osv(_('Error'), _('The currency %s is not defined!') % line[0])
                        break
                    else:
                        # check for date. 2 checks done:
                        # - if the rate date is the 1st of the month, no check.
                        # - all other dates: check if the 1st day of the month has a rate;
                        #   otherwise, raise a warning
                        rate_datetime = datetime.datetime.strptime(wizard.rate_date, '%Y-%m-%d')
                        if rate_datetime.day != 1:
                            rate_date_start = '%s-%s-01' % (rate_datetime.year, rate_datetime.month)
                            cr.execute("SELECT name FROM res_currency_rate WHERE currency_id = %s AND name = %s" ,(currency_ids[0], rate_date_start))
                            if not cr.rowcount:
                                # add currency in warning list
                                undefined_currencies += "%s\n" % line[0]
                                wizard_date = wizard.rate_date
                        # Now, creating/updating the rate
                        currency_rates = currency_rate_obj.search(cr, uid, [('currency_id', '=', currency_ids[0]), ('name', '=', wizard.rate_date)], context=context)
                        if len(currency_rates) > 0:
                            # A rate exists for this date; we update it
                            currency_rate_obj.write(cr, uid, currency_rates, {'name': wizard.rate_date,
                                                                              'rate': float(line[1])}, context=context)
                            existing_currencies += "%s\n" % line[0]
                            wizard_date = wizard.rate_date
                        else:
                            # No rate for this date: create it
                            currency_rate_obj.create(cr, uid, {'name': wizard.rate_date,
                                                               'rate': float(line[1]),
                                                               'currency_id': currency_ids[0]})
        # Return undefined currencies
        if len(undefined_currencies) > 0 or len(existing_currencies) > 0:
            period_name = ''
            w_vals = {'currency_list': undefined_currencies}
            periods = self.pool.get('account.period').get_period_from_date(cr, uid, wizard_date)
            if periods:
                period_name = self.pool.get('account.period').browse(cr, uid, periods)[0].name
            message = ""
            if not len(existing_currencies) > 0:
                message = 
                context.update({'message': "FX rates have been properly imported for the date %s; be aware that no rates have been defined on the 1st of %s for the following currencies..." % (wizard_date, period_name)})
            else:
                w_vals = {'currency_list': existing_currencies, 'state': 'yes/no'}
                message = "You are trying to import FX rates already defined in the system at the date specified; do you want to proceed?"
            context.update({'message': message})
            wizard_id = self.pool.get('warning.import.currencies').create(cr, uid, w_vals, context=context)
            return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'warning.import.currencies',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wizard_id,
                    'context': context
            }
        else:
            return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'confirm.import.currencies',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': context
            }
    
import_currencies()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
