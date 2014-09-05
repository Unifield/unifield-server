import time
from report import report_sxw
import pooler
import locale
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
from osv import osv

class report_project_expenses(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        res = {}

        obj = pool.get('wizard.expense.report')
        # Context updated with wizard's value
        contract_id = data['id']
        reporting_type = 'project'

        csv_data = obj._get_expenses_data(cr, uid, contract_id, reporting_type, context=context)

        return obj._create_csv(csv_data)

report_project_expenses('report.financing.project.expenses', 'financing.contract.contract', False, parser=False)

class allocated_expense_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(allocated_expense_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        """
        Check that each financing contract have a FP selected.
        This is to avoid UTP-1063 bug.
        """
        if context is None:
            context = {}
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        for contract in table_obj.browse(cr, uid, ids):
            if contract.format_id:
                if not contract.format_id.funding_pool_ids:
                    raise osv.except_osv(_('Warning'), _('No FP selected in the financing contract: %s') % (contract.name))
        return super(allocated_expense_report_xls, self).create(cr, uid, ids, data, context=context)

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
        self.totalRptCurrency = 0
        self.totalBookAmt = 0
        self.iter = []
        self.localcontext.update({
            'getLines':self.getLines,
            'getCostCenter':self.getCostCenter,
            'getAccountName':self.getAccountName,
            'getBookAm':self.getBookAm,
            'getSub1':self.getSub1,
            'getSub2':self.getSub2,
            'getLines2':self.getLines2,
            'getFormula':self.getFormula,
            'isDate':self.isDate,
            'totalRptCurrency': self.totalRptCurrency,
            'totalBookAmt':self.totalBookAmt,
            'getTotalRptCurrency': self.getTotalRptCurrency,
            'getTotalBookAmt': self.getTotalBookAmt,
        })

    def isDate(self,date):
        if len(date) > 9 :
            return True
        return False

    def getFormula(self):
        formul = ''
        iters = self.iter[1:]
        temp = self.iter[1:]
        tour = 1
        for i in temp:
            tour += 1
            nb = 0
            for x in iters:
                nb += x + 1
            rang = nb + 1
            formul += '+R[-'+str(rang)+']C'
            iters = self.iter[tour:]

        return self.totalRptCurrency
        return formul

    def getTotalBookAmt(self):
        return self.totalBookAmt

    def getTotalRptCurrency(self):
        return self.totalRptCurrency

    def getLines2(self,):
        return self.lines

    def getSub1(self,):
        temp = self.len1
        self.len1 = 0
        return temp

    def getSub2(self,):
        temp = self.len2
        self.len2 = 0
        return temp


    def getBookAm(self,contract,analytic_line):
        date_context = {'date': analytic_line.document_date,'currency_table_id': contract.currency_table_id and contract.currency_table_id.id or None}
        amount = self.pool.get('res.currency').compute(self.cr, self.uid, analytic_line.currency_id.id, contract.reporting_currency.id, analytic_line.amount_currency or 0.0, round=True, context=date_context)
        self.len1 += 1
        self.len2 += 1
        self.totalBookAmt += analytic_line.amount_currency
        self.totalRptCurrency += amount
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
        pool = pooler.get_pool(self.cr.dbname)
        contract_obj = self.pool.get('financing.contract.contract')
        format_line_obj = self.pool.get('financing.contract.format.line')
        contract_domain = contract_obj.get_contract_domain(self.cr, self.uid, contract, reporting_type=self.reporting_type)
        analytic_line_obj = self.pool.get('account.analytic.line')
        analytic_lines = analytic_line_obj.search(self.cr, self.uid, contract_domain, context=None)

        # list of analytic journal_ids which are in the engagement journals
        exclude_journal_ids = self.pool.get('account.analytic.journal').search(self.cr, self.uid, [('type','=','engagement')])
        exclude_line_ids = []
        for analytic_line in analytic_line_obj.browse(self.cr, self.uid, analytic_lines, context=None):
            if analytic_line.journal_id.id in exclude_journal_ids:
                exclude_line_ids.append(analytic_line.id)
        analytic_lines = [x for x in analytic_lines if x not in exclude_line_ids]

        # UFTP-16: First search in the triplet in format line, then in the second block below, search in quadruplet
        for analytic_line in analytic_line_obj.browse(self.cr, self.uid, analytic_lines, context=None):
            ids_adl = self.pool.get('account.destination.link').search(self.cr, self.uid,[('account_id', '=', analytic_line.general_account_id.id),('destination_id','=',analytic_line.destination_id.id) ])
            ids_fcfl = format_line_obj.search(self.cr, self.uid, [('account_destination_ids','in',ids_adl), ('format_id', '=', contract.format_id.id)])
            for fcfl in format_line_obj.browse(self.cr, self.uid, ids_fcfl):
                ana_tuple = (analytic_line, fcfl.code, fcfl.name)
                if lines.has_key(fcfl.code):
                    if not ana_tuple in lines[fcfl.code]:
                        lines[fcfl.code] += [ana_tuple]
                else:
                    lines[fcfl.code] = [ana_tuple]

        # UFTP-16: First search in the triplet in format line, then in the second block below, search in quadruplet
        for analytic_line in analytic_line_obj.browse(self.cr, self.uid, analytic_lines, context=None):
            ids_adl = self.pool.get('financing.contract.account.quadruplet').search(self.cr, self.uid,[('account_id', '=', analytic_line.general_account_id.id),('account_destination_id','=',analytic_line.destination_id.id) ])
            ids_fcfl = format_line_obj.search(self.cr, self.uid, [('account_quadruplet_ids','in',ids_adl), ('format_id', '=', contract.format_id.id)])
            for fcfl in format_line_obj.browse(self.cr, self.uid, ids_fcfl):
                ana_tuple = (analytic_line, fcfl.code, fcfl.name)
                if lines.has_key(fcfl.code):
                    if not ana_tuple in lines[fcfl.code]:
                        lines[fcfl.code] += [ana_tuple]
                else:
                    lines[fcfl.code] = [ana_tuple]

        self.lines = lines
        for x in lines:
            self.iter.append(len(lines[x]))
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

allocated_expense_report_xls('report.financing.allocated.expenses.2','financing.contract.contract','addons/financing_contract/report/project_expenses_xls.mako', parser=report_project_expenses3)

