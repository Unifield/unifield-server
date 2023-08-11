# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2010 Camptocamp SA (http://www.camptocamp.com)
# All Right Reserved
#
# Author : Nicolas Bessi (Camptocamp)
# Contributor(s) : Florent Xicluna (Wingo SA)
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import subprocess
import os
import tempfile
import time
from mako.template import Template
from mako import exceptions
import netsvc
import pooler
import logging
from .report_helper import WebKitHelper
from report.report_sxw import report_sxw, report_rml, _int_format, \
    _float_format, _date_format, _dttime_format, browse_record_list, \
    rml_parse
from lxml import etree
from lxml.etree import XMLSyntaxError
import addons
from tools.translate import _
from osv.osv import except_osv


def mako_template(text):
    """Build a Mako template.

    This template uses UTF-8 encoding
    """
    # default_filters=['unicode', 'h'] can be used to set global filters
    return Template(text, input_encoding='utf-8', output_encoding='utf-8', default_filters=['decode.utf8'])

class _int_noformat(_int_format):
    def __str__(self):
        return str(self.val)


class _float_noformat(_float_format):
    def __str__(self):
        return str(self.val)


_fields_process = {
    'integer': _int_noformat,
    'float': _float_noformat,
    'date': _date_format,
    'datetime': _dttime_format
}


class WebKitParser(report_sxw):
    """Custom class that use webkit to render HTML reports
       Code partially taken from report openoffice. Thanks guys :)
    """

    def __init__(self, name, table, rml=False, parser=False,
                 header=True, store=False):
        self.localcontext={}
        report_sxw.__init__(self, name, table, rml, parser,
                            header, store)

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        return table_obj.browse(cr, uid, ids, list_class=browse_record_list, context=context, fields_process=_fields_process)

    def get_lib(self, cursor, uid, company) :
        """Return the lib wkhtml path"""
        #TODO Detect lib in system first
        path = self.pool.get('res.company').read(cursor, uid, company, ['lib_path',])
        path = path['lib_path']
        if not path:
            raise except_osv(
                _('Wkhtmltopdf library path is not set in company'),
                _('Please install executable on your system'+
                  ' (sudo apt-get install wkhtmltopdf) or download it from here:'+
                  ' http://code.google.com/p/wkhtmltopdf/downloads/list and set the'+
                  ' path to the executable on the Company form.'+
                  'Minimal version is 0.9.9')
            )
        if os.path.isabs(path) :
            if (os.path.exists(path) and os.access(path, os.X_OK)\
                    and os.path.basename(path).startswith('wkhtmltopdf')):
                return path
            else:
                raise except_osv(
                    _('Wrong Wkhtmltopdf path set in company'+
                      'Given path is not executable or path is wrong'),
                    'for path %s'%(path)
                )
        else :
            raise except_osv(
                _('path to Wkhtmltopdf is not absolute'),
                'for path %s'%(path)
            )
    def generate_pdf(self, comm_path, report_xml, header, footer, html_list, webkit_header=False):
        """Call webkit in order to generate pdf"""
        if not webkit_header:
            webkit_header = report_xml.webkit_header
        tmp_dir = tempfile.gettempdir()
        out = report_xml.name+str(time.time())+'.pdf'
        out = os.path.join(tmp_dir, out.replace(' ',''))
        file_to_del = []
        if comm_path:
            command = [comm_path]
        else:
            command = ['wkhtmltopdf']

        command.append('--quiet')
        # default to UTF-8 encoding.  Use <meta charset="latin-1"> to override.
        command.extend(['--encoding', 'utf-8'])
        if header :
            head_file = open( os.path.join(
                tmp_dir,
                str(time.time()) + '.head.html'
            ),
                'w'
            )
            head_file.write(header)
            head_file.close()
            file_to_del.append(head_file.name)
            command.extend(['--header-html', head_file.name])
        if footer :
            foot_file = open(  os.path.join(
                tmp_dir,
                str(time.time()) + '.foot.html'
            ),
                'w'
            )
            foot_file.write(footer)
            foot_file.close()
            file_to_del.append(foot_file.name)
            command.extend(['--footer-html', foot_file.name])

        if webkit_header.margin_top :
            command.extend(['--margin-top', str(webkit_header.margin_top).replace(',', '.')])
        if webkit_header.margin_bottom :
            command.extend(['--margin-bottom', str(webkit_header.margin_bottom).replace(',', '.')])
        if webkit_header.margin_left :
            command.extend(['--margin-left', str(webkit_header.margin_left).replace(',', '.')])
        if webkit_header.margin_right :
            command.extend(['--margin-right', str(webkit_header.margin_right).replace(',', '.')])
        if webkit_header.orientation :
            command.extend(['--orientation', str(webkit_header.orientation).replace(',', '.')])
        if webkit_header.format :
            command.extend(['--page-size', str(webkit_header.format).replace(',', '.')])
        count = 0
        for html in html_list :
            html_file = open(os.path.join(tmp_dir, str(time.time()) + str(count) +'.body.html'), 'w')
            count += 1
            html_file.write(html)
            html_file.close()
            file_to_del.append(html_file.name)
            command.append(html_file.name)
        command.append(out)
        try:
            status = subprocess.call(command, stderr=subprocess.PIPE) # ignore stderr
            if status :
                raise except_osv(
                    _('Webkit raise an error' ),
                    status
                )
        except Exception:
            for f_to_del in file_to_del :
                os.unlink(f_to_del)

        pdf = open(out, 'rb').read()
        for f_to_del in file_to_del :
            os.unlink(f_to_del)

        os.unlink(out)
        return pdf


    def setLang(self, lang):
        if not lang:
            lang = 'en_US'
        self.localcontext['lang'] = lang


    # override needed to keep the attachments' storing procedure
    def create_single_pdf(self, cursor, uid, ids, data, report_xml, context=None):
        """generate the PDF"""

        if context is None:
            context={}

        if report_xml.report_type != 'webkit':
            return super(WebKitParser,self).create_single_pdf(cursor, uid, ids, data, report_xml, context=context)

        self.report_xml = report_xml
        parser_instance = self.parser(
            cursor,
            uid,
            self.name2,
            context=context
        )
        orig_file = self.report_xml.report_file or self.tmpl
        parser_instance.orig_file = orig_file and "addons/%s"%orig_file or self.name

        self.pool = pooler.get_pool(cursor.dbname)
        objs = self.getObjects(cursor, uid, ids, context)
        parser_instance.set_context(objs, data, ids, report_xml.report_type)

        template =  False
        if report_xml.report_file :
            path = addons.get_module_resource(report_xml.report_file)
            if path and os.path.exists(path) :
                template = open(path).read()
        if not template and report_xml.report_webkit_data :
            template =  report_xml.report_webkit_data
        if not template :
            raise except_osv(_('Error!'), _('Webkit Report template not found !'))
        header = report_xml.webkit_header.html
        footer = report_xml.webkit_header.footer_html
        if not header and report_xml.header:
            raise except_osv(
                _('No header defined for this Webkit report!'),
                _('Please set a header in company settings')
            )
        if not report_xml.header :
            #I know it could be cleaner ...
            header = """
<html>
    <head>
        <meta content="text/html; charset=UTF-8" http-equiv="content-type"/>
        <style type="text/css"> 
            ${css}
        </style>
        <script>
        function subst() {
           var vars={};
           var x=document.location.search.substring(1).split('&');
           for(var i in x) {var z=x[i].split('=',2);vars[z[0]] = unescape(z[1]);}
           var x=['frompage','topage','page','webpage','section','subsection','subsubsection'];
           for(var i in x) {
             var y = document.getElementsByClassName(x[i]);
             for(var j=0; j<y.length; ++j) y[j].textContent = vars[x[i]];
           }
         }
        </script>
    </head>
<body style="border:0; margin: 0;" onload="subst()">
</body>
</html>"""
        css = report_xml.webkit_header.css
        if not css :
            css = ''
        user = self.pool.get('res.users').browse(cursor, uid, uid)
        company= user.company_id

        #default_filters=['unicode', 'entity'] can be used to set global filter
        body_mako_tpl = mako_template(template)
        helper = WebKitHelper(cursor, uid, report_xml.id, context)
        self.localcontext.update({'lang': context.get('lang')})
        parser_instance.localcontext.update({'setLang':self.setLang})
        parser_instance.localcontext.update({'formatLang':parser_instance.format_xls_lang})
        try :
            html = body_mako_tpl.render_unicode(     helper=helper,
                                                     css=css,
                                                     _=parser_instance.translate_call,
                                                     **parser_instance.localcontext
                                                     )
        except Exception:
            msg = exceptions.text_error_template().render()
            netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
            raise except_osv(_('Webkit render'), msg)
        head_mako_tpl = mako_template(header)
        try :
            head = head_mako_tpl.render(
                company=company,
                time=time,
                helper=helper,
                css=css,
                formatLang=parser_instance.format_xls_lang,
                setLang=self.setLang,
                _=parser_instance.translate_call,
                _debug=False
            )
        except Exception:
            raise except_osv(_('Webkit render'),
                             exceptions.text_error_template().render())
        foot = False
        if footer :
            foot_mako_tpl = mako_template(footer)
            try :
                foot = foot_mako_tpl.render(
                    company=company,
                    time=time,
                    helper=helper,
                    css=css,
                    formatLang=parser_instance.format_xls_lang,
                    setLang=self.setLang,
                    _=parser_instance.translate_call,
                )
            except:
                msg = exceptions.text_error_template().render()
                netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
                raise except_osv(_('Webkit render'), msg)
        if report_xml.webkit_debug :
            try :
                deb = head_mako_tpl.render(
                    company=company,
                    time=time,
                    helper=helper,
                    css=css,
                    _debug=html,
                    formatLang=parser_instance.format_xls_lang,
                    setLang=self.setLang,
                    _=parser_instance.translate_call,
                )
            except Exception:
                msg = exceptions.text_error_template().render()
                netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
                raise except_osv(_('Webkit render'), msg)
            return (deb, 'html')
        bin = self.get_lib(cursor, uid, company.id)
        pdf = self.generate_pdf(bin, report_xml, head, foot, [html])
        return (pdf, 'pdf')


    def create(self, cursor, uid, ids, data, context=None):
        """We override the create function in order to handle generator
           Code taken from report openoffice. Thanks guys :) """
        pool = pooler.get_pool(cursor.dbname)
        ir_obj = pool.get('ir.actions.report.xml')
        report_xml_ids = ir_obj.search(cursor, uid,
                                       [('report_name', '=', self.name[7:])], context=context)
        if report_xml_ids:
            report_xml = ir_obj.browse(
                cursor,
                uid,
                report_xml_ids[0],
                context=context
            )
            report_xml.report_rml = None
            report_xml.report_rml_content = None
            report_xml.report_sxw_content_data = None
            report_rml.report_sxw_content = None
            report_rml.report_sxw = None
        else:
            return super(WebKitParser, self).create(cursor, uid, ids, data, context)
        if report_xml.report_type != 'webkit' :
            return super(WebKitParser, self).create(cursor, uid, ids, data, context)
        result = self.create_source_pdf(cursor, uid, ids, data, report_xml, context)
        if not result:
            return (False,False)
        if result and isinstance(result[0], (str, bytes)) and\
                result[0][0:5] in (b'<?xml', '<?xml'):
            new_result = self.check_malformed_xml_spreadsheet(xml_string=result[0],
                                                              report_name=report_xml.report_name)
            if new_result:
                # change the first element of the tuple
                result = list(result)
                result[0] = new_result
                result = tuple(result)

        return result

    def sanitizeWorksheetName(self, name):
        '''
        according to microsoft documentation :
        https://msdn.microsoft.com/en-us/library/office/aa140066(v=office.10).aspx#odc_xmlss_ss:worksheet
        The following caracters are not allowed : /, \, ?, *, [, ]
        It also seems that microsoft excel do not accept Worksheet name longer
        than 31 characters.
        '''
        if not name:
            return _('Sheet 1')
        replacement_char = '-'
        not_allowed_char_list = ['/', '\\', '?', '*', '[', ']']
        new_name = name
        if set(new_name).intersection(not_allowed_char_list):
            for char in not_allowed_char_list:
                if char in new_name:
                    new_name = new_name.replace(char, replacement_char)

        return new_name[:31]

    def check_malformed_xml_spreadsheet(self, xml_string, report_name):
        '''Check that the xml spreadsheet doesn't contain
        node <Date ss:Type="DateTime"> with 'False' in the values
        log an error if that is the case an remove the corresponding node.
        '''
        logger = logging.getLogger('mako_spreadsheet')
        try:
            file_dom = etree.fromstring(xml_string)
        except XMLSyntaxError as e:
            # US-2540: in case of xml syntax error, log the error and return
            # the malformed XML
            error_message = 'Error in report %s: %s' % (report_name, e)
            logger.error(error_message)
            return xml_string

        try:
            namespaces = {
                'o': 'urn:schemas-microsoft-com:office:office',
                'x': 'urn:schemas-microsoft-com:office:excel',
                'ss': 'urn:schemas-microsoft-com:office:spreadsheet',
                'html': 'http://www.w3.org/TR/REC-html40'
            }

            spreadsheet_elements = file_dom.xpath('//ss:Worksheet',
                                                  namespaces=namespaces)

            # Check spreadcheet names
            xml_modified = False
            sheet_name_dict = {}
            count = 0
            for sheet in spreadsheet_elements:
                sheet_name = sheet.get('{%(ss)s}Name' % namespaces, _('Sheet 1'))
                new_name = self.sanitizeWorksheetName(sheet_name)
                if new_name != sheet_name:
                    # if the sheet name already exists, modify it to add
                    # a counter to the name
                    if new_name in sheet_name_dict:
                        sheet_name_dict[new_name] += 1
                        count = sheet_name_dict[new_name]
                        new_name = '%s_%s' % (new_name[:28], count)
                    else:
                        sheet_name_dict[new_name] = 1
                    sheet.attrib['{urn:schemas-microsoft-com:office:spreadsheet}Name'] = new_name
                    xml_modified = True
                else:
                    if new_name not in sheet_name_dict:
                        sheet_name_dict[new_name] = 1

            # Check date cells
            data_time_elements = file_dom.xpath('//ss:Data[@ss:Type="DateTime"]',
                                                namespaces=namespaces)
            element_to_remove = []
            for element in data_time_elements:
                if 'False' in element.text:
                    error_message = 'Line %s of document %s is corrupted, ' \
                        'DateTime cannot contain \'False\': %s' % \
                        (element.sourceline, report_name, element.text)
                    logger.error(error_message)
                    element_to_remove.append(element)
            for element in element_to_remove:
                # if a malformed node exists, replace it with an empty String cell
                element.attrib['{urn:schemas-microsoft-com:office:spreadsheet}Type'] = 'String'
                element.text = ''
                xml_modified = True

            # Check Number cells
            number_cells = file_dom.xpath('//ss:Data[@ss:Type="Number"]',
                                          namespaces=namespaces)
            for cell in number_cells:
                # if space in the in Numbers, remove them
                forbidden_chars = [' ', '\xc2\xa0', '\xa0']
                for char in forbidden_chars:
                    if isinstance(cell.text, str) and char in cell.text:
                        error_message = 'Line %s of document %s is corrupted, a '\
                            'Number cannot contain characters or spaces: %r' % \
                            (cell.sourceline, report_name, cell.text)
                        logger.warning(error_message)
                        cell.text = cell.text.replace(char, '')
                        xml_modified = True

                # check the number is really a number, if not, set it to zero
                try:
                    if cell.text:
                        float(cell.text)
                except (ValueError, TypeError):
                    error_message = 'Line %s of document %s is corrupted, a '\
                        'Number cell contain other things than number: %r. '\
                        'It has been replaced by 0.0.' % \
                        (cell.sourceline, report_name, cell.text)
                    logger.warning(error_message)
                    cell.text = '0.0'
                    xml_modified = True

            if xml_modified:
                # return modified xml
                return etree.tostring(file_dom, xml_declaration=True, encoding="utf-8")
        except Exception as e:
            # US-2540: in case of xml syntax error, log the error and return
            # the malformed XML
            logger.error('Error check_malformed_xml_spreadsheet: %s' % e)

        return xml_string


class XlsWebKitParser(WebKitParser):
    def __init__(self, name, table, rml=False, parser=rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(XlsWebKitParser, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        a = super(XlsWebKitParser, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
