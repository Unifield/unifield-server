<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>Report Generation</title>
    <script type="text/javascript">
        if ('${total}' === 'True') {
            setTimeout(function () {window.location.reload();}, 100);
        }
        else if ('${finish}' == '') {
            setTimeout(function () {window.location.reload();}, 3000);
        }
    </script>
</%def>

<%def name="content()">
<h1>${_('Report generation in progress')}: ${'%d'%(percent*100)}% <img src="/openerp/static/images/load.gif" width="16" height="16" title="loading..."/></h1>
</%def>
