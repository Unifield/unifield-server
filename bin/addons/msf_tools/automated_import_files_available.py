# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF
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

from osv import osv
from osv import fields
from tools.translate import _

import os


def all_files_under(path):
    """
    Iterates through all files that are under the given path.
    :param path: Path on which we want to iterate
    """
    res = []
    for cur_path, dirnames, filenames in os.walk(path):
        res.extend([os.path.join(cur_path, fn) for fn in filenames])
        break # don't parse children
    return res


class automated_import_files_available(osv.osv_memory):
    _name = 'automated.import.files.available'

    def on_change_display_info(self, cr, uid, ids, import_id, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        auto_import = self.pool.get('automated.import').browse(cr, uid, import_id, context=context)
        if auto_import.ftp_source_ok:
            files = []
            context.update({'no_raise_if_ok': True})
            ftp_connec = self.pool.get('automated.import').ftp_test_connection(cr, uid, auto_import.id, context=context)
            context.pop('no_raise_if_ok')
            ftp_connec.dir(auto_import.src_path, files.append)
            file_names = []
            for file in files:
                if file.startswith('d'): # directory
                    continue
                file_names.append( os.path.join(auto_import.src_path, file.split(' ')[-1]) )
        else: # local
            file_names = all_files_under(auto_import.src_path)

        msg = ''
        if not file_names:
            msg = _('No files available under "%s" (%s folder)') % (auto_import.src_path, _('local') if not auto_import.ftp_source_ok else _('FTP'))
        else:
            msg = _('Files available under "%s" (%s folder):\n') % (auto_import.src_path, _('local') if not auto_import.ftp_source_ok else _('FTP'))
            for fn in file_names:
                msg += '\t- %s\n' % fn

        return {'value': {'display_info': msg}}


    _columns = {
        'import_id': fields.many2one('automated.import', string='Automated Import', required=True),
        'display_info': fields.text(string='Files available', readonly=True),
    }


automated_import_files_available()
