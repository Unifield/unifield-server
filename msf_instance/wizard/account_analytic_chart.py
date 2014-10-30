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

from osv import osv
from osv import fields

class account_analytic_chart(osv.osv_memory):
    _name = 'account.analytic.chart'
    _inherit = 'account.analytic.chart'

    _columns = {
        'instance_ids': fields.many2many('msf.instance', 'account_chart_instance_rel', 'wizard_id', 'instance_id', 'Instance'),
    }

    def analytic_account_chart_open_window(self, cr, uid, ids, context=None):
        """
        Add instance_ids information to only display analytic journal items linked to the given instance
        """
        result = super(account_analytic_chart, self).analytic_account_chart_open_window(cr, uid, ids, context=context)
        data = self.read(cr, uid, ids, ['instance_ids'], context=context)[0]
        if data['instance_ids']:
            context = eval(result['context'])
            context.update({'instance_ids': data['instance_ids']})
            result['context'] = unicode(context)
        return result

account_analytic_chart()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
