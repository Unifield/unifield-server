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
from osv import osv
import time
import pooler
import csv
from tempfile import TemporaryFile
from report_webkit.webkit_report import WebKitParser


def getIds(self, cr, uid, ids, context):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids

def getObjects(self, cr, uid, ids, context):
    ids = getIds(self, cr, uid, ids, context)
    return super(self.__class__, self).getObjects(cr, uid, ids, context)

def create_csv(self, cr, uid, ids, data, context=None):
    if not context:
        context = {}
    ids = getIds(self, cr, uid, ids, context)
    pool = pooler.get_pool(cr.dbname)
    obj = pool.get('account.line.csv.export')
    outfile = TemporaryFile('w+')
    writer = csv.writer(outfile, quotechar='"', delimiter=',')

    if self.table == 'account.analytic.line':
        obj._account_analytic_line_to_csv(cr, uid, ids, writer, context.get('output_currency_id'), context={})
    else:
        obj._account_move_line_to_csv(cr, uid, ids, writer, context.get('output_currency_id'), context={})

    outfile.seek(0)
    out = outfile.read()
    outfile.close()
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
        return create_csv(self, cr, uid, ids, data, context)

account_move_line_report_csv('report.account.move.line_csv','account.move.line','addons/account_mcdb/report/report_account_move_line.rml')

class account_move_line_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(account_move_line_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(account_move_line_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

account_move_line_report_xls('report.account.move.line_xls','account.move.line','addons/account_mcdb/report/report_account_move_line_xls.mako')


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
        return create_csv(self, cr, uid, ids, data, context)

account_analytic_line_report_csv('report.account.analytic.line_csv','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line.rml')


class account_analytic_line_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(account_analytic_line_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(account_analytic_line_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

account_analytic_line_report_xls('report.account.analytic.line_xls','account.analytic.line','addons/account_mcdb/report/report_account_analytic_line_xls.mako')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
