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

    def check_currency(self, cr, uid, line, date, context=None):
        """
        Do some check on data
        """
        if not context:
            context = {}
        if not line or not date:
            raise osv.except_osv(_('Error'), _('Missing argument'))
            return False, 'missing_argument', _('Missing argument')
        # Prepare some values
        currency_obj = self.pool.get('res.currency')
        currency_rate_obj = self.pool.get('res.currency.rate')
        # we have a currency ISO code; search it and its rates
        currency_ids = currency_obj.search(cr, uid, [('name', '=', line[0])], context=context)
        if len(currency_ids) == 0:
            raise osv.except_osv(_('Error'), _('The currency %s is not defined!') % line[0])
            return False, 'undefined', _('Undefined')
        # check for date. 2 checks done:
        # - if the rate date is the 1st of the month, no check.
        # - all other dates: check if the 1st day of the month has a rate;
        #   otherwise, raise a warning
        rate_datetime = datetime.datetime.strptime(date, '%Y-%m-%d')
        if rate_datetime.day != 1:
            rate_date_start = '%s-%s-01' % (rate_datetime.year, rate_datetime.month)
            cr.execute("SELECT name FROM res_currency_rate WHERE currency_id = %s AND name = %s" ,(currency_ids[0], rate_date_start))
            if not cr.rowcount:
                return False, 'no_first_rate', _('No date at the first day of this month.')
        # Now, creating/updating the rate (if all is ok)
        currency_rates = currency_rate_obj.search(cr, uid, [('currency_id', '=', currency_ids[0]), ('name', '=', date)], context=context)
        if len(currency_rates) > 0:
            return False, 'exist', _('Already exists at this date.')
        return True, '', ''

    def import_rates(self, cr, uid, ids, context=None, auto_import=False):
        """
        Read wizard and import currencies even if they already exists.
        Create a list of what problem have been encounted during process.
        """
        # Some checks
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Prepare some values
        currency_obj = self.pool.get('res.currency')
        currency_rate_obj = self.pool.get('res.currency.rate')
        currency_list = []
        date = None

        def manage_error(line_index, msg, name='', code='', status=''):
            if auto_import:
                rejected_lines.append((line_index, [name, code, status], msg))
            else:
                raise osv.except_osv(_('Error'), 'Line %s, %s' % (line_index, _(msg)))

        for wizard in self.browse(cr, uid, ids, context=context):
            if not wizard.import_file:
                raise osv.except_osv(_('Warning'), _('Please browse a csv file.'))
            import_file = base64.decodestring(wizard.import_file)
            import_string = StringIO.StringIO(import_file)
            import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))

            if not import_data:
                raise osv.except_osv(_('Warning'), _('File is empty.'))

            self._check_periods(cr, uid, wizard.rate_date, context=context)
            date = wizard.rate_date
            processed_lines = []
            rejected_lines = []
            headers = []
            line_index = 0
            for line in import_data:
                if not line:
                    # ignore empty lines
                    continue
                if auto_import:
                    # auto_import uses a Date column, useless here
                    # remove it
                    line = line[1:]
                if line_index == 0:
                    headers = line
                    if headers[0] != 'Currency Code' and headers[0] != 'Rate':
                        msg = _('File header is not in the correct format and cannot be imported.')
                        manage_error(line_index, msg)
                    else:
                        line_index += 1
                        continue
                if len(line) != 2:
                    msg = _('File is not in the correct format and cannot be imported.')
                    manage_error(line_index, msg)
                else:
                    if len(line[0]) > 0 and len(line[0]) == 3:
                        # update context with active_test = False; otherwise, non-set currencies
                        context.update({'active_test': False})
                        line_res, line_problem, line_problem_description = self.check_currency(cr, uid, line, wizard.rate_date, context)
                        currency_ids = currency_obj.search(cr, uid, [('name', '=', line[0])], context=context)
                        if line_res:
                            # No rate for this date: create it
                            currency_rate_obj.create(cr, uid, {
                                'name': wizard.rate_date,
                                'rate': float(line[1]),
                                'currency_id': currency_ids[0]
                            })
                            processed_lines.append((line_index,[]))
                        else:
                            currency_list.append([line, "%s (%s)" % (line[0], line_problem_description)])
                            rejected_lines.append((line, "%s (%s)" % (line[0], line_problem_description)))
                    else:
                        msg = _('File is not in the correct format and cannot be imported.')
                        manage_error(line_index, msg)
                line_index += 1

        if auto_import:
            return processed_lines, rejected_lines, headers

        # Prepare some info
        model = 'confirm.import.currencies'
        complementary_data = {}
        # Give currencies list if any problem occurred
        if currency_list and len(currency_list) > 0:
            model = 'warning.import.currencies'
            wizard_id = self.pool.get(model).create(cr, uid, {'currency_list': '\n'.join([x and x and x[1] for x in currency_list]), 'date': date}, context=context)
            # create lines regarding currency_list content
            for currency in currency_list:
                self.pool.get('warning.import.currencies.lines').create(cr, uid, {'code': currency[0][0], 'rate': float(currency[0][1]), 'wizard_id': wizard_id,}, context=context)
            complementary_data.update({'res_id': wizard_id})
        # Prepare result
        res = {
            'type': 'ir.actions.act_window',
            'res_model': model,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }
        # Add complementary data if necessary
        if complementary_data:
            res.update(complementary_data)
        # return right wizard
        return res

import_currencies()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
