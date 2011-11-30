# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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

class stock_incoterms(osv.osv):
    _name = 'stock.incoterms'
    _inherit = 'stock.incoterms'

    _columns = {
        'name': fields.char('Name', size=128, required=True, help="Incoterms are series of sales terms.They are used to divide transaction costs and responsibilities between buyer and seller and reflect state-of-the-art transportation practices."),
    }

stock_incoterms()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
