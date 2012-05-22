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

class account_destination_link(osv.osv):
    _name = 'account.destination.link'
    _description = 'Destination link between G/L and Analytic accounts'

    _columns = {
        'account_id': fields.many2one('account.account', "G/L Account", required=True),
        'destination_id': fields.many2one('account.analytic.account', "Analytical Destination Account", required=True, domain="[('type', '!=', 'view'), ('category', '=', 'DEST')]"),
        'funding_pool_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_destinations', 'tuple_id', 'funding_pool_id', "Funding Pools"),
    }

account_destination_link()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    _columns = {
        'user_type_code': fields.related('user_type', 'code', type="char", string="User Type Code", store=False),
        'funding_pool_line_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_accounts', 'account_id', 'funding_pool_id', 
            string='Funding Pools'),
        'default_destination_id': fields.many2one('account.analytic.account', 'Default Destination'),
        'destination_ids': fields.many2many('account.analytic.account', 'account_destination_link', 'account_id', 'destination_id', 'Destinations'),
    }

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
