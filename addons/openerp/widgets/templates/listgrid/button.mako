% if visible:
    % if icon:
        <a class="listImage-container" name="${name}" id="${name}" title="${help}" context="${ctx}" ${py.attrs(attrs, confirm=confirm)}
            onclick="new ListView('${parent_grid}').onButtonClick('${name}', '${btype}', ${id}, getNodeAttribute(this, 'confirm'), getNodeAttribute(this, 'context'));"
            oncontextmenu="showBtnSdref(event, '${name}', '${model}', '${id}', '${parent_grid}');">
            <img height="16" width="16" class="listImage" src="${icon}"/>
        </a>
    % else:
        <a class="button-b" name="${name}" id="${name}" href="javascript: void(0)" ${py.attrs(attrs, context=ctx, confirm=confirm)} title="${help}"
            onclick="new ListView('${parent_grid}').onButtonClick('${name}', '${btype}', ${id}, getNodeAttribute(this, 'confirm'), getNodeAttribute(this, 'context'))"
            oncontextmenu="showBtnSdref(event, '${name}', '${model}', '${id}'), '${parent_grid}';">
            ${string}
        </a>
    % endif
% elif not icon:
    <span><img style="display:none" name="${name}" id="${name}" height="16" width="16" class="listImage" src="${icon}" title="${help}" context="${ctx}" ${py.attrs(attrs, confirm=confirm)} onclick="new ListView('${parent_grid}').onButtonClick('${name}', '${btype}', ${id}, getNodeAttribute(this, 'confirm'), getNodeAttribute(this, 'context'))" oncontextmenu="showBtnSdref(event, '${name}', '${model}', '${id}', '${parent_grid}');"/></span>
% endif
