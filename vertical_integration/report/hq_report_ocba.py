# -*- coding: utf-8 -*-

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
    # digits decimal number for amounts
    # like for OCA: 2 for entries, 8 for ccy rate
    _ENTRIES_DIGITS = 2
    _EXCHANGE_RATE_DIGITS = 8
    _CUR_ADJ_JOURNAL_TYPE = ('cur_adj', )

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

    def export_ji(self, cr, uid, r, file_data, build_data):
        """
        Export not expense entries (from JIs)
        """
        if r.account_id and r.account_id.shrink_entries_for_hq:
            # account with 'shrink entries for HQ':
            # pivot data with sum booking/func balance
            key = (
                r.account_id.code,
                r.currency_id.name,
                r.journal_id.code,
            )
            if not key in build_data['shrink']:
                build_data['shrink'][key] = {
                    'booking': 0.,
                    'func': 0.,
                    'is_cur_adj': self._CUR_ADJ_JOURNAL_TYPE \
                        and r.journal_id.type in self._CUR_ADJ_JOURNAL_TYPE,
                    'account_name': r.account_id.name or '',
                    'ids': [],  # shrinked ids
                }

            # sum/append shrink amount/ids
            build_data['shrink'][key]['booking'] += \
                r.debit_currency - r.credit_currency
            build_data['shrink'][key]['func'] += r.debit - r.credit
            build_data['shrink'][key]['ids'].append(r.id)
            return

        data={
            'DB ID': finance_export.finance_archive._get_hash(cr, uid, [r.id], 'account.move.line'),
            'Proprietary instance': self._enc(r.instance_id and r.instance_id.code or r.instance_id.name or ''),
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
            'Booking Debit': self._enc_amount(not r.is_addendum_line and r.debit_currency or 0.),
            'Booking Credit': self._enc_amount(not r.is_addendum_line and r.credit_currency or 0.),
            'Booking Currency': self._enc(r.currency_id and r.currency_id.name or ''),
            'Functional Debit': self._enc_amount(r.debit),
            'Functional Credit': self._enc_amount(r.credit),
            'Functional Currency': self._enc(r.functional_currency_id and r.functional_currency_id.name or ''),
            'Exchange rate': self._enc_amount(self._get_rate(cr, uid, r, is_analytic=False), digits=self._EXCHANGE_RATE_DIGITS),
            'Reconciliation code': self._enc(r.reconcile_txt),  # only for B/S)
        }
        self._add_row('entries', file_data=file_data, data=data)

    def export_shrinked_entries(self, cr, uid, file_data, build_data, key):
        account_code, ccy_name, journal_code = key
        
        # shrink entry balance sum amounts (per account/ccy/journal)
        entry_data = build_data['shrink'][key]
        if entry_data['booking'] == 0. and entry_data['func'] == 0.:
            # skip null entry
            return
        booking = entry_data['booking']
        func = entry_data['func']

        # auto seq number for shrink entry
        period = build_data['period']
        seq_number = "%s-%s-%s-%s-%s-%s" % (
            build_data['move_prefix'],
            period.date_start[5:7], period.date_start[:4],
            account_code, ccy_name, journal_code,
        )

        rate = booking / func if func != 0 else 0.
        if entry_data['is_cur_adj']:
            booking = 0.  # always 0 for FXA entries
            rate = 1.

        # line description from account code, ccy, journal, period
        description = "Subtotal - %s - %s - %s - %s" % (
            account_code, ccy_name, journal_code,
            build_data['period_name'], )

        data={
            'DB ID': finance_export.finance_archive._get_hash(cr, uid, entry_data['ids'], 'account.move.line'),
            'Proprietary instance': '',
            'Journal Code': self._enc(journal_code),
            'Entry Sequence': seq_number,
            'Description': self._enc(description),
            'Reference': '',
            'Document Date': build_data['default_date'],
            'Posting Date': build_data['default_date'],
            'G/L Account': self._enc(account_code or ''),
            'Account description': self._enc(entry_data['account_name']),
            'Third Party': '',
            'EE ID': '',
            'Partner DB ID': '',
            'Destination': '',
            'Cost Centre': '',
            'Booking Debit': self._enc_amount(booking, debit=True),
            'Booking Credit': self._enc_amount(booking, debit=False),
            'Booking Currency': self._enc(ccy_name or ''),
            'Functional Debit': self._enc_amount(func, debit=True),
            'Functional Credit': self._enc_amount(func, debit=False),
            'Functional Currency': self._enc(build_data['functional_ccy_name']),
            'Exchange rate': self._enc_amount(rate,
                digits=self._EXCHANGE_RATE_DIGITS),
            'Reconciliation code': '',
        }
        self._add_row('entries', file_data=file_data, data=data)

    def export_aji(self, cr, uid, r, file_data, build_data):
        """
        Export not expense entries (from AJIs)
        """
        rate = 0

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

        data={
            'DB ID': finance_export.finance_archive._get_hash(cr, uid, [r.id], 'account.analytic.line'),
            'Proprietary instance': self._enc(r.instance_id and r.instance_id.code or r.instance_id.name or ''),
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
            'Exchange rate': self._enc_amount(self._get_rate(cr, uid, r, is_analytic=True), digits=self._EXCHANGE_RATE_DIGITS),
            'Reconciliation code': '',  # no reconcile for expense account
        }
        self._add_row('entries', file_data=file_data, data=data)

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
        zip_buffer = self._generate_files(data['target_filename_suffix'],
            file_data)
        self._mark_exported_entries(cr, uid, move_line_ids, analytic_line_ids)
        return (zip_buffer.getvalue(), 'zip', )

    def _generate_data(self, cr, uid, file_data=None, form_data=None,
            context=None):
        pool = pooler.get_pool(cr.dbname)
        aml_obj = pool.get('account.move.line')
        aal_obj = pool.get('account.analytic.line')

        # set internal build data
        period = pool.get('account.period').browse(cr, uid,
            form_data['period_id'])

        functional_ccy_name = pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.currency_id.name
        country_code = "0"
        move_prefix = "0"
        if len(form_data['instance_ids']) > 0:
            parent_instance = pool.get('msf.instance').browse(cr, uid,
                form_data['instance_ids'][0], context=context)
            if parent_instance:
                country_code = self._translate_country(cr, uid, pool,
                    parent_instance, context=context)
                if period and period.date_start:
                    move_prefix = parent_instance.move_prefix[:2]

        build_data = {
            'period': period,
            'period_name': period and period.code or '',
            'default_date': period and period.date_stop and \
                datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').date().strftime('%d/%m/%Y') or "",
            'functional_ccy_name': functional_ccy_name,
            'country_code': country_code,
            'move_prefix': move_prefix,
            'shrink': {},
        }

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
                self.export_ji(cr, uid, ji_br, file_data, build_data)

        # export skrinked entries for hq
        # (data build in 'build_data' during 'export_ji')
        for key in build_data['shrink']:
            self.export_shrinked_entries(cr, uid, file_data, build_data, key)

        # get expense lines
        domain = [
            ('period_id', '=', form_data['period_id']),
            ('instance_id', 'in', form_data['instance_ids']),
            ('journal_id.type', 'not in', ['hq', 'engagement', 'migration', ]),  # HQ/ENG/MIG entries already exist in SAP
            ('account_id.category', 'not in', ['FREE1', 'FREE2']),  # only FP dimension
            ('exported', 'in', form_data['to_export']),  # exported filter
            '|',
            ('move_id', '=', False),  # synced (so posted) AJI without JI
            ('move_id.move_id.state', '=', 'posted'),  # move line of posted JE
        ]
        analytic_line_ids = aal_obj.search(cr, uid, domain, context=context)
        if analytic_line_ids:
            for aji_br in aal_obj.browse(cr, uid, analytic_line_ids,
                context=context):
                self.export_aji(cr, uid, aji_br, file_data, build_data)

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

    def _generate_files(self, target_filename, file_data):
        """
        :return zip buffer
        """
        zip_buffer = StringIO.StringIO()
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        tmp_fds = []

        # fill zip file
        for f in file_data:
            tmp_fd = NamedTemporaryFile('w+b', delete=False)
            tmp_fds.append(tmp_fd)
            writer = csv.writer(tmp_fd, quoting=csv.QUOTE_ALL)

            for line in file_data[f]['data']:
                writer.writerow(map(self._enc, line))
            tmp_fd.close()

            out_zipfile.write(tmp_fd.name, target_filename + ".csv",
                zipfile.ZIP_DEFLATED)
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

    def _enc_amount(self, amount, debit=None, digits=False):
        """
        :param amount: amount
        :param debit: for AJI specify if is for the debit or credit csv output
        :return:
        """
        if not digits:
            digits=self._ENTRIES_DIGITS

        if isinstance(amount, float):
            if abs(amount) < 0.001:
                amount = 0.
            if debit is not None:
                if debit:
                    # ensure debit
                    amount = amount < 0 and abs(round(amount, digits)) or 0.
                else:
                    # ensure credit
                    amount = amount > 0 and round(amount, digits) or 0.
        else:
            amount = round(0., digits)

        return str(amount)

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
