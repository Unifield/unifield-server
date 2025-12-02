% if editable:
    % if inline:
        <input id ="${name}" name="${name}" type="text" class="${css_class}" size="1"
            ${py.attrs(attrs, kind=kind, value=value)}/>
    % else:
        <textarea rows="${rows}" id ="${name}" name="${name}" class="${css_class}"
            ${py.attrs(attrs, kind=kind)} style="width: 100%;"
    % if translatable:
        translatable="1"
    % endif
    % if ro_by_trans:
        ro_by_trans="1"
    % endif
        >${value}</textarea>
        % if translatable and ( not readonly_before_state or ro_by_trans ):
            <img src="/openerp/static/images/stock/stock_translate.png" id="${name}_translatable" class="area_translatable" />
            <script type="text/javascript">
                jQuery('#${name}_translatable').click(function() {
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
        <script type="text/javascript">
            if (!window.browser.isWebKit) {
                new openerp.ui.TextArea('${name}');
            }
        </script>
    % endif

    % if error:
        <span class="fielderror">${error}</span>
    % endif
% else:
    <p kind="${kind}" id="${name}" class="raw-text">${value}</p>
% endif

