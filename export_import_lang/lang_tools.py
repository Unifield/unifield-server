# -*- coding: utf-8 -*-

from tools.translate import _
from osv import fields,osv
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from tempfile import TemporaryFile
import zipfile
import base64
import cStringIO

def open_requests(self, cr, uid, ids, filter=False, context=None):
    view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'export_import_lang', 'res_request_trans-act')
    result = self.pool.get(view[0]).read(cr, uid, view[1], ['view_id', 'view_mode', 'view_type', 'res_model', 'type', 'search_view_id', 'domain'])
    result['target'] = 'crunch'
    #result['context'] = {'search_default_import': filter=='import' , 'search_default_export': filter=='export', 'search_default_act_to': uid}
    return result

def get_data_file(cr, uid, data):
    filedata = base64.decodestring(data)
    buf = cStringIO.StringIO(filedata)

    try:
        zipf = zipfile.ZipFile(buf, 'r')
        file_name = zipf.namelist()
        if not file_name or len(file_name) > 1:
            raise osv.except_osv(_('Error'), _('The Zip file should contain only one file'))
        filedata = zipf.read(file_name[0])
        zipf.close()
    except zipfile.BadZipfile:
        pass
    buf.close()

    try:
        s_xml = SpreadsheetXML(xmlstring=filedata)
    except osv.except_osv:
        fileobj = TemporaryFile('w+b')
        fileobj.write(filedata)
        fileformat = 'csv'
    else:
        fileobj = TemporaryFile('w+')
        s_xml.to_csv(to_file=fileobj)
        fileformat = 'xml'
    fileobj.seek(0)

    return (fileobj, fileformat)
