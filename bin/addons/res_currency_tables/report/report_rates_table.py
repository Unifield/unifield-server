# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from report import report_sxw
from report_webkit.webkit_report import WebKitParser

class report_rates_table(WebKitParser):
    _name = 'report.rates.table'

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(report_rates_table, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def _get_lines(self, cr, uid, data, context=None):
        if context is None:
            context = {}
        period_start_dates = []
        header =  ['Ccy Code','Ccy Name']
        cr.execute("SELECT name, date_start FROM account_period WHERE date_start >= %s \
                                                                  AND date_start <= %s \
                                                                  AND special = False \
                                                             ORDER BY date_start ASC",
                   (data['form']['start_date'],
                    data['form']['end_date']))
        if cr.rowcount:
            periods = cr.fetchall()
            period_names = [x[0] for x in periods]
            period_start_dates = [x[1] for x in periods]
            header += period_names
        data['form']['header'] = header
        # get the table's currencies (or all)
        if data['form']['currency_table_id']:
            cr.execute("SELECT id, name, currency_name FROM res_currency WHERE currency_table_id = %s \
                                                                      ORDER BY name ASC",
                       str(data['form']['currency_table_id']))
        else:
            if context.get('active_ids') and not data['form'].get('export_all'):  # display only the selected currencies
                cr.execute("SELECT id, name, currency_name "
                           "FROM res_currency "
                           "WHERE currency_table_id IS NULL "
                           "AND id in %s "
                           "ORDER BY name ASC;", (tuple(context['active_ids']),))
            else:
                cr.execute("SELECT id, name, currency_name FROM res_currency WHERE currency_table_id IS NULL ORDER BY name ASC;")

        data['form']['report_lines'] = []
        if cr.rowcount:
            currencies = [[x[0], x[1], x[2]] for x in cr.fetchall()]
            for currency in currencies:
                line = currency[1:]
                for date in period_start_dates:
                    cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s \
                                                                     AND name <= %s \
                                                                     ORDER BY name DESC LIMIT 1",
                               (currency[0],
                                date))
                    if cr.rowcount:
                        line.append(cr.fetchall()[0][0])
                    else:
                        line.append('')
                data['form']['report_lines'].append(line)
        return data

    def create(self, cr, uid, ids, data, context=None):
        data = self._get_lines(cr, uid, data, context=context)
        a = super(report_rates_table, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

report_rates_table('report.msf.rates.table','res.currency.table','addons/res_currency_tables/report/rates_table_xls.mako')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
