<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Change password")}</title>
    <script type="text/javascript">
        // replace existing openLink to intercept transformations of hash-urls
        var openLink = function (url) {
            jQuery(document).ready(function () {
                var form = jQuery('#changepasswordform');
                var separator = (form.attr('action').indexOf('?') == -1) ? '?' : '&';
                form.attr('action',
                          form.attr('action') + separator + jQuery.param({'next': url}));
            })
        }
        function disable_save() {
            email = $('#email').val()
            if (email && !email.includes('@')) {
                alert(_('An email address must contain a single @'));
                return false;
            }
            var pass = $("#show_password").val()
            $("#password").val(pass);
            $("#show_password").val(false);
            $("#replace_password").show();
            $("#replace_password").val(Array(pass.length+1).join('\u2022'));
            $("#show_password").remove();
            $("#changepasswordform").submit();
        }
    </script>
</%def>

<%def name="content()">
    <table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>

    <table id="logintable" class="view" cellpadding="0" cellspacing="0" style="padding-top: 25px; border:none;">
        <tr>
            <td class="loginbox">
                <form action="${py.url(target)}" method="post" name="changepasswordform" id="changepasswordform" style="padding-bottom: 5px; min-width: 100px;">
                    % for key, value in origArgs.items():
                        <input type="hidden" name="${key}" value="${value}"/>
                    % endfor
                    <input name="login_action" value="login" type="hidden"/>

                    <fieldset class="box">
                        <legend style="padding: 4px;">
                            <img src="/openerp/static/images/stock/stock_person.png" alt=""/>
                        </legend>
                        <div class="box2" style="padding: 5px 5px 20px 5px">
                            <table width="100%" align="center" cellspacing="2px" cellpadding="0" style="border:none;">
                                <tr>
                                    <td class="label"><label for="db">${_("Database:")}</label></td>
                                    <td style="padding: 3px;">
                                        % if dblist is None:
                                            <input type="text" name="db" id="db" class="db_user_pass" value="${db}"/>
                                        % else:
                                            <select name="db" id="db" class="db_user_pass">
                                                % for v in dblist:
                                                    <option value="${v}" ${v==db and "selected" or ""}>${v}</option>
                                                % endfor
                                            </select>
                                        % endif
                                    </td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="user">${_("User:")}</label></td>
                                    <td style="padding: 3px;"><input type="text" id="user" name="user" class="db_user_pass" value="${user}" autofocus="true" autocomplete="off"/></td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="show_password">${_("Current password:")}</label></td>
                                    <td style="padding: 3px;"><input type="password" id="show_password" name="show_password" class="db_user_pass" autocomplete="off" onkeydown = "if (event.keyCode == 13) disable_save()"/>
                                    <input id="replace_password" type="text" class="db_user_pass" style="display:none;"/>
                                    <input type="hidden" name="password" id="password" />
                                    </td>

                                </tr>
                                <tr>
                                    <td class="label"><label for="show_password">${_("New password:")}</label></td>
                                    <td style="padding: 3px;"><input type="password" id="show_new_password" name="new_password" class="db_user_pass" autocomplete="off" onkeydown = "if (event.keyCode == 13) disable_save()"/>
                                    <input id="new_password" type="text" class="db_user_pass" style="display:none;"/>
                                    </td>

                                </tr>
                                <tr>
                                    <td class="label"><label for="show_password">${_("Confirm new password:")}</label></td>
                                    <td style="padding: 3px;"><input type="password" id="show_confirm_password" name="confirm_password" class="db_user_pass" autocomplete="off" onkeydown = "if (event.keyCode == 13) disable_save()"/>
                                    <input id="confirm_password" type="text" class="db_user_pass" style="display:none;"/>
                                    </td>

                                </tr>
                                <tr>
                                    <td class="label"><label for="email">${_("Email address:")}</label></td>
                                    <td style="padding: 3px;"><input type="input" id="email" name="email" class="db_user_pass" autocomplete="off" value="${email}">
                                    </td>

                                </tr>
                                <tr>
                                    <td></td>
                                    <td class="db_login_buttons">
                                        <button type="button" class="static_boxes" onclick="disable_save()">${_("Update password")}</button>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </fieldset>
                </form>
                % if message:
                    <div class="login_error_message" id="message">${message}</div>
                % endif

                % if tz_offset:
                    <div class="login_error_message" id="badregional">${tz_offset}</div>
                % endif

                % if bad_regional:
                    <div class="login_error_message" id="badregional">${bad_regional}</div>
                % endif

                % if info:
                    <div class="information">${info|n}</div>
                % endif
            </td>

            <td class="vision">
                <fieldset class="box">
                    <img src="/openerp/static/images/stock/password.png" alt=""/>
                    <p>
                    % if expired:
                        ${_("Your password has been reset by an administrator.")}
                    % else:
                        ${_("Your password has expired.")}
                    % endif

                    ${_("Please choose a new password. It must be at least 8 characters long and must contain at least one digit, one capital letter and one special character.")}</p>
                </fieldset>
            </td>
        </tr>
    </table>
                <div style="margin-top: 10px; height: 150px">
                </div>
    
    <%include file="footer.mako"/>
</%def>
