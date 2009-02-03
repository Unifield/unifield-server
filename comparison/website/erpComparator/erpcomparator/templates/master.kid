<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python import sitetemplate ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#" py:extends="sitetemplate">

<head py:match="item.tag=='{http://www.w3.org/1999/xhtml}head'" py:attrs="item.items()">
	<meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <meta py:replace="item[:]"/>
    
    <script type="text/javascript" src="/static/javascript/MochiKit/MochiKit.js"></script>
    <script type="text/javascript" src="/static/javascript/master.js"></script>
    <script type="text/javascript" src="/static/javascript/treegrid.js"></script>
    <script type="text/javascript" src="/static/javascript/ajax.js"></script>
    <script type="text/javascript" src="/static/javascript/comparison.js"></script>
    <script type="text/javascript" src="/static/javascript/modalbox.js"></script>
    <script type="text/javascript" src="/static/javascript/swfobject.js"></script>
    
    <link href="/static/css/tabs.css" rel="stylesheet" type="text/css"/>
    <link href="/static/css/treegrid.css" rel="stylesheet" type="text/css"/>
    <link href="/static/css/new_style.css" rel="stylesheet" type="text/css"/>
    <link href="/static/css/modalbox.css" rel="stylesheet" type="text/css"/>

    <!--[if lt IE 7]>
        <link href="/static/css/iepngfix.css" rel="stylesheet" type="text/css"/>
    <![endif]-->

    <!--[if lt IE 7]>
    <style type="text/css">
        ul.tabbernav {
        padding: 0px;
    }

    ul.tabbernav li {
        left: 10px;
        top: 1px;
    }
    </style>
    <![endif]-->

    <!--[if IE]>
        <link href="/static/css/style-ie.css" rel="stylesheet" type="text/css"/>
    <![endif]-->
        
    <title py:replace="''">Your title goes here</title>
    
</head>

<body margin="0" py:match="item.tag=='{http://www.w3.org/1999/xhtml}body'" py:attrs="item.items()">

<?python
# put in try block to prevent improper redirection on connection refuse error
try:
    criterions, feedbacks, user_info = tg.root.comparison.check_data()
except:
	criterions = None
	feedbacks = None
	user_info = None
?>

	<table id="container" border="0" cellpadding="0" cellspacing="0">
    	<tr py:if="value_of('show_header_footer', True)">
        	<td>
				<div id="site">
					<div id="header"></div>
					
					<div id="header_bar"> 
						<div style="padding: 12px 20px; width: 35%; float: left;">
							Based on<font color="#FF3300"><b> ${criterions} </b></font>
							criterions,<font color="#FF3300"><b> ${feedbacks} </b></font>
							users' feedback
						</div>
						
						<div id="loginbg" py:if="not user_info"> 
					    	<div style="padding-top:5px;padding-left:10px;">
					    			Login : <input type="text" name="user_name" id="user_name" class="textInput"/> 
					    			Password : <input type="password" name="password" id="password" class="textInput"/>
					      		<button type="button" class="button" onclick="do_login()" name="continue">Continue</button>
					    	</div>
						</div>
						<div  id="loginbg" py:if="user_info">
							<div style="padding-top: 10px; padding-right: 20px; font-size: 12px; font-weight: bold; text-align: right;">
								Welcome ${user_info}
							</div>
						</div>
					</div>
					
					<div py:replace="[item.text]+item[:]"></div>
					
					<div align="center" id="bodybackground"><br/>
						(c) 2008-TODAY - Copyright Evaluation-Matrix.com -
						<font color="#990000">
							<a href="mailto:info@evaluation-matrix.com" class ="a">
								Contact us
							</a>
						</font> for more information.
					</div>
					<div>
						<img src="/static/images/footerbg.gif"/>
					</div>
					<div>
						<img src="/static/images/bottom_shadow2.png"/>
					</div>
				</div>
			</td>
		</tr>
	</table>
</body>
</html>
