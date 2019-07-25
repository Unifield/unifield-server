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
        <Interior ss:Color="#ff0000" ss:Pattern="Solid" />
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line_number">
        <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="header_short_date">
     <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
     <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
     </Borders>
     <NumberFormat ss:Format="General Date"/>
    </Style>
    <Style ss:ID="short_date">
     <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
     <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
     </Borders>
     <NumberFormat ss:Format="General Date"/>
    </Style>
</Styles>
% for o in objects:
    <ss:Worksheet ss:Name="${_('Periodical forecast report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">

        <Row>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('DB/instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${o.requestor_id and o.requestor_id.company_id and o.requestor_id.company_id.instance_id and o.requestor_id.company_id.instance_id.name or ''|x}</Data></Cell>
        </Row>

        <Row>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('From date')|x}</Data></Cell>
            <Cell ss:StyleID="header_short_date"><Data ss:Type="DateTime">${o.requestor_date[:10]|n}T${o.requestor_date[11:]|n}.000</Data></Cell>
        </Row>

        <Row>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('Number of')|x} ${o.interval_type == 'week' and _('weeks') or _('months')|n} ${_('from now')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="Number">${o.interval|x}</Data></Cell>
        </Row>

        <Row>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('Consumption calculation method')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${o.consumption_type == 'fmc' and _('FMC') or o.consumption_type == 'amc' and _('AMC') or _('RAC')|x}</Data></Cell>
        </Row>

        ${o.xml_data}

    </Table>

    <x:WorksheetOptions/>
    </ss:Worksheet>
% endfor
</Workbook>
