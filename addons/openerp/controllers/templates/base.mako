<%inherit file="/openobject/controllers/templates/base.mako"/>

<%def name="header()">
    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.base.js?v=8.1"></script>
    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.tips.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.textarea.js"></script>

    <script type="text/javascript" src="/openerp/static/javascript/scripts.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/form.js?v=9.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/form_state.js?v=7.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/listgrid.js?v=9.0"></script>

    <script type="text/javascript" src="/openerp/static/javascript/m2o.js?v=7.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/m2m.js?v=7.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/o2m.js?v=7.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/binary.js"></script>
    <script type="text/javascript" src="/openerp/static/jscal/calendar.js"></script>
    <script type="text/javascript" src="/openerp/static/jscal/calendar-setup.js"></script>

    <script type="text/javascript" src="/openerp/static/javascript/web_keyboard_shortcuts.js?v=7.0rc4b"></script>

    <link rel="stylesheet" type="text/css" href="/openerp/static/css/style.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/menu.css?v=2.7b1"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/tips.css?v=7.0"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/screen.css?v=9.0"/>

    <link rel="stylesheet" type="text/css" href="/openerp/static/jscal/calendar-blue.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/dashboard.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/treegrid.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/notebook.css"/>

    <link rel="stylesheet" type="text/css" href="/openerp/static/css/pager.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/listgrid.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/autocomplete.css"/>

    <!--[if lt IE 9]>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/style-ie.css"/>
    <![endif]-->
    ${self.header()}
</%def>

