# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class account_chart_activable(osv.osv_memory):
    _inherit = "account.chart"
    _columns = {
        'show_inactive': fields.boolean('Show inactive accounts'),
    }

    def account_chart_open_window(self, cr, uid, ids, context=None):
            
        result = super(account_chart_activable, self).account_chart_open_window(cr, uid, ids, context=context)
        # add 'active_test' to the result's context; this allows to show or hide inactive items
        data = self.read(cr, uid, ids, [], context=context)[0]
        result['context'] = str({'fiscalyear': data['fiscalyear'], 'periods': result['periods'], \
                                    'state': data['target_move'], 'active_test': not data['show_inactive']})
        
        return result


    _defaults = {
        'show_inactive': False
    }

account_chart_activable()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
