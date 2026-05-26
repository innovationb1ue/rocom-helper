import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Space, Table, Tag, Tooltip, message } from 'antd';
import type { TableProps } from 'antd';
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons';

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
      message.error('导出报告失败');
    } finally {
      setDownloading(null);
    }
  };

  const columns = useMemo<TableProps<BattleReportSummary>['columns']>(() => [
    {
      title: '场次',
      dataIndex: 'battle_index',
      width: 88,
      render: (value: number) => <Tag color="blue">#{value}</Tag>,
      sorter: (a, b) => a.battle_index - b.battle_index,
    },
    {
      title: '会话',
      dataIndex: 'session_id',
      ellipsis: true,
      sorter: (a, b) => a.session_id.localeCompare(b.session_id),
    },
    {
      title: '时间',
      dataIndex: 'enter_ts',
      width: 180,
      render: (_: string, record) => `${record.enter_ts} - ${record.finish_ts}`,
      sorter: (a, b) => a.enter_ts.localeCompare(b.enter_ts),
    },
    {
      title: '状态',
      dataIndex: 'complete',
      width: 96,
      render: (complete: boolean) => (
        complete ? <Tag color="success">完整</Tag> : <Tag color="warning">未完成</Tag>
      ),
      filters: [
        { text: '完整', value: true },
        { text: '未完成', value: false },
      ],
      onFilter: (value, record) => record.complete === value,
    },
    {
      title: '结果',
      dataIndex: 'result',
      width: 120,
      render: (value: string | null) => value ? <Tag>{value}</Tag> : <Tag color="default">未知</Tag>,
      sorter: (a, b) => (a.result || '').localeCompare(b.result || ''),
    },
    {
      title: '回合',
      dataIndex: 'rounds',
      width: 88,
      render: (value: number | null) => value ?? '-',
      sorter: (a, b) => (a.rounds ?? -1) - (b.rounds ?? -1),
    },
    {
      title: '文件',
      dataIndex: 'file_count',
      width: 96,
      render: (value: number, record) => `${value} / ${record.battle_packet_count}`,
      sorter: (a, b) => a.file_count - b.file_count,
    },
    {
      title: '时长',
      dataIndex: 'duration_seconds',
      width: 110,
      render: formatDuration,
      sorter: (a, b) => a.duration_seconds - b.duration_seconds,
    },
    {
      title: '',
      key: 'actions',
      width: 110,
      align: 'right',
      render: (_, record) => (
        <Tooltip title="导出报告">
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={downloading === record.report_id}
            onClick={() => void handleDownload(record)}
          >
            导出
          </Button>
        </Tooltip>
      ),
    },
  ], [downloading]);

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
        dataSource={reports}
        loading={loading}
        pagination={{ pageSize: 12, showSizeChanger: false }}
        locale={{ emptyText: <Empty description="暂无战斗记录" /> }}
        size="small"
      />
    </Card>
  );
};

export default BattleHistory;
