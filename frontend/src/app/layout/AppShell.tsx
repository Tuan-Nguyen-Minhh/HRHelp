import { useQuery } from "@tanstack/react-query";
import { Bell, FileSearch, Gavel, LayoutDashboard, LogOut, Scale, ScrollText } from "lucide-react";
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
    <div className="min-h-screen bg-[#f4fafb] lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <aside className="border-b border-[#062c36] bg-[#073642] text-white lg:min-h-screen lg:border-b-0">
        <div className="px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.18em] text-[#7fd3e6]">HR HELP</p>
          <p className="mt-1 text-lg font-semibold leading-tight">Kỷ luật lao động</p>
          <p className="mt-1 text-xs text-[#b7dbe3]">AI đề xuất. Người quyết định.</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 lg:block lg:space-y-1 lg:px-3 lg:pb-6" aria-label="Điều hướng">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#d7eef3]",
                  isActive ? "bg-[#009EC1] text-white" : "hover:bg-white/10",
                )
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="min-w-0">
        <header className="flex items-center justify-between gap-3 border-b border-[#d5e8ed] bg-white px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[#073642]">{me.data?.full_name || me.data?.email || "Phiên làm việc"}</p>
            <p className="text-xs text-[#4d7380]">{ROLE_LABEL[role] ?? role}</p>
          </div>
          <Link
            className="relative inline-flex h-9 items-center gap-2 rounded-full border border-[#d5e8ed] px-3 text-sm text-[#073642] hover:bg-[#f4fafb]"
            to="/notifications"
          >
            <Bell className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Thông báo</span>
            {unread > 0 ? <span className="font-semibold text-[#009EC1]">{unread}</span> : <span className="text-[#4d7380]">0</span>}
          </Link>
          <Button variant="ghost" size="sm" onClick={() => void logout()}>
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Đăng xuất
          </Button>
        </header>
        <main id="main" className="px-4 py-5">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
