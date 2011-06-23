##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
import pooler

class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'

    _columns = {
        'life_date': fields.date('End of Life Date',
            help='The date on which the lot may become dangerous and should not be consumed.'),
        'use_date': fields.date('Best before Date',
            help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.date('Removal Date',
            help='The date on which the lot should be removed.'),
        'alert_date': fields.date('Alert Date', help="The date on which an alert should be notified about the production lot."),
    }
stock_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
