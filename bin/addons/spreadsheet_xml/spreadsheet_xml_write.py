# -*- coding: utf-8 -*-

from tools.translate import _
from tools.misc import file_open
from tools.misc import Path
from osv import osv
from report_webkit.webkit_report import WebKitParser
from .report import report_sxw
import os
import netsvc
import pooler
from mako.template import Template
from mako import exceptions
from mako.runtime import Context

from mako import filters
import addons
import zipfile
import tempfile
import codecs
import re
import logging
# new mako filter |xn to escape html entities + replace \n by &#10;
xml_escapes = {
    '&' : '&amp;',
    '>' : '&gt;',
    '<' : '&lt;',
    '"' : '&#34;',   # also &quot; in html-only
    "'" : '&#39;',    # also &apos; in html-only
    "\n": '&#10;'
}
def xml_escape_br(string):
    return re.sub(r"([&<\"'>\n])", lambda m: xml_escapes[m.group()], string)
filters.xml_escape_br = xml_escape_br
filters.DEFAULT_ESCAPES['xn'] = 'filters.xml_escape_br'


class SpreadsheetReport(WebKitParser):
    _fields_process = {
        'date': report_sxw._date_format,
        'datetime': report_sxw._dttime_format
    }
    log_export = False

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        if not rml:
            rml = 'addons/spreadsheet_xml/report/spreadsheet_xls.mako'
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        if context is None:
            context = {}
        if report_xml.report_type != 'webkit':
            return super(WebKitParser,self).create_single_pdf(cr, uid, ids, data, report_xml, context=context)

        self.report_xml = report_xml
        parser_instance = self.parser(cr, uid, self.name2, context=context)
        self.pool = pooler.get_pool(cr.dbname)

        if not context.get('splitbrowse'):
            objs = self.getObjects(cr, uid, ids, context)
        else:
            objs = []
            parser_instance.localcontext['ids'] = ids
            parser_instance.localcontext['context'] = context
        parser_instance.set_context(objs, data, ids, report_xml.report_type)
        orig_file = self.report_xml.report_file or self.tmpl
        parser_instance.orig_file = orig_file and "addons/%s"%orig_file or self.name
        template = False
        if report_xml.report_file:
            path = addons.get_module_resource(report_xml.report_file)
            if path and os.path.exists(path):
                template = file(path).read()

        if self.tmpl:
            f = file_open(self.tmpl)
            template = f.read()
            f.close()

        if not template:
            raise osv.except_osv(_('Error!'), _('Webkit Report template not found !'))

        self.localcontext.update({'lang': context.get('lang')})
        parser_instance.localcontext.update({'setLang':self.setLang})
        parser_instance.localcontext.update({'formatLang':parser_instance.format_xls_lang})

        null, tmpname = tempfile.mkstemp()
        fileout = codecs.open(tmpname, 'wb', 'utf8')
        body_mako_tpl = Template(template, input_encoding='utf-8', default_filters=['unicode'])
        try:
            mako_ctx = Context(fileout, _=parser_instance.translate_call, **parser_instance.localcontext)
            body_mako_tpl.render_context(mako_ctx)
            fileout.close()
        except Exception:
            msg = exceptions.text_error_template().render()
            netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
            raise osv.except_osv(_('Webkit render'), msg)

        if context.get('zipit'):
            null1, tmpzipname = tempfile.mkstemp()
            zf = zipfile.ZipFile(tmpzipname, 'w')
            zf.write(tmpname, 'export_result.xls', zipfile.ZIP_DEFLATED)
            zf.close()
            out = file(tmpzipname, 'rb').read()
            os.close(null1)
            os.close(null)
            os.unlink(tmpzipname)
            os.unlink(tmpname)
            return (out, 'zip')

        if context.get('pathit'):
            os.close(null)
            return (Path(tmpname, delete=True), 'xls')

        out = file(tmpname, 'rb').read()
        os.close(null)
        os.unlink(tmpname)
        return (out, 'xls')

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        return table_obj.browse(cr, uid, ids, list_class=report_sxw.browse_record_list, context=context, fields_process=self._fields_process)

    def create(self, cr, uid, ids, data, context=None):
        if self.log_export:
            logger = logging.getLogger('XLS export')
            logger.info('Exporting %d %s ...' % (len(ids), self.table))
        try:
            return super(SpreadsheetReport, self).create(cr, uid, ids, data, context)
        finally:
            if self.log_export:
                logger.info('End of Export %s' % (self.table,))
class SpreadsheetCreator(object):
    def __init__(self, title, headers, datas):
        self.headers = headers
        self.datas = datas
        self.title = title


    def get_xml(self, default_filters=None):
        if default_filters is None:
            default_filters = []

        f, filename = file_open('addons/spreadsheet_xml/report/spreadsheet_writer_xls.mako', pathinfo=True)
        f[0].close()
        tmpl = Template(filename=filename, input_encoding='utf-8', output_encoding='utf-8', default_filters=default_filters)
        return tmpl.render(objects=self.datas, headers=self.headers, title=self.title)
