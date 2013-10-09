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
  <ProtectStructure>True</ProtectStructure>
  <ProtectWindows>True</ProtectWindows>
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
     <NumberFormat ss:Format="Standard"/>
   </Style>
</Styles>
<Worksheet ss:Name="${_('Analytic Chart of Account')}">
<Table >
  <Column ss:Width="37.3039"/>
  <Column ss:Width="293.5559"/>
  <Column ss:Width="34.2142"/>
  <Column ss:Width="193.2094"/>
  <Column ss:Width="78.9449"/>
  <Column ss:Width="157.6913"/>
  <Column ss:Width="58.1102"/>
  <Column ss:Width="200.1543"/>
  <Row>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Code')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Name')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Category')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Parent')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Balance')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('For FX gain/loss')}</Data></Cell>
  </Row>
% for o in objects:
  <Row>
    <Cell>
      <Data ss:Type="String">${o.code or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.name or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.category and getSel(o, 'category') or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.parent_id and o.parent_id.code or ''|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="Number" ss:Style="number">${o.balance or '0.0'|x}</Data>
    </Cell>
    <Cell>
      <Data ss:Type="String">${o.for_fx_gain_loss and _('True') or _('False')|x}</Data>
    </Cell>
  </Row>
% endfor
</Table>
<WorksheetOptions/>
</Worksheet>
</Workbook>
