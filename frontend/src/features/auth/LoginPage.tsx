import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  FileCheck2,
  Gavel,
  Layers3,
  LockKeyhole,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
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

const stats = [
  { value: "70-90%", label: "thời gian tổng hợp hồ sơ được rút ngắn" },
  { value: "4 lớp", label: "nhân sự, AI, pháp chế và người ký cùng kiểm soát" },
  { value: "100%", label: "căn cứ được truy vết trước khi ban hành" },
];

const capabilities = [
  {
    icon: MessageSquareText,
    title: "Hỏi đáp tình tiết",
    text: "Trợ lý dẫn dắt HR làm rõ sự kiện, mốc thời gian, người liên quan và tài liệu còn thiếu.",
    tone: "bg-sky-50 text-[#009ec1]",
  },
  {
    icon: FileCheck2,
    title: "Đọc căn cứ nội bộ",
    text: "Kết nối quy định, biên bản và chứng cứ để đề xuất hướng xử lý có thể kiểm tra lại.",
    tone: "bg-amber-50 text-amber-600",
  },
  {
    icon: ShieldCheck,
    title: "Chặn rủi ro quy trình",
    text: "Tách rõ bước đề xuất, rà soát pháp chế, duyệt quản lý và ký quyết định.",
    tone: "bg-emerald-50 text-emerald-600",
  },
];

const workflow = ["Tạo hồ sơ", "Bổ sung chứng cứ", "AI phân tích", "Pháp chế rà soát", "Ban hành quyết định"];

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
    <main id="main" className="min-h-screen bg-[#f3f8fb] text-[#0b2230]">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-4 md:px-8">
        <a className="flex items-center gap-3" href="#top" aria-label="HR Help">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#073642] text-sm font-bold text-white shadow-lg shadow-cyan-900/20">
            HR
          </span>
          <span>
            <span className="block text-sm font-bold leading-tight">HR Help</span>
            <span className="block text-xs text-[#5b7885]">AI kỷ luật lao động</span>
          </span>
        </a>
        <nav className="hidden items-center gap-6 text-sm font-medium text-[#496a77] md:flex" aria-label="Trang giới thiệu">
          <a className="hover:text-[#007c9d]" href="#about">Về giải pháp</a>
          <a className="hover:text-[#007c9d]" href="#services">Năng lực</a>
          <a className="hover:text-[#007c9d]" href="#workflow">Quy trình</a>
          <a className="hover:text-[#007c9d]" href="#contact">Liên hệ</a>
        </nav>
        <a className="rounded-full bg-[#073642] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0b4c5d]" href="#auth">
          Vào hệ thống
        </a>
      </header>

      <section id="top" className="mx-auto grid w-full max-w-7xl gap-8 px-5 pb-10 pt-4 md:px-8 lg:grid-cols-[minmax(0,1.03fr)_minmax(360px,0.97fr)] lg:items-center lg:pb-16">
        <div className="space-y-7">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-100 bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-[#008db1] shadow-sm">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Giải pháp AI thế hệ mới cho HR
          </div>
          <div>
            <h1 className="max-w-3xl text-4xl font-bold leading-[1.08] text-[#062b36] md:text-6xl">
              Xử lý kỷ luật lao động nhanh hơn, chặt chẽ hơn với AI
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-[#4a6975] md:text-lg">
              HR Help giúp đội nhân sự gom tình tiết, đọc căn cứ, truy vết chứng cứ và chuyển hồ sơ qua pháp chế, quản lý, người ký trong một luồng rõ ràng.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <a className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#009ec1] px-5 text-sm font-semibold text-white shadow-lg shadow-cyan-700/20 transition hover:bg-[#0089a8]" href="#auth">
              Bắt đầu xử lý hồ sơ
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
            <a className="inline-flex h-11 items-center justify-center rounded-xl border border-[#c9dfe6] bg-white px-5 text-sm font-semibold text-[#073642] transition hover:border-[#8fcbdc] hover:bg-[#eefbff]" href="#services">
              Xem năng lực AI
            </a>
          </div>
          <dl className="grid gap-3 sm:grid-cols-3">
            {stats.map((item) => (
              <div key={item.value} className="rounded-2xl border border-white bg-white/80 p-4 shadow-sm">
                <dt className="text-2xl font-bold text-[#073642]">{item.value}</dt>
                <dd className="mt-1 text-sm leading-5 text-[#5a7782]">{item.label}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="relative">
          <div className="overflow-hidden rounded-[2rem] border border-white bg-[#073642] shadow-2xl shadow-cyan-950/20">
            <div className="bg-[linear-gradient(135deg,#073642_0%,#0a6374_52%,#0aa6c7_100%)] p-5 text-white md:p-7">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">Trung tâm hồ sơ</p>
                  <h2 className="mt-2 text-2xl font-bold">Hồ sơ KL-2026-014</h2>
                </div>
                <span className="rounded-full bg-white/[0.15] px-3 py-1 text-xs font-semibold backdrop-blur">Đang phân tích</span>
              </div>
              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {["Tình tiết", "Căn cứ", "Rủi ro"].map((label, index) => (
                  <div key={label} className="rounded-2xl bg-white/[0.12] p-3 backdrop-blur">
                    <p className="text-xs text-cyan-100">{label}</p>
                    <p className="mt-2 text-2xl font-bold">{[12, 8, 3][index]}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white p-5 md:p-6">
              <div className="flex items-start gap-3 rounded-2xl border border-[#d8edf2] bg-[#f6fbfd] p-4">
                <Bot className="mt-1 h-5 w-5 text-[#009ec1]" aria-hidden="true" />
                <div>
                  <p className="font-semibold text-[#073642]">AI đề xuất mức xử lý</p>
                  <p className="mt-1 text-sm leading-6 text-[#587681]">
                    Thiếu xác nhận đã mời người lao động tham dự họp. Cần bổ sung biên bản trước khi chuyển pháp chế.
                  </p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {workflow.slice(0, 4).map((item, index) => (
                  <div key={item} className="flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#e7f7fb] text-xs font-bold text-[#008aaa]">{index + 1}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#e8f1f4]">
                      <div className="h-full rounded-full bg-[#009ec1]" style={{ width: `${index < 2 ? 100 : index === 2 ? 74 : 32}%` }} />
                    </div>
                    <span className="w-28 text-xs font-medium text-[#536f7a]">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="border-y border-[#dcecf1] bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-14 md:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#009ec1]">Về chúng tôi</p>
            <h2 className="mt-3 text-3xl font-bold text-[#073642]">Giúp doanh nghiệp xử lý hồ sơ nhạy cảm có căn cứ hơn</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <InfoBlock title="AI hỗ trợ, người quyết định" text="Mọi đề xuất đều giữ vai trò tham khảo, còn quyền duyệt và ký vẫn nằm ở đúng người phụ trách." />
            <InfoBlock title="Thực chiến theo quy trình HR" text="Luồng làm việc bám hồ sơ thật: sự kiện, chứng cứ, đánh giá rủi ro, rà soát và ban hành." />
          </div>
        </div>
      </section>

      <section id="services" className="mx-auto max-w-7xl px-5 py-14 md:px-8">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#009ec1]">Năng lực</p>
          <h2 className="mt-3 text-3xl font-bold text-[#073642]">Một hệ sinh thái cho hồ sơ kỷ luật lao động</h2>
          <p className="mt-3 text-sm leading-6 text-[#5a7782]">Lấy cảm hứng từ cách trang mẫu nhấn mạnh tự động hóa, nhưng tinh chỉnh cho nghiệp vụ pháp lý nội bộ và trải nghiệm dùng hằng ngày.</p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {capabilities.map((item) => (
            <article key={item.title} className="rounded-2xl border border-[#d8e9ee] bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-lg hover:shadow-cyan-900/10">
              <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${item.tone}`}>
                <item.icon className="h-6 w-6" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-[#073642]">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#5a7782]">{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="workflow" className="bg-[#062b36] text-white">
        <div className="mx-auto max-w-7xl px-5 py-14 md:px-8">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Quy trình</p>
              <h2 className="mt-3 text-3xl font-bold">Từ tình tiết đến quyết định trong một mạch</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-cyan-50/80">Mỗi bước có người chịu trách nhiệm, trạng thái rõ ràng và nhật ký để kiểm tra lại khi cần.</p>
          </div>
          <div className="mt-8 grid gap-3 md:grid-cols-5">
            {workflow.map((item, index) => (
              <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.08] p-4">
                <p className="text-sm font-bold text-cyan-200">0{index + 1}</p>
                <p className="mt-3 font-semibold">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="contact" className="mx-auto grid max-w-7xl gap-8 px-5 py-14 md:px-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#009ec1]">Liên hệ</p>
          <h2 className="mt-3 text-3xl font-bold text-[#073642]">Cần triển khai cho đội HR?</h2>
          <p className="mt-3 text-sm leading-6 text-[#5a7782]">Đăng nhập nếu bạn đã có tài khoản, hoặc tạo tài khoản thử nghiệm để bắt đầu kiểm tra luồng hồ sơ.</p>
          <div className="mt-6 space-y-3 text-sm text-[#4f6f7b]">
            <p className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-[#009ec1]" aria-hidden="true" /> Dữ liệu hồ sơ được phân quyền theo vai trò.</p>
            <p className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-[#009ec1]" aria-hidden="true" /> Có nhật ký thao tác cho quản trị.</p>
            <p className="flex items-center gap-2"><Gavel className="h-4 w-4 text-[#009ec1]" aria-hidden="true" /> Tách riêng pháp chế, quản lý và người ký.</p>
          </div>
        </div>

        <div id="auth" className="w-full rounded-3xl border border-[#d5e8ed] bg-white p-5 shadow-xl shadow-cyan-950/10 md:p-7">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">KHÔNG GIAN HỒ SƠ</p>
              <h2 className="mt-2 text-2xl font-bold text-[#073642]">{mode === "login" ? "Đăng nhập hệ thống" : "Tạo tài khoản"}</h2>
            </div>
            <Layers3 className="h-8 w-8 text-[#009ec1]" aria-hidden="true" />
          </div>
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

      <footer className="border-t border-[#dcecf1] bg-white px-5 py-6 text-sm text-[#5a7782] md:px-8">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 sm:flex-row">
          <p className="font-semibold text-[#073642]">HR Help</p>
          <p>AI đề xuất. Người quyết định.</p>
        </div>
      </footer>
    </main>
  );
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-[#d8e9ee] bg-[#f7fbfd] p-5">
      <h3 className="font-bold text-[#073642]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#5a7782]">{text}</p>
    </div>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-red-700">{message}</p>;
}
