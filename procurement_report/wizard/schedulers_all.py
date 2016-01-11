# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import threading

from osv import osv

class procurement_purchase_compute_all(osv.osv_memory):
    _name = 'procurement.purchase.compute.all'
    _description = 'Compute all schedulers'

    _columns = {
    }

    _defaults = {
    }

    def _procure_calculation_all_purchase(self, cr, uid, ids, context=None):
        """
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        """
        proc_obj = self.pool.get('procurement.order')
        proc_obj._procure_confirm(cr, uid, use_new_cursor=cr.dbname, context=context)
        return {}

    def procure_calculation_purchase(self, cr, uid, ids, context=None):
        """
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        """
        if context is None:
            context = {}

        context.update({'run_id': True})

        threaded_calculation = threading.Thread(target=self._procure_calculation_all_purchase, args=(cr, uid, ids, context))
        threaded_calculation.start()
        self.infolog(cr, uid, "The 'Auto POs creation' scheduler has been launched")
        return {'type': 'ir.actions.act_window_close'}

procurement_purchase_compute_all()


class procurement_min_max_compute_all(osv.osv_memory):
    _name = 'procurement.min.max.compute.all'
    _description = 'Compute all schedulers'

    _columns = {
    }

    _defaults = {
    }

    def _procure_calculation_all_min_max(self, cr, uid, ids, context=None):
        """
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        """
        proc_obj = self.pool.get('procurement.order')
        proc_obj._procure_orderpoint_confirm(cr, uid, use_new_cursor=cr.dbname, automatic=False, context=context)
        return {}

    def procure_calculation_min_max(self, cr, uid, ids, context=None):
        """
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        """
        threaded_calculation = threading.Thread(target=self._procure_calculation_all_min_max, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

procurement_min_max_compute_all()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
