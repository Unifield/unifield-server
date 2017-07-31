<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>
<%def name="current_for(name)"><%
    if form.name == name: context.write('current')
%></%def>
<%def name="header()">
    <title>${form.string}</title>

    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css"/>
    <script type="text/javascript">
        function on_create() {
            new openerp.ui.WaitBox().showAfter(2000);
            return true;
        }
    </script>
    % if error:
        <script type="text/javascript">
            var $error_tbl = jQuery('<table class="errorbox">');
            $error_tbl.append('<tr><td style="padding: 4px 2px;" width="10%"><img src="/openerp/static/images/warning.png"></td><td class="error_message_content">${error["message"]}</td></tr>');
            $error_tbl.append('<tr><td style="padding: 0 8px 5px 0; vertical-align:top;" align="right" colspan="2"><a class="button-a" id="error_btn" onclick="$error_tbl.dialog(\'close\');">OK</a></td></tr>');

            jQuery(document).ready(function () {
                jQuery(document.body).append($error_tbl);
                var error_dialog_options = {
                    modal: true,
                    resizable: false,
                    title: '<div class="error_message_header">${error.get("title", "Warning")}</div>'
                };
                % if error.get('redirect_to'):
                    error_dialog_options['close'] = function( event, ui ) {
                        $(location).attr('href','${error['redirect_to']}');
                    };
                % endif
                $error_tbl.dialog(error_dialog_options);
            })
        </script>
    % endif
</%def>

<%def name="content()">
	<table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>
    <div class="db-form">
        <h1>Automated instance creation detected</h1>

        <div class='auto_instance_text'>
            <p>If you have checked the following points and you are ready to start
               instance creation, login to start. Points to check:
                <ul>
                    <li>truc 1</li>
                    <li>truc 2</li>
                </ul>
            </p>
        </div>
        <div class="auto_create_text">
            <p>flklfjjffdsqf  fdsq fsqf dsqf </p>
        </div>
        <div>${form.display()}</div>
    </div>
<%include file="footer.mako"/>
</%def>
