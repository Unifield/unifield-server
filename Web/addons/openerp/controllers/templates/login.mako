<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Login")}</title>
    <script type="text/javascript">
        // replace existing openLink to intercept transformations of hash-urls
        var openLink = function (url) {
            jQuery(document).ready(function () {
                var form = jQuery('#loginform');
                var separator = (form.attr('action').indexOf('?') == -1) ? '?' : '&';
                form.attr('action',
                          form.attr('action') + separator + jQuery.param({'next': url}));
            })
        }
        function disable_save() {
            var pass = $("#show_password").val()
            $("#password").val(pass);
            $("#show_password").val(false);
            $("#replace_password").show();
            $("#replace_password").val(Array(pass.length+1).join('\u2022'));
            $("#show_password").remove();
            $("#loginform").submit();
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
                <form action="${py.url(target)}" method="post" name="loginform" id="loginform" style="padding-bottom: 5px; min-width: 100px;">
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
                                                    <option value="${v}" ${db and v.lower()==db.lower() and "selected" or ""}>${v}</option>
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
                                    <td class="label"><label for="show_password">${_("Password:")}</label></td>
                                    <td style="padding: 3px;"><input type="password" id="show_password" name="show_password" class="db_user_pass" autocomplete="off" onkeydown = "if (event.keyCode == 13) disable_save()"/>
                                    <input id="replace_password" type="text" class="db_user_pass" style="display:none;"/>
                                    <input type="hidden" name="password" id="password" />
                                    </td>

                                </tr>
                                <tr>
                                    <td></td>
                                    <td class="db_login_buttons">
                                        % if cp.config('dbbutton.visible', 'openerp-web'):
                                            <button type="button" class="static_boxes" tabindex="-1" onclick="location.href='${py.url('/openerp/database')}'" id="databases">${_("Databases")}
                                            </button>
                                        % endif
                                        <button type="button" class="static_boxes" onclick="disable_save()" id="login">${_("Login")}</button>
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

                % if info:
                    <div class="information">${info|n}</div>
                % endif
            </td>

            <td class="vision">
                <fieldset class="box">
                    <img src="/openerp/static/images/stock/logo.png" alt=""/>
                    <p>
                    ${_("All MSF missions will share UniField, integrating finance and supply, enhancing functional and technical capacities, improving visibility and transparency in the management of our operations.")}</p>
                </fieldset>
            </td>
        </tr>
    </table>
                <div style="margin-top: 10px; height: 150px">
                </div>
    <%include file="footer.mako" args="multi_host=multi_host, sync_user=sync_user, dblen=len(dblist)"/>
</%def>
