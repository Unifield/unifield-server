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
                            <table width="100%" align="center" cellspacing="2px" cellpadding="0" style="border:none;">
                                <tr>
                                    <td class="label"><label for="password">${_("New password:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="password" id="password" name="password" class="db_user_pass" autocomplete="off"/>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="label"><label for="password2">${_("Confirm password:")}</label></td>
                                    <td style="padding: 3px;">
                                        <input type="password" id="password2" name="password2" class="db_user_pass" autocomplete="off"/>
                                    </td>
                                </tr>

                                <!-- Hidden fields -->
                                <input type="hidden" name="token" value="${token or ''}"/>
                                <input type="hidden" name="db" value="${db or ''}"/>

                                <tr>
                                    <td></td>
                                    <td class="db_login_buttons">
                                        <button type="submit" class="static_boxes" id="send">${_("Change password")}</button>
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
