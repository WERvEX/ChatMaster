import { useState } from "react";
import { useUpload } from "../hooks/useUpload";

interface Props {
  identityId: string | null;
}

export function DocumentUpload({ identityId }: Props) {
  const [target, setTarget] = useState<"private" | "common">("private");
  const { busy, result, error, upload, reset } = useUpload(identityId);

  const onPick = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    upload(Array.from(files), target);
  };

  return (
    <div className="upload">
      <div className="upload-header">
        <span>知识库导入</span>
        <label className="toggle">
          <input
            type="radio"
            checked={target === "private"}
            onChange={() => setTarget("private")}
          /> 私有
          <input
            type="radio"
            checked={target === "common"}
            onChange={() => setTarget("common")}
          /> 共享
        </label>
      </div>
      <label className={`dropzone ${!identityId ? "disabled" : ""}`}>
        <input
          type="file"
          multiple
          accept=".txt,.md,.pdf,.docx"
          disabled={!identityId || busy}
          onChange={(e) => onPick(e.target.files)}
          style={{ display: "none" }}
        />
        {busy ? "处理中…" : identityId ? "点击选择文件（txt/md/pdf/docx）" : "请先选择身份"}
      </label>

      {error && <div className="error">{error}</div>}
      {result && (
        <div className="upload-result">
          <div>已导入集合 <b>{result.collection}</b>，共 {result.total_chunks} 个分块：</div>
          <ul>
            {result.files.map((f, i) => (
              <li key={i}>
                {f.file} — {f.error ? <span className="error">{f.error}</span> : `${f.chunks} 块`}
              </li>
            ))}
          </ul>
          <button className="btn-link" onClick={reset}>清除</button>
        </div>
      )}
    </div>
  );
}
