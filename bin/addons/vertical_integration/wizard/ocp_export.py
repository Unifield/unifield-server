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

import logging
from . import wizard_hq_report_oca

import uuid

class ocp_fin_sync(osv.osv):
    __logger = logging.getLogger('ocp.fin.sync')
    _name = 'ocp.fin.sync'
    _order = 'id desc'
    limit = 200
    _columns = {
        'model': fields.char('model', size=256, required=1),
        'confirmed': fields.boolean('Confirmed'),
        'max_auditrail_id': fields.integer('Last auditrail log'),
        'previous_auditrail_id': fields.integer('Last auditrail log'),
        'client_key': fields.char('Client Key', size=256, select=1),
        'session_name': fields.char('Session Name', size=256, select=1),
        'has_next_page': fields.boolean('Has next page'),
    }

    def generate_session(self, cr, uid, model, client_key, full=False):
        ret = {
            'success': True
        }
        try:
            if model not in self._objects:
                raise osv.except_osv('Error', 'Incorrect model name %s, must be %s' % (model, ' or '.join(self._objects)))

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
                'has_next_page': True,
            }
            if prev_id:
                prev_session = self.browse(cr, 1, prev_id[0])
                data['previous_auditrail_id'] = prev_session.max_auditrail_id

            self.create(cr, 1, data)
            ret['session'] = new_session

        except Exception as e:
            self.__logger.exception(e)
            cr.rollback()
            ret['success'] = False
            ret['error'] = '%s'%e

        return ret

    def _get_partner(self, cr, uid, session_id, page_offset):
        sess = self.browse(cr, 1, session_id)
        model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'res.partner')])[0]
        field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model_id', '=', model_id), ('name', '=', 'name')])

        cond = ''
        if not sess.previous_auditrail_id:
            # no TC entry for Local Market
            cond = " or p.name = 'Local Market' "

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
                ''' + cond + '''
            group by
                p.id, p.name
            order by p.id
            offset %s
            limit %s
        ''', (tuple(field_ids), model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page_offset*self.limit, self.limit+1)) # not_a_user_entry

        return [{'id': x[0] or '', 'name': x[1] or ''} for x in cr.fetchall()]

    def _get_hr_employee(self, cr, uid, session_id, page_offset):
        sess = self.browse(cr, 1, session_id)
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
        ''', (tuple(field_ids), ressource_model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page_offset*self.limit, self.limit+1))

        return [{'identification_id': x[0] or '', 'uuid': x[1] or '', 'name': x[2] or ''} for x in cr.fetchall()]

    def _get_journal_cash(self, cr, uid, session_id, page_offset):
        sess = self.browse(cr, 1, session_id)
        model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'account.journal')])[0]
        field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model_id', '=', model_id), ('name', 'in', ['name', 'code', 'currency', 'is_active', 'inactivation_date', 'instance_id'])])

        cond = ''
        if not sess.previous_auditrail_id:
            cond = ' or l.id is null '
        cr.execute('''
            select
                j.code, j.name, i.code, c.name, j.is_active, j.inactivation_date
            from
                account_journal j
                inner join res_currency c on c.id = j.currency
                inner join msf_instance i on i.id = j.instance_id
                left join audittrail_log_line l on l.field_id in %s and l.res_id = j.id and l.object_id = %s
            where
                j.type = 'cash' and (l.id > %s and l.id <= %s ''' + cond + ''')
            group by
                j.id, j.code, j.name, i.code, c.name, j.is_active, j.inactivation_date
            order by j.code, j.id
            offset %s
            limit %s
        ''', (tuple(field_ids), model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page_offset*self.limit, self.limit+1)) # not_a_user_entry

        return [{'code': x[0] or '', 'name': x[1] or '', 'mission': x[2] and x[2][0:3] or '', 'currency': x[3] or '', 'active': x[4], 'inactivation_date': x[5] or False} for x in cr.fetchall()]


    _objects = {
        'res.partner': _get_partner,
        'hr.employee': _get_hr_employee,
        'account.journal.cash': _get_journal_cash,
    }

    def get_record(self, cr, uid, session_name, page=1):
        ret = {
            'page': page,
            'limit': self.limit,
            'model': False,
            'session': session_name,
            'success': True,
            'records': [],
        }
        try:
            if not isinstance(page, int) or not page > 0:
                raise osv.except_osv('Error', 'Page attribute must be a positive integer and not zero')

            page_offset = page - 1
            sess_ids = self.search(cr, 1, [('session_name', '=', session_name), ('confirmed', '=', False)])
            if not sess_ids:
                raise osv.except_osv('Error', 'Session %s not found' % session_name)
            session_id = sess_ids[0]

            sess = self.browse(cr, 1, sess_ids[0])
            ret['model'] = sess.model

            if sess.model in self._objects:
                ret['records'] =  self._objects[sess.model](self, cr, uid, session_id, page_offset)

            if len(ret['records']) > self.limit:
                ret['records'].pop()
                ret['has_next_page'] = True
            else:
                ret['has_next_page'] = False

            self.write(cr, 1, session_id, {'has_next_page': ret['has_next_page']})
        except Exception as e:
            self.__logger.exception(e)
            cr.rollback()
            ret['success'] = False
            ret['error'] = '%s'%e

        return ret

    def confirm_session(self, cr, uid, session_name):
        ret = {
            'success': True
        }
        try:
            sess_ids = self.search(cr, 1, [('session_name', '=', session_name), ('confirmed', '=', False)])
            if not sess_ids:
                raise osv.except_osv('Error', 'Session %s not found' % session_name)
            sess_ids = self.search(cr, 1, [('session_name', '=', session_name), ('confirmed', '=', False), ('has_next_page', '=', False)])
            if not sess_ids:
                raise osv.except_osv('Error', 'Session %s has more records to retrieve.' % session_name)

            self.write(cr, 1, sess_ids, {'confirmed': True})
        except Exception as e:
            self.__logger.exception(e)
            cr.rollback()
            ret['success'] = False
            ret['error'] = '%s'%e

        return ret

    def _import_employee(self, cr, uid, data):
        hr_obj = self.pool.get('hr.employee')
        if not isinstance(data, dict):
            raise osv.except_osv('Error', "A dictionnary must by used: {'name': XXX, 'identification_id': YYY, 'section_code': 'FR'}")

        if not data.get('identification_id') or not data['identification_id'].strip():
            raise osv.except_osv('Error', '"identification_id" value cannot be empty (name: %s)' % (data.get('name'), ))
        identification_id = data['identification_id'].strip()

        if not data.get('name') or not data['name'].strip():
            raise osv.except_osv('Error', '"name" value cannot be empty (identification_id: %s)' % (identification_id, ))
        name = data['name'].strip()
        if not data.get('section_code'):
            raise osv.except_osv('Error', '"section_code" value cannot be empty (identification_id: %s)' % (identification_id, ))

        if data.get('section_code').lower() not in ('fr', 'nofr'):
            raise osv.except_osv('Error', '"section_code" value must be FR or NOFR (identification_id: %s)' % (identification_id, ))


        c_data = {
            'name': name,
            'section_code': data['section_code'].upper(),
            'employee_type': 'ex',
        }

        if data.get('creation_date'):
            try:
                time.strptime(data['creation_date'], '%Y-%m-%d')
                c_data['expat_creation_date'] = data['creation_date']
            except:
                raise osv.except_osv('Error', '"creation_date %s must be a date, format: YYYY-MM-DD' % (data['creation_date'], ))

        expat_id = hr_obj.search(cr, uid, [('identification_id', '=ilike', identification_id), ('employee_type', '=', 'ex'), ('active', 'in', ['t','f'])])

        if not expat_id:
            c_data['identification_id'] = identification_id
            c_data['active'] = False
            hr_obj.create(cr, uid, c_data)
            return 'created'

        if not hr_obj.search_exists(cr, uid, [('id', '=', expat_id[0]), ('name', '=', c_data['name']), ('section_code', '=', c_data['section_code']), ('active', 'in', ['t','f'])]):
            hr_obj.write(cr, uid, expat_id[0], c_data)
            return 'updated'

        return ''

    def import_employees(self, cr, uid, datas):
        updated = 0
        created = 0
        error = 0
        errors = []
        record = 0
        if isinstance(datas, dict):
            datas = [datas]
        elif not isinstance(datas, list):
            return {
                'success': False,
                'error': "Datas attribute must be a list of dictionnaries [{'name': XXX, 'identification_id': YYY, 'section_code': 'FR'}] or a single dictionnary {'name': XXX, 'identification_id': YYY, 'section_code': 'FR'}",
                'nb_errors': 1,
                'nb_created': 0,
                'nb_updated': 0,
                'nb_processed': 0,
            }

        for data in datas:
            try:
                cr.execute("SAVEPOINT import_expat")
                record += 1
                action = self._import_employee(cr, uid, data)
                if action == 'created':
                    created += 1
                elif action == 'updated':
                    updated += 1
                cr.execute("RELEASE SAVEPOINT import_expat")
            except Exception as e:
                self.__logger.exception('Record %d: %s' % (record, e))
                error += 1
                errors.append('Record %d: %s' % (record, e))
                cr.execute("ROLLBACK TO SAVEPOINT import_expat")

        if error:
            cr.rollback()
            return {
                'success': False,
                'nb_errors': error,
                'nb_created': 0,
                'nb_updated': 0,
                'nb_processed': record,
                'error': '\n'.join(errors),
            }
        return {
            'success': True,
            'nb_created': created,
            'nb_updated': updated,
            'nb_processed': record,
            'nb_errors': 0,
        }

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


class waca_fin_sync(osv.osv):
    _name = 'waca.fin.sync'
    _inherit = 'ocp.fin.sync'

    def _get_hr_employee(self, cr, uid, session_id, page_offset):
        sess = self.browse(cr, 1, session_id)
        ressource_model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'resource.resource')])[0]
        field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model', 'in', ['resource.resource', 'hr.employee']), ('name', 'in', ['name', 'identification_id', 'employee_type', 'instance_creator'])])

        cr.execute('''
            select
                e.identification_id, r.name, e.employee_type, e.instance_creator, e.id
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
        ''', (tuple(field_ids), ressource_model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page_offset*self.limit, self.limit+1))

        return [{'id': x[4], 'identification_id': x[0] or '', 'name': x[1] or '', 'type': x[2] or '', 'instance_creator': x[3] or ''} for x in cr.fetchall()]

    def _get_partner(self, cr, uid, session_id, page_offset):
        sess = self.browse(cr, 1, session_id)
        model_id = self.pool.get('ir.model').search(cr, 1, [('model', '=', 'res.partner')])[0]
        field_ids = self.pool.get('ir.model.fields').search(cr, 1, [('model_id', '=', model_id), ('name', 'in', ['name', 'partner_type', 'instance_creator'])])

        cond = ''
        if not sess.previous_auditrail_id:
            # no TC entry for Local Market
            cond = " or p.name = 'Local Market' "

        cr.execute('''
            select
                p.id, p.name, p.instance_creator, p.partner_type
            from
                res_partner p
            left join
                audittrail_log_line l on l.field_id in %s and l.res_id = p.id and l.object_id = %s
            where
                l.id > %s and
                l.id <= %s
                ''' + cond + '''
            group by
                p.id, p.name
            order by p.id
            offset %s
            limit %s
        ''', (tuple(field_ids), model_id, sess.previous_auditrail_id, sess.max_auditrail_id, page_offset*self.limit, self.limit+1)) # not_a_user_entry

        return [{'id': x[0] or '', 'name': x[1] or '', 'instance_creator': x[2] or '', 'partner_type': x[3] or ''} for x in cr.fetchall()]

    _objects = {
        'res.partner': _get_partner,
        'hr.employee': _get_hr_employee,
    }

waca_fin_sync()
