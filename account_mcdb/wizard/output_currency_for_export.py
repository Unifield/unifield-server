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
from tools.translate import _

class output_currency_for_export(osv.osv_memory):
    _name = 'output.currency.for.export'
    _description = 'Output currency choice wizard'

    _columns = {
        'currency_id': fields.many2one('res.currency', string="Output currency", help="Give an output currency that would be used for export", required=True)
    }

    def button_validate(self, cr, uid, ids, context={}):
        """
        Launch export wizard
        """
        # Some verifications
        if not context or not context.get('active_ids', False) or not context.get('active_model', False):
            raise osv.except_osv(_('Error'), _('An error has occured. Please contact an administrator.'))
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        model = context.get('active_model')
        line_ids = context.get('active_ids')
        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]
        wiz = self.browse(cr, uid, ids, context=context)[0]
        currency_id = wiz and wiz.currency_id and wiz.currency_id.id or False
        # Return good view
        return self.pool.get('account.line.csv.export').export_to_csv(cr, uid, line_ids, currency_id, model, context=context) or False

output_currency_for_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
