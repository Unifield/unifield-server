# -*- coding: utf-8 -*-

import tools
import base64
import cStringIO
import pooler
from osv import fields,osv
from tools.translate import _
from tools.misc import get_iso_codes
import threading
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import logging

class base_language_export(osv.osv_memory):
    _inherit = "base.language.export"
    _name = "base.language.export"


    _columns = {
        'format': fields.selection([('csv', 'CSV File'), ('po', 'PO File'), ('tgz', 'TGZ Archive'), ('xls', 'Microsoft SpreadSheet XML')], 'File Format', required=True)
    }

    _defaults = {
        'format': lambda *a: 'xls',
    }

    def act_getfile_background(self, cr, uid, ids, context=None):
        thread = threading.Thread(target=self._export, args=(cr.dbname, uid, ids, context))
        thread.start()
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_profile', 'export_lang_background_result')[1]

        return {
            'view_mode': 'form',
            'view_id': [view_id],
            'view_type': 'form',
            'res_model': 'base.language.export',
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }

    def open_requests(self, cr, uid, ids, context=None):
        return {
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'res.request',
            'type': 'ir.actions.act_window',
            'target': 'crunch',
            'context': {},
        }

    def _export(self, dbname, uid, ids, context=None):
        #modules = ['account_mcdb']
        modules = 'all'
        try:
            cr = pooler.get_db(dbname).cursor()

            this = self.browse(cr, uid, ids)[0]
            if this.lang:
                filename = get_iso_codes(this.lang)
            this.name = "%s.%s" % (filename, this.format)

            if this.format == 'xls':
                trans = tools.trans_generate(this.lang, modules, cr)
                if trans:
                    headers = []
                    for h in trans.pop(0):
                        headers.append([h, 'char'])
                
                    xml = SpreadsheetCreator(title=this.name, headers=headers, datas=trans)
                    out = base64.encodestring(xml.get_xml(default_filters=['decode.utf8']))
            else:
                buf=cStringIO.StringIO()
                tools.trans_export(this.lang, modules, buf, this.format, cr)
                out = base64.encodestring(buf.getvalue())
                buf.close()

            subject = _("Export translations %s %s ") % (this.lang, this.format)
            summary = _('''Export translations %s %s
    Find in attachment the file''') % (this.lang, this.format)
            request_obj = self.pool.get('res.request')
            req_id = request_obj.create(cr, uid, {
                'name': subject,
                'act_from': uid,
                'act_to': uid,
                'body': summary,
            })

            if req_id:
                request_obj.request_send(cr, uid, [req_id])

            attachment = self.pool.get('ir.attachment')
            attachment.create(cr, uid, {
                'name': this.name,
                'datas_fname': this.name,
                'description': 'Translations',
                'res_model': 'res.request',
                'res_id': req_id,
                'datas': out,
            })
            cr.commit()
            cr.close()
        except Exception, e:
            cr.rollback()
            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': 'Translations Export failed',
                'act_from': uid,
                'act_to': uid,
                'body': '''The process to export the translations failed !
                %s
                '''% (e,),
            })
            cr.commit()
            cr.close()
            raise
        logging.getLogger('export').info('Export translation ended')

base_language_export()
