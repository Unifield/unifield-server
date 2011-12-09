import time

from report import report_sxw
import pooler
import locale
import StringIO
import csv

class report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        res = {}
        contract_obj = pool.get('financing.contract.contract')

        obj = pool.get('wizard.csv.report')
        # Context updated with wizard's value
        contract_id = data['id']
        reporting_type = 'project' #???????
        context.update({'reporting_type': reporting_type})
        
        contract = contract_obj.browse(cr, uid, contract_id, context=context)
        
        header_data = obj._get_contract_header(cr, uid, contract, context=context)
        footer_data = obj._get_contract_footer(cr, uid, contract, context=context)
        
        # Report lines with analytic lines for each one
        analytic_data = [['Date',
                          'Analytic Journal',
                          'Reference',
                          'Description',
                          'General Account',
                          'Cost Center',
                          'Funding Pool',
                          'Booking Amount',
                          'Booking Currency',
                          'Reporting Amount',
                          'Reporting Currency',
                          'Invoice Line']]
        contract_domain = contract_obj.get_contract_domain(cr,
                                                           uid,
                                                           contract,
                                                           reporting_type=reporting_type,
                                                           context=context)
        # get lines
        analytic_line_obj = pool.get('account.analytic.line')
        analytic_lines = analytic_line_obj.search(cr, uid, contract_domain ,context=context)
        amount_sum = 0.0
        amount_currency_sum = 0.0
        currency_table = None
        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
            date_context = {'date': analytic_line.source_date or analytic_line.date,
                            'currency_table_id': contract.currency_table_id and contract.currency_table_id.id or None}
            amount = pool.get('res.currency').compute(cr,
                                                           uid,
                                                           analytic_line.currency_id.id,
                                                           contract.reporting_currency.id, 
                                                           analytic_line.amount_currency or 0.0,
                                                           round=True,
                                                           context=date_context)
            amount_currency = analytic_line.amount_currency
            amount_sum += amount
            amount_currency_sum += amount_currency
            
            # Localized to add comma separators for thousands
            formatted_amount = locale.format("%.2f", amount, grouping=True)
            formatted_amount_currency = locale.format("%.2f", amount_currency, grouping=True)
            
            analytic_data.append([analytic_line.date,
                                  analytic_line.journal_id.name,
                                  analytic_line.ref or '',
                                  analytic_line.name,
                                  analytic_line.general_account_id.code + ' ' + analytic_line.general_account_id.name,
                                  analytic_line.cost_center_id.name,
                                  analytic_line.account_id.name,
                                  formatted_amount,
                                  contract.reporting_currency.name,
                                  formatted_amount_currency,
                                  analytic_line.currency_id.name,
                                  analytic_line.invoice_line_id.name])
            
        # Localized to add comma separators for thousands
        formatted_amount_sum = locale.format("%.2f", amount_sum, grouping=True)
        formatted_amount_currency_sum = locale.format("%.2f", amount_currency_sum, grouping=True)
        
        analytic_data.append(['','','','','','','',formatted_amount_sum,'', formatted_amount_currency_sum])
        
        data = header_data + [[]] + analytic_data + [[]] + footer_data
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(line)
        out = buffer.getvalue()    
        buffer.close()
        return (out, 'csv')

report('report.financing.test', 'financing.contract.contract', False, parser=False)
