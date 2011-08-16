# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

import time
from osv import fields, osv
from tools.translate import _

class res_currency_functional(osv.osv):
    _inherit = 'res.currency'

    def _verify_rate(self, cr, uid, ids, context={}):
        """
        Verify that a currency set to active has a non-zero rate.
        """
        for currency in self.browse(cr, uid, ids, context=context):
            if not currency.rate_ids and currency.active:
                return False
        return True

    def _check_name_exists(self, cr, uid, name, ids = None, context={}):
        """
        Check if the given name exists already in the currency list with regard of the given ids:
        - If no "id" is given --> create mode: if there exists a record with the same name: return True, otherwise return False
        - If id is given --> edit mode: only return True if the given name does NOT belong to the editing object
        """
        
        # use this direct "select" to avoid executing "read" methods
        cr.execute("SELECT id, name FROM res_currency WHERE name = '" + name + "' LIMIT 1") 
        if cr.rowcount:
            id_db, text = cr.fetchall()[0]
            if ids and ids[0] == id_db:
                return False
            return True

        return False  

    def write(self, cr, uid, ids, values, context={}):
        # check if the given new_name exists already in other currency in the system
        new_name = values.get('name', False)
        if new_name:
            if self._check_name_exists(cr, uid, new_name, ids, context):
                raise osv.except_osv(_('Error !'), _('The currency name exists already in the system!'))
        
        return super(osv.osv, self).write(cr, uid, ids, values, context=context)

    def create(self, cr, uid, vals, context={}):
        # check if the given new_name exists already in the system
        new_name = vals.get('name', False)
        if new_name:
            if self._check_name_exists(cr, uid, new_name, [],context):
                raise osv.except_osv(_('Error !'), _('The currency name exists already in the system!'))
            
        return super(res_currency_functional, self).create(cr, uid, vals, context=context)
    
    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        res=super(res_currency_functional, self).read(cr, uid, ids, fields, context, load)
        
        if context is None:
            context = {}
            
        if 'date' in context:
            date = context['date']
        else:
            date = time.strftime('%Y-%m-%d')
        date = date or time.strftime('%Y-%m-%d')
        
        # The code below calculates the date of the valid rate of each currency and shows it in the list view
        for r in res:
            if r.__contains__('rate'):
                rate=r['rate']
                currency_id = r['id']
                if rate and currency_id:
                    currency_rate_obj=  self.pool.get('res.currency.rate')
                    rate_ids = currency_rate_obj.search(cr, uid, [('currency_id','=', currency_id), ('rate','=', rate)])                    
                    if rate_ids:
                        currency_date = currency_rate_obj.browse(cr,uid,rate_ids[0],['name'])['name']
                        r['date'] = currency_date
                        
        return res
    
    def _current_rate(self, cr, uid, ids, name, arg, context=None):
        return super(res_currency_functional, self)._current_rate(cr, uid, ids, name, arg, context)
    
    _columns = {
        'currency_name': fields.char('Currency Name', size=64, required=True),
        'rate': fields.function(_current_rate, method=True, string='Current Rate', digits=(12,6),
            help='The rate of the currency to the functional currency'),
        'date': fields.date('Validity From'),
    }
    
    _constraints = [
        (_verify_rate, "No rate is set. Please set one before activating the currency. ", ['active', 'rate_ids']),
    ]

    _defaults = {
        'active': lambda *a: 0,
        'accuracy': 4, 
    }

res_currency_functional()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
