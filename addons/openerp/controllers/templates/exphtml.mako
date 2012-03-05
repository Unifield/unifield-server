<html>
<head>
<title>Export Data</title>
</head>
<body>
<table border="1">
<tr>
% for header in fields:
  <th>${header}</th>
% endfor
</tr>
% for row in result:
<tr>
  % for d in row:
  <td>${d or ''}</td>
  % endfor
</tr>
% endfor
</table>
</body>
</html>
