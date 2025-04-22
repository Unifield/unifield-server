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
        <Font ss:FontName="Calibri" x:Family="Swiss" ss:Bold="1" ss:Color="#000000"/>
        <Interior ss:Color="#efefef" ss:Pattern="Solid" />
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
  </Style>
  <Style ss:ID="line">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
      <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
      </Borders>
  </Style>
  <Style ss:ID="line_left">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
      <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
      </Borders>
  </Style>
  <Style ss:ID="line_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="Short Date"/>
  </Style>
</Styles>

<ss:Worksheet ss:Name="${_('BN/ED inconsistencies')|x}">
<Table x:FullColumns="1" x:FullRows="1">

    # Product code
    <Column ss:AutoFitWidth="1" ss:Width="75" />
    # Product Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # Batch Number Mandatory
    <Column ss:AutoFitWidth="1" ss:Width="60" />
    # Expiry Date Mandatory
    <Column ss:AutoFitWidth="1" ss:Width="60" />
    # BN
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # ED
    <Column ss:AutoFitWidth="1" ss:Width="75" />
    # Quantity
    <Column ss:AutoFitWidth="1" ss:Width="75" />
    # Location
    <Column ss:AutoFitWidth="1" ss:Width="120" />
    # Document number
    <Column ss:AutoFitWidth="1" ss:Width="120" />

    % for o in objects:
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Batch Number Mandatory')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Expiry Date Mandatory')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('BN')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('ED')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Quantity')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Location')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Document number')|x}</Data></Cell>
    </Row>

        % for l in o.line_ids:
        <Row ss:AutoFitHeight="1">
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.product_code or ''|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${l.product_id.name or ''|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.product_bn and 'TRUE' or '-'|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.product_ed and 'TRUE' or '-'|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.prodlot_name or '-'|x}</Data></Cell>
            % if isDate(l.expiry_date):
            <Cell ss:StyleID="line_date"><Data ss:Type="DateTime">${l.expiry_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="line"><Data ss:Type="String">-</Data></Cell>
            % endif
            <Cell ss:StyleID="line"><Data ss:Type="Number">${l.quantity|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.location_id.name or '-'|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${l.document_number or '-'|x}</Data></Cell>
        </Row>
        % endfor
    % endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>17</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</ss:Worksheet>

</Workbook>
