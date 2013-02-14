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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from report import report_sxw
from tools.translate import _

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
        customer_header = ['Document Date', 'Posting Date', 'Number', 'Customer', 'Description', 'Responsible', 'Due Date', 'Source Document', 'Currency', 'Residual', 'Total', 'State']
        supplier_header = ['Document Date', 'Posting Date', 'Number', 'Supplier', 'Description', 'Responsible', 'Due Date', 'Source Document', 'Currency', 'Residual', 'Total', 'State']
        
        # retrieve a big sql query with all information
        sql_request = """
            SELECT DISTINCT invoice.document_date, invoice.date_invoice, move.name,
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


class report_open_invoices2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_open_invoices2, self).__init__(cr, uid, name, context=context)
        self.cur = ''
        self.funcCur = ''
        self.res = 0
        self.tot = 0
        self.localcontext.update({
            'getLines':self.getLines,
            'getConvert':self.getConvert,
            'getFuncCur':self.getFuncCur,
            'getCurTot':self.getCurTot,
            'getRes':self.getRes,
            'getTot':self.getTot,
            'isDate':self.isDate,
        })
        return

    def isDate(self,date):
        if date:
            return True
        return False

    def getRes(self):
        temp = self.res
        self.res = 0
        return temp

    def getTot(self):
        temp = self.tot
        self.tot = 0
        return temp

    def getLines(self,option):
        ids = []
        result = []
        sql_request = """
            SELECT DISTINCT invoice.id, invoice.document_date, invoice.date_invoice, move.name,
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
        if option == 'ci':
            self.cr.execute(sql_request % ('out_invoice'))
            result = self.cr.fetchall()
        
        # Supplier Invoices
        if option == 'si':
            self.cr.execute(sql_request % ('in_invoice'))
            result = self.cr.fetchall()

        # Customer Refunds
        if option == 'cr':
            self.cr.execute(sql_request % ('out_refund'))
            result = self.cr.fetchall()
        
        # Supplier Refunds
        if option == 'sr':
            self.cr.execute(sql_request % ('in_refund'))
            result = self.cr.fetchall()

        return result

    def getConvert(self,id_,amount,option):
        ids = []
        bro_ac = self.pool.get('account.invoice').browse(self.cr, self.uid, id_)
        conv = self.pool.get('res.currency').compute(self.cr, self.uid, bro_ac.currency_id.id, bro_ac.journal_id.company_id.currency_id.id, amount or 0.0, round=True,)

        if option == 'res':
            self.res += 1
        elif option == 'tot':
            self.tot += 1

        return conv

    def getFuncCur(self,id_):
        bro_ac = self.pool.get('account.invoice').browse(self.cr, self.uid, id_)
        self.funcCur = bro_ac.journal_id and bro_ac.journal_id.company_id and bro_ac.journal_id.company_id.currency_id.name or ''
        return bro_ac.journal_id and bro_ac.journal_id.company_id and bro_ac.journal_id.company_id.currency_id.name or ''

    def getCurTot(self):
        return self.funcCur

SpreadsheetReport('report.open.invoices.2','account.invoice','addons/account_override/report/open_invoices_xls.mako', parser=report_open_invoices2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
