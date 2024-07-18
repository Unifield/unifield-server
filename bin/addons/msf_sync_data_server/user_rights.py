# -*- coding: utf-8 -*-


from osv import osv
from tools.config import config
import os
import hashlib
import logging
import release
from base64 import b64encode

class user_rights_auto_load(osv.osv_memory):
    _name = 'user.rights.auto.load'
    _logger = logging.getLogger('sync.server')
    _columns = {

    }

    def load(self, cr, uid, mode, context=None):
        if context is None:
            context = {}
        context['run_foreground'] = True
        zipfile = os.path.join(config['root_path'], 'addons', 'msf_sync_data_server', 'data', 'UR.zip')
        if os.path.isfile(zipfile):
            f = open(zipfile, 'rb')
            plain_zip = f.read()
            f.close()
            md5 = hashlib.md5(plain_zip).hexdigest()
            ur_obj = self.pool.get('sync_server.user_rights')
            if ur_obj.search_exist(cr, uid, [('sum', '=', md5)], context=context):
                self._logger.info('UR file exists on server')
                return True
            cur_data = ur_obj.get_last_user_rights_info(cr, uid, context=context)
            if cur_data.get('sum') != md5:
                ur_name = release.version
                i = 0
                while ur_obj.search(cr, uid, [('name', '=', ur_name)]):
                    i += 1
                    ur_name = '%s V%s' % (release.version, i)

                self._logger.info('UR file found current sum: %s, new sum: %s, name: %s' % (cur_data.get('sum'), md5, ur_name))

                loader = self.pool.get('sync_server.user_rights.add_file')
                load_id = loader.create(cr, uid, {'name': ur_name, 'zip_file': b64encode(plain_zip), 'install': False}, context=context)
                loader.import_zip(cr, uid, [load_id], context=context)
                result = loader.read(cr, uid, load_id, ['state', 'message'], context=context)
                if result['state'] != 'done':
                    self._logger.error('Unable to load UR: %s' % result['message'])
                    #raise osv.except_osv(_('Warning !'), result['message'])
                else:
                    loader.done(cr, uid, [load_id], context=context)
                    self._logger.info('New UR file loaded')
        return True


user_rights_auto_load()
