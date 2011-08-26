# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import osv, fields
from tools.translate import _

import netsvc

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'
    
    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }
    
    def finalize_invoice_move_lines(self, cr, uid, invoice_browse, move_lines):
        if invoice_browse.analytic_distribution_id:
            distrib_id = invoice_browse.analytic_distribution_id.id
            for move_line in move_lines:
                if not move_line['analytic_distribution_id']:
                    move_line['analytic_distribution_id'] = distrib_id
        return
    
account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'
    
    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        res = super(account_invoice_line, self).line_get_convert(cr, uid, x, part, date, context=context)
        res['analytic_distribution_id'] = x.get('analytic_distribution_id', False)
        return res
        
account_invoice_line()