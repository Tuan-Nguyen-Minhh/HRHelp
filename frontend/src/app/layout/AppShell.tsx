import { useQuery } from "@tanstack/react-query";
import { Bell, BookOpen, Bot, FileSearch, Gavel, LayoutDashboard, LogOut, PanelLeftClose, PanelLeftOpen, Scale, ScrollText, ShieldCheck, Upload, Users } from "lucide-react";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { Link, matchPath, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth, useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { GuidePage } from "@/features/guide/GuidePage";
import { FloatingChat } from "@/features/conversation/FloatingChat";
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
  { to: "/manager", label: "Quản lý tài khoản", icon: Users, roles: ["MANAGER"] },
  { to: "/decisions", label: "Quyết định", icon: Gavel, roles: ["SIGNER", "ADMIN"] },
  { to: "/guide", label: "Giới thiệu & hướng dẫn", icon: BookOpen, roles: ["HR", "MANAGER", "LEGAL", "SIGNER", "ADMIN"] },
  { to: "/notifications", label: "Thông báo", icon: Bell, roles: ["HR", "MANAGER", "LEGAL", "SIGNER", "ADMIN"] },
  { to: "/admin/ingestion", label: "Nạp văn bản", icon: Upload, roles: ["ADMIN"] },
  { to: "/audit", label: "Nhật ký", icon: ScrollText, roles: ["ADMIN"] },
];

export function AppShell() {
  const { auth, logout } = useAuth();
  const location = useLocation();
  const caseMatch = matchPath("/cases/:caseId/*", location.pathname);
  const caseWorkspace = Boolean(caseMatch && caseMatch.params.caseId !== "new");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const collapsed = caseWorkspace && !sidebarExpanded;
  const [panel, setPanel] = useState<"/dashboard" | "/notifications" | "/guide" | null>(null);
  const panelTrigger = useRef<HTMLAnchorElement | null>(null);
  const isCasePage = ["/cases/:caseId/*", "/legal-review/:caseId", "/manager/:caseId", "/decisions/:caseId"].some((pattern) => {
    const match = matchPath(pattern, location.pathname);
    return Boolean(match && match.params.caseId !== "new");
  });
  const me = useMe();
  const role = me.data?.role || auth?.roles?.[0] || "";
  const items = NAV.filter((item) => item.roles.includes(role));
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api.notifications(), enabled: Boolean(auth) });
  const unread = (notes.data?.notifications ?? []).filter((item) => !item.read_at).length;

  useEffect(() => { setSidebarExpanded(false); }, [caseMatch?.params.caseId]);

  useEffect(() => {
    setPanel(null);
  }, [location.key]);

  function openPanel(event: MouseEvent<HTMLAnchorElement>, to: string) {
    if (!isCasePage || (to !== "/dashboard" && to !== "/notifications" && to !== "/guide")) return;
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    panelTrigger.current = event.currentTarget;
    setPanel(to);
  }

  return (
    <div className={cn(
      "bg-paper",
      caseWorkspace ? "grid h-dvh min-h-0 grid-cols-[64px_minmax(0,1fr)] overflow-hidden" : "min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]",
      caseWorkspace && sidebarExpanded && "md:grid-cols-[248px_minmax(0,1fr)]",
    )}>
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      {caseWorkspace && sidebarExpanded ? <button className="fixed inset-0 z-30 bg-ink/40 md:hidden" aria-label="Đóng thanh điều hướng" onClick={() => setSidebarExpanded(false)} /> : null}
      <aside className={cn(
        "z-30 border-rule bg-linen text-ink",
        caseWorkspace ? "flex h-dvh min-h-0 flex-col border-r" : "border-b shadow-sm lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:overflow-y-auto",
        caseWorkspace && sidebarExpanded && "fixed inset-y-0 left-0 z-40 w-[248px] shadow-xl md:static md:w-auto md:shadow-none",
      )}>
        {caseWorkspace ? (
          <div className={cn("flex shrink-0 pt-3", collapsed ? "justify-center" : "justify-end px-3")}>
            <Button variant="ghost" size="icon" aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} title={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} aria-expanded={sidebarExpanded} aria-controls="app-navigation" onClick={() => setSidebarExpanded((current) => !current)}>
              {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
            </Button>
          </div>
        ) : null}
        <div className={collapsed ? "flex justify-center px-2 py-5" : "px-5 py-5 lg:py-6"}>
          <div className={cn("flex items-center gap-3", !collapsed && "mb-2")}>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-[1.5px] border-son font-doc text-[6px] font-semibold leading-tight text-son" style={{ transform: "rotate(-9deg)" }} aria-hidden="true">
              HR
              <br />
              HELP
            </div>
            <div className={cn("min-w-0", collapsed && "hidden")}>
              <p className="text-[11px] font-semibold tracking-[0.18em] text-son">HR HELP</p>
              <p className="truncate font-ui text-[17px] font-semibold leading-tight text-ink">Kỷ luật lao động</p>
            </div>
          </div>
          {!collapsed ? <p className="mt-1 text-xs leading-5 text-ink-3">AI đề xuất. Người quyết định.</p> : null}
        </div>
        <div className={cn("mx-5 mb-4 rounded-md border border-rule bg-paper p-4", collapsed ? "hidden" : "hidden lg:block")}>
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
        <hr className={cn("mb-4 border-rule", collapsed ? "mx-3" : "mx-5")} />
        <nav id="app-navigation" className={cn(caseWorkspace ? "flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-4" : "flex gap-2 overflow-x-auto px-4 pb-3 lg:block lg:space-y-1 lg:pb-5")} aria-label="Điều hướng">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/manager"}
              title={collapsed ? item.label : undefined}
              aria-label={item.label}
              onClick={(event) => openPanel(event, item.to)}
              aria-haspopup={isCasePage && (item.to === "/dashboard" || item.to === "/notifications" || item.to === "/guide") ? "dialog" : undefined}
              className={({ isActive }) =>
                cn(
                  "flex shrink-0 items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-200 lg:w-full",
                  collapsed && "h-11 justify-center px-0",
                  isActive
                    ? "bg-paper font-semibold text-ink shadow-sm ring-1 ring-rule"
                    : "text-ink-2 hover:bg-paper-2 hover:text-ink",
                )
              }
              style={({ isActive }) =>
                isActive ? { boxShadow: "inset 2px 0 0 var(--son)" } : undefined
              }
            >
              <item.icon className={collapsed ? "h-5 w-5" : "h-4 w-4"} aria-hidden="true" />
              <span className={collapsed ? "sr-only" : undefined}>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className={cn("mx-5 mb-5 rounded-md border border-son-line bg-son-tint p-4 text-xs leading-5 text-son-dark", collapsed ? "hidden" : "hidden lg:block")}>
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Luồng an toàn
          </div>
          AI chỉ gợi ý, các bước duyệt và ký vẫn tách rõ theo vai trò.
        </div>
      </aside>
      <div className={cn("min-w-0", caseWorkspace && "col-start-2 row-start-1 flex h-full min-h-0 flex-col")}>
        <header className={cn("z-20 flex shrink-0 items-center justify-between gap-3 border-b border-rule bg-paper px-4 lg:px-6", caseWorkspace ? "py-2" : "sticky top-0 py-3.5")}>
          <div className={cn("min-w-0", caseWorkspace && "hidden sm:block")}>
            <p className="truncate text-sm font-semibold text-ink">{me.data?.full_name || me.data?.email || "Phiên làm việc"}</p>
            <p className="text-xs text-ink-3">{ROLE_LABEL[role] ?? role}</p>
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            {role === "HR" ? (
              <Button asChild>
                <Link to="/cases/new">Tạo hồ sơ</Link>
              </Button>
            ) : null}
            <Link
              className="relative inline-flex h-10 items-center gap-2 rounded-md border border-rule bg-paper px-3 text-sm text-ink transition-colors hover:bg-paper-2"
              to="/notifications"
              onClick={(event) => openPanel(event, "/notifications")}
              aria-haspopup={isCasePage ? "dialog" : undefined}
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
            <Button variant="ghost" size="sm" className="px-2 sm:px-3" onClick={() => void logout()}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only sm:not-sr-only">Đăng xuất</span>
            </Button>
          </div>
        </header>
        <main id="main" key={caseWorkspace ? caseMatch?.params.caseId : location.pathname} className={caseWorkspace ? "min-h-0 min-w-0 flex-1 overflow-hidden" : "page-fade px-4 py-5 lg:px-6 lg:py-6"}>
          <Outlet />
        </main>
      </div>
      <Sheet
        open={panel !== null}
        onOpenChange={(open) => { if (!open) setPanel(null); }}
        title={panel === "/dashboard" ? "Bảng điều khiển" : panel === "/guide" ? "Giới thiệu & hướng dẫn" : "Thông báo"}
        description="Xem thông tin và đóng bảng để tiếp tục hồ sơ đang mở."
        className={panel === "/notifications" ? "max-w-2xl" : "max-w-5xl"}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          panelTrigger.current?.focus();
        }}
      >
        {panel === "/dashboard" ? <DashboardPage /> : panel === "/notifications" ? <NotificationsPage /> : panel === "/guide" ? <GuidePage /> : null}
      </Sheet>
      <FloatingChat />
    </div>
  );
}
