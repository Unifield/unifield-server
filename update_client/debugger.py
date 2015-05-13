from osv import osv, fields
import updater
import release
from report import report_sxw
import pooler
import zipfile
import tempfile

import logging
import os
import time


class debugger(osv.osv):
    _name = 'sync.client.logs'
    _order = "mtime desc, id"
    _description = 'Log files'

    def open_wiz(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        self.populate(cr, 1, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sync.client.logs',
            'view_type': 'form',
            'view_mode': 'tree,form',
        }

    def populate(self, cr, user, context=None):
        ids = self.search(cr, user, [], context=context)
        all_file = {}
        if ids:
            for logfile in self.read(cr, user, ids, ['path']):
                all_file[logfile['path']] = logfile['id']
        for baseFilename in [h.baseFilename for h in logging.Logger.manager.root.handlers if hasattr(h, 'baseFilename')]:
            if os.sep in baseFilename:
                path, filename = baseFilename.rsplit(os.sep, 1)
            else:
                path, filename = os.curdir, baseFilename
            for filepath, filename in map(
                    lambda f: (os.path.join(path, f), f),
                    [filename] + filter(
                        lambda f: f.startswith(filename+'.'),
                        os.listdir(path))):
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    data = {'mtime': time.strftime("%F %T", time.localtime(stat.st_mtime)), 'type': 'server'}
                    if filepath not in all_file:
                        data.update({
                            'name': filename,
                            'path': filepath
                        })
                        self.create(cr, user, data, context=context)
                    else:
                        self.write(cr, user, [all_file[filepath]], data)
                        del(all_file[filepath])
        if os.path.isfile(updater.log_file):
            full_path = os.path.abspath(updater.log_file)
            path, filename = full_path.rsplit(os.sep, 1)
            stat = os.stat(updater.log_file)
            data = {'mtime': time.strftime("%F %T", time.localtime(stat.st_mtime)), 'type': 'update'}
            if full_path not in all_file:
                data.update({
                    'name': filename,
                    'path': full_path
                })
                self.create(cr, user, data, context=context)
            else:
                self.write(cr, user, [all_file[full_path]], data, context=context)
                del(all_file[full_path])

        if all_file:
            self.unlink(cr, user, all_file.values(), context=context)
        return True

    def get_content(self, cr, uid, ids, context=None):
        name = self.read(cr, uid, ids[0], ['name'])['name']
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sync.client.logs.content',
            'datas': {'ids': [ids[0]], 'target_filename': name, 'force_attach': 1}
        }

    _columns = {
        'name': fields.char("File name", size=64, readonly=True),
        'path': fields.text("File path", readonly=True),
        'mtime': fields.datetime("Modification Time", readonly=True),
        'type': fields.selection([('update', 'Update'), ('server', 'Server')], string='Type', readonly=True),
    }



debugger()

class export_log_content(report_sxw.report_sxw):
    def create(self, cr, uid, ids, data, context=None):
        log = pooler.get_pool(cr.dbname).get('sync.client.logs')
        if len(ids) == 1 and data.get('force_attach') == 1:
            for rec in log.read(cr, uid, ids, ['path'], context=context):
                f = open(rec['path'], 'rb')
                try:
                    result = (f.read(), 'txt')
                finally:
                    f.close()
        else:
            null1, tmpzipname = tempfile.mkstemp()
            zf = zipfile.ZipFile(tmpzipname, 'w')
            for rec in log.read(cr, uid, ids, ['path', 'name'], context=context):
                zf.write(rec['path'], rec['name'], compress_type=zipfile.ZIP_DEFLATED)
            zf.close()
            result = (file(tmpzipname, 'rb').read(), 'zip')
            os.close(null1)
            os.unlink(tmpzipname)
        return result

export_log_content('report.sync.client.logs.content', 'sync.client.logs', False, parser=False)

