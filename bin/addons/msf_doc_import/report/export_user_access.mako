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
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
            <Font ss:Bold="1" ss:Color="#000000" />
            <Protection />
        </Style>
        <Style ss:ID="header_no_style">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Protection />
        </Style>
        <Style ss:ID="header_supply">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#99cc00" ss:Pattern="Solid"/>
            <Protection />
        </Style>
        <Style ss:ID="header_finance">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#00ffff" ss:Pattern="Solid"/>
            <Protection />
        </Style>
        <Style ss:ID="header_synchro">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#cc99ff" ss:Pattern="Solid"/>
            <Protection />
        </Style>
        <Style ss:ID="main_menu_entry">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#ffcc00" ss:Pattern="Solid"/>
            <Protection />
        </Style>
        <Style ss:ID="sub_menu_entry">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#bfbfbf" ss:Pattern="Solid"/>
            <Protection />
        </Style>
    </Styles>

    <ss:Worksheet ss:Name="${data.get('model_name', _('Sheet 1'))|x}" ss:Protected="0">

        <Table x:FullColumns="1" x:FullRows="1">

            <% rows = getUserAccessRows(data['context']) %>
            <% headers = rows.pop(0) %>
            % for col in headers:
            <Column ss:AutoFitWidth="1" ss:Width="${col[1] or 70|x}" />
            % endfor

            <Row>
            % for col in headers:
            <Cell ss:StyleID="${col[2]|x}">
                    <Data ss:Type="String">${col[0]|x}</Data>
                </Cell>
            % endfor
            </Row>

            % for row in rows:
            % if not row[2]:
            <Row ss:StyleID="main_menu_entry">
            % elif row[2] == '+':
            <Row ss:StyleID="sub_menu_entry">
            % else:
            <Row>
            % endif
                % for index, cell in enumerate(row):
                <Cell>
                    <Data ss:Type="String">${cell is True and 'YES' or cell is False and 'NO' or cell|x}</Data>
                </Cell>
                % endfor
            </Row>
            % endfor
        </Table>

        <x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
            <ProtectScenarios>False</ProtectScenarios>
            <EnableSelection>UnlockedCells</EnableSelection>
            <AllowInsertRows />
        </x:WorksheetOptions>

    </ss:Worksheet>

</Workbook>
