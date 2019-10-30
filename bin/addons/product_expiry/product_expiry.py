#-*- coding: utf-8 -*-
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

from osv import fields, osv

class product_product(osv.osv):
    _inherit = 'product.product'
    _columns = {
        'life_time': fields.integer('Product Life Time',
                                    help='The number of days before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
                                   help='The number of days before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
                                       help='The number of days before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of days after which an alert should be notified about the production lot."),
    }
product_product()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
