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
            ('engagement', 'Engagement')], 'Type', size=32, required=True, help="Gives the type of the analytic journal. When it needs for a document \
(eg: an invoice) to create analytic entries, OpenERP will look for a matching journal of the same type."),
    }

    # FIXME : Constraint doesn't works! Try another method not to create 2 engagement journal
    _sql_constraints = [
        ('engagement_journal_uniq', "CHECK (COUNT (case when type = 'engagement' then 1 else NULL end) < 2)", 'You cannot have more than one engagement journal!'),
    ]

    def create(self, cr, uid, vals, context={}):
        """
        Raise an exception if user attemp to create another engagement journal
        """
        if not context:
            context={}
        engagement_ids = self.search(cr, uid, [('type', '=', 'engagement')])
        if len(engagement_ids) and len(engagement_ids) >= 1:
            raise osv.except_osv(_('Error'), _('You cannot create a second engagement journal!'))
        res = super(account_analytic_journal, self).create(cr, uid, vals, context=context)
        return res

account_analytic_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
