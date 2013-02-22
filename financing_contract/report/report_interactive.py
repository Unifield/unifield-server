import time
from report import report_sxw
import pooler
import locale
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class report_interactive(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_interactive, self).__init__(cr, uid, name, context=context)
        self.tot = []
        self.lines = {}
        self.localcontext.update({
            'getLines':self.getLines,
            'getTot':self.getTot,
            'getCostCenter':self.getCostCenter,
            'isDate':self.isDate,
            'checkType':self.checkType,
        })

    def checkType(self,obj):
        if obj.reporting_type == 'project':
            return False
        return True

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
        csv_data = pool.get('wizard.interactive.report')._get_interactive_data(self.cr, self.uid, contract.id, context={'mako':True})
        lines = []
        self.tot = csv_data.pop()[4:]
        for x in csv_data[1:]:
            code = x[0] and x[0] or x[1] and x[1] or x[2] and x[2]
            if contract.reporting_type == 'project':
                temp = [code] + [int(x[3])] + [int(x[4])] + [int(x[5])] + [x[6]] 
            else:
                temp = [code] + [int(x[3])] + [int(x[4])] + [int(x[5])] + [x[6]] + [int(x[7])] + [int(x[8])]  + [x[9]]
            lines += [temp]
        return lines

SpreadsheetReport('report.financing.interactive.2', 'financing.contract.contract', 'addons/financing_contract/report/financing_interactive_xls.mako', parser=report_interactive)

