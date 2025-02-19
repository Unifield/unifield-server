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

<ss:Worksheet ss:Name="${_('Products')|x}">

  <Table x:FullColumns="1" x:FullRows="1">

    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # instance
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # code
    <Columns ss:AutoFitWidth="1" ss:Width="200" /> # product description
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product creator
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unifield status
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unidata status
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # standardization level
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # active

    ##### Table with all stopped products #####

    % if not get_inconsistent_lines():
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_content"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${_('There is no inconsistencies to report')|x}</Data></Cell>
        </Row>
    % else:
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Instance')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Product Creator')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('UniField Status')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Unidata Status')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Standardization Level')|x}</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Active/Inactive')|x}</Data></Cell>
        </Row>
        % for prod in get_products_with_inconsistencies():
                # Instance data:
                <Row ss:AutoFitHeight="1">
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['instance_name']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_default_code']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_name_template']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_international_status'] or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_state'] or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_state_ud']  or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${prod['prod_standard_ok']  or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${_('Active') if prod['prod_active'] else _('Inactive')|x}</Data></Cell>
                </Row>
            % for smrl in prod['smrl_list']:
                <Row ss:AutoFitHeight="1">
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['instance_name']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['smrl_default_code']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['smrl_name_template']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['internationnal_status_code_name'] or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['uf_status_code']|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['ud_status_code'] or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${smrl['standard_ok'] or ''|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${_('Active') if smrl['active'] else _('Inactive')|x}</Data></Cell>
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
