#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
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

class account_journal(osv.osv):
    _name = "account.journal"
    _inherit = "account.journal"

    _columns = {
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'), \
            ('cash', 'Cash'), ('bank', 'Bank and Cheques'), ('general', 'General'), ('cheque', 'Cheque'), \
            ('situation', 'Opening/Closing Situation')], 'Type', size=32, required=True,
             help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
             " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
             " Select 'Cash' to be used at the time of making payment."\
             " Select 'General' for miscellaneous operations."\
             " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        }

account_journal()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
