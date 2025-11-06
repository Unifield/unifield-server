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
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class pre_packing_excel_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(pre_packing_excel_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getShipper': self.get_shipper,
            'getPickingShipper': self.get_picking_shipper,
            'getConsignee': self.get_consignee,
            'getPackTypes': self.get_pack_types,
        })

    def get_consignee(self, picking):
        """
        Return values for consignee
        @param picking: browse_record of the picking.ticket
        @return: A dictionnary with consignee values
        """
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')
        cr = self.cr
        uid = self.uid
        res = {}

        if picking.partner_id2:
            consignee_partner = picking.partner_id2
            if picking.sale_id and picking.sale_id.procurement_request and picking.address_id:
                consignee_addr = picking.address_id
            else:
                consignee_addr_id = partner_obj.address_get(cr, uid, consignee_partner.id)['default']
                consignee_addr = addr_obj.browse(cr, uid, consignee_addr_id)

            addr = ''
            addr_street = ''
            addr_zip_city = ''
            if consignee_addr:
                if consignee_addr.street:
                    addr += consignee_addr.street
                    addr += ' '
                    addr_street += consignee_addr.street + ' '
                if consignee_addr.street2:
                    addr += consignee_addr.street2
                    addr += ' '
                    addr_street += consignee_addr.street2
                if consignee_addr.zip:
                    addr += consignee_addr.zip
                    addr += ' '
                    addr_zip_city += consignee_addr.zip + ' '
                if consignee_addr.city:
                    addr += consignee_addr.city
                    addr += ' '
                    addr_zip_city += consignee_addr.city
                if consignee_addr.country_id:
                    addr += consignee_addr.country_id.name

            res.update({
                'consignee_name': consignee_partner.name,
                'consignee_contact': consignee_partner.partner_type == 'internal' and 'Supply responsible' or consignee_addr and consignee_addr.name or '',
                'consignee_address': addr,
                'consignee_phone': consignee_addr and consignee_addr.phone or '',
                'consignee_email': consignee_addr and consignee_addr.email or '',
                'consignee_addr_street': addr_street,
                'consignee_addr_zip_city': addr_zip_city,
            })

        return [res]

    def get_shipper(self):
        """
        Return the shipper value for the given field
        @param field: Name of the field to retrieve
        @return: The value of the shipper field
        """
        return [self.pool.get('shipment').default_get(self.cr, self.uid, [])]

    def get_picking_shipper(self):
        """
        The 'Shipper' fields must be filled automatically with the
        default address of the current instance
        """
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        addr_obj = self.pool.get('res.partner.address')

        instance_partner = user_obj.browse(self.cr, self.uid, self.uid).company_id.partner_id
        instance_addr_id = partner_obj.address_get(self.cr, self.uid, instance_partner.id)['default']
        instance_addr = addr_obj.browse(self.cr, self.uid, instance_addr_id)

        addr_street = ''
        addr_zip_city = ''
        if instance_addr.street:
            addr_street += instance_addr.street + ' '
        if instance_addr.street2:
            addr_street += instance_addr.street2
        if instance_addr.zip:
            addr_zip_city += instance_addr.zip + ' '
        if instance_addr.city:
            addr_zip_city += instance_addr.city + ' '
        if instance_addr.country_id:
            addr_zip_city += instance_addr.country_id.name

        return {
            'shipper_name': instance_partner.name,
            'shipper_contact': 'Supply responsible',
            'shipper_addr_street': addr_street,
            'shipper_addr_zip_city': addr_zip_city,
            'shipper_phone': instance_addr.phone,
            'shipper_email': instance_addr.email,
        }

    def get_pack_types(self):
        '''
        Get all the Pack Types
        '''
        pack_type_obj = self.pool.get('pack.type')

        packs = []
        pack_type_ids = pack_type_obj.search(self.cr, self.uid, [], context=self.localcontext)
        for pack_type in pack_type_obj.read(self.cr, self.uid, pack_type_ids, [], context=self.localcontext):
            packs.append([pack_type['name'], '%gx%gx%g' % (pack_type['width'], pack_type['length'], pack_type['height'])])

        return packs, len(pack_type_ids)


SpreadsheetReport(
    'report.pre.packing.excel.export',
    'stock.picking',
    'addons/msf_outgoing/report/pre_packing_excel_report_xls.mako',
    parser=pre_packing_excel_report_parser,
    header=False,
)
