import { DRAFT_LABEL, DRAFT_STATUS_LABEL } from "@/lib/labels";
import type { DraftView } from "@/types/api";

export function DraftList({ drafts }: { drafts: DraftView[] }) {
  if (!drafts.length) return <p className="text-sm text-neutral-600">Chưa có bản thảo.</p>;
  return (
    <div className="space-y-3">
      {drafts.map((draft) => (
        <article key={draft.draft_id} className="rounded-md border border-neutral-200 px-3 py-3">
          <header className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold tracking-wide text-neutral-500">{DRAFT_LABEL[draft.draft_type] ?? draft.draft_type}</p>
            <p className="text-xs text-neutral-500">{DRAFT_STATUS_LABEL[draft.status] ?? draft.status}</p>
          </header>
          <h3 className="mt-1 text-sm font-medium">{draft.title}</h3>
          <DraftBody draft={draft} />
        </article>
      ))}
    </div>
  );
}

function DraftBody({ draft }: { draft: DraftView }) {
  if (draft.draft_type !== "TICKET") return <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{draft.content}</p>;
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(draft.content);
  } catch {
    parsed = null;
  }
  if (!parsed || typeof parsed !== "object") return <p className="mt-2 whitespace-pre-wrap text-sm">{draft.content}</p>;
  return <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs leading-5 text-neutral-800">{JSON.stringify(parsed, null, 2)}</pre>;
}
