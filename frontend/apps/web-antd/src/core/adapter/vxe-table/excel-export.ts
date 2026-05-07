import writeXlsxFile from 'write-excel-file/browser';

type ExcelCellValue = boolean | Date | number | string;

function toExcelCellValue(value: unknown): ExcelCellValue {
  if (value === null || value === undefined) {
    return '';
  }
  if (
    typeof value === 'boolean' ||
    typeof value === 'number' ||
    typeof value === 'string' ||
    value instanceof Date
  ) {
    return value;
  }
  return JSON.stringify(value);
}

export async function writeRecordsToExcel({
  filename,
  headers,
  rows,
  sheetName,
}: {
  filename: string;
  headers: string[];
  rows: unknown[][];
  sheetName: string;
}) {
  const sheetData = [headers, ...rows].map((row) =>
    row.map((value) => toExcelCellValue(value)),
  );

  await writeXlsxFile(sheetData, {
    sheet: sheetName,
  }).toFile(`${filename}.xlsx`);
}
