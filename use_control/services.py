import pooler
import time
import netsvc
import os
import os.path
import tools

##############################################################################
# Service to record use of the database
##############################################################################

HOUR_MINI = 1.0

def check(chk_fnct):
    data = {}
    def check_one(db, uid, passwd):
        data.setdefault(db, {})
        if (uid not in data) or (data[uid]<time.time()):
            data[uid] = time.time() + 3600 * HOUR_MINI
            cr = pooler.get_db(db).cursor()
            try:
                cr.execute('SELECT name FROM use_control_db_block')
                msg = cr.fetchone()
                if msg:
                    raise Exception(msg[0])
                try:
                    cr.execute('insert into use_control_time (user_id, date, duration) values (%s,%s,%s)', 
                                (int(uid), time.strftime('%Y-%m-%d %H:%M:%S'), HOUR_MINI))
                    cr.commit()
                except:
                    pass
            finally:
                cr.close()
        return chk_fnct(db, uid, passwd)
    return check_one

# May be it's better using inheritancy and resubscribing the service
# Override the check method to store use of the database
from service import security
security.check = check(security.check)

##############################################################################
# Service to request feedback on a database usage
##############################################################################

class use_control_service(netsvc.Service):
    def __init__(self, name="use_control"):
        netsvc.Service.__init__(self, name)
        self.joinGroup("web-services")
        self.exportMethod(self.data_get)
        self.exportMethod(self.block)
        self.exportMethod(self.unblock)

    def _get_size(self, cr, dbname):
        """Return the size of the system in Mb."""
        cr.execute('select pg_database_size(%s)', (dbname,))
        db_size = cr.fetchone()[0]
        dir_size = 0.0
        filestore = os.path.join(tools.config['root_path'], 'filestore', dbname)
        if os.path.isdir(filestore):
            for (path, dirs, files) in os.walk(filestore):
                for file in files:
                    filename = os.path.join(path, file)
                    dir_size += os.path.getsize(filename)
        return float((dir_size + db_size) / (1024*1024) + 1.0) / 1024.0

    def data_get(self, password, db):
        security.check_super(password)
        cr = pooler.get_db(db).cursor()
        cr.execute('''select
                to_char(t.date, 'YYYY-MM-DD') as date,
                u.name as username,
                u.login as login,
                sum(t.duration) as hours
            from
                use_control_time t
            left join
                res_users u on (u.id=t.user_id)
            where (not uploaded) or (uploaded is null)
            group by
                to_char(t.date, 'YYYY-MM-DD'),
                u.name,
                u.login
           ''')
        data = cr.fetchall()
        cr.execute('update use_control_time t set uploaded=True where (not uploaded) or (uploaded is null)')
        cr.execute('select name from ir_module_module where state=%s', ('installed',))
        modules = map(lambda x: x[0], cr.fetchall())

        hours = reduce(lambda x, y: x+y[3], data, 0.0)

        cr.execute('select count(id) from res_users where active')
        users = cr.fetchone()[0]
        cr.execute('select max(date) from use_control_time')
        maxdate = cr.fetchone()[0]
        result = {
            'details': data,
            'modules': modules,
            'latest_connection': maxdate,
            'users_number': users,
            'space': self._get_size(cr, db),
            'hours': hours,
        }
        cr.commit()
        cr.close()
        return result

    def block(self, password, dbname, message):
        security.check_super(password)
        db, pool = pooler.get_db_and_pool(dbname)
        cr = db.cursor()
        try:
            obj = pool.get('use.control.db.block')
            obj.create(cr, 1, {'name': message})
        finally:
            cr.close()
        return True

    def unblock(self, password, dbname):
        security.check_super(password)
        db, pool = pooler.get_db_and_pool(dbname)
        cr = db.cursor()
        try:
            obj = pool.get('use.control.db.block')
            obj.unlink(cr, 1, obj.search(cr, 1, []))
        finally:
            cr.close()
        return True
        

use_control_service()


