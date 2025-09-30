<%
# put in try block to prevent improper redirection on connection refuse error
try:
    #SHORTCUT = cp.request.pool.get_controller("/openerp/shortcut_tooltip")
    #display_message = SHORTCUT.get_show_shortcut()
    display_message = False
    message = _("You haven't recently used a keyboard shortcut. You can see what shortcuts are available on this screen by holding SHIFT + CTRL.")
except:
    display_message = False
    message = 'toto'
%>
% if display_message:
<td id="shortcut_message" colspan="3">${message | h}</td>
% endif
