<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css?v=7.0"/>
    <style type="text/css">
        .form-container {
            margin: 0 auto;
        }
    </style>
    % if changed:
        <script type="text/javascript">
            window.open("/openerp/logout", '_top');
        </script>
    % endif
</%def>

<%def name="content()">
    % if errors:
        <div class="login_error_message">
            % for error in errors:
                ${error}<br>
            % endfor
        </div>
    % endif
    ${form.display()}
</%def>
