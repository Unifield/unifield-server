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
from openerp.controllers import SecuredController
from openerp.utils import rpc, TinyDict, TinyForm

from openobject.tools import expose

class FieldPref(SecuredController):

    _cp_path = "/openerp/fieldpref"

    def is_admin_profile(self):
        return rpc.RPCProxy('res.users').get_admin_profile()

    @expose(template="/openerp/controllers/templates/fieldpref.mako")
    def index(self, **kw): #_terp_model, _terp_field, _terp_deps


        click_ok = None
        params, data = TinyDict.split(kw)
        deps = params.deps
        return dict(model=params.model, click_ok=click_ok, field=params.field, deps=deps, admin_profile=self.is_admin_profile())

    @expose(template="/openerp/controllers/templates/fieldresetpref.mako")
    def reset_default(self, **kw):
        is_admin = self.is_admin_profile()
        params, data = TinyDict.split(kw)
        field = params.field.split('/')[-1]
        values_obj = rpc.RPCProxy('ir.values')
        dom = [('model', '=', params.model), ('name', '=', field), ('key', '=', 'default')]
        if not self.is_admin_profile():
            dom.append(('user_id', '=', rpc.session.uid))
        else:
            dom.append(('user_id', 'in', [rpc.session.uid, False]))


        fields = rpc.RPCProxy(params.model).fields_get(field, rpc.session.context)
        txt = fields.get(field,{}).get('string', '')

        val_ids = values_obj.search(dom, 0, 0, False, rpc.session.context)
        values = values_obj.read(val_ids, ['name', 'real_value', 'user_id', 'key2'], rpc.session.context)
        return dict(model=params.model, click_ok='', field=params.field, values=values, admin_profile=is_admin, string=txt)

    @expose(template="/openerp/controllers/templates/fieldresetpref.mako")
    def reset_apply(self, **kw):
        params, data = TinyDict.split(kw)
        if params.to_del:
            rpc.RPCProxy('ir.values').delete_default(list(params.to_del.values()), params.model, params.field.split('/')[-1])
        return dict(click_ok=1, model=params.model, field=params.field, values=[], admin_profile=self.is_admin_profile(), string=params.string)

    @expose('json')
    def get(self, **kw):
        params, data = TinyDict.split(kw)

        field = params.field.split('/')

        prefix = '.'.join(field[:-1])
        field = field[-1]

        pctx = TinyForm(**kw).to_python(safe=True)
        ctx = pctx.chain_get(prefix) or pctx

        fields = rpc.RPCProxy(params.model).fields_get(False, rpc.session.context)

        if field not in fields:
            return {}
        text = fields[field].get('string')
        deps = []

        for name, attrs in fields.items():
            if attrs.get('change_default'):
                value = ctx.get(name)
                if value:
                    deps.append((name, name, value, value))

        return dict(text=text, deps=str(deps))

    @expose(template="/openerp/controllers/templates/fieldpref.mako")
    def save(self, **kw):
        params, data = TinyDict.split(kw)

        deps = False
        if params.deps:
            for n, v in list(params.deps.items()):
                deps = "%s=%s" %(n,v)
                break

        model = params.model
        field = params.field['name']
        value = params.field['value']
        click_ok = 1

        field = field.split('/')[-1]

        proxy = rpc.RPCProxy('ir.values')
        proxy.set('default', deps, field, [(model,False)], value, True, False, 'web', params.you or False, True)

        return dict(model=params.model, click_ok=click_ok, field=params.field, deps=params.deps2, should_close=True)

# vim: ts=4 sts=4 sw=4 si et

