import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { AppShell } from "@/app/layout/AppShell";
import { useAuth, useMe } from "@/app/providers";
import { StaffAccountsPage } from "@/features/accounts/StaffAccountsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { CasePage } from "@/features/case-management/CasePage";
import { CasesPage } from "@/features/case-management/CasesPage";
import { CaseWorkspace } from "@/features/case-management/CaseWorkspace";
import {
  AssessmentPage,
  DocumentsPage,
  EvidencePage,
  FactsPage,
  TimelinePage,
} from "@/features/case-management/CaseSections";
import { NewCasePage } from "@/features/case-management/NewCasePage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { DecisionPage } from "@/features/decision/DecisionPage";
import { ManagerReviewPage } from "@/features/decision/ManagerReviewPage";
import { SignerPage } from "@/features/decision/SignerPage";
import { SignerQueuePage } from "@/features/decision/SignerQueuePage";
import { AuditPage } from "@/features/audit/AuditPage";
import { AdminIngestionPage } from "@/features/admin-ingestion/AdminIngestionPage";
import { LegalCasePage } from "@/features/legal-review/LegalCasePage";
import { LegalQueuePage } from "@/features/legal-review/LegalQueuePage";
import { LegalReviewPage } from "@/features/legal-review/LegalReviewPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";

function RequireAuth() {
  const { auth } = useAuth();
  if (!auth) return <Navigate to="/login" replace />;
  return <AppShell />;
}

function GuestOnly() {
  const { auth } = useAuth();
  if (auth) return <Navigate to="/dashboard" replace />;
  return <LoginPage />;
}

function useRole(): { role: string; loading: boolean } {
  const { auth } = useAuth();
  const me = useMe();
  const role = me.data?.role || auth?.roles?.[0] || "";
  return { role, loading: Boolean(auth) && me.isLoading && !role };
}

function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { role, loading } = useRole();
  if (loading) return <p className="text-sm text-ink-3">Đang kiểm tra quyền…</p>;
  if (!roles.includes(role)) return <Navigate to="/dashboard" replace />;
  return children;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<GuestOnly />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route
          path="/cases"
          element={
            <RequireRole roles={["HR", "MANAGER", "SIGNER", "ADMIN"]}>
              <CasesPage />
            </RequireRole>
          }
        />
        <Route
          path="/cases/new"
          element={
            <RequireRole roles={["HR"]}>
              <NewCasePage />
            </RequireRole>
          }
        />
        <Route
          path="/cases/:caseId"
          element={
            <RequireRole roles={["HR", "MANAGER", "SIGNER", "ADMIN"]}>
              <CaseWorkspace />
            </RequireRole>
          }
        >
          <Route index element={null} />
          <Route path="overview" element={<CasePage />} />
          <Route path="conversation" element={null} />
          <Route path="facts" element={<FactsPage />} />
          <Route path="evidence" element={<EvidencePage />} />
          <Route path="assessment" element={<AssessmentPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="decision" element={<DecisionPage />} />
          <Route path="legal-review" element={<LegalReviewPage />} />
        </Route>
        <Route
          path="/legal-review"
          element={
            <RequireRole roles={["LEGAL"]}>
              <LegalQueuePage />
            </RequireRole>
          }
        />
        <Route
          path="/legal-review/:caseId"
          element={
            <RequireRole roles={["LEGAL"]}>
              <LegalCasePage />
            </RequireRole>
          }
        />
        <Route
          path="/manager"
          element={
            <RequireRole roles={["MANAGER"]}>
              <StaffAccountsPage />
            </RequireRole>
          }
        />
        <Route
          path="/manager/:caseId"
          element={
            <RequireRole roles={["MANAGER"]}>
              <ManagerReviewPage />
            </RequireRole>
          }
        />
        <Route
          path="/decisions"
          element={
            <RequireRole roles={["SIGNER", "ADMIN"]}>
              <SignerQueuePage />
            </RequireRole>
          }
        />
        <Route
          path="/decisions/:caseId"
          element={
            <RequireRole roles={["SIGNER", "ADMIN"]}>
              <SignerPage />
            </RequireRole>
          }
        />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route
          path="/audit"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AuditPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/ingestion"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminIngestionPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
