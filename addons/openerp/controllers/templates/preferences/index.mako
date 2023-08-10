<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <script type="text/javascript">
        document.title = '${params.string}' + ' - OpenERP';
        var form_controller = '/openerp/pref';
        function open_password() {
            jQuery.frame_dialog({
                'src': '/openerp/pref/password'
            }, null, {
                'width': 600,
                'height': 400
            });
        }

        function validate_email() {
            var ok = true;
            jQuery("span[class=fielderror]").remove();
            jQuery('#view_form').find('input[kind=email]').each(function () {
                var val = jQuery(this).val();

                if (val && !val.includes('@')) {
                    jQuery("<span class='fielderror'>${_('An email address must contain a single @')}</span>").insertAfter(jQuery(this));
                    ok = false;
                }
            });
            if (ok) {
                submit_form('ok');
            }
        }
    </script>
    % if saved:
        <script type="text/javascript">
            window.frameElement.close();
        </script>
    % endif
</%def>

<%def name="content()">
    <div class="view">
        <form name="view_form" id="view_form" action="/openerp/pref/ok" method="post" target="_self">
            <table align="center" style="border: none;" width="100%">
                <tr>
                    <td class="error_message_header">${params.string}</td>
                </tr>
                <tr>
                    <td style="padding: 0;">${form.display()}</td>
                </tr>
                <tr>
                <td style="text-align: right; padding: 0 15px 5px 0;">
                    <button type='button' class="static_boxes"
                            onclick="open_password(); return false;"
                            >${_("Change Password")}</button>
                    <button type='button' class="static_boxes oe_form_button_cancel" onclick="window.frameElement.close();">${_("Cancel")}</button>
                    <button type='button' class="static_boxes" onclick="validate_email();">${_("Save")}</button>
                </td>
            </tr>
            </table>
        </form>
    </div>

</%def>
