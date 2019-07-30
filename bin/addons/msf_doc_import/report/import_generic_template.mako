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
            <Font ss:Bold="1" ss:Color="#000000" />
            <Borders>
              <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <Protection />
        </Style>
        <Style ss:ID="String">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Borders>
              <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="Boolean">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Borders>
              <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="Float">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Borders>
              <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <NumberFormat ss:Format="Fixed" />
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="Number">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Borders>
              <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
              <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <NumberFormat ss:Format="Fixed" />
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="DateTime">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Borders>
                <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
                <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
                <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
                <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            </Borders>
            <NumberFormat ss:Format="Short Date" />
            <Protection ss:Protected="0" />
        </Style>
    </Styles>

    <ss:Worksheet ss:Name="${data.get('model_name', _('Sheet 1'))|x}" ss:Protected="0">

        <Table x:FullColumns="1" x:FullRows="1">

        % for col in data.get('header_columns', []):
            <Column ss:AutoFitWidth="1" ss:Width="${col[2] or 70|x}" ss:StyleID="${col[1]|x}" />
        % endfor

            <Row>
            % for col in data.get('header_columns', []):
                <Cell ss:StyleID="header">
                    <Data ss:Type="String">${col[0]}</Data>
                </Cell>
            % endfor
            </Row>

            <Row>
            % for col in data.get('header_columns', []):
                <Cell ss:StyleID="${col[1]|x}" />
            % endfor
            </Row>
        </Table>
        
        <x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
            <ProtectScenarios>False</ProtectScenarios>
            <EnableSelection>UnlockedCells</EnableSelection>
            <AllowInsertRows />
        </x:WorksheetOptions>

    </ss:Worksheet>

</Workbook>
