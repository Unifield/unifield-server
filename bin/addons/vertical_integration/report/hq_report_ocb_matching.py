# -*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from tools.translate import _
import pooler

from account_override import finance_export

from report import report_sxw

class finance_archive(finance_export.finance_archive):
    def postprocess_reconciliable(self, cr, uid, data, model, column_deletion=False):
        """
        ##### WARNING #####
        ### IN CASE CHANGES ARE MADE TO THIS METHOD, keep in mind that this is used for OCP export as well. ###
        Replace 15th column by its reconcile name.
        Note: as we begin to 0, the python column is 14.
        """
        # Checks
        if not data:
            return []
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        new_data = []
        reconcile_obj = pool.get('account.move.reconcile')
        for line in data:
            tmp_line = list(line)
            reconcile_id = line[14]
            if reconcile_id:
                reconcile = reconcile_obj.read(cr, uid, reconcile_id, ['name'])
                if reconcile and reconcile.get('name', False):
                    tmp_line[14] = reconcile.get('name')
            # Add DB ID on each line (first column)
            line_ids = str(line[0])
            tmp_line[0] = self.get_hash(cr, uid, line_ids, model)
            new_data.append(self.line_to_utf8(tmp_line))
        return new_data

class hq_report_ocb_matching(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        """
        Create a kind of report and return its content.
        The content is composed of:
         - reconciliable lines
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        excluded_journal_types = ['hq', 'migration']
        # Fetch data from wizard
        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))
        form = data.get('form')
        instance_ids = form.get('instance_ids', False)
        if not instance_ids:
            raise osv.except_osv(_('Warning'), _('Some info are missing: instance.'))
        instance_id = form.get('instance_id', False)
        if not instance_id:
            raise osv.except_osv(_('Warning'), _('Missing info: instance.'))

        # Prepare SQL requests and PROCESS requests for finance_archive object (CF. account_tools/finance_export.py)
        sqlrequests = {
            # Do not take lines that come from a HQ or MIGRATION journal
            'reconciliable': """
                SELECT aml.id, m.name AS "entry_sequence", aml.name, aml.ref, aml.document_date, aml.date, a.code, aml.partner_txt, debit_currency, credit_currency, c.name AS "Booking Currency", ROUND(aml.debit, 2), ROUND(aml.credit, 2), cc.name AS "functional_currency", aml.reconcile_id
                FROM account_move_line AS aml, account_move AS m, account_account AS a, res_currency AS c, res_company AS e, res_currency AS cc, account_journal AS j, account_period AS p
                WHERE aml.move_id = m.id
                AND aml.account_id = a.id
                AND aml.currency_id = c.id
                AND aml.company_id = e.id
                AND e.currency_id = cc.id
                AND aml.journal_id = j.id
                AND p.id = aml.period_id
                AND a.reconcile = 't'
                AND j.type not in %s
                AND p.number not in (0, 16)
                AND aml.instance_id in %s;
                """,
        }

        # Create part of filename (search 3 first code digits)
        processrequests = [
            {
                'headers': ['DB ID', 'Entry Sequence', 'Description', 'Reference', 'Document Date', 'Posting Date', 'G/L Account', 'Third Party', 'Booking Debit', 'Booking Credit', 'Booking Currency', 'Functional Debit', 'Functional Credit', 'Functional Currency', 'Reconcile reference'],
                'filename': "Check on reconcilable entries.csv",
                'key': 'reconciliable',
                'query_params': (tuple(excluded_journal_types), tuple(instance_ids),),
                'function': 'postprocess_reconciliable',
                'fnct_params': 'account.move.line',
            },
        ]
        # Launch finance archive object
        fe = finance_archive(sqlrequests, processrequests, context=context)
        # Use archive method to create the archive
        return fe.archive(cr, uid)

hq_report_ocb_matching('report.hq.ocb.matching', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
