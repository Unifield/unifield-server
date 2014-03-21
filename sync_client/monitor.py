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
import pooler
import tools


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
            'msg_pull' : 'null',
            'data_push' : 'null',
            'msg_push' : 'null',
        }
        self.info.update(defaults)
        self.final_status = 'ok'
        self.messages = []
        self.link_to = set()
        self.row_id = self.monitor.create(self.cr, self.uid, self.info, context=self.context)

    def write(self):
        if not hasattr(self, 'cr'):
            raise Exception("Cannot write into a closed sync.monitor logger!")
        self.info['error'] = "\n".join(map(tools.ustr, self.messages))
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
            self.monitor.last_status = (status, self.info['end'])

    def close(self):
        self.switch('status', self.final_status)
        for model, column, res_id in self.link_to:
            self.monitor.pool.get(model).write(self.cr, self.uid, res_id, {
                column : self.row_id,
            }, context=self.context)
        self.write()
        self.cr.close()
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
        monitor_ids = self.search(cr, 1, [], limit=1, order='sequence_number desc')
        if not monitor_ids: return
        # get the status of the last row
        row = self.read(cr, 1, monitor_ids, ['status', 'end'])[0]
        self.last_status = (row['status'], row['end'])

    def _get_default_sequence_number(self, cr, uid, context=None):
        return int(self.pool.get('ir.sequence').get(cr, uid, 'sync.monitor'))

    def get_logger(self, cr, uid, defaults={}, context=None):
        return MonitorLogger(cr, uid, defaults=defaults, context=context)

    def name_get(self, cr, user, ids, context=None):
        return [
            (rec.id, "(%d) %s" % (rec.sequence_number, rec.start))
            for rec in self.browse(cr, user, ids, context=context) ]

    _rec_name = 'start'

    _columns = {
        'sequence_number' : fields.integer("Sequence",  readonly=True, required=True),
        'start' : fields.datetime("Start Date", readonly=True, required=True),
        'end' : fields.datetime("End Date", readonly=True),
        'data_pull' : fields.selection(status_dict.items(), string="Data Pull", readonly=True),
        'msg_pull' : fields.selection(status_dict.items(), string="Msg Pull", readonly=True),
        'data_push' : fields.selection(status_dict.items(), string="Data Push", readonly=True),
        'msg_push' : fields.selection(status_dict.items(), string="Msg Push", readonly=True),
        'status' : fields.selection(status_dict.items(), string="Status", readonly=True),
        'error' : fields.text("Messages", readonly=True),
    }

    _defaults = {
        'start' : fields.datetime.now,
        'sequence_number' : _get_default_sequence_number,
    }

    #must be sequence!
    _order = "sequence_number desc"

sync_monitor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

