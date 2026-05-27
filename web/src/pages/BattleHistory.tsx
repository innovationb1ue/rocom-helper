import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Space, Table, Tag, Tooltip, message } from 'antd';
import type { TableProps } from 'antd';
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { AxiosError } from 'axios';

import { downloadBattleReport, fetchBattleReports } from '../utils/api';
import type { BattleReportSummary } from '../utils/api';

const formatDuration = (seconds: number) => {
  if (!Number.isFinite(seconds)) return '-';
  const minutes = Math.floor(seconds / 60);
  const remain = Math.round(seconds % 60);
  return minutes > 0 ? `${minutes}分${remain}秒` : `${remain}秒`;
};

const saveBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

const canExportReport = (report: BattleReportSummary) =>
  report.file_count > 0 && report.battle_packet_count > 0;

const sessionDateParts = (sessionId: string) => {
  const match = sessionId.match(/^(\d{4})-(\d{2})-(\d{2})_/);
  return match ? { year: match[1], month: match[2], day: match[3] } : null;
};

const addOneDay = (year: string, month: string, day: string) => {
  const date = new Date(Number(year), Number(month) - 1, Number(day) + 1);
  return {
    year: String(date.getFullYear()).padStart(4, '0'),
    month: String(date.getMonth() + 1).padStart(2, '0'),
    day: String(date.getDate()).padStart(2, '0'),
  };
};

const reportDatePartsFor = (report: BattleReportSummary, timeKind: 'enter' | 'finish') => {
  const parts = sessionDateParts(report.session_id);
  if (!parts) return null;
  if (timeKind === 'finish' && report.finish_ts.localeCompare(report.enter_ts) < 0) {
    return addOneDay(parts.year, parts.month, parts.day);
  }
  return parts;
};

const formatFullDateTime = (report: BattleReportSummary, timeKind: 'enter' | 'finish') => {
  const parts = reportDatePartsFor(report, timeKind);
  const time = timeKind === 'enter' ? report.enter_ts : report.finish_ts;
  if (!parts) return time;
  return `${parts.year}年${parts.month}月${parts.day}日 ${time}`;
};

const reportSortKey = (report: BattleReportSummary) => {
  const parts = reportDatePartsFor(report, 'enter');
  if (!parts) return `${report.session_id}_${report.enter_ts}`;
  return `${parts.year}-${parts.month}-${parts.day} ${report.enter_ts}`;
};

const formatSessionTime = (report: BattleReportSummary) => (
  <Space orientation="vertical" size={0}>
    <span>{formatFullDateTime(report, 'enter')}</span>
    <span style={{ color: '#8c8c8c', fontSize: 12 }}>
      至 {formatFullDateTime(report, 'finish')}
    </span>
  </Space>
);

const renderStatusTags = (complete: boolean, record: BattleReportSummary) => (
  <Space size={4} wrap>
    {complete ? <Tag color="success">完整</Tag> : <Tag color="warning">未完成</Tag>}
    {record.archived ? (
      <Tag color="geekblue">已归档</Tag>
    ) : (
      <Tag color={canExportReport(record) ? 'default' : 'error'}>
        {canExportReport(record) ? '可导出' : '无包'}
      </Tag>
    )}
  </Space>
);

const readDownloadError = async (err: unknown) => {
  const fallback = '导出报告失败';
  const responseData = (err as AxiosError)?.response?.data;
  if (responseData instanceof Blob) {
    const text = await responseData.text();
    if (!text) return fallback;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      return typeof parsed.detail === 'string' ? parsed.detail : text;
    } catch {
      return text;
    }
  }
  if (
    responseData &&
    typeof responseData === 'object' &&
    'detail' in responseData &&
    typeof responseData.detail === 'string'
  ) {
    return responseData.detail;
  }
  return fallback;
};

const BattleHistory: React.FC = () => {
  const [reports, setReports] = useState<BattleReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const data = await fetchBattleReports();
      setReports(data.reports);
    } catch (err) {
      console.error('[BattleHistory] load reports failed:', err);
      message.error('加载战斗历史失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchBattleReports()
      .then((data) => {
        if (!cancelled) {
          setReports(data.reports);
        }
      })
      .catch((err) => {
        console.error('[BattleHistory] load reports failed:', err);
        message.error('加载战斗历史失败');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDownload = async (report: BattleReportSummary) => {
    setDownloading(report.report_id);
    try {
      const { blob, filename } = await downloadBattleReport(report.report_id);
      saveBlob(blob, filename);
      message.success('报告已导出');
    } catch (err) {
      console.error('[BattleHistory] download report failed:', err);
      message.error(await readDownloadError(err));
    } finally {
      setDownloading(null);
    }
  };

  const sortedReports = useMemo(
    () => [...reports].sort((a, b) => reportSortKey(b).localeCompare(reportSortKey(a))),
    [reports],
  );
  const sequenceByReportId = useMemo(
    () => new Map(sortedReports.map((report, index) => [report.report_id, index + 1])),
    [sortedReports],
  );

  const columns = useMemo<TableProps<BattleReportSummary>['columns']>(() => [
    {
      title: '记录',
      key: 'compact_record',
      responsive: ['xs', 'sm'],
      width: 250,
      render: (_: unknown, record) => (
        <Space orientation="vertical" size={2} style={{ maxWidth: '100%' }}>
          <Space size={6} wrap>
            <Tag color="blue">#{sequenceByReportId.get(record.report_id)}</Tag>
            <span style={{ fontWeight: 500 }}>{record.session_id}</span>
          </Space>
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>
            原始 #{record.battle_index} · {formatFullDateTime(record, 'enter')}
          </span>
        </Space>
      ),
    },
    {
      title: '#',
      key: 'sequence',
      width: 64,
      fixed: 'left',
      responsive: ['md'],
      render: (_: unknown, record) => (
        <Tooltip title={`原始场次：${record.session_id} #${record.battle_index}`}>
          <Tag color="blue">#{sequenceByReportId.get(record.report_id)}</Tag>
        </Tooltip>
      ),
    },
    {
      title: '会话',
      dataIndex: 'session_id',
      width: 240,
      ellipsis: true,
      responsive: ['md'],
      render: (value: string, record) => (
        <Tooltip title={`${value} #${record.battle_index}`}>
          <span>{value}</span>
        </Tooltip>
      ),
      sorter: (a, b) => a.session_id.localeCompare(b.session_id),
    },
    {
      title: '时间',
      dataIndex: 'enter_ts',
      width: 130,
      defaultSortOrder: 'descend',
      responsive: ['md'],
      render: (_: string, record) => (
        <Tooltip title={`${formatFullDateTime(record, 'enter')} - ${formatFullDateTime(record, 'finish')}`}>
          {formatSessionTime(record)}
        </Tooltip>
      ),
      sorter: (a, b) => reportSortKey(a).localeCompare(reportSortKey(b)),
    },
    {
      title: '状态',
      dataIndex: 'complete',
      width: 130,
      render: renderStatusTags,
      filters: [
        { text: '完整', value: true },
        { text: '未完成', value: false },
      ],
      onFilter: (value, record) => record.complete === value,
    },
    {
      title: '结果',
      dataIndex: 'result',
      width: 92,
      responsive: ['md'],
      render: (value: string | null) => value ? <Tag>{value}</Tag> : <Tag color="default">未知</Tag>,
      sorter: (a, b) => (a.result || '').localeCompare(b.result || ''),
    },
    {
      title: '回合',
      dataIndex: 'rounds',
      width: 88,
      responsive: ['md'],
      render: (value: number | null) => value ?? '-',
      sorter: (a, b) => (a.rounds ?? -1) - (b.rounds ?? -1),
    },
    {
      title: '文件',
      dataIndex: 'file_count',
      width: 96,
      responsive: ['lg'],
      render: (value: number, record) => (
        <Tooltip title={`窗口文件 ${value} 个，战斗包 ${record.battle_packet_count} 个`}>
          <span>{value} / {record.battle_packet_count}</span>
        </Tooltip>
      ),
      sorter: (a, b) => a.file_count - b.file_count,
    },
    {
      title: '时长',
      dataIndex: 'duration_seconds',
      width: 110,
      responsive: ['lg'],
      render: formatDuration,
      sorter: (a, b) => a.duration_seconds - b.duration_seconds,
    },
    {
      title: '',
      key: 'actions',
      width: 64,
      align: 'right',
      render: (_, record) => {
        const exportable = canExportReport(record);
        return (
          <Tooltip title={exportable ? '导出报告' : '无可导出包'}>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              aria-label="导出报告"
              disabled={!exportable}
              loading={downloading === record.report_id}
              onClick={() => void handleDownload(record)}
            />
          </Tooltip>
        );
      },
    },
  ], [downloading, sequenceByReportId]);

  return (
    <Card
      title="战斗历史"
      extra={(
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void loadReports()} loading={loading}>
            刷新
          </Button>
        </Space>
      )}
    >
      <Table<BattleReportSummary>
        rowKey="report_id"
        columns={columns}
        dataSource={sortedReports}
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{ emptyText: <Empty description="暂无战斗记录" /> }}
        size="small"
        scroll={{ x: 'max-content' }}
      />
    </Card>
  );
};

export default BattleHistory;
