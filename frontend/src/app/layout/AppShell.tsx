import { useQuery } from "@tanstack/react-query";
import { Bell, Bot, FileSearch, Gavel, LayoutDashboard, LogOut, Scale, ScrollText, ShieldCheck } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";

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
  const me = useMe();
  const role = me.data?.role || auth?.roles?.[0] || "";
  const items = NAV.filter((item) => item.roles.includes(role));
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api.notifications(), enabled: Boolean(auth) });
  const unread = (notes.data?.notifications ?? []).filter((item) => !item.read_at).length;

  return (
    <div className="min-h-screen bg-[#f4f8fb] lg:grid lg:grid-cols-[272px_minmax(0,1fr)]">
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <aside className="sticky top-0 z-30 border-b border-white/10 bg-gradient-dark text-white shadow-xl shadow-slate-950/10 lg:h-screen lg:border-b-0 lg:border-r lg:overflow-y-auto">
        <div className="px-5 py-5 lg:py-6">
          <div className="mb-2 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center">
              <img className="h-full w-full object-contain drop-shadow-md" src="/legal-scales-books-bg.png" alt="" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold tracking-[0.18em] text-brand-300">HR HELP</p>
              <p className="truncate text-lg font-display font-bold leading-tight text-white">Kỷ luật lao động</p>
            </div>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-300">AI đề xuất. Người quyết định.</p>
        </div>
        <div className="mx-5 mb-4 hidden rounded-2xl border border-white/10 bg-white/[0.07] p-4 lg:block">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-400/15 text-cyan-200">
              <Bot className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-semibold text-white">Trợ lý hồ sơ</p>
              <p className="mt-1 text-xs leading-5 text-slate-300">Dẫn dắt từng bước, giữ ngữ cảnh và nhắc phần còn thiếu.</p>
            </div>
          </div>
        </div>
        <hr className="mx-5 mb-4 border-white/10" />
        <nav className="flex gap-2 overflow-x-auto px-4 pb-3 lg:block lg:space-y-1 lg:pb-5" aria-label="Điều hướng">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 lg:w-full",
                  isActive 
                    ? "bg-white/[0.12] text-white shadow-sm ring-1 ring-white/10 lg:bg-brand-600/20 lg:border-l-2 lg:border-brand-400" 
                    : "text-slate-300 hover:bg-white/5 hover:text-white",
                )
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mx-5 mb-5 hidden rounded-2xl border border-emerald-300/15 bg-emerald-300/10 p-4 text-xs leading-5 text-emerald-50 lg:block">
          <div className="mb-2 flex items-center gap-2 font-semibold text-emerald-100">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Luồng an toàn
          </div>
          AI chỉ gợi ý, các bước duyệt và ký vẫn tách rõ theo vai trò.
        </div>
      </aside>
      <div className="min-w-0">
        <header className="z-20 flex items-center justify-between gap-3 border-b border-slate-200/70 bg-white/85 px-4 py-3.5 backdrop-blur-md lg:sticky lg:top-0 lg:px-6">
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-dark-900">{me.data?.full_name || me.data?.email || "Phiên làm việc"}</p>
            <p className="text-xs text-slate-500">{ROLE_LABEL[role] ?? role}</p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              className="relative inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 px-3 text-sm text-dark-900 hover:bg-brand-50 hover:border-brand-200 transition-all"
              to="/notifications"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Thông báo</span>
              {unread > 0 ? (
                <div className="flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
                  </span>
                  <span className="font-semibold text-brand-600">{unread}</span>
                </div>
              ) : (
                <span className="text-slate-500">0</span>
              )}
            </Link>
            <Button variant="ghost" size="sm" onClick={() => void logout()}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Đăng xuất
            </Button>
          </div>
        </header>
        <main id="main" className="px-4 py-5 lg:px-6 lg:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
