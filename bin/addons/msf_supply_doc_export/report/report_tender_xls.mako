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
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
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
  </Style>
</Styles>
## ==================================== we loop over the purchase_order "objects" == tender  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.name.split('/')[-1] or 'Sheet1')|x}">

## definition of the columns' size
<% nb_of_columns = 6 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="320" />
<Column ss:AutoFitWidth="1" ss:Width="70" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="70" />

## we loop over the tender_line_ids
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Quantity')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit Price')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit Price (Comparison Currency)')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Requested Date')}</Data></Cell>
    </Row>
    % for line in o.tender_line_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.qty or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.price_unit or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.price_unit and computePrice(line.currency_id.id, line.tender_id.currency_id.id, line.price_unit) or '')|x}</Data></Cell>
        % if isDate(o.requested_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.requested_date|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/></ss:Worksheet>
% endfor
</Workbook>
