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
import xmlrpc.client

class ReplaceLoginField(openobject.widgets.PasswordField):
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
        super(ReplaceLoginField, self).__init__(*arg, **kwargs)

class DBForm(openobject.widgets.Form):
    strip_name = True
    display_string = False
    display_description = False

    def __init__(self, *args, **kw):
        super(DBForm, self).__init__(*args, **kw)
        to_add = []
        for field in self.fields:
            if isinstance(field, ReplaceLoginField):
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


class FormForgottenLogin(DBForm):
    name = "forgotten_login"
    string = _('Forgotten Login')
    action = '/openerp/forgotten_login/send'
    submit_text = _('Send reset link')

    fields = [
        openobject.widgets.TextField(
            name='email',
            label=_('Email'),
            validator=formencode.validators.Email(not_empty=True)
        )
    ]



_FORMS = {
    'forgotten_login': FormForgottenLogin()
}

class ForgottenLogin(BaseController):
    _inherit = 'res.users'
    _cp_path = "/openerp/forgotten_login"
    msg = {}

    def __init__(self, *args, **kwargs):
        super(ForgottenLogin, self).__init__(*args, **kwargs)
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


    @expose(template="/openerp/controllers/templates/forgotten_login.mako")
    def index(self, tg_errors=None, **kw):
        form = _FORMS['forgotten_login']
        error = self.msg
        self.msg = {}
        db_data = get_db_list()
        dblist = db_data.get('dblist', [])
        return dict(form=form, error=error, dblist=dblist, email="")

    @expose()
    @validate(form=_FORMS['forgotten_login'])
    @error_handler(index)
    def send(self, db, email, **kw):
        self.msg = {}

        try:
            result = session.execute_noauth(
                'common', 'send_login_email',
                db,
                email
            )

            self.msg = {
                'title': _('Success'),
                'message': _('User login has been sent to you via email')
            }
            return self.index()

        except Exception as e:
            cherrypy.log("ERROR: %s" % e)
            self.msg = {'title': _('Error'), 'message': ustr(e)}
            return self.index()
