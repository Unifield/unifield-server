#!/usr/bin/env python
#-*- encoding:utf-8 -*-

##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
from tools.translate import _

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _description = 'Analytic Journal'
    _inherit = 'account.analytic.journal'

    def get_journal_type(self, cr, uid, context={}):
        """
        Get all analytic journal type
        """
        return [
            ('sale','Sale'),
            ('purchase','Purchase'),
            ('cash','Cash'),
            ('general','General'),
            ('situation','Situation'),
            ('engagement', 'Engagement'),
            ('hq', 'HQ'),
            ('correction', 'Correction'),
            ('cur_adj', 'Currency Adjustement'),
            ('hr', 'HR'),
            ('inkind', 'In-kind Donation'),
        ]

    _columns = {
        'type': fields.selection(get_journal_type, 'Type', size=32, required=True, help="Gives the type of the analytic journal. When it needs for a document \
(eg: an invoice) to create analytic entries, OpenERP will look for a matching journal of the same type."),
    }

account_analytic_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
