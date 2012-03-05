#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

class stock_invoice_onshipping(osv.osv_memory):
    _name = 'stock.invoice.onshipping'
    _inherit = 'stock.invoice.onshipping'

    _defaults = {
        'journal_id': lambda obj, cr, uid, c: obj.pool.get('stock.invoice.onshipping')._get_journal_id(cr, uid, c) and obj.pool.get('stock.invoice.onshipping')._get_journal_id(cr, uid, c)[0] or False,
    }

stock_invoice_onshipping()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
