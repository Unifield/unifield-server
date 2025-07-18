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


class sde_import(osv.osv_memory):
    _name = 'sde.import'
    _description = 'SDE for IN'

    _columns = {
        'file': fields.binary(string='File', filters='*.xml, *.xls', required=True),
        'filename': fields.char(string='Imported filename', size=256),
        'message': fields.text(string='Message'),
    }

    def sde_file_import(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return True

        pick_obj = self.pool.get('stock.picking')
        in_proc_obj = self.pool.get('stock.incoming.processor')
        in_simu_obj = self.pool.get('wizard.import.in.simulation.screen')

        context['sde_flow'] = True
        msg = 'Done'
        try:
            sde_import = self.read(cr, uid, ids[0], ['file', 'filename'], context=context)
            if not sde_import['file']:
                raise osv.except_osv(_('Warning'), _('No file to import'))

            file = os.path.join(sde_import['filename'])
            file_desc = open(file, 'wb+')
            file_desc.write(base64.b64decode(sde_import['file']))
            file_desc.close()
            filetype = pick_obj.get_import_filetype(cr, uid, file, context=context)
            file_content = pick_obj.get_file_content(cr, uid, file, context=context)

            # get the IN
            in_id = pick_obj.get_incoming_id_from_file(cr, uid, file, context)

            in_proc_ids = in_proc_obj.search(cr, uid, [('picking_id', '=', in_id), ('draft', '=', True)], context=context)
            if in_proc_ids:  # Reset previous saved as draft
                in_proc_obj.write(cr, uid, in_proc_ids, {'draft': False, 'partial_process_sign': False}, context=context)
            # create stock.incoming.processor and its stock.move.in.processor
            in_processor = in_proc_obj.create(cr, uid, {'picking_id': in_id, 'sde_updated': True}, context=context)
            # import all lines and set qty to zero
            in_proc_obj.create_lines(cr, uid, in_processor, context=context)
            in_proc_obj.launch_simulation(cr, uid, in_processor, context=context)

            simu_id = context.get('simu_id')

            # create simulation screen to get the simulation report:
            in_simu_obj.write(cr, uid, [simu_id], {
                'filetype': filetype,
                'file_to_import': base64.b64encode(bytes(file_content, 'utf8')),
            }, context=context)

            in_simu_obj.launch_simulate(cr, uid, [simu_id], context=context)
            file_res = pick_obj.generate_simulation_screen_report(cr, uid, simu_id, context=context)
            in_simu_obj.launch_import(cr, uid, [simu_id], context=context)

            # attach simulation report to new IN
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
            msg = e
        finally:
            if 'sde_flow' in context:
                context.pop('sde_flow')
            self.write(cr, uid, ids, {'message': msg}, context=context)

        return True


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
