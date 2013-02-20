import time

from report import report_sxw
import pooler
import locale
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class report_interactive(report_sxw.report_sxw):
    _name = 'report.interactive.export'
    
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        print "create"
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
        print csv_data
        return obj._create_csv(csv_data)

report_interactive('report.financing.interactive', 'financing.contract.contract', False, parser=False)



class report_interactive_2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_interactive_2, self).__init__(cr, uid, name, context=context)
        self.tot = []
        self.lines = {}
        self.localcontext.update({
            'getLines':self.getLines,
            'getTot':self.getTot,
            'getCostCenter':self.getCostCenter,
            'isDate':self.isDate,
        })

    def isDate(self,date):
        if len(date) > 9 :
            return True
        return False

    def getCostCenter(self,obj):
        ccs = []
        for cc in obj.cost_center_ids:
            ccs += [cc.code]
        return ', '.join(ccs)

    def getTot(self,o):
        if self.tot[o]:
            return self.tot[o]
        return ''

    def getLines(self,contract):
        pool = pooler.get_pool(self.cr.dbname)
        print "get lines"
        print contract
        csv_data = pool.get('wizard.interactive.report')._get_interactive_data(self.cr, self.uid, contract.id, context={'mako':True})
        lines = []
        print csv_data
        self.tot = csv_data.pop()[4:]
        print 

        for x in csv_data[1:]:
            print x
            code = x[0] and x[0] or x[1] and x[1] or x[2] and x[2]
            temp = [code] + [x[3]] + [int(x[4])] + [int(x[5])] + [x[6]] + [int(x[7])] + [int(x[8])]  + [x[9]]
            lines += [temp]
        return lines

SpreadsheetReport('report.financing.interactive.2', 'financing.contract.contract', 'addons/financing_contract/report/financing_interactive_xls.mako', parser=report_interactive_2)

