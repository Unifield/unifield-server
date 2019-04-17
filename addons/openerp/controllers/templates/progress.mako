<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Information")}</title>
    <link href="/openerp/static/css/style.css" rel="stylesheet" type="text/css"/>
    <script type="text/javascript">
    jQuery(document).ready(function () {
        setInterval(function () {
            var req = openobject.http.postJSON('/openerp/progressbar/get', {'model': "${model}", 'id': "${id}"});
            req.addCallback(function(obj) {
                if (obj.error) {
                    jQuery.fancybox(obj.error, {scrolling: 'no'});
                }
                else {
                    $('#indicator').width((obj.progress*250)/100+'px');
                    $('#percentage').html(obj.progress+'%');
                }
                });

        }, 1500);
    });
    </script>

    <style>
        #progressbar {
            width: 250px;
            padding:1px;
            background-color:white;
            border:1px solid black;
            height:28px;
            line-height: 28px;
            vertical-align: middle;
            text-align: center;
            font-weight: bold;
            font-size: 120%;
            }

        #pwidget {
            background-color:lightgray;
            width:254px;
            margin-top: 20px;
            margin-left: auto;
            margin-right: auto;
            padding:2px;
            -moz-border-radius:3px;
            border-radius:3px;
            text-align:center;
            border:1px solid gray;
        }

        #indicator {
            width: 0px;
            background-image: linear-gradient(white, green);
            height: 28px;
            margin: 0;
        }

        #percentage {
            position: absolute;
        }
    </style>
</%def>

<%def name="content()">
    <table class="view" cellspacing="5" border="0" height="200px" width="400px">
        <tr>
            <td>
                <h1>${_("Information")}</h1>
            </td>
        </tr>
        <tr><td>
                <div id="pwidget">
                    <div id="progressbar">
                    <span id="percentage">10</span>
                    <div id="indicator" style="width: 25px"></div>
                    </div>
                </div>
    </td></tr>
    </table>
</%def>
