# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

import time
from osv import osv
from tools.translate import _
from report import report_sxw

class invoice(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(invoice, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getCompanyInfo': self._get_company_info,
            'getMoves': self._get_moves,
            'getMoveIndex': self._get_move_index,
            'getTotal': self._get_total,
            'getCurrency': self._get_ccy_name,
        })
        self.vars = {}  # key is shipment id
        
    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if not obj.backshipment_id:
                raise osv.except_osv(_('Warning !'),
                _('Invoice is only available for Shipment Objects (not draft)!'))
        
        return super(invoice, self).set_context(objects, data, ids, report_type=report_type)

    def _get_company_info(self, field):
        """
        Return info from instance's company.
        :param field: Field to read
        :return: Information of the company
        :rtype: str
        """
        company = self.pool.get('res.users').browse(self.cr, self.uid,
            self.uid).company_id.partner_id
            
        res = ''
        if field == 'name':
            res = company.name
        else:
            if company.address:
                addr = company.address[0]
                if field == 'addr_name':
                    res = addr.name
                elif field == 'street':
                    res = addr.street
                elif field == 'street2':
                    res = addr.street2
                elif field == 'city':
                    res = '%s %s' % (addr.zip, addr.city)
                elif field == 'country':
                    res = addr.country_id and addr.country_id.name or ''
                elif field == 'phone':
                    res = addr.phone or addr.mobile or ''
        return res
        
    def _get_moves(self, shipment):
        self.vars[shipment.id] = {
            'move_index': 1,
            'currency_id': False,
        }
        
        res = []
        total = 0.
        for pf in shipment.pack_family_memory_ids:
            for move in pf.move_lines:
                res.append(move)
                total += move.total_amount
                if not self.vars[shipment.id]['currency_id']:
                    self.vars[shipment.id]['currency_id'] = move.currency_id.id
        self.vars[shipment.id]['total'] = total
        return res
        
    def _get_move_index(self, shipment):
        """
        get stock move line index (report line)
        :rtype int
        """
        if shipment.id in self.vars:
            res = self.vars[shipment.id].get('move_index', 1)
            self.vars[shipment.id]['move_index'] = res + 1
            return res
        return 0.
        
    def _get_total(self, shipment):
        """
        get total amount
        :rtype float
        """
        res = 0.
        for pf in shipment.pack_family_memory_ids:
            for move in pf.move_lines:
                if move.total_amount:
                    res += move.total_amount
        return res

    def _get_ccy_name(self, shipment, in_parenthesis):
        """
        get currency name
        :rtype str
        """
        res = ''
        currency_id = self.vars.get(shipment.id, {}).get('currency_id', False)
        if currency_id:
            res = self.pool.get('res.currency').browse(self.cr, self.uid,
                currency_id).name
        if res and in_parenthesis:
            res = '(' + res + ')'
        return res

report_sxw.report_sxw('report.invoice', 'shipment',
    'addons/msf_outgoing/report/invoice.rml', parser=invoice,
    header="external")
