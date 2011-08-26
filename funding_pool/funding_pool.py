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

from osv import fields, osv
import decimal_precision as dp

class analytic_distribution(osv.osv):
    
    _name = "analytic.distribution"
    _columns = {
        'name': fields.char('Name', size=12, required=True),
    }
    
    _defaults ={
        'name': 'Distribution',
    }
    
analytic_distribution()

class distribution_line(osv.osv):
    
    _name = "distribution_line"
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        "distribution_id": fields.many2one('analytic.distribution', 'Associated Analytic Distribution'),
        "analytic_id": fields.many2one('account.analytic.account', 'Analytical Account'),
        "amount": fields.float('Amount'),
        "percentage": fields.float('Percentage'),
    }
    
    _defaults ={
        'name': 'Distribution Line',
    }

distribution_line()

class cost_center_distribution_line(osv.osv):
    _name = "cost_center_distribution_line"
    _inherit = "distribution_line"
    
cost_center_distribution_line()

class funding_pool_distribution_line(osv.osv):
    _name = "funding_pool_distribution_line"
    _inherit = "distribution_line"
    _columns = {
        "cost_center_id": fields.many2one('account.analytic.account', 'Cost Center Account'),
    }
    
funding_pool_distribution_line()

class free_1_distribution_line(osv.osv):
    _name = "free_1_distribution_line"
    _inherit = "distribution_line"
    
free_1_distribution_line()

class free_2_distribution_line(osv.osv):
    _name = "free_2_distribution_line"
    _inherit = "distribution_line"
    
free_2_distribution_line()

class analytic_distribution(osv.osv):
    
    _inherit = "analytic.distribution"
    _columns = {
        'cost_center_lines': fields.one2many('cost_center_distribution_line', 'distribution_id', 'Cost Center Distribution'),
        'funding_pool_lines': fields.one2many('funding_pool_distribution_line', 'distribution_id', 'Funding Pool Distribution'),
        'free_1_lines': fields.one2many('free_1_distribution_line', 'distribution_id', 'Free 1 Distribution'),
        'free_2_lines': fields.one2many('free_2_distribution_line', 'distribution_id', 'Free 2 Distribution'),
    }
    
analytic_distribution()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
