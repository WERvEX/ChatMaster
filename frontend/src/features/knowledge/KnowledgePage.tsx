import {
  AlertTriangle,
  Check,
  ChevronDown,
  FileText,
  Layers3,
  ListFilter,
  Trash2,
  X,
} from "lucide-react";
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  deleteDocument,
  getDocuments,
  getIndexes,
  getIngestJobs,
  rebuildIndex,
  retryIngestJob,
} from "../../api/client";
import { DocumentUpload } from "../../components/DocumentUpload";
import type { IndexVersionOut } from "../../types/api";

interface Props {
  identityId: string | null;
  onBack: () => void;
}

type KnowledgeTab = "documents" | "jobs" | "import";

export function KnowledgePage({ identityId, onBack }: Props) {
  const [activeTab, setActiveTab] = useState<KnowledgeTab>("documents");
  const [scope, setScope] = useState<"all" | "private" | "common">("all");
  const [statusFilter, setStatusFilter] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [rebuildingId, setRebuildingId] = useState<string | null>(null);
  const documents = useQuery({
    queryKey: ["documents", identityId, scope, statusFilter],
    queryFn: () =>
      getDocuments({
        identityId: scope === "private" ? identityId : null,
        namespace: scope === "all" ? "" : scope,
        status: statusFilter,
      }),
  });
  const jobs = useQuery({
    queryKey: ["ingest-jobs", statusFilter],
    queryFn: () => getIngestJobs(statusFilter),
    refetchInterval: (query) =>
      query.state.data?.some((job) => ["pending", "running"].includes(job.status))
        ? 2000
        : false,
  });
  const indexes = useQuery({
    queryKey: ["indexes"],
    queryFn: getIndexes,
    refetchInterval: 5000,
  });

  const retry = async (jobId: string) => {
    await retryIngestJob(jobId);
    await jobs.refetch();
  };

  const remove = async (documentId: string) => {
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteDocument(documentId);
      setDeletingId(null);
      await Promise.all([documents.refetch(), jobs.refetch()]);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "删除失败，请稍后重试。");
    } finally {
      setDeleteBusy(false);
    }
  };

  const rebuild = async (index: IndexVersionOut) => {
    setRebuildingId(index.id);
    try {
      await rebuildIndex(index.namespace, index.namespace === "private" ? index.identity_id : null);
      await indexes.refetch();
    } finally {
      setRebuildingId(null);
    }
  };

  return (
    <main className="main knowledge-page">
      <div className="main-header">
        <span>知识库</span>
        <button className="btn-link" type="button" onClick={onBack}>
          返回对话
        </button>
      </div>
      <div className="knowledge-body">
        <nav className="secondary-nav" aria-label="知识库功能">
          <button
            className={activeTab === "documents" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("documents")}
          >
            文档
          </button>
          <button
            className={activeTab === "jobs" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("jobs")}
          >
            导入任务
          </button>
          <button
            className={activeTab === "import" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("import")}
          >
            导入文档
          </button>
        </nav>

        {activeTab === "import" && (
          <section className="knowledge-section">
            <DocumentUpload identityId={identityId} />
          </section>
        )}

        {activeTab === "documents" && (
          <section className="knowledge-section">
          <div className="knowledge-section-heading">
            <div>
              <h3>文档</h3>
              <p>管理当前人格的私有资料与所有人格可用的共享资料。</p>
            </div>
            <span className="knowledge-result-count">{documents.data?.length ?? 0} 个文档</span>
          </div>
          <div className="knowledge-toolbar" aria-label="文档筛选">
            <label className="knowledge-filter">
              <span className="knowledge-filter-label"><Layers3 size={14} />知识范围</span>
              <span className="knowledge-select-shell">
                <select
                  aria-label="知识范围"
                  value={scope}
                  onChange={(event) => setScope(event.target.value as typeof scope)}
                >
                  <option value="all">全部范围</option>
                  <option value="private">当前身份私有库</option>
                  <option value="common">共享库</option>
                </select>
                <ChevronDown aria-hidden="true" size={15} />
              </span>
            </label>
            <label className="knowledge-filter">
              <span className="knowledge-filter-label"><ListFilter size={14} />处理状态</span>
              <span className="knowledge-select-shell">
                <select
                  aria-label="处理状态"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                >
                  <option value="">全部状态</option>
                  <option value="pending">等待中</option>
                  <option value="ingesting">处理中</option>
                  <option value="indexed">已完成</option>
                  <option value="failed">失败</option>
                </select>
                <ChevronDown aria-hidden="true" size={15} />
              </span>
            </label>
          </div>
          {documents.isLoading && <div className="muted">加载中…</div>}
          {documents.error && <div className="error">{String(documents.error)}</div>}
          {deleteError && <div className="knowledge-inline-error">{deleteError}</div>}
          {documents.data?.length === 0 && <div className="empty-state">暂无文档</div>}
          {documents.data && documents.data.length > 0 && (
            <div className="knowledge-table-shell">
            <table className="data-table knowledge-table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>范围</th>
                  <th>状态</th>
                  <th>时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((doc) => (
                  <Fragment key={doc.id}>
                    <tr>
                      <td>
                        <span className="knowledge-file">
                          <span className="knowledge-file-icon"><FileText size={16} /></span>
                          <span>{doc.filename}</span>
                        </span>
                      </td>
                      <td>
                        <span className={`knowledge-badge ${doc.namespace === "common" ? "common" : "private"}`}>
                          {doc.namespace === "common" ? "共享" : "私有"}
                        </span>
                      </td>
                      <td>
                        <span className={`knowledge-badge status-${doc.status}`}>
                          {doc.status === "indexed" ? "已完成" : doc.status}
                        </span>
                      </td>
                      <td className="knowledge-time">{new Date(doc.created_at).toLocaleString()}</td>
                      <td>
                        <button
                          className="knowledge-delete-button"
                          type="button"
                          aria-label={`删除 ${doc.filename}`}
                          onClick={() => {
                            setDeleteError(null);
                            setDeletingId(doc.id);
                          }}
                        >
                          <Trash2 size={15} />
                          <span>删除</span>
                        </button>
                      </td>
                    </tr>
                    {deletingId === doc.id && (
                      <tr className="knowledge-delete-row">
                        <td colSpan={5}>
                          <div className="knowledge-delete-confirm" role="alert">
                            <span className="knowledge-delete-warning"><AlertTriangle size={18} /></span>
                            <span className="knowledge-delete-copy">
                              <strong>删除“{doc.filename}”及其全部向量？</strong>
                              <small>此操作不可恢复，其他文档不会受到影响。</small>
                            </span>
                            <span className="knowledge-delete-actions">
                              <button
                                className="knowledge-cancel-button"
                                type="button"
                                disabled={deleteBusy}
                                onClick={() => setDeletingId(null)}
                              >
                                <X size={15} />
                                取消
                              </button>
                              <button
                                className="knowledge-confirm-delete"
                                type="button"
                                disabled={deleteBusy}
                                onClick={() => void remove(doc.id)}
                              >
                                <Check size={15} />
                                {deleteBusy ? "删除中…" : "确认删除"}
                              </button>
                            </span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </section>
        )}

        {activeTab === "jobs" && (
          <section className="knowledge-section">
          <h3>导入任务</h3>
          {jobs.isLoading && <div className="muted">加载中…</div>}
          {jobs.error && <div className="error">{String(jobs.error)}</div>}
          {jobs.data?.length === 0 && <div className="empty-state">暂无导入任务</div>}
          {jobs.data && jobs.data.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>状态</th>
                  <th>分块</th>
                  <th>错误</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.map((job) => (
                  <tr key={job.id}>
                    <td>{job.id.slice(0, 8)}</td>
                    <td>{job.status}</td>
                    <td>{job.total_chunks}</td>
                    <td>{job.error ?? ""}</td>
                    <td>
                      {job.status === "failed" && (
                        <button className="btn-link" onClick={() => void retry(job.id)}>
                          重试
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        )}
        {activeTab === "documents" && (
          <section className="knowledge-section">
            <h3>索引状态</h3>
            {indexes.data?.map((index) => (
              <div key={index.id} className="settings-actions">
                <span>
                  {index.namespace === "common" ? "共享" : index.identity_id} · {index.status} ·{" "}
                  {index.embedding_model}
                </span>
                {index.status === "stale" && (
                  <button
                    className="btn-link"
                    onClick={() => void rebuild(index)}
                    disabled={
                      rebuildingId !== null ||
                      (index.namespace === "private" && !index.identity_id)
                    }
                  >
                    {rebuildingId === index.id ? "重建中…" : "重建"}
                  </button>
                )}
              </div>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
