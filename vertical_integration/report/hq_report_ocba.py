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

import datetime
import csv
import StringIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os
from osv import osv
from tools.translate import _

from report import report_sxw

from account_override import finance_export


class hq_report_ocba(report_sxw.report_sxw):
    _export_fields_index = {
        'entries': [
            'DB ID',  # xmlid
            'Proprietary instance',
            'Journal Code',
            'Entry Sequence',
            'Description',
            'Reference',
            'Document Date',
            'Posting Date',
            'G/L Account',  # code
            'Account description',
            'Third Party',
            'EE ID',  # nat/staff ID Number
            'Partner DB ID',  # xmlid
            'Destination',
            'Cost Centre',
            'Booking Debit',
            'Booking Credit',
            'Booking Currency',
            'Functional Debit',
            'Functional Credit',
            'Functional Currency',
            'Exchange rate',  # of exported month based on booking ccy
            'Reconciliation code',  # only for B/S
        ]
    }

    def export_ji(self, cr, uid, r, file_data):
        """
        Export not expense entries (from JIs)
        """
        self._add_row('entries', file_data=file_data, data={
            'DB ID': finance_export.finance_archive._get_hash(cr, uid, [r.id], 'account.move.line'),
            'Proprietary instance': self._enc(r.instance_id and r.instance_id.name or ''),
            'Journal Code': self._enc(r.journal_id and r.journal_id.code or ''),
            'Entry Sequence': self._enc(r.move_id and r.move_id.name or ''),
            'Description': self._enc(r.name),
            'Reference': self._enc(r.ref),
            'Document Date': r.document_date or '',
            'Posting Date': r.date or '',
            'G/L Account': self._enc(r.account_id and r.account_id.code or ''),  # code
            'Account description': self._enc(r.account_id and r.account_id.name or ''),
            'Third Party': self._enc(r.partner_id and r.partner_id.name or ''),  # US-497: extract name from partner_id (better than partner_txt)
            'EE ID': self._enc(r.employee_id and r.employee_id.identification_id or ''),  # nat/staff ID Number
            'Partner DB ID': r.partner_id and finance_export.finance_archive._get_hash(cr, uid, [r.partner_id.id], 'res_partner') or '',
            'Destination': '',
            'Cost Centre': '',
            'Booking Debit': self._enc_amount(r.is_addendum_line and r.debit_currency or 0.),
            'Booking Credit': self._enc_amount(r.is_addendum_line and r.credit_currency or 0.),
            'Booking Currency': self._enc(r.currency_id and r.currency_id.name or ''),
            'Functional Debit': self._enc_amount(r.debit),
            'Functional Credit': self._enc_amount(r.credit),
            'Functional Currency': self._enc(r.functional_currency_id and r.functional_currency_id.name or ''),
            'Exchange rate': self._enc_amount(self._get_rate(cr, uid, r, is_analytic=False)),
            'Reconciliation code': self._enc(r.reconcile_txt),  # only for B/S)
        })

    def export_aji(self, cr, uid, r, file_data):
        """
        Export not expense entries (from AJIs)
        """
        rate = 0  # TODO

        ee_id = ''
        partner_db_id = ''
        partner_txt = ''
        if r.move_id:
            ee_id = self._enc(r.move_id.employee_id and r.move_id.employee_id.identification_id or '')
            partner_db_id = r.move_id.partner_id and finance_export.finance_archive._get_hash(cr, uid, [r.move_id.partner_id.id], 'res_partner') or ''
            partner_txt = r.move_id.partner_id and r.move_id.partner_id.name or ''
        # NOTE: if from sync no move line, no 3rd party link, only partner_txt:
        # impossible to get EE ID/Partner ID hash

        booking_amount = r.amount_currency
        if r.journal_id and r.journal_id.type == 'cur_adj':
            # FXA entries no booking
            booking_amount = 0.

        self._enc_amount(r.amount_currency, debit=True)

        self._add_row('entries', file_data=file_data, data={
            'DB ID': finance_export.finance_archive._get_hash(cr, uid, [r.id], 'account.analytic.line'),
            'Proprietary instance': self._enc(r.instance_id and r.instance_id.name or ''),
            'Journal Code': self._enc(r.journal_id and r.journal_id.code or ''),
            'Entry Sequence': self._enc(r.entry_sequence or ''),
            'Description': self._enc(r.name),
            'Reference': self._enc(r.ref),
            'Document Date': r.document_date or '',
            'Posting Date': r.date or '',
            'G/L Account': self._enc(r.general_account_id and r.general_account_id.code or ''),  # code
            'Account description': self._enc(r.general_account_id and r.general_account_id.name or ''),
            'Third Party': self._enc(partner_txt),
            'EE ID': ee_id,  # nat/staff ID Number
            'Partner DB ID': partner_db_id,
            'Destination': self._enc(r.destination_id and r.destination_id.code or ''),
            'Cost Centre': self._enc(r.cost_center_id and r.cost_center_id.code or ''),
            'Booking Debit': self._enc_amount(booking_amount, debit=True),
            'Booking Credit': self._enc_amount(booking_amount, debit=False),
            'Booking Currency': self._enc(r.currency_id and r.currency_id.name or ''),
            'Functional Debit': self._enc_amount(r.amount, debit=True),
            'Functional Credit': self._enc_amount(r.amount, debit=False),
            'Functional Currency': self._enc(r.functional_currency_id and r.functional_currency_id.name or ''),
            'Exchange rate': self._enc_amount(self._get_rate(cr, uid, r, is_analytic=True)),
            'Reconciliation code': '',  # no reconcile for expense account
        })

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        def get_wizard_data(data, form_data):
            # top instance
            form_data['instance_ids'] = data['form']['instance_ids']

            # period
            period = pool.get('account.period').browse(cr, uid,
                data['form']['period_id'])# only for B/S)
            form_data['period'] = period
            form_data['period_id'] = period.id

            # integration reference
            integration_ref = ''
            if len(data['form']['instance_ids']) > 0:
                parent_instance = pool.get('msf.instance').browse(cr, uid,
                    data['form']['instance_ids'][0], context=context)
                if parent_instance:
                    if period and period.date_start:
                        integration_ref = parent_instance.code[:2] \
                            + period.date_start[5:7]
            form_data['integration_ref'] = integration_ref

            # to export filter: (never exported or all)
            selection = data['form'].get('selection', False)
            if not selection:
                raise osv.except_osv(_('Error'),
                    _('No selection value for lines to select.'))
            if selection == 'all':
                to_export = ['f', 't']
            elif selection == 'unexported':
                to_export = ['f']
            else:
                raise osv.except_osv(_('Error'),
                    _('Wrong value for selection: %s.') % (selection, ))
            form_data['to_export'] = to_export

        file_data = {
            'entries': { 'file_name': 'entries', 'data': [], 'count': 0, },
        }

        # get wizard form values
        pool = pooler.get_pool(cr.dbname)
        form_data = {}
        get_wizard_data(data, form_data)

        # generate export data
        move_line_ids, analytic_line_ids = self._generate_data(cr, uid,
            file_data=file_data, form_data=form_data,
            context=context)

        # generate zip result and post processing
        zip_buffer = self._generate_files(form_data['integration_ref'],
            file_data)
        self._mark_exported_entries(cr, uid, move_line_ids, analytic_line_ids)
        return (zip_buffer.getvalue(), 'zip', )

    def _generate_data(self, cr, uid, file_data=None, form_data=None,
            context=None):
        pool = pooler.get_pool(cr.dbname)
        aml_obj = pool.get('account.move.line')
        aal_obj = pool.get('account.analytic.line')

        # get not expense entries
        domain = [
            ('period_id', '=', form_data['period_id']),
            ('instance_id', 'in', form_data['instance_ids']),
            ('account_id.is_analytic_addicted', '=', False),  # not expense
            ('move_id.state', '=', 'posted'),  # JE posted
            ('journal_id.type', 'not in', ['hq', 'migration', ]),  # HQ/MIG entries already exist in SAP
            ('exported', 'in', form_data['to_export']),  # exported filter
        ]
        move_line_ids = aml_obj.search(cr, uid, domain, context=context)
        if move_line_ids:
            for ji_br in aml_obj.browse(cr, uid, move_line_ids,
                context=context):
                self.export_ji(cr, uid, ji_br, file_data)

        # get expense lines
        domain = [
            ('period_id', '=', form_data['period_id']),
            ('instance_id', 'in', form_data['instance_ids']),
            ('journal_id.type', 'not in', ['hq', 'engagement', 'migration', ]),  # HQ/ENG/MIG entries already exist in SAP
            ('account_id.category', 'not in', ['FREE1', 'FREE2']),  # only FP dimension
            ('exported', 'in', form_data['to_export']),  # exported filter
            ('move_id.move_id.state', '=', 'posted'),  # move line of posted JE
        ]
        analytic_line_ids = aal_obj.search(cr, uid, domain, context=context)
        if analytic_line_ids:
            for aji_br in aal_obj.browse(cr, uid, analytic_line_ids,
                context=context):
                self.export_aji(cr, uid, aji_br, file_data)

        return (move_line_ids, analytic_line_ids, )

    def _add_row(self, data_key_name, file_data=None, data=None):
        if file_data[data_key_name]['count'] == 0:
            # add header
            file_data[data_key_name]['data'].append(
                [ f for f in self._export_fields_index[data_key_name] ])

        row = []
        for f in self._export_fields_index[data_key_name]:
            row.append(data.get(f, ''))
        file_data[data_key_name]['data'].append(row)
        file_data[data_key_name]['count'] += 1

    def _generate_files(self, integration_ref, file_data):
        """
        :return zip buffer
        """
        zip_buffer = StringIO.StringIO()
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        tmp_fds = []
        file_prefix = integration_ref and (integration_ref + '_') or ''

        # fill zip file
        for f in file_data:
            tmp_fd = NamedTemporaryFile('w+b', delete=False)
            tmp_fds.append(tmp_fd)
            writer = csv.writer(tmp_fd, quoting=csv.QUOTE_ALL)

            for line in file_data[f]['data']:
                writer.writerow(map(self._enc, line))
            tmp_fd.close()

            out_zipfile.write(tmp_fd.name,
                "%s%s.csv" % (file_prefix, file_data[f]['file_name'], ),
                zipfile.ZIP_DEFLATED
            )
        out_zipfile.close()

        # delete temporary files
        for fd in tmp_fds:
            os.unlink(fd.name)

        return zip_buffer

    def _mark_exported_entries(self, cr, uid, move_line_ids, analytic_line_ids):
        if move_line_ids:
            cr.execute(
                "UPDATE account_move_line SET exported='t' WHERE id in %s",
                (tuple(move_line_ids), )
            )

        if analytic_line_ids:
            cr.execute(
                "UPDATE account_analytic_line SET exported='t' WHERE id in %s",
                (tuple(analytic_line_ids), )
            )

    def _get_rate(self, cr, uid, r, is_analytic=False):
        def get_month_rate(currency_id, entry_dt):
            cr.execute(
                "SELECT rate FROM res_currency_rate WHERE currency_id = %s" \
                    " AND name <= %s ORDER BY name desc LIMIT 1" ,
                (currency_id, entry_dt, )
            )
            return cr.rowcount and cr.fetchall()[0][0] or False

        if r.currency_id.id == r.functional_currency_id.id:
            return 1.

        # US-478 accrual account (always refer to previous period)
        # base on doc date instead posting in this case
        # - 1st period accruals: doc date and posting same period
        # - next accruals: doc date previous period (accrual of)
        if not is_analytic:
            entry_dt = r.journal_id and r.journal_id.type == 'accrual' \
                and r.document_date or r.date
        else:
            entry_dt = r.date
            if r.move_id:
                if r.move_id.journal_id.type == 'accrual':
                    entry_dt = r.document_date or r.date
            elif r.journal_id and r.journal_id.code == 'ACC':
                # sync border case no JI for the AJI
                entry_dt = r.document_date or r.date

        return get_month_rate(r.currency_id.id, entry_dt)

    def _enc(self, st):
        if not st:
            return ''
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def _enc_amount(self, amount, debit=None):
        """
        :param amount: amount
        :param debit: for AJI specify if is for the debit or credit csv output
        :return:
        """
        res = "0.0"
        if amount:
            if amount < 0.001:
                amount = 0.
            if debit is None:
                res = str(amount)
            else:
                if debit:
                    if amount < 0:
                        res = str(abs(amount))
                else:
                    if amount > 0:
                        res = str(amount)
        return res

    def _translate_country(self, cr, uid, pool, browse_instance, context={}):
        mapping_obj = pool.get('country.export.mapping')
        if browse_instance:
            mapping_ids = mapping_obj.search(cr, uid, [('instance_id', '=', browse_instance.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], context=context)
                return mapping.mapping_value
        return "0"

hq_report_ocba('report.hq.ocba', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
