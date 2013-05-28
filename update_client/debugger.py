from osv import osv, fields
import updater
import release

import logging
import os
import time


class wizard(osv.osv_memory):
    _name = 'sync.client.debugger'

    def action_populate(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.logs').populate(cr, uid, ids[0], context=context)
        return {}

    def _get_last_revision(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        currev = revisions._get_last_revision(cr, uid, context=context)
        return currev.name if currev else False

    _columns = {
        'release_version' : fields.char("Unifield Version",
            size=64, readonly=True),
        'database_revision' : fields.char("Database Revision",
            size=64, readonly=True),
        'log_ids' : fields.one2many('sync.client.logs', 'wizard_id',
            string="Log Files", readonly=True),
    }

    _defaults = {
        'release_version' : release.version[:-16] or release.version,
        'database_revision' : _get_last_revision,
    }


class debugger(osv.osv_memory):
    _name = 'sync.client.logs'

    def populate(self, cr, user, wizard_id, context=None):
        ids = self.search(cr, user, [], context=context)
        self.unlink(cr, user, ids, context=context)
        ids = []
        for baseFilename in map(lambda h: h.baseFilename,
                                logging.Logger.manager.root.handlers):
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
                    ids.append( self.create(cr, user, {
                        'wizard_id' : wizard_id,
                        'name'      : filename,
                        'path'      : filepath,
                        'mtime'     : time.strftime("%F %T",
                            time.localtime(stat.st_mtime)),
                    }, context=context) )
        if os.path.isfile(updater.log_file):
            if os.sep in baseFilename:
                path, filename = updater.log_file.rsplit(os.sep, 1)
            else:
                path, filename = os.curdir, updater.log_file
            stat = os.stat(updater.log_file)
            ids.append( self.create(cr, user, {
                'wizard_id' : wizard_id,
                'name'      : filename,
                'path'      : os.path.join(path, filename),
                'mtime'     : time.strftime("%F %T",
                    time.localtime(stat.st_mtime)),
            }, context=context) )
        return ids

    def _get_log_content(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for rec in self.browse(cr, uid, ids, context=context):
            f = open(rec.path, 'rb')
            try:
                content = f.read()
                result[rec.id] = len(content) if context.get('bin_size') else \
                    content.encode('base64')
            finally:
                f.close()
        return result

    _columns = {
        'wizard_id' : fields.many2one('sync.client.debugger', string="Debugger"),
        'name' : fields.char("File name", size=64, readonly=True),
        'path' : fields.text("File path", readonly=True),
        'mtime' : fields.datetime("Modification Time", readonly=True),
        'content' : fields.function(_get_log_content, readonly=True,
            string="Download file", type='binary', method=True),
    }

    _order = "mtime desc"


debugger()
wizard()
