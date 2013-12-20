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
<ss:Worksheet ss:Name="Expiry report">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="250" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
## products/batches already expired
<Row>
<Cell ss:StyleID="header"><Data ss:Type="String">CODE</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">DESCRIPTION</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Location</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Stock</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">UoM</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Batch</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Expirity Date</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Exp. Qty</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Unit Cost</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Exp. Value</Data></Cell>
</Row>
## lines
##% for line in o.line_ids:
##<Row>
##<Cell ss:StyleID="line"><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##<Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
##</Row>
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
##    <Header x:Data="&amp;l&amp;&quot;Arial,Bold&quot;&amp;12${getAddress()}"/>
##    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14EXPIRY REPORT"/>
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
