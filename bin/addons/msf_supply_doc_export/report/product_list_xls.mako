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
    <Style ss:ID="redline">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Font ss:Color="#ff0000"/>
    </Style>
</Styles>
## ==================================== we loop over the product_list so "objects" == product_list  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.name.replace('/', '_') or 'Sheet1')|x}">
<Table >
    <Column ss:AutoFitWidth="1" ss:Span="5" ss:Width="64.26"/>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MML')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MSL')}</Data></Cell>
    </Row>
    ## we loop over the product_list_line
    % for line in o.product_ids:
    <Row>
        ## % if line['mml_status'] == 'F'
        ##    <Cell ss:StyleID="redline" ><Data ss:Type="String">${(line.name.default_code or '')|x}</Data></Cell>
        ##    <Cell ss:StyleID="redline" ><Data ss:Type="String">${(line.name.name or '')|x}</Data></Cell>
        ##    <Cell ss:StyleID="redline" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
        ##    <Cell ss:StyleID="redline" ><Data ss:Type="String">${(getSel(line, 'mml_status') or '')|x}</Data></Cell>
        ##    <Cell ss:StyleID="redline" ><Data ss:Type="String">${(getSel(line, 'msl_status') or '')|x}</Data></Cell>
        ## % else:
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name.default_code or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
            ## <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(line, 'mml_status') or '')|x}</Data></Cell>
            ## <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(line, 'msl_status') or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        ## % endif
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
