<button class="button-b oe_form_button_${btype}"
        id="${name}"
        name="${name}"
        type="button"
        href="javascript: void(0)"
        title="${help}"
        onclick="buttonClicked('${name}', '${btype}', '${model}', '${id}', getNodeAttribute(this, 'confirm'), '${target}', getNodeAttribute(this, 'context'), '${set_ids}', '${ignore_access_error}');"
        oncontextmenu="showBtnSdref(event, '${name}', '${model}', '${id}');"
        style="height: 20px;"
        ${py.attrs(attrs, confirm=confirm, context=ctx)}
        % if force_readonly:
            disabled="disabled"
        % endif
        >
    % if string:
        % if icon:
            <img src="${icon}" width="16" height="16" alt="">&nbsp;<span>${string}</span>
        % else:
            <div style="text-align: center; padding-top: 3px;">${string}</div>
        % endif
    %else:
        <img align="middle" src="${icon}" width="16" height="16" alt="">
    % endif
    % if help:
        <span class="help" title="${help}">?</span>
    % endif
</button>

% if default_focus:
    <script type="text/javascript">
       jQuery('#${name}').focus();
       jQuery('#${name}').keypress(function(evt) {
            if(evt.keyCode == 0) {
                jQuery(this).click();
            }
            if(evt.keyCode == 27) {
                window.close();
            }
       });
    </script>
% endif

