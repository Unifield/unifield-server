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
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection />
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection ss:Protected="0" />
    </Style>
  <Style ss:ID="short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
   <Protection ss:Protected="0" />
  </Style>
</Styles>
## ==================================== we loop over the log lines "objects" == audittrail_log_lines  ====================================================
<ss:Worksheet ss:Name="${"%s"%(order_name(objects[0].id)[:31] or 'Sheet1')|x}" ss:Protected="1">
## definition of the columns' size
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="30" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="100" />
<Column ss:AutoFitWidth="1" ss:Width="200" />
<Column ss:AutoFitWidth="1" ss:Width="200" />
<Column ss:AutoFitWidth="1" ss:Width="200" />
<Column ss:AutoFitWidth="1" ss:Width="100" />

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Log ID')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Line')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Method')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Field description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Old value')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('New value')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('User')}</Data></Cell>
    </Row>

    % for line in get_lines(order_id(objects[0].id)):
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.log or '')|x}</Data></Cell>
        % if isDateTime(line.timestamp):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.timestamp[:10]|n}T${line.timestamp[11:]}.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.sub_obj_name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(get_method(line, 'method') or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.trans_field_description or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.old_value_fct or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.new_value_fct or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.user_id.name or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <ProtectObjects>True</ProtectObjects>
    <ProtectScenarios>True</ProtectScenarios>
    <EnableSelection>UnlockedCells</EnableSelection>
    <AllowInsertRows />
</x:WorksheetOptions>
</ss:Worksheet>
</Workbook>
