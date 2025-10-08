<%!
import itertools
background = '#F5F5F5'
%>

% if not grp_childs:

% for j, grp_row in enumerate(grp_records):
    <tr class="grid-row-group" parent="${parent_group}" grp_by_id="${grp_row['group_by_id']}"
        records="${grp_row['groups_id']}" style="cursor: pointer; background-color: ${background};"
        ch_records="${map(lambda x: x['id'],grp_row['child_rec'])}" grp_domain="${grp_row['__domain']}"
        grp_context="${grp_row['__context']['group_by']}" grp_level="${grp_row['__level']}">
        % if editable or selectable:
            <td class="grid-cell" ></td>
        % endif
        % for i, (field, field_attrs) in enumerate(headers):
            % if field != 'button':
                <%
                if field_attrs.get('type') != 'progressbar' and i == group_level - 1:
                    if len(group_by_ctx) == 1 and group_by_no_leaf:
                        subgroup_expander = ''
                        subgroup_class = ''
                    else:
                      subgroup_expander = "new ListView('%s').group_by('%s', '%s', '%s', this)" % (
                          name, grp_row['group_by_id'], grp_row['groups_id'], group_by_no_leaf)
                      subgroup_class = 'group-expand'
                else:
                    subgroup_expander = ''
                    subgroup_class = ''
                %>
                <td class="grid-cell ${subgroup_class} ${field_attrs.get('type', 'char')}"
                    onclick="${subgroup_expander}">
                        % if field_attrs.get('type') == 'progressbar':
                            ${grouped[j][field].display()}
                        % elif i != group_level - 1:
                            % if grp_row.get(field):
                                % if field_attrs.get('type') == 'many2one':
                                    ${grp_row.get(field)[-1]}
                                % elif field_attrs.get('type') == 'selection':
                                    % for k in field_attrs.get('selection'):
                                       % if k[0] == grp_row.get(field):
                                            ${k[1]}
                                       % endif
                                    % endfor
                                % else:
                                    ${grp_row.get(field)}
                                % endif
                            % else:
                                <span style="color: #888;">${(i == group_level) and "undefined" or "&nbsp;"|n}</span>
                            % endif
                        % endif
                </td>
            % else:
                <td class="grid-cell" nowrap="nowrap" >
                    <span></span>
                </td>
            % endif
        % endfor
        % if editable:
            <td class="grid-cell selector" >
                <div style="width: 0px;"></div>
            </td>
        % endif
    </tr>
    % for ch in grp_row.get('child_rec'):
        <tr class="grid-row grid-row-group" id="${grp_row.get('groups_id')}" parent="${parent_group}"
            parent_grp_id="${grp_row.get('group_by_id')}" record="${ch.get('id')}"
            style="cursor: pointer; display:none;">
            % for field, field_attrs in hiddens:
                % if field in ch:
                    ${ch[field].display()}
                % endif
            % endfor

            % if editable:
                <td class="grid-cell">
                    % if (not ch.get('id') or ch.get('id') not in noteditable) and not hide_edit_button:
                    <img src="/openerp/static/images/listgrid/edit_inline.gif" class="listImage" border="0"
                         title="${_('Edit')}" onclick="editRecord(${ch.get('id')}, '${source}')"/>
                    % endif
                </td>
            % elif selectable:
                <td class="grid-cell selector">
                    % if not m2m:
                    <%
                        selector_click = "new ListView('%s').onBooleanClicked(!this.checked, '%s');" % (name, ch.get('id'))
                        if selector == "radio":
                            selector_click += " do_select();"
                    %>
                    <input type="${selector}" class="${selector} grid-record-selector"
                        id="${name}/${ch.get('id')}" name="${(checkbox_name or None) and name}"
                        value="${ch.get('id')}"
                        onclick="${selector_click}"/>
                    % endif
                </td>
            % endif
            % for i, (field, field_attrs) in enumerate(headers):
                % if field != 'button':
                    <td class="grid-cell ${field_attrs.get('type', 'char')}"
                        style="${(ch.get(field).color or None) and 'color: ' + ch.get(field).color};"
                        sortable_value="${ch.get(field).get_sortable_text()}">
                        <span>${ch[field].display()}</span>
                    </td>
                % else:
                    <td class="grid-cell" nowrap="nowrap">
                        ${buttons[field_attrs-1].display(parent_grid=name, **buttons[field_attrs-1].params_from(ch))}
                    </td>
                % endif
            % endfor
            % if editable and not hide_delete_button:
                <td class="grid-cell selector">
                    <img src="/openerp/static/images/iconset-b-remove.gif" class="listImage" border="0"
                         title="${_('Delete')}" onclick="new ListView('${name}').remove(${ch.get('id')})"/>
                </td>
            % endif
        </tr>
    % endfor
% endfor

% else: # display only resulting rows
% for j, grp_row in enumerate(grp_childs):
% if pageable:
 <tr parent="${grp_row.get('group_by_id')}">
<%
lenh = len(headers)
if editable:
    lenh += 2
elif selector:
    lenh += 1
%>
    <td colspan="${lenh}" class="pager"><span class="paging" style="float: left;">
   % if pager.prev:
        <a href="#prev" onclick="next_p(this, '${name}', ${group_by_no_leaf}, ${pager.limit}, -1); return false;">
   % endif

        <span class="prev nav${' ' if pager.prev else ' inactive'}">${_("< Previous")}</span>
   % if pager.prev:
        </a>
   % endif
   ${pager.page_info} ${_('of')} ${pager.count}
   % if pager.next:
        <a href="#next" onclick="next_p(this, '${name}', ${group_by_no_leaf}, ${pager.limit}, 1); return false;">
   % endif

        <span class="next nav${' ' if pager.next else ' inactive'}">${_("Next >")}</span>
   % if pager.next:
        </a>
   % endif
   </span>
   </td>
 </tr>
% endif
  % for ch in grp_row.get('child_rec'):
  <tr class="grid-row grid-row-group" id="${grp_row.get('groups_id')}" parent="${grp_row.get('group_by_id')}"
      record="${ch.get('id')}" style="cursor: pointer;">
            % for field, field_attrs in hiddens:
                % if field in ch:
                    ${ch[field].display()}
                % endif
            % endfor

      % if editable:
          <td class="grid-cell">
              % if (not ch.get('id') or ch.get('id') not in noteditable) and not hide_edit_button:
              <img src="/openerp/static/images/iconset-b-edit.gif" class="listImage" border="0"
                   title="${_('Edit')}" onclick="editRecord(${ch.get('id')}, '${source}')"/>
              % endif
          </td>
      % elif selector:
          <td class="grid-cell selector">
              % if not m2m:
              <%
                  selector_click = "new ListView('%s').onBooleanClicked(!this.checked, '%s');" % (name, ch.get('id'))
                  if selector == "radio":
                      selector_click += " do_select();"
              %>
              <input type="${selector}" class="${selector} grid-record-selector"
                  id="${name}/${ch.get('id')}" name="${(checkbox_name or None) and name}"
                  value="${ch.get('id')}"
                  onclick="${selector_click}"/>
              % endif
          </td>
      % endif
      % for i, (field, field_attrs) in enumerate(headers):
          % if field != 'button':
              <td class="grid-cell ${field_attrs.get('type', 'char')}"
                  style="${(ch.get(field).color or None) and 'color: ' + ch.get(field).color};"
                  sortable_value="${ch.get(field).get_sortable_text()}">
                  <span>${ch[field].display()}</span>
              </td>
          % else:
              <td class="grid-cell" nowrap="nowrap">
                  ${buttons[field_attrs-1].display(parent_grid=name, **buttons[field_attrs-1].params_from(ch))}
              </td>
          % endif
      % endfor

      % if editable:
          <td class="grid-cell selector">
              % if not hide_delete_button:
              <img src="/openerp/static/images/iconset-b-remove.gif" class="listImage" border="0"
                   title="${_('Delete')}" onclick="new ListView('${name}').remove(${ch.get('id')})"/>
              % endif
          </td>
      % endif
  </tr>


  % endfor
% endfor
<script type="text/javascript">
list_hookAttrChange('${name}');
</script>


% endif

