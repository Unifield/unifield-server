% if kind == 'boolean':
<input type="checkbox" name="${name}" id="${name}" kind="${kind}" class="checkbox" readonly="readonly" disabled="disabled" ${py.checker(val)} value="${val}">
% else:
<span class="text_null_boolean" name="${name}" id="${name}" >${val}</span>
% endif
