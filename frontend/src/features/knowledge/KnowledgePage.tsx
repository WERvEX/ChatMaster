import { useQuery } from "@tanstack/react-query";
import { getDocuments, getIngestJobs } from "../../api/client";
import { DocumentUpload } from "../../components/DocumentUpload";

interface Props {
  identityId: string | null;
}

export function KnowledgePage({ identityId }: Props) {
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });
  const jobs = useQuery({
    queryKey: ["ingest-jobs"],
    queryFn: getIngestJobs,
  });

  return (
    <main className="main knowledge-page">
      <div className="main-header">
        <span>知识库</span>
      </div>
      <div className="knowledge-body">
        <section className="knowledge-section">
          <DocumentUpload identityId={identityId} />
        </section>

        <section className="knowledge-section">
          <h3>文档</h3>
          {documents.isLoading && <div className="muted">加载中…</div>}
          {documents.error && <div className="error">{String(documents.error)}</div>}
          {documents.data && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>范围</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((doc) => (
                  <tr key={doc.id}>
                    <td>{doc.filename}</td>
                    <td>{doc.namespace}</td>
                    <td>{doc.status}</td>
                    <td>{new Date(doc.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="knowledge-section">
          <h3>导入任务</h3>
          {jobs.isLoading && <div className="muted">加载中…</div>}
          {jobs.error && <div className="error">{String(jobs.error)}</div>}
          {jobs.data && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>状态</th>
                  <th>分块</th>
                  <th>错误</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.map((job) => (
                  <tr key={job.id}>
                    <td>{job.id.slice(0, 8)}</td>
                    <td>{job.status}</td>
                    <td>{job.total_chunks}</td>
                    <td>{job.error ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </main>
  );
}
