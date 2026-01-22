import cherrypy
import openobject
from openobject.tools import expose, validate, error_handler, redirect, url
from openobject.i18n import _
from openobject import ustr
from openobject.controllers import BaseController
from openerp.utils.rpc import session
import formencode


class ResetPasswordForm(openobject.widgets.Form):
    name = "reset_password"
    string = _('Reset Password')
    action = '/openerp/reset_password/confirm'
    submit_text = _('Change password')

    fields = [
        openobject.widgets.PasswordField(
            name='password',
            label=_('New password'),
            validator=formencode.validators.NotEmpty()
        ),
        openobject.widgets.PasswordField(
            name='password2',
            label=_('Confirm password'),
            validator=formencode.validators.NotEmpty()
        ),
        openobject.widgets.HiddenField(
            name='token'
        ),
        openobject.widgets.HiddenField(
            name='db'
        ),
    ]


_FORM = ResetPasswordForm()


class ResetPassword(BaseController):
    _cp_path = "/openerp/reset_password"
    msg = {}

    def __init__(self, *args, **kwargs):
        super(ResetPassword, self).__init__(*args, **kwargs)
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


    @expose(template="/openerp/controllers/templates/reset_password.mako")
    def index(self, token=None, db=None, **kw):
        form = _FORM
        error = self.msg
        self.msg = {}
        return dict(form=form, error=error, token=token, db=db)


    @expose()
    @validate(form=_FORM)
    @error_handler(index)
    def confirm(self, password, password2, token, db, **kw):

        if password != password2:
            self.msg = {'title': _('Error'), 'message': _('Passwords do not match')}
            return self.index(token=token, db=db)

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
                'reset_password_from_token',
                token, password
            )

            session.logout()

            self.msg = {'title': _('Success'), 'message': _('Password changed successfully')}
            return self.index()

        except Exception as e:
            cherrypy.log("ERROR: %s" % e)
            self.msg = {'title': _('Error'), 'message': ustr(e)}
            return self.index(token=token, db=db)
