from report import report_sxw
import pooler
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
assert _ #pyflakes check

class report_interactive(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_interactive, self).__init__(cr, uid, name, context=context)
        self.context = {}
        self.tot = []
        self.lines = []
        self.localcontext.update({
            'getLines':self.getLines,
            'getTot':self.getTot,
            'getCostCenter':self.getCostCenter,
            'checkType':self.checkType,
            'checkType2':self.checkType2,
        })


    def checkType2(self,):
        taille = 0
        for x in self.lines:
            if len(x) > taille:    # taille = 'size'
                taille = len(x)
        if taille < 7:
            return False
        return True

    def checkType(self,obj,line=False):
        if line:
            if obj.reporting_type == 'project' or len(line) < 7:
                return False
            return True
        else:
            if obj.reporting_type == 'project' :
                return False
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

        self.context.update({'mako': True})
        if 'out_currency' in self.datas:
            self.context.update({'out_currency': self.datas['out_currency']})

        csv_data = pool.get('wizard.interactive.report')._get_interactive_data(self.cr, self.uid, contract.id, context=self.context)

        lines = []
        if contract.reporting_type == 'project':
            self.tot = csv_data.pop()[2:]
        else:
            self.tot = csv_data.pop()[2:]

        for x in csv_data[1:]:
            if contract.reporting_type == 'project' or len(x) < 7:
                code = x[0] and x[0] or ''
                temp = [code] + [x[1]] + [x[2]] + [x[3]] + [x[4]]
            else:
                code = x[0] and x[0] or x[1] and x[1] or x[2] and x[2]
                temp = [code] + [x[1]] + [x[2]] + [x[3]] + [x[4]] + [x[5]] + [x[6]]  + [x[7]]
            lines += [temp]
        self.lines = lines
        return lines

    def set_context(self, objects, data, ids, report_type=None):
        self.context = data.get('context', {})
        return super(report_interactive, self).set_context(objects, data, ids, report_type)


SpreadsheetReport('report.financing.interactive.2', 'financing.contract.contract', 'addons/financing_contract/report/financing_interactive_xls.mako', parser=report_interactive)

