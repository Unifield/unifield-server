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

from report import report_sxw
import locale
import pooler
import time

class funding(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(funding, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'locale': locale,
            'getDest': self.getDestinations,
            'getBoolDest': self.getBoolDest,
            'today': self.today,
        })

    def today(self):
        return time.strftime('%Y-%m-%d',time.localtime())

    def getDestinations(self):
        """
        Fetch destination analytic account:
          * ID
          * code
        Then sort by code
        """
        res = [('Code', False), ('Name', False)] # We need the 2 first column header name
        pool = pooler.get_pool(self.cr.dbname)
        destination_ids = pool.get('account.analytic.account').search(self.cr, self.uid, [('category', '=', 'DEST'), ('type', '!=', 'view')], order='id')
        data = pool.get('account.analytic.account').read(self.cr, self.uid, destination_ids, ['code'])
        res += [(x.get('code'), x.get('id')) for x in data]
        return res

    def getBoolDest(self, line, o):
        pool = pooler.get_pool(self.cr.dbname)
        fields = []
        for field in pool.get('account.destination.summary').fields_get(self.cr, self.uid, ['account_id']):
            fields.append(field)
        r = pool.get('account.destination.summary').read(self.cr, self.uid, line.id, fields)
        if r[o]:
            return 'x'
        return ''

report_sxw.report_sxw('report.funding.pool', 'account.analytic.account', 'addons/analytic_distribution/report/funding_pool.rml', parser=funding)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
