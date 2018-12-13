<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>[${'%d'%(percent*100)}%] Report Generation</title>
    <script type="text/javascript">
        if ('${total}' != 'True' && '${finish}' == '') {
            setTimeout(function () {window.location.reload();}, 3000);
        }
    </script>
    <style>
        #downloadbg-form {
            margin-top: auto;
            margin-bottom: auto;
            height: 300px;
        }
        #down_title
        {
            font-weight: bold;
            font-size: 200%;
            text-align: center;
            margin-bottom: 20px;
        }
        #report_name
        {
            font-size: 120%;
            text-align: center;
        }
        #explanations
        {
            font-size: 90%;
            text-align: center;
            margin-top: 15px;
            margin-bottom: 15px;
        }
        #pwidget
        {
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
        #progressbar
        {
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
        #indicator
        {
            width: 0px;
            background-image: linear-gradient(white, green);
            height: 28px;
            margin: 0;
        }
        .percentage
        {
            position: absolute;
        }
    </style>
</%def>

<%def name="content()">
<div class="downloadbg-form">
    <div id="down_title">${_('Report generation in progress')}</div>
    <div id="pwidget">
        <div id="progressbar">
            <span class="percentage">${'%d'%(percent*100)}%</span>
            <div id="indicator" style="width: ${'%d'%(percent*250)}px"></div>
        </div>
    </div>
    %if data_collected == 'True' and total != 'True':
        <div id="explanations">${_('All the data have been collected. The report is now under rendering (this can take some time one big reports). A button to download it will be displayed soon...')}</div>
    %endif
    %if data_collected != 'True' and total != 'True':
        <div id="explanations">${_('A button to download the report will be displayed when finished.')}</div>
    %endif
    <div id="report_name">${_('Name of the requested report: ')}${report_name}
    %if total == 'True':
        <div>
            <input type="button" value="Download report"
            onclick="setTimeout(function(){window.close();}, 1000); window.open('/openerp/downloadbg?res_id=${res_id}&from_button=1', '_blank'); window.frameElement.close()" />
        </div>
    %endif
    </div>
</div>
</%def>
