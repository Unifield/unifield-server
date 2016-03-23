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

from osv import osv, fields
from sync_client import sync_client

class sync_manager(osv.osv_memory):
    _name = 'sync.client.sync_manager'

    _rec_name = 'state'

    def _get_state(self, cr, uid, context=None):
        return self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).state

    _columns = {
        'state' : fields.selection([('init','Init'),
                                    ('msg_push','Sending Message'),
                                    ('update_send','Sending Data'),
                                    ('update_validate','Validating Data'),
                                    ('update_pull','Receiving Data'),
                                    ('corrupted', 'Corrupted')], 'State', required=True, readonly=True),
    }

    _defaults = {
                 'state' : _get_state,
    }

    def sync(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').sync_manual_withbackup(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def sync_threaded(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').sync_threaded(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def sync_manual_threaded(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').sync_manual_threaded(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def pull_data(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').pull_update(cr, uid, recover=False, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def pull_all_data(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').pull_update(cr, uid, recover=True, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def push_data(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').push_update(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def push_message(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').push_message(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def pull_message(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').pull_message(cr, uid, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def recover_message(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').pull_message(cr, uid, recover=True, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def recover_data_and_messages(self, cr, uid, ids, context=None):
        self.pool.get('sync.client.entity').sync_manual_threaded(cr, uid, recover=True, context=context)
        return {'type': 'ir.actions.act_window_close'}

sync_manager()
