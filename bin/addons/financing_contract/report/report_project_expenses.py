from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
import logging

assert _  # pyflakes check

class report_project_expenses2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        if not context:
            context={}
        super(report_project_expenses2, self).__init__(cr, uid, name, context=context)
        if 'reporting_type' in context:
            self.reporting_type = context['reporting_type']
        else:
            self.reporting_type = 'project'
        self.len1 = 0
        self.len2 = 0
        self.lines = {}
        self.totalRptCurrency = {}
        self.totalBookAmt = 0
        self.localcontext.update({
            'getLines':self.getLines,
            'getCostCenter':self.getCostCenter,
            'getAccountName':self.getAccountName,
            'getBookAm':self.getBookAm,
            'getSub1':self.getSub1,
            'getSub2':self.getSub2,
            'getLines2':self.getLines2,
            'totalBookAmt':self.totalBookAmt,
            'getTotalRptCurrency': self.getTotalRptCurrency,
            'getTotalBookAmt': self.getTotalBookAmt,
        })


    def getTotalBookAmt(self):
        return self.totalBookAmt

    def getTotalRptCurrency(self, contract):
        return self.totalRptCurrency.get(contract.id, 0.0)

    def getLines2(self,):
        return self.lines

    def getSub1(self,):
        temp = self.len1
        self.len1 = 0
        return temp

    def getSub2(self,):
        """
        len2 gives the number of previous line for a given CC.
        Return number of lines then intialize to 0
        """
        res = self.len2
        self.len2 = 0
        return res

    def getBookAm(self,contract,analytic_line):
        # this report is based on doc. date
        date_context = {'currency_date': analytic_line.document_date,
                        'currency_table_id': contract.currency_table_id and contract.currency_table_id.id or None}
        amount = self.pool.get('res.currency').compute(self.cr, self.uid, analytic_line.currency_id.id, contract.reporting_currency.id, analytic_line.amount_currency or 0.0, round=True, context=date_context)
        self.len1 += 1
        self.len2 += 1
        self.totalBookAmt += analytic_line.amount_currency
        if not contract.id in self.totalRptCurrency:
            self.totalRptCurrency[contract.id] = 0.0
        self.totalRptCurrency[contract.id] += amount
        return amount

    def getAccountName(self,analytic_line):
        name = ''
        if analytic_line.general_account_id and analytic_line.general_account_id.code:
            name = analytic_line.general_account_id.code + ' '
        if analytic_line.general_account_id and analytic_line.general_account_id.name:
            name += analytic_line.general_account_id.name
        return name

    def getLines(self,contract):
        lines = {}
        if self.objects[0].format_id.reporting_type == 'allocated' and self.name == 'financing.project.expenses.2':
            return []
        if self.objects[0].format_id.reporting_type == 'project' and self.name == 'financing.allocated.expenses.2':
            return []
        contract_obj = self.pool.get('financing.contract.contract')
        format_line_obj = self.pool.get('financing.contract.format.line')
        logger = logging.getLogger('contract.report')

        contract_domain = contract_obj.get_contract_domain(self.cr, self.uid, contract, reporting_type=self.reporting_type)
        analytic_line_obj = self.pool.get('account.analytic.line')
        analytic_lines = analytic_line_obj.search(self.cr, self.uid, contract_domain, context=None)

        # list of analytic journal_ids which are in the engagement journals: to be added in get_contract_domain ?
        exclude_journal_ids = self.pool.get('account.analytic.journal').search(self.cr, self.uid, [('type','=','engagement')])

        # gen a dict to store aji cond = reporting_line.code, reporting_line.name
        line_code_name_by_cond = {}
        reporting_lines_id = format_line_obj.search(self.cr, self.uid, [('format_id', '=', contract.format_id.id), ('line_type', '!=', 'view')])
        for report_line in format_line_obj.browse(self.cr, self.uid, reporting_lines_id):
            if report_line.is_quadruplet:
                for quad in report_line.account_quadruplet_ids:
                    line_code_name_by_cond[(quad.account_id.id, quad.account_destination_id.id, quad.cost_center_id.id, quad.funding_pool_id.id)] = (report_line.code, report_line.name)
            elif not report_line.reporting_select_accounts_only:
                for triplet in report_line.account_destination_ids:
                    line_code_name_by_cond[(triplet.account_id.id, triplet.destination_id.id)] = (report_line.code, report_line.name)
            else:
                for gl_only in report_line.reporting_account_ids:
                    line_code_name_by_cond[gl_only.id] = (report_line.code, report_line.name)

        # iterate over aji, to link each aji to its reporting_line
        for analytic_line in analytic_line_obj.browse(self.cr, self.uid, analytic_lines, context=None):
            if analytic_line.journal_id.id in exclude_journal_ids:
                continue
            quad_key = (analytic_line.general_account_id.id, analytic_line.destination_id.id, analytic_line.cost_center_id.id, analytic_line.account_id.id)
            if quad_key in line_code_name_by_cond:
                lines.setdefault(line_code_name_by_cond[quad_key], []).append((analytic_line, line_code_name_by_cond[quad_key][0], line_code_name_by_cond[quad_key][1]))
            elif quad_key[0:2] in line_code_name_by_cond:
                triplet_key = quad_key[0:2]
                lines.setdefault(line_code_name_by_cond[triplet_key], []).append((analytic_line, line_code_name_by_cond[triplet_key][0], line_code_name_by_cond[triplet_key][1]))
            elif quad_key[0] in line_code_name_by_cond:
                gl_key = quad_key[0]
                lines.setdefault(line_code_name_by_cond[gl_key], []).append((analytic_line, line_code_name_by_cond[gl_key][0], line_code_name_by_cond[gl_key][1]))
            else:
                logger.warn('AJI id:%s, name: %s does not match any reporting lines on contract %s' % (analytic_line.id, analytic_line.entry_sequence, self.objects[0].code))

        self.lines = lines
        return lines


    def getCostCenter(self,obj):
        ccs = []
        for cc in obj.cost_center_ids:
            ccs += [cc.code]
        return ', '.join(ccs)

class report_project_expenses3(report_project_expenses2):
    def __init__(self, cr, uid, name, context=None):
        super(report_project_expenses3, self).__init__(cr, uid, name, context={'reporting_type': 'allocated'})

SpreadsheetReport('report.financing.project.expenses.2','financing.contract.contract','addons/financing_contract/report/project_expenses_xls.mako', parser=report_project_expenses2)

SpreadsheetReport('report.financing.allocated.expenses.2','financing.contract.contract','addons/financing_contract/report/project_expenses_xls.mako', parser=report_project_expenses3)

