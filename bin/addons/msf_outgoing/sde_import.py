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

from osv import osv, fields
from tools.translate import _

import os
import base64
import time
from datetime import datetime
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import xml.etree.ElementTree as ET
import re

import sys
import xmlrpc.client


class sde_import(osv.osv_memory):
    _name = 'sde.import'
    _description = 'SDE import'

    _columns = {
        'xmlrpc_url': fields.char(string='XMLRPC server address', size=256),
        'xmlrpc_db': fields.char(string='XMLRPC database', size=64),
        'xmlrpc_pass': fields.char(string='XMLRPC password', size=64),
        'file': fields.binary(string='File', filters='*.xml, *.xls', required=True),
        'filename': fields.char(string='Imported filename', size=256),
        'message': fields.text(string='Message'),
    }

    def fetch_sde_data(self, cr, uid, ids, context=None):
        """
        Simulacrum of XMLRPC script for the API
        """
        if context is None:
            context = {}
        if not ids:
            return True

        sde_import = self.browse(cr, uid, ids[0], context=context)

        # Config data
        # host = args.runbot
        # if args.database:
        #     dbname = args.database
        host = sde_import.xmlrpc_url
        if sde_import.xmlrpc_db:
            dbname = sde_import.xmlrpc_db
        else:
            raise Exception('Please use the "-db" option to set the database you want to use')
        user = 'admin'
        # password = args.password
        password = sde_import.xmlrpc_pass
        # if args.runbot and args.runbot != '127.0.0.1':
        if sde_import.xmlrpc_url and sde_import.xmlrpc_url != '127.0.0.1':
            xmlrpcport = 80
        else:
            xmlrpcport = 8069

        # Login
        sock = xmlrpc.client.ServerProxy('http://%s:%s/xmlrpc/common' % (host, xmlrpcport))
        uid = sock.login(dbname, user, password)
        if not uid:
            print('Wrong %s password on %s:%s db: %s' % (user, host, xmlrpcport, dbname))
            sys.exit(1)
        sock = xmlrpc.client.ServerProxy('http://%s:%s/xmlrpc/object' % (host, xmlrpcport))

        if not sde_import.file:
            raise osv.except_osv(_('Warning'), _('No file to import'))
        msg = sock.execute(dbname, uid, password, 'sde.import', 'sde_file_import', sde_import.file, sde_import.filename)
        sock.execute(dbname, uid, password, 'sde.import', 'write', sde_import.id, {'message': msg})

        return True

    # def sde_file_import(self, cr, uid, file, filename, context=None):
    def sde_file_import(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        # if not ids:
        #     return True

        pick_obj = self.pool.get('stock.picking')
        in_proc_obj = self.pool.get('stock.incoming.processor')
        in_simu_obj = self.pool.get('wizard.import.in.simulation.screen')

        context['sde_flow'] = True
        msg = False
        try:
            sde_import = self.read(cr, uid, ids[0], ['file', 'filename'], context=context)
            if not sde_import['file']:
                raise osv.except_osv(_('Warning'), _('No file to import'))
            file = sde_import['file']
            filename = sde_import['filename']

            # TODO: Temporary solution ?
            # clean_filename = sde_import['filename'] and sde_import['filename'].replace('C:\\fakepath\\', '/tmp/')
            clean_filename = filename and filename.replace('C:\\fakepath\\', '/tmp/')
            file_path = os.path.join(clean_filename)
            file_desc = open(file_path, 'wb+')
            # file_desc.write(base64.b64decode(sde_import['file']))
            file_desc.write(base64.b64decode(file))
            file_desc.close()
            filetype = pick_obj.get_import_filetype(cr, uid, file_path, context=context)
            file_content = pick_obj.get_file_content(cr, uid, file_path, context=context)

            # get the IN with the Ship Ref or the Origin
            in_id = self.get_incoming_id_from_file(cr, uid, file_path, filetype, context=context)

            in_proc_ids = in_proc_obj.search(cr, uid, [('picking_id', '=', in_id), ('draft', '=', True)], context=context)
            if in_proc_ids:
                in_processor = in_proc_ids[0]
                if not in_proc_obj.read(cr, uid, in_processor, ['sde_updated'], context=context)['sde_updated']:
                    in_proc_obj.write(cr, uid, in_processor, {'sde_updated': True}, context=context)
            else:
                # create stock.incoming.processor and its stock.move.in.processor
                in_processor = in_proc_obj.create(cr, uid, {'picking_id': in_id, 'sde_updated': True}, context=context)
                # import all lines and set qty to zero
                in_proc_obj.create_lines(cr, uid, in_processor, context=context)

            in_proc_obj.launch_simulation(cr, uid, in_processor, context=context)

            simu_id = context.get('simu_id')

            # create simulation screen to get the simulation report:
            in_simu_obj.write(cr, uid, [simu_id], {
                'filename': filename,
                'filetype': filetype,
                'file_to_import': base64.b64encode(bytes(file_content, 'utf8')),
            }, context=context)

            in_simu_obj.launch_simulate(cr, uid, [simu_id], context=context)
            file_res = pick_obj.generate_simulation_screen_report(cr, uid, simu_id, context=context)

            simu_data = in_simu_obj.read(cr, uid, simu_id, ['import_error_ok', 'message'], context=context)
            msg = simu_data['message'] or 'Done'
            # Only import when all the data is correct
            if not simu_data['import_error_ok']:
                in_simu_obj.launch_import(cr, uid, [simu_id], context=context)

            # attach the simulation report to the IN
            # TODO: Point 4.3.19 ?
            self.pool.get('ir.attachment').create(cr, uid, {
                'name': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'datas_fname': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'description': 'IN simulation screen',
                'res_model': 'stock.picking',
                'res_id': in_id,
                'datas': file_res.get('result'),
            })

            # Log the update
            in_name = pick_obj.read(cr, uid, in_id, ['name'], context=context)['name']
            self.pool.get('sde.update.log').create(cr, uid, {'date': datetime.now(), 'doc_type': 'in', 'doc_ref': in_name}, context=context)
        except Exception as e:
            # Rejection message to send back
            if isinstance(e, osv.except_osv):
                msg = e.value
            else:
                msg = e
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')
            self.write(cr, uid, ids, {'message': msg}, context=context)

        # return msg
        return True

    def get_incoming_id_from_file(self, cr, uid, file_path, filetype, context=None):
        '''
        The Origin field is required in the file, but not the Ship Reference. If the Ship Reference is filled, only
        Available Shipped INs will be searched, Available otherwise
        '''
        if context is None:
            context = {}

        xmlstring = open(file_path).read()

        # Search the file
        po_name, ship_ref = False, False
        if filetype == 'excel':
            file_obj = SpreadsheetXML(xmlstring=xmlstring)
            ship_ref_found = False
            for index, row in enumerate(file_obj.getRows()):
                line_header = (row.cells[0].data or '').lower()
                if line_header == 'origin':
                    po_name = row.cells[1].data or ''
                    if isinstance(po_name, str):
                        po_name = po_name.strip().lower()
                    if not po_name:
                        raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
                elif line_header == 'freight':
                    ship_ref_found = True
                    ship_ref = row.cells[1].data or ''
                    if isinstance(ship_ref, str):
                        ship_ref = ship_ref.strip().lower()
                if po_name and ship_ref_found:
                    break
            if not po_name:
                raise osv.except_osv(_('Error'), _('Header field "Origin" not found in the given XLS file'))
        elif filetype == 'xml':
            root = ET.fromstring(xmlstring)
            orig = root.findall('.//field[@name="origin"]')
            if orig:
                po_name = orig[0].text or ''
                po_name = po_name.strip().lower()
                if not po_name:
                    raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
            else:
                raise osv.except_osv(_('Error'), _('No field with name "Origin" was found in the XML file'))
            ship_ref_field = root.findall('.//field[@name="freight"]')
            if ship_ref_field:
                ship_ref = ship_ref_field[0].text or ''
                ship_ref = ship_ref.strip().lower()

        if po_name.find(':') != -1:
            for part in po_name.split(':'):
                re_res = re.findall(r'PO[0-9]+$', part, re.I)
                if re_res:
                    po_name = part
                    break

        # Search the IN
        po_id = self.pool.get('purchase.order').search(cr, uid, [('name', '=ilike', po_name)], context=context)
        if not po_id:
            raise osv.except_osv(_('Error'), _('PO with name %s not found') % po_name)
        in_domain = [('purchase_id', '=', po_id[0]), ('type', '=', 'in'), ('claim', '=', False)]
        error_msg = _('No available IN found for the given PO %s') % po_name
        if ship_ref:
            in_domain.extend([('shipment_ref', '=ilike', ship_ref), ('state', '=', 'shipped')])
            error_msg = _('No available shipped IN found for the given PO %s and the given Ship Reference %s') % (po_name, ship_ref)
        else:
            in_domain.append(('state', 'in', ['assigned', 'shipped']))
        in_id = self.pool.get('stock.picking').search(cr, uid, in_domain, context=context)
        if not in_id:
            raise osv.except_osv(_('Error'), error_msg)

        return in_id[0]

    # TODO: Remove once the shipment method is called from the API
    def generate_sde_dispatched_packing_list_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.pool.get('shipment').generate_dispatched_packing_list_report(cr, uid, context=context)


sde_import()


class sde_update_log(osv.osv):
    _name = 'sde.update.log'
    _description = 'SDE Update Logs'
    _order = 'id desc'

    _columns = {
        'date': fields.datetime('Update Date', required=True, readonly=True),
        'doc_type': fields.selection(string='Document', selection=[('in', 'Incoming Shipment')], required=True, readonly=True),
        'doc_ref': fields.char(string='Reference', size=64, required=True, readonly=True),
    }


sde_update_log()
