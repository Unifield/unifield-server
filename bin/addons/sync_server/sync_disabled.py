# -*- coding: utf-8 -*-


from osv import osv
from osv import fields
import time


class sync_server_disabled(osv.osv):
    _name = 'sync.server.disabled'
    _description = 'Disable new sync'
    _rec_name = 'from_date'

    def _get_message(self,cr, uid, ids, name, args, context=None):
        msg = self.get_message(cr, uid, context=context)
        ret = {}
        for id in ids:
            ret[id] = msg
        return ret

    _columns = {
        'from_date': fields.datetime('From'),
        'to_date': fields.datetime('To'),
        'activate': fields.boolean('Active'),
        'message': fields.function(_get_message, type='char', string='message', method=1),
    }

    def _only_one(self, cr, uid, ids, context=None):
        return self.search(cr, uid, [], count=True) < 2

    _constraints = [
        (_only_one, 'Error! You cannot create new config.', ['activate']),
    ]

    _sql_constraints = [
        ('dates_ok', 'check (from_date < to_date)', 'From / To dates inconsistent')
    ]

    def get_or_create(self, cr, uid, context=None):
        ids = self.search(cr, uid, [])
        if ids:
            return ids[0]

        return self.create(cr, uid, {'activate': False}, context=context)

    def is_sync_active(self, cr, uid, context=None):
        now = fields.datetime.now()
        return not self.search_exist(cr, uid, [('activate', '=', True), ('from_date', '<=', now), ('to_date', '>=', now)])

    def is_set(self, cr, uid, context=None):
        now = fields.datetime.now()
        return self.search_exist(cr, uid, [('activate', '=', True), ('to_date', '>=', now)])

    def get_data(self, cr, uid, context=None):
        rec_id = self.get_or_create(cr, uid, context)
        data = self.read(cr, uid, rec_id, ['from_date', 'to_date', 'activate'], context)
        from_d = ''
        to_d = ''

        if data['from_date']:
            from_d = time.strftime('%d/%b/%Y %H:%M', time.strptime(data['from_date'], '%Y-%m-%d %H:%M:%S'))
        if data['to_date']:
            to_d = time.strftime('%d/%b/%Y %H:%M', time.strptime(data['to_date'], '%Y-%m-%d %H:%M:%S'))
        data['from_date'] = from_d
        data['to_date'] = to_d

        return data

    def get_message(self, cr, uid, context=None):
        if not self.is_set(cr, uid, context):
            return ""

        data = self.get_data(cr, uid, context=None)
        if not self.is_sync_active(cr, uid, context):
            return "Sync IS DISABLED from %s to %s" % (data['from_date'], data['to_date'])

        return "Sync WILL BE DISABLED from %s to %s" % (data['from_date'], data['to_date'])



sync_server_disabled()
