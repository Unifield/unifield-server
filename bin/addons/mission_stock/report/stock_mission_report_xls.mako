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
    <Style ss:ID="ssBorder">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
</Styles>
% for o in [objects]:
    <ss:Worksheet ss:Name="Mission stock report">
        <Table x:FullColumns="1" x:FullRows="1">

            <Row>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Reference')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Name')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Active')}</Data></Cell>
         if o.local_report:
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('MML')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('MSL')}</Data></Cell>
         % endif
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('UoM')}</Data></Cell>
         % if o.with_valuation:
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Cost Price')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Func. Cur.')}</Data></Cell>
         % endif
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Instance stock')}</Data></Cell>
         % if o.with_valuation:
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Instance stock val.')}</Data></Cell>
         % endif
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Stock Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Cross-Docking Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Secondary Stock Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Internal Cons. Unit Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Quarantine / For Scrap Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Input Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('Output/Packing/Dispatch/Distribution Qty.')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('AMC')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('FMC')}</Data></Cell>
                <Cell ss:StyleID="header"><Data ss:Type="String">${_('In Pipe Qty')}</Data></Cell>
            </Row>

         % if o.with_valuation:
            % if o.local_report:
                ${o.report_id.s_v_mml_vals}
            % else:
                ${o.report_id.s_v_vals}
            % endif
         % else:
            % if o.local_report:
                ${o.report_id.s_nv_mml_vals}
            % else:
                ${o.report_id.s_nv_vals}
            % endif
         % endif
    </Table>

    <x:WorksheetOptions/>
    </ss:Worksheet>
% endfor
</Workbook>
