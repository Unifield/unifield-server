<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Reset Password")}</title>
</%def>

<%def name="content()">
    <table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>

    <table id="logintable" class="view" cellpadding="0" cellspacing="0" style="padding-top: 25px; border:none;">
        <tr>
            <td class="loginbox">
                <form action="${py.url('/openerp/reset_password/confirm')}" method="post" name="resetform" id="resetform">
                    % if origArgs:
                        % for key, value in origArgs.items():
                            <input type="hidden" name="${key}" value="${value}"/>
                        % endfor
                    % endif

                    <fieldset class="box">
                        <legend style="padding: 4px;">
                            <img src="/openerp/static/images/stock/stock_key.png" alt=""/>
                        </legend>
                        <div class="box2" style="padding: 5px 5px 20px 5px">
                            <div>
                                <h1>${_("Reset of password using email code")}</h1>
                                <p>${_("Please choose a new password. It must be at least 8 characters long and must contain at least one digit, one capital letter and one special character.")}</p>
                            </div>
                            <table width="100%" align="center" cellspacing="2px" cellpadding="0" style="border:none;">
                                <tr>
                                    <td class="label"><label for="login">${_("Login:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="text" id="login" name="login" class="db_user_pass"
                                               value="${data.get('login','')}" autocomplete="off"/>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="email">${_("Email address:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="text" id="email" name="email" class="db_user_pass"
                                               value="${data.get('email','')}" autocomplete="off"/>
                                    </td>
                                </tr>
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
                                    <td class="label"><label for="token">${_("Token:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="password" id="token" name="token" class="db_user_pass"
                                               value="${data.get('token','')}" autocomplete="off"/>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="password">${_("New password:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="password" id="password" name="password" class="db_user_pass" autocomplete="off"/>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="password2">${_("Confirm new password:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="password" id="password2" name="password2" class="db_user_pass" autocomplete="off"/>
                                    </td>
                                </tr>

                                <tr>
                                    <td></td>
                                    <td class="db_login_buttons">
                                        <button type="submit" class="static_boxes" id="send">${_("Change password")}</button>

                                        % if error and error.get('title') == 'Success':
                                            <a href="/openerp/login" style="margin-left:10px;">
                                                <button type="button" class="static_boxes">
                                                    ${_("Return to login page")}
                                                </button>
                                            </a>
                                        % endif
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </fieldset>
                </form>

                % if error:
                    <div class="login_error_message" id="message">${error['message']}</div>
                % endif

            </td>
        </tr>
    </table>

    <%include file="footer.mako"/>
</%def>