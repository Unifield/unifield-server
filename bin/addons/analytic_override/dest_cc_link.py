# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2021 MSF, TeMPO Consulting.
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


class dest_cc_link(osv.osv):
    _name = "dest.cc.link"
    _description = "Destination / Cost Center Combination"

    _columns = {
        'dest_id': fields.many2one('account.analytic.account', string="Destination", required=True,
                                   domain="[('category', '=', 'DEST'), ('type', '!=', 'view')]"),
        'cc_id': fields.many2one('account.analytic.account', "Cost Center", required=True,
                                 domain="[('category', '=', 'OC'), ('type', '!=', 'view')]"),
        'cc_name': fields.related('cc_id', 'name', type="char", string="Cost Center Name", readonly=True, store=False),
        'inactive_from': fields.date('Inactivation Combination Dest / CC from', required=False),
    }

    _order = 'dest_id, cc_id'

    _sql_constraints = [
        ('dest_cc_uniq', 'unique(dest_id, cc_id)', 'Each Cost Center can only be added once to the same Destination.')
    ]


dest_cc_link()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
