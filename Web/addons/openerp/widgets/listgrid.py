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
import copy
import math
import xml.dom.minidom
from openerp import utils
from itertools import chain, count

import cherrypy
from openerp.utils import rpc, icons, common, expr_eval, node_attributes
from openerp.widgets import TinyWidget, TinyInputWidget, ConcurrencyInfo, get_widget

from . import form
from openobject import tools
from openobject.tools import ast
from openobject.i18n import format
from openobject import ustr
from .pager import Pager
from openobject.i18n import _

class List(TinyWidget):

    template = "/openerp/widgets/templates/listgrid/listgrid.mako"
    params = ['name', 'data', 'columns', 'headers', 'model', 'selectable', 'editable', 'noteditable', 'nopopup', 'resequencable',
              'pageable', 'selector', 'source', 'offset', 'limit', 'show_links', 'editors', 'view_mode',
              'hiddens', 'edit_inline', 'field_total', 'field_real_total',
              'link', 'checkbox_name', 'm2m', 'min_rows', 'string', 'o2m',
              'dashboard', 'impex', 'hide_new_button', 'hide_delete_button',
              'hide_edit_button', 'notselectable', 'filter_selector', 'default_selector', 'button_attrs', 'bothedit', 'extra_button', 'field_sum_field']

    member_widgets = ['pager', 'buttons', 'editors', 'concurrency_info']

    pager = None
    field_total = {}
    field_real_total = {}
    editors = {}
    hiddens = []
    buttons = []

    edit_inline = None
    data = None
    columns = 0
    headers = None
    noteditable = None
    notselectable = None
    nopopup = False
    model = None
    selectable = False
    editable = False
    pageable = False
    show_links = 1
    source = None
    checkbox_name = True
    min_rows = 5
    hide_new_button = False
    hide_delete_button = False
    hide_edit_button = False
    bothedit = False
    extra_button = False

    def __init__(self, name, model, view, ids=[], domain=[], context={}, **kw):

        super(List, self).__init__(name=name, model=model, ids=ids, force_readonly=kw.get('force_readonly'))
        self.context = context or {}
        self.domain = domain or []
        custom_search_domain = getattr(cherrypy.request, 'custom_search_domain', [])
        custom_filter_domain = getattr(cherrypy.request, 'custom_filter_domain', [])

        if name.endswith('/'):
            self._name = name[:-1]
        if name != '_terp_list':
            self.source = self.name.replace('/', '/') or None

        self.sort_order = kw.get('sort_order', '')
        self.sort_key = kw.get('sort_key', '')
        #this Condition is for Dashboard to avoid new, edit, delete operation
        self.dashboard = 0
        self.noteditable = []
        self.notselectable = []
        self.nopopup = []
        self.selectable = kw.get('selectable', 0)
        self.editable = kw.get('editable', False)
        self.pageable = kw.get('pageable', True)
        self.view_mode = kw.get('view_mode', [])
        self.offset = kw.get('offset', 0)
        self.limit = 0
        self.count = kw.get('count', 0)
        self.approximation = kw.get('approximation', False)
        self.link = kw.get('nolinks')
        self.m2m = kw.get('m2m', 0)
        self.o2m = kw.get('o2m', 0)
        self.concurrency_info = None
        self.selector = None
        self.force_readonly = kw.get('force_readonly', False)
        self.filter_selector = kw.get('filter_selector', None)
        self.default_selector = kw.get('default_selector', 0)

        self.rounding_values = view.get('uom_rounding', {})

        self.field_no_sum = []
        self.field_sum_field = {}
        terp_params = getattr(cherrypy.request, 'terp_params', {})
        if terp_params:
            if terp_params.get('_terp_model'):
                if terp_params['_terp_model'] == 'board.board' and terp_params.view_type == 'form':
                    self.dashboard = 1
            if terp_params.get('_terp_source'):
                if (str(terp_params.source) == self.source) or (terp_params.source == '_terp_list' and terp_params.sort_key):
                    self.sort_key = terp_params.sort_key
                    self.sort_order = terp_params.sort_order

        if self.selectable == 1:
            self.selector = 'radio'

        if self.selectable == 2:
            self.selector = 'checkbox'

        fields = view['fields']
        dom = xml.dom.minidom.parseString(view['arch'].encode('utf-8'))
        root = dom.childNodes[0]

        attrs = node_attributes(root)

        if attrs.get('min_rows'):
            self.min_rows = int(attrs.get('min_rows'))

        self.button_attrs = attrs.get('button_attrs', None)

        # Get the hide status of some buttons - by default buttons are shown
        self.hide_new_button = False
        self.hide_delete_button = False
        self.hide_edit_button = False
        self.show_add_button = False
        try:
            self.hide_new_button = expr_eval(attrs.get('hide_new_button', False), {'context': context})
            self.show_add_button = expr_eval(attrs.get('show_add_button', False), {'context': context})
            if (self.o2m or self.m2m) and self.show_add_button:
                self.hide_new_button = False
            self.hide_delete_button = expr_eval(attrs.get('hide_delete_button', False), {'context': context})
            self.hide_edit_button = expr_eval(attrs.get('hide_edit_button', False), {'context': context})
        except:
            pass

        self.string = attrs.get('string','')

        search_param = copy.deepcopy(domain) or []
        if custom_search_domain:
            for elem in custom_search_domain:
                if elem not in self.domain:
                    search_param.append(elem)

            for elem in custom_filter_domain:
                if elem not in self.domain:
                    search_param.append(elem)

        # -- Limits --
        # 1. use action limit or default global listview limit: 20
        # 2. apply tree view limit if defined in attrs: <tree limit='..'>...</tree>
        # 3. apply user limit if changed
        self.limit = getattr(cherrypy.request, 'action_limit', 20)
        if attrs.get('limit'):
            try:
                self.limit = int(attrs.get('limit'))
            except Exception:
                pass
        if kw.get('limit') is not None:
            self.limit = int(kw.get('limit'))

        self.colors = {}
        for color_spec in attrs.get('colors', '').split(';'):
            if color_spec:
                colour, test_c = color_spec.split(':')
                self.colors[colour] = test_c

        proxy = rpc.RPCProxy(model)

        default_data = kw.get('default_data', [])
        search_text = terp_params.get('_terp_search_text', False)
        if not self.source:
            self.source = terp_params.get('_terp_source', None)


        if not default_data and not self.o2m and not self.m2m:
            if 'unique_id' in kw:
                context['unique_id'] = kw['unique_id']
            if self.limit > 0:
                if self.sort_key:
                    ids = proxy.search(search_param, self.offset, self.limit, self.sort_key + ' ' +self.sort_order + ',id', context)
                else:
                    if search_text:
                        if self.source == '_terp_list':
                            ids = proxy.search(search_param, self.offset, self.limit, False, context)
                    else:
                        ids = proxy.search(search_param, self.offset, self.limit, False, context)
            else:
                ids = proxy.search(search_param, 0, 0, 0, context)
            if len(ids) < self.limit:
                if self.offset and self.offset > 0:
                    self.count = len(ids) + self.offset
                else:
                    self.count = len(ids)
            else:
                self.count, self.approximation = proxy.approximate_search_count(search_param, context)

        if not default_data and self.m2m:
            # prefilter datas for m2m
            # XXX: make it explicit about how 'sum' are computed as this is going to change default behaviour
            if ids and self.limit not in (0, -1):
                ids = self.ids[self.offset:self.offset+self.limit]

        self.data_dict = {}
        data = []

        if ids and not isinstance(ids, list):
            ids = [ids]

        if ids and len(ids) > 0:

            ctx = rpc.session.context.copy()
            ctx.update(context)

            try:
                data = proxy.read_web(ids, list(fields.keys()) + ['__last_update'], ctx)
            except:
                pass

            ConcurrencyInfo.update(self.model, data)
            cherrypy.response.headers.pop('X-Concurrency-Info', None)
            self.concurrency_info = ConcurrencyInfo(self.model, ids)

            order_data = [(d['id'], d) for d in data]
            orderer = dict(list(zip(ids, count())))
            ordering = sorted(order_data, key=lambda object: orderer[object[0]])
            data = [i[1] for i in ordering]

            for item in data:
                self.data_dict[item['id']] = item.copy()

            if not self.m2m:
                self.ids = ids
        elif kw.get('default_data', []):
            data = kw['default_data']

        self.values = copy.deepcopy(data)
        self.headers, self.hiddens, self.data, self.field_total, self.field_real_total, self.buttons = self.parse(root, fields, data)

        for k, v in list(self.field_total.items()):
            if(len([test[0] for test in self.hiddens if test[0] == k])) <= 0:
                if k in self.field_no_sum:
                    self.field_total[k][1] = ''
                else:
                    self.field_total[k][1] = self.do_sum(self.data, k)

        for k, v in list(self.field_real_total.items()):
            if(len([test[0] for test in self.hiddens if test[0] == k])) <= 0:
                self.field_real_total[k][1] = self.do_real_sum(self.data, k)

        self.columns = len(self.headers)

        self.columns += (self.selectable or 0) and 1
        self.columns += (self.editable or 0) and 2
        self.columns += (self.buttons or 0) and 1

        if self.pageable:
            self.pager = Pager(ids=self.ids, offset=self.offset,
                               limit=self.limit, count=self.count,
                               approximation=self.approximation)
            self.pager._name = self.name

        if self.editable and context.get('set_editable'):#Treeview editable by default or set_editable in context
            attrs['editable'] = "bottom"

        if self.selectable and attrs.get('notselectable'):
            for x in self.values:
                try:
                    if expr_eval(attrs.get('notselectable'), x):
                        self.notselectable.append(x['id'])
                except:
                    pass

        self.resequencable = expr_eval(attrs.get('resequencable') or '1')
        # self.resequencable = True  # uncomment this if you want to disable this globally

        # make editors
        if self.editable and attrs.get('noteditable'):
            for x in self.values:
                try:
                    if expr_eval(attrs.get('noteditable'), x):
                        self.noteditable.append(x['id'])
                except:
                    pass
        if self.editable and attrs.get('nopopup'):
            for x in self.values:
                try:
                    if expr_eval(attrs.get('nopopup'), x):
                        self.nopopup.append(x['id'])
                except:
                    pass

        if self.editable and attrs.get('editable') in ('top', 'bottom', 'both'):
            self.bothedit = attrs.get('editable') == 'both'
            for f, fa in self.headers:
                if not isinstance(fa, int):
                    fa['prefix'] = '_terp_listfields' + ((self.name != '_terp_list' or '') and '/' + self.name)
                    fa['inline'] = True
                    if fa.get('type') == 'one2many':
                        self.edit_inline = False
                        self.editors = {}
                        break
                    fa['editable_style'] = attrs.get('editable_style', False)
                    fa['model'] = self.model
                    Widget = get_widget(fa.get('type', 'char')) or get_widget('char')
                    self.editors[f] = Widget(**fa)

            # generate hidden fields
            if self.editors:
                for f, fa in self.hiddens:
                    fa['prefix'] = '_terp_listfields' + ((self.name != '_terp_list' or '') and '/' + self.name)
                    self.editors[f] = form.Hidden(**fa)

        # limit the data
        if self.pageable and len(self.data) > self.limit and self.limit != -1:
            self.data = self.data[self.offset:]
            self.data = self.data[:min(self.limit, len(self.data))]


    def do_sum(self, data, field):
        sum = 0.0

        for d in data:
            value = d[field].value
            sum += value

        attrs = {}
        if data:
            d = data[0]
            attrs = d[field].attrs

        digits = attrs.get('digits', (16,2))
        if isinstance(digits, str):
            digits = eval(digits)

        # custom fields - decimal_precision computation
        computation = attrs.get('computation', False)
        if isinstance(computation, str):
            computation = eval(computation)

        integer, digit = digits
        return format.format_decimal(sum or 0.0, digit, computation=computation)

    def do_real_sum(self, data, field):
        sum = 0.0

        for d in data:
            if d['line_type'].value != 'view':
                value = d[field].value
                sum += value

        attrs = {}
        if data:
            d = data[0]
            attrs = d[field].attrs

        digits = attrs.get('digits', (16,2))
        if isinstance(digits, str):
            digits = eval(digits)

        # custom fields - decimal_precision computation
        computation = attrs.get('computation', False)
        if isinstance(computation, str):
            computation = eval(computation)

        integer, digit = digits
        return format.format_decimal(sum or 0.0, digit, computation=computation)


    def display(self, value=None, **params):

        # set editor values
        if not (self.editors and self.edit_inline):
            return super(List, self).display(value, **params)

        ctx = dict(rpc.session.context,
                   **self.context)

        headers_info = dict(self.headers)
        fields = [name for name, _ in chain(self.headers, self.hiddens)]

        proxy = rpc.RPCProxy(self.model)
        if isinstance(self.edit_inline, int) and self.edit_inline > 0 and \
                self.edit_inline in self.data_dict:
            values = self.data_dict[self.edit_inline]
        else:
            values = dict(proxy.default_get(fields, ctx, True))

            # update values according to domain
            list_of_tuple = [x for x in self.domain if isinstance(x, tuple)]
            for (field, operator, value) in list_of_tuple:
                if field in fields:
                    if operator == '=':
                        values[field] = value
                    elif operator == 'in' and len(value) == 1:
                        values[field] = value[0]

        for f in fields:
            if f in values:
                if headers_info.get(f, {}).get('related_uom') and self.rounding_values and headers_info[f]['related_uom'] in values:
                    headers_info[f]['uom_rounding'] = self.rounding_values
                    headers_info[f]['rounding_value'] = values[headers_info[f]['related_uom']]
                    self.editors[f] = get_widget('float')(**headers_info[f])
                self.editors[f].set_value(values[f])

        return super(List, self).display(value, **params)

    def parse(self, root, fields, data=None):
        """Parse the given node to generate valid list headers.

        @param root: the root node of the view
        @param fields: the fields

        @return: an instance of List
        """

        if data is None:
            data = []
        headers = []
        hiddens = []
        buttons = []

        field_total = {}
        field_real_total = {}
        values  = [row.copy() for row in data]

        myfields = [] # check for duplicate fields

        set_tooltip = {}
        for node in root.childNodes:
            if node.nodeName == 'button':
                if self.force_readonly:
                    continue
                attrs = node_attributes(node)
                if attrs.get('invisible', False):
                    visible = eval(attrs['invisible'], {'context':self.context})
                    if visible:
                        continue
                if attrs.get('name') == 'tree_button':
                    self.extra_button = attrs
                else:
                    buttons += [Button(**attrs)]
                    headers.append(("button", len(buttons)))
            elif node.nodeName == 'separator':
                attrs = node_attributes(node)
                if attrs.get('invisible', False):
                    invisible = eval(attrs['invisible'], {'context':self.context})
                    if invisible:
                        continue
                headers += [("separator", {'type': 'separator', 'string': '|', 'not_sortable': 1})]
            elif node.nodeName == 'field':
                attrs = node_attributes(node)
                if 'name' in attrs:

                    name = attrs['name']

                    if name in myfields:
                        print("-"*30)
                        print(" malformed view for:", self.model)
                        print(" duplicate field:", name)
                        print("-"*30)
                        raise common.error(_('Application Error'), _('Invalid view, duplicate field: %s') % name)

                    myfields.append(name)

                    if attrs.get('widget'):
                        if attrs['widget']=='one2many_list':
                            attrs['widget']='one2many'
                        attrs['type'] = attrs['widget']

                    try:
                        fields[name].update(attrs)
                    except:
                        print("-"*30,"\n malformed tag for:", attrs)
                        print("-"*30)
                        raise

                    kind = fields[name]['type']

                    if kind not in CELLTYPES:
                        kind = 'char'

                    fields[name].update(attrs)

                    cell_colors = {}
                    if fields[name].get('colors'):
                        for color_spec in fields[name].get('colors', '').split(';'):
                            if color_spec:
                                colour, test_c = color_spec.split(':')
                                cell_colors[colour] = test_c

                    try:
                        visval = fields[name].get('invisible', 'False')
                        invisible = visval if isinstance(visval, bool) \
                            else eval(visval, {'context': self.context})
                    except NameError as e:
                        cherrypy.log.error(e, context='listgrid.List.parse')
                        invisible = False

                    if invisible:
                        hiddens += [(name, fields[name])]

                    if 'sum' in attrs:
                        field_total[name] = [attrs['sum'], 0.0]

                    if 'sum_selected' in attrs:
                        self.field_no_sum.append(name)

                    if 'sum_field' in attrs and attrs['sum_field']:
                        self.field_sum_field[name] = format.format_decimal(round(sum([x.get(attrs['sum_field'], 0) for x in data]), 2) or 0)

                    if 'real_sum' in attrs:
                        field_real_total[name] = [attrs['real_sum'], 0.0]

                    if fields[name].get('tooltip'):
                        set_tooltip[name] = fields[name].get('tooltip')

                    for i, row in enumerate(data):
                        row_value = values[i]
                        if invisible:
                            cell = Hidden(**fields[name])
                            cell.set_value(row_value.get(name, False))
                        else:
                            if kind == 'float' and fields[name].get('related_uom') and self.rounding_values and row_value.get(fields[name]['related_uom']):
                                if isinstance(row_value.get(fields[name]['related_uom']), (list, tuple)):
                                    rounding = row_value.get(fields[name]['related_uom'])[0]
                                else:
                                    rounding = row_value.get(fields[name]['related_uom'])
                                cell = CELLTYPES[kind](value=row_value.get(name, False), rounding=self.rounding_values.get(rounding), **fields[name])
                            else:
                                cell = CELLTYPES[kind](value=row_value.get(name, False), **fields[name])

                        for color, expr in list(self.colors.items()) or list(cell_colors.items()):
                            try:
                                if expr_eval(expr,
                                             dict(row_value, active_id=rpc.session.active_id or False)):
                                    cell.color = color
                                    break
                            except:
                                pass
                        row[name] = cell

                    if invisible:
                        continue

                    headers += [(name, fields[name])]

        if set_tooltip:
            for row in data:
                for to_set in set_tooltip:
                    if isinstance(row[set_tooltip[to_set]], Hidden):
                        row[to_set].tooltip = row[set_tooltip[to_set]].widget.get_display_value()
                    else:
                        row[to_set].tooltip = row[set_tooltip[to_set]].get_display_value()

        return headers, hiddens, data, field_total, field_real_total, buttons


class Char(TinyWidget):
    template = "/openerp/widgets/templates/listgrid/char.mako"

    params = ['text', 'link', 'value', 'truncate', 'tooltip']

    def __init__(self, **attrs):

        super(Char, self).__init__(**attrs)

        self.attrs = attrs.copy()

        self.tooltip = attrs.get('tooltip_value')
        self.text = self.get_text()
        self.link = self.get_link()

        # fill the value attribute an span, used if state is both displayed on line and used in a readonly condition
        self.default = attrs.get('value', '')

        self.truncate = attrs.get('truncate', False)

        self.color = None
        self.onclick = None

    def get_text(self):
        if self.truncate:
            try:
                nb_trunc = int(self.truncate)
                value = self.value and self.value[:nb_trunc] or ''
            except:
                value = self.value or ''
        else:
            value = self.value or ''

        return value

    def get_link(self):
        return None

    def get_sortable_text(self):
        """ If returns anything other then None, the return value will be
        used to sort the listgrid. Useful for localized data.
        """
        return None

    def __unicode__(self):
        return ustr(self.text)

    def __str__(self):
        return ustr(self.text)


class Image(TinyWidget):
    template = "/openerp/widgets/templates/listgrid/image.mako"
    params = ['height', 'width', 'img']

    def __init__(self, **attrs):
        super(Image, self).__init__(**attrs)
        self.img = self.value
        self.color = None
        self.height = attrs.get('height')
        self.width = attrs.get('width')

    def get_sortable_text(self):
        return False

class HtmlText(Char):
    template = "/openerp/widgets/templates/listgrid/html.mako"

class Reference(Char):

    def get_text(self):
        self.refrel = False
        self.refid = False
        if isinstance(self.value, dict):
            self.value = self.value.get('selection',"")
        if self.value and ',' in self.value:
            self.refrel, self.refid = self.value.split(',', 2)
            self.value = rpc.name_get(self.refrel, self.refid, rpc.session.context)
            return self.value
        return ''

    def get_link(self):
        m2o_link = int(self.attrs.get('link', 1))

        if m2o_link == 1 and self.refrel and self.refid:
            return tools.url('/openerp/form/view', model=self.refrel, id=self.refid)
        return None

class M2O(Char):

    def get_text(self):

        if isinstance(self.value, int):
            self.value = self.value, rpc.name_get(self.attrs['relation'], self.value, rpc.session.context)

        if self.value and len(self.value) > 0:
            if isinstance(self.value, (tuple, list)):
                return self.value[-1]
            else:
                return self.value

        return ''

    def get_link(self):
        m2o_link = int(self.attrs.get('link', 1))

        if m2o_link == 1:
            return tools.url('/openerp/form/view', model=self.attrs['relation'], id=(self.value or False) and self.value[0])
        else:
            return None

class O2M(Char):

    def get_text(self):
        return "%d" % len(self.value)

class M2M(Char):

    def get_text(self):
        if self.truncate:
            if not self.value:
                return ''
            max_length = int(self.truncate)
            value_string = ', '.join([x[1] for x in  rpc.RPCProxy(self.attrs['relation']).name_get(self.value, rpc.session.context)])
            if len(value_string) > max_length:
                value_string = '%s...' % value_string[:max_length-3]
            return value_string
        return "%d" % len(self.value)

class Selection(Char):

    def get_text(self):
        if self.value:
            if isinstance(self.value, (tuple, list)):
                self.value = self.value[0]
            selection = self.attrs['selection']
            hidden_selection = self.attrs.get('hidden_selection', [])
            for k, v in selection + hidden_selection:
                if k == self.value:
                    return v

        return ''

class Float(Char):

    def __init__(self, **attrs):
        self.with_null = attrs.get('with_null')
        self.null_value = attrs.get('null_value', '')
        super(Float, self).__init__( **attrs)

    def get_text(self):
        if self.with_null and self.value is False:
            return self.null_value

        digits = self.attrs.get('digits', (16,2))
        if isinstance(digits, str):
            digits = eval(digits)

        # custom fields - decimal_precision computation
        computation = self.attrs.get('computation', False)
        if isinstance(computation, str):
            computation = eval(computation)

        if self.attrs.get('rounding'):
            return format.format_decimal(self.value or 0.0, int(abs(math.log10(self.attrs['rounding']))))

        integer, digit = digits
        return format.format_decimal(self.value or 0.0, digit, computation=computation)

    def get_sortable_text(self):
        return ustr(self.value or '0.0')

class FloatTime(Char):

    def get_text(self):
        val = self.value or 0.0
        t = '%02d:%02d' % (math.floor(abs(val)),round(abs(val)%1+0.01,2) * 60)

        hour, min = t.split(':')
        if int(min) == 60:
            t = str(int(hour) + 1) + ":00"
        if val < 0:
            t = '-' + t

        return t

class Int(Char):

    def __init__(self, **attrs):
        self.with_null = attrs.get('with_null')
        self.null_value = attrs.get('null_value', '')
        super(Int, self).__init__( **attrs)

    def get_text(self):
        if self.value:
            if isinstance(self.value, str):
                return ast.literal_eval(self.value)
            return int(self.value)

        elif self.with_null and (self.value is False or self.value is None):
            return self.null_value
        return 0

class ProgressBar(Char):
    template = "/openerp/widgets/templates/listgrid/progressbar.mako"

    params = ['range']


    def get_text(self):
        if not self.value:
            return 0.0

        if self.value == "no-progressbar":
            return "no-progressbar"

        if isinstance(self.value, float):
            self.value = '%.2f' % (self.value)
            self.value = float(self.value)

            if self.value > 100.0:
                self.range = 100.0
            else:
                self.range = self.value
            return self.range
        else:
            self.value = '%d' % (self.value)
            self.range = self.value
            return self.range

class DateTime(Char):

    def get_text(self):
        try:
            return format.format_datetime(self.value, kind=self.attrs.get('type', 'datetime'))
        except ValueError:
            return self.value

    def get_sortable_text(self):
        return ustr(self.value or '')

class Separator(Char):

    def __init__(self, **attrs):
        super(Separator, self).__init__(**attrs)
        self.separator = True

    def get_text(self):
        return '|'

class Boolean(Char):
    template = "/openerp/widgets/templates/listgrid/boolean.mako"

    params = ['val', 'kind']

    def get_text(self):
        self.val = int(self.value)
        self.kind = 'boolean'
#        if int(self.value) == 1:
#            return _('Yes')
#        else:
#            return _('No')

class NullBoolean(Char):
    template = "/openerp/widgets/templates/listgrid/null_boolean.mako"

    params = ['val', 'kind']

    def get_text(self):
        self.val = 0
        self.kind = 'boolean'
        if self.value == 'X':
            self.val = 1
        elif self.value == '?':
            self.val = self.value
            self.kind = 'text'

class HumanSize(Char):

    def get_text(self):
        return utils.get_size(self.value or 0.0)

class Button(TinyInputWidget):

    params = ['icon', 'id', 'parent_grid', 'btype', 'confirm', 'width', 'context']

    template = "/openerp/widgets/templates/listgrid/button.mako"

    def __init__(self, **attrs):
        super(Button, self).__init__(**attrs)

        self.states = attrs.get('states')
        if self.states:
            self.states = self.states.split(',')

        self.btype = attrs.get('special', attrs.get('type', 'workflow'))
        self.icon = attrs.get('icon')
        self.attrs = attrs.get('attrs', {})
        if self.icon:
            self.icon = icons.get_icon(self.icon)

        self.context = attrs.get('context', {})

        self.help = self.help or self.string
        self.confirm = attrs.get('confirm') or ''
        self.readonly = False

        self.width = attrs.get('width', 16)

        self.header = attrs.get('header', False)


    def params_header(self):

        return dict(header=True,       \
                    visible=self.header);

    def params_from(self, data):

        id = data.get('id')
        visible = True

        if self.states:
            state = data.get('state')
            try:
                state = ((state or False) and state.value) or 'draft'
            except:
                state = ustr(state)
            visible = state in self.states

        return dict(header=False,  \
                    id=id,         \
                    visible=visible)

    def update_params(self, params):
        super(Button, self).update_params(params)
        params['attrs']['attrs']=self.attrs

class Hidden(TinyInputWidget):
    template = "openerp/widgets/templates/listgrid/hidden.mako"

    params = ['relation', 'field_id']
    member_widgets = ['widget']

    def __init__(self, **attrs):
        super(Hidden, self).__init__(**attrs)
        kind = self.kind or 'text'
        self.widget = get_widget(kind)(**attrs)
        self.validator = self.widget.validator
        self.relation = attrs.get('relation') or None
        self.editable = self.readonly
        self.color = None
        if 'field_id' not in attrs:
            self.field_id = self.name

    def set_value(self, value):
        self.widget.set_value(value)
        self.default = self.widget.default

    def get_sortable_text(self):
        """ If returns anything other then None, the return value will be
        used to sort the listgrid. Useful for localized data.
        """
        return None

    def update_params(self, params):
        super(Hidden, self).update_params(params)

class URL(Char):
    template = "openerp/widgets/templates/listgrid/url.mako"

CELLTYPES = {
    'char':Char,
    'many2one':M2O,
    'reference': Reference,
    'datetime':DateTime,
    'date':DateTime,
    'one2many':O2M,
    'many2many':M2M,
    'selection':Selection,
    'float':Float,
    'float_time':FloatTime,
    'integer':Int,
    'boolean' : Boolean,
    'null_boolean' : NullBoolean,
    'progressbar' : ProgressBar,
    'separator': Separator,
    'human_size': HumanSize,
    'html_text': HtmlText,
    'url': URL,
    'image': Image,
}
