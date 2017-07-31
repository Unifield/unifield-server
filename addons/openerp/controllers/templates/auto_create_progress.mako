<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>
<%def name="header()">
    <title>Instance creation progression</title>

    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css"/>

</%def>

<%def name="content()">
	<table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>



    <div class="db-form">
        <h1>Automated instance creation in progress...</h1>

        <div class="instance_creation_progress">
          <div class="progressbar" style="width:${'%d'%(percent*100)}%">${'%d'%(percent*100)}%</div>
        </div>
    </div>
<%include file="footer.mako"/>
</%def>
