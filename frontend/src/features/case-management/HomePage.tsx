import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { rememberedCase } from "@/lib/session";

const schema = z.object({
  caseId: z.string().trim().uuid("Nhập đúng mã định danh hồ sơ."),
});

export function HomePage() {
  const navigate = useNavigate();
  const saved = rememberedCase();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { caseId: "" } });

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-wide text-ink-3">KHÔNG GIAN HỒ SƠ</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">Hồ sơ của tôi</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-2">
          Máy chủ chưa có danh sách hồ sơ. Tạo hồ sơ mới, mở lại hồ sơ trong phiên này, hoặc dán mã định danh.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Hồ sơ mới</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-ink-2">Ghi nhận nhân viên, ngày xảy ra việc và mô tả. Tình tiết được hỏi ở bước sau.</p>
            <Button asChild>
              <Link to="/cases/new">Tạo hồ sơ</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Mở hồ sơ đã có</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={form.handleSubmit((values) => navigate(`/cases/${values.caseId}`))}
            >
              <div className="space-y-1.5">
                <Label htmlFor="case-id">Mã định danh</Label>
                <Input id="case-id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" {...form.register("caseId")} />
                {form.formState.errors.caseId ? (
                  <p className="text-xs text-son-dark">{form.formState.errors.caseId.message}</p>
                ) : null}
              </div>
              <Button type="submit">Mở</Button>
            </form>
            {saved ? (
              <p className="mt-4 text-sm text-ink-2">
                Hồ sơ gần nhất trong phiên này:{" "}
                <Link className="font-medium text-ink underline" to={`/cases/${saved}`}>
                  {saved}
                </Link>
              </p>
            ) : (
              <p className="mt-4 text-sm text-ink-3">Chưa có hồ sơ nào trong phiên trình duyệt này.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
