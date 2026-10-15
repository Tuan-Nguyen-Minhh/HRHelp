import { BookOpen, ClipboardList, FileCheck2, Files, Gavel, History, Info, ShieldCheck } from "lucide-react";

export const CASE_SECTIONS = [
  { path: "overview", label: "Thông tin hồ sơ", icon: Info },
  { path: "facts", label: "Tình tiết vi phạm", icon: ClipboardList },
  { path: "evidence", label: "Căn cứ đối chiếu", icon: BookOpen },
  { path: "assessment", label: "Đánh giá và biên bản", icon: FileCheck2 },
  { path: "documents", label: "Văn bản", icon: Files },
  { path: "timeline", label: "Dòng thời gian", icon: History },
  { path: "decision", label: "Phiếu xử lý", icon: Gavel },
  { path: "legal-review", label: "Gói duyệt pháp chế", icon: ShieldCheck },
] as const;
