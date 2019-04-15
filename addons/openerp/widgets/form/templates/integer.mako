% if editable:
    <input 
        type="text" 
        kind="${kind}" 
        name='${name}' 
        id ='${name}' 
        value="${value}" 
        class="${css_class}"
        ${py.attrs(attrs, fld_readonly=1 if readonly_before_state else 0)}/>
    % if editable_style:
        <span id="${name}_ro" />
    % endif
% endif

% if editable and error:
    <span class="fielderror">${error}</span>
% endif

% if not editable:
    <span kind="${kind}" id="${name}" value="${value}">${value}</span>
% endif

