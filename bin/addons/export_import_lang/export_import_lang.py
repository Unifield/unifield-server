# -*- coding: utf-8 -*-

import tools
import base64
import io
import pooler
from osv import fields,osv
from tools.translate import _
from tools.misc import get_iso_codes
import threading
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import logging
from . import lang_tools

class base_language_export(osv.osv_memory):
    _inherit = "base.language.export"
    _name = "base.language.export"


    _columns = {
        'only_translated_terms': fields.selection([('', 'All terms'), ('y', 'Only translated'), ('n', 'Only untranslated')], 'Filter'),
        'format': fields.selection([('csv', 'CSV File'), ('po', 'PO File'), ('tgz', 'TGZ Archive'), ('xls', 'Microsoft SpreadSheet XML'), ('compact.xls', 'Compact SpreadSheet XML')], 'File Format', required=True),
        'advanced': fields.boolean('Show advanced options'),
    }

    _defaults = {
        'format': lambda *a: 'xls',
        'only_translated_terms': lambda *a: False,
    }

    def act_getfile_background(self, cr, uid, ids, context=None):
        thread = threading.Thread(target=self._export, args=(cr.dbname, uid, ids, context))
        thread.start()
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'export_import_lang', 'export_lang_background_result')[1]

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
        return lang_tools.open_requests(self, cr, uid, ids, 'export', context)

    def split_xlscell(self, array):
        size = len(array)
        if size > 1 and len('\n'.join(array)) > 32700:
            half_size = int(size/2)
            return self.split_xlscell(array[:half_size])+self.split_xlscell(array[half_size:])
        else:
            return [array]

    def _export(self, dbname, uid, ids, context=None):
        #modules = ['account_mcdb']
        modules = 'all_installed'
        try:
            cr = pooler.get_db(dbname).cursor()

            this = self.browse(cr, uid, ids)[0]
            if this.modules:
                modules = [m.name for m in this.modules]
                modules.sort()

            if this.lang:
                filename = get_iso_codes(this.lang)
            this.name = "%s.%s" % (filename, this.format)
            ignore_name = ['ir.filters,model_id', 'ir.actions.server,copy_object', 'ir.ui.menu,icon', 'ir.sequence,code', 'stock.location,icon']
            out = ''
            if this.format in ('xls', 'compact.xls'):
                trans = tools.trans_generate(this.lang, modules, cr, ignore_name=ignore_name, only_translated_terms=this.only_translated_terms)
                if trans:
                    if this.format == 'compact.xls':
                        headers = [('Source', 'char'), ('Value', 'char'), ('Type', 'type'), ('Internal Data', 'char')]
                        # remove the header
                        trans.pop(0)
                        grouped_rows = {}
                        for module, type, name, res_id, src, trad in trans:
                            row = grouped_rows.setdefault((src, trad, type), {})
                            if ('translation' not in row) or (not row['translation']):
                                row['translation'] = trad
                            row.setdefault('tnrs', []).append('%s:%s:%s' % (type, name, res_id))

                        trans_data = []
                        for (src, trad, type), row in list(grouped_rows.items()):
                            for splited in self.split_xlscell(row['tnrs']):
                                trans_data.append([src, trad, type, '\n'.join(splited)])
                        xml = SpreadsheetCreator(title=this.name, headers=headers, datas=trans_data)

                    else:
                        headers = []
                        for h in trans.pop(0):
                            headers.append([h, 'char'])
                        xml = SpreadsheetCreator(title=this.name, headers=headers, datas=trans)

                    out = base64.b64encode(xml.get_xml(default_filters=['decode.utf8']))
            else:
                buf=io.StringIO()
                tools.trans_export(this.lang, modules, buf, this.format, cr, ignore_name=ignore_name, only_translated_terms=this.only_translated_terms)
                out = base64.b64encode(bytes(buf.getvalue(), 'utf8'))
                buf.close()

            subject = _("Export translation %s %s ") % (this.lang, this.format)
            summary = _('''Export translation %s %s
    Find the file in attachment in the right panel.''') % (this.lang, this.format)
            request_obj = self.pool.get('res.request')
            req_id = request_obj.create(cr, uid, {
                'name': subject,
                'act_from': uid,
                'act_to': uid,
                'export_trans': True,
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
            cr.close(True)
        except Exception as e:
            cr.rollback()
            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': _('Export translation failed'),
                'act_from': uid,
                'act_to': uid,
                'export_trans': True,
                'body': _('''The process to export the translations failed !
                %s
                ''')% (e,),
            })
            cr.commit()
            cr.close(True)
            raise
        logging.getLogger('export').info('Export translation ended')

base_language_export()


class base_language_import(osv.osv_memory):
    _name = "base.language.import"
    _inherit = "base.language.import"

    def act_cancel(self, cr, uid, ids, context=None):
        return {'type':'ir.actions.act_window_close' }

    def import_lang_background(self, cr, uid, ids, context):
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'export_import_lang', 'import_lang_background_result')[1]

        return {
            'view_mode': 'form',
            'view_id': [view_id],
            'view_type': 'form',
            'res_model': 'base.language.import',
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }

    def open_requests(self, cr, uid, ids, context=None):
        return lang_tools.open_requests(self, cr, uid, ids, 'import', context)

    def _import(self, dbname, uid, ids, context=None):
        try:
            cr = pooler.get_db(dbname).cursor()
            import_data = self.browse(cr, uid, ids)[0]
            (fileobj, fileformat) = lang_tools.get_data_file(cr, uid, import_data.data)
            if fileformat == 'xml':
                first_line = fileobj.readline().strip().replace('"', '').replace(' ', '')
                if first_line.startswith('Source'):
                    fileformat = 'compactcsv'
                else:
                    fileformat = 'csv'
            else:
                first_line = fileobj.readline().strip().replace('"', '').replace(' ', '')
                fileformat = first_line.endswith("type,name,res_id,src,value") and 'csv' or 'po'
            fileobj.seek(0)

            lang_obj = self.pool.get('res.lang')
            lang_ids = lang_obj.search(cr, uid, [('code', '=', import_data.name)])
            if lang_ids:
                lang_data = lang_obj.read(cr, uid, lang_ids[0], ['translatable'])
                if not lang_data['translatable']:
                    lang_obj.write(cr, uid, [lang_ids[0]], {'translatable': True})


            tools.trans_load_data(cr, fileobj, fileformat, import_data.code, lang_name=import_data.name, context={'overwrite': 1})
            tools.trans_update_res_ids(cr)
            fileobj.close()

            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': _('Translation file imported'),
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
                'body': _('Your translation file has been successfully imported.')
            })
            if req_id:
                self.pool.get('res.request').request_send(cr, uid, [req_id])

            self.write(cr, uid, [ids[0]], {'data': ''})
            tools.cache.clean_caches_for_db(cr.dbname)
            tools.read_cache.clean_caches_for_db(cr.dbname)

            cr.commit()
            cr.close(True)
        except Exception as e:
            cr.rollback()
            self.write(cr, uid, [ids[0]], {'data': ''})
            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': _('Import translation failed'),
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
                'body': _('''The process to import the translation file failed !
                %s
                ''')% (e,),
            })
            cr.commit()
            cr.close(True)
            raise
        logging.getLogger('export').info('Import translation ended')

base_language_import()

class res_request(osv.osv):
    _name = 'res.request'
    _inherit = 'res.request'

    _columns = {
        'import_trans': fields.boolean('Import Translations request'),
        'export_trans': fields.boolean('Export Translations request'),
    }

    _defaults = {
        'import_trans': lambda *a: False,
        'export_trans': lambda *a: False,
    }
res_request()

class res_lang(osv.osv):
    _name = 'res.lang'
    _inherit = 'res.lang'

    def install_new_lang(self, cr, uid, ids, context=None):
        lang = self.read(cr, uid, ids[0], ['code'])
        self.write(cr, uid, [ids[0]], {'translatable': True})
        thread = threading.Thread(target=self._install_new_lang_bg, args=(cr.dbname, uid, ids[0], lang['code'], context))
        thread.start()
        return lang_tools.open_requests(self, cr, uid, ids, 'import', context)

    def _install_new_lang_bg(self, dbname, uid, id, code, context):
        try:
            cr = pooler.get_db(dbname).cursor()
            self.write(cr, uid, [id], {'translatable': True})
            modobj = self.pool.get('ir.module.module')
            mids = modobj.search(cr, uid, [('state', '=', 'installed')])
            modobj.update_translations(cr, uid, mids, code, context=context)
        except Exception as e:
            cr.rollback()
            self.pool.get('res.request').create(cr, uid, {
                'name': _('Failed to install new language %s') % code,
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
                'body': _('''The process to install new language %s failed !
                    %s
                ''') % (code, e)
            })
        else:
            self.pool.get('res.request').create(cr, uid, {
                'name': _('New language %s installed') % code,
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
                'body': _("New language %s terms successfully loaded") % code
            })

        cr.commit()
        cr.close(True)

res_lang()

class base_language_install(osv.osv_memory):
    _name = "base.language.install"
    _inherit = "base.language.install"

    _columns = {
        'lang': fields.selection([('fr_MF', 'MSF French'), ('es_MF', 'MSF Spanish')],'Language', required=True),
    }
base_language_install()
