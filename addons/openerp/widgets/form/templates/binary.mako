<div>
    % if bin_data and not value_bin_size:
        <input
            type="hidden"
            class="${css_class}"
            kind="${kind}"
            id="${name}"
            name="${name}"
            value="${bin_data}"/>
    % endif
    <div id="${name}_binary_add" style="display: none;">
        % if editable and not readonly and model != 'ir.attachment':
        <input ${py.attrs(attrs)}
            accept="${accept}"
            type="file"
            class="${css_class}"
            kind="${kind}"
            disabled="disabled"
            id="${name}"
            name="${name}"/>
        % elif editable and not readonly and model == 'ir.attachment':
        <input ${py.attrs(attrs)}
            accept="${accept}"
            type="file"
            class="${css_class}"
            kind="${kind}"
            disabled="disabled"
            max-size="${max_attachment_size}"
            id="${name}"
            name="${name}"/>
        % endif
    </div>
    <div id="${name}_binary_buttons" class="binary_buttons">
        <input type="text" value="${value or text or ''}" readonly="readonly"/>
        %if value:
        	<input type="hidden" name="${name}" value="${value}"></input>
       	% endif
        % if (text or value_bin_size) and model == 'ir.attachment' and ctx != 'usb_synchronization' and editable:
        <a class="button-a" href="javascript: void(0)" onclick="save_binary_data('${name}', '${filename}')">${_("Open donation certificate")}</a>
        % elif text and editable:
        <a class="button-a" href="javascript: void(0)" onclick="save_binary_data('${name}', '${filename}')">${_("Save As")}</a>
        % endif
        % if editable and not readonly:
        <a class="button-a" href="javascript: void(0)" onclick="add_binary('${name}')">${_("add attachment")}</a>
        % endif
    </div>
    % if editable and error:
    <span class="fielderror">${error}</span>
    % endif
</div>

