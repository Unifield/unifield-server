# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010-2011 OpenERP s.a. (<http://openerp.com>).
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

__all__ = ['db_connect', 'close_db']

from threading import current_thread
import logging
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE
from psycopg2.pool import PoolError

import psycopg2.extensions
import warnings
import pooler
from tools import cache
from tools import misc
import time

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

types_mapping = {
    'date': (1082,),
    'time': (1083,),
    'datetime': (1114,),
}

def unbuffer(symb, cr):
    if symb is None: return None
    return str(symb)

def undecimalize(symb, cr):
    if symb is None: return None
    return float(symb)

for name, typeoid in list(types_mapping.items()):
    psycopg2.extensions.register_type(psycopg2.extensions.new_type(typeoid, name, lambda x, cr: x))
psycopg2.extensions.register_type(psycopg2.extensions.new_type((700, 701, 1700,), 'float', undecimalize))


import tools
from tools.func import wraps, frame_codeinfo
from netsvc import Agent
from datetime import datetime as mdt
from datetime import timedelta
import threading
from inspect import currentframe

import re
re_from = re.compile('.* from "?([a-zA-Z_0-9]+)"? .*$');
re_into = re.compile('.* into "?([a-zA-Z_0-9]+)"? .*$');

sql_counter = 0

class Cursor(object):
    IN_MAX = 1000 # decent limit on size of IN queries - guideline = Oracle limit
    __logger = logging.getLogger('db.cursor')

    def check(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if self.__closed:
                raise psycopg2.OperationalError('Unable to use the cursor after having closed it')
            return f(self, *args, **kwargs)
        return wrapper

    def __init__(self, pool, dbname, serialized=False):
        self.sql_from_log = {}
        self.sql_into_log = {}

        # default log level determined at cursor creation, could be
        # overridden later for debugging purposes
        self.sql_log = self.__logger.isEnabledFor(logging.DEBUG_SQL)

        self.sql_log_count = 0
        self.__closed = True    # avoid the call of close() (by __del__) if an exception
        # is raised by any of the following initialisations
        self._pool = pool
        self.dbname = dbname
        self._serialized = serialized
        self._cnx = pool.borrow(dsn(dbname))
        self._oc = None
        p = pooler.pool_dic.get(self.dbname, None)
        if p is not None:
            self._oc = p.get('operations.count')
            self._oe = p.get('operations.event')
        self._obj = self._cnx.cursor()
        self.__closed = False   # real initialisation value
        self.autocommit(False)
        if self.sql_log:
            self.__caller = frame_codeinfo(currentframe(),2)
        else:
            self.__caller = False

    def __del__(self):
        if not self.__closed:
            # Oops. 'self' has not been closed explicitly.
            # The cursor will be deleted by the garbage collector,
            # but the database connection is not put back into the connection
            # pool, preventing some operation on the database like dropping it.
            # This can also lead to a server overload.
            msg = "Cursor not closed explicitly\n"
            if self.__caller:
                msg += "Cursor was created at %s:%s" % self.__caller
            else:
                msg += "Please enable sql debugging to trace the caller."
            self.__logger.warn(msg)
            self._close(True)

    def recursiveCastUid(self, params):
        if params and isinstance(params, (tuple, list)):
            param_type = isinstance(params, tuple) and 'tuple' or 'list'
            new_params = []
            for param in params:
                if param and isinstance(param, (tuple, list)):
                    new_params.append(self.recursiveCastUid(param))
                else:
                    if hasattr(param, 'realUid'):
                        new_params.append(int(param))
                    else:
                        new_params.append(param)
            return param_type == 'tuple' and tuple(new_params) or new_params
        elif hasattr(params, 'realUid'):
            return int(params)
        else:
            return params

    @check
    def execute(self, query, params=None, log_exceptions=True):
        if '%d' in query or '%f' in query:
            self.__logger.warn(query)
            self.__logger.warn("SQL queries cannot contain %d or %f anymore. "
                               "Use only %s")

        #self.sql_log = True
        if self.sql_log:
            now = mdt.now()

        try:
            params = params or None
            params = self.recursiveCastUid(params)
            before = time.time()
            res = self._obj.execute(query, params)
            after = time.time()
            if self._oc:
                delta = after-before
                self._oc.histogram['sql'].add(delta)
                if self._oe and delta > self._oe.SLOW_QUERY:
                    self._oe.remember_slow_query(query, delta)
        except psycopg2.ProgrammingError as pe:
            if log_exceptions:
                self.__logger.error("Programming error: %s, in query %s", pe, query)
            raise
        except psycopg2.IntegrityError as ie:
            if log_exceptions:
                osv_pool = pooler.pool_dic.get(self.dbname)
                if osv_pool:
                    for key in list(osv_pool._sql_error.keys()):
                        if key in ie.pgerror:
                            self.__logger.warn("Normal Constraint Error: %s : %s", self._obj.query or query, tools.misc.ustr(ie.pgerror))
                            #US-88: if error occurred for account analytic then just clear the cache
                            if 'account_analytic_account_parent_id_fkey' in ie.pgerror:
                                cache.clean_caches_for_db(self.dbname)
                            raise
                self.__logger.exception("Unknown Constraint Error: %s %s", self._obj.query or query, misc.get_stack())

            #US-88: if error occurred for account analytic then just clear the cache
            if 'account_analytic_account_parent_id_fkey' in ie.pgerror:
                cache.clean_caches_for_db(self.dbname)
            raise
        except Exception:
            if log_exceptions:
                query = self._obj.query or query
                if len(query) > 500000:
                    query = ''.join((query[:500000], '... the query has been truncated because it is too big (%s characters)' % len(query)))
                self.__logger.exception("bad query: %s", query)
            raise

        if self.sql_log:
            delay = mdt.now() - now
            delay = delay.seconds * 1E6 + delay.microseconds
            #if len(self._obj.query) > 500:
            #    self.__logger.warn(misc.get_stack())
            self.__logger.warn("query: %s %s", str(self._obj.query, 'utf8').replace('\n', ''), delay)
        return res


    def split_for_in_conditions(self, ids, max_split=None):
        """Split a list of identifiers into one or more smaller tuples
           safe for IN conditions, after uniquifying them."""
        if max_split is None:
            max_split = self.IN_MAX
        return tools.misc.split_every(max_split, list(dict.fromkeys(ids)))

    def print_log(self):
        global sql_counter
        sql_counter += self.sql_log_count
        if not self.sql_log:
            return
        def process(type):
            sqllogs = {'from':self.sql_from_log, 'into':self.sql_into_log}
            sum = 0
            if sqllogs[type]:
                sqllogitems = list(sqllogs[type].items())
                sqllogitems.sort(key=lambda k: k[1][1])
                self.__logger.log(logging.DEBUG_SQL, "SQL LOG %s:", type)
                sqllogitems.sort(key=lambda x: x[1][0])
                for r in sqllogitems:
                    delay = timedelta(microseconds=r[1][1])
                    self.__logger.log(logging.DEBUG_SQL, "table: %s: %s/%s",
                                      r[0], delay, r[1][0])
                    sum+= r[1][1]
                sqllogs[type].clear()
            sum = timedelta(microseconds=sum)
            self.__logger.log(logging.DEBUG_SQL, "SUM %s:%s/%d [%d]",
                              type, sum, self.sql_log_count, sql_counter)
            sqllogs[type].clear()
        process('from')
        process('into')
        self.sql_log_count = 0
        self.sql_log = False

    @check
    def close(self, drop=False):
        return self._close(False, drop=drop)

    def _close(self, leak=False, drop=False):
        if not self._obj:
            return

        self.print_log()

        if not self._serialized:
            self.rollback() # Ensure we close the current transaction.

        self._obj.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self._obj
        self.__closed = True

        if leak:
            self._cnx.leaked = True
        else:
            keep_in_pool = self.dbname not in ('template1', 'template0', 'postgres')
            self._pool.give_back(self._cnx, keep_in_pool=keep_in_pool and not drop)

    @check
    def autocommit(self, on):
        offlevel = [ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE][bool(self._serialized)]
        self._cnx.set_isolation_level([offlevel, ISOLATION_LEVEL_AUTOCOMMIT][bool(on)])

    @check
    def commit(self):
        return self._cnx.commit()

    @check
    def rollback(self):
        return self._cnx.rollback()

    @check
    def __getattr__(self, name):
        return getattr(self._obj, name)

    @check
    def table_exists(self, table):
        self.execute("SELECT relname FROM pg_class WHERE relkind in ('r', 'v') AND relname=%s", (table,))
        return self.rowcount

    @check
    def column_exists(self, table, column):
        self.execute("""SELECT c.relname
            FROM pg_class c, pg_attribute a
            WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
        """, (table, column))
        return self.rowcount

    @check
    def get_referenced(self, table, column='id'):
        self.execute("""
            SELECT tc.table_name, kcu.column_name, ref.delete_rule
            FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
                JOIN information_schema.referential_constraints AS ref ON ref.constraint_name = tc.constraint_name
            WHERE
                tc.constraint_type = 'FOREIGN KEY' AND
                ccu.table_name=%s AND
                ccu.column_name=%s
        """, (table, column))
        return self.fetchall()

    @check
    def constraint_exists(self, table, constraint):
        self.execute("SELECT conname FROM pg_constraint WHERE conname = %s", (constraint, ))
        return self.fetchone()

    @check
    def drop_constraint_if_exists(self, table, constraint):
        if self.constraint_exists(table, constraint):
            self.execute('ALTER table '+table+' DROP CONSTRAINT "%s"' % (constraint,))

    @check
    def drop_index_if_exists(self, table, indexname):
        if self.index_exists(table, indexname):
            self.execute('DROP INDEX "%s"' % (indexname,))

    @check
    def index_exists(self, table, indexname):
        self.execute("SELECT indexname FROM pg_indexes WHERE indexname = %s and tablename = %s", (indexname, table))
        return self.fetchone()


    @check
    def sql_user_exists(self, username):
        self.execute("SELECT rolname FROM pg_roles WHERE rolname=%s", (username, ))
        return self.fetchone()

    def __build_dict(self, row):
        return {d.name: row[i] for i, d in enumerate(self._obj.description)}

    def dictfetchall(self):
        return [self.__build_dict(row) for row in self._obj.fetchall()]

    def dictfetchmany(self, num):
        return [self.__build_dict(row) for row in self._obj.fetchmany(num)]

    def dictfetchone(self):
        row = self._obj.fetchone()
        return row and self.__build_dict(row)


class PsycoConnection(psycopg2.extensions.connection):
    pass

class ConnectionPool(object):

    __logger = logging.getLogger('db.connection_pool')

    def locked(fun):
        @wraps(fun)
        def _locked(self, *args, **kwargs):
            self._lock.acquire()
            try:
                return fun(self, *args, **kwargs)
            finally:
                self._lock.release()
        return _locked


    def __init__(self, maxconn=64):
        self._connections = []
        self._maxconn = max(maxconn, 1)
        self._lock = threading.Lock()

    def __repr__(self):
        used = len([1 for c, u, t in self._connections[:] if u])
        count = len(self._connections)
        return "ConnectionPool(used=%d/count=%d/max=%d)" % (used, count, self._maxconn)

    def _debug(self, msg, *args):
        self.__logger.log(logging.DEBUG_SQL, ('%r ' + msg), self, *args)

    @locked
    def borrow(self, dsn):
        self._debug('Borrow connection to %r', dsn)

        # free leaked connections
        for i, (cnx, _, t) in tools.reverse_enumerate(self._connections):
            if getattr(cnx, 'leaked', False):
                delattr(cnx, 'leaked')
                self._connections.pop(i)
                self._connections.append((cnx, False, t))
                self.__logger.warn('%r: Free leaked connection to %r', self, cnx.dsn)

        for i, (cnx, used, t) in enumerate(self._connections):
            if not used and dsn_are_equals(cnx.dsn, dsn):
                self._connections.pop(i)
                if time.time() - t > 3600:
                    cnx.close()
                    try:
                        cnx = psycopg2.connect(dsn=dsn, connection_factory=PsycoConnection)
                        t = time.time()
                    except psycopg2.Error:
                        self.__logger.exception('Connection to the database failed')
                        raise
                self._connections.append((cnx, True, t))
                self._debug('Existing connection found at index %d', i)

                return cnx

        if len(self._connections) >= self._maxconn:
            # try to remove the oldest connection not used
            for i, (cnx, used, t) in enumerate(self._connections):
                if not used:
                    self._connections.pop(i)
                    if not cnx.closed:
                        cnx.close()
                    self._debug('Removing old connection at index %d: %r', i, cnx.dsn)
                    break
            else:
                # note: this code is called only if the for loop has completed (no break)
                raise PoolError('The Connection Pool Is Full')

        try:
            result = psycopg2.connect(dsn=dsn, connection_factory=PsycoConnection)
        except psycopg2.Error:
            log = logging.getLogger()
            if len(log.handlers) > 1:
                log.removeHandler(log.handlers[1])
            self.__logger.exception('Connection to the database failed')
            raise
        self._connections.append((result, True, time.time()))
        self._debug('Create new connection')
        return result

    @locked
    def give_back(self, connection, keep_in_pool=True):
        self._debug('Give back connection to %r', connection.dsn)
        for i, (cnx, used, t) in enumerate(self._connections):
            if cnx is connection:
                self._connections.pop(i)
                if keep_in_pool:
                    self._connections.append((cnx, False, t))
                    self._debug('Put connection to %r in pool', cnx.dsn)
                else:
                    self._debug('Forgot connection to %r', cnx.dsn)
                    cnx.close()
                break
        else:
            raise PoolError('This connection does not below to the pool')

    @locked
    def close_all(self, dsn):
        self.__logger.info('%r: Close all connections', self)
        for i, (cnx, used, t) in tools.reverse_enumerate(self._connections):
            if dsn_are_equals(cnx.dsn, dsn):
                cnx.close()
                self._connections.pop(i)


class Connection(object):
    __logger = logging.getLogger('db.connection')

    def __init__(self, pool, dbname):
        self.dbname = dbname
        self._pool = pool

    def cursor(self, serialized=False):
        cursor_type = serialized and 'serialized ' or ''
        self.__logger.log(logging.DEBUG_SQL, 'create %scursor to %r', cursor_type, self.dbname)
        return Cursor(self._pool, self.dbname, serialized=serialized)

    def serialized_cursor(self):
        return self.cursor(True)

    def __bool__(self):
        """Check if connection is possible"""
        try:
            warnings.warn("You use an expensive function to test a connection.",
                          DeprecationWarning, stacklevel=1)
            cr = self.cursor()
            cr.close()
            return True
        except Exception:
            return False


_dsn = ''
for p in ('host', 'port', 'user', 'password'):
    cfg = tools.config['db_' + p]
    if cfg:
        _dsn += '%s=%s ' % (p, cfg)

def dsn(db_name):
    return '%sdbname=%s' % (_dsn, db_name)

def dsn_are_equals(first, second):
    def key(dsn):
        k = dict(x.split('=', 1) for x in dsn.strip().split())
        k.pop('password', None) # password is not relevant
        return k
    return key(first) == key(second)


_Pool = ConnectionPool(int(tools.config['db_maxconn']))

def db_connect(db_name):
    if db_name not in ('template1', 'template0', 'postgres'):
        current_thread().dbname = db_name
    return Connection(_Pool, db_name)

def close_db(db_name):
    _Pool.close_all(dsn(db_name))
    Agent.cancel(db_name)
    tools.cache.clean_caches_for_db(db_name)
    ct = current_thread()
    if hasattr(ct, 'dbname'):
        delattr(ct, 'dbname')


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

