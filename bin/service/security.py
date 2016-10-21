# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
import threading
import updater
import re
from passlib.hash import bcrypt
from tools.translate import _
from osv import osv
PASSWORD_MIN_LENGHT = 6

# When rejecting a password, hide the traceback
class ExceptionNoTb(Exception):
    def __init__(self, msg):
        super(ExceptionNoTb, self).__init__(msg)
        self.traceback = ('','','')

def number_update_modules(db):
    cr = pooler.get_db_only(db).cursor()
    n = _get_number_modules(cr)
    cr.close()
    return n

def _get_number_modules(cr, testlogin=False):
    ready = True
    if testlogin and cr.dbname in pooler.pool_dic:
        if pooler.pool_dic[cr.dbname]._ready:
            return False
        ready = False
    cr.execute("select count(id) from ir_module_module where state in ('to install', 'to upgrade')")
    n = cr.fetchone()
    if n and n[0]:
        return n[0]
    if not ready:
        # when loading the trans. modules are installed but db is not ready
        return True
    return False

def change_password(db_name, login, password, new_password, confirm_password):
    '''
    Call the res.user change_password method
    '''
    db, pool = pooler.get_db_and_pool(db_name)
    cr = db.cursor()
    user_obj = pool.get('res.users')
    return user_obj.change_password(db_name, login, password, new_password,
            confirm_password)

def login(db_name, login, password):
    db, pool = pooler.get_db_and_pool(db_name)
    cr = db.cursor()
    nb = _get_number_modules(cr, testlogin=True)
    patch_failed = [0]
    cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname='patch_scripts'")
    if cr.rowcount:
        cr.execute("SELECT count(id) FROM patch_scripts WHERE run = \'f\'")
        patch_failed = cr.fetchone()
    to_update = False
    if not nb:
        to_update = updater.test_do_upgrade(cr)

    # check if the user have to change his password
    cr.execute("""SELECT force_password_change
    FROM res_users
    WHERE login='%s'""" % (login))
    force_password = [x[0] for x in cr.fetchall()]
    if any(force_password):
        raise Exception("ForcePasswordChange: The admin requests your password change ...")

    cr.close()
    if nb or to_update:
        s = threading.Thread(target=pooler.get_pool, args=(db_name,),
                kwargs={'threaded': True})
        s.start()
        raise Exception("ServerUpdate: Server is updating modules ...")

    user_obj = pool.get('res.users')
    user_res = user_obj.login(db_name, login, password)

    if user_res != 1 and patch_failed[0]:
        raise Exception("PatchFailed: A script during upgrade has failed. Login is forbidden. Please contact your administrator")

    return user_res

def check_password_validity(self, cr, uid, old_password, new_password, confirm_password, login):
    '''
    Check password respect some conditions
    Raise is any of the condition is not respected

    :param self: the caller of this method. It is needed for _get_lang to be
    able to know the language of the requested user
    :param cr: database cursor
    :param uid: the user id of the password to check
    :param old_password: the previous password
    :param new_password: the new password to setup
    :param confirm_password: the confirmation of the new password
    :param login: the login that request the password check
    :return: True if the password check pass
    :rtype: boolean
    :raise osv.except_osv: if the password is not ok
    '''
    # check it contains at least one digit
    if not re.search(r'\d', new_password):
        message = _('The new password is not strong enough. '\
            'Password must contain at least one digit.')
        raise osv.except_osv(_('Operation Canceled'), message)

    # check new_password lenght
    if len(new_password) < PASSWORD_MIN_LENGHT:
        message = _('The new password is not strong enough. '\
            'Password must be at least %s characters long.' % PASSWORD_MIN_LENGHT)
        raise osv.except_osv(_('Operation Canceled'), message)

    # check login != new_password:
    if new_password == login:
        message = _('The new password cannot be equal to the login.')
        raise osv.except_osv(_('Operation Canceled'), message)

    # check confirm_password == new_password:
    if new_password != confirm_password:
        message = _('The new password does not match the confirm password.')
        raise osv.except_osv(_('Operation Canceled'), message)

    # check new_password != old_password
    if new_password == old_password:
        message = _('The new password must be different from the actual one.')
        raise osv.except_osv(_('Operation Canceled'), message)
    return True

def check_password(password, hashed_password):
    '''
    Check that the password match the hashed_password

    :param password: a string containing the password to check
    :param hashed_password: a string containing the hash to check against, such
    as returned by encrypt()
    :return: True if the password match
    :rtype: boolean
    :raise ExceptionNoTb: if password don't match
    '''
    hashed_password = tools.ustr(hashed_password)
    password = tools.ustr(password)

    # check the password is a bcrypt encrypted one
    if bcrypt.identify(hashed_password) and \
            bcrypt.verify(password, hashed_password):
        return True
    elif password == hashed_password:
        # this is a not encrypted password (we want to keep compatibility with
        # old way password
        return True
    else:
        raise ExceptionNoTb('AccessDenied: Invalid super administrator password.')

def check_super_password_validity(password):
    check_password_validity(None, None, 1, None, password, password, 'admin')
    return True

def check_super(passwd):
    return check_password(passwd, tools.config['admin_passwd'])

def check_super_dropdb(passwd):
    return check_password(passwd, tools.config['admin_dropdb_passwd'])

def check_super_bkpdb(passwd):
    return check_password(passwd, tools.config['admin_bkpdb_passwd'])

def check_super_restoredb(passwd):
    return check_password(passwd, tools.config['admin_restoredb_passwd'])

def check(db, uid, passwd):
    pool = pooler.get_pool(db)
    user_obj = pool.get('res.users')
    return user_obj.check(db, uid, passwd)
