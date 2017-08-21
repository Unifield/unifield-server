<%
# put in try block to prevent improper redirection on connection refuse error
try:
    BANNER = cp.request.pool.get_controller("/openerp/banner")
    display_banner = BANNER.display_banner()
    banner_message = BANNER.get_message()
except:
    display_banner = False
    banner_message = ''
%>
% if display_banner:
<td id="communication_banner" colspan="3">${banner_message | h}</td>
% endif
