<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>
<%def name="header()">
    <title>Instance creation progression</title>

    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <script type="text/javascript">
        $(document).ready(function(){
            interval = setInterval(function()
            {
                $.ajax({
                    type: 'get',
                    dataType: "json",
                    url: 'get_auto_create_progress',
                    success: function (data) {
                        $("div.auto_creation_resume textarea").val(data.resume);
                        $("div.progressbar").text((data.progress*100).toPrecision(3)+'%');
                        $("div.progressbar").css({"width":(data.progress*100).toPrecision(3)+'%'});
                        $("div.my_state").text(data.state);
                        if (data.state === 'done') {
                            clearInterval(interval);
                        }
                    },
                    error: function (xhr, status, error) {
                    }
                });
            }, 3000)
        });
    </script>

    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css"/>

</%def>

<%def name="content()">
	<table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>



    <div class="db-form">
        <h1>Automated instance creation in progress...</h1>

        <div class="my_state">state</div>

        <div class="instance_creation_progress">
          <div class="progressbar" style="width:${'%d'%(percent*100)}%">${'%d'%(percent*100)}%</div>
        </div>

        <div class="auto_creation_resume">
            <textarea rows="10" cols="80">${resume}</textarea>
        </div>
    </div>
<%include file="footer.mako"/>
</%def>
