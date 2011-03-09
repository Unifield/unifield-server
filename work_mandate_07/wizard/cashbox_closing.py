#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

class wizard_closing_cashbox(osv.osv_memory):
    
    _name = 'wizard.closing.cashbox'
    _columns = {
        'be_sure': fields.boolean( string="Are you sure ?", required=False ),
    }
    
    def button_close_cashbox(self, cr, uid, ids, context={}):
        # retrieving context active id (verification)
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv('Warning', _("You don't select any item!"))
        else:
            # retrieving user's choice
            res = self.browse(cr,uid,ids)[0].be_sure
            if res:
                cashbox = self.pool.get('account.bank.statement').browse(cr, uid, id)
                cashbox.write({'state': 'confirm'})
                return { 'type' : 'ir.actions.act_window_close', }
            else:
                raise osv.except_osv('Warning', _("You don't have really confirm by ticking!"))
        return True

wizard_closing_cashbox()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
