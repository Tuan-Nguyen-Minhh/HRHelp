import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { StatusTone } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";
import type { IngestionDocument } from "@/types/api";

const ACCEPT = ".docx,.pdf,.md,.markdown,.txt";
const IN_PROGRESS = new Set(["UPLOADED", "CHUNKED"]);
const STATUS: Record<string, { label: string; tone: StatusTone }> = {
  UPLOADED: { label: "Đang xử lý", tone: "info" },
  CHUNKED: { label: "Đang nhúng", tone: "warning" },
  EMBEDDED: { label: "Hoàn tất", tone: "success" },
  FAILED: { label: "Thất bại", tone: "danger" },
};

function formatTime(value: string): string {
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? value : at.toLocaleString("vi-VN");
}

export function AdminIngestionPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["ingestion-documents"],
    queryFn: () => api.listIngestionDocuments(),
    refetchInterval: (q) =>
      (q.state.data?.documents ?? []).some((doc) => IN_PROGRESS.has(doc.ingest_status)) ? 3000 : false,
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["ingestion-documents"] });

  const upload = useMutation({
    mutationFn: () => api.uploadIngestionDocument(file as File, effectiveFrom || undefined),
    onSuccess: () => {
      setFile(null);
      setEffectiveFrom("");
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const retry = useMutation({
    mutationFn: (documentId: string) => api.retryIngestionDocument(documentId),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const rows = query.data?.documents ?? [];

  function pick(next: File | null) {
    if (!next) return;
    setFile(next);
    setError(null);
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="font-ui text-2xl font-semibold text-ink">Nạp văn bản</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-3">
          Tải lên văn bản nguồn mới. Hệ thống tự chuyển sang Markdown, tách Điều/Khoản/Điểm và nhúng vào kho tri thức
          mà trợ lý đang tra cứu.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Tải tệp lên</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label
            htmlFor="ingestion-file"
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              pick(event.dataTransfer.files?.[0] ?? null);
            }}
            className={cn(
              "flex min-h-[112px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-6 text-center text-sm transition-colors",
              dragging ? "border-son bg-son-tint text-son-dark" : "border-rule-2 bg-paper text-ink-3 hover:border-ink-3",
            )}
          >
            <input
              id="ingestion-file"
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={(event) => pick(event.target.files?.[0] ?? null)}
            />
            {file ? (
              <span className="font-medium text-ink">{file.name}</span>
            ) : (
              <span>Kéo thả tệp vào đây hoặc bấm để chọn (.docx, .pdf, .md, .txt)</span>
            )}
          </label>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ingestion-date">Ngày hiệu lực (tùy chọn)</Label>
              <Input
                id="ingestion-date"
                type="date"
                value={effectiveFrom}
                onChange={(event) => setEffectiveFrom(event.target.value)}
              />
            </div>
            <Button disabled={!file || upload.isPending} onClick={() => upload.mutate()}>
              {upload.isPending ? "Đang nạp…" : "Nạp văn bản"}
            </Button>
          </div>
          {error ? <p className="text-sm text-son-dark">{error}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Văn bản đã nạp</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? <p className="text-sm text-ink-3">Đang tải…</p> : null}
          {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
          {!query.isLoading && !query.isError && rows.length === 0 ? (
            <p className="text-sm text-ink-3">Chưa có văn bản nào được nạp.</p>
          ) : null}
          <ul className="divide-y divide-rule">
            {rows.map((doc) => (
              <DocumentRow key={doc.document_id} doc={doc} retrying={retry.isPending} onRetry={() => retry.mutate(doc.document_id)} />
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}

function DocumentRow({ doc, retrying, onRetry }: { doc: IngestionDocument; retrying: boolean; onRetry: () => void }) {
  const status = STATUS[doc.ingest_status] ?? { label: doc.ingest_status, tone: "neutral" as StatusTone };
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-ink">{doc.policy_name || doc.file_name}</p>
        <p className="mt-0.5 text-sm text-ink-3">
          {doc.file_name}
          {doc.policy_code ? ` · ${doc.policy_code}` : ""}
        </p>
        <p className="mt-0.5 text-xs text-ink-4">
          {doc.chunk_count} đoạn · đã nhúng {doc.embedded_chunk_count}/{doc.chunk_count} · {formatTime(doc.created_at)}
        </p>
        {doc.error ? <p className="mt-1 text-xs text-son-dark">{doc.error}</p> : null}
      </div>
      <div className="flex items-center gap-3">
        <Badge tone={status.tone}>{status.label}</Badge>
        {doc.ingest_status === "FAILED" ? (
          <Button variant="secondary" size="sm" disabled={retrying} onClick={onRetry}>
            Chạy lại
          </Button>
        ) : null}
      </div>
    </li>
  );
}
