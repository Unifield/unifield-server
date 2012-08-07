import time

from report import report_sxw
import pooler
import locale

class report_interactive(report_sxw.report_sxw):
    _name = 'report.interactive.export'

    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        res = {}
        contract_obj = pool.get('financing.contract.contract')
        
        if 'out_currency' in data:
            out_currency = data['out_currency']
            output_currency_obj = pool.get('res.currency').browse(cr, uid, out_currency, context=context)
            context['output_currency'] = output_currency_obj

        if context:
            contract_id = context['active_id']
            
        obj = pool.get('wizard.interactive.report')
        csv_data = obj._get_interactive_data(cr, uid, contract_id, context=context)
        
        return obj._create_csv(csv_data)

report_interactive('report.financing.interactive', 'financing.contract.contract', False, parser=False)
