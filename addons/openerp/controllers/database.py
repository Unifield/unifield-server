###############################################################################
#
#  Copyright (C) 2007-TODAY OpenERP SA. All Rights Reserved.
#
#  $Id$
#
#  Developed by OpenERP (http://openerp.com) and Axelor (http://axelor.com).
#
#  The OpenERP web client is distributed under the "OpenERP Public License".
#  It's based on Mozilla Public License Version (MPL) 1.1 with following
#  restrictions:
#
#  -   All names, links and logos of OpenERP must be kept as in original
#      distribution without any changes in all software screens, especially
#      in start-up page and the software header, even if the application
#      source code has been changed or updated or code has been added.
#
#  You can see the MPL licence at: http://www.mozilla.org/MPL/MPL-1.1.html
#
###############################################################################
import base64
import re
import time
import os
import sys
import csv

import cherrypy
import formencode

from openobject import paths
from openobject import ustr
from openobject.controllers import BaseController
from openobject.tools import url, expose, redirect, validate, error_handler
import openobject
import openobject.errors
from openobject.i18n import _

from openerp import validators
from openerp.utils import rpc, get_server_version, is_server_local, serve_file
from tempfile import NamedTemporaryFile
import shutil
import configparser
from configparser import NoOptionError, NoSectionError
import threading

TRUE_LIST = (True, 'True', 'true', 'TRUE', 'Yes', 'YES', 'yes')
def get_lang_list():
    langs = [('en_US', 'English (US)')]
    try:
        return langs + (rpc.session.execute_db('list_lang') or [])
    except Exception:
        pass
    return langs

def get_db_list():
    try:
        return rpc.session.execute_db('list') or []
    except:
        return []

class DatabaseExist(Exception): pass

class ReplacePasswordField(openobject.widgets.PasswordField):
    params = {
        'autocomplete': 'Autocomplete field',
    }
    autocomplete = 'off'
    replace_for = False

    def __init__(self, *arg, **kwargs):
        # disable form default submit action when user hits Enter in the field
        self.replace_for = kwargs['name']
        kwargs['name'] = 'show_%s' % kwargs['name']
        kwargs.setdefault('attrs', {}).update({
            'onkeydown': 'if (event.keyCode == 13) replace_pass_submit()',
            'class': 'requiredfield',
        })
        super(ReplacePasswordField, self).__init__(*arg, **kwargs)


class DBForm(openobject.widgets.Form):
    strip_name = True
    display_string = False
    display_description = False

    def __init__(self, *args, **kw):
        super(DBForm, self).__init__(*args, **kw)
        to_add = []
        for field in self.fields:
            if isinstance(field, ReplacePasswordField):
                to_add.append(openobject.widgets.HiddenField(name=field.replace_for, attrs={'autocomplete':'off'}))
                self.replace_password_fields[field.name] = field.replace_for
        if to_add:
            self.hidden_fields += to_add
        if self.validator is openobject.validators.DefaultValidator:
            self.validator = openobject.validators.Schema()
        for f in self.fields:
            self.validator.add_field(f.name, f.validator)
        for add in to_add:
            self.validator.add_field(add.name, formencode.validators.NotEmpty())

    def update_params(self, params):
        super(DBForm, self).update_params(params)
        params['attrs']['action'] = url(self.action)

    def error_for(self, item, error):
        if error and isinstance(item, ReplacePasswordField):
            return error.error_dict.get(item.replace_for)
        return super(DBForm, self).error_for(item, error)

class FormCreate(DBForm):
    name = "create"
    string = _('Create database')
    action = '/openerp/database/do_create'
    submit_text = _('Create')
    strip_name = True
    form_attrs = {'onsubmit': 'return on_create()'}
    fields = [
        ReplacePasswordField(name='password', label=_('Super admin password:'), help=_("This is the password of the user that have the rights to administer databases. This is not a OpenERP user, just a super administrator.")),
        openobject.widgets.TextField(name='dbname', label=_('New database name:'), validator=formencode.validators.NotEmpty(), help=_("Choose the name of the database that will be created. The name must not contain any special character. Exemple: 'terp'.")),
        #       openobject.widgets.CheckBox(name='demo_data', label=_('Load Demonstration data:'), default=False, validator=validators.Bool(if_empty=False), help=_("Check this box if you want demonstration data to be installed on your new database. These data will help you to understand OpenERP, with predefined products, partners, etc.")),
        openobject.widgets.SelectField(name='language', options=get_lang_list, validator=validators.String(), label=_('Default Language:'), help=_("Choose the default language that will be installed for this database. You will be able to install new languages after installation through the administration menu.")),
        ReplacePasswordField(name='admin_password', label=_('Administrator password:'), help=_("This is the password of the 'admin' user that will be created in your new database.")),
        ReplacePasswordField(name='confirm_password', label=_('Confirm administrator password:'), help=_("This is the password of the 'admin' user that will be created in your new database. It has to be the same than the above field.")),
    ]
    validator = openobject.validators.Schema(chained_validators=[formencode.validators.FieldsMatch("admin_password","confirm_password")])


class FormAutoCreate(DBForm):
    name = "auto_create"
    string = _('Instance Auto Creation')
    action = '/openerp/database/do_auto_create'
    submit_text = _('Start auto creation')
    #form_attrs = {'onsubmit': 'return window.confirm(_("Do you really want to drop the selected database?"))'}
    fields = [
        ReplacePasswordField(name='password', label=_('Super admin password:')),
    ]


class AutoCreateProgress(DBForm):
    name = "get_auto_create_progress"
    string = _('Auto Creation Progress')
    action = '/openerp/database/get_auto_create_progress'


class FormDrop(DBForm):
    name = "drop"
    string = _('Drop database')
    action = '/openerp/database/do_drop'
    submit_text = _('Drop')
    form_attrs = {'onsubmit': 'return window.confirm(_("Do you really want to drop the selected database?"))'}
    fields = [
        openobject.widgets.SelectField(name='dbname', options=get_db_list, label=_('Database:'), validator=validators.String(not_empty=True)),
        ReplacePasswordField(name='password', label=_('Drop password:')),
    ]


class FormBackup(DBForm):
    name = "backup"
    string = _('Backup database')
    action = '/openerp/database/do_backup'
    submit_text = _('Backup')
    fields = [
        openobject.widgets.SelectField(name='dbname', options=get_db_list, label=_('Database:'), validator=validators.String(not_empty=True)),
        ReplacePasswordField(name='password', label=_('Backup password:')),
    ]


class FileField(openobject.widgets.FileField):
    def adjust_value(self, value, **params):
        return False


class FormRestore(DBForm):
    name = "restore"
    string = _('Restore database')
    action = '/openerp/database/do_restore'
    submit_text = _('Restore')
    fields = [
        FileField(name="filename", label=_('File:'), validator=openobject.validators.IteratorValidator()),
        ReplacePasswordField(name='password', label=_('Restore password:')),
        openobject.widgets.TextField(name='dbname', label=_('New database name:'), validator=formencode.validators.NotEmpty(), readonly=1, attrs={'readonly': ''})
    ]

    hidden_fields = [openobject.widgets.HiddenField(name='fpath', label=_('Path:'))]

class FormPassword(DBForm):
    name = "password"
    string = _('Change Administrator Password')
    action = '/openerp/database/do_password'
    submit_text = _('Change Password')
    fields = [
        ReplacePasswordField(name='old_password', label=_('Old super admin password:')),
        ReplacePasswordField(name='new_password', label=_('New super admin password:')),
        ReplacePasswordField(name='confirm_password', label=_('Confirm Password:')),
    ]
    validator = openobject.validators.Schema(chained_validators=[formencode.validators.FieldsMatch("new_password","confirm_password")])



_FORMS = {
    'auto_create': FormAutoCreate(),
    'create': FormCreate(),
    'drop': FormDrop(),
    'backup': FormBackup(),
    'restore': FormRestore(),
    'password': FormPassword()
}


class DatabaseCreationError(Exception): pass


class DatabaseCreationCrash(DatabaseCreationError): pass


class Database(BaseController):

    _cp_path = "/openerp/database"
    msg = {}

    def __init__(self, *args, **kwargs):
        super(Database, self).__init__(*args, **kwargs)
        self._msg = {}

    def get_msg(self):
        return self._msg

    def set_msg(self, msg):
        # msg will be displayed by javascript:
        # we need to remove some characters like '\n':
        if 'title' in msg:
            msg['title'] = msg['title'].replace('\n', '')
        if 'message' in msg:
            msg['message'] = msg['message'].replace('\n', '')
        self._msg = msg

    msg = property(get_msg, set_msg)

    def sanitize(self, msg):
        return msg.replace('\n', '<br />')

    @expose()
    def index(self, *args, **kw):
        self.msg = {}
        raise redirect('/openerp/database/create')

    @expose(template="/openerp/controllers/templates/database.mako")
    def create(self, tg_errors=None, **kw):

        error = self.msg
        self.msg = {}
        form = _FORMS['create']
        return dict(form=form, error=error)

    @expose()
    @validate(form=_FORMS['create'])
    @error_handler(create)
    def do_create(self, password, dbname, admin_password, confirm_password, demo_data=False, language=None, **kw):

        self.msg = {}
        if not re.match('^[a-zA-Z][a-zA-Z0-9_-]+$', dbname):
            self.msg = {'message': ustr(_("You must avoid all accents, space or special characters.")),
                        'title': ustr(_('Bad database name'))}
            return self.create()

        ok = False
        res = rpc.session.execute_db('check_super_password_validity', admin_password)
        if res is not True:
            self.msg = {'message': res,
                        'title': ustr(_('Bad admin password'))}
            return self.create()
        try:
            res = rpc.session.execute_db('create', password, dbname, demo_data, language, admin_password)
            while True:
                try:
                    progress, users = rpc.session.execute_db('get_progress', password, res)
                    if progress == 1.0:
                        for x in users:
                            if x['login'] == 'admin':
                                rpc.session.login(dbname, 'admin', x['password'])
                                ok = True
                        break
                    else:
                        time.sleep(1)
                except Exception:
                    raise DatabaseCreationCrash()
        except DatabaseCreationCrash:
            self.msg = {'message': (_("The server crashed during installation.\nWe suggest you to drop this database.")),
                        'title': (_('Error during database creation'))}
            return self.create()
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Bad super admin password'),
                        'title' : e.title}
            return self.create()
        except Exception:
            self.msg = {'message':_("Could not create database.")}
            return self.create()

        if ok:
            raise redirect('/openerp/menu', {'next': '/openerp/home'})
        raise redirect('/openerp/login', db=dbname)

    @expose(template="/openerp/controllers/templates/auto_create.mako")
    def auto_create(self, tg_errors=None, **kw):
        form = _FORMS['auto_create']
        error = self.msg
        self.msg = {}
        return dict(form=form, error=error)

    @expose()
    def get_auto_create_progress(self, **kw):
        config_file_name = 'uf_auto_install.conf'
        if sys.platform == 'win32':
            config_file_path = os.path.join(paths.root(), '..', 'UFautoInstall', config_file_name)
        else:
            config_file_path = os.path.join(paths.root(), '..', 'unifield-server', 'UFautoInstall', config_file_name)
        if not os.path.exists(config_file_path):
            return False
        config = configparser.ConfigParser()
        config.read(config_file_path)
        dbname = config.get('instance', 'db_name')
        self.resume, self.progress, self.state, self.error, monitor_status = rpc.session.execute_db('creation_get_resume_progress', dbname)
        my_dict = {
            'resume': self.resume,
            'progress': self.progress,
            'state': self.state,
            'error': self.error,
            'monitor_status': monitor_status,
        }
        import json
        return json.dumps(my_dict)

    @expose(template="/openerp/controllers/templates/auto_create_progress.mako")
    def auto_create_progress(self, tg_errors=None, **kw):
        finish = ""
        finished = "False"
        data_collected = "False"
        return dict(finish=finish, percent=self.progress, resume=self.resume, total=finished,
                    data_collected=data_collected)

    def check_not_empty_string(self, config, section, option):
        if not config.has_option(section, option) or not config.get(section, option):
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' cannot be empty, please set a value.') % (option, section)),
                        'title': ustr(_('Empty option'))}

    def check_mandatory_int(self, config, section, option):
        try:
            value = config.getint(section, option)
        except ValueError:
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' have to be a int.') % (option, section)),
                        'title': ustr(_('Wrong option value'))}
            return
        if not value:
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' cannot be empty, please set a value.') % (option, section)),
                        'title': ustr(_('Empty option'))}

    def check_possible_value(self, config, section, option, possible_values):
        value = config.get(section, option)
        if value not in possible_values:
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' have to be one of those values: %r. (currently it is \'%s\').') % (option, section, possible_values, value)),
                        'title': ustr(_('Wrong option'))}

    def check_boolean(self, config, section, option):
        if not config.has_option(section, option):
            return True
        try:
            config.getboolean(section, option)
            return True
        except Exception as e:
            self.msg = {
                'message': 'Option: %s, error: %s' % (option, ustr(e)),
                'title': _('Bad value'),
            }
            return False

    def check_date_time(self, config, section, option, time_format):
        if not config.has_option(section, option):
            return True
        value = config.get(section, option)
        if value:
            try:
                time.strptime(value, time_format)
            except:
                return False
        return True

    def check_datetime(self, config, section, option):
        if not self.check_date_time(config, section, option, '%Y-%m-%d %H:%M'):
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' datetime format expected YYY-MM-DD HH:MM') % (option, section)),
                        'title': ustr(_('Wrong format'))}

    def check_time(self, config, section, option):
        if not self.check_date_time(config, section, option, '%H:%M'):
            self.msg = {'message': ustr(_('The option \'%s\' from section \'[%s]\' time format expected HH:MM') % (option, section)),
                        'title': ustr(_('Wrong format'))}

    def check_config_file(self, file_path):
        '''
        perform some basic checks to avoid crashing later
        '''
        if not os.path.exists(file_path):
            self.msg = {'message': ustr(_("The auto creation config file '%s' does not exists.") % file_path),
                        'title': ustr(_('Auto creation file not found'))}

        config = configparser.ConfigParser()
        config.read(file_path)
        try:
            db_name = config.get('instance', 'db_name')
            if not re.match('^[a-zA-Z][a-zA-Z0-9_-]+$', db_name):
                self.msg = {'message': ustr(_("You must avoid all accents, space or special characters.")),
                            'title': ustr(_('Bad database name'))}
                return

            admin_password = config.get('instance', 'admin_password')
            res = rpc.session.execute_db('check_super_password_validity', admin_password)
            if res is not True:
                self.msg = {'message': res,
                            'title': ustr(_('Bad admin password'))}
                return

            # check the mandatory string fields have a value
            not_empty_string_option_list = (
                ('instance', 'oc'),
                ('instance', 'admin_password'),
                ('instance', 'sync_user'),
                ('instance', 'sync_pwd'),
                ('instance', 'sync_port'),
                ('instance', 'sync_host'),
                ('instance', 'sync_server'),
                ('instance', 'sync_protocol'),
                ('instance', 'instance_level'),
                ('instance', 'parent_instance'),
                ('instance', 'lang'),
                ('backup', 'auto_bck_path'),
                ('instance', 'prop_instance_code'),
                ('reconfigure', 'address_contact_name'),
                ('reconfigure', 'address_street'),
                ('reconfigure', 'address_city'),
                ('reconfigure', 'address_country'),
                ('reconfigure', 'delivery_process'),
                ('reconfigure', 'functional_currency'),
                ('company', 'default_cheque_account'),
                ('company', 'default_bank_account'),
                ('company', 'default_cash_account'),
            )
            for section, option in not_empty_string_option_list:
                self.check_not_empty_string(config, section, option)
                if self.msg:
                    return

            # check mandatory integer values
            not_empty_int_option_list = (
                ('backup', 'auto_bck_interval_nb'),
                ('partner', 'external_account_receivable'),
                ('partner', 'external_account_payable'),
                ('partner', 'internal_account_receivable'),
                ('partner', 'internal_account_payable'),
                ('autosync', 'interval_nb'),
                ('stockmission', 'interval_nb'),
            )
            for section, option in not_empty_int_option_list:
                self.check_mandatory_int(config, section, option)
                if self.msg:
                    return

            # check value is in possibles values
            possible_value_list = (
                ('instance', 'instance_level', ('coordo', 'project')),
                ('instance', 'lang', ('fr_MF', 'es_MF', 'en_MF')),
                ('backup', 'auto_bck_interval_unit', ('minutes', 'hours', 'work_days', 'days', 'weeks', 'months')),
                ('autosync', 'interval_unit', ('minutes', 'hours', 'work_days', 'days', 'weeks', 'months')),
                ('stockmission', 'interval_unit', ('minutes', 'hours', 'work_days', 'days', 'weeks', 'months')),
                ('reconfigure', 'delivery_process', ('complex', 'simple')),
            )
            for section, option, possible_values in possible_value_list:
                self.check_possible_value(config, section, option, possible_values)
                if self.msg:
                    return

            check_format = [
                ('backup', 'auto_bck_next_exec_date', self.check_datetime),
                ('autosync', 'next_exec_date', self.check_datetime),
                ('stockmission', 'next_exec_date', self.check_datetime),
                ('silentupgrade', 'hour_from', self.check_time),
                ('silentupgrade', 'hour_to', self.check_time),
                ('reconfigure', 'activate_international_invoices_lines', self.check_boolean),
                ('reconfigure', 'activate_fixed_asset', self.check_boolean),
                ('reconfigure', 'activate_electronic_validation', self.check_boolean),

            ]
            for section, option, check_fct in check_format:
                check_fct(config, section, option)
                if self.msg:
                    return

            if config.get('instance', 'instance_level') == 'project':
                if len(config.get('instance', 'group_names').split(',')) != 3:
                    self.msg = {
                        'message': _('Project creation asked, you must set 3 sync groups'),
                        'title': _('Bad sync groups'),
                    }
                    return

            if config.get('instance', 'instance_level') == 'coordo':
                if len(config.get('instance', 'group_names').split(',')) != 4:
                    self.msg = {
                        'message': _('Project creation asked, you must set 3 sync groups'),
                        'title': _('Bad sync groups'),
                    }
                    return

            if config.get('reconfigure', 'address_country'):
                if len(config.get('reconfigure', 'address_country')) != 2:
                    self.msg = {
                        'message': _('address_country %s must be a 2 characters country code') % (config.get('reconfigure', 'address_country'), ),
                        'title': _('Bad Country'),
                    }
                    return

            protocol = 'http'
            if config.get('instance', 'sync_protocol') in ('gzipxmlrpcs', 'xmlrpcs'):
                protocol = 'https'
            server_rpc = rpc.RPCSession(config.get('instance', 'sync_host'), config.get('instance', 'sync_port'), protocol=protocol)
            uid = server_rpc.login(config.get('instance', 'sync_server'), config.get('instance', 'sync_user'), config.get('instance', 'sync_pwd'))
            if uid <= 0:
                self.msg = {
                    'message': _('Unable to connect to Sync Server %s:%s,  db:%s, user:%s') % (config.get('instance', 'sync_host'), config.get('instance', 'sync_port'), config.get('instance', 'sync_server'), config.get('instance', 'sync_user')),
                    'title': _('Sync Server Error'),
                }
                return

            # silent uprade True only if autosync True
            if (not config.has_option('silentupgrade', 'active') or config.get('silentupgrade', 'active') in TRUE_LIST) and config.has_option('autosync', 'active') and config.get('autosync', 'active') not in TRUE_LIST:
                self.msg = {
                    'message': _('Silent Upgrade active value and Autosync active value are not consistent '),
                    'title': _('Auto sync / silent upgrade'),
                }
                return

            # check date betweens auto patch and sync scheduler
            if config.has_option('autosync', 'next_exec_date') and config.has_option('silentupgrade', 'hour_to') and config.has_option('silentupgrade', 'hour_from'):
                if (not config.has_option('autosync', 'active') or config.get('autosync', 'active') in TRUE_LIST) and (not config.has_option('silentupgrade', 'active') or config.get('silentupgrade', 'active') in TRUE_LIST):
                    time_from = time.strptime(config.get('silentupgrade', 'hour_from'), '%H:%M')
                    time_to = time.strptime(config.get('silentupgrade', 'hour_to'), '%H:%M')
                    if not server_rpc.execute('object', 'execute', 'sync.client.sync_server_connection', 'is_automatic_patching_allowed',
                                              config.get('autosync', 'next_exec_date'), True, time_from.tm_hour + time_from.tm_min/60. , time_to.tm_hour + time_to.tm_min/60.
                                              ):
                        self.msg = {
                            'message': _('"Scheduler autosync next date" and "Silent Upgrade interval" are not consistent'),
                            'title': _('Auto sync / silent upgrade'),
                        }
                        return
            config_groups = config.get('instance', 'group_names').split(',')
            found_group = []
            groups_ids = server_rpc.execute('object', 'execute', 'sync.server.entity_group', 'search', [('name', 'in', config_groups)])
            for x in server_rpc.execute('object', 'execute', 'sync.server.entity_group', 'read', groups_ids, ['name', 'oc']):
                found_group.append(x['name'])
                if x['oc'].lower() != config.get('instance', 'oc').lower():
                    self.msg = {
                        'message': _('Group %s has not the same OC (configured: %s)') % (x['name'], config.get('instance', 'oc')),
                        'title': _('Sync Group'),
                    }
                    return

            if set(config_groups) - set(found_group):
                self.msg = {
                    'message': _('Sync Groups %s not found on sync server') % (", ".join(list(set(config_groups) - set(found_group)),)),
                    'title': _('Sync Group'),
                }
                return

            if not server_rpc.execute('object', 'execute', 'sync.server.entity', 'search', [('name', '=', config.get('instance', 'parent_instance'))]):
                self.msg = {
                    'message': _('Parent Instance %s not found on sync server') % (config.get('instance', 'parent_instance'), ),
                    'title': _('Parent Instance'),
                }
                return

            if not server_rpc.execute('object', 'execute', 'sync.server.update', 'search', [('model', '=', 'msf.instance'), ('values', 'like', "'%s'" % config.get('instance', 'prop_instance_code'))]):
                self.msg = {
                    'message': _('No update found for %s. Did you create and sync. the new prop. instance at HQ ?') % (config.get('instance', 'prop_instance_code'), ),
                    'title': _('HQ creation'),
                }
                return

            import_path = os.path.join(os.path.dirname(file_path), 'import')
            if os.path.exists(import_path):
                for file_name in os.listdir(import_path):
                    if file_name.endswith('.imported'):
                        continue
                    if not file_name.endswith('.csv'):
                        self.msg = {
                            'message': 'File to import %s: incorrect name (must end with .csv)' % file_name,
                            'title': 'File name error',
                        }
                        return
                    import_object = file_name.split('.csv')[0]
                    if not server_rpc.execute('object', 'execute', 'ir.model', 'search', [('model', '=', import_object)]):
                        self.msg = {
                            'message': 'File to import %s: incorrect name object %s does not exist' % (file_name, import_object),
                            'title': 'File name error',
                        }
                        return
                    if file_name == 'res.users.csv':
                        with open(os.path.join(import_path, file_name), 'r') as fcsv:
                            reader = csv.reader(fcsv, quotechar='"', delimiter=',')
                            line_num = 0
                            for row in reader:
                                line_num += 1
                                if line_num == 1:
                                    if row != ['login', 'groups_id', 'new_password']:
                                        self.msg = {
                                            'message': 'File to import %s: 1st line must be login,groups_id,new_password' % (file_name),
                                            'title': 'File name error',
                                        }
                                        return
                                else:
                                    if len(row) and len(row)!=3:
                                        self.msg = {
                                            'message': 'File to import %s: line %d must have 3 columns' % (file_name, line_num),
                                            'title': 'File name error',
                                        }
                                        return
                                    res = rpc.session.execute_db('check_password_validity', row[0], row[2])
                                    if res is not True:
                                        self.msg = {
                                            'message': res,
                                            'title': ustr(_('Bad password line %d, user %s') % (line_num, row[0]))
                                        }
                                        return




        except NoOptionError as e:
            self.msg = {'message': ustr(_('No option \'%s\' found for the section \'[%s]\' in the config file \'%s\'') % (e.option, e.section, file_path)),
                        'title': ustr(_('Option missing in configuration file'))}
            return
        except NoSectionError as e:
            self.msg = {'message': ustr(_('No section \'%s\' found in the config file \'%s\'') % (e.section, file_path)),
                        'title': ustr(_('Option missing in configuration file'))}
            return

    def database_creation(self, password, dbname, admin_password):
        try:
            res = rpc.session.execute_db('create', password, dbname, False, 'en_US', admin_password)
            while True:
                try:
                    progress, users = rpc.session.execute_db('get_progress', password, res)
                    if progress == 1.0:
                        for x in users:
                            if x['login'] == 'admin':
                                rpc.session.login(dbname, 'admin', x['password'])
                        break
                    else:
                        time.sleep(1)
                except Exception:
                    raise DatabaseCreationCrash()
        except DatabaseCreationCrash:
            self.msg = {'message': (_("The server crashed during installation.\nWe suggest you to drop this database.")),
                        'title': (_('Error during database creation'))}
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Bad super admin password'),
                        'title' : e.title}

    def background_auto_creation(self, password, dbname, config_dict):
        rpc.session.execute_db('instance_auto_creation', password, dbname)
        self.resume, self.progress, self.state, self.error, monitor_status = rpc.session.execute_db('creation_get_resume_progress', dbname)

    @expose()
    @validate(form=_FORMS['auto_create'])
    @error_handler(auto_create)
    def do_auto_create(self, password, **kw):
        self.msg = {}
        self.progress = 0.03
        self.state = 'draft'
        try:
            config_file_name = 'uf_auto_install.conf'
            if sys.platform == 'win32':
                config_file_path = os.path.join(paths.root(), '..', 'UFautoInstall', config_file_name)
            else:
                config_file_path = os.path.join(paths.root(), '..', 'unifield-server', 'UFautoInstall', config_file_name)

            self.check_config_file(config_file_path)
            if self.msg:
                return self.auto_create()
            config = configparser.ConfigParser()
            config.read(config_file_path)

            config_dict =  {x:dict(config.items(x)) for x in config.sections()}
            dbname = config_dict['instance'].get('db_name')
            db_exists = False

            # check the database not already exists
            if dbname in get_db_list():
                db_exists = True
                self.resume = _('Database with this name exists, resume from the last point...\n')
            else:
                self.resume = _('Empty database creation in progress...\n')
                #raise DatabaseExist

            if not db_exists:
                # create database
                self.database_creation(password, dbname, config_dict['instance'].get('admin_password'))

            create_thread = threading.Thread(target=self.background_auto_creation,
                                             args=(password, dbname, config_dict)
                                             )
            create_thread.start()
            create_thread.join(0.5)

        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Wrong password'),
                        'title' : e.title}
        except DatabaseExist:
            pass
            #self.msg = {'message': ustr(_('The database already exist')),
            #            'title': 'Database exist'}
        except Exception as e:
            self.msg = {'message' : _("Could not auto create database: %s") % e}

        if self.msg:
            return self.auto_create()
        return self.auto_create_progress()

    @expose(template="/openerp/controllers/templates/database.mako")
    def drop(self, tg_errors=None, **kw):
        form = _FORMS['drop']
        error = self.msg
        self.msg = {}
        return dict(form=form, error=error)

    @expose()
    @validate(form=_FORMS['drop'])
    @error_handler(drop)
    def do_drop(self, dbname, password, **kw):
        self.msg = {}
        try:
            if not rpc.session.execute_db('connected_to_prod_sync_server',
                                          dbname):
                rpc.session.execute_db('drop', password, dbname)
            else:
                self.msg = {'message': _('You are trying to delete a production database, please disconnect from sync server before to delete it.'),
                            'title': 'Producion database deletion'}
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Wrong password'),
                        'title' : e.title}
        except Exception:
            self.msg = {'message' : _("Could not drop database")}

        return self.drop()

    @expose(template="/openerp/controllers/templates/database.mako")
    def backup(self, tg_errors=None, **kw):
        form = _FORMS['backup']
        error = self.msg
        self.msg = {}
        return dict(form=form, error=error)

    @expose()
    @validate(form=_FORMS['backup'])
    @error_handler(backup)
    def do_backup(self, dbname, password, **kw):
        self.msg = {}
        try:
            filename = [dbname, time.strftime('%Y%m%d-%H%M%S')]
            version = get_server_version(dbname)
            if version:
                filename.append(version)

            if is_server_local():
                res = rpc.session.execute_db('dump_file', password, dbname)
                try:
                    return serve_file.serve_file(res, "application/x-download", 'attachment', '%s.dump' % '-'.join(filename), delete=True)
                finally:
                    if os.path.exists(res):
                        os.remove(res)
            else:
                res = rpc.session.execute_db('dump', password, dbname)
                if res:
                    cherrypy.response.headers['Content-Type'] = "application/data"
                    cherrypy.response.headers['Content-Disposition'] = 'filename="%s.dump"' % '-'.join(filename)
                    return base64.b64decode(res)
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Wrong password'),
                        'title' : e.title}
            return self.backup()
        except Exception:
            self.msg = {'message' : _("Could not create backup.")}
            return self.backup()
        raise redirect('/openerp/login')

    @expose(template="/openerp/controllers/templates/database.mako")
    def restore(self, tg_errors=None, **kw):
        form = _FORMS['restore']
        error = self.msg
        self.msg = {}
        return dict(form=form, error=error)

    @expose()
    @validate(form=_FORMS['restore'])
    @error_handler(restore)
    def do_restore(self, filename, password, dbname=None, **kw):
        self.msg = {}
        if getattr(filename, 'filename', ''):
            submitted_filename = filename.filename
            matches = re.search('^(.*)-[0-9]{8}-[0-9]{6}(?:-(.*))?.dump$', submitted_filename)
            if matches:
                dbname = matches.group(1)
                #if matches.group(2):
                #    server_version = get_server_version()
                #    if server_version and server_version != matches.group(2):
                #        self.msg = {
                #            'message': _('The restore version (%s) and the server version (%s) differ') % (matches.group(2), server_version),
                #            'title': _('Error')
                #        }
                #        return self.restore()
            else:
                self.msg = {'message': _('The choosen file in not a valid database file'),
                            'title': _('Error')}
                return self.restore()
        try:
            if is_server_local():
                if not filename.filename and kw.get('fpath'):
                    filename = kw.get('fpath')
                else:
                    newfile = NamedTemporaryFile(delete=False)
                    shutil.copyfileobj(filename.file, newfile)
                    filename = newfile.name
                    newfile.close()
                rpc.session.execute_db('restore_file', password, dbname, filename)
            else:
                data = base64.b64encode(filename.file.read())
                rpc.session.execute_db('restore', password, dbname, data)
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Wrong password'),
                        'title' : e.title}
            if hasattr(cherrypy.request, 'input_values') and filename:
                cherrypy.request.input_values['fpath'] = filename
            return self.restore()
        except Exception as e:
            msg = _("Could not restore database")
            if isinstance(e, openobject.errors.TinyException):
                if 'Database already exists' in e.message:
                    msg = _("Could not restore: database already exists")
            self.msg = {'message': msg}
            return self.restore()
        raise redirect('/openerp/login', db=dbname)

    @expose(template="/openerp/controllers/templates/database.mako")
    def password(self, tg_errors=None, **kw):
        form = _FORMS['password']
        error = self.msg
        self.msg = {}
        return dict(form=form, error = error)

    @validate(form=_FORMS['password'])
    @error_handler(password)
    @expose()
    def do_password(self, old_password, new_password, confirm_password, **kw):
        self.msg = {}
        try:
            rpc.session.execute_db('change_admin_password', old_password, new_password)
            self.msg = {'message': _('The super admin password has been '
                                     'successfully changed. As a consequence, '
                                     'you must back up the configuration files.\\n'
                                     'Please refer to the documentation on how to do it.'),
                        'title': _('Information'),
                        'redirect_to': '/openerp/login'}
            return self.password()
        except openobject.errors.AccessDenied as e:
            self.msg = {'message': _('Bad super admin password'),
                        'title' : e.title}
            return self.password()
        except Exception:
            self.msg = {'message': _("Error, password not changed.")}
            return self.password()
        raise redirect('/openerp/login')

# vim: ts=4 sts=4 sw=4 si et
