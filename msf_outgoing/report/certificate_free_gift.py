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
            'parse_fo_ref': self._parse_fo_ref,
        })
        
    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if not obj.backshipment_id:
                raise osv.except_osv(_('Warning !'), _('Free Gift Certificate is only available for Shipment Objects (not draft)!'))
        
        return super(certificate_free_gift, self).set_context(objects, data, ids, report_type=report_type)

    def _parse_fo_ref(self, fo_id):
        if fo_id:
            name = fo_id.name or ''
            if name:
                # force word wrap at the end of the reference (last slash)
                parts = name.split('/')
                parts_len = len(parts)
                index = 1
                
                new_name = ''
                for p in parts:
                    if index < parts_len:
                        if index > 1:
                            new_name += '/'
                    else:
                        new_name += '/ '  # last slash of the reference
                    new_name += p
                    index += 1
                return new_name
        return ''

report_sxw.report_sxw('report.certificate.free.gift', 'shipment', 'addons/msf_outgoing/report/certificate_free_gift.rml', parser=certificate_free_gift, header="external")

