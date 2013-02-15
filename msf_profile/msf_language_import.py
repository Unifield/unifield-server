# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import tools
import base64
from tempfile import TemporaryFile
from osv import osv, fields
import csv
from tools.translate import _
import threading
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import zipfile
import pooler
import cStringIO


class msf_language_import(osv.osv_memory):
    """ Language Import """

    _name = "msf.language.import"
    _description = "Language Import"
    _inherit = "ir.wizard.screen"

    def _get_languages(self, cr, uid, context):
        return self.pool.get('base.language.export')._get_languages(cr, uid, context)

    _columns = {
        'name': fields.selection(_get_languages, 'Language', required=1),
        'data': fields.binary('File', required=True),
    }

    _defaults = {
        'name': lambda *a: 'fr_MF',
    }

    def import_data_lang(self, cr, uid, ids, context):
        """
        This method is for importing the data translation in MSF
        """
        thread = threading.Thread(target=self._import_data_bg, args=(cr.dbname, uid, ids, context))
        thread.start()
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_profile', 'view_msf_import_language_2')[1]
        return {
            'view_mode': 'form',
            'view_id': [view_id],
            'view_type': 'form',
            'res_model': 'msf.language.import',
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }

    def _import_data_bg(self, dbname, uid, ids, context):

        try:
            cr = pooler.get_db(dbname).cursor()
            import_data = self.browse(cr, uid, ids)[0]
            filedata = base64.decodestring(import_data.data)

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
                fileobj.seek(0)
            else:
                fileobj = TemporaryFile('w+')
                s_xml.to_csv(to_file=fileobj)
                fileobj.seek(0)

            reader = csv.reader(fileobj, delimiter=",",quotechar='"')
            first_line = reader.next()
            rejected = []
            trans_obj = self.pool.get('ir.translation')
            line = 0
            for row in reader:
                line += 1
                if ',' not in row[1]:
                    rejected.append(_('Line %s, Column B: Incorrect format') % (line, ))
                    continue
                obj, field = row[1].split(',', 1)
                obj = obj.strip()
                field = field.strip()
                if obj == 'product.product' and field == 'name':
                    obj = 'product.template'

                obj_ids = self.pool.get(obj).search(cr, uid, [(field, '=', row[2])])
                if not obj_ids:
                    rejected.append(_('Line %s Record %s not found') % (line, row[2].decode('utf-8')))
                    continue
                try:
                    cr.execute("""delete from ir_translation
                        where
                            lang=%s and
                            type='model' and
                            name=%s and
                            res_id in %s"""
                        ,(import_data.name, "%s,%s" % (obj, field), tuple(obj_ids))
                    )
                    for obj_id in obj_ids:
                        trans_obj.create(cr, uid, {
                            'lang': import_data.name,
                            'src': row[2],
                            'name': '%s,%s' % (obj, field),
                            'res_id': obj_id,
                            'value': row[3],
                            'type': 'model'
                        })
                    cr.commit()
                except Exception, e:
                    cr.rollback()
                    rejected.append(_('Line %s, system error: %s') % (line, e))

            tools.cache.clean_caches_for_db(cr.dbname)
            fileobj.close()
            req_obj = self.pool.get('res.request')

            req_val = {
                'name': _('Import Translation Data: %s/%s') % (line-len(rejected), line),
                'act_from': uid,
                'act_to': uid,
                #'export_trans': True,
            }
            if rejected:
                req_val['body'] =  _("The following lines couldn't be imported:\n%s") % ("\n".join(rejected), )
            else:
                req_val['body'] = _("Your translation file has been successfully imported.")

            req_id = req_obj.create(cr, uid, req_val)
            req_obj.request_send(cr, uid, [req_id])

            self.write(cr, uid, [ids[0]], {'data': ''})
            cr.commit()
            cr.close()

        except Exception, e:
            cr.rollback()
            self.write(cr, uid, [ids[0]], {'data': ''})
            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': _('Import translation failed'),
                'act_from': uid,
                'act_to': uid,
                #'import_trans': True,
                'body': _('''The process to import the translation file failed !
                %s
                ''') % (e,)
            })
            cr.commit()
            cr.close()
            raise

        return {}

msf_language_import()
