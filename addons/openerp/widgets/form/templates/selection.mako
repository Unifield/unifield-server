% if editable:
    <select 
        id="${name}"
        kind="${kind}"
        name="${name}"
        type2 = "${type2}"
        operator="${operator}"
        class="${css_class}"
        search_context="${search_context}"
        ${py.attrs(attrs, fld_readonly=1 if readonly_before_state else 0)}>
        ## add empty option only if no empty option exist
        ## and no default value is set
        % if all(label for _, label in options) and (not required or add_empty):
            <option value=""></option>
        % endif
        % for (val, label) in options:
            <option value="${val or ''}" ${py.selector(val==(value or False))}>${label}</option>
        % endfor
    </select>
    % if editable_style:
    <span id="${name}_ro" />
    % endif
    % if error:
    <span class="fielderror">${error}</span>
    % endif
% else:
    <span kind="${kind}" id="${name}" value="${value}"
     ${py.attrs(fld_readonly=1 if readonly_before_state else 0)}>
    ${dict(options).get(value)}</span>
% endif

