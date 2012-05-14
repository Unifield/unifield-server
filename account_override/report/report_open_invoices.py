# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import csv
import StringIO

from report import report_sxw

class report_open_invoices(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st
    
    def create(self, cr, uid, ids, data, context=None):
        result = []
        # Create the header
        customer_header = ['Invoice Date', 'Number', 'Customer', 'Description', 'Responsible', 'Due Date', 'Source Document', 'Currency', 'Residual', 'Total', 'State']
        supplier_header = ['Invoice Date', 'Number', 'Supplier', 'Description', 'Responsible', 'Due Date', 'Source Document', 'Currency', 'Residual', 'Total', 'State']
        
        # retrieve a big sql query with all information
        sql_request = """
            SELECT DISTINCT invoice.date_invoice, move.name,
                            partner.name, invoice.name, responsible.name,
                            invoice.date_due, invoice.origin,
                            currency.name, invoice.residual,
                            invoice.amount_total, invoice.state
            FROM 
                account_invoice invoice
                LEFT JOIN account_move move ON invoice.move_id = move.id
                LEFT JOIN res_partner partner ON invoice.partner_id = partner.id
                LEFT JOIN res_users responsible ON invoice.user_id = responsible.id
                LEFT JOIN res_currency currency ON invoice.currency_id = currency.id
            WHERE 
                invoice.state NOT IN ('paid', 'cancel') AND
                invoice.type = '%s'
            ORDER BY invoice.date_invoice
        """
        
        # Customer Invoices
        result.append(['Customer Invoices'])
        result.append(customer_header)
        cr.execute(sql_request % ('out_invoice'))
        result += cr.fetchall()
        result.append([])
        
        # Supplier Invoices
        result.append(['Supplier Invoices'])
        result.append(supplier_header)
        cr.execute(sql_request % ('in_invoice'))
        result += cr.fetchall()
        result.append([])
        
        # Customer Refunds
        result.append(['Customer Refunds'])
        result.append(customer_header)
        cr.execute(sql_request % ('out_refund'))
        result += cr.fetchall()
        result.append([])
        
        # Supplier Refunds
        result.append(['Supplier Refunds'])
        result.append(supplier_header)
        cr.execute(sql_request % ('in_refund'))
        result += cr.fetchall()
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in result:
            writer.writerow(map(self._enc,line))
        out = buffer.getvalue()    
        buffer.close()
        return (out, 'csv')

report_open_invoices('report.open.invoices', 'account.invoice', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
