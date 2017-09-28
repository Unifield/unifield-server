#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _inherit = 'account.commitment'

    _columns = {
        'purchase_id': fields.many2one('purchase.order', string="Source document", readonly=True),
    }

account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _inherit = 'account.commitment.line'

    _columns = {
        'purchase_order_line_ids': fields.many2many('purchase.order.line', 'purchase_line_commitment_rel', 'commitment_id', 'purchase_id',
                                                    string="Purchase Order Lines", readonly=True),
    }

account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
