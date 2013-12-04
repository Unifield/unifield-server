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
from osv import osv
import pooler
from report_webkit.webkit_report import WebKitParser
import xml.sax.saxutils

class report_currency_table(WebKitParser):
    _name = 'report.currency.table'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(report_currency_table, self).create_single_pdf(cr, uid, ids, data, report_xml, context)
    
    def _get_lines(self, cr, uid, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        currency = pool.get('res.currency').browse(cr, uid, data['form']['currency_id'], context=context)
        header = [currency.name]
        # list of tuples with (table_name, currency_id)
        currency_tables = [('Standard', currency.id)]
        for currency_table_id in data['form']['currency_table_ids']:
            currency_table = pool.get('res.currency.table').browse(cr, uid, currency_table_id, context=context)
            cr.execute("SELECT id FROM res_currency WHERE currency_table_id = %s \
                                                      AND reference_currency_id = %s \
                                                 ORDER BY name ASC",
                                                         (str(currency_table_id),
                                                          str(currency.id)))
            if cr.rowcount:
                table_currency_id = cr.fetchall()[0][0]
                currency_tables.append((currency_table.name, table_currency_id))
                
        header += [x[0] for x in currency_tables]
        data['form']['header'] = header
        # Get periods
        data['form']['report_lines'] = []
        periods = []
        cr.execute("SELECT name, date_start FROM account_period WHERE date_start >= %s \
                                                                  AND date_start <= %s \
                                                                  AND special = False \
                                                             ORDER BY date_start ASC",
                                                                     (data['form']['start_date'],
                                                                      data['form']['end_date']))
        if cr.rowcount:
            periods = cr.fetchall()
        
        for period in periods:
            line = [period[0]]
            for currency in [x[1] for x in currency_tables]:
                cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s \
                                                                 AND name <= %s \
                                                                 ORDER BY name DESC LIMIT 1",
                                                                    (currency,
                                                                     period[1]))
                if cr.rowcount:
                    line.append(cr.fetchall()[0][0])
                else:
                    line.append('')
            data['form']['report_lines'].append(line)
            
        return data
    
    def create(self, cr, uid, ids, data, context=None):
        data = self._get_lines(cr, uid, data, context=context)
        a = super(report_currency_table, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
    
report_currency_table('report.msf.currency.table','res.currency.table','addons/res_currency_tables/report/currency_table_xls.mako')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
