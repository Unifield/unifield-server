<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>
<%def name="current_for(name)"><%
    if form.name == name: context.write('current')
%></%def>
<%def name="header()">
    <title>${form.string}</title>

    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css?v=7.0"/>
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
            <p>If you have checked the following points, you can start the
process of instance auto creation by login with the Super admin password. Points to check:
                <ul>
                    <li>A Folder 'UFautoInstall' is present in Unifield/Server folder.</li>
                    <li>This folder contain a file 'uf_auto_install.conf'</li>
                    <li>This file is correct (required fields, correct values)</li>
                    <li>The folder also contain an 'import' directory
(Unifield/Server/UFautoInstall/import)</li>
                    <li>This 'import' directory contain files where the name of
the file is the model to import and the extension is csv (typically,
'account.analytic.journal.csv' and 'account.journal.csv')</li>
                    <li>The connexion to the SYNC_SERVER is ok (credentials,
address, port, ...)</li>
                    <li>The parents instance (HQ, and Coordo if it is a
project) exists and are present as instance in the SYNC_SERVER</li>
                </ul>
            </p>
        </div>
        <div>${form.display()}</div>
    </div>
     <a class="auto_instance_debug" href="/openerp/login/?style=noauto"><img src="/openerp/static/images/icons/idea.png" alt="debug access" /></a>
<%include file="footer.mako"/>
</%def>
