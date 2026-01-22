import re
import time
import cherrypy
import openobject
from openobject.tools import url, expose, validate, error_handler, redirect
from openobject.i18n import _
from openobject import ustr
from openobject.controllers import BaseController
from openerp.utils import rpc
from openerp import validators
import formencode
from openerp.controllers.utils import get_db_list
from openerp.utils.rpc import RPCProxy, session
import openobject
from openobject import pooler
import cherrypy

class ReplacePasswordField(openobject.widgets.PasswordField):
    params = {
        'autocomplete': 'Autocomplete field',
    }
    autocomplete = 'off'
    replace_for = False

    def __init__(self, *arg, **kwargs):
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
                to_add.append(openobject.widgets.HiddenField(name=field.replace_for, attrs={'autocomplete': 'off'}))
                self.replace_password_fields[field.name] = field.replace_for
        if to_add:
            self.hidden_fields += to_add
        if self.validator is openobject.validators.DefaultValidator:
            self.validator = openobject.validators.Schema()
        for f in self.fields:
            self.validator.add_field(f.name, f.validator)
        for add in to_add:
            self.validator.add_field(add.name, formencode.validators.NotEmpty())


class FormForgottenPassword(DBForm):
    name = "forgotten_password"
    string = _('Forgotten Password')
    action = '/openerp/forgotten_password/send'
    submit_text = _('Send reset link')

    fields = [
        openobject.widgets.TextField(
            name='user',
            label=_('User'),
            validator=formencode.validators.NotEmpty()
        ),
        openobject.widgets.TextField(
            name='email',
            label=_('Email'),
            validator=formencode.validators.Email(not_empty=True)
        )
    ]



_FORMS = {
    'forgotten_password': FormForgottenPassword()
}

class ForgottenPassword(BaseController):
    _inherit = 'res.users'
    _cp_path = "/openerp/forgotten_password"
    msg = {}

    def __init__(self, *args, **kwargs):
        super(ForgottenPassword, self).__init__(*args, **kwargs)
        self._msg = {}

    def get_msg(self):
        return self._msg

    def set_msg(self, msg):
        if 'title' in msg:
            msg['title'] = msg['title'].replace('\n', '')
        if 'message' in msg:
            msg['message'] = msg['message'].replace('\n', '')
        self._msg = msg

    msg = property(get_msg, set_msg)


    @expose(template="/openerp/controllers/templates/forgotten_password.mako")
    def index(self, tg_errors=None, **kw):
        form = _FORMS['forgotten_password']
        error = self.msg
        self.msg = {}
        db_data = get_db_list()
        dblist = db_data.get('dblist', [])
        return dict(form=form, error=error, user="", dblist=dblist, email="")

    @expose()
    @validate(form=_FORMS['forgotten_password'])
    @error_handler(index)
    def send(self, user, db, email, **kw):
        self.msg = {}

        try:
            # 1) login technique
            uid = session.execute_noauth('common', 'login', db, 'admin', 'admin')
            if uid <= 0:
                raise Exception("Technical login failed")

            session._logged_as(db, uid, 'admin')
            session.storage['open'] = True

            # 2) call res.users
            session.execute(
                'object', 'execute',
                'res.users',
                'send_reset_password_email',
                user, email
            )

            cherrypy.engine.subscribe(
                'after_request',
                lambda: session.logout()
            )

            self.msg = {
                'title': _('Success'),
                'message': _('Email envoyé !')
            }
            return self.index()

        except Exception as e:
            cherrypy.log("ERROR: %s" % e)
            self.msg = {'title': _('Error'), 'message': ustr(e)}
            return self.index()
