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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from osv import osv
from tools.translate import _

class combined_journals_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(combined_journals_report, self).__init__(cr, uid, name, context=context)
        self.context = {}
        self.selector_id = False
        self.aml_domain = []
        self.aal_domain = []
        self.analytic_journal_ids = []
        self.analytic_axis = 'fp'  # 'fp', 'f1' or 'f2'
        self.total_booking_debit = 0.0
        self.total_booking_credit = 0.0
        self.total_func_debit = 0.0
        self.total_func_credit = 0.0
        self.percent = 0.0
        self.line_position = 0
        self.nb_lines = 0  # total number of lines to be displayed
        self.localcontext.update({
            'analytic_axis': lambda *a: self.analytic_axis,
            'lines': self._get_lines,
            'criteria': self._get_criteria,
            'current_inst_code': self._get_current_instance_code,
            'total_booking_debit': lambda *a: self.total_booking_debit,
            'total_booking_credit': lambda *a: self.total_booking_credit,
            'total_func_debit': lambda *a: self.total_func_debit,
            'total_func_credit': lambda *a: self.total_func_credit,
            'update_percent_display': self._update_percent_display,
            'display_hq_account': self.display_hq_account,
            'get_col_widths': self.get_col_widths,
        })
        self._display_hq_account = self.pool.get('account.export.mapping')._is_mapping_display_active(cr, uid)

    def display_hq_account(self):
        return self._display_hq_account

    def get_col_widths(self):
        if self._display_hq_account:
            if self.analytic_axis == 'fp':
                return {'colWidths': "45.0,33.0,41.0,52.0,38.0,44.0,44.0,30.0,39.0,39.0,35.0,36.0,26.0,40.0,40.0,28.0,40.0,40.0,28.0,31.0,35.0,39.0"}
            return {'colWidths': "45.0,35.0,43.0,53.0,40.0,48.0,48.0,33.0,42.0,47.0,42.0,38.0,47.0,32.0,42.0,40.0,32.0,37.0,38.0,41.0"}

        if self.analytic_axis == 'fp':
            return {'colWidths': "45.0,36.0,46.0,52.0,39.0,45.0,45.0,31.0,40.0,40.0,36.0,37.0,33.0,41.0,41.0,31.0,41.0,41.0,31.0,36.0,36.0"}

        return {'colWidths': "45.0,36.0,48.0,55.0,41.0,49.0,49.0,34.0,43.0,48.0,43.0,45.0,45.0,38.0,45.0,45.0,38.0,38.0,38.0"}

    def _cmp_sequence_account_type(self, a, b):
        """
        Comparison function to sort the JIs by Entry Sequence and then Account "analytic_addicted"
        """
        if a['entry_sequence'] > b['entry_sequence']:
            return 1
        elif a['entry_sequence'] < b['entry_sequence']:
            return -1
        else:
            if a['account_analytic_addicted'] > b['account_analytic_addicted']:
                return 1
            elif a['account_analytic_addicted'] < b['account_analytic_addicted']:
                return -1
        return 0

    def _get_lines(self):
        """
        - Returns a list of dicts containing the data to display:
            - first, ordered by Entry Sequence:
                => the JIs booked on a "NON analytic_addicted" account
                => the AJIs or Free1/2 lines (depending on the self.analytic_axis) linked to the same JE
            - then, ordered by Entry Sequence:
                => the AJIs without JIs.
        - Updates the global totals in booking & functional (self.total_booking_debit...).
        - Updates the % of the process (cf report run in BG) from 0 to 50%.
        """
        res = []
        aml_obj = self.pool.get('account.move.line')
        aal_obj = self.pool.get('account.analytic.line')
        user_obj = self.pool.get('res.users')
        analytic_acc_obj = self.pool.get('account.analytic.account')
        bg_obj = self.pool.get('memory.background.report')
        bg_id = False
        if self.context.get('background_id'):
            bg_id = self.context['background_id']
        company = user_obj.browse(self.cr, self.uid, self.uid, fields_to_fetch=['company_id'], context=self.context).company_id
        func_currency_name = company.currency_id.name
        allow_display_hq_accounts = company.display_hq_system_accounts_buttons
        if bg_id:
            self.percent += 0.05  # 5% of the total process
            bg_obj.update_percent(self.cr, self.uid, [bg_id], self.percent)
        # get the JIs corresponding to the criteria selected
        aml_ids = aml_obj.search(self.cr, self.uid, self.aml_domain, context=self.context, order='move_id ASC')
        amls = []
        aml_fields = ['instance_id', 'journal_id', 'move_id', 'name', 'ref', 'document_date', 'date', 'period_id', 'account_id',
                      'partner_txt', 'debit_currency', 'credit_currency', 'currency_id', 'debit', 'credit', 'reconcile_txt',
                      'move_state', 'hq_system_account']
        current_line_position = 0
        aml_num = len(aml_ids)
        processed = 0
        step = 1000
        while processed < aml_num:
            limit = processed
            processed += step
            for aml in aml_obj.browse(self.cr, self.uid, aml_ids[limit:processed], fields_to_fetch=aml_fields, context=self.context):
                current_line_position += 1
                aml_dict = {
                    'type': 'aml',
                    'id': aml.id,
                    'prop_instance': aml.instance_id and aml.instance_id.code or '',
                    'journal_code': aml.journal_id.code,
                    'entry_sequence': aml.move_id.name,
                    'description': aml.name,
                    'reference': aml.ref or '',
                    'document_date': aml.document_date,
                    'posting_date': aml.date,
                    'period': aml.period_id.code or '',
                    'gl_account': '%s - %s' % (aml.account_id.code, aml.account_id.name),
                    'account_analytic_addicted': aml.account_id.is_analytic_addicted and 1 or 0,
                    'third_party': aml.partner_txt or '',
                    'cost_center': '',
                    'destination': '',
                    'funding_pool': '',
                    'analytic_account': '',
                    'booking_debit': aml.debit_currency or 0.0,
                    'booking_credit': aml.credit_currency or 0.0,
                    'booking_currency': aml.currency_id and aml.currency_id.name or '',
                    'func_debit': aml.debit or 0.0,
                    'func_credit': aml.credit or 0.0,
                    'func_currency': func_currency_name,
                    'reconcile': aml.reconcile_txt or '',
                    'status': aml.move_state,
                    'hq_system_account': allow_display_hq_accounts and aml.hq_system_account or '',
                }
                amls.append(aml_dict)
                self.percent = bg_obj.compute_percent(self.cr, self.uid, current_line_position, len(aml_ids), before=0.05, after=0.15, context=self.context)
        amls = sorted(amls, key=lambda a: '%s-%s' % (a['entry_sequence'], a['account_analytic_addicted']))
        if bg_id:
            self.percent += 0.05  # 20% of the total process
            bg_obj.update_percent(self.cr, self.uid, [bg_id], self.percent)
        aal_fields = ['instance_id', 'journal_id', 'entry_sequence', 'name', 'ref', 'document_date', 'date',
                      'period_id', 'general_account_id', 'partner_txt', 'cost_center_id', 'destination_id', 'account_id',
                      'amount_currency', 'currency_id', 'amount', 'move_id', 'hq_system_account']
        current_line_position = 0
        for ml in amls:
            current_line_position += 1
            # if the JI has no related Analytic lines, store it directly
            # check Entry Seq. matching to exclude REV/COR AJI linked to the original JI in case of a pure AD correction
            search_aal_domain = [('move_id', '=', ml['id']), ('entry_sequence', '=', ml['entry_sequence'])]
            category = (self.analytic_axis == 'f1' and 'FREE1') or (self.analytic_axis == 'f2' and 'FREE2') or 'FUNDING'
            analytic_account_ids = analytic_acc_obj.search(self.cr, self.uid,
                                                           [('category', '=', category), ('type', '=', 'normal')],
                                                           context=self.context, order='NO_ORDER')
            search_aal_domain.append(('account_id', 'in', analytic_account_ids))
            aal_ids = aal_obj.search(self.cr, self.uid, search_aal_domain, context=self.context, order='NO_ORDER')
            if not aal_ids:
                res.append(ml)
                self.total_booking_debit += ml['booking_debit']
                self.total_booking_credit += ml['booking_credit']
                self.total_func_debit += ml['func_debit']
                self.total_func_credit += ml['func_credit']
            # else store only the related Analytic lines
            else:
                for aal in aal_obj.browse(self.cr, self.uid, aal_ids, fields_to_fetch=aal_fields, context=self.context):
                    aal_dict = {
                        'type': 'aal',
                        'id': aal.id,
                        'prop_instance': aal.instance_id and aal.instance_id.code or '',
                        'journal_code': aal.journal_id.code,
                        'entry_sequence': aal.entry_sequence or '',
                        'description': aal.name,
                        'reference': aal.ref or '',
                        'document_date': aal.document_date,
                        'posting_date': aal.date,
                        'period': aal.period_id and aal.period_id.code or '',
                        'gl_account': '%s - %s' % (aal.general_account_id.code, aal.general_account_id.name),
                        'account_analytic_addicted': 1,
                        'third_party': aal.partner_txt or '',
                        'cost_center': aal.cost_center_id and aal.cost_center_id.code or '',
                        'destination': aal.destination_id and aal.destination_id.code or '',
                        'funding_pool': aal.account_id.code or '',
                        'analytic_account': aal.account_id.code or '',  # can be a Funding Pool or a Free1/2 account
                        'booking_debit': aal.amount_currency < 0 and abs(aal.amount_currency) or 0.0,
                        'booking_credit': aal.amount_currency >= 0 and aal.amount_currency or 0.0,
                        'booking_currency': aal.currency_id and aal.currency_id.name or '',
                        'func_debit': aal.amount < 0 and abs(aal.amount) or 0.0,
                        'func_credit': aal.amount >= 0 and aal.amount or 0.0,
                        'func_currency': func_currency_name,
                        'reconcile': aal.move_id and aal.move_id.reconcile_txt or '',
                        'status': aal.move_id and aal.move_id.move_state or '',
                        'hq_system_account': allow_display_hq_accounts and aal.hq_system_account or '',
                    }
                    res.append(aal_dict)
                    self.total_booking_debit += aal_dict['booking_debit']
                    self.total_booking_credit += aal_dict['booking_credit']
                    self.total_func_debit += aal_dict['func_debit']
                    self.total_func_credit += aal_dict['func_credit']
                    self.percent = bg_obj.compute_percent(self.cr, self.uid, current_line_position, len(amls), before=0.20, after=0.45, context=self.context)
        # get the AJIs corresponding to the criteria selected AND not linked to a JI (use self.aal_domain)
        orphan_aal_ids = aal_obj.search(self.cr, self.uid, self.aal_domain, context=self.context, order='entry_sequence')
        current_line_position = 0
        for al in aal_obj.browse(self.cr, self.uid, orphan_aal_ids, fields_to_fetch=aal_fields, context=self.context):
            current_line_position += 1
            al_dict = {
                'type': 'aal',
                'id': al.id,
                'prop_instance': al.instance_id and al.instance_id.code or '',
                'journal_code': al.journal_id.code,
                'entry_sequence': al.entry_sequence or '',
                'description': al.name,
                'reference': al.ref or '',
                'document_date': al.document_date,
                'posting_date': al.date,
                'period': al.period_id and al.period_id.code or '',
                'gl_account': '%s - %s' % (al.general_account_id.code, al.general_account_id.name),
                'account_analytic_addicted': 1,
                'third_party': al.partner_txt or '',
                'cost_center': al.cost_center_id and al.cost_center_id.code or '',
                'destination': al.destination_id and al.destination_id.code or '',
                'funding_pool': al.account_id.code or '',
                'analytic_account': al.account_id.code or '',
                'booking_debit': al.amount_currency < 0 and abs(al.amount_currency) or 0.0,
                'booking_credit': al.amount_currency >= 0 and al.amount_currency or 0.0,
                'booking_currency': al.currency_id and al.currency_id.name or '',
                'func_debit': al.amount < 0 and abs(al.amount) or 0.0,
                'func_credit': al.amount >= 0 and al.amount or 0.0,
                'func_currency': func_currency_name,
                'reconcile': '',
                'status': '',
                'hq_system_account': al.hq_system_account or '',
            }
            res.append(al_dict)
            self.total_booking_debit += al_dict['booking_debit']
            self.total_booking_credit += al_dict['booking_credit']
            self.total_func_debit += al_dict['func_debit']
            self.total_func_credit += al_dict['func_credit']
            self.percent = bg_obj.compute_percent(self.cr, self.uid, current_line_position, len(orphan_aal_ids), before=0.45, after=0.5, context=self.context)
        self.nb_lines = len(res)
        return res

    def _get_criteria(self):
        """
        Returns a String corresponding to the criteria selected
        """
        selector_obj = self.pool.get('account.mcdb')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        # first get the Analytic axis
        category = (self.analytic_axis == 'f1' and 'Free 1') or (self.analytic_axis == 'f2' and 'Free 2') or 'Funding Pool'
        criteria = 'Display: %s' % category
        # then get all the other criteria from the 'account.move.line' model
        model = 'account.move.line'
        aml_selection = selector_obj.get_selection_from_domain(self.cr, self.uid, self.aml_domain, model, context=self.context)
        if aml_selection:
            criteria = '%s ; %s' % (criteria, aml_selection)
        # finally get the Analytic Journal list
        if self.analytic_journal_ids:
            analytic_journals = analytic_journal_obj.read(self.cr, self.uid, self.analytic_journal_ids, ['code'],
                                                          context=self.context)
            journal_selection = '%s: %s' % (_('Analytic Journals'),
                                            ', '.join([analytic_journal['code'] for analytic_journal in analytic_journals]))
            criteria = '%s ; %s' % (criteria, journal_selection)
        # truncate the string if it is too long
        if len(criteria) > 4000:
            criteria = "%s..." % criteria[:4000]
        return criteria or '-'

    def _get_current_instance_code(self):
        """
        Returns the code of the current instance
        """
        res_obj = self.pool.get('res.users')
        company = res_obj.browse(self.cr, self.uid, self.uid, fields_to_fetch=['company_id'], context=self.context).company_id
        return company.instance_id and company.instance_id.code or ''

    def _update_percent_display(self):
        """
        Updates the % of the process (cf report run in background)
        from self.percent (end of the data recovery) to 100% (end of the display generation).
        """
        bg_obj = self.pool.get('memory.background.report')
        self.line_position += 1
        return bg_obj.compute_percent(self.cr, self.uid, self.line_position, self.nb_lines, before=self.percent, after=1,
                                      context=self.context) or True

    def set_context(self, objects, data, ids, report_type=None):
        """
        Gets the domains to take into account for JIs and AJIs and stores them in self.aml_domain and self.aal_domain,
        stores the Analytic Axis in self.analytic_axis
        """
        selector_obj = self.pool.get('account.mcdb')
        journal_obj = self.pool.get('account.journal')
        aal_obj = self.pool.get('account.analytic.line')
        self.context = data.get('context', {})
        self.selector_id = data.get('selector_id', False)
        if not self.selector_id:
            raise osv.except_osv(_('Warning'), _('Selector not found.'))
        self.analytic_axis = data.get('analytic_axis', 'fp')
        # get the domain for the Journal Items
        aml_context = self.context.copy()
        aml_context.update({'selector_model': 'account.move.line'})  # Analytic axis will be excluded
        self.aml_domain = selector_obj._get_domain(self.cr, self.uid, self.selector_id, context=aml_context)
        # get the domain for the Analytic Journal Items
        aal_context = self.context.copy()
        aal_context.update({'selector_model': 'account.analytic.line'})
        original_aal_domain = selector_obj._get_domain(self.cr, self.uid, self.selector_id, context=aal_context)
        aal_domain = []
        analytic_journal_ids = set()
        analytic_journal_operator = 'in'
        for t in original_aal_domain:
            # get the Analytic Journals matching the G/L journals selected
            if t[0] == 'gl_journal_id':
                journal_dom = [('id', t[1], t[2])]  # ex: ('gl_journal_id', 'not in', (9,)) ==> [('id', 'not in', (9,))]
                gl_journal_ids = journal_obj.search(self.cr, self.uid, journal_dom, context=self.context)
                for gl_journal in journal_obj.browse(self.cr, self.uid, gl_journal_ids,
                                                     fields_to_fetch=['analytic_journal_id'], context=self.context):
                    if gl_journal.analytic_journal_id:
                        analytic_journal_ids.add(gl_journal.analytic_journal_id.id)
            # add the Analytic Journals selected if any
            elif t[0] == 'analytic_journal_id':
                analytic_journal_operator = t[1]
                self.analytic_journal_ids.extend(t[2])  # store the journals selected in the Analytic Journals filter (only)
                analytic_journal_ids.update(t[2])
            # exclude Entry Status
            elif t[0] != 'move_id.state':
                aal_domain.append(t)
        if analytic_journal_ids:
            aal_domain.append(('journal_id', analytic_journal_operator, list(analytic_journal_ids)))
        # only take into account AJIs which are NOT linked to a JI i.e. without move_id
        # Particular case: AJIs generated by a pure AD correction have the original JI as move_id
        analytic_line_ids = aal_obj.search(self.cr, self.uid, aal_domain, context=self.context)
        aji_ids = []
        aji_fields = ['move_id', 'journal_id', 'last_corrected_id', 'reversal_origin']
        for aji in aal_obj.browse(self.cr, self.uid, analytic_line_ids, fields_to_fetch=aji_fields, context=self.context):
            if not aji.move_id:
                aji_ids.append(aji.id)
            elif aji.journal_id.type in ('correction', 'correction_hq', 'extra'):
                corrected_aal = aji.last_corrected_id or aji.reversal_origin or False
                corrected_aml = corrected_aal and corrected_aal.move_id or False
                if corrected_aml and corrected_aml.last_cor_was_only_analytic and corrected_aml.id == aji.move_id.id:
                    aji_ids.append(aji.id)
        self.aal_domain = [('id', 'in', aji_ids)]
        return super(combined_journals_report, self).set_context(objects, data, ids, report_type)


# XLS report
SpreadsheetReport('report.combined.journals.report.xls', 'account.mcdb',
                  'addons/account_mcdb/report/combined_journals_report.mako', parser=combined_journals_report)

# PDF report
report_sxw.report_sxw('report.combined.journals.report.pdf', 'account.mcdb',
                      'addons/account_mcdb/report/combined_journals_report.rml', parser=combined_journals_report,
                      header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
