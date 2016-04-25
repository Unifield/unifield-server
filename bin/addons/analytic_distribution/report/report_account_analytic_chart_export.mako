<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>${time.strftime('%Y-%m-%dT%H:%M:%SZ')|n}</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
   <Style ss:ID="header">
     <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
     <Borders>
       <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
       <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
       <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
       <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
     </Borders>
     <Font ss:Bold="1" ss:Size="11"/>
     <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
   </Style>
   <Style ss:ID="number">
     <NumberFormat ss:Format="#,##0.00"/>
   </Style>
  <Style ss:ID="header_part">
    <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
    </Borders>
  </Style>
  <Style ss:ID="header_part_center">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
    </Borders>
  </Style>
  <Style ss:ID="short_date2">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <NumberFormat ss:Format="Short Date"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
    </Borders>
  </Style>
</Styles>
<Worksheet ss:Name="${_('Info')}">
<Table >
  <Column ss:Width="37.3039"/>
  <Column ss:Width="293.5559"/>
  <Column ss:Width="34.2142"/>
  <Column ss:Width="193.2094"/>
  <Column ss:Width="78.9449"/>
  <Column ss:Width="157.6913"/>
  <Column ss:Width="58.1102"/>
  <Column ss:Width="200.1543"/>
  <Row ss:Height="12.8126">
    <Cell ss:Index="2"/>
  </Row>
  <Row ss:Height="12.1039">
    <Cell ss:StyleID="header_part">
      <Data ss:Type="String">Report Date:</Data>
    </Cell>
    <Cell ss:StyleID="short_date2" >
      <Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data>
    </Cell>
  </Row>
<!-- Desactivate output currency functionnality until further notice
  <Row ss:Height="12.6425">
    <Cell ss:StyleID="header_part">
      <Data ss:Type="String">Currency</Data>
    </Cell>
    <Cell ss:StyleID="header_part_center">
      <Data ss:Type="String">${( data.get('currency', False) and data.get('currency') or _('No one specified'))|x}</Data>
    </Cell>
  </Row>
-->
<%
header_fields = [
    (_('Fiscalyear'), 'fy'),
    (_('From'), 'from_period_header'),
    (_('To'), 'to_period_header'),
    (_('Instances'), 'instance_header'),
    (_('Show inactive accounts?'), 'show_inactive', 'boolean'),
    (_('Filtering on currency'), 'currency_filtering'),
]
%>
% for t in header_fields:
<%
 header_val = data.get('wiz_fields').get(t[1], '')
 if len(t) >= 3:
    if t[2] == 'boolean':
        header_val = _(header_val and 'Yes' or 'No')
    elif t[2] == 'selection':
        if len(t) >= 4:
            header_val = t[3] and t[3].get(header_val, '') or header_val
%>
  <Row ss:Height="12.6425">
    <Cell ss:StyleID="header_part">
      <Data ss:Type="String">${ t[0] or ''|x }</Data>
    </Cell>
    <Cell ss:StyleID="header_part_center">
      <Data ss:Type="String">${( data.get('wiz_fields', False) and data.get('wiz_fields').get(t[1], False) and data.get('wiz_fields').get(t[1]) or '')|x}</Data>
    </Cell>
  </Row>
% endfor
</Table>
<WorksheetOptions/>
</Worksheet>
% for cat in [(_('Cost Center'), 'OC'), (_('Destination'), 'DEST'), (_('Funding Pool'), 'FUNDING'), (_('Free 1'), 'FREE1'), (_('Free 2'), 'FREE2')]:
<Worksheet ss:Name="${cat[0]}">
<Table >
  <Column ss:Width="37.3039"/>
  <Column ss:Width="293.5559"/>
  <Column ss:Width="34.2142"/>
  <Column ss:Width="193.2094"/>
  <Column ss:Width="78.9449"/>
  <Column ss:Width="157.6913"/>
  <Column ss:Width="58.1102"/>
  <Column ss:Width="200.1543"/>
  <Row ss:Height="12.8126">
    <Cell ss:Index="2"/>
  </Row>
  <Row>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Name')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Code')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Type')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Balance')}</Data></Cell>
  </Row>
<% total = 0.0 %>
% for o in localSort(objects, cat[1]):
<%
  if not o.parent_id:
    total += o.balance or 0.0
%>
  <Row>
    <Cell>
      <Data ss:Type="String">${o.name or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.code or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.type and getSel(o, 'type') or ''|x}</Data>
    </Cell>
    <Cell ss:StyleID="number">
      <Data ss:Type="Number">${o.balance or 0.0|x}</Data>
    </Cell>
  </Row>
% endfor
  <Row>
    <Cell ss:Index="3">
      <Data ss:Type="String">${_('Total')}</Data>
    </Cell>
    <Cell ss:StyleID="number">
      <Data ss:Type="Number">${total or 0.0|x}</Data>
    </Cell>
  </Row>
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
  <FitToPage/>
  <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <Scale>83</Scale>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
  </Print>
  <Selected/>
</WorksheetOptions>
</Worksheet>
% endfor
</Workbook>
