<%
   if header == True:
       ids = "new ListView('%s').getSelectedRecords()" % parent_grid
       attrs_ = ""
       attrs_with_context = ""
   else:
       ids = id
       attrs_ = py.attrs(attrs, confirm=confirm)
       attrs_with_context = py.attrs(attrs, context=ctx, confirm=confirm)
  
   if btype == 'openform':
       onclickAction="new One2Many('%s', false).edit(%s, 0, 1);" % (parent_grid, id)
   elif btype == 'deletem2m':
       onclickAction="new Many2Many('%s').remove(%s); return false;" % (parent_grid, id)
   else:
       onclickAction="new ListView('%s').onButtonClick('%s', '%s', %s, getNodeAttribute(this, 'confirm'), getNodeAttribute(this, 'context'));" % (parent_grid, name, btype, ids)
   oncontextmenuAction="showBtnSdref(event, '%s', '%s', '%s', '%s');" % (name, model, ids, parent_grid)
%>
% if visible and not force_readonly:
    % if icon:
        <a class="listImage-container" name="${name}" id="${name}" title="${help}" context="${ctx}" ${attrs_}
            onclick="${onclickAction}"
            oncontextmenu="${oncontextmenuAction}">
            <img height="16" width="16" class="listImage" src="${icon}"/>
        </a>
    % else:
        <a class="button-b" name="${name}" id="${name}" href="javascript: void(0)"
            ${attrs_with_context}
            title="${help}"
            onclick="${onClickAction}"
            oncontextmenu="${oncontextmenuAction}">
            ${string}
        </a>
    % endif
% elif not icon:
    <span><img style="display:none" name="${name}" id="${name}" height="16" width="16" class="listImage" src="${icon}" title="${help}" context="${ctx}" ${attrs} onclick="${onClickAction}" oncontextmenu="${oncontextmenuAction}"/></span>
% endif
