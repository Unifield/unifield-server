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

class mass_reallocation_wizard(osv.osv_memory):
    _name = 'mass.reallocation.wizard'
    _description = 'Mass Reallocation Wizard'

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True),
        'line_ids': fields.many2many('account.analytic.line', 'mass_reallocation_rel', 'wizard_id', 'analytic_line_id', 
            string="Analytic Journal Items", required=True),
    }

    def default_get(self, cr, uid, fields=[], context={}):
        """
        Fetch context active_ids to populate line_ids wizard field
        """
        # Some verifications
        if not context:
            context = {}
        # Default behaviour
        res = super(mass_reallocation_wizard, self).default_get(cr, uid, fields, context=context)
        # Populate line_ids field
        if context.get('active_ids', False) and context.get('active_model', False) == 'account.analytic.line':
            res['line_ids'] = context.get('active_ids')
        return res

    def button_validate(self, cr, uid, ids, context={}):
        """
        Launch mass reallocation process
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse given wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            to_process = [x.id for x in wiz.line_ids] or []
        return {'type': 'ir.actions.act_window_close'}

mass_reallocation_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
