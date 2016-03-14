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
from tools.translate import _

class activate_currencies(osv.osv_memory):
    _name = "activate.currencies"
    
    _columns = {
        'active_status': fields.boolean('Set selected currencies as active')
    }
    
    _defaults = {
        'active_status': True
    }
    
    def change_currency_status(self, cr, uid, ids, context=None):
        
        currency_obj = self.pool.get('res.currency')
        data = self.read(cr, uid, ids, [], context=context)[0]
        for currency_id in context['active_ids']:
            currency_obj = self.pool.get('res.currency').browse(cr, uid, currency_id)
            # Don't activate currencies with no rates.
            if not currency_obj.rate_ids and data['active_status']:
                raise osv.except_osv(_('Error'), _('No rate is set for currency %s !') % (currency_obj.name,))
                break
            else:
                self.pool.get('res.currency').write(cr, uid, currency_id, {'active': data['active_status']}, context=context)
        return {'type': 'ir.actions.act_window_close'}
    
activate_currencies()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
