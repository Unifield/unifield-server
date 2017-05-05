# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv

class wizard_budget_import_finish(osv.osv_memory):
    _name = 'wizard.budget.import.finish'

    def button_close(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        return {'type' : 'ir.actions.act_window_close'}

wizard_budget_import_finish()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: