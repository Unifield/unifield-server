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

def drop_view_if_exists(cr, viewname):
    cr.execute("select count(1) from pg_class where relkind=%s and relname=%s", ('v', viewname,))
    if cr.fetchone()[0]:
        cr.execute("DROP view %s" % (viewname,))  # not_a_user_entry
        cr.commit()

SQL_VERSION = False

def sql_version(cr):
    global SQL_VERSION

    if not SQL_VERSION:
        cr.execute('SHOW SERVER_VERSION')
        result = cr.fetchone()
        SQL_VERSION = result and result[0] or False

    return SQL_VERSION

def is_pg14(cr):
    version = sql_version(cr)
    if version:
        return version.startswith('14')

    return False
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
