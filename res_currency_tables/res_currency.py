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

from osv import fields, osv

class res_currency(osv.osv):
    _inherit = 'res.currency'
    _name = 'res.currency'

    _columns = {
        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table', ondelete='cascade'),
        'reference_currency_id': fields.many2one('res.currency', 'Reference Currency', ondelete='cascade'),
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name, currency_table_id)', 'The currency name exists already in the system!')
    ]
    
    def search(self, cr, uid, args=[], offset=0, limit=None, order=None, context={}, count=False):
        return super(res_currency, self).search(cr, uid, args, offset, limit, order, context, count=count)
    
    def compute(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, context=None):
        return super(res_currency, self).compute(cr, uid, from_currency_id, to_currency_id, from_amount, round, context=context)
    
    def compute(self, cr, uid, from_currency_id, to_currency_id, from_amount, round=True, context=None, table_id=None):
        if table_id is None:
            return super(res_currency, self).compute(cr, uid, from_currency_id, to_currency_id, from_amount, round, context=context)
        else:
            # A currency table is set, retrieve the correct currency ids
            new_from_currency_id = self.search(cr, uid, [('currency_table_id', '=', table_id),
                                                         ('reference_currency_id', '=', from_currency_id)], context=context)
            new_to_currency_id = self.search(cr, uid, [('currency_table_id', '=', table_id),
                                                       ('reference_currency_id', '=', to_currency_id)], context=context)
            return super(res_currency, self).compute(cr, uid, new_from_currency_id, new_to_currency_id, from_amount, round, context=context)
            
res_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
