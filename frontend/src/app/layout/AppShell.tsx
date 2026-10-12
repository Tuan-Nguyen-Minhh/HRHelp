import { useQuery } from "@tanstack/react-query";
import { Bell, Bot, FileSearch, Gavel, LayoutDashboard, LogOut, Scale, ScrollText, ShieldCheck } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth, useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { ROLE_LABEL } from "@/lib/labels";
import { api } from "@/services/api";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: string[];
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Bảng điều khiển", icon: LayoutDashboard, roles: ["HR", "MANAGER", "LEGAL", "SIGNER", "ADMIN"] },
  { to: "/cases", label: "Hồ sơ HR", icon: FileSearch, roles: ["HR", "ADMIN"] },
  { to: "/legal-review", label: "Pháp chế", icon: Scale, roles: ["LEGAL"] },
  { to: "/manager", label: "Duyệt cuối", icon: Gavel, roles: ["MANAGER"] },
  { to: "/decisions", label: "Quyết định", icon: Gavel, roles: ["SIGNER", "ADMIN"] },
  { to: "/notifications", label: "Thông báo", icon: Bell, roles: ["HR", "MANAGER", "LEGAL", "SIGNER", "ADMIN"] },
  { to: "/audit", label: "Nhật ký", icon: ScrollText, roles: ["ADMIN"] },
];

export function AppShell() {
  const { auth, logout } = useAuth();
  const location = useLocation();
  const me = useMe();
  const role = me.data?.role || auth?.roles?.[0] || "";
  const items = NAV.filter((item) => item.roles.includes(role));
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api.notifications(), enabled: Boolean(auth) });
  const unread = (notes.data?.notifications ?? []).filter((item) => !item.read_at).length;

  return (
    <div className="min-h-screen bg-paper lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <aside className="sticky top-0 z-30 border-b border-rule bg-linen text-ink shadow-sm lg:h-screen lg:border-b-0 lg:border-r lg:overflow-y-auto">
        <div className="px-5 py-5 lg:py-6">
          <div className="mb-2 flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-[1.5px] border-son font-doc text-[6px] font-semibold leading-tight text-son" style={{ transform: "rotate(-9deg)" }} aria-hidden="true">
              HR
              <br />
              HELP
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold tracking-[0.18em] text-son">HR HELP</p>
              <p className="truncate font-ui text-[17px] font-semibold leading-tight text-ink">Kỷ luật lao động</p>
            </div>
          </div>
          <p className="mt-1 text-xs leading-5 text-ink-3">AI đề xuất. Người quyết định.</p>
        </div>
        <div className="mx-5 mb-4 hidden rounded-md border border-rule bg-paper p-4 lg:block">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-paper-2 text-ink-2">
              <Bot className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">Trợ lý hồ sơ</p>
              <p className="mt-1 text-xs leading-5 text-ink-3">Dẫn dắt từng bước, giữ ngữ cảnh và nhắc phần còn thiếu.</p>
            </div>
          </div>
        </div>
        <hr className="mx-5 mb-4 border-rule" />
        <nav className="flex gap-2 overflow-x-auto px-4 pb-3 lg:block lg:space-y-1 lg:pb-5" aria-label="Điều hướng">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex shrink-0 items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-200 lg:w-full",
                  isActive
                    ? "bg-paper font-semibold text-ink shadow-sm ring-1 ring-rule"
                    : "text-ink-2 hover:bg-paper-2 hover:text-ink",
                )
              }
              style={({ isActive }) =>
                isActive ? { boxShadow: "inset 2px 0 0 var(--son)" } : undefined
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mx-5 mb-5 hidden rounded-md border border-son-line bg-son-tint p-4 text-xs leading-5 text-son-dark lg:block">
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Luồng an toàn
          </div>
          AI chỉ gợi ý, các bước duyệt và ký vẫn tách rõ theo vai trò.
        </div>
      </aside>
      <div className="min-w-0">
        <header className="z-20 flex items-center justify-between gap-3 border-b border-rule bg-paper px-4 py-3.5 lg:sticky lg:top-0 lg:px-6">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{me.data?.full_name || me.data?.email || "Phiên làm việc"}</p>
            <p className="text-xs text-ink-3">{ROLE_LABEL[role] ?? role}</p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              className="relative inline-flex h-10 items-center gap-2 rounded-md border border-rule bg-paper px-3 text-sm text-ink transition-colors hover:bg-paper-2"
              to="/notifications"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Thông báo</span>
              {unread > 0 ? (
                <div className="flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-son opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-son"></span>
                  </span>
                  <span className="font-semibold text-son-dark">{unread}</span>
                </div>
              ) : (
                <span className="text-ink-3">0</span>
              )}
            </Link>
            <Button variant="ghost" size="sm" onClick={() => void logout()}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Đăng xuất
            </Button>
          </div>
        </header>
        <main id="main" key={location.pathname} className="page-fade px-4 py-5 lg:px-6 lg:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
