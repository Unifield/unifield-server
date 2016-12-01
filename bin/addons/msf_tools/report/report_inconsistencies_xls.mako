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

    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # instance
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # code
    <Columns ss:AutoFitWidth="1" ss:Width="200" /> # product description
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product creator
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unifield status
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unidata status
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # active

    ##### Table with all stopped products #####

    % if not get_inconsistent_lines():
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_content"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">There is no inconsistencies to report</Data></Cell>
        </Row>
    % else:
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Instance</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Code</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Description</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Product Creator</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">UniField Status</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Unidata Status</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Active/Inactive</Data></Cell>
        </Row>
        % for prod in get_products_with_inconsistencies():
            # HQ data:
            <Row ss:AutoFitHeight="1">
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${('HQ')|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${(prod.default_code)|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${(prod.name_template)|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${(prod.international_status and prod.international_status.name or '')|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${(prod.state and prod.state.name or '')|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${(prod.state_ud and getSel(prod, 'state_ud') or '')|x}</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${('Active' if prod.active else 'Inactive')|x}</Data></Cell>
            </Row>
            % for smrl in get_inconsistent_lines(prod.id):
                <Row ss:AutoFitHeight="1">
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(smrl.mission_report_id.instance_id.name)|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(smrl.default_code)|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(smrl.product_id.name_template)|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(get_product_creator_name_from_code(smrl.international_status_code) or '')|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(get_uf_status(smrl.product_state))|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(get_ud_status(smrl.state_ud) or '')|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${('Active' if smrl.product_active else 'Inactive')|x}</Data></Cell>
                </Row>
            % endfor
        % endfor
    % endif


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
