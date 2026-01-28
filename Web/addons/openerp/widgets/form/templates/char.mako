% if editable:
    <span class="char">
        <input type="${password and 'password' or 'text'}" size="1"
            id="${name}" name="${name}" class="${css_class}"
        % if translatable:
            translatable="1"
        % endif
        % if ro_by_trans:
            ro_by_trans="1"
        % endif
            ${py.attrs(attrs, kind=kind, maxlength=size, value=value, required=required and 1 or 0, fld_readonly=1 if readonly_before_state else 0)}/>
        % if translatable and ( not readonly_before_state or ro_by_trans ) :
            <img src="/openerp/static/images/stock/stock_translate.png" class="translatable" id="${name}_translatable"/>
            <script type="text/javascript">
                jQuery(idSelector('${name}_translatable')).click(function() {
                    var params = {
                        'relation': '${model}',
                        'id': jQuery('#_terp_id').attr('value'),
                        'data': jQuery('#_terp_context').attr('value'),
                        'clicked_field': '${name}'
                    };
                    translate_fields(null, params);
                });
            </script>
        % endif
        % if editable_style:
            <span id="${name}_ro" />
        % endif
        % if error:
            <span class="fielderror">${error}</span>
        % endif
        % if password:
            <img
                src="/openerp/static/images/eye.png"
                alt=""
                title="${_('Hold to show password')}"
                style="
                    width:12px;
                    height:12px;
                    position:absolute;
                    right:8px;
                    top:50%;
                    transform:translateY(-50%);
                    cursor:pointer;
                "
                onmousedown="document.getElementById('${name}').type='text';"
                onmouseup="document.getElementById('${name}').type='password';"
                onmouseleave="document.getElementById('${name}').type='password';"
            />
        % endif
    </span>
% endif
% if not editable and not password:
<span kind="${kind}" id="${name}" value="${value}">${value}</span>\
% endif
% if not editable and password and value:
    <span>${'*' * len(value)}</span>
% endif
