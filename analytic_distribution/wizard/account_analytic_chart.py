# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class account_analytic_chart(osv.osv_memory):
    _inherit = "account.analytic.chart"
    _columns = {
        'show_inactive': fields.boolean('Show inactive accounts'),
        'fiscalyear': fields.many2one('account.fiscalyear', 'Fiscal year', help = 'Keep empty for all open fiscal years'),
    }

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear_id=False, context=None):
        res = {}
        res['value'] = {}
        if fiscalyear_id:
            start_period = end_period = False
            cr.execute('''
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                               WHERE f.id = %s
                               ORDER BY p.date_start ASC
                               LIMIT 1) AS period_start
                UNION
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                               WHERE f.id = %s
                               AND p.date_start < NOW()
                               ORDER BY p.date_stop DESC
                               LIMIT 1) AS period_stop''', (fiscalyear_id, fiscalyear_id))
            periods =  [i[0] for i in cr.fetchall()]
            if periods and len(periods) > 1:
                p1 = self.pool.get('account.period').browse(cr, uid, [periods[0]])[0]
                start_period = p1.date_start
                p2 = self.pool.get('account.period').browse(cr, uid, [periods[1]])[0]
                end_period = p2.date_stop
            res['value'] = {'from_date': start_period, 'to_date': end_period}
        return res

    def analytic_account_chart_open_window(self, cr, uid, ids, context=None):
        result = super(account_analytic_chart, self).analytic_account_chart_open_window(cr, uid, ids, context=context)
        # add 'active_test' to the result's context; this allows to show or hide inactive items
        data = self.read(cr, uid, ids, [], context=context)[0]
        context = eval(result['context'])
        context['filter_inactive'] = not data['show_inactive']
        if data['currency_id']:
            context['currency_id'] = data['currency_id']
        if data['fiscalyear']:
            result['name'] += ':' + self.pool.get('account.fiscalyear').read(cr, uid, [data['fiscalyear']], context=context)[0]['code']
        # Display FP on result
        context['display_fp'] = True
        result['context'] = unicode(context)
        return result

    def button_export(self, cr, uid, ids, context=None):
        """
        Export chart of analytic account in a XML file
        """
        if not context:
            context = None
        account_ids = []
        for wiz in self.browse(cr, uid, ids):
            args = [('filter_active', '=', True)]
            if wiz.show_inactive == True:
                args += [('filter_active', 'in', (True, False))]
            if wiz.currency_id:
                context.update({'currency_id': wiz.currency_id.id,})
            if wiz.instance_ids:
                context.update({'instance_ids': [x.id for x in wiz.instance_ids],})
            account_ids = self.pool.get('account.analytic.account').search(cr, uid, args, context=context)
        datas = {'ids': account_ids, 'context': context} # context permit balance to be processed regarding context's elements
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.analytic.chart.export',
            'datas': datas,
        }

account_analytic_chart()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
