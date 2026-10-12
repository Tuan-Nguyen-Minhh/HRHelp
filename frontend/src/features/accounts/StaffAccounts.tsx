import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ROLE_LABEL } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { StaffAccount } from "@/types/api";

type Role = "HR" | "LEGAL";

interface Draft {
  email: string;
  full_name: string;
  password: string;
  role: Role;
  is_active: boolean;
}

const emptyDraft = (): Draft => ({ email: "", full_name: "", password: "", role: "HR", is_active: true });

export function StaffAccounts() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["staff-accounts"], queryFn: () => api.staffAccounts() });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [error, setError] = useState<string | null>(null);
  const rows = query.data?.users ?? [];

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["staff-accounts"] });
  }

  const create = useMutation({
    mutationFn: () =>
      api.createStaff({
        email: draft.email.trim(),
        full_name: draft.full_name.trim() || null,
        password: draft.password,
        role: draft.role,
      }),
    onSuccess: () => {
      setCreating(false);
      setDraft(emptyDraft());
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const update = useMutation({
    mutationFn: (userId: string) =>
      api.updateStaff(userId, {
        email: draft.email.trim(),
        full_name: draft.full_name.trim(),
        role: draft.role,
        is_active: draft.is_active,
        ...(draft.password.trim() ? { password: draft.password } : {}),
      }),
    onSuccess: () => {
      setEditing(null);
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (userId: string) => api.deleteStaff(userId),
    onSuccess: () => {
      setRemoving(null);
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function startEdit(row: StaffAccount) {
    setCreating(false);
    setRemoving(null);
    setEditing(row.user_id);
    setError(null);
    setDraft({
      email: row.email,
      full_name: row.full_name ?? "",
      password: "",
      role: row.role === "LEGAL" ? "LEGAL" : "HR",
      is_active: row.is_active,
    });
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-ink">Tài khoản HR và pháp chế</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-3">
            Quản lý tạo, sửa và xóa hai vai trò này. Tài khoản quản lý, người ký và quản trị không nằm ở đây.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setRemoving(null);
            setCreating(true);
            setDraft(emptyDraft());
            setError(null);
          }}
        >
          Thêm tài khoản
        </Button>
      </div>
      {error ? <p className="text-sm text-son-dark">{error}</p> : null}
      {query.isLoading ? (<div className="space-y-2" role="status" aria-label="Đang tải tài khoản">{Array.from({ length: 3 }).map((_, i) => (<div key={i} className="skeleton h-12" aria-hidden="true" />))}</div>) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {creating ? (
        <AccountForm
          draft={draft}
          setDraft={setDraft}
          passwordRequired
          pending={create.isPending}
          submitLabel="Tạo tài khoản"
          onCancel={() => setCreating(false)}
          onSubmit={() => create.mutate()}
        />
      ) : null}
      {!query.isLoading && !query.isError && rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">
          Chưa có tài khoản HR hoặc pháp chế.
        </p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((row) => (
          <li key={row.user_id} className="rounded-xl border border-rule bg-white px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium text-ink">{row.full_name || row.email}</p>
                <p className="text-sm text-ink-3">
                  {row.email} · {ROLE_LABEL[row.role] ?? row.role}
                  {row.is_active ? "" : " · Đang khóa"}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => startEdit(row)}>
                  Sửa
                </Button>
                <Button variant="secondary" size="sm" onClick={() => { setCreating(false); setEditing(null); setRemoving(row.user_id); setError(null); }}>
                  Xóa
                </Button>
              </div>
            </div>
            {editing === row.user_id ? (
              <div className="mt-3">
                <AccountForm
                  draft={draft}
                  setDraft={setDraft}
                  pending={update.isPending}
                  submitLabel="Lưu sửa"
                  onCancel={() => setEditing(null)}
                  onSubmit={() => update.mutate(row.user_id)}
                />
              </div>
            ) : null}
            {removing === row.user_id ? (
              <div className="mt-3 rounded-lg border border-son-line bg-son-tint p-3 text-sm">
                <p>Xóa {row.email}? Người này không đăng nhập được nữa. Hồ sơ đã tạo vẫn giữ nguyên.</p>
                <div className="mt-2 flex gap-2">
                  <Button variant="secondary" onClick={() => setRemoving(null)}>
                    Hủy
                  </Button>
                  <Button variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate(row.user_id)}>
                    {remove.isPending ? "Đang xóa…" : "Xác nhận xóa"}
                  </Button>
                </div>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function AccountForm({
  draft,
  setDraft,
  passwordRequired = false,
  pending,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  draft: Draft;
  setDraft: (next: Draft) => void;
  passwordRequired?: boolean;
  pending: boolean;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const passwordOk = !passwordRequired || draft.password.trim().length >= 8;
  return (
    <form
      className="space-y-3 rounded-xl border border-rule bg-white p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="staff-email">Email</Label>
          <Input id="staff-email" type="email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="staff-name">Họ tên</Label>
          <Input id="staff-name" value={draft.full_name} onChange={(event) => setDraft({ ...draft, full_name: event.target.value })} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="staff-role">Vai trò</Label>
          <select
            id="staff-role"
            className="h-9 w-full rounded-md border border-rule bg-white px-3 text-sm text-ink"
            value={draft.role}
            onChange={(event) => setDraft({ ...draft, role: event.target.value as Role })}
          >
            <option value="HR">Nhân sự</option>
            <option value="LEGAL">Pháp chế</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="staff-password">{passwordRequired ? "Mật khẩu" : "Mật khẩu mới"}</Label>
          <Input
            id="staff-password"
            type="password"
            autoComplete="new-password"
            value={draft.password}
            placeholder={passwordRequired ? "Ít nhất 8 ký tự" : "Để trống nếu giữ mật khẩu cũ"}
            onChange={(event) => setDraft({ ...draft, password: event.target.value })}
            required={passwordRequired}
            minLength={passwordRequired ? 8 : undefined}
          />
        </div>
      </div>
      {passwordRequired ? null : (
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={draft.is_active} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })} />
          Đang được đăng nhập
        </label>
      )}
      <div className="flex gap-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Hủy
        </Button>
        <Button type="submit" disabled={pending || !draft.email.trim() || !passwordOk}>
          {pending ? "Đang lưu…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
