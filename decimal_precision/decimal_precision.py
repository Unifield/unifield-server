# -*- encoding: utf-8 -*-
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

from osv import osv, fields
from tools import cache
import pooler

class decimal_precision(osv.osv):
    _name = 'decimal.precision'
    _columns = {
        'name': fields.char('Usage', size=50, select=True, required=True),
        'digits': fields.integer('Digits', required=True),
        'computation': fields.boolean(string='Remove trailing zeros')
    }
    _defaults = {
        'digits': 2,
        'computation': False,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)', """Only one value can be defined for each given usage!"""),
    ]

    @cache(skiparg=3)
    def precision_get(self, cr, uid, application):
        cr.execute('select digits from decimal_precision where name=%s', (application,))
        res = cr.fetchone()
        return res[0] if res else 2
    
    @cache(skiparg=3)
    def computation_get(self, cr, uid, application):
        cr.execute('select computation from decimal_precision where name=%s', (application,))
        res = cr.fetchone()
        return res[0] if res else False
    
    def create(self, cr, uid, vals, context=None):
        '''
        create function updates digits as well
        '''
        res = super(decimal_precision, self).create(cr, uid, vals, context=context)
        self.precision_get.clear_cache(cr.dbname)
        self.computation_get.clear_cache(cr.dbname)
        for obj in self.pool.obj_list():
            for colname, col in self.pool.get(obj)._columns.items():
                if isinstance(col, (fields.float, fields.function)):
                    col.digits_change(cr)
        return res

    def write(self, cr, uid, ids, data, *args, **argv):
        res = super(decimal_precision, self).write(cr, uid, ids, data, *args, **argv)
        self.precision_get.clear_cache(cr.dbname)
        self.computation_get.clear_cache(cr.dbname)
        for obj in self.pool.obj_list():
            for colname, col in self.pool.get(obj)._columns.items():
                if isinstance(col, (fields.float, fields.function)):
                    col.digits_change(cr)
        return res

decimal_precision()

def get_precision(application):
    def change_digit(cr, **kwargs):
        # modify the initial function so we can gather other customized fields
        if kwargs.get('computation', False):
            return pooler.get_pool(cr.dbname).get('decimal.precision').computation_get(cr, 1, application)
        
        res = pooler.get_pool(cr.dbname).get('decimal.precision').precision_get(cr, 1, application)
        return (16, res)
    return change_digit

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
