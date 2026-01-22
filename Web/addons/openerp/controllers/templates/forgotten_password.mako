<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Forgotten Password")}</title>
</%def>

<%def name="content()">
    <table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>

    <table id="logintable" class="view" cellpadding="0" cellspacing="0" style="padding-top: 25px; border:none;">
        <tr>
            <td class="loginbox">
                <form action="${py.url('/openerp/forgotten_password/send')}" method="post" name="forgottenform" id="forgottenform">
                    % if origArgs:
                        % for key, value in origArgs.items():
                            <input type="hidden" name="${key}" value="${value}"/>
                        % endfor
                    % endif

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
                                    <td class="label"><label for="email">${_("Email:")}</label></td>
                                    <td style="padding: 3px;"><input type="text" id="email" name="email" class="db_user_pass" value="${email}" autofocus="true" autocomplete="off"/></td>
                                </tr>
                                <tr>
                                    <td></td>
                                    <td class="db_login_buttons">
                                        <button type="submit" class="static_boxes" id="send">${_("Send")}</button>
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
