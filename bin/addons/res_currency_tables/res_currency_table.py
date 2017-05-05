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

import datetime
from osv import fields, osv
from tools.translate import _

class res_currency_table(osv.osv):
    _name = 'res.currency.table'

    _columns = {
        'name': fields.char('Currency table name', size=64, required=True),
        'code': fields.char('Currency table code', size=16, required=True),
        'currency_ids': fields.one2many('res.currency', 'currency_table_id', 'Currencies', domain=[('active','in',['t','f'])]),
        'state': fields.selection([('draft','Draft'),
                                   ('valid','Valid'),
                                   ('closed', 'Closed')], 'State', required=True),
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    def validate(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        # just get one table
        if not isinstance(ids, (int, long)):
            ids = ids[0]
        table = self.browse(cr, uid, ids, context=context)
        for currency in table.currency_ids:
            if currency.rate == 0.0:
                raise osv.except_osv(_('Error'), _('A currency has an invalid rate! Please set a rate before validation.'))
        
        return self.write(cr, uid, ids, {'state': 'valid'}, context=context)

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context={}
        for table in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', table.name),('code', '=ilike', table.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between currency tables!', ['code', 'name']),
    ]
    
res_currency_table()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
    
