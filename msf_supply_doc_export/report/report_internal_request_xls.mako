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
</Styles>
## we loop over the sale_order so "objects" == sale_order
% for o in objects:
<ss:Worksheet ss:Name="${(o.name or '')|x}">
<Table>
    <Column ss:AutoFitWidth="1" ss:Span="3" ss:Width="64.26"/>

## we loop over the sale_order_line
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Product Code</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Product Description</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Quantity</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">UoM</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Currency</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Comment</Data></Cell>
    </Row>
    % for line in o.order_line:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.product_uom_qty or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.functional_currency_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
    </Row>
    % endfor
% endfor
</Table>
<x:WorksheetOptions/></ss:Worksheet></Workbook>