import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { familyLabel } from "@/lib/labels";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/services/api";

const schema = z
  .object({
    case_code: z.string().trim().min(1, "Nhập mã hồ sơ.").max(100),
    employee_name: z.string().trim().min(1, "Nhập họ tên.").max(255),
    employee_code: z.string().trim().min(1, "Nhập mã nhân viên.").max(100),
    department: z.string().trim().max(255).optional(),
    position: z.string().trim().max(255).optional(),
    violation: z.string().trim().max(500).optional(),
    incident_date: z.string().min(1, "Chọn ngày xảy ra việc."),
    family: z.enum(["UNAUTHORIZED_ABSENCE", "LATE", "GENERAL"], { message: "Chọn nhóm vụ việc." }),
    description: z.string().trim().min(1, "Nhập mô tả.").max(8000),
  })
  .superRefine((values, ctx) => {
    if (composeDescription(values).length > 8000) {
      ctx.addIssue({ code: "custom", path: ["description"], message: "Mô tả sau khi ghép vượt 8000 ký tự." });
    }
  });

type CaseForm = z.infer<typeof schema>;

function composeDescription(values: Pick<CaseForm, "department" | "position" | "violation" | "description">): string {
  const lines = [
    values.department ? `Phòng ban: ${values.department}` : "",
    values.position ? `Chức danh: ${values.position}` : "",
    values.violation ? `Vi phạm: ${values.violation}` : "",
    values.description,
  ].filter(Boolean);
  return lines.join("\n");
}

export function NewCasePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<CaseForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      case_code: "",
      employee_name: "",
      employee_code: "",
      department: "",
      position: "",
      violation: "",
      incident_date: "",
      family: "GENERAL",
      description: "",
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <Link className="text-sm font-medium text-[#009EC1] underline" to="/cases">
          Danh sách hồ sơ
        </Link>
        <p className="mt-3 text-xs font-semibold tracking-[0.16em] text-[#009EC1]">HỒ SƠ MỚI</p>
        <h1 className="mt-1 text-2xl font-semibold text-[#073642]">Ghi nhận vụ việc</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Phòng ban, chức danh và mô tả vi phạm được ghi vào phần mô tả. API lưu một trường mô tả cùng ngày xảy ra việc.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Thông tin hồ sơ</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900" role="alert">
              {error}
            </p>
          ) : null}
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(async (values) => {
              setError(null);
              try {
                const created = await api.createCase({
                  case_code: values.case_code,
                  employee_code: values.employee_code,
                  employee_name: values.employee_name,
                  incident_date: values.incident_date,
                  family: values.family,
                  description: composeDescription(values),
                });
                navigate(`/cases/${created.case_id}`);
              } catch (err) {
                setError(errorMessage(err));
              }
            })}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Mã hồ sơ" error={form.formState.errors.case_code?.message}>
                <Input placeholder="CASE-001" {...form.register("case_code")} />
              </Field>
              <Field label="Ngày xảy ra" error={form.formState.errors.incident_date?.message}>
                <Input type="date" {...form.register("incident_date")} />
              </Field>
              <Field label="Nhóm vụ việc" error={form.formState.errors.family?.message}>
                <select
                  className="flex h-9 w-full rounded-md border border-[#d5e8ed] bg-white px-3 text-sm"
                  {...form.register("family")}
                >
                  <option value="UNAUTHORIZED_ABSENCE">{familyLabel("UNAUTHORIZED_ABSENCE")}</option>
                  <option value="LATE">{familyLabel("LATE")}</option>
                  <option value="GENERAL">{familyLabel("GENERAL")}</option>
                </select>
              </Field>
              <Field label="Nhân viên" error={form.formState.errors.employee_name?.message}>
                <Input placeholder="Nguyễn Văn A" {...form.register("employee_name")} />
              </Field>
              <Field label="Mã nhân viên" error={form.formState.errors.employee_code?.message}>
                <Input placeholder="EMP-001" {...form.register("employee_code")} />
              </Field>
              <Field label="Phòng ban">
                <Input placeholder="Engineering" {...form.register("department")} />
              </Field>
              <Field label="Chức danh">
                <Input placeholder="Software Engineer" {...form.register("position")} />
              </Field>
            </div>
            <Field label="Vi phạm" error={form.formState.errors.violation?.message}>
              <Input placeholder="Nghỉ không phép" {...form.register("violation")} />
            </Field>
            <Field label="Mô tả" error={form.formState.errors.description?.message}>
              <Textarea
                rows={6}
                placeholder="Nhân viên tự ý nghỉ 5 ngày không phép trong tháng 3..."
                {...form.register("description")}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" asChild>
                <Link to="/cases">Hủy</Link>
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "Đang tạo…" : "Tạo hồ sơ"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5 text-sm font-medium text-neutral-800">
      <span>{label}</span>
      {children}
      {error ? <span className="block text-xs font-normal text-red-700">{error}</span> : null}
    </label>
  );
}
