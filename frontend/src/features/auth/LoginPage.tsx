import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/app/providers";
import { errorMessage } from "@/services/api";

const loginSchema = z.object({
  email: z.string().trim().email("Email không hợp lệ."),
  password: z.string().min(8, "Mật khẩu cần ít nhất 8 ký tự."),
});

const registerSchema = loginSchema.extend({
  full_name: z.string().trim().max(255).optional(),
  role: z.enum(["HR", "MANAGER", "LEGAL"]),
  password: z
    .string()
    .min(8, "Mật khẩu cần ít nhất 8 ký tự.")
    .refine((value) => new TextEncoder().encode(value).length <= 72, "Mật khẩu dài quá 72 byte."),
});

type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;

export function LoginPage() {
  const { login, register: registerAccount } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const registerForm = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", full_name: "", role: "HR" },
  });
  const busy = loginForm.formState.isSubmitting || registerForm.formState.isSubmitting;

  return (
    <main id="main" className="grid min-h-screen bg-[#f4fafb] lg:grid-cols-[1.05fr_0.95fr]">
      <section className="hidden bg-[#073642] px-12 py-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div>
          <p className="text-xs font-semibold tracking-[0.18em] text-[#7fd3e6]">HR HELP</p>
          <h1 className="mt-6 max-w-md text-3xl font-semibold leading-tight">Kỷ luật lao động, có căn cứ và có người quyết.</h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-[#d7eef3]">
            AI đề xuất từ tình tiết và văn bản đã lưu. Nhân sự, pháp chế và người ký mới chốt từng bước.
          </p>
        </div>
        <ol className="space-y-3 text-sm text-[#d7eef3]">
          <li>1. Mở hồ sơ và làm rõ tình tiết</li>
          <li>2. Đọc căn cứ, biên bản và rủi ro</li>
          <li>3. Gửi pháp chế, rồi người ký ban hành</li>
        </ol>
      </section>
      <section className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-[#d5e8ed] bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">ĐĂNG NHẬP</p>
          <h2 className="mt-2 text-xl font-semibold text-[#073642]">{mode === "login" ? "Vào không gian hồ sơ" : "Tạo tài khoản"}</h2>
          {error ? (
            <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900" role="alert">
              {error}
            </p>
          ) : null}
          {mode === "login" ? (
            <form
              className="mt-5 space-y-4"
              onSubmit={loginForm.handleSubmit(async (values) => {
                setError(null);
                try {
                  await login(values.email, values.password);
                } catch (err) {
                  setError(errorMessage(err));
                }
              })}
            >
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" autoComplete="email" {...loginForm.register("email")} />
                <FieldError message={loginForm.formState.errors.email?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Mật khẩu</Label>
                <Input id="password" type="password" autoComplete="current-password" {...loginForm.register("password")} />
                <FieldError message={loginForm.formState.errors.password?.message} />
              </div>
              <Button className="w-full" type="submit" disabled={busy}>
                {busy ? "Đang xử lý…" : "Đăng nhập"}
              </Button>
            </form>
          ) : (
            <form
              className="mt-5 space-y-4"
              onSubmit={registerForm.handleSubmit(async (values) => {
                setError(null);
                try {
                  await registerAccount({
                    email: values.email,
                    password: values.password,
                    full_name: values.full_name || undefined,
                    role: values.role,
                  });
                } catch (err) {
                  setError(errorMessage(err));
                }
              })}
            >
              <div className="space-y-1.5">
                <Label htmlFor="reg-email">Email</Label>
                <Input id="reg-email" type="email" autoComplete="email" {...registerForm.register("email")} />
                <FieldError message={registerForm.formState.errors.email?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="full-name">Họ và tên</Label>
                <Input id="full-name" autoComplete="name" {...registerForm.register("full_name")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="role">Vai trò</Label>
                <select
                  id="role"
                  className="flex h-9 w-full rounded-md border border-[#d5e8ed] bg-white px-3 text-sm"
                  {...registerForm.register("role")}
                >
                  <option value="HR">Nhân sự</option>
                  <option value="MANAGER">Quản lý</option>
                  <option value="LEGAL">Pháp chế</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-password">Mật khẩu</Label>
                <Input id="reg-password" type="password" autoComplete="new-password" {...registerForm.register("password")} />
                <FieldError message={registerForm.formState.errors.password?.message} />
              </div>
              <Button className="w-full" type="submit" disabled={busy}>
                {busy ? "Đang xử lý…" : "Tạo tài khoản"}
              </Button>
            </form>
          )}
          <p className="mt-4 text-sm text-neutral-600">
            {mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
            <button
              className="font-medium text-[#009EC1] underline"
              type="button"
              onClick={() => {
                setError(null);
                setMode(mode === "login" ? "register" : "login");
              }}
            >
              {mode === "login" ? "Tạo tài khoản" : "Đăng nhập"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-red-700">{message}</p>;
}
