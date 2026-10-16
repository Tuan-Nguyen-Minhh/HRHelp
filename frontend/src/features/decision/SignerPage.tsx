import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { useMe } from "@/app/providers";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { sanctionLabel } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { DecisionView } from "@/types/api";

export function SignerPage() {
  const { caseId = "" } = useParams();
  const location = useLocation();
  const me = useMe();
  const manager = location.pathname.startsWith("/manager");
  const back = manager ? "/dashboard" : "/decisions";
  const canMarkPrecedent = me.data?.role === "SIGNER" || me.data?.role === "ADMIN";
  const queryClient = useQueryClient();
  const preview = useQuery({
    queryKey: ["decision-preview", caseId],
    queryFn: () => api.decisionPreview(caseId),
    retry: false,
  });
  const issued = useQuery({
    queryKey: ["export-decision", caseId],
    queryFn: () => api.exportCase(caseId, "decision"),
    enabled: axios.isAxiosError(preview.error) && preview.error.response?.status === 409,
    retry: false,
  });
  const [code, setCode] = useState("");
  const [summary, setSummary] = useState("");
  const [basis, setBasis] = useState("");
  const [precedent, setPrecedent] = useState("");
  const [confirmIssue, setConfirmIssue] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionView | null>(null);

  const issue = useMutation({
    mutationFn: () =>
      api.issueDecision(caseId, { decision_code: code, summary, legal_basis: basis || null }, idempotencyKey(`decision:${caseId}`)),
    onSuccess: (view) => {
      clearIdempotency(`decision:${caseId}`);
      setResult(view);
      setError(null);
      setConfirmIssue(false);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["decision-preview", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["manager-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });
  const mark = useMutation({
    mutationFn: () => api.markPrecedent(caseId, precedent, idempotencyKey(`precedent:${caseId}`)),
    onSuccess: (view) => {
      clearIdempotency(`precedent:${caseId}`);
      setResult(view);
      setError(null);
    },
    onError: (err) => setError(errorMessage(err)),
  });
  const close = useMutation({
    mutationFn: () => api.closeCase(caseId, idempotencyKey(`close:${caseId}`)),
    onSuccess: () => {
      clearIdempotency(`close:${caseId}`);
      setConfirmClose(false);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const sanction = preview.data?.sanction_type || result?.sanction_type;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link className="text-sm text-son-dark underline" to={back}>
        {manager ? "Bảng điều khiển" : "Danh sách quyết định"}
      </Link>
      <h1 className="text-2xl font-semibold text-ink">{manager ? "Duyệt lần cuối" : "Ban hành quyết định"}</h1>
      {error ? <p className="text-sm text-son-dark">{error}</p> : null}
      {preview.data ? (
        <Card>
          <CardHeader>
            <CardTitle>Mức đã được duyệt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-lg font-semibold text-ink">{sanctionLabel(preview.data.sanction_type)}</p>
            <p className="whitespace-pre-wrap text-ink-2">{preview.data.decision_draft}</p>
            <Input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Mã quyết định" />
            <Textarea rows={4} value={summary} onChange={(event) => setSummary(event.target.value)} placeholder="Tóm tắt quyết định" />
            <Textarea rows={3} value={basis} onChange={(event) => setBasis(event.target.value)} placeholder="Căn cứ ban hành" />
            {confirmIssue ? (
              <div className="rounded-lg border border-son-line bg-son-tint p-3">
                <p>
              {manager ? "Duyệt lần cuối mức" : "Ban hành mức"} {sanctionLabel(sanction)}? Thao tác được ghi vào lịch sử hồ sơ.
            </p>
                <div className="mt-2 flex gap-2">
                  <Button variant="secondary" onClick={() => setConfirmIssue(false)}>Hủy</Button>
                  <Button disabled={!code.trim() || !summary.trim() || issue.isPending} onClick={() => issue.mutate()}>
                    {issue.isPending ? "Đang ghi…" : manager ? "Xác nhận duyệt cuối" : "Xác nhận ban hành"}
                  </Button>
                </div>
              </div>
            ) : (
              <Button disabled={!code.trim() || !summary.trim()} onClick={() => setConfirmIssue(true)}>
                {manager ? "Duyệt lần cuối" : "Ban hành quyết định"}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : null}
      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>Đã ban hành {result.decision_code}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Mức: {sanctionLabel(result.sanction_type)}</p>
            <p>Tiền lệ: {result.is_precedent ? "Đã đánh dấu" : "Chưa"}</p>
          </CardContent>
        </Card>
      ) : null}
      {(result || issued.data) && !preview.data ? (
        <Card>
          <CardHeader>
            <CardTitle>Quyết định đã lưu</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm">
              {typeof issued.data?.content === "string" ? issued.data.content : JSON.stringify(issued.data?.content ?? result, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>{canMarkPrecedent ? "Tiền lệ và đóng hồ sơ" : "Đóng hồ sơ"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {canMarkPrecedent ? (
            <>
              <p>Chỉ quyết định đã ban hành mới thành tiền lệ. Tóm tắt không được để trống.</p>
              <Textarea rows={3} value={precedent} onChange={(event) => setPrecedent(event.target.value)} placeholder="Tóm tắt tiền lệ" />
              <Button variant="secondary" disabled={!precedent.trim() || mark.isPending} onClick={() => mark.mutate()}>
                Đánh dấu tiền lệ
              </Button>
            </>
          ) : (
            <p>Sau khi duyệt cuối, hồ sơ có thể đóng. Tiền lệ do người ký ghi.</p>
          )}
          {confirmClose ? (
            <div className="rounded-lg border border-rule p-3">
              <p>Đóng hồ sơ? Sau khi đóng, hồ sơ không nhận thêm tình tiết.</p>
              <div className="mt-2 flex gap-2">
                <Button variant="secondary" onClick={() => setConfirmClose(false)}>Hủy</Button>
                <Button disabled={close.isPending} onClick={() => close.mutate()}>Đóng hồ sơ</Button>
              </div>
            </div>
          ) : (
            <Button onClick={() => setConfirmClose(true)}>Đóng hồ sơ</Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
