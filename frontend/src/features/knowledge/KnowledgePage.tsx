import { useState } from "react";
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

interface Props {
  identityId: string | null;
  onBack: () => void;
}

type KnowledgeTab = "documents" | "jobs" | "import";

export function KnowledgePage({ identityId, onBack }: Props) {
  const [activeTab, setActiveTab] = useState<KnowledgeTab>("documents");
  const [scope, setScope] = useState<"all" | "private" | "common">("all");
  const [statusFilter, setStatusFilter] = useState("");
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
    if (!window.confirm("确定删除该文档及其全部向量吗？")) return;
    await deleteDocument(documentId);
    await Promise.all([documents.refetch(), jobs.refetch()]);
  };

  const rebuild = async (target: "private" | "common") => {
    await rebuildIndex(target, target === "private" ? identityId : null);
    await indexes.refetch();
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
          <h3>文档</h3>
          <div className="settings-actions">
            <select value={scope} onChange={(event) => setScope(event.target.value as typeof scope)}>
              <option value="all">全部范围</option>
              <option value="private">当前身份私有库</option>
              <option value="common">共享库</option>
            </select>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">全部状态</option>
              <option value="pending">等待中</option>
              <option value="ingesting">处理中</option>
              <option value="indexed">已完成</option>
              <option value="failed">失败</option>
            </select>
          </div>
          {documents.isLoading && <div className="muted">加载中…</div>}
          {documents.error && <div className="error">{String(documents.error)}</div>}
          {documents.data?.length === 0 && <div className="empty-state">暂无文档</div>}
          {documents.data && documents.data.length > 0 && (
            <table className="data-table">
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
                  <tr key={doc.id}>
                    <td>{doc.filename}</td>
                    <td>{doc.namespace === "common" ? "共享" : "私有"}</td>
                    <td>{doc.status === "indexed" ? "已完成" : doc.status}</td>
                    <td>{new Date(doc.created_at).toLocaleString()}</td>
                    <td>
                      <button className="btn-link danger-link" onClick={() => void remove(doc.id)}>
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                    onClick={() => void rebuild(index.namespace)}
                    disabled={index.namespace === "private" && !identityId}
                  >
                    重建
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
