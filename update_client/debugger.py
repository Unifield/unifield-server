from osv import osv, fields
import updater
import release
from report import report_sxw
import pooler

import logging
import os
import time


class wizard(osv.osv_memory):
    _name = 'sync.client.debugger'

    def action_populate(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.logs').populate(cr, uid, ids[0], context=context)
        return {}

    def open_wiz(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        nids = self.search(cr, uid, [], limit=1, context=context)
        if not nids:
            nids = [self.create(cr, uid, {}, context=context)]
        self.action_populate(cr, 1, nids, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sync.client.debugger',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': nids[0],
            'target': 'crush',
        }


    _columns = {
        'release_version' : fields.char("Unifield Version",
            size=64, readonly=True),
        'log_ids' : fields.one2many('sync.client.logs', 'wizard_id',
            string="Log Files", readonly=True),
    }

    _defaults = {
        'release_version' : release.version[:-16] or release.version,
    }


class debugger(osv.osv_memory):
    _name = 'sync.client.logs'

    def populate(self, cr, user, wizard_id, context=None):
        ids = self.search(cr, user, [('wizard_id', '=', wizard_id)], context=context)
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
                    data = {'mtime': time.strftime("%F %T", time.localtime(stat.st_mtime))}
                    if filepath not in all_file:
                        data.update({
                            'wizard_id': wizard_id,
                            'name': filename,
                            'path': filepath
                        })
                        self.create(cr, user, data, context=context)
                    else:
                        self.write(cr, user, [user, all_file[filepath]], data)
                        del(all_file[filepath])
        if os.path.isfile(updater.log_file):
            full_path = os.path.abspath(updater.log_file)
            path, filename = full_path.rsplit(os.sep, 1)
            stat = os.stat(updater.log_file)
            data = {'mtime': time.strftime("%F %T", time.localtime(stat.st_mtime))}
            if full_path not in all_file:
                data.update({
                    'wizard_id': wizard_id,
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

        result = {}

    _columns = {
        'wizard_id' : fields.many2one('sync.client.debugger', string="Debugger"),
        'name' : fields.char("File name", size=64, readonly=True),
        'path' : fields.text("File path", readonly=True),
        'mtime' : fields.datetime("Modification Time", readonly=True),
    }

    _order = "mtime desc"


debugger()
wizard()

class export_log_content(report_sxw.report_sxw):
    def create(self, cr, uid, ids, data, context=None):
        log = pooler.get_pool(cr.dbname).get('sync.client.logs')
        for rec in log.read(cr, uid, ids, ['path'], context=context):
            f = open(rec['path'], 'rb')
            try:
                result = (f.read(), 'txt')
            finally:
                f.close()
        return result

export_log_content('report.sync.client.logs.content', 'sync.client.logs', False, parser=False)

