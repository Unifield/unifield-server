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
## ==================================== we loop over the monthly_review_consumption so "objects" == monthly_review_consumption  ====================================================
<% val = 0 %>
% for o in objects:
<% val += 1 %>
## the val enables to have several reports with the same name (in tab) except for the val
<ss:Worksheet ss:Name="${"%s- %s"%(val, o.cons_location_id)|x}">

## definition of the columns' size
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('DB/Instance name')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.company_id.name or '')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Generated on')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${o.creation_date|n}T00:00:00.000</Data></Cell>
    </Row>

    <Row>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('AMC')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('FMC')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Safety Stock (qty)')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Valid Until')}</Data></Cell>
    </Row>
    ## we loop over the products line
    % for line in o.line_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name.uom_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" >
            % if line.amc and line.amc:
                <Data ss:Type="Number">${(line.amc or '')|x}</Data>
            % else:
                <Data ss:Type="String"></Data>
            % endif
        </Cell>
        <Cell ss:StyleID="line" >
            % if line.fmc and line.fmc:
                <Data ss:Type="Number">${(line.fmc or '')|x}</Data>
            % else:
                <Data ss:Type="String"></Data>
            % endif
        </Cell>
        <Cell ss:StyleID="line" >
            % if line.security_stock and line.security_stock:
                <Data ss:Type="Number">${(line.security_stock or '')|x}</Data>
            % else:
                <Data ss:Type="String"></Data>
            % endif
        </Cell>
        <Cell ss:StyleID="short_date" >
            % if line.valid_until and line.valid_until != 'False':
                <Data ss:Type="DateTime">${line.valid_until|n}T00:00:00.000</Data>
            % else:
                <Data ss:Type="String"></Data>
            % endif
        </Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
