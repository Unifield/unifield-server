#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

from report import report_sxw
import pooler
import csv
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import zipfile
import tempfile
import os
import logging

limit_tozip = 15000


def getIds(self, cr, uid, ids, limit=5000, context=None):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context and not context.get('export_selected'):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        domain = context.get('search_domain')
        if table_obj._name == 'account.move.line':
            # US-1290: JI export search result always exclude IB entries
            domain = [('period_id.number', '>', 0)] + domain
        ids = table_obj.search(cr, uid, domain, limit=limit)
    return ids

def getObjects(self, cr, uid, ids, context):
    ids = getIds(self, cr, uid, ids, context)
    return super(self.__class__, self).getObjects(cr, uid, ids, context)

def getIterObjects(self, cr, uid, ids, context):
    if context is None:
        context = {}
    ids = getIds(self, cr, uid, ids, limit=0, context=context)
    len_ids = len(ids)
    l = 0
    steps = 1000
    pool =  pooler.get_pool(cr.dbname)
    table_obj = pool.get(self.table)
    field_process = None
    back_browse = False
    if context.get('background_id'):
        back_browse = self.pool.get('memory.background.report').browse(cr, uid, context['background_id'])

    if hasattr(self, '_fields_process'):
        field_process = self._fields_process
    # we need to sort analytic line by account code
    if context.get('sort_by_account_code') and len_ids > 1:
        cr.execute('select an.id from account_analytic_line an left join account_analytic_account a on an.account_id = a.id where an.id in %s order by a.code', (tuple(ids), ))
        ids = []
        for i in cr.fetchall():
            ids.append(i[0])

    while l < len_ids:
        if back_browse:
            back_browse.update_percent(l/float(len_ids))
        old_l = l
        l = l + steps
        new_ids = ids[old_l:l]
        if new_ids:
            for o in table_obj.browse(cr, uid, new_ids, list_class=report_sxw.browse_record_list, context=context, fields_process=field_process):
                yield o
    return

def create_csv(self, cr, uid, ids, data, context=None):
    try:
        if context is None:
            context = {}
        ids = getIds(self, cr, uid, ids, limit=0, context=context)
        logging.getLogger('Finance export').info('CSV Exporting %d %s ...' % (len(ids), self.table))
        pool = pooler.get_pool(cr.dbname)
        obj = pool.get('account.line.csv.export')
        outfile = tempfile.TemporaryFile('w+', newline='')
        writer = csv.writer(outfile, quotechar='"', delimiter=',')

        if self.table == 'account.analytic.line':
            obj._account_analytic_line_to_csv(cr, uid, ids, writer, context.get('output_currency_id'), context)
        elif self.table == 'account.bank.statement.line':
            obj._account_bank_statement_line_to_csv(cr, uid, ids, writer, context.get('output_currency_id'), context)
        else:
            obj._account_move_line_to_csv(cr, uid, ids, writer, context.get('output_currency_id'), context)

        outfile.seek(0)
        out = outfile.read()
        outfile.close()
        if len(ids) > limit_tozip:
            fd, tmpzipname = tempfile.mkstemp()
            zf = zipfile.ZipFile(tmpzipname, 'w')
            zf.writestr('export_result.csv', out)
            zf.close()
            out = open(tmpzipname, 'rb').read()
            os.close(fd)
            os.unlink(tmpzipname)
            return (out, 'zip')

        return (out, 'csv')
    finally:
        logging.getLogger('Finance export').info('CSV End of Export %s' % (self.table,))


class account_move_line_report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if context is None:
            context = {}
        return super(account_move_line_report, self).create(cr, uid, ids, data, context=context)

    def getObjects(self, cr, uid, ids, context):
        return getObjects(self, cr, uid, ids, context)

account_move_line_report('report.account.move.line','account.move.line','addons/account_mcdb/report/report_account_move_line.rml')


class account_move_line_report_csv(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        if 'output_currency_id' in data:
            context.update({'output_currency_id': data.get('output_currency_id')})
        return create_csv(self, cr, uid, ids, data, context)

account_move_line_report_csv('report.account.move.line_csv','account.move.line','addons/account_mcdb/report/report_account_move_line.rml')

class account_move_line_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_move_line_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)
        self.log_export = True

    def getObjects(self, cr, uid, ids, context):
        return getIterObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, limit=0, context=context)
        if context is None:
            context = {}
        if len(ids) > limit_tozip:
            context['zipit'] = True
        return super(account_move_line_report_xls, self).create(cr, uid, ids, data, context=context)

class parser_account_move_line(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_account_move_line, self).__init__(cr, uid, name, context=context)
        self._display_hq_account = self.pool.get('account.export.mapping')._is_mapping_display_active(cr, uid)
        self.localcontext.update({
            'display_hq_account': lambda *a: self._display_hq_account,

        })

    def getObjects(self, cr, uid, ids, context):
        return getIterObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if context is None:
            context = {}
        return super(parser_account_move_line, self).create(cr, uid, ids, data, context=context)

account_move_line_report_xls('report.account.move.line_xls','account.move.line','addons/account_mcdb/report/report_account_move_line_xls.mako', parser=parser_account_move_line)


class account_analytic_line_report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if context is None:
            context = {}
        return super(account_analytic_line_report, self).create(cr, uid, ids, data, context=context)

    def getObjects(self, cr, uid, ids, context):
        return getObjects(self, cr, uid, ids, context)

account_analytic_line_report('report.account.analytic.line','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line.rml')


class account_analytic_line_report_csv(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        if 'output_currency_id' in data:
            context.update({'output_currency_id': data.get('output_currency_id')})
        return create_csv(self, cr, uid, ids, data, context)

account_analytic_line_report_csv('report.account.analytic.line_csv','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line.rml')


class account_analytic_line_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_analytic_line_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)
        self.log_export = True

    def getObjects(self, cr, uid, ids, context):
        return getIterObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, limit=0, context=context)
        if context is None:
            context = {}
        if len(ids) > limit_tozip:
            context['zipit'] = True
        return super(account_analytic_line_report_xls, self).create(cr, uid, ids, data, context)

class parser_account_analytic_line_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_account_analytic_line_report, self).__init__(cr, uid, name, context=context)
        self._display_hq_account = self.pool.get('account.export.mapping')._is_mapping_display_active(cr, uid)
        self.localcontext.update({
            'display_hq_account': lambda *a: self._display_hq_account,
        })

account_analytic_line_report_xls('report.account.analytic.line_xls','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line_xls.mako', parser=parser_account_analytic_line_report)

class account_analytic_line_free_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_analytic_line_free_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)
        self.log_export = True

    def getObjects(self, cr, uid, ids, context):
        if context is None:
            context = {}
        context['sort_by_account_code'] = 1
        return getIterObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        if context is None:
            context = {}
        if len(ids) > limit_tozip:
            context['zipit'] = True
        return super(account_analytic_line_free_report_xls, self).create(cr, uid, ids, data, context)

account_analytic_line_free_report_xls('report.account.analytic.line.free_xls','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line_free_xls.mako')

class account_bank_statement_line_report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def getObjects(self, cr, uid, ids, context):
        return getObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if context is None:
            context = {}
        return super(account_bank_statement_line_report, self).create(cr, uid, ids, data, context=context)

account_bank_statement_line_report('report.account.bank.statement.line','account.bank.statement.line','addons/account_mcdb/report/report_account_bank_statement_line.rml')


class account_bank_statement_line_report_csv(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        if 'output_currency_id' in data:
            context.update({'output_currency_id': data.get('output_currency_id')})
        return create_csv(self, cr, uid, ids, data, context)

account_bank_statement_line_report_csv('report.account.bank.statement.line_csv','account.bank.statement.line','addons/account_mcdb/report/report_account_bank_statement_line.rml')


class account_bank_statement_line_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_bank_statement_line_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)
        self.log_export = True

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if 'output_currency_id' in data:
            context.update({'output_currency_id': data.get('output_currency_id')})
        else:
            pool = pooler.get_pool(cr.dbname)
            company_currency = pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            context.update({'output_currency_id': company_currency})
        a = super(account_bank_statement_line_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

account_bank_statement_line_report_xls('report.account.bank.statement.line_xls','account.bank.statement.line','addons/account_mcdb/report/report_account_bank_statement_line_xls.mako')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
