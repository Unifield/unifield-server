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

import updater
pool_dic = {}


def get_db_and_pool(db_name, force_demo=False, status=None,
                    update_module=False, pooljobs=True, threaded=False, upgrade_modules=True, if_open=False):
    '''
    Return the db and pool.

    :param db_name: database name
    :param force_demo: load demo data
    :param status: status dictionary for keeping track of progress
    :param update_module: update the list of available modules
    :pooljobs: restart the cron job
    :upgrade_modules: start the modules upgrade process ('-u base') if needed
    :rtype: list of two object: (dabase, pool)

    '''
    if not status:
        status={}

    db = get_db_only(db_name)

    if db_name in pool_dic:
        pool = pool_dic[db_name]
    else:
        # If they only wanted open ones, do not continue
        if if_open:
            return db, None

        import addons
        from osv import osv
        pool = osv.osv_pool()
        pool_dic[db_name] = pool

        try:
            addons.load_modules(db, force_demo, status, update_module)
        except Exception:
            del pool_dic[db_name]
            raise

        from tools.config import config
        if config.get('save_db_name_in_config') == 'Y':
            try:
                config.add_db_name(db_name)
            except Exception:
                import logging
                logging.getLogger('server').exception('Add db_name inf config, error %s')

        cr = db.cursor()
        try:
            pool.init_set(cr, False)
            pool.get('ir.actions.report.xml').register_all(cr)
            if upgrade_modules:
                if not updater.do_upgrade(cr, pool):
                    pool_dic.pop(db_name)
                    # please do not change "updater.py" in the message, or change unifield-web/addons/openerp/utils/rpc.py accordingly
                    raise Exception("updater.py told us that OpenERP version doesn't match database version!")

            oe = pool.get('operations.event')
            if oe is not None:
                oe.create(cr, 1, { 'kind': 'connect' })

            cr.commit()
        finally:
            if threaded:
                cr.close(True)
            else:
                cr.close()

        if pooljobs:
            pool.get('ir.cron').restart(db.dbname)
    return db, pool


def restart_pool(db_name, force_demo=False, status=None, update_module=False):
    if db_name in pool_dic:
        del pool_dic[db_name]
    return get_db_and_pool(db_name, force_demo, status, update_module=update_module)


def get_db_only(db_name):
    # ATTENTION:
    # do not put this import outside this function
    # sql_db must not be loaded before the logger is initialized.
    # sql_db import psycopg2.tool which create a default logger if there is not.
    # this resulting of having the logs outputed twice...
    import sql_db
    db = sql_db.db_connect(db_name)
    return db


def get_db(db_name):
    return get_db_and_pool(db_name)[0]


def get_pool(db_name, force_demo=False, status=None, update_module=False,
             threaded=False, upgrade_modules=True):
    pool = get_db_and_pool(db_name, force_demo, status, update_module,
                           threaded=threaded, upgrade_modules=upgrade_modules)[1]
    return pool

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
