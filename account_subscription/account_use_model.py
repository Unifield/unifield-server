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
from tools.translate import _

class account_use_model(osv.osv_memory):
    _name = 'account.use.model'
    _inherit = 'account.use.model'

    def __hook_val_update_before_line_creation(self, cr, uid, val, context=None):
        """
        Add document date to val
        """
        if not 'document_date' in val:
            if not 'date' in val:
                raise osv.except_osv(_('Warning'), _('Date is missing!'))
            val.update({'document_date': val.get('date')})
        return val

account_use_model()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
