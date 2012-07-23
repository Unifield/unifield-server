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
    <Style ss:ID="so_header_data">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
</Styles>
<ss:Worksheet ss:Name="Tender">
<Table>
    <Column ss:AutoFitWidth="1" ss:Span="3" ss:Width="64.26"/>
## we loop over the tender so "objects" == tender
% for o in objects:


## we loop over the tender_line_ids

    
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">Product Code</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">Product Description</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">Quantity</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">UoM</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">Price</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">Delivery requested date</Data></Cell>
    </Row>
    % for line in o.tender_line_ids:
    <Row>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="String">${(line.product_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="Number">${(line.qty or '')|x}</Data></Cell>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="Number">${(line.price_unit or '')|x}</Data></Cell>
        <Cell ss:StyleID="so_header_data" ><Data ss:Type="Date">${(o.requested_date or '')|x}</Data></Cell>
    </Row>
    % endfor
% endfor
</Table>
<x:WorksheetOptions/></ss:Worksheet></Workbook>