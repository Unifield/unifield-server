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
import base64,re

import cherrypy
from openerp import utils, widgets as tw
from openerp.controllers import SecuredController
from openerp.utils import rpc, common, TinyDict, TinyForm, expr_eval, serve_file
from .error_page import _ep
from openobject.tools import expose, redirect, validate, error_handler, exception_handler
import openobject
import openobject.paths
from openobject import ustr
from openobject.i18n import _

FIELDS_INTERNAL_NAME = '__openerp__real_fiels'

def make_domain(name, value, kind='char'):
    """A helper function to generate domain for the given name, value pair.
    Will be used for search window...
    """

    if isinstance(value, int) and not isinstance(value, bool):
        return [(name, '=', value)]

    if isinstance(value, dict):

        start = value.get('from')
        end = value.get('to')

        if start and end:
            return [(name, '>=', start), (name, '<=', end)]

        elif start:
            return [(name, '>=', start)]

        elif end:
            return [(name, '<=', end)]

        return None

    if kind == "selection" and value:
        return [(name, '=', value)]

    if isinstance(value, str) and value:
        return [(name, 'ilike', value)]

    if isinstance(value, bool) and value:
        return [(name, '=', 1)]

    return []

def search(model, offset=0, limit=50, domain=[], context={}, data={}):
    """A helper function to search for data by given criteria.

    @param model: the resource on which to make search
    @param offset: offset from when to start search
    @param limit: limit of the search result
    @param domain: the domain (search criteria)
    @param context: the context
    @param data: the form data

    @returns dict with list of ids count of records etc.
    """

    domain = domain or []
    context = context or {}
    data = data or {}

    proxy = rpc.RPCProxy(model)
    fields = proxy.fields_get([], rpc.session.context)

    search_domain = domain[:]
    search_data = {}

    for k, v in data.items():
        t = fields.get(k, {}).get('type', 'char')
        t = make_domain(k, v, t)

        if t:
            search_domain += t
            search_data[k] = v

    l = limit
    o = offset

    if l < 1: l = 50
    if o < 0: o = 0

    ctx = rpc.session.context.copy()
    ctx.update(context)

    ids = proxy.search(search_domain, o, l, 0, ctx)
    if len(ids) < l:
        count = len(ids)
    else:
        count = proxy.search_count(search_domain, ctx)

    if isinstance(ids, list):
        count = len(ids)

    return dict(model=model, ids=ids, count=count, offset=o, limit=l,
                search_domain=search_domain, search_data=search_data)

def get_validation_schema(self):
    """Generate validation schema for the given Form instance. Should be used
    to validate form inputs with @validate decorator.

    @param self: and instance of Form

    @returns a new instance of Form with validation schema
    """

    kw = cherrypy.request.params
    params, data = TinyDict.split(kw)

    # bypass validations, if saving from button in non-editable view
    if params.button and not params.editable and params.id:
        return None

    cherrypy.request.terp_validators = {}
    cherrypy.request.terp_data = data

    params.nodefault = True
    params.validation_form = True

    # validation from wizard popup: hide save/edit buttons and attachements sidebar if fields (date) validation fails
    target = params._terp_view_target
    if target in ('new', 'same'):
        # tw.form_view.ViewForm uses params.target to display or not the sidebar
        params.target = target

        # create_from uses cherrypy.request._terp_view_target to hide save/save&edit button on wizard
        cherrypy.request._terp_view_target = target

    form = self.create_form(params)
    cherrypy.request.terp_form = form

    vals = cherrypy.request.terp_validators
    keys = vals.keys()
    to_remove =[]
    for k in keys:
        if k not in kw:
            to_remove.append(k)

    for k in to_remove:
        vals.pop(k)

    if 'fields' in vals:
        vals[FIELDS_INTERNAL_NAME] = vals.pop('fields')
    form.validator = openobject.validators.Schema(**vals)
    if FIELDS_INTERNAL_NAME in vals:
        form.validator.fields['fields'] = form.validator.fields.pop(FIELDS_INTERNAL_NAME)
    return form

def default_error_handler(self, tg_errors=None, **kw):
    """ Error handler for the given Form instance.

    @param self: an instance for Form
    @param tg_errors: errors
    """
    params, data = TinyDict.split(kw)
    return self.create(params, tg_errors=tg_errors)

def default_exception_handler(self, tg_exceptions=None, **kw):
    """ Exception handler for the given Form instance.

    @param self: an instance for Form
    @param tg_exceptions: exception
    """
    # let _cp_on_error handle the exception
    raise tg_exceptions

class Form(SecuredController):

    _cp_path = "/openerp/form"

    def create_form(self, params, tg_errors=None):
        if tg_errors:
            return cherrypy.request.terp_form

        params.offset = params.offset or 0
        params.count = params.count or 0
        params.approximation = params.approximation or False
        params.view_type = params.view_type or params.view_mode[0]
        target = getattr(cherrypy.request, '_terp_view_target', None)
        if target in ('new', 'same'):
            # for target='new' keep orignal value as '_terp_view_target' hidden field,
            # that's necessary to keep wizard without toolbar button (new, save, pager, etc...)
            hidden_fields = params.hidden_fields or []
            hidden_fields.append(tw.form.Hidden(name='_terp_view_target', default=ustr(target)))
            params.hidden_fields = hidden_fields

        return tw.form_view.ViewForm(params, name="view_form", action="/openerp/form/save")

    @expose('json')
    def get_form(self, **kw):
        params, data = TinyDict.split(kw)
        data['editable'] = data.get('editable') == 'True'
        cherrypy.request.terp_params = params
        screen = tw.screen.Screen(params, name="view_form", **data)
        if params.view_ids:
            for x in screen.widget.frame.children:
                if x.__class__.__name__ == 'O2M':
                    x.parent_view_ids = params.view_ids
        return {'view': str(screen.widget.render())}

    @expose(template="/openerp/controllers/templates/form.mako")
    def create(self, params, tg_errors=None):
        params.view_type = params.view_type or params.view_mode[0]

        loading_id = False
        if params.view_type == 'form' and params.id:
            try:
                loading_ids = rpc.RPCProxy('job.in_progress').search([('model', '=', params.model), ('res_id', '=', params.id), ('read', '=', False)])
            except openobject.errors.TinyWarning as e:
                # backkground compatibility between web and server
                if e.message == "Object job.in_progress doesn't exist":
                    loading_ids = []
                else:
                    raise
            if loading_ids:
                loading_id = [loading_ids[-1]]
                params.editable = False
                params.readonly = True
                params.force_readonly = True
        if params.view_type == 'tree':
            params.editable = True

        form = self.create_form(params, tg_errors)


        if not tg_errors:
            try:
                cherrypy.session.pop('remember_notebooks')
            except:
                self.reset_notebooks()

        editable = form.screen.editable
        mode = form.screen.view_type
        id = form.screen.id
        buttons = TinyDict()    # toolbar
        buttons.new = (not editable or mode == 'tree') and mode != 'diagram' and form.screen.button_new
        buttons.edit = not editable and (mode == 'form' or mode == 'diagram') and form.screen.button_edit
        buttons.save = editable and mode == 'form' and form.screen.button_save
        buttons.duplicate = form.screen.button_duplicate
        buttons.cancel = editable and mode == 'form' and form.screen.button_cancel
        buttons.delete = not editable and mode == 'form' and form.screen.button_delete
        buttons.pager =  mode == 'form' or mode == 'diagram'# Pager will visible in edit and non-edit mode in form view.
        buttons.can_attach = id and mode == 'form'
        buttons.i18n = not editable and mode == 'form'
        buttons.show_grid = mode == 'diagram'
        buttons.create_node = mode == 'diagram' and editable

        from openerp.widgets import get_registered_views
        buttons.views = []

        for kind, view in get_registered_views():
            buttons.views.append(dict(kind=kind, name=view.name, desc=view.desc))

        target = getattr(cherrypy.request, '_terp_view_target', None)
        buttons.toolbar = (target not in ('new', 'same') and not form.is_dashboard) or mode == 'diagram'

        pager = None
        if buttons.pager:
            pager = tw.pager.Pager(id=form.screen.id, ids=form.screen.ids, offset=form.screen.offset,
                                   limit=form.screen.limit,
                                   count=form.screen.count,
                                   view_type=params.view_type,
                                   approximation=form.screen.approximation)

        can_shortcut = self.can_shortcut_create()
        shortcut_ids = []

        if cherrypy.session.get('terp_shortcuts'):
            for sc in cherrypy.session['terp_shortcuts']:
                if isinstance(sc['res_id'], tuple):
                    shortcut_ids.append(sc['res_id'][0])
                else:
                    shortcut_ids.append(sc['res_id'])

        title = form.screen.string or ''
        display_name = {}
        if params.view_type == 'form':
            if params.id:
                title_field = form.screen.view.get('title_field')
                if form.screen.widget.force_string and form.screen.widget.string:
                    form.screen.string = form.screen.widget.string
                elif title_field and form.screen.view['fields'].get(title_field, {}).get('value'):
                    form.screen.string = form.screen.view['fields'][title_field]['value']
                if form.screen.view.get('fields') and form.screen.view['fields'].get('name'):
                    display_name = {'field': form.screen.view['fields']['name']['string'], 'value': ustr(form.screen.view['fields']['name']['value'])}
                    title= ustr(display_name['field']) + ':' + ustr(display_name['value'])
        elif params.view_type == 'diagram':
            display_name = {'field': form.screen.view['fields']['name']['string'], 'value': rpc.RPCProxy(params.model).name_get(form.screen.id, rpc.session.context)[0][1]}

        # For Corporate Intelligence visibility.
        obj_process = rpc.RPCProxy('ir.model').search([('model', '=', 'process.process')]) or None

        tips = params.display_menu_tip
        if params.view_type == params.view_mode[0] and tips:
            tips = tips

        is_dashboard = form.screen.is_dashboard or False

        return dict(form=form, pager=pager, buttons=buttons, path=self.path, can_shortcut=can_shortcut, shortcut_ids=shortcut_ids, display_name=display_name, title=title, tips=tips, obj_process=obj_process, is_dashboard=is_dashboard, sidebar_closed=params._terp_sidebar_closed, sidebar_open=params.sidebar_open, auto_refresh=params.auto_refresh, tg_errors=tg_errors, loading_id=loading_id)

    @expose('json', methods=('POST',))
    def close_or_disable_tips(self):
        rpc.RPCProxy('res.users').write(rpc.session.uid,{'menu_tips':False}, rpc.session.context)

    def get_sd_ref(self, model, res_id):
        """
        Get the sdref of the record
        """
        data_pool = rpc.RPCProxy('ir.model.data')
        data_ids = data_pool.search([
            ('model', '=', model),
            ('res_id', '=', res_id)
        ])
        if not data_ids:
            return False

        return data_pool.read(data_ids[0], ['name'])['name']

    @expose('json', methods=('POST',))
    def display_action_sd_ref(self, action_name, model, action_id):
        """
        Get sdref values of Button Access Rule and Model
        :param view_id: The ID of the ir.ui.view where the button is on
        :param btn_name: Name of the button to get values
        :param btn_model: Name (model) of the ir.model on which the button act
        :param btn_id: ID of the button
        """

        action_win_pool = rpc.RPCProxy('ir.actions.act_window')
        data = action_win_pool.read([int(action_id)], ['groups_txt', 'type'])
        if not data:
            return False
        sdref = action_win_pool.get_sd_ref(action_id)

        model_pool = rpc.RPCProxy('ir.model')
        model_id = model_pool.search([('model', '=', model)])
        model_sdref = model_pool.get_sd_ref(model_id[0])
        return dict(model=model, sdref=sdref, groups=data[0]['groups_txt'], model_sdref=model_sdref)

    @expose('json', methods=('POST',))
    def display_button_sd_ref(self, view_id, btn_name, btn_model, btn_id):
        """
        Get sdref values of Button Access Rule and Model
        :param view_id: The ID of the ir.ui.view where the button is on
        :param btn_name: Name of the button to get values
        :param btn_model: Name (model) of the ir.model on which the button act
        :param btn_id: ID of the button
        """
        bar_sdref = ''
        model_sdref = ''
        group_names = False

        # If the user is not the administrator, don't display values
        if rpc.session.uid != 1:
            return dict(admin=False)

        rules_pool = rpc.RPCProxy('msf_button_access_rights.button_access_rule')
        model_pool = rpc.RPCProxy('ir.model')

        if btn_name and '/' in btn_name:
            btn_name = btn_name.split('/')[-1]

        if btn_name and view_id:
            view_ids = rules_pool.get_family_ids(int(view_id))
            if not view_ids:
                view_ids = [view_id]

            rule_ids = rules_pool.search([
                ('name', '=', btn_name),
                ('view_id', 'in', view_ids),
            ])

            if rule_ids:
                bar_sdref = self.get_sd_ref('msf_button_access_rights.button_access_rule', rule_ids[0])
                group_names = rules_pool.read(rule_ids[0], ['group_names'])['group_names']

        model_ids = model_pool.search([
            ('model', '=', btn_model)
        ])
        if model_ids:
            model_sdref = self.get_sd_ref('ir.model', model_ids[0])

        return dict(model=btn_model, name=btn_name, btn_id=btn_id, bar_sdref=bar_sdref, model_sdref=model_sdref, admin=True, group_names=group_names)

    def _read_form(self, context, count, domain, filter_domain, id, ids, kw,
                   limit, model, offset, search_data, search_domain, source,
                   view_ids, view_mode, view_type, notebook_tab, o2m_edit=False,
                   editable=False, sidebar_closed=False, approximation=False,
                   target_action_id=False):
        """ Extract parameters for form reading/creation common to both
        self.edit and self.view
        """
        params, data = TinyDict.split({'_terp_model': model,
                                       '_terp_id': id,
                                       '_terp_ids': ids,
                                       '_terp_view_ids': view_ids,
                                       '_terp_target_action_id': target_action_id,
                                       '_terp_view_mode': view_mode,
                                       '_terp_view_type': view_type,
                                       '_terp_source': source,
                                       '_terp_domain': domain,
                                       '_terp_context': context,
                                       '_terp_offset': offset,
                                       '_terp_limit': limit,
                                       '_terp_count': count,
                                       '_terp_approximation': approximation,
                                       '_terp_search_domain': search_domain,
                                       '_terp_search_data': search_data,
                                       '_terp_filter_domain': filter_domain,
                                       '_terp_notebook_tab': notebook_tab,
                                       '_terp_sidebar_closed': sidebar_closed})
        params.o2m_edit = o2m_edit
        params.editable = editable
        params.action_id = kw.get('action_id')

        if kw.get('default_date'):
            params.context.update({'default_date' : kw['default_date']})

        cherrypy.request._terp_view_target = kw.get('target')

        if params.view_mode and 'form' not in params.view_mode:
            params.view_type = params.view_mode[-1]

        if params.view_type == 'tree':
            params.view_type = 'form'

        if not params.ids:
            params.offset = 0

        return params

    @expose()
    def edit(self, model, id=False, ids=None, view_ids=None,
             view_mode=['form', 'tree'], view_type='form', source=None, domain=[], context={},
             offset=0, limit=50, count=0, search_domain=None,
             search_data=None, filter_domain=None, o2m_edit=False,
             sidebar_closed=False, approximation=False, target_action_id=False, **kw):

        notebook_tab = kw.get('notebook_tab') or 0
        if search_domain != '[]':
            approximation = 'False'
        params = self._read_form(context, count, domain, filter_domain, id,
                                 ids, kw, limit, model, offset, search_data,
                                 search_domain, source, view_ids, view_mode,
                                 view_type, notebook_tab, o2m_edit=o2m_edit,
                                 editable=True, sidebar_closed=sidebar_closed,
                                 approximation=approximation,
                                 target_action_id=target_action_id)

        if not params.ids:
            params.count = 0

        # On New O2M
        if params.source:
            current = TinyDict()
            current.id = False
            params[params.source] = current

        return self.create(params)

    @expose()
    def view(self, model, id, ids=None, view_ids=None,
             view_mode=['form', 'tree'], view_type='form', source=None, domain=[], context={},
             offset=0, limit=50, count=0, search_domain=None,
             search_data=None, filter_domain=None, sidebar_closed=False,
             approximation=False, target_action_id=False, **kw):

        notebook_tab = kw.get('notebook_tab') or 0
        if search_domain != '[]':
            approximation = 'False'
        params = self._read_form(context, count, domain, filter_domain, id,
                                 ids, kw, limit, model, offset, search_data,
                                 search_domain, source, view_ids, view_mode,
                                 view_type, notebook_tab,
                                 sidebar_closed=sidebar_closed,
                                 approximation=approximation,
                                 target_action_id=target_action_id)

        if not params.ids:
            params.count = 1

        return self.create(params)

    @expose()
    def cancel(self, **kw):
        params, data = TinyDict.split(kw)

        if params.button:
            res = self.button_action(params)
            if res:
                return res
            raise redirect('/')

        if not params.id and params.ids:
            params.id = params.ids[0]
        if params.id and params.editable:
            raise redirect(self.path + "/view", model=params.model,
                           id=params.id,
                           ids=ustr(params.ids),
                           view_ids=ustr(params.view_ids),
                           view_mode=ustr(params.view_mode),
                           domain=ustr(params.domain),
                           context=ustr(params.context),
                           offset=params.offset,
                           limit=params.limit,
                           count=params.count,
                           search_domain=ustr(params.search_domain),
                           search_data = ustr(params.search_data),
                           filter_domain= ustr(params.filter_domain),
                           sidebar_closed=params._terp_sidebar_closed)

        params.view_type = 'tree'
        return self.create(params)

    @expose(methods=('POST',))
    @validate(form=get_validation_schema)
    @error_handler(default_error_handler)
    @exception_handler(default_exception_handler)
    def save(self, terp_save_only=False, **kw):
        """Controller method to save/button actions...

        @param tg_errors: TG special arg, used durring validation
        @param kw: keyword arguments

        @return: form view
        """
        params, data = TinyDict.split(kw)
        # remember the current page (tab) of notebooks
        cherrypy.session['remember_notebooks'] = True

        Model = rpc.RPCProxy(params.model)
        # bypass save, for button action in non-editable view
        params.is_new_doc = False
        if params.editable:
            if not params.id:
                if params.default_o2m:
                    data.update(params.default_o2m)
                ctx = dict((params.context or {}), **rpc.session.context)
                if params.button and params.button.name:
                    ctx.update({'button': params.button.name})
                params.id = int(Model.create(data, ctx))
                params.ids = (params.ids or []) + [params.id]
                params.count += 1
                if params.model == 'product.history.consumption':
                    params.is_new_doc = True
            else:
                ctx = utils.context_with_concurrency_info(params.context, params.concurrency_info)
                ctx['from_web_interface'] = True
                ignore_access_error = False
                if params.button and params.button.name:
                    ctx.update({'button': params.button.name})
                    ignore_access_error = params.button.ignore_access_error

                #original_data = Model.read(params.id, data.keys())
                #modified = {}

                #if original_data and isinstance(original_data, dict):
                #    for field, original_value in original_data.iteritems():
                #        if isinstance(original_value, tuple):
                #            original_data[field] = original_value[0]
                #        if field in data and data[field] != original_data[field]:
                #            modified[field] = data[field]

                #    Model.write([params.id], modified, ctx)
                #else:
                #    Model.write([params.id], data, ctx)
                Model.write_web([params.id], data, ctx, ignore_access_error)

            tw.ConcurrencyInfo.update(
                params.model, Model.read([params.id], ['__last_update'], ctx)
            )

        cherrypy.request.params = params

        button = params.button

        # perform button action
        if params.button:
            res = self.button_action(params)
            if res:
                return res

        current = params.chain_get(params.source or '')
        if current:
            current.id = None
        elif not button:
            params.editable = False

        if terp_save_only:
            return dict(params=params, data=data)

        def get_params(p, f):

            pp = p.chain_get(f)
            px = rpc.RPCProxy(p.model)

            _ids = pp.ids
            _all = px.read([p.id], [f])[0][f]
            _new = [i for i in _all if i not in _ids]

            pp.ids = _all
            if _new:
                pp.id = _new[0]

            return pp

        if params.source and len(params.source.split("/")) > 1:

            path = params.source.split("/")
            p = params
            for f in path:
                p = get_params(p, f)

            return self.create(params)

        args = {'model': params.model,
                'id': params.id,
                'ids': ustr(params.ids),
                'view_ids': ustr(params.view_ids),
                'view_mode': ustr(params.view_mode),
                'domain': ustr(params.domain),
                'context': ustr(params.context),
                'offset': params.offset,
                'limit': params.limit,
                'count': params.count,
                'approximation': params.approximation,
                'search_domain': ustr(params.search_domain),
                'search_data': ustr(params.search_data),
                'filter_domain': ustr(params.filter_domain),
                'notebook_tab': params.notebook_tab,
                'sidebar_closed': params.sidebar_closed}
        if params.view_target and params.view_target in ('new', 'same'):
            # within a wizard popup dialog - keep the orignal target mode
            # (here target='new' will hide toolbar buttons (new, save, pager, etc..)
            args['target'] = params.view_target
        if params.o2m_edit:
            # hack to avoid creating new record line when editing o2m inline:
            # by default one2many.mako is going to fetch a new line (.create)
            # on /edit
            args['o2m_edit'] = "1"

        if params.editable or params.source or params.return_edit:
            raise redirect(self.path + '/edit', source=params.source, **args)
        raise redirect(self.path + '/view', **args)

    def button_action_cancel(self, name, params):
        if name:
            params.button.btype = "object"
            params.id = False
            res = self.button_action(params)
            if res:
                return res

        from . import actions
        return actions.close_popup(reload=False)
    def button_action_save(self, _, params):
        params.id = False
        params.button = None

    def button_action_workflow(self, name, params):
        model, id, _, _ = self._get_button_infos(params)
        res = rpc.session.execute('object', 'exec_workflow', model, name, id)
        if isinstance(res, dict):
            from . import actions
            return actions.execute(res, ids=[id])
        params.button = None

    def button_action_object(self, name, params):
        model, id, ids, ctx = self._get_button_infos(params)

        res = rpc.session.execute('object', 'execute', model, name, ids, ctx)
        # after installation of modules (esp. initial) we may
        # need values from the global context for some contexts & domains (e.g.
        # leads) => installer wizards are generally postfixed by '.installer'
        # so use this characteristic to setup context reloads
        if model.endswith('.installer'):
            rpc.session.context_reload()
        if isinstance(res, dict):
            from . import actions
            return actions.execute(res, ids=[id], context=ctx, is_new_doc=params.is_new_doc)
        params.button = None

    def button_action_action(self, name, params):
        model, id, ids, ctx = self._get_button_infos(params)
        from . import actions

        action_id = int(name)
        action_type = actions.get_action_type(action_id)

        if action_type == 'ir.actions.wizard':
            cherrypy.session['wizard_parent_form'] = self.path
            cherrypy.session['wizard_parent_params'] = params.parent_params or params

        res = actions.execute_by_id(
            action_id, type=action_type,
            model=model, id=id, ids=ids,
            context=ctx or {})
        if res:
            return res
        params.button = None

    BUTTON_ACTIONS_BY_BTYPE = {
        'action': button_action_action,
        'cancel': button_action_cancel,
        'object': button_action_object,
        'save': button_action_save,
        'workflow': button_action_workflow,
    }

    def _get_button_infos(self, params):
        model = params.button.model
        id = params.button.id or params.id
        id = (id or False) and (id)
        ids = (id or []) and [id]
        ctx = dict((params.context or {}), **rpc.session.context)
        ctx.update(params.button.context or {})
        if params.button.selected_ids:
            if isinstance(params.button.selected_ids, (dict, list)):
                s_ids = params.button.selected_ids
            else:
                s_ids = [params.button.selected_ids]
            ctx['button_selected_ids'] = s_ids
        if params.button.selected_domain:
            ctx['selected_domain'] = params.button.selected_domain
        return model, id, ids, ctx

    def button_action(self, params):
        button_name = openobject.ustr(params.button.name)
        button_name = button_name.rsplit('/', 1)[-1]

        btype = params.button.btype
        try:
            return self.BUTTON_ACTIONS_BY_BTYPE[btype](self, button_name, params)
        except KeyError:
            raise common.warning(_('Invalid button type "%s"') % btype)

    @expose()
    def duplicate(self, **kw):
        params, data = TinyDict.split(kw)

        if not params.ids:
            params.ids = []

        id = params.id
        ctx = params.context
        ctx['from_button'] = True
        model = params.model

        proxy = rpc.RPCProxy(model)
        new_id = proxy.copy_web(id, {}, ctx)

        if new_id:
            params.id = new_id
            params.ids += [int(new_id)]
            params.count += 1

        args = {'model': params.model,
                'id': params.id,
                'ids': ustr(params.ids),
                'view_ids': ustr(params.view_ids),
                'view_mode': ustr(params.view_mode),
                'domain': ustr(params.domain),
                'context': ustr(params.context),
                'offset': params.offset,
                'limit': params.limit,
                'count': params.count,
                'approximation': params.approximation,
                'search_domain': ustr(params.search_domain),
                'filter_domain': ustr(params.filter_domain),
                'sidebar_closes': params.sidebar_closed}

        if new_id:
            raise redirect(self.path + '/edit', **args)

        raise redirect(self.path + '/view', **args)

    @expose()
    def delete(self, **kw):
        params, data = TinyDict.split(kw)

        current = params.chain_get(params.source or '') or params
        proxy = rpc.RPCProxy(current.model)

        idx = -1
        if current.id:
            ctx = utils.context_with_concurrency_info(current.context, params.concurrency_info)
            proxy.unlink([current.id], ctx)
            if current.ids:
                idx = current.ids.index(current.id)
                if idx >= 0:
                    current.ids.remove(current.id)
            params.count -= 1
            if not len(current.ids) and params.count > 0:
                params.offset = max(params.offset - params.limit, 0)
                current.ids = proxy.search([], params.offset, params.limit,0, ctx)
                idx = -1
            if idx == len(current.ids):
                idx = -1
        current.id = (current.ids or None) and current.ids[idx]
        self.reset_notebooks()

        args = {'model': params.model,
                'id': params.id,
                'ids': ustr(params.ids),
                'view_ids': ustr(params.view_ids),
                'view_mode': ustr(params.view_mode),
                'domain': ustr(params.domain),
                'context': ustr(params.context),
                'offset': params.offset,
                'limit': params.limit,
                'count': params.count,
                'approximation': params.approximation,
                'search_domain': ustr(params.search_domain),
                'filter_domain': ustr(params.filter_domain),
                'sidebar_closed': params.sidebar_closed}

        if not params.id:
            raise redirect(self.path + '/edit', **args)

        raise redirect(self.path + '/view', **args)

    @expose(content_type='application/octet-stream')
    def save_binary_data(self, _fname='file.dat', *args, **kw):
        params, data = TinyDict.split(kw)

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename="%s"' % _fname

        if params.datas:
            form = params.datas['form']
            res = form.get(params.field)
            return base64.b64decode(res)

        elif params.id:
            proxy = rpc.RPCProxy(params.model)
            res = proxy.read([params.id],[params.field, 'path', 'datas_fname'], rpc.session.context)
            if res[0].get('path'):
                return serve_file.serve_file(res[0]['path'],
                                             "application/x-download", 'attachment',
                                             res[0]['datas_fname'])

            return base64.b64decode(res[0][params.field])
        else:
            return base64.b64decode(data[params.field])


    @expose()
    def clear_binary_data(self, **kw):
        params, data = TinyDict.split(kw)

        proxy = rpc.RPCProxy(params.model)
        ctx = utils.context_with_concurrency_info(params.context, params.concurrency_info)
        ctx['from_web_interface'] = True

        if params.fname:
            proxy.write([params.id], {params.field: False, params.fname: False}, ctx)
        else:
            proxy.write([params.id], {params.field: False}, ctx)

        args = {'model': params.model,
                'id': params.id,
                'ids': ustr(params.ids),
                'view_ids': ustr(params.view_ids),
                'view_mode': ustr(params.view_mode),
                'domain': ustr(params.domain),
                'context': ustr(params.context),
                'offset': params.offset,
                'limit': params.limit,
                'count': params.count,
                'approximation': params.approximation,
                'search_domain': ustr(params.search_domain),
                'filter_domain': ustr(params.filter_domain)}

        raise redirect(self.path + '/edit', **args)

    @expose(content_type='image/png')
    def binary_image_get_image(self, **kw):
        model = kw.get('model')
        field = kw.get('field')
        id = kw.get('id')
        proxy = rpc.RPCProxy(model)
        if id == 'None':
            # FIXME: doesnt honor the context
            res = proxy.default_get([field]).get(field,'')
        else:
            res = proxy.read([int(id)], [field])[0].get(field)
        if res:
            return base64.b64decode(res)
        else:
            return open(openobject.paths.addons('openerp','static','images','placeholder.png'),'rb').read()

    @expose("json")
    def binary_image_delete(self, **kw):
        model = kw.get('model')
        id = kw.get('id')
        if id:
            id = int(id)
        field = kw.get('field')
        if id:
            proxy = rpc.RPCProxy(model)
            proxy.write([id], {field: False})
        return {}

    @expose()
    def b64(self, **kw):
        #idea from http://dean.edwards.name/weblog/2005/06/base64-ie/
        try:
            qs = cherrypy.request.query_string
            content_type, data = qs.split(';')
            data_type, data = data.split(',')
            assert(data_type == 'base64')
            cherrypy.response.headers['Content-Type'] = content_type
            return base64.b64decode(data)
        except:
            raise cherrypy.HTTPError(400)   # Bad request

    @expose()
    @validate(form=get_validation_schema)
    @error_handler(default_error_handler)
    @exception_handler(default_exception_handler)
    def filter(self, **kw):
        params, data = TinyDict.split(kw)
        if params.get('_terp_save_current_id'):
            ctx = dict((params.context or {}), **rpc.session.context)
            ctx['from_web_interface'] = True
            if params.id:
                rpc.RPCProxy(params.model).write([params.id], data, ctx)
            else:
                id = rpc.RPCProxy(params.model).create(data, ctx)
                params.ids.append(id)
                params.count += 1

        l = params.limit or 50
        o = params.offset or 0
        c = params.count or 0

        id = params.id or False
        ids = params.ids or []
        filter_action = params.filter_action

        if not filter_action:
            params.filter_action = 'PAGER_LIMIT'

        if ids and filter_action == 'FIRST':
            o = 0
            id = ids[0]

        if ids and filter_action == 'LAST':
            o = c - c % l
            id = ids[-1]

        if ids and filter_action == 'PREV':
            if id == ids[0]:
                o -= l
            elif id in ids:
                id = ids[ids.index(id)-1]

        if ids and filter_action == 'NEXT':
            if id == ids[-1]:
                o += l
            elif id in ids:
                id = ids[ids.index(id)+1]
            elif id is False:
                o = 0
                id = ids[0]

        if filter_action:
            # remember the current page (tab) of notebooks
            cherrypy.session['remember_notebooks'] = True

        if params.offset != o:

            domain = params.domain
            if params.search_domain is not None:
                domain = params.search_domain
                data = params.search_data

            ctx = params.context or {}
            ctx.update(rpc.session.context.copy())
            res = search(params.model, o, l, domain=domain, context=ctx, data=data)

            o = res['offset']
            l = res['limit']
            if not c: c = res['count']
            params.approximation = False

            params.search_domain = res['search_domain']
            params.search_data = res['search_data']

            ids = res['ids']
            id = False

            if ids and filter_action in ('FIRST', 'NEXT'):
                id = ids[0]

            if ids and filter_action in ('LAST', 'PREV'):
                id = ids[-1]

        params.id = id
        params.ids = ids
        params.offset = o
        params.limit = l
        params.count = c

        return self.create(params)

    @expose()
    def find(self, **kw):
        kw['_terp_offset'] = None
        kw['_terp_limit'] = None

        kw['_terp_search_domain'] = None
        kw['_terp_search_data'] = None
        kw['_terp_filter_action'] = 'FIND'

        return self.filter(**kw)

    @expose()
    def first(self, **kw):
        kw['_terp_filter_action'] = 'FIRST'
        return self.filter(**kw)

    @expose()
    def last(self, **kw):
        kw['_terp_filter_action'] = 'LAST'
        return self.filter(**kw)

    @expose()
    def previous(self, **kw):
        if '_terp_source' in kw:
            return self.previous_o2m(**kw)

        kw['_terp_filter_action'] = 'PREV'
        return self.filter(**kw)

    @expose()
    def next(self, **kw):
        if '_terp_source' in kw:
            return self.next_o2m(**kw)

        kw['_terp_filter_action'] = 'NEXT'
        return self.filter(**kw)

    @expose()
    @validate(form=get_validation_schema)
    @error_handler(default_error_handler)
    @exception_handler(default_exception_handler)
    def previous_o2m(self, **kw):
        params, data = TinyDict.split(kw)

        if params.get('_terp_save_current_id'):
            ctx = dict((params.context or {}), **rpc.session.context)
            if params.id:
                rpc.RPCProxy(params.model).write([params.id], data, ctx)
            else:
                id = rpc.RPCProxy(params.model).create(data, ctx)
                params.ids.append(id)
                params.count += 1

        current = params.chain_get(params.source or '') or params
        idx = -1

        if current.id:
            # save current record
            if params.editable:
                self.save(terp_save_only=True, **kw)

            idx = current.ids.index(current.id)
            idx = idx-1

            if idx == len(current.ids):
                idx = len(current.ids) -1

        if current.ids:
            current.id = current.ids[idx]

        return self.create(params)

    @expose()
    def next_o2m(self, **kw):
        params, data = TinyDict.split(kw)
        current = params.chain_get(params.source or '') or params

        idx = 0
        if current.id:

            # save current record
            if params.editable:
                self.save(terp_save_only=True, **kw)

            idx = current.ids.index(current.id)
            idx = idx + 1

            if idx == len(current.ids):
                idx = 0

        if current.ids:
            current.id = current.ids[idx]

        return self.create(params)

    @expose()
    @validate(form=get_validation_schema)
    def switch(self, **kw):
        params, data = TinyDict.split(kw)
        if params['_terp_search_data'] and params['_terp_search_data'].get('filter_status',False):
            to_del = []
            for k, v in params.context.items():
                if k.startswith('search_default') and k[15:] in params['_terp_search_data'].get('filter_status',False):
                    to_del.append(k)
            for k in to_del:
                del params.context[k]
        if params.get('_terp_save_current_id'):
            ctx = dict((params.context or {}), **rpc.session.context)
            if params.id:
                rpc.RPCProxy(params.model).write([params.id], data, ctx)
            else:
                id = rpc.RPCProxy(params.model).create(data, ctx)
                params.ids.append(id)
                params.count += 1
        # switch the view
        params.view_type = params.source_view_type
        return self.create(params)

    def do_action(self, name, adds={}, datas={}):
        params, data = TinyDict.split(datas)

        model = params.model

        id = params.id or False
        ids = params.selection or params.ids or []

        if params.view_type == 'form':
            #TODO: save current record
            ids = (id or []) and [id]

        if id and not ids:
            ids = [id]

        if len(ids):
            from . import actions
            return actions.execute_by_keyword(name, adds=adds, model=model, id=id, ids=ids, report_type='pdf')
        else:
            raise common.message(_("No record selected"))

    @expose()
    def report(self, **kw):
        return self.do_action('client_print_multi', adds={'Print Screen': {'report_name':'printscreen.list',
                                                                           'name': _('Print Screen'),
                                                                           'type':'ir.actions.report.xml'}}, datas=kw)

    @expose()
    def action(self, **kw):
        params, data = TinyDict.split(kw)
        context_menu = kw.get('context_menu')

        id = params.id or False
        ids = params.selection or []

        if not ids and id:
            ids = [id]

        if not id and ids:
            id = ids[0]

        domain = params.domain or []
        context = params.context or {}
        if not context and rpc.session.context:
            context['lang'] = rpc.session.context.get('lang')
        action = {}

        if data.get('datas'):
            action = eval(data.get('datas'))
        type = action.get('type')
        act_id = params.action

        if not act_id:
            return self.do_action('client_action_multi', datas=kw)

        if type is None:
            action_type = rpc.RPCProxy('ir.actions.actions').read(act_id, ['type'], context)['type']
            action = rpc.session.execute('object', 'execute', action_type, 'read', act_id, False, context)

        # US-9993 Track Changes: active_ids is [] when coming from Form view, only fix TC action to prevent regressions
        if action.get('res_model') == 'audittrail.log.line' and not context.get('active_ids') and context.get('active_id'):
            context['active_ids'] = [context.get('active_id')]

        if domain:
            if isinstance(domain, str):
                domain = eval(domain)
            domain.extend(expr_eval(action.get('domain', '[]'), context))
            action['domain'] = ustr(domain)

        action['form_context'] = context or {}
        from . import actions
        return actions.execute(action, model=params.model, id=id, ids=ids, report_type='pdf', context_menu=context_menu)

    @expose()
    def dashlet(self, **kw):
        params, data = TinyDict.split(kw)
        current = params.chain_get(str(params.source) or '') or params

        if hasattr(current, 'target_action_id') and current.target_action_id:
            action_id = current.target_action_id
            action_type = rpc.RPCProxy('ir.actions.actions').read(action_id,
                                                                  ['type'], params.context)['type']
            action = rpc.session.execute('object', 'execute', action_type,
                                         'read', action_id, ['views', 'domain'], params.context)
            current.view_ids = [x[0] for x in action['views']]
            while len(current.view_ids) < len(current.view_mode):
                current.view_ids.append(False)
            current.domain = action['domain']

        # remove the limit. On a click on the dashboard title more results are
        # displayed than in the dashboard itself
        if '_terp_limit' in current:
            current.pop('_terp_limit')
        return self.create(current)

    @expose('json')
    def on_change(self, **kw):

        data = kw.copy()

        callback = data.pop('_terp_callback')
        caller = data.pop('_terp_caller')
        model = data.pop('_terp_model')
        context = data.pop('_terp_context')

        try:
            context = eval(context) # convert to python dict
        except:
            context = {}

        match = re.match('^(.*?)\((.*)\)$', callback)

        if not match:
            raise common.error(_('Application Error'), _('Wrong on_change trigger: %s') % callback)

        for k, v in data.items():
            try:
                # specific UC on Kit Substitution when on_change on product_id replacement is called where a line in Products to remove is edited
                if model == 'substitute.item' and callback.startswith('on_change_product_id') and k.startswith('composition_item_ids/'):
                    del (data[k])
                    del (kw[k])
                else:
                    data[k] = eval(v)
            except:
                pass

        result = {}

        prefix = ''
        if '/' in caller:
            prefix = caller.rsplit('/', 1)[0]

        ctx = TinyForm(**kw).to_python(safe=True)
        pctx = ctx

        if prefix:
            ctx = ctx.chain_get(prefix)

            if '/' in prefix:
                pprefix = prefix.rsplit('/', 1)[0]
                pctx = pctx.chain_get(pprefix)

        ctx2 = dict(rpc.session.context,
                    **context or {})

        ctx['parent'] = pctx
        ctx['context'] = ctx2

        func_name = match.group(1)
        arg_names = [n.strip() for n in match.group(2).split(',')]

        args = [utils.expr_eval(arg, ctx) for arg in arg_names]
        # TODO: If the eval fails in expr_eval (because `arg` does not exist in `ctx`), it returns `{}`
        # This is a value we don't want, but not sure where that behavior
        # comes from/is used so in order not to risk breakage throughout
        # patch it here
        args = [(False if arg == {} else arg)
                for arg in args]

        proxy = rpc.RPCProxy(model)

        ids = ctx.id and [ctx.id] or ctx.parent.id and [ctx.parent.id] or []

        try:
            response = getattr(proxy, func_name)(ids, *args)
        except Exception:
            return dict(error=_ep.render())

        if response is False: # response is False when creating new record for inherited view.
            response = {}

        if 'value' not in response:
            response['value'] = {}

        result.update(response)

        # apply validators (transform values from python)
        values = result['value']
        values2 = {}

        float_fields = []
        float_def = {}
        for k in values:
            key = ((prefix or '') and prefix + '/') + k
            kind = data.get(key, {}).get('type', '')
            if data.get(key, {}).get('type', '') == 'float':
                float_fields.append(k)
        if float_fields:
            float_def = proxy.fields_get(float_fields, with_uom_rounding=True, context=ctx2)

        for k, v in values.items():
            key = ((prefix or '') and prefix + '/') + k

            kind = data.get(key, {}).get('type', '')

            if key in data and key != 'id':
                values2[k] = data[key]
                values2[k]['value'] = v
            else:
                values2[k] = {'value': v}

            if kind == 'float':
                if float_def.get(k, {}).get('related_uom') and float_def.get(k, {}).get('related_uom') in values:
                    values2[k]['rounding_value'] = values[float_def[k]['related_uom']]
                    values2[k]['uom_rounding'] = float_def[k].get('uom_rounding')
                digit = float_def.get(k, {}).get('digits')
                if digit:
                    digit = digit[1]
                values2[k]['digit'] = digit or 2

                # custom fields - decimal_precision computation
                computation = float_def.get(k, {}).get('computation')
                values2[k]['computation'] = computation

        values = TinyForm(**values2).from_python().make_plain()

        # get name of m2o and reference fields
        for k, v in values2.items():
            kind = v.get('type')
            relation = v.get('relation')
            if kind == 'reference' and not relation and ',' in values.get(k,''):
                relation,v = values[k].split(',',2)
                values[k] = "%s,%s,%s"%(relation, v, rpc.name_get(relation, v, context))
            elif relation and kind in ('many2one', 'reference') and values.get(k):
                values[k] = [values[k], rpc.name_get(relation, values[k], context)]
            elif kind == 'reference' and values.get(k+'/options'):
                values[k] = {'options': values[k+'/options'], 'selection': False}
                del(values[k+'/options'])
                if ',' in values.get(k+'/selection',''):
                    relation,v = values[k+'/selection'].split(',',2)
                    values[k]['selection'] = "%s,%s,%s"%(relation, v, rpc.name_get(relation, v, context))
                    del(values[k+'/selection'])
        result['value'] = values

        # convert domains in string to prevent them being converted in JSON
        if 'domain' in result:
            for k in result['domain']:
                result['domain'][k] = ustr(result['domain'][k])
        return result

    @expose('json')
    def get_context_menu(self, model, field, kind="char", relation=None,
                         value=None, hide_default_menu=False):

        defaults = []
        actions = []
        relates = []

        if kind == "many2one" or kind == "reference":
            defaults.append({'text': _('Open resource'), 'action': "new ManyToOne('%s').open_record('%s')" % (field, value)})

        if isinstance(hide_default_menu, str):
            if hide_default_menu and hide_default_menu.lower() in ('1', 'true'):
                hide_default_menu = True
            else:
                hide_default_menu = False

        if kind != 'reference' and not hide_default_menu:
            defaults += [
                {'text': _('Set to default value'), 'action': "set_to_default('%s', '%s')" % (field, model)},
                {'text': _('Set as default'), 'action': "set_as_default('%s', '%s')"  % (field, model)},
                {'text': _('Reset default'), 'action': "reset_default('%s', '%s')"  % (field, model)},
            ]

        if kind=='many2one':

            act = (value or None) and "javascript: void(0)"

            actions += [{'text': _('Action'), 'relation': relation, 'field': field, 'action': act and "do_action(this, true)"},
                        {'text': _('Report'), 'action': act and "do_report('%s', '%s')" %(field, relation)}]

            res = rpc.RPCProxy('ir.values').get('action', 'client_action_relate', [(relation, False)], False, rpc.session.context)
            res = [x[2] for x in res]

            for x in res:
                act = (value or None) and "javascript: void(0)"
                x['string'] = x['name']
                relates += [{'text': '... '+x['name'],
                             'action_id': x['id'],
                             'field': field,
                             'relation': relation,
                             'action': act and "do_action(this, true)",
                             'domain': x.get('domain', []),
                             'context': x.get('context', {})}]

        return dict(defaults=defaults, actions=actions, relates=relates)

    @expose('json')
    def get_default_value(self, model, field):

        field = field.split('/')[-1]

        res = rpc.RPCProxy(model).default_get([field], {}, True)
        value = res.get(field)

        return dict(value=value)

    def reset_notebooks(self):
        for name in cherrypy.request.cookie.keys():
            if name.startswith('_notebook_'):
                cherrypy.response.cookie[name] = 0

    @expose('json')
    def change_default_get(self, **kw):
        params, data = TinyDict.split(kw)

        ctx = rpc.session.context.copy()
        ctx.update(params.context or {})

        model = params.model
        field = params.caller.split('/')[-1]
        value = params.value or False

        proxy = rpc.RPCProxy('ir.values')
        values = proxy.get('default', '%s=%s' % (field, value), [(model, False)], False, ctx)

        data = {}
        for index, fname, value in values:
            data[fname] = value

        return dict(values=data)

    # Possible to create shortcut for particular object or not.
    def can_shortcut_create(self):
        """ We only handle creating shortcuts to menu actions (for now
        anyway), and those go through the execute routine, so only match
        execute()d actions concerning ir.ui.menu. And trees, just because
        """
        action_data = cherrypy.request.params.get('data', {})
        return (rpc.session.is_logged() and
                rpc.session.active_id and
                ((cherrypy.request.path_info == '/openerp/execute'
                  and action_data.get('model') == 'ir.ui.menu')
                 # FIXME: hack hack hack
                 or cherrypy.request.params.get('_terp_source_view_type') == 'tree'))

    @expose()
    def action_submenu(self, **kw):
        params, data = TinyDict.split(kw)

        from . import actions

        act_id = rpc.session.execute('object', 'execute', 'ir.model.data', 'search', [('name','=', params.action_id)])
        res_model = rpc.session.execute('object', 'execute', 'ir.model.data', 'read', act_id, ['res_id'])

        res = rpc.session.execute('object', 'execute', 'ir.actions.act_window', 'read', res_model[0]['res_id'], False)

        if res:
            return actions.execute(res, model=params.model, id=params.id, context=rpc.session.context.copy())

# vim: ts=4 sts=4 sw=4 si et

