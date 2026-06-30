import type { SourceItem } from "../../types/api";

export function SourceList({ sources }: { sources: SourceItem[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="sources">
      <div className="sources-title">参考资料（{sources.length}）</div>
      <ul>
        {sources.map((s) => (
          <li key={s.n}>
            <span className="src-n">[{s.n}]</span> {s.source_file}
            <span className="src-coll"> · {s.collection}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
