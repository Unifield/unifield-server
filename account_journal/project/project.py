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
    _columns = {
        'type': fields.selection([('sale','Sale'), ('purchase','Purchase'), ('cash','Cash'), ('general','General'), ('situation','Situation'), 
            ('engagement', 'Engagement'), ('correction', 'Correction'), ('cur_adj', 'Currency Adjustement'),], 'Type', size=32, required=True, help="Gives the type of the analytic journal. When it needs for a document \
(eg: an invoice) to create analytic entries, OpenERP will look for a matching journal of the same type."),
    }

    def _check_engagement_count(self, cr, uid, ids, context={}):
        """
        Check that no more than one engagement journal exists
        """
        if not context:
            context={}
        eng_ids = self.search(cr, uid, [('type', '=', 'engagement')])
        if len(eng_ids) and len(eng_ids) > 1:
            return False
        return True

    _constraints = [
        (_check_engagement_count, 'You cannot have more than one engagement journal!', ['type']),
    ]

account_analytic_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
