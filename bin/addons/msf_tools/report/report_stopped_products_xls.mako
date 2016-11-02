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
  <Style ss:ID="tab_header_orange">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_header_gray">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#dbdbdb" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_content">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
</Styles>


<ss:Worksheet ss:Name="Stopped products">

  <Table x:FullColumns="1" x:FullRows="1">

    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product code
    <Columns ss:AutoFitWidth="1" ss:Width="200" /> # product description
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product creator
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # standardization level
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unidata status

    ##### Table with all stopped products #####

    % for line in get_uf_stopped_products():
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Code</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Description</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Product Creator</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Standardization Level</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Unidata Status</Data></Cell>
        </Row>

        <% standard_level = 'Standard' if line.standard_ok == 'True' else 'Non-standard' %>
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(line.default_code)|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(line.name_template)|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(line.international_status and line.international_status.name or '')|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(standard_level)|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(line.state_ud and getSel(line, 'state_ud') or '')|x}</Data></Cell>
        </Row>

        <% smrl_list = get_stock_mission_report_lines(line.id) %>
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Instance/Mission</Data></Cell>
          <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Unifield Status</Data></Cell>
          <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Instance stock</Data></Cell>
          <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Pipeline Qty</Data></Cell>
        </Row>
        % for smrl in smrl_list:
            <Row ss:AutoFitHeight="1">
              <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(smrl.mission_report_id.name)|x}</Data></Cell>
              <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(get_uf_status(smrl.product_state))|x}</Data></Cell>
              <Cell ss:StyleID="tab_content"><Data ss:Type="Number">${(smrl.internal_qty)|x}</Data></Cell>
              <Cell ss:StyleID="tab_content"><Data ss:Type="Number">${(smrl.in_pipe_qty)|x}</Data></Cell>
            </Row>
        % endfor
            <Row></Row>
            <Row></Row>
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
