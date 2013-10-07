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

class account_chart_activable(osv.osv_memory):
    _inherit = "account.chart"
    _columns = {
        'show_inactive': fields.boolean('Show inactive accounts'),
        'currency_id': fields.many2one('res.currency', 'Currency'),
    }

    def account_chart_open_window(self, cr, uid, ids, context=None):
        
        result = super(account_chart_activable, self).account_chart_open_window(cr, uid, ids, context=context)
        # add 'active_test' to the result's context; this allows to show or hide inactive items
        data = self.read(cr, uid, ids, [], context=context)[0]
        context = eval(result['context'])
        context['filter_inactive_accounts'] = not data['show_inactive']
        if data['currency_id']:
            context['currency_id'] = data['currency_id']
        result['context'] = unicode(context)
        return result

    _defaults = {
        'show_inactive': False
    }

    def button_export(self, cr, uid, ids, context=None):
        """
        Export chart of account in a XML file
        """
        if not context:
            context = None
        account_ids = []
        for wiz in self.browse(cr, uid, ids):
            args = [('active', '=', True)]
            if wiz.show_inactive == True:
                args += [('active', 'in', (True, False))]
            if wiz.currency_id:
                context.update({'currency_id': wiz.currency_id.id,})
            if wiz.instance_ids:
                context.update({'instance_ids': [x.id for x in wiz.instance_ids],})
            account_ids = self.pool.get('account.account').search(cr, uid, args, context=context)
        datas = {'ids': account_ids, 'context': context} # context permit balance to be processed regarding context's elements
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.chart.export',
            'datas': datas,
        }

account_chart_activable()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
