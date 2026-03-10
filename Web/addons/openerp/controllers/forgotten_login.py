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
from openerp.controllers.password_utils import ReplaceField, DBForm

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
    def index(self, tg_errors=None, data=None, **kw):
        form = _FORMS['forgotten_login']
        error = self.msg
        self.msg = {}

        db_data = get_db_list()
        dbfilter = cherrypy.request.app.config['openerp-web'].get('dblist.filter')
        dblist = db_data.get('dblist', [])
        db_from_url = kw.get('db')

        if db_from_url and db_from_url in dblist:
            dblist.remove(db_from_url)
            dblist.insert(0, db_from_url)

        if not db_from_url and (dbfilter != 'EXACT' or len(dblist) != 1):
            dblist = [''] + dblist

        data = data or {}
        return dict(form=form, error=error, dblist=dblist, data=data)

    @expose()
    @validate(form=_FORMS['forgotten_login'])
    @error_handler(index)
    def send(self, db, email, **kw):
        self.msg = {}

        try:
            if not all([email, db]):
                self.msg = {
                    'title': _('Error'),
                    'message': _('All fields are required')
                }
                return self.index(data={
                    'email': email,
                    'db': db
                })

            mail_ok = session.execute_noauth(
                'common',
                'is_mail_configured',
                db
            )
            if not mail_ok:
                self.msg = {
                    'title': _('Configuration Error'),
                    'message': _('Email server is not configured')
                }
                return self.index()

            session.execute_noauth(
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
            return self.index(data={
                'email': email,
                'db': db
            })
