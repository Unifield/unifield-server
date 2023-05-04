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


class certificate_free_gift(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(certificate_free_gift, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getCompany': self._get_company(),
        })

    def _get_company(self):
        '''
        Return information about the company.
        '''
        company = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

        res = {}
        if company:
            res['partner'] = company.partner_id and company.partner_id.name or False
            if company.partner_id and len(company.partner_id.address):
                res['street'] = company.partner_id.address[0].street
                res['street2'] = company.partner_id.address[0].street2
                if company.partner_id.address[0].zip is not False:
                    res['zip'] = company.partner_id.address[0].zip
                else:
                    res['zip'] = ""
                res['city'] = company.partner_id.address[0].city
                res['country'] = company.partner_id.address[0].country_id and company.partner_id.address[0].country_id.name or False

        return res

    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if not obj.backshipment_id:
                raise osv.except_osv(_('Warning !'), _('Free Gift Certificate is only available for Shipment Objects (not draft)!'))

        return super(certificate_free_gift, self).set_context(objects, data, ids, report_type=report_type)


report_sxw.report_sxw('report.certificate.free.gift', 'shipment', 'addons/msf_outgoing/report/certificate_free_gift.rml', parser=certificate_free_gift, header="external")
