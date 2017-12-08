# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2017 MSF, TeMPO Consulting
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

from report import report_sxw


class cash_request_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(cash_request_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getStateValue': self._get_state_value,
        })

    def _get_state_value(self, state):
        """
        Returns the value corresponding to the state (open ==> Open)
        """
        cash_req_obj = self.pool.get('cash.request')
        if state:
            state = dict(cash_req_obj._columns['state'].selection).get(state) or ''
        return state


report_sxw.report_sxw('report.cash.request.export', 'cash.request', 'addons/finance/report/cash_request.rml', parser=cash_request_parser)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
