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
from report_webkit.webkit_report import WebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import zipfile
import tempfile
import os

limit_tozip = 15000

def getIds(self, cr, uid, ids, limit=5000, context=None):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context and not context.get('export_selected'):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=limit)
    return ids

def context_out(cr, uid, context):
    pool =  pooler.get_pool(cr.dbname)
    if context is None:
        return {}
    if not context.get('output_currency_id'):
        return context
    cmp_curr_id = pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
    if context['output_currency_id'] == cmp_curr_id:
        del context['output_currency_id']
    return context

def getObjects(self, cr, uid, ids, context):
    ids = getIds(self, cr, uid, ids, context)
    return super(self.__class__, self).getObjects(cr, uid, ids, context)

def getIterObjects(self, cr, uid, ids, context):
    ids = getIds(self, cr, uid, ids, limit=65000, context=context)
    len_ids = len(ids)
    l = 0
    steps = 1000
    pool =  pooler.get_pool(cr.dbname)
    table_obj = pool.get(self.table)
    context = context_out(cr, uid, context)
    field_process = None
    if hasattr(self, '_fields_process'):
        field_process = self._fields_process
    while l < len_ids:
        old_l = l
        l = l + steps
        new_ids = ids[old_l:l]
        if new_ids:
            for o in table_obj.browse(cr, uid, new_ids, list_class=report_sxw.browse_record_list, context=context, fields_process=field_process):
                yield o
    raise StopIteration

def create_csv(self, cr, uid, ids, data, context=None):
    context = context_out(cr, uid, context)
    ids = getIds(self, cr, uid, ids, limit=65000, context=context)
    pool = pooler.get_pool(cr.dbname)
    obj = pool.get('account.line.csv.export')
    outfile = tempfile.TemporaryFile('w+')
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
        null, tmpzipname = tempfile.mkstemp()
        zf = zipfile.ZipFile(tmpzipname, 'w')
        zf.writestr('export_result.csv', out)
        zf.close()
        out = file(tmpzipname, 'rb').read()
        os.unlink(tmpzipname)
        os.unlink(tmpname)
        return (out, 'zip')

    return (out, 'csv')


class account_move_line_report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
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

    def getObjects(self, cr, uid, ids, context):
        return getIterObjects(self, cr, uid, ids, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, limit=65000, context=context)
        if context is None:
            context = {}
        if len(ids) > limit_tozip:
            context['zipit'] = True
        return super(account_move_line_report_xls, self).create(cr, uid, ids, data, context=context)

class parser_account_move_line(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_account_move_line, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'reconcile_name': self.reconcile_name,
            #'getSub': self.getSub,
        })

#    def getSub(self):
#        len_ids = len(self.localcontext.get('ids'))
#        obj = self.pool.get('account.move.line')
#        ctx = {}
#        l = 0
#        steps = 1000
#        output_cur = self.localcontext.get('data',{}).get('context', {}).get('output_currency_id')
#        if output_cur and output_cur != self.localcontext.get('company').currency_id.id:
#            ctx['output_currency_id'] = output_cur
#        else:
#            output_cur = False
#        while l < len_ids:
#            old_l = l
#            l = l+steps
#            yield obj.browse(self.cr, self.uid, self.localcontext.get('ids')[old_l:l], context={'output_currency_id': output_cur})
#        yield []

    def reconcile_name(self, r_id=None, context=None):
        if not r_id:
            return None
        res = self.pool.get('account.move.reconcile').name_get(self.cr, self.uid, [r_id])
        if res and res[0] and res[0][1]:
            return res[0][1]
        return None

account_move_line_report_xls('report.account.move.line_xls','account.move.line','addons/account_mcdb/report/report_account_move_line_xls.mako', parser=parser_account_move_line)


class account_analytic_line_report(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
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

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, limit=65000, context=context)
        if context is None:
            context = {}
        if len(ids) > limit_tozip:
            context['zipit'] = True
        return super(account_analytic_line_report_xls, self).create(cr, uid, ids, data, context)

account_analytic_line_report_xls('report.account.analytic.line_xls','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line_xls.mako')

class account_analytic_line_free_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_analytic_line_free_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def getObjects(self, cr, uid, ids, context):
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

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
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
