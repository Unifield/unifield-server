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
from account_override import finance_export

import time
from time import strftime
from time import strptime

#from . import wizard_export_vi_finance
from . import wizard_hq_report_oca

import uuid

class ocp_fin_sync(osv.osv):
    _name = 'ocp.fin.sync'
    _order = 'id desc'
    _columns = {
        'model': fields.char('model', size=256, required=1),
        'confirmed': fields.boolean('Confirmed'),
        'max_auditrail_id': fields.integer('Last auditrail log'),
        'previous_auditrail_id': fields.integer('Last auditrail log'),
        'client_key': fields.char('Client Key', size=256, select=1),
        'session_name': fields.char('Session Name', size=256, select=1),
    }

    def generate_session(self, cr, uid, model, client_key, full=False):
        ret = {
            'result': 'OK'
        }
        try:
            models = ['res.partner', 'hr.employee', 'account.journal.cash']
            if model not in models:
                raise osv.except_osv('Error', 'Incorrect model name %s, must be %s' % (model, ' or '.join(models)))

            new_session = '%s'%uuid.uuid4()
            prev_id = False
            if not full:
                prev_id = self.search(cr, 1, [('model', '=', model), ('client_key', '=', client_key), ('confirmed', '=', True)], order='id desc', limit=1)

            max_audit_id = self.pool.get('audittrail.log.line').search(cr, 1, [], order='id desc', limit=1)
            data = {
                'session_name': new_session,
                'client_key': client_key,
                'confirmed': False,
                'max_auditrail_id': max_audit_id and max_audit_id[0] or False,
                'model': model,
                'previous_auditrail_id': 0,
            }
            if prev_id:
                prev_session = self.browse(cr, uid, prev_id[0])
                data['previous_auditrail_id'] = prev_session.max_auditrail_id

            self.create(cr, 1, data)
            ret['session'] = new_session

        except Exception as e:
            cr.rollback()
            ret['result'] = 'KO'
            ret['error'] = '%s'%e

        return ret

    def get_record(self, cr, uid, session_name, page=0):
        limit = 200
        ret = {
            'page': page,
            'limit': limit,
            'model': False,
            'session': session_name,
            'result': 'OK',
            'records': [],
        }
        try:
            sess_ids = self.search(cr, 1, [('session_name', '=', session_name), ('confirmed', '=', False)])
            if not sess_ids:
                raise osv.except_osv('Error', 'Session %s not found' % session_name)

            sess = self.browse(cr, 1, sess_ids[0])
            ret['model'] = sess.model
            if sess.model == 'res.partner':
                model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'res.partner')])[0]
                field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model_id', '=', model_id), ('name', '=', 'name')])

                cr.execute('''
                    select
                        p.id, p.name
                    from
                        res_partner p
                    left join
                        audittrail_log_line l on l.field_id in %s and l.res_id = p.id and l.object_id = %s
                    where
                        l.id > %s and
                        l.id <= %s
                    group by
                        p.id, p.name
                    order by p.id
                    offset %s
                    limit %s
                ''', (tuple(field_ids), model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page*limit, limit))

                ret['records'] = [{'id': x[0] or '', 'name': x[1] or ''} for x in cr.fetchall()]

            elif sess.model == 'hr.employee':
                ressource_model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'resource.resource')])[0]
                field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model', 'in', ['resource.resource', 'hr.employee']), ('name', 'in', ['name', 'homere_uuid_key', 'identification_id'])])

                cr.execute('''
                    select
                        e.identification_id, e.homere_uuid_key, r.name
                    from
                        hr_employee e
                        inner join resource_resource r on r.id = e.resource_id
                        left join audittrail_log_line l on l.field_id in %s and l.res_id = r.id and l.object_id = %s
                    where
                        l.id > %s and
                        l.id <= %s and
                        e.employee_type = 'local'
                    group by
                        e.id, e.identification_id, e.homere_uuid_key, r.name
                    order by e.id
                    offset %s
                    limit %s
                ''', (tuple(field_ids), ressource_model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page*limit, limit))

                ret['records'] = [{'identification_id': x[0] or '', 'uuid': x[1] or '', 'name': x[2] or ''} for x in cr.fetchall()]

            elif sess.model == 'account.journal.cash':
                model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'account.journal')])[0]
                field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model_id', '=', model_id), ('name', 'in', ['name', 'code', 'currency', 'is_active', 'inactivation_date', 'instance_id'])])

                cr.execute('''
                    select
                        j.code, j.name, i.code, c.name, j.is_active, j.inactivation_date
                    from
                        account_journal j
                        inner join res_currency c on c.id = j.currency
                        inner join msf_instance i on i.id = j.instance_id
                        left join audittrail_log_line l on l.field_id in %s and l.res_id = j.id and l.object_id = %s
                    where
                        l.id > %s and
                        l.id <= %s and
                        j.type = 'cash'
                    group by
                        j.id, j.code, j.name, i.code, c.name, j.is_active, j.inactivation_date
                    order by j.code, j.id
                    offset %s
                    limit %s
                ''', (tuple(field_ids), model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page*limit, limit))

                ret['records'] = [{'code': x[0] or '', 'name': x[1] or '', 'mission': x[2] and x[2][0:3] or '', 'currency': x[3] or '', 'active': x[4], 'inactivation_date': x[5] or False} for x in cr.fetchall()]

        except Exception as e:
            cr.rollback()
            ret['result'] = 'KO'
            ret['error'] = '%s'%e

        return ret

    def confirm_session(self, cr, uid, session_name):
        ret = {
            'result': 'OK'
        }
        try:
            sess_ids = self.search(cr, 1, [('session_name', '=', session_name), ('confirmed', '=', False)])
            if not sess_ids:
                raise osv.except_osv('Error', 'Session %s not found' % session_name)
            self.write(cr, 1, sess_ids, {'confirmed': True})
        except Exception as e:
            cr.rollback()
            ret['result'] = 'KO'
            ret['error'] = '%s'%e

        return ret

ocp_fin_sync()



class ocp_export_wizard(wizard_hq_report_oca.wizard_export_vi_finance):
    _name = "ocp.export.wizard"
    _export_filename = '{instance}_Y{year}P{month:02d}_formatted_data_workday_{date}.zip'
    _export_report_name = 'report.hq.ocp.workday'
    _export_extra_data = {
        'export_type': 'workday'
    }

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance'),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'all_missions': fields.boolean('All Missions', help="Generate the Monthly Export (only) for all missions at once"),
        # a warning is displayed in case the DB name is not "OCP_HQ" (export done from a coordo or from a test environment),
        # as this impacts the DB ID column
        'warning_db_name': fields.boolean('Display a warning on database name', invisible=True, readonly=True),
        'export_type': fields.selection([('arcole', 'Arcole'), ('workday', 'Workday')], string='export type', readonly=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
        'all_missions': False,
        'warning_db_name': lambda self, cr, uid, c: cr.dbname != 'OCP_HQ',
        'export_type': lambda self, cr, uid, c: c and c.get('export_type') or 'arcole',
    }

    def onchange_instance_id(self, cr, uid, ids, instance_id, context=None):
        """
        - Resets the period field when another prop. instance is selected.
          Covers the case when in HQ the user selects a period mission-closed in a coordo,
          and then select another coordo in which the period previously selected is not mission-closed.
        - Also resets the tick box "All Missions" as soon as a Prop. Instance is selected.
        """
        res = {}
        res['value'] = {'period_id': False}
        if instance_id:
            res['value'].update({'all_missions': False})
        return res

    def onchange_all_missions(self, cr, uid, ids, all_missions, context=None):
        """
        Resets the Prop. Instance field when "All Missions" is ticked
        """
        res = {}
        if all_missions:
            res['value'] = {'instance_id': False}
        return res

    def button_ocp_export_to_hq(self, cr, uid, ids, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        inst = None
        all_missions = False
        instance_ids = []
        period = None
        if wizard.all_missions:
            all_missions = True
            instance_ids = self.pool.get('msf.instance').search(cr, uid, [('level', '!=', 'section')], order='NO_ORDER', context=context)
        elif wizard.instance_id:
            # Get projects below instance
            inst = wizard.instance_id
            instance_ids = [inst.id] + [x.id for x in inst.child_ids]
        data['form'].update({
            'instance_id': inst and inst.id or None,
            'instance_ids': instance_ids,
            'all_missions': all_missions,
        })
        if wizard.period_id:
            period = wizard.period_id
            data['form'].update({'period_id': period.id})
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        # The file name is composed of:
        # - the first 3 characters of the Prop. Instance code or "Allinstances"
        # - the year and month of the selected period
        # - the current datetime
        # Ex: KE1_201609_171116110306_Formatted_data_UF_to_OCP_HQ_System
        if all_missions:
            prefix = 'Allinstances'
        elif inst:
            prefix = inst.code[:3]
        else:
            prefix = ''
        selected_period = period and strftime('%Y%m', strptime(period.date_start, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        data['target_filename'] = '%s_%s_%s_Formatted_data_UF_to_OCP_HQ_System' % (prefix, selected_period, current_time)


        internal_report_name = 'hq.ocp'
        if wizard.export_type == 'workday':
            internal_report_name = 'hq.ocp.workday'

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': internal_report_name,
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        report_name = _("Export to HQ system (OCP)")
        finance_export.log_vi_exported(self, cr, uid, report_name, wizard.id, data['target_filename'])

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': internal_report_name,
            'datas': data,
            'context': context,
        }

ocp_export_wizard()
