# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF
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

from osv import osv
from osv import fields
import threading

from tools.translate import _
from automated_import_job import all_files_under, move_to_process_path


class manual_import_job(osv.osv):
    _name = 'manual.import.job'
    _inherit = 'automated.import.job'

    _columns = {
        'import_id': fields.many2one(
            'automated.import',
            string='Automated import',
            readonly=True,
            required=False,
        ),
        'file_to_import': fields.binary(
            string='File to import',
            required=True,
        ),
        'function_id': fields.many2one(
            'automated.import.function',
            string='Functionality',
            required=True,
        ),
    }

    _order = "name desc"


    def unlink(self, cr, uid, ids, context=None):
        '''
        method called when user wants to delete import
        '''
        # do not delete a job which is in progress:
        for job_id in ids:
            job_state = self.read(cr, uid, [job_id], ['state'], context=context)[0]['state']
            if job_state == 'in_progress':
                raise osv.except_osv(_('Error'), _('You cannot delete an import job which is in progress'))

        return super(manual_import_job, self).unlink(cr, uid, ids, context=context)


    def process_import_bg(self, cr, uid, ids, context=None):
        """
        Method called when user click on button 'import in background' in Manual imports
        Create a new thread that process import in background
        """
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        context.update({'import_in_bg': True})

        cr.commit()
        new_thread = threading.Thread(
            target=self.process_import,
            args=(cr, uid, ids, context)
        )
        new_thread.start()

        res = {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'view_id': [data_obj.get_object_reference(cr, uid, 'msf_tools', 'manual_import_job_info_view')[1]],
            'target': 'same',
            'context': context,
        }

        return res


manual_import_job()