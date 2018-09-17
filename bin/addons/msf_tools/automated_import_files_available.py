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

    _columns = {
        'import_id': fields.many2one('automated.import', string='Automated Import', required=True),
        'po_id': fields.many2one('purchase.order', string='Purchase Order'),
        'in_id': fields.many2one('stock.picking', string='Incoming Shipment'),
        'display_info': fields.text(string='Files available', readonly=True),
        'selected_model': fields.char('Related model', size=256),
    }

    def on_change_display_info(self, cr, uid, ids, import_id, po_id, in_id, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not import_id:
            return {}

        if po_id:
            po_name = self.pool.get('purchase.order').read(cr, uid, po_id, ['name'], context=context)['name']
            po_name = po_name.replace('/', '_')
        if in_id:
            in_name = self.pool.get('stock.picking').read(cr, uid, in_id, ['name'], context=context)['name']
            in_name = in_name.replace('/', '_')

        auto_import = self.pool.get('automated.import').browse(cr, uid, import_id, context=context)
        if auto_import.ftp_protocol == 'ftp' and auto_import.ftp_source_ok:
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
        elif auto_import.ftp_protocol == 'sftp' and auto_import.ftp_source_ok:
            files = []
            context.update({'no_raise_if_ok': True})
            sftp = self.pool.get('automated.import').sftp_test_connection(cr, uid, auto_import.id, context=context)
            context.pop('no_raise_if_ok')
            file_names = []
            with sftp.cd(auto_import.src_path):
                files = sftp.listdir()
                for file in files:
                    if sftp.isfile(file):
                        file_names.append(os.path.join(auto_import.src_path, file))
        else: # local
            file_names = all_files_under(auto_import.src_path)

        fold = 'local'
        if auto_import.ftp_source_ok and auto_import.ftp_protocol == 'ftp':
            fold = 'FTP'
        elif auto_import.ftp_source_ok and auto_import.ftp_protocol == 'sftp':
            fold = 'SFTP'

        found = False
        msg = _('Files available under "%s" (%s folder):\n') % (auto_import.src_path, fold)
        for fn in file_names:
            if auto_import.function_id.startswith and not os.path.basename(fn).startswith(auto_import.function_id.startswith):
                continue
            if po_id:
                if fn.find(po_name) != -1:
                    msg += '\t- %s\n' % os.path.basename(fn)
                    found = True
            elif in_id:
                if fn.find(in_name) != -1:
                    msg += '\t- %s\n' % os.path.basename(fn)
                    found = True
            else:
                msg += '\t- %s\n' % os.path.basename(fn)
                found = True
        if not found:
            msg = _('No files available under "%s" (%s folder)') % (auto_import.src_path, fold)

        return {'value': {'display_info': msg, 'selected_model': auto_import.function_id.model_id.model}}

automated_import_files_available()
