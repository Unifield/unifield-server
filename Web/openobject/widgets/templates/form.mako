<form ${py.attrs(attrs)} class="${css_class}">
    % if hidden_fields:
    <div>
        % for child in hidden_fields:
        ${display_member(child)}
        % endfor
    </div>
    % endif
    <table class="form-container">
        % if display_string:
            <h1>${string}</h1>
            % if display_description:
            <div style="
                margin-top: 2em;
                margin-bottom: 2em;
                margin-left: 25%;
                width: 50%;
                font-size: 1.3em;
                "> ${description}</div>
            % endif
        % endif
        % for child in fields:
        <%
            error = error_for(child)
            label = label_for(child)
            help = help_for(child)
        %>
        <tr>
            <td class="label">
                % if help:
                    <label id="${child.name}.label" for="${child.name}" class="fieldlabel help" title="${help}">${label}</label>
                    <span class="help" title="${help}">?</span>
                % else:
                    <label id="${child.name}.label" for="${child.name}" class="fieldlabel">${label}</label>
                % endif
            </td>
            <td class="fieldcol">
                ${display_member(child)}
                % if error:
                <span class="fielderror">${error}</span>
                % endif
            </td>
        </tr>
        % endfor
        <tr>
            <td>&nbsp;</td>
            <td align="right" style="padding: 0px 5px 5px 0px;">
            % if not replace_password_fields:
                <button type="submit" class="static_boxes">${submit_text}</button>
            % else:
                <script type="text/javascript">
                function replace_pass_submit() {
                    var this_form = false;
                    % for src_field, target_field in replace_password_fields.items():
                        if (!this_form) {
                            this_form = $("#${target_field}").attr('form');
                            var result = true;
                            if (this_form.onsubmit) {
                                result = this_form.onsubmit.call(this_form);
                            }
                            if (!result) {
                                return false;
                            }
                        }
                        var ${src_field}_val = $("#${src_field}").val()
                        var fake_${src_field} = jQuery('<input type="text"/>');
                        fake_${src_field}.addClass($("#${src_field}").attr('class'));
                        fake_${src_field}.val(Array(${src_field}_val.length+1).join('\u2022'));
                        $("#${target_field}").val(${src_field}_val);
                        $("#${src_field}").val(false);
                        $("#${src_field}").replaceWith(fake_${src_field});
                    % endfor
                    this_form.submit();
                }
                </script>
                <button type="button" class="static_boxes" onclick="replace_pass_submit()">${submit_text}</button>
            % endif
            </td>
        </tr>
    </table>
</form>
