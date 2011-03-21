#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF
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

class wizard_hard_posting(osv.osv_memory):
    _name = "wizard.hard.posting"

    def action_confirm_hard_posting(self, cr, uid, ids, context={}):
        """
        Hard post some statement lines
        """
        if 'active_ids' in context:
            # Retrieve statement line ids
            st_line_ids = context.get('active_ids')
            # Browse statement lines
            for st_line_id in st_line_ids:
                # Verify that the line isn't in hard state
                st_line = self.pool.get('account.bank.statement.line').browse(cr, uid, [st_line_id])[0]
                state = st_line.state
                if state != 'hard':
                    # If in the good state : temp posting !
                    self.pool.get('account.bank.statement.line').button_hard_posting(cr, uid, [st_line_id], context=context)
            mod_obj = self.pool.get('ir.model.data')
            act_obj = self.pool.get('ir.actions.act_window')
            result = mod_obj._get_id(cr, uid, 'account', 'action_view_bank_statement_tree')
            id = mod_obj.read(cr, uid, [result], ['res_id'], context=context)[0]['res_id']
            result = act_obj.read(cr, uid, [id], context=context)[0]
            result['res_id'] = st_line.statement_id.id
            result['view_mode'] = 'form,tree,graph'
            views_id = {}
            for (num, typeview) in result['views']:
                views_id[typeview] = num
            result['views'] = []
            for typeview in ['form','tree','graph']:
                if views_id.get(typeview):
                    result['views'].append((views_id[typeview], typeview))
            result['target'] = 'crush'
            return result
        else:
            raise osv.except_osv(_('Warning'), _('You have to select some lines before using this wizard.'))

wizard_hard_posting()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
