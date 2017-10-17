% if editable:
    <input 
        type="text" 
        kind="${kind}" 
        name='${name}' 
        id ='${name}' 
        value="${value}" 
        class="${css_class}"
        ${py.attrs(attrs, fld_readonly=1 if readonly else 0)}/>
% endif

% if editable and error:
    <span class="fielderror">${error}</span>
% endif

% if not editable:
    <span kind="${kind}" id="${name}" value="${value}">${value}</span>
% endif

