#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

class account_export_mapping(osv.osv):
    _name = 'account.export.mapping'
    _description = 'Mapping of UF code into AX code'
    _rec_name = 'account_id'

    _columns = {
        'account_id': fields.many2one('account.account', string="Unifield Account Code", required=True),
        'mapping_value': fields.char('HQ System Account Code', required=True, size=64)
    }

    _sql_constraints = [
        ('unique_account_id', 'unique(account_id)', 'A mapping already exists for this account')
    ]

    def menu_import_wizard(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wiz_obj = self.pool.get('wizard.import.mapping')
        wiz_id = wiz_obj.create(cr, uid, {}, context=context)
        # we open a wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.mapping',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

account_export_mapping()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
