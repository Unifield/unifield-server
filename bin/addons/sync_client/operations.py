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
import logging
import threading
from histogram import Histogram

class ratelimit():
    ''' A mix-in class to implement rate limiting. '''
    MAX = 10000

    def _rate_limit(self, cr, uid, context=None):
        """ If this returns False, then the current create should
        be aborted."""
        if self._rl == 0:
            return False

        self._rl -= 1
        if self._rl > 0:
            return True

        vals = { 'kind': 'rate-limit',
                 'data': 'No more %s will be logged until next purge.' % self._rl_name
                 }
        # Do not call self.create, because it calls us -> loop.
        osv.osv.create(self, cr, uid, vals, context=context)
        return False

    def create(self, cr, uid, vals, context=None):
        if self._rate_limit(cr, uid, context):
            return osv.osv.create(self, cr, uid, vals, context=context)
        else:
            # Writes not allowed right now.
            return None

class operations_event(osv.osv, ratelimit):
    """Operational events are things that happen while Unifield is running
    that we would like to have recorded so that we can
    investigate/summarize via queries on non-production
    instances. Once written by Unifield in response to something
    happening, they are read-only. They can be inspected using the
    Search view, or exported via SQL to another system for
    processing.
    """

    _name = 'operations.event'
    _rec_name = 'time'
    _order = 'time desc'

    def __init__(self, pool, cr):
        osv.osv.__init__(self, pool, cr)

        self._rl_name = 'events'
        self._rl_max = ratelimit.MAX
        self._rl = self._rl_max

    def create(self, cr, uid, vals, context=None):
        """Override create in order to respect the rate limit."""
        ratelimit.create(self, cr, uid, vals, context=context)

    def _shorten(self, x):
        if not isinstance(x, basestring):
            return x

        if len(x) < 80:
            return x

        if x.startswith("Traceback"):
            lines = x.split("\n")
            return "\n".join(lines[-4:])

        return x[0:80]+"..."

    def _shorten_data(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for ev in self.browse(cr, uid, ids, context=context):
            res[ev.id] = self._shorten(ev.data)
        return res

    _columns = {
        'time': fields.datetime('Time', readonly=True, select=True, required=True, help="When the event happened."),
        'instance': fields.char('Instance', readonly=True, size=64, required=True, help="The originating instance."),
        'remote_id': fields.integer('Remote id', help="Holds the row id of rows imported from a remote instance. Unused except for de-duplicating during event centralization."),
        'kind': fields.char('Kind', readonly=True, size=64, required=True, help="What kind of event it was."),
        'data': fields.text('Data', readonly=True, help="The data associated with the event."),
        'data_short': fields.function(_shorten_data, method=True, type='char'),
    }

    _sql_constraints = [
        ('dedup', 'UNIQUE(instance, remote_id)',
         'Duplicate events from an instance and not allowed.')
    ]

    _defaults = {
        'time': lambda self,cr,uid,c: fields.datetime.now(),
        'instance': lambda self,cr,uid,c: self._get_inst(cr, uid)
    }

    _logger = logging.getLogger('operations.event')

    def _get_inst(self, cr, uid):
        i = self.pool.get('sync.client.entity').get_entity(cr, uid).name;
        if i is None:
            return "unknown"
        return i

    def bang(self, cr, uid, ids=None, context=None):
        raise ValueError("bang!")
        return 1

    def purge(self, cr, uid, keep='30 day'):
        """Called from ir.cron every day to purge events older
        than X days, where X comes from either an argument like
        ['5 day'], or defaults to 30 days.
        """
        self._logger.info("Operations event purge: keep %s" % keep)
        cr.execute("delete from operations_event WHERE time < CURRENT_DATE - INTERVAL %s;", (keep,))
        self._rl = self._rl_max

operations_event()

class operations_count(osv.osv, ratelimit):
    """Operational counts are gathered in memory at runtime
    and then periodically flushed to the database.
    """

    _name = 'operations.count'
    _columns = {
        'time': fields.datetime('Time', readonly=True, select=True, required=True, help="When the measurement was collected."),
        'instance': fields.char('Instance', readonly=True, size=64, required=True, help="The originating instance."),
        'remote_id': fields.integer('Remote id', help="Holds the row id of rows imported from a remote instance. Unused except for de-duplicating during count centralization."),
        'kind': fields.char('Kind', readonly=True, size=64, required=True, help="What kind of count."),
        'count': fields.integer('Count', readonly=True, required=True, help="The count/measurement."),
    }

    _sql_constraints = [
        ('dedup', 'UNIQUE(instance, remote_id)',
         'Duplicate counts from an instance and not allowed.')
    ]

    _logger = logging.getLogger('operations.count')

    def __init__(self, pool, cr):
        osv.osv.__init__(self, pool, cr)
        self._counts = {}
        self.lock = threading.Lock()
        i = pool.get('sync.client.entity').get_entity(cr, 1).name;
        if i is None:
            self._instance = "unknown"
        else:
            self._instance = i
        self.lock = threading.Lock()

        self._rl_name = 'counts'
        self._rl_max = ratelimit.MAX
        self._rl = self._rl_max

        self.histogram = {}
        # Watch OpenERP method calls from 0 to 2 seconds
        self.histogram['netsvc'] = Histogram( buckets=20, range=2, name='netsvc')
        # Watch SQL queries with auto-range
        self.histogram['sql'] = Histogram( buckets=20, name='sql')

    def create(self, cr, uid, vals, context=None):
        """Override create in order to respect the rate limit."""
        ratelimit.create(self, cr, uid, vals, context=context)

    def increment(self, kind, count=1):
        with self.lock:
            self._counts[kind] = self._counts.get(kind, 0) + count

    def write_counts(self, cr, uid):
        # Take a copy of the counts, then reset to zero.
        # Hold the lock for the shortest time possible.
        with self.lock:
            counts = self._counts
            self._counts = {}

        # Write them all out. Take the time one time so that all
        # events will have exactly the same time on them, to better
        # group by time later.
        now = fields.datetime.now()
        for kind in counts:
            self.create(cr, uid, { 'time': now,
                                   'instance': self._instance,
                                   'kind': kind,
                                   'count': counts[kind] })
        rows = len(counts)
        # Write out all the histograms
        for h in self.histogram.values():
            limits = h.limits()
            for i in range(len(h.buckets)):
                kind = "%s:%s" % (h.name, limits[i])
                self.create(cr, uid, { 'time': now,
                                       'instance': self._instance,
                                       'kind': kind,
                                       'count': h.buckets[i] })
                rows += 1
            h.clear()
        self._logger.debug("Operations count write: %d rows" % rows)

    def purge(self, cr, uid, keep='30 day'):
        """Called from ir.cron every day to purge counts older
        than X days, where X comes from either an argument like
        ['5 day'], or defaults to 30 days.
        """
        self._logger.info("Operations count purge: keep %s" % keep)
        cr.execute("delete from operations_count WHERE time < CURRENT_DATE - INTERVAL %s;", (keep,))
        self._rl = self._rl_max

operations_count()
