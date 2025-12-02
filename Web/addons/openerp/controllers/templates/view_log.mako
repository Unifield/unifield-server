<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Information")}</title>
    <link href="/openerp/static/css/style.css" rel="stylesheet" type="text/css"/>
</%def>

<%def name="content()">
    <table class="view" cellspacing="5" border="0" width="100%">
        <tr>
            <td>
                <h1>${_("Information")}
                % if rpc.session and rpc.session.uid == 1:
                        <a class="help" id="show_fields_button" title="${_('Show fields')}" href="${py.url('/openerp/showfields', model=model)}"></a>
                % endif
                </h1>
            </td>
        </tr>
        <tr>
            <td>
                <div class="box2">
                    <table border="0" width="100%" align="center">
                        % for field, description in fields:
                        <tr>
                            <td class="label" width="50%">${description}:</td>
                            <td width="50%">${values[field]}</td>
                        </tr>
                        % endfor
                    </table>
                </div>
            </td>
        </tr>
    </table>

    <script type="text/javascript">
        jQuery(document).ready(function() {
            jQuery('#show_fields_button').fancybox();
        });
    </script>
</%def>
