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
  <Created>2012-06-18T15:46:09Z</Created>
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
<Style ss:ID="Default" ss:Name="Normal">
<Alignment ss:Vertical="Bottom"/>
<Borders/>
<Font/>
<Interior/>
<NumberFormat/>
<Protection/>
</Style>


<Style ss:ID="s22">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
</Style>

<Style ss:ID="s22nobold">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
</Style>

<Style ss:ID="s22bold">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<Font ss:Bold="1"/>
</Style>

<Style ss:ID="s23">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<NumberFormat ss:Format="#,##0"/>
</Style>

<Style ss:ID="s23nobold">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<NumberFormat ss:Format="#,##0"/>
</Style>

<Style ss:ID="s23bold">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<NumberFormat ss:Format="#,##0"/>
<Font ss:Bold="1"/>
</Style>

<Style ss:ID="s24">
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<Font x:Family="Swiss" ss:Bold="1"/>

</Style>
<Style ss:ID="s28">
<Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<Font x:Family="Swiss" ss:Bold="1"/>
</Style>
<Style ss:ID="s29">
<Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
<Borders>
<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
</Borders>
<Interior ss:Color="#FFFF00" ss:Pattern="Solid"/>
</Style>
</Styles>

% for o in objects:
<ss:Worksheet ss:Name="${sheet_name(o.name and o.name.split('/')[-1])|x}">

<Table x:FullColumns="1" x:FullRows="1">
<Column ss:Width="160.75"/>
<Column ss:AutoFitWidth="0" ss:Width="273"/>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Budget name:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.name or '' )|x}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Budget code:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.code or '' )|x}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Fiscal year:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.fiscalyear_id and o.fiscalyear_id.name or '' )|x}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Cost center:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.cost_center_id and o.cost_center_id.name or '' )|x}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Decision moment:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.decision_moment_id and o.decision_moment_id.name or '' )|x}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="s22">
<Data ss:Type="String">${_('Version:')}</Data>
</Cell>
<Cell ss:StyleID="s22" ><Data ss:Type="String">${( o.version or '' )|x}</Data></Cell>
</Row>

<Row ss:Index="8">
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Account code - Destination code')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Account description')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Jan')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Feb')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Mar')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Apr')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('May')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Jun')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Jul')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Aug')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Sep')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Oct')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Nov')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Dec')}</Data></Cell>
<Cell ss:StyleID="s24"><Data ss:Type="String">${_('Total')}</Data></Cell>
</Row>

<% view_codes = fetchViewCodes() %>
% for line in process(o.budget_line_ids):
<% 
  isBold = False
  if line[0] in view_codes:
    isBold = True
%>
<Row>
<Cell ss:StyleID="${"%s"%( isBold and 's22bold' or 's22nobold')|x}" ><Data ss:Type="String">${( line[0] )|x}</Data></Cell>

<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="String">${( line[1] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[2] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[3] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[4] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[5] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[6] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[7] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[8] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[9] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[10] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[11] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[12] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[13] )|x}</Data></Cell>
<Cell ss:StyleID="${"%s"%( isBold and 's23bold' or 's23nobold')|x}" ><Data ss:Type="Number">${( line[14] )|x}</Data></Cell>
</Row>
% endfor

</Table>
<x:WorksheetOptions/></ss:Worksheet>
% endfor
</Workbook>
