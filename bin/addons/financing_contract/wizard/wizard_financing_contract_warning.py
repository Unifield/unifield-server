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
from osv import osv, fields
import netsvc


class wizard_financing_contract_contract_warning(osv.osv_memory):
    """
    Financing Contract Message Wizard (with workflow signal forwarding)
    """
    _name = "wizard.financing.contract.contract.warning"

    _columns = {
        'warn_message': fields.text('Message', readonly=True),
    }

    def _get_default_warn_message(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('financing_contract_warning', {}).get('text', '')

    _defaults = {
        'warn_message': _get_default_warn_message,
    }

    def btn_close(self, cr, uid, ids, context=None):
        contract_obj = self.pool.get('financing.contract.contract')
        signal = context.get('financing_contract_warning', {}).get(
            'signal', False)
        res_id = context.get('financing_contract_warning', {}).get(
            'res_id', False)
        if signal and res_id:
            contract_obj.change_contract_state(cr, uid, res_id, signal, context=context)
        return {
            'type': 'ir.actions.act_window_close', 'context': context,
        }

wizard_financing_contract_contract_warning()
