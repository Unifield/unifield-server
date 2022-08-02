# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import pooler
from tools.translate import _

from mako.template import Template
from mako import exceptions
import netsvc
from osv.osv import except_osv
import weasyprint
import tools
import os


class report_fully_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_fully_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getMoveLines': self.getMoveLines,
            'getAnalyticLines': self.getAnalyticLines,
            'getNumberOfEntries': self.getNumberOfEntries,
            'getImportedMoveLines': self.getImportedMoveLines,
            'getEntryType': self.getEntryType,
            'getRegRef': self.getRegRef,
            'getFreeRef': self.getFreeRef,
            'getDownPaymentReversals': self.getDownPaymentReversals,
            'getManualAmls': self.getManualAmls,
            'getManualAjis': self.getManualAjis,
            'getManualFreeLines': self.getManualFreeLines,
            'getManualAalColor': self.getManualAalColor,
            'update_percent': self.update_percent,
        })

        self._cache_move = {}
        self._cache_ana = {}

    def update_percent(self, nbloop, tot):
        bk_id = self.localcontext.get('background_id')
        if bk_id:
            self.pool.get('memory.background.report').write(self.cr, self.uid, bk_id, {'percent': min(0.9, max(0.1,nbloop/float(tot)))})

    def getEntryType(self, line):
        """
        Returns the Entry Type to be displayed in the Full Report for the current line
        """
        entry_type = _('Direct Payment')  # by default
        if line.direct_invoice:
            entry_type = _('Direct Invoice')
        elif line.from_cash_return and line.account_id.type_for_register == 'advance':
            if line.amount_in:
                entry_type = _('Advance Closing')
            else:
                entry_type = _('Advance')
        elif line.is_down_payment:
            entry_type = _('Down Payment')
        elif line.transfer_journal_id:
            if line.is_transfer_with_change:
                entry_type = _('Transfer with change')
            else:
                entry_type = _('Transfer')
        elif line.imported_invoice_line_ids:
            entry_type = _('Imported Invoice')
        elif line.from_import_cheque_id:
            entry_type = _('Imported Cheque')
        return entry_type

    def getRegRef(self, reg_line):
        if reg_line.direct_invoice_move_id:
            return reg_line.direct_invoice_move_id.name
        if reg_line.imported_invoice_line_ids:
            num = []
            for inv in reg_line.imported_invoice_line_ids:
                num.append(inv.move_id.name)
            return " ".join(num)
        if reg_line.from_import_cheque_id and reg_line.from_import_cheque_id.move_id:
            return reg_line.from_import_cheque_id.move_id.name
        return reg_line.ref or ''

    def filter_regline(self, regline_br):
        """
        :param regline_br: browsed regline
        :return: True to show detail of the reg line False to not display
        """
        # US-69

        # exclude ALL detail of register line of account of given user_type
        # (redondencies of invoice detail)
        # http://jira.unifield.org/browse/US-69?focusedCommentId=38845&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-38845
        excluded_acc_type_codes = [
            'tax',
            'cash',
            'receivables',
        ]
        if regline_br and regline_br.account_id and \
                regline_br.account_id.user_type:
            if regline_br.account_id.user_type.code and \
                    regline_br.account_id.user_type.code in \
                    excluded_acc_type_codes:
                return False
        return True

    def get_move_lines(self, move_ids):
        # We need move lines linked to the given move ID. Except the invoice counterpart.
        #+ Lines that have is_counterpart to True is the invoice counterpart. We do not need it.
        res = []
        if not move_ids:
            return res

        aml_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
        key = tuple(move_ids)

        if key not in self._cache_move:
            domain = [
                ('move_id', 'in', move_ids),
                ('is_counterpart', '=', False)
            ]
            aml_ids = aml_obj.search(self.cr, self.uid, domain)
            if aml_ids:
                res = aml_obj.browse(self.cr, self.uid, aml_ids, context={'lang': self.localcontext.get('lang')})
            self._cache_move[key] = sorted(res, key=lambda x: (x.invoice.number, x.line_number))
        return self._cache_move[key]

    def getMoveLines(self, move_brs, regline_br):
        """
        Fetch all lines except the partner counterpart one
        :param move_brs: browsed moves (JIs)
        :type move_brs: list
        :param regline_br: browsed regline
        """
        if not move_brs:
            return []
        if not self.filter_regline(regline_br):
            return []  # not any detail for this reg line
        return self.get_move_lines([m.id for m in move_brs])

    def getImportedMoveLines(self, ml_brs, regline_br):
        """
        Fetch all lines except the partner counterpart one
        :param ml_brs: list of browsed move lines
        :type ml_brs: list
        :param regline_br: browsed regline
        """
        if not self.filter_regline(regline_br):
            return []  # not any detail for this reg line
        if not ml_brs:
            return []

        # exclude detail for Balance/Sheet entries (whatever the Account type) booked in a HR journal are imported in a register
        # http://jira.unifield.org/browse/US-69?focusedCommentId=38845&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-38845
        move_ids = [
            ml.move_id.id for ml in ml_brs if not ( \
                ml.journal_id and ml.journal_id.type == 'hr' and \
                ml.account_id and ml.account_id.user_type and \
                ml.account_id.user_type.report_type in ('asset', 'liability', ))
        ]
        return self.get_move_lines(move_ids)

    def getAnalyticLines(self, analytic_ids):
        """
        Get anlytic lines history from given analytic lines
        """
        res = []
        if not analytic_ids:
            return res

        if isinstance(analytic_ids, (int, long)):
            analytic_ids = [analytic_ids]

        key = tuple(analytic_ids)
        if key not in self._cache_ana:
            al_obj = pooler.get_pool(self.cr.dbname).get('account.analytic.line')
            al_ids = al_obj.get_corrections_history(self.cr, self.uid, analytic_ids)
            if al_ids:
                res = sorted(al_obj.browse(self.cr, self.uid, al_ids, context={'lang': self.localcontext.get('lang')}), key=lambda x: x.id)
            self._cache_ana[key] = res

        return self._cache_ana[key]

    def getNumberOfEntries(self, o):
        """
        Returns the number of register lines booked in the register (o)
        """
        db = pooler.get_pool(self.cr.dbname)
        regline_obj = db.get('account.bank.statement.line')
        nb_lines = regline_obj.search(self.cr, self.uid, [('statement_id', '=', o.id)], count=True)
        return nb_lines

    def getFreeRef(self, acc_move_line):
        '''
        Return the "manual" invoice reference associated with the account move line if it exists
        (field Reference in DI and Free Reference in SI)
        Note: for Supplier Refund and SI with Source Doc that are synched from Project to Coordo,
        the free ref will appear in Project only (US-970)
        '''
        db = pooler.get_pool(self.cr.dbname)
        acc_inv = db.get('account.invoice')
        free_ref = False
        if acc_move_line:
            acc_move = acc_move_line.move_id
            inv_id = acc_inv.search(self.cr, self.uid, [('move_id', '=', acc_move.id)])
            if inv_id:
                inv = acc_inv.browse(self.cr, self.uid, inv_id, context={'lang': self.localcontext.get('lang')})
                free_ref = inv and inv[0].reference
            if not free_ref:
                # display the free ref if it is different from the "standard" ref
                if acc_move.name != acc_move.ref:
                    free_ref = acc_move.ref
        return free_ref or ''

    def getDownPaymentReversals(self, reg_line):
        '''
        If the register line corresponds to a down payment that has been totally or partially reversed,
        returns a list of the related account move line(s), else returns an empty list.
        '''
        dp_reversals = []
        db = pooler.get_pool(self.cr.dbname)
        acc_move_line_obj = db.get('account.move.line')
        second_acc_move_line_id = False
        if reg_line and reg_line.account_id.type_for_register == 'down_payment' and reg_line.first_move_line_id and reg_line.first_move_line_id.move_id:
            acc_move = reg_line.first_move_line_id.move_id
            acc_move_line_id = acc_move_line_obj.search(self.cr, self.uid, [('move_id', '=', acc_move.id), ('id', '!=', reg_line.first_move_line_id.id)])
            acc_move_line = acc_move_line_obj.browse(self.cr, self.uid, acc_move_line_id, context={'lang': self.localcontext.get('lang')})
            # totally reconciled
            reconcile_id = acc_move_line[0] and acc_move_line[0].reconcile_id or False
            if reconcile_id:
                second_acc_move_line_id = acc_move_line_obj.search(self.cr, self.uid, [('reconcile_id', '=', reconcile_id.id), ('id', '!=', acc_move_line[0].id)])
            else:
                # partially reconciled
                reconcile_partial_id = acc_move_line[0] and acc_move_line[0].reconcile_partial_id or False
                if reconcile_partial_id:
                    second_acc_move_line_id = acc_move_line_obj.search(self.cr, self.uid, [('reconcile_partial_id', '=', reconcile_partial_id.id), ('id', '!=', acc_move_line[0].id)])
            if second_acc_move_line_id:
                dp_reversals = acc_move_line_obj.browse(self.cr, self.uid, second_acc_move_line_id, context={'lang': self.localcontext.get('lang')})
        return dp_reversals

    def getManualAmls(self, o):
        """
        Returns of list of manual Journal Items booked on the same liquidity journal as the register (o),
        and with a posting date belonging to the register period
        (= a JI booked in Period 13 is visible in the December register report)
        """
        db = pooler.get_pool(self.cr.dbname)
        aml_obj = db.get('account.move.line')
        period_obj = db.get('account.period')
        # Don't get the dates directly from the o.period_id, otherwise it would have the type
        # "report.report_sxw._date_format" and would be interpreted differently depending on language settings
        period = period_obj.browse(self.cr, self.uid, o.period_id.id, fields_to_fetch=['date_start', 'date_stop'])
        aml_ids = aml_obj.search(self.cr, self.uid, [('journal_id', '=', o.journal_id.id),
                                                     ('status_move', '=', 'manu'),
                                                     ('date', '>=', period.date_start),
                                                     ('date', '<=', period.date_stop)])
        amls = aml_obj.browse(self.cr, self.uid, aml_ids, context={'lang': self.localcontext.get('lang')})
        return [aml for aml in amls]

    def getManualAjis(self, aml, free=False):
        """
        Returns of list of Account Analytic Lines linked to the manual JI in parameter
        If free = False returns only non Free1/2 lines, if free = True returns only Free lines.
        """
        if not aml:
            return []
        db = pooler.get_pool(self.cr.dbname)
        aji_obj = db.get('account.analytic.line')
        aji_ids = aji_obj.search(self.cr, self.uid, [('move_id', '=', aml.id), ('free_account', '=', free)])
        # add the correction lines if any
        return self.getAnalyticLines(aji_ids)

    def getManualFreeLines(self, aml):
        """
        Returns of list of Free1/Free2 Lines linked to the manual JI in parameter
        """
        return self.getManualAjis(aml, free=True)

    def getManualAalColor(self, aal):
        """
        :param aal: Analytic Line linked to a manual JI
        :return: the color to use (str) for the display of the Analytic line
        """
        color = 'grey'
        if aal.is_reallocated:
            color = 'purple'
        elif aal.is_reversal:
            color = 'green'
        elif aal.last_corrected_id:
            color = 'red'
        return color



class SpreadsheetReportX(SpreadsheetReport):
    def create(self, cr, uid, ids, data, context=None):
        if not context:
            context = {}
        context['pathit'] = True
        return super(SpreadsheetReportX, self).create(cr, uid, ids, data, context=context)


class report_fully_report2(report_sxw.report_sxw):
    _name = 'report.fully.report.pdf'

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        return table_obj.browse(cr, uid, ids, list_class=report_sxw.browse_record_list, context=context)

    def create(self, cr, uid, ids, data, context=None):
        parser_instance = self.parser(cr, uid, self.name2, context=context)
        parser_instance.orig_file = os.path.join(tools.config['addons_path'], 'register_accounting/report/fully_report_pdf.html')
        parser_instance.localcontext.update({'formatLang':parser_instance.format_xls_lang})
        parser_instance.localcontext.update({'objects': self.getObjects(cr, uid, ids, context)})


        body = Template(filename=parser_instance.orig_file, input_encoding='utf-8', output_encoding='utf-8', default_filters=['decode.utf8'])
        try :
            html = body.render(
                _=parser_instance.translate_call,
                **parser_instance.localcontext
            )
        except Exception:
            msg = exceptions.text_error_template().render()
            netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
            raise except_osv(_('Webkit render'), msg)

        wp = weasyprint.HTML(string=html)
        pdf = wp.write_pdf(stylesheets=[os.path.join(tools.config['addons_path'], 'register_accounting/report/fully_report_pdf.css')])

        return (pdf, 'pdf')



SpreadsheetReportX('report.fully.report','account.bank.statement','addons/register_accounting/report/fully_report_xls.mako', parser=report_fully_report)
report_fully_report2('report.fully.report.pdf', 'account.bank.statement', False, parser=report_fully_report)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
