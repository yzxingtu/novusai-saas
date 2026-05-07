// 中文: 测试类型 structural，覆盖 Excel 导出封装的文件名、sheet 名和单元格转换合同。
// EN: Test type structural, covering the Excel export wrapper file name, sheet name, and cell conversion contract.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const writeToFileMock = vi.hoisted(() => vi.fn());

vi.mock('write-excel-file/browser', () => ({
  default: vi.fn(() => ({
    toFile: writeToFileMock,
  })),
}));

import writeXlsxFile from 'write-excel-file/browser';

import { writeRecordsToExcel } from '../excel-export';

describe('writeRecordsToExcel', () => {
  beforeEach(() => {
    writeToFileMock.mockReset();
    vi.mocked(writeXlsxFile).mockClear();
  });

  it('writes headers and rows to the expected xlsx path and sheet', async () => {
    await writeRecordsToExcel({
      filename: 'notification-templates',
      headers: ['Code', 'Payload'],
      rows: [[123, { nested: true }]],
      sheetName: 'Templates',
    });

    expect(writeXlsxFile).toHaveBeenCalledWith(
      [
        ['Code', 'Payload'],
        [123, '{"nested":true}'],
      ],
      { sheet: 'Templates' },
    );
    expect(writeToFileMock).toHaveBeenCalledWith(
      'notification-templates.xlsx',
    );
  });
});
