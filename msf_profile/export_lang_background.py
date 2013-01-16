# -*- coding: utf-8 -*-

import tools
import base64
import cStringIO
import pooler
from osv import fields,osv
from tools.translate import _
from tools.misc import get_iso_codes
import threading

class base_language_export(osv.osv_memory):
    _inherit = "base.language.export"
    _name = "base.language.export"

    def act_getfile_background(self, cr, uid, ids, context=None):
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
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

    def _import(self, dbname, uid, ids, context=None):
        cr = pooler.get_db(dbname).cursor()

        this = self.browse(cr, uid, ids)[0]
        buf=cStringIO.StringIO()
        tools.trans_export(this.lang, 'all', buf, this.format, cr)
        if this.lang:
            filename = get_iso_codes(this.lang)
        this.name = "%s.%s" % (filename, this.format)
        out=base64.encodestring(buf.getvalue())
        subject = _("Export translations %s ") % (this.format,)
        summary = _('''Export translations %s
Find in attachment the file''') % (this.format,)
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
        buf.close()
        cr.commit()
        cr.close()

base_language_export()
