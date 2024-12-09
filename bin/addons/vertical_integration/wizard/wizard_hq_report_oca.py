# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
from tools.translate import _
assert _ # pyflakes
from tools import misc
import time
from time import strptime
import netsvc
import os
import threading

class wizard_export_vi_finance(osv.osv_memory):
    _delete_suffix = '.delete'
    _export_extra_data = {}

    def get_period_state(self, cr, uid, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            return []

        coordo_ids = self.pool.get('msf.instance').search(cr, uid, [('level', '=', 'coordo')], context=context)
        return self.pool.get('account.period.state').search(cr, uid, [('instance_id', 'in', coordo_ids), ('state', '=', 'mission-closed'), ('auto_export_vi', '=', False), ('period_id.number', '<', 16)], context=context)


    def get_active_export_ids(self, cr, uid, context=None):
        instance = self.pool.get('res.company')._get_instance_record(cr, uid)
        if not instance or instance.instance not in ('HQ_OCA', 'OCP_HQ'):
            return False

        return self.pool.get('automated.export').search(cr, uid, [('active', '=', True), ('function_id.model_id', '=', self._name)], context=context)

    def launch_auto_export(self, cr, uid, context=None):
        export_ids = self.get_active_export_ids(cr, uid, context)
        if not export_ids:
            return False

        if not self.get_period_state(cr, uid, context=None):
            return False

        export_obj = self.pool.get('automated.export')
        new_thread = threading.Thread(
            target=export_obj.run_job_newcr,
            args=(cr.dbname, uid, export_ids, context)
        )
        new_thread.start()
        return True

    def _delete_file(self, filename):
        try:
            if filename.endswith(self._delete_suffix):
                # request to delete the suffixed file, try to delete the original first
                original = filename[:-len(self._delete_suffix)]
                if os.path.isfile(original) and not self._delete_file(original):
                    # unable to delete the original: do not delete the suffixed file
                    return False
            os.unlink(filename)
        except:
            to_delete_name = '%s%s' % (filename, self._delete_suffix)
            if not filename.endswith(self._delete_suffix) and not os.path.isfile(to_delete_name):
                with open(to_delete_name, 'wb'):
                    pass
            return False
        return True

    def auto_export_vi(self, cr, uid, export_wiz, remote_con=False, disable_generation=False, context=None):
        """
            disable_generation=True when we only want to push files to remote
        """

        instance = self.pool.get('res.company')._get_instance_record(cr, uid)
        if not instance or instance.level != 'section':
            raise osv.except_osv(_('Warning'), _('Export is only available at HQ level.'))

        p_state_obj = self.pool.get('account.period.state')
        export_job_obj = self.pool.get('automated.export.job')
        nb_ok = 0
        nb_error = 0
        msg = []

        if not disable_generation:
            period_state_ids = self.get_period_state(cr, uid, context=context)
            instance_seen = {}
            for period_state in p_state_obj.browse(cr, uid, period_state_ids, context=context):
                if period_state.instance_id.id in instance_seen:
                    continue

                try:
                    file_name = self._export_filename.format(
                        instance=period_state.instance_id.code,
                        year=strptime(period_state.period_id.date_start, '%Y-%m-%d').tm_year,
                        month=period_state.period_id.number or 0,
                        date=time.strftime('%Y%m%d%H%M%S'),
                    )
                    if not export_wiz.ftp_dest_ok:
                        out_file_name = os.path.join(export_wiz.dest_path, file_name)
                    else:
                        out_file_name = os.path.join(export_wiz.destination_local_path, file_name)

                    msg.append('[%s] processing %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), out_file_name))

                    out_file = open(out_file_name, 'wb')
                    form_data = {
                        'instance_id': period_state.instance_id.id,
                        'instance_ids': [period_state.instance_id.id] + [child_id.id for child_id in period_state.instance_id.child_ids],
                        'period_id': period_state.period_id.id,
                        'selection': 'unexported'
                    }
                    form_data.update(self._export_extra_data)
                    report_data = {
                        'form': form_data,
                        'output_file': out_file,
                    }

                    obj = netsvc.LocalService(self._export_report_name)
                    obj.create(cr, uid, [], report_data, context=context)
                    out_file.close()
                    p_state_obj.write(cr, uid, period_state.id, {'auto_export_vi': True}, context=context)
                    nb_ok += 1
                    msg.append('[%s] %s done' % (time.strftime('%Y-%m-%d %H:%M:%S'), period_state.instance_id.code))
                    cr.commit()
                except Exception as e:
                    cr.rollback()
                    msg.append('ERROR %s %s' % (period_state.instance_id.code,misc.get_traceback(e)))
                    nb_error += 1

            for period_state_ids in list(instance_seen.items()):
                # overkill ? just in case of duplicates period_id / coordo_id
                p_state_obj.write(cr, uid, period_state_ids, {'auto_export_vi': True}, context=context)


        if nb_ok and export_wiz.pause:
            msg.append('[%s] pause for %s seconds' % (time.strftime('%Y-%m-%d %H:%M:%S'), export_wiz.pause))
            time.sleep(export_wiz.pause)

        if export_wiz.ftp_dest_ok:
            # send all reports (old + and new) to remote
            for filename in os.listdir(export_wiz.destination_local_path):
                fullfilename = os.path.join(export_wiz.destination_local_path, filename)
                try:
                    to_delete = '%s%s' % (fullfilename, self._delete_suffix)
                    if os.path.isfile(fullfilename) and (os.path.isfile(to_delete) or fullfilename.endswith(self._delete_suffix)):
                        self._delete_file(fullfilename)
                    elif os.path.isfile(fullfilename):
                        msg.append('[%s] sending %s to %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), fullfilename, export_wiz.dest_path))
                        export_job_obj.send_file(cr, uid, export_wiz, remote_con, fullfilename, export_wiz.dest_path, delete=False, context=context)
                        self._delete_file(fullfilename)
                        if disable_generation:
                            nb_ok += 1
                except Exception as e:
                    nb_error += 1
                    msg.append('ERROR %s %s' % (filename,  misc.get_traceback(e)))

        current_report_path = export_wiz.report_path
        if export_wiz.ftp_report_ok:
            # send all old log files
            current_report_path = export_wiz.report_local_path
            for filename in os.listdir(export_wiz.report_local_path):
                fullfilename = os.path.join(export_wiz.report_local_path, filename)
                try:
                    to_delete = '%s%s' % (fullfilename, self._delete_suffix)
                    if os.path.isfile(fullfilename) and (os.path.isfile(to_delete) or fullfilename.endswith(self._delete_suffix)):
                        self._delete_file(fullfilename)
                    elif os.path.isfile(fullfilename):
                        msg.append('[%s] sending %s to %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), fullfilename, export_wiz.report_path))
                        export_job_obj.send_file(cr, uid, export_wiz, remote_con, fullfilename, export_wiz.report_path, delete=False, context=context)
                        self._delete_file(fullfilename)
                        if disable_generation:
                            nb_ok += 1
                except Exception as e:
                    nb_error += 1
                    msg.append('ERROR %s %s' % (filename,  misc.get_traceback(e)))

        if msg:
            # generate the current log file and push to remote
            current_report = os.path.join(current_report_path, '%s_report.txt' % time.strftime('%Y-%m-%d-%H%M%S'))
            with open(current_report, 'w') as current_report_fp:
                current_report_fp.write("\n".join(msg))
            if export_wiz.ftp_report_ok:
                msg.append('[%s] sending %s to %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), current_report, export_wiz.report_path))
                try:
                    export_job_obj.send_file(cr, uid, export_wiz, remote_con, current_report, export_wiz.report_path, delete=False, context=context)
                    self._delete_file(current_report)
                except Exception as e:
                    nb_error += 1
                    msg.append('ERROR %s %s' % (current_report,  misc.get_traceback(e)))

        return nb_ok, nb_error, msg


class wizard_hq_report_oca(wizard_export_vi_finance):
    _name = "wizard.hq.report.oca"

    _export_filename = '{instance}_Y{year}P{month:02d}_formatted_data_D365_import_{date}.zip'
    _export_report_name = 'report.hq.oca'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('all', 'All lines'), ('unexported', 'Not yet exported')], string="Select", required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, time.strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'all',
    }


    def onchange_instance_id(self, cr, uid, ids, context=None):
        '''
        (US-226) Reset the period field when another prop. instance is selected.
        Cover the case when in HQ the user selects a period mission-closed in a coordo,
        and then select another coordo in which the period previously selected is not mission-closed
        '''
        res = {}
        res['value'] = {'period_id': False}
        return res

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        mission_code = ''
        year = ''
        period_number = ''
        if wizard.instance_id:
            mission_code = "%s" % wizard.instance_id.code[:3]
            # Get projects below instance
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        if wizard.period_id:
            tm = strptime(wizard.period_id.date_start, '%Y-%m-%d')
            year = str(tm.tm_year)
            period_number = wizard.period_id.number and '%02d' % wizard.period_id.number or ''
            data['form'].update({'period_id': wizard.period_id.id})
        # UFTP-375: Permit user to select all lines or only previous ones
        data['form'].update({'selection': wizard.selection})
        data['target_filename'] = '%sY%sP%s_formatted data D365 import' % (mission_code, year, period_number)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': 'hq.oca',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hq.oca',
            'datas': data,
            'context': context,
        }

wizard_hq_report_oca()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
