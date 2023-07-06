<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Utilisateur Windows</Author>
  <LastAuthor>Utilisateur Windows</LastAuthor>
  <Created>2020-01-16T16:43:56Z</Created>
  <Version>16.00</Version>
 </DocumentProperties>
 <OfficeDocumentSettings xmlns="urn:schemas-microsoft-com:office:office">
  <AllowPNG/>
 </OfficeDocumentSettings>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>10590</WindowHeight>
  <WindowWidth>28800</WindowWidth>
  <WindowTopX>0</WindowTopX>
  <WindowTopY>0</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Bottom"/>
   <Borders/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <Style ss:ID="s63">
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Interior ss:Color="#FFC000" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="s69">
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
  </Style>
  <Style ss:ID="s70">
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <Interior/>
  </Style>
  <Style ss:ID="s74">
   <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
   <Borders/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
  </Style>
  <Style ss:ID="s82">
   <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
  </Style>
  <Style ss:ID="s84">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Interior ss:Color="#FFC000" ss:Pattern="Solid"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="RR Prod list">
  <Table x:FullColumns="1"
   x:FullRows="1" ss:DefaultColumnWidth="60" ss:DefaultRowHeight="15">
   <Column ss:AutoFitWidth="0" ss:Width="132.75"/>
   <Column ss:AutoFitWidth="0" ss:Width="236.25"/>
   <Column ss:AutoFitWidth="0" ss:Width="228"/>
   <Column ss:AutoFitWidth="0" ss:Width="272.25"/>
   <Column ss:AutoFitWidth="0" ss:Width="40.0"/>
   <Column ss:AutoFitWidth="0" ss:Width="40.0"/>
   <% list = get_list() %>
   <Row>
    <Cell ss:MergeAcross="3" ss:StyleID="s74"><Data ss:Type="String">${_('Product List Consistency Report')|x}</Data></Cell>
   </Row>
   <Row>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
   </Row>
   <Row>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
    <Cell ss:StyleID="s74"/>
   </Row>
   <Row>
    <Cell ss:StyleID="s63"><Data ss:Type="String">${_('Product list Ref')|x}</Data></Cell>
    <Cell ss:StyleID="s82"><Data ss:Type="String">${(list.ref or '')|x}</Data></Cell>
   </Row>
   <Row>
    <Cell ss:StyleID="s63"><Data ss:Type="String">${_('Prod list name')|x}</Data></Cell>
    <Cell ss:StyleID="s82"><Data ss:Type="String">${(list.name or '')|x}</Data></Cell>
   </Row>
   <Row ss:Index="7">
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('Product code')|x}</Data></Cell>
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('Product Description')|x}</Data></Cell>
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('Segment Ref')|x}</Data></Cell>
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('Segment name')|x}</Data></Cell>
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('MML')|x}</Data></Cell>
    <Cell ss:StyleID="s84"><Data ss:Type="String">${_('MSL')|x}</Data></Cell>
   </Row>
   % for line in get_prod(list.id):
   <Row>
    <Cell ss:StyleID="s69"><Data ss:Type="String">${line.default_code|x}</Data></Cell>
    <Cell ss:StyleID="s69"><Data ss:Type="String">${line.product_id.name|x}</Data></Cell>
    <Cell ss:StyleID="s69"><Data ss:Type="String">${(line.name_seg or '')|x}</Data></Cell>
    <Cell ss:StyleID="s70"><Data ss:Type="String">${(line.description_seg or '')|x}</Data></Cell>
    ## <Cell ss:StyleID="s70"><Data ss:Type="String">${(getSel(line, 'mml_status'))|x}</Data></Cell>
    ## <Cell ss:StyleID="s70"><Data ss:Type="String">${(getSel(line, 'msl_status'))|x}</Data></Cell>
    <Cell ss:StyleID="s70"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="s70"><Data ss:Type="String"></Data></Cell>
   </Row>
   % endfor
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Header x:Margin="0.3"/>
    <Footer x:Margin="0.3"/>
    <PageMargins x:Bottom="0.75" x:Left="0.7" x:Right="0.7" x:Top="0.75"/>
   </PageSetup>
   <Selected/>
   <FreezePanes/>
   <FrozenNoSplit/>
   <SplitHorizontal>7</SplitHorizontal>
   <TopRowBottomPane>7</TopRowBottomPane>
   <ActivePane>2</ActivePane>
   <Panes>
    <Pane>
     <Number>3</Number>
    </Pane>
    <Pane>
     <Number>2</Number>
     <ActiveRow>3</ActiveRow>
     <ActiveCol>1</ActiveCol>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
  </WorksheetOptions>
 </Worksheet>
</Workbook>
