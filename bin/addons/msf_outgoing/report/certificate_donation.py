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

class certificate_donation(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(certificate_donation, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })
        
    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if not obj.backshipment_id:
                raise osv.except_osv(_('Warning !'), _('Certificate of Donation is only available for Shipment Objects (not draft)!'))
        
        return super(certificate_donation, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw('report.certificate.donation', 'shipment', 'addons/msf_outgoing/report/certificate_donation.rml', parser=certificate_donation, header="external")

