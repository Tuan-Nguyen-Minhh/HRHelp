import { StaffAccounts } from "@/features/accounts/StaffAccounts";

export function StaffAccountsPage() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">QUẢN LÝ</p>
        <h1 className="text-2xl font-semibold text-ink">Quản lý tài khoản</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-3">
          Tạo và quản lý tài khoản cho nhân sự (HR) và pháp chế.
        </p>
      </div>
      <StaffAccounts />
    </div>
  );
}
