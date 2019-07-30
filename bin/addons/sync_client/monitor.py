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

import pooler
import tools
import os
import psutil
from osv import osv, fields
from tools.translate import _

class MonitorLogger(object):
    def __init__(self, cr, uid, defaults={}, context=None):
        db, pool = pooler.get_db_and_pool(cr.dbname)
        self.monitor = pool.get('sync.monitor')
        self.cr = db.cursor()
        self.cr.autocommit(True)
        self.uid = uid
        self.context = context
        self.info = {
            'status' : 'in-progress',
            'data_pull' : 'null',
            'data_pull_receive' : 'null',
            'data_pull_execute' : 'null',

            'msg_pull' : 'null',
            'msg_pull_receive' : 'null',
            'msg_pull_execute' : 'null',

            'msg_push' : 'null',
            'msg_push_create' : 'null',
            'msg_push_send' : 'null',

            'data_push' : 'null',
            'data_push_create' : 'null',
            'data_push_send' : 'null',

            'nb_msg_pull': 0,
            'nb_msg_push': 0,
            'nb_data_pull': 0,
            'nb_data_push': 0,
            'nb_msg_not_run': 0,
            'nb_data_not_run': 0,

        }
        self.info.update(defaults)
        self.final_status = 'ok'
        self.messages = []
        self.link_to = set()
        self.row_id = self.monitor.create(self.cr, self.uid, self.info, context=self.context)

    def write(self):
        if not hasattr(self, 'cr'):
            raise Exception("Cannot write into a closed sync.monitor logger!")
        self.info['error'] = "\n".join(map(tools.ustr, self.messages)) or False
        self.monitor.write(self.cr, self.uid, [self.row_id], self.info, context=self.context)

    def __format_message(self, message, step):
        return "%s: %s" % (self.monitor._columns[step].string, message) \
               if step is not None and not step == 'status' \
               else message

    def append(self, message='', step=None):
        self.messages.append(self.__format_message(message, step))
        return len(self.messages) - 1

    def replace(self, index, message, step=None):
        self.messages[index] = self.__format_message(message, step)

    def pop(self, index):
        return self.messages.pop(index)

    def switch(self, step, status):
        if status in ('failed', 'aborted'):
            self.final_status = status
        self.info[step] = status
        if step == 'status' and status != 'in-progress':
            self.info['end'] = fields.datetime.now()
            self.monitor.last_status = (status, self.info['end'], self.info['nb_data_not_run'], self.info['nb_msg_not_run'])

    def update_sale_purchase_logger(self):
        # UTP-1200: Moved to this method and call this right after the message pull is done, not need to wait until
        # the end of sync since it's not relevant to the push but also to avoid unnecessary error caused by the
        # "in progress" issue (fixed but better to avoid)
        for model, column, res_id in self.link_to:
            # if a message failed, a rollback is made so the log message doesn't exist anymore
            if self.monitor.pool.get(model).exists(self.cr, self.uid, res_id, self.context):
                self.monitor.pool.get(model).write(self.cr, self.uid, res_id, {
                    column : self.row_id,
                }, context=self.context)

    def close(self):
        self.switch('status', self.final_status)
        self.write()
        self.cr.close(True)
        del self.cr

    def link(self, model, column, res_id):
        self.link_to.add((model, column, res_id))

    def unlink(self, model, column, res_id):
        try:
            self.link_to.remove((model, column, res_id))
        except KeyError:
            pass

    def __del__(self):
        self.close()


## msf_III.3_Monitor_object
class sync_monitor(osv.osv):
    _name = "sync.monitor"

    status_dict = {
        'ok' : 'Ok',
        'null' : '/',
        'in-progress' : 'In Progress...',
        'failed' : 'Failed',
        'aborted' : 'Aborted',
    }

    def __init__(self, pool, cr):
        super(sync_monitor, self).__init__(pool, cr)
        self.last_status = None
        # check table existence
        cr.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename = %s;",
                   [self._table])
        if not cr.fetchone(): return
        # check rows existence
        monitor_ids = self.search(cr, 1, [('status', '!=', False)], limit=1, order='sequence_number desc')
        if not monitor_ids: return
        # get the status of the last row
        row = self.read(cr, 1, monitor_ids, ['status', 'end', 'nb_data_not_run', 'nb_msg_not_run'])[0]
        self.last_status = (row['status'], row['end'], row['nb_data_not_run'], row['nb_msg_not_run'])

    def _get_default_sequence_number(self, cr, uid, context=None):
        return int(self.pool.get('ir.sequence').get(cr, uid, 'sync.monitor'))

    def _get_default_instance_id(self, cr, uid, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        return instance and instance.id

    def _get_default_destination_instance_id(self, cr, uid, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if instance:
            if instance.parent_id:
                if instance.parent_id.parent_id:
                    return instance.parent_id.parent_id.id
                return instance.parent_id.id
        return False


    def _get_my_instance(self, cr, uid, ids, field_name, args, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if not instance:
            return dict.fromkeys(ids, False)
        ret = {}
        for msg in self.read(cr, uid, ids, ['instance_id']):
            ret[msg['id']] = msg['instance_id'] and msg['instance_id'][0] == instance.id

        return ret

    def _search_my_instance(self, cr, uid, obj, name, args, context=None):
        res = []
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if not instance:
            return []

        for arg in args:
            if arg[1] not in ('=', '!='):
                raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % name)
            cond = arg[2] in ('True', 't', '1', 1, True)
            if arg[1] == '!=':
                cond = not cond
            if cond:
                res += ['|',('instance_id', '=', instance.id),('instance_id', '=', False)]
            else:
                res.append(('instance_id', '!=', instance.id))

        return res


    def get_logger(self, cr, uid, defaults={}, context=None):
        return MonitorLogger(cr, uid, defaults=defaults, context=context)

    def name_get(self, cr, user, ids, context=None):
        return [
            (rec.id, "(%d) %s" % (rec.sequence_number, rec.start))
            for rec in self.browse(cr, user, ids, context=context) ]

    def interrupt(self, cr, uid, ids, context=None):
        return self.pool.get('sync.client.entity').interrupt_sync(cr, uid, context=context)

    def _is_syncing(self, cr, uid, ids, name, arg, context=None):
        res = dict.fromkeys(ids, "not_syncing")
        is_syncing = self.pool.get('sync.client.entity').is_syncing()
        max_id = 0
        if is_syncing:
            for monitor in self.browse(cr, uid, ids, context=context):
                if monitor.status == 'in-progress' and monitor.id > max_id:
                    max_id = monitor.id
        if max_id:
            if self.pool.get('sync.client.entity').aborting:
                res[max_id] = "aborting"
            else:
                res[max_id] = "syncing"

        return res

    _rec_name = 'start'

    _columns = {
        'sequence_number' : fields.integer("Seq",  readonly=True, required=True),
        'start' : fields.datetime("Start Date", readonly=True, required=True),
        'end' : fields.datetime("End Date", readonly=True),
        'user_rights': fields.selection(status_dict.items(), string="User Rights", readonly=True),
        'data_pull' : fields.selection(status_dict.items(), string="Data Pull", readonly=True),
        'data_pull_receive' : fields.selection(status_dict.items(), string="DP receive", readonly=True),
        'data_pull_execute' : fields.selection(status_dict.items(), string="DP execute", readonly=True),

        'msg_pull' : fields.selection(status_dict.items(), string="Msg Pull", readonly=True),
        'msg_pull_receive' : fields.selection(status_dict.items(), string="MP receive", readonly=True),
        'msg_pull_execute' : fields.selection(status_dict.items(), string="Msg execute", readonly=True),

        'data_push' : fields.selection(status_dict.items(), string="Data Push", readonly=True),
        'data_push_create' : fields.selection(status_dict.items(), string="DP create", readonly=True),
        'data_push_send' : fields.selection(status_dict.items(), string="DP send", readonly=True),

        'msg_push' : fields.selection(status_dict.items(), string="Msg Push", readonly=True),
        'msg_push_create' : fields.selection(status_dict.items(), string="MP Create", readonly=True),
        'msg_push_send' : fields.selection(status_dict.items(), string="MP Send", readonly=True),
        'status' : fields.selection(status_dict.items(), string="Status", readonly=True),
        'error' : fields.text("Messages", readonly=True),
        'state' : fields.function(_is_syncing, method=True, type='selection', string="Is Syncing", selection=[('syncing', 'Syncing'), ('not_syncing', 'Done'), ('aborting', 'Aborting')]),

        'instance_id': fields.many2one('msf.instance', 'Instance', select=1),
        'my_instance': fields.function(_get_my_instance, method=True, type='boolean', fnct_search=_search_my_instance, string="My Instance"),
        'nb_msg_pull': fields.integer('# pull msg'),
        'nb_msg_push': fields.integer('# push msg'),
        'nb_data_pull': fields.integer('# pull data'),
        'nb_data_push': fields.integer('# push data'),
        'nb_msg_not_run': fields.integer('# msg not run'),
        'nb_data_not_run': fields.integer('# data not run'),
        'destination_instance_id': fields.many2one('msf.instance', 'HQ Instance'),
    }

    _defaults = {
        'start' : fields.datetime.now,
        'sequence_number' : _get_default_sequence_number,
        'instance_id': _get_default_instance_id,
        'destination_instance_id':  _get_default_destination_instance_id,
    }

    #must be sequence!
    _order = "sequence_number desc, start desc, id desc"

sync_monitor()


class sync_version_instance_monitor(osv.osv):
    _name = "sync.version.instance.monitor"

    def _get_default_instance_id(self, cr, uid, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        return instance and instance.id

    def _get_my_instance(self, cr, uid, ids, field_name, args, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if not instance:
            return dict.fromkeys(ids, False)
        ret = {}
        for msg in self.read(cr, uid, ids, ['instance_id']):
            ret[msg['id']] = msg['instance_id'] and msg['instance_id'][0] == instance.id

        return ret

    def _search_my_instance(self, cr, uid, obj, name, args, context=None):
        res = []
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if not instance:
            return []

        for arg in args:
            if arg[1] not in ('=', '!='):
                raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % name)
            cond = arg[2] in ('True', 't', '1', 1, True)
            if arg[1] == '!=':
                cond = not cond
            if cond:
                res += ['|',('instance_id', '=', instance.id),('instance_id', '=', False)]
            else:
                res.append(('instance_id', '!=', instance.id))

        return res

    # code from https://stackoverflow.com/questions/13343700/bytes-to-human-readable-and-back-without-data-loss
    def bytes2human(self, n, format="%(value)i%(symbol)s"):
        """
        >>> bytes2human(10000)
        '9K'
        >>> bytes2human(100001221)
        '95M'
        """
        symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols[1:]):
            prefix[s] = 1 << (i+1)*10
        for symbol in reversed(symbols[1:]):
            if n >= prefix[symbol]:
                value = float(n) / prefix[symbol]
                return format % locals()
        return format % dict(symbol=symbols[0], value=n)

    def get_path_disk_usage(self, cr, uid, path):
        '''return a human readable information of used disk space of the given
        path, ex of output: 281.9G/436.1G (30.3% used)
        '''
        if os.path.exists(path):
            du = psutil.disk_usage(path)
            usage = '%s/%s (%s%% used)' % (self.bytes2human(du.free), self.bytes2human(du.total), du.percent)
        else:
            usage = "Path %s doesn't exists" % path
        return usage

    def _get_default_postgresql_disk_space(self, cr, uid, context=None):
        if os.name == 'nt':
            try:
                # get the path from the database
                cr.execute('SHOW data_directory')
                postgres_path = cr.fetchone()
                postgres_path = postgres_path  and postgres_path[0] or None
            except:
                cr.rollback()
                return "?"
        else:
            # for linux (RB)
            postgres_path = '/var/lib/postgresql/'
        return self.get_path_disk_usage(cr, uid, postgres_path)

    def _get_default_unifield_disk_space(self, cr, uid, context=None):
        unifield_path = tools.config['root_path']
        return self.get_path_disk_usage(cr, uid, unifield_path)

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance', select=1, m2o_order='code'),
        'my_instance': fields.function(_get_my_instance, method=True, type='boolean', fnct_search=_search_my_instance, string="My Instance"),
        'version': fields.char(size=128, string='Version', readonly=True),
        'backup_path': fields.char('Backup Location', size=128),
        'backup_date': fields.datetime("Backup Date", readonly=True,
                                       required=True),
        'backup_size': fields.integer('Backup Size', readonly=True),
        'instance_state': fields.related('instance_id', 'state', type='selection',
                                         selection=[('draft', 'Draft'),
                                                    ('active', 'Active'),
                                                    ('inactive', 'Inactive')],
                                         string='Instance State',
                                         readonly=True, store=True),
        'postgresql_disk_space': fields.char('PostgreSQL hd', size=128),
        'unifield_disk_space': fields.char('UniField hd', size=128),
        'cloud_date': fields.datetime('Cloud Date', readonly=True),
        'cloud_backup': fields.char('Cloud Dump', size=256, readonly=True),
        'cloud_error': fields.text('Cloud last error', readonly=True),
        'cloud_size': fields.integer('Cloud Size Zipped', readonly=True),
    }

    _defaults = {
        'backup_date' : fields.datetime.now,
        'instance_id': _get_default_instance_id,
        'cloud_size': 0,
        'backup_size': 0,
    }

    _sql_constraints = [
        ('instance_id_key', 'UNIQUE (instance_id)',  'You can not have two instances with the same id !')
    ]

    def create(self, cr, uid, vals, context=None):
        if 'instance_id' not in vals:
            instance_id = self._get_default_instance_id(cr, uid, context=context)
        else:
            instance_id = vals['instance_id']

        # look for existing entrie for this instance
        ids = self.search(cr, uid, [('instance_id', '=', instance_id)], limit=1)
        if ids:
            super(osv.osv, self).write(cr, uid, ids[0], vals)
            return ids[0]
        else:
            # create new entry
            return super(osv.osv, self).create(cr, uid, vals)

sync_version_instance_monitor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

