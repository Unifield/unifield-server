<%!
    import itertools
    import cherrypy
    import markupsafe

    def br(text):
        return text.replace('\\n', markupsafe.Markup('<br />'))
%>
<%
    object = "new ListView('%s')" % name
    if o2m:
        object = "new One2Many('%s')" % name
%>
<script type="text/javascript">
var auto_field = $('#_terp_auto_refresh');
var model = $('#_terp_model').val();
if (auto_field && auto_field.val()){
    if (global_list_refresh) {
        clearTimeout(global_list_refresh);
    }
    global_list_refresh = setTimeout(function(model) {
       if (model == $('#_terp_model').val()) {
           new ListView('_terp_list').reload(undefined, undefined, undefined, undefined, undefined, undefined, undefined, true);
       }
    }, 1000*auto_field.val(), model);
}

</script>
<%def name="make_editors(data=None)">
    % if editable and editors:
        <tr class="grid-row editors" record="${(data and data['id']) or -1}">
            % if selector:
                <td class="grid-cell selector">&nbsp;</td>
            % endif
            <td class="grid-cell selector" style="text-align: center; padding: 0;">
                <!-- begin hidden fields -->
                % for field, field_attrs in hiddens:
                    ${editors[field].display()}
                % endfor
                <!-- end of hidden fields -->
            </td>
            <% cnt = 1 %>
            % for i, (field, field_attrs) in enumerate(headers):
                % if field == 'button':
                    <td class="grid-cell"></td>
                % elif field_attrs.get('displayon') not in ('noteditable', 'notedition'):
                    % if field_attrs.get('displayon') == 'editable':
                       <% cnt -= 1 %>
                    % endif
                    <td class="grid-cell ${field_attrs.get('type', 'char')}"
                        % if field_attrs.get('attrs'):
                            ${py.attrs(id=field_attrs.get('prefix'),attrs=field_attrs.get('attrs'),widget=field_attrs.get('prefix')+'/'+field_attrs.get('name',''))}
                        % endif

                        % if cnt > 1:
                            colspan="${cnt}"
                        % endif
                    >
                        ${editors[field].display()}
                    </td>
                    <% cnt = 1 %>
                % else:
                   <% cnt += 1 %>
                % endif
            % endfor
            <td class="grid-cell selector" style="text-align: center; padding: 0;">
                <img alt="save record" src="/openerp/static/images/listgrid/save_inline.gif"
                    class="listImage editors oe_form_button_save_line" border="0" title="${_('Update')}"
                    onclick="${object}.save(${(data and data['id']) or 'null'})"/>
            </td>
        </tr>
    % endif
</%def>

<%def name="make_row(data, row_num)">
    <%
        if row_num % 2:
            row_class = 'grid-row-even'
        else:
            row_class = 'grid-row-odd'

        if 'form' not in view_mode:
            row_class = '%s-nosel' % row_class
    %>

    % if editors:
        <tr class="grid-row inline_editors ${row_class} ${data['id'] and data['id'] in noteditable and 'noteditable' or ''}" record="${data['id']}"
        % if data['id'] in notselectable:
            notselectable=1
        % endif
        >
    % else:
        <tr class="grid-row ${row_class}" record="${data['id']}"
        % if data['id'] in notselectable:
            notselectable=1
        % endif
        >
    % endif
    % if selector:
        <td class="grid-cell selector">
        % if not data['id'] or data['id'] not in notselectable:
            <%
                nosidedar = name != '_terp_list' and 'true' or 'false'
                selector_click = "new ListView('%s').onBooleanClicked(!this.checked, '%s', %s);" % (name, data['id'], nosidedar)
                if selector == "radio":
                    selector_click += " do_select();"
            %>
            <input type="${selector}" class="${selector} grid-record-selector ignore_changes_when_leaving_page"
                id="${name}/${data['id']}" name="${(checkbox_name or None) and name}"
                value="${data['id']}"
                onclick="${selector_click}"/>
        % endif
        </td>
    % endif
    % for field, field_attrs in hiddens:
        ${data[field].display()}
    % endfor

    % if editable:
        <td class="grid-cell selector">
            % if not editors:
                % if (not data['id'] or data['id'] not in noteditable) and not hide_edit_button:
                <img alt="edit record" src="/openerp/static/images/iconset-b-edit.gif"
                    class="listImage" border="0" title="${_('Edit')}"
                    onclick="editRecord(${data['id']}, '${source}')"/>
                % endif
            % elif (not data['id'] or data['id'] not in noteditable) and not hide_edit_button:
                <%
                    if o2m and not data['id']:
                        edit_image = '/openerp/static/images/listgrid/save_inline.gif'
                    else:
                        edit_image = '/openerp/static/images/iconset-b-edit.gif'
                %>
                % if bothedit:
                    <img alt="edit record" src="${edit_image}"
                        class="listImage" border="0" title="${_('Inline Edit')}"
                        onclick="listgridValidation('${name}', ${o2m or 0}, ${data['id']})"/>
                    % if (not nopopup or not data['id'] or data['id'] not in nopopup):
                    <img alt="edit record" src="/openerp/static/images/icons/stock_align_left_24.png"
                        class="listImage" border="0" title="${_('Edit')}"
                        onclick="listgridValidation('${name}', ${o2m or 0}, ${data['id']}, false)" />
                    % else:
                        <img src="/openobject/static/images/fancybox/blank.gif" alt="" width="24" class="listImage" border="0" title="" onclick="listgridValidation('${name}', ${o2m or 0}, ${data['id']})"/>
                    % endif

                % else:
                    <img alt="edit record" src="${edit_image}"
                        class="listImage" border="0" title="${_('Edit')}"
                        onclick="listgridValidation('${name}', ${o2m or 0}, ${data['id']})"/>
                % endif
            % endif
        </td>
    % endif
    % for i, (field, field_attrs) in enumerate(headers):
        %if field == 'button':
            <td class="grid-cell">
                ${buttons[field_attrs-1].display(parent_grid=name, **buttons[field_attrs-1].params_from(data))}
            </td>
        % elif field == 'separator':
            <td class="grid-cell"><b>|</b></td>
        % elif field_attrs.get('displayon') != 'editable':
            <td class="grid-cell ${field_attrs.get('type', 'char')}"
                style="${(data[field].color or None) and 'color: ' + data[field].color};"
                sortable_value="${data[field].get_sortable_text()}">\
                % if impex:
                    <a href="javascript: void(0)" onclick="do_select('${data['id']}')">${data[field].display()}</a>\
                % elif (edit_inline == -1 or not edit_inline or field_attrs.get('displayon') != 'notedition'):
<span>${data[field].display()}</span>\
                % endif
</td>
        % endif
    % endfor
    % if editable and not hide_delete_button:
        <td class="grid-cell selector">
            % if m2m:
                <img src="/openerp/static/images/iconset-b-remove.gif" class="listImage"
                    border="0" title="${_('Delete')}"
                    onclick="new Many2Many('${name}').remove(${data['id']}); return false;"/>
            % elif o2m:
                <img src="/openerp/static/images/iconset-b-remove.gif" class="listImage"
                    border="0" title="${_('Delete')}"
                    onclick="new One2Many('${name}').rm(${data['id']}, this); return false;"/>
            % else:
                <img src="/openerp/static/images/iconset-b-remove.gif" class="listImage"
                    border="0" title="${_('Delete')}"
                    onclick="new ListView('${name}').remove(${data['id']}, this)"/>
            % endif
        </td>
    % endif
    </tr>
</%def>

<div class="box-a list-a">
% if any([field != 'button' and field_attrs.get('filter_selector') for field, field_attrs in headers+hiddens]):
<div class="o2m_filter_block">
    <table id="${name}_o2m_filter" class="o2m_header_filter"><tr>
        % for (field, field_attrs) in headers+hiddens:
            % if field != 'button' and field_attrs.get('filter_selector'):
               <% has_filter = True %>
                <td> ${field_attrs['string']|br}:
                    % if field_attrs['type'] == 'selection':
                        <select id="${name}_${field}" class="paging ignore_changes_when_leaving_page" style="width: auto" field="${field}" kind="selection">
                            <option value=""></option>
                            % for key, val in field_attrs['selection']:
                                <option value="${key}">${val}</option>
                            % endfor
                        </select>
                    % elif field_attrs['type'] == 'boolean':
                        <select id="${name}_${field}" class="paging ignore_changes_when_leaving_page" style="width: auto" field="${field}" kind="boolean">
                            <option value=""></option>
                            <option value="t">${_('Yes')}</option>
                            <option value="f">${_('No')}</option>
                        </select>
                    % else:
                        <input id="${name}_${field}" type="text" class="paging ignore_changes_when_leaving_page" style="width: auto" field="${field}" onkeydown="if (event.keyCode == 13) new ListView('${name}').update_o2m_filter();"/>
                    % endif
                </td>
            % endif
        % endfor
        <td><button type="button" onclick="new ListView('${name}').update_o2m_filter()">${_('Search')}</button></td>
        <td><button type="button" onclick="new ListView('${name}').clear_filter()">${_('Clear')}</button></td>
    </table>
</div>
% endif

    <div class="inner">
        <table id="${name}" class="gridview" width="100%" cellspacing="0" cellpadding="0">
            % if pageable:
                <tr class="pagerbar">
                    <td colspan="2" class="pagerbar-cell" align="right">
                        <table class="pager-table">
                            <tr>
                                <td class="pager-cell">
                                    <h2>${string}</h2>
                                </td>
                                <td style="min-width: 16px">
                                    <img src="/openerp/static/images/load.gif" width="16" height="16" title="loading..." class="loading-list" style="display: none;"/>
                                </td>
                                % if editable:
                                    <td class="pager-cell-button">
                                        % if m2m:
                                            % if not hide_new_button:
                                            <button title="${_('Add records...')}" id="${name}_add_records" type="button">
                                                    ${_('Add')}
                                            </button>
                                            % endif
                                        % elif o2m:
                                           % if not hide_new_button:
                                            <button title="${_('Create new record.')}" id="${name}_btn_"
                                                % if button_attrs:
                                                attrs="${button_attrs}"
                                                % endif
                                                onclick="listgridValidation('${name}', '${o2m or 0}', -1); return false;" type="button" class="oe_form_button_create">
                                                    ${_('New')}
                                            </button>

                                            % if extra_button:
                                                <button title="${extra_button.get('string')}" id="${name}_btn2_"
                                                    % if extra_button.get('attrs'):
                                                    attrs="${extra_button.get('attrs')}"
                                                    % endif
                                                    onclick="listgridValidation('${name}', '${o2m or 0}', -1); return false;" type="button" class="oe_form_button_create"
                                                    oncontextmenu="showBtnSdref(event, 'tree_button', 'None', '0', '${name}');"
                                                    >
                                                        ${extra_button.get('string')}
                                                </button>
                                            % endif
                                           % endif
                                        % else:
                                            % if not dashboard and not hide_new_button:
                                                <button id="${name}_new" title="${_('Create new record.')}" class="oe_form_button_create" type="button">${_('New')}</button>
                                                % if editors:
                                                    <script type="text/javascript">
                                                        jQuery('[id=${name}_new]').click(function() {
                                                            listgridValidation('${name}', '${o2m or 0}', -1);
                                                            return false;
                                                        });
                                                    </script>
                                                % else:
                                                    <script type="text/javascript">
                                                        jQuery('[id=${name}_new]').click(function() {
                                                            editRecord(null);
                                                            return false;
                                                        });
                                                    </script>
                                                % endif
                                            % endif
                                        % endif
                                        % if not m2m and not dashboard and editors:
                                            <script type="text/javascript">
                                                jQuery(document).ready(function() {
                                                    validateList('${name}')
                                                });
                                            </script>
                                        % endif
                                    </td>
                                    <td class="pager-cell-button" style="display: none;">
                                        % if not hide_delete_button:
	                                        % if m2m:
	                                            <button id="${name}_delete_record" title="${_('Delete record(s).')}" type="button">
	                                                ${_('Delete')}
	                                            </button>
	                                        % else:
	                                            <button id="${name}_delete_record" title="${_('Delete record(s).')}"
	                                                onclick="new ListView('${name}').remove(null,this); return false;" type="button">
	                                                    ${_('Delete')}
	                                            </button>
	                                        % endif
                                        % endif
                                    </td>
                                % endif
                                    <td class="pager-cell" id="${name}_extra_text" style="padding-left: 20px;">
                                    </td>
                                % if filter_selector:
                                    % if isinstance(filter_selector[0], list):
                                        % for iter, filter in enumerate(filter_selector):
                                            <td class="pager-cell" style="width: 90%">
                                                <div class="pager">
                                                    <select id="${name}_filter_${iter}"
                                                        class="paging ignore_changes_when_leaving_page"
                                                        onchange="new ListView('${name}').update_filter()"
                                                        onload="new ListView('${name}').update_filter()">
                                                </div>
                                                <% i = 0 %>
                                                % for filtername, domain in filter:
                                                    <option domain="${domain}" ${i == default_selector[iter] and 'selected="selected"' or ""}>${filtername}</option>
                                                    <% i += 1 %>
                                                % endfor
                                            </td>
                                        % endfor
                                    % else:
                                        <td class="pager-cell" style="width: 90%">
                                            <div class="pager">
                                                 <select id="${name}_filter"
                                                    class="paging ignore_changes_when_leaving_page"
                                                    onchange="new ListView('${name}').update_filter()"
                                                    onload="new ListView('${name}').update_filter()">
                                            </div>
                                            <% i = 0 %>
                                            % for filtername, domain in filter_selector:
                                                <option domain="${domain}" ${i == default_selector and 'selected="selected"' or ""}>${filtername}</option>
                                                <% i += 1 %>
                                            % endfor
                                        </td>
                                    % endif
                                % else:
                                <td class="pager-cell" style="width: 90%">
                                </td>
                                % endif
                                <td class="pager-cell" style="width: 90%">
                                    ${pager.display()}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            % endif
            <tr>
                <td colspan="2" class="grid-content">
                    <table id="${name}_grid" class="grid" width="100%" cellspacing="0" cellpadding="0" style="background: none;">
                        <thead>
                            <tr class="grid-header">
                                % if selector:
                                    <th width="1" class="grid-cell selector">
                                        % if selector == 'checkbox':
                                            <input type="checkbox" class="checkbox grid-record-selector ignore_changes_when_leaving_page" id="${name}_check_all"  onclick="new ListView('${name}').checkAll(!this.checked)"/>
                                        % endif
                                        % if selector != 'checkbox':
                                            <span>&nbsp;</span>
                                        % endif
                                    </th>
                                % endif
                                % if editable:
                                    <th class="grid-cell selector"><div style="width: 0;"></div></th>
                                % endif
                                % for (field, field_attrs) in headers:
                                    % if field == 'button':
                                        % if selector:
                                            <th class="grid-cell">
                                                ${buttons[field_attrs-1].display(parent_grid=name, **buttons[field_attrs-1].params_header())}
                                            </th>
                                        % else:
                                            <th class="grid-cell"><div style="width: 0;"></div></th>
                                        % endif
                                    % elif field_attrs.get('displayon') != 'editable':
                                    % if (field_attrs.get('function') and not field_attrs.get('store') and not field_attrs.get('allow_sort')) and not field_attrs.get('sort_column') or field_attrs.get('not_sortable'):
                                        <th id="grid-data-column/${(name != '_terp_list' or None) and (name + '/')}${field}" class="grid-cell ${field_attrs.get('type', 'char')}" kind="${field_attrs.get('type', 'char')}">${field_attrs['string']|br}</th>
                                    % else:
                                        <th id="grid-data-column/${(name != '_terp_list' or None) and (name + '/')}${field}" class="grid-cell ${field_attrs.get('type', 'char')}" kind="${field_attrs.get('type', 'char')}" style="cursor: pointer;" onclick="new ListView('${name}').sort_by_order('${field}', this)"
                                        % if field_attrs.get('sort_column'):
                                            sort_column="${field_attrs.get('sort_column')}"
                                        % endif
                                        >${field_attrs['string']|br}</th>
                                    % endif
                                    % endif
                                % endfor
                                % if editable:
                                    <th class="grid-cell selector"><div style="width: 0;"></div></th>
                                % endif
                            </tr>
                        </thead>
                        <tbody>
                            % if edit_inline == -1:
                                ${make_editors()}
                            % endif
                            % for i, d in enumerate(data):
                                % if d['id'] == edit_inline:
                                    ${make_editors(d)}
                                % else:
                                    ${make_row(d, i)}
                                % endif
                            % endfor
                            % if concurrency_info:
                                <tr style="display: none">
                                    <td>${concurrency_info.display()}</td>
                                </tr>
                            % endif
                            % for i in range(min_rows - len(data)):
                                % if editors:
                                    <tr class="grid-row inline_editors ${hide_new_button and 'noteditable' or ''}">
                                % else:
                                    <tr class="grid-row">
                                % endif
                                % if selector:
                                    <td width="1%" class="grid-cell selector">&nbsp;</td>
                                % endif
                                % if editable:
                                    <td style="text-align: center" class="grid-cell selector">&nbsp;</td>
                                % endif
                                % for i, (field, field_attrs) in enumerate(headers):
                                    % if field == 'button':
                                        <td class="grid-cell">&nbsp;</td>
                                    % elif field_attrs.get('displayon') != 'editable':
                                        <td class="grid-cell">&nbsp;</td>
                                    % endif
                                % endfor
                                % if editable:
                                    <td style="text-align: center" class="grid-cell selector">&nbsp;</td>
                                % endif
                                </tr>
                            % endfor
                        </tbody>
                        % if field_total or field_real_total or field_sum_field:
                            <tfoot>
                                <tr class="field_sum">
                                    % if selector:
                                        <td width="1%" class="grid-cell">&nbsp;</td>
                                    % endif
                                    % if editable:
                                        <td width="1%" class="grid-cell">&nbsp;</td>
                                    % endif
                                    % for i, (field, field_attrs) in enumerate(headers):
                                        % if field == 'button':
                                            <td class="grid-cell"><div style="width: 0;"></div></td>
                                        % else:
                                            <td class="grid-cell" id="total_sum_value" nowrap="nowrap">
                                                % if 'sum' in field_attrs:
                                                    % for key, val in field_total.items():
                                                        % if field == key:
                                                            <span class="sum_value_field" id="${field}"
                                                            % if field_attrs.get('sum_selected'):
                                                                sum_selected="1"
                                                            % endif
                                                            >${val[1]}</span>
                                                        % endif
                                                    % endfor
                                                % elif 'real_sum' in field_attrs:
                                                    % for key, val in field_real_total.items():
                                                        % if field == key:
                                                            <span class="sum_value_field" id="${field}">${val[1]}</span>
                                                        % endif
                                                    % endfor
                                                % elif 'sum_field' in field_attrs:
                                                    <span class="sum_value_field super_sum" id="${field_attrs['sum_field']}">${field_sum_field.get(field, '')}</span>
                                                % else:
                                                    &nbsp;
                                                % endif
                                            </td>
                                        % endif
                                    % endfor
                                    % if editable:
                                        <td width="1%" class="grid-cell">&nbsp;</td>
                                    % endif
                                </tr>
                            </tfoot>
                        % endif
                    </table>
                    % if editors:
                        <script type="text/javascript">
                            /* In editable grid, clicking on empty row will create new and on existing row will edit. */
                           jQuery('table[id=${name}_grid] tr.grid-row').each(function(index, row) {
                               if (! jQuery(row).hasClass('noteditable')) {
                               jQuery(row).click(function(event) {
                                   if (jQuery('table[id=${name}]').hasClass("readonlyfield")
                                   &&  jQuery(row).hasClass("inline_editors"))
                                   {
                                       return;
                                   }
                                   if (!jQuery(event.target).is(':input, img, option, a.listImage-container, td.m2o_coplition')) {
                                       var record_id = parseInt(jQuery(row).attr('record'), 10) || -1;
                                       listgridValidation('${name}','${o2m or 0}', record_id);
                                   }
                               });
                               }
                               % if bothedit:
                                else {
                                    jQuery(row).click(function(event) {
                                        if (jQuery(event.target).is('img')) {
                                            return;
                                        }
                                        var rec_id = parseInt(jQuery(row).attr('record'), 10);
                                        if (rec_id) {
                                            new One2Many('${name}', false).edit(rec_id,  true);
                                        } else {
                                            var current_id = jQuery(idSelector('${name}')).attr('current_id');
                                            if (current_id) {
                                                new ListView('${name}').save(current_id);
                                            }
                                        }
                                    });
                                }
                               % endif
                           });
                        </script>
                    % else:
                        % if 'form' in view_mode:
                            <script type="text/javascript">
                                var view_type;
                                var editable;
                                if ('${name}' == '_terp_list') {
                                    view_type = jQuery('#_terp_view_type').val();
                                    editable = jQuery('#_terp_editable').val();
                                }
                                else {
                                    view_type = jQuery('[id=${name}/_terp_view_type]').val();
                                    editable = jQuery('[id=${name}/_terp_editable]').val();
                                }

                                jQuery('table[id=${name}_grid] tr.grid-row').click(function(event) {
                                    var $this = jQuery(this);
                                    if(jQuery(event.target).is('img, input, a.listImage-container')
                                     || view_type != 'tree'
                                     || !$this.attr('record')
                                     || $this.attr('notselectable') ) {
                                        return;
                                    }
                                     if (event.ctrlKey) {
                                         return;
                                    }
                                    do_select($this.attr('record'), '${name}');
                                });
                            </script>
                        % endif
                    % endif
                    <script type="text/javascript">
                        // force attrs evaluation after listgrid loading
                        // (otherwise this won't be catched by form_hookAttrChange() as we don't have any 'id')
                        list_hookStateChange('${name}');
                        list_hookAttrChange('${name}');
                    </script>
                </td>
            </tr>
            % if pageable:
                <tr class="pagerbar">
                    <td class="pagerbar-cell" align="right">${pager.display(pager_id=2)}</td>
                </tr>
            % endif
        </table>
    </div>
</div>
