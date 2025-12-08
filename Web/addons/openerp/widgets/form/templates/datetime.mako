% if editable:
    <input type="text" 
           id="${name}" 
           name="${name}" 
           autocomplete="OFF" 
           size="3"
           class="${css_class}" 
           ${py.attrs(attrs, kind=kind, value=value, 
                      fld_readonly=1 if readonly_before_state else 0 )}/>
    % if editable_style:
    <span id="${name}_ro" />
    % endif
    % if error:
        <span class="fielderror">${error}</span>
    % endif
    % if not attrs.get('disabled'):
        <img id="${name}_trigger" width="16" height="16" alt="${_('Select')}"
            src="/openerp/static/images/stock/stock_calendar.png"
            class="${css_class}" style="cursor: pointer;"/>
        <script type="text/javascript">
            jQuery("[id='${name}']").each(function(){
                Calendar.setup(
                {
                    inputField : this,
                    button: jQuery(this).siblings('img').get(0),
                    ifFormat : "${format}",
                    showsTime: ${str(picker_shows_time).lower()},
                    onClose: function(cal){
                        cal.destroy();
                    },
                    electric: false,
                % if depends:
                    depends: '${depends}',
                % endif
                });
            });
        </script>
    % endif
% else:
<span kind="${kind}" id="${name}" value="${value}">${value}</span>\
% endif
