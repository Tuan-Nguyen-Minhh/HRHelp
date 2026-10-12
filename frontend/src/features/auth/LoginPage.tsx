import { zodResolver } from "@hookform/resolvers/zod";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAuth } from "@/app/providers";
import { errorMessage } from "@/services/api";
import "./landing.css";

gsap.registerPlugin(ScrollTrigger);

const MOTION_KEY = "hrhelp:motion";

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

const ROLE_LABEL: Record<string, string> = { HR: "Nhân sự", MANAGER: "Quản lý", LEGAL: "Pháp chế" };

const CHAT_ROLE_LABEL: Record<string, string> = { user: "Nhân sự", assistant: "Trợ lý", system: "Trạng thái" };

const FLOW_READS = [
  "Hồ sơ được <b>HR mở</b> và 12 mục tình tiết được khẳng định trước khi chuyển bước.",
  "Agent đọc tình tiết và <b>đối chiếu 8 điều khoản</b> còn hiệu lực tại thời điểm xảy ra sự việc.",
  "Pháp chế mở gói duyệt và <b>không được sửa</b> tình tiết, mức xử lý hay trích dẫn.",
  "Quyết định được <b>người có thẩm quyền ký</b>, kèm nhật ký toàn bộ bước trước đó.",
];

export function LoginPage() {
  const { login, register: registerAccount } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [lite, setLite] = useState(() =>
    typeof localStorage !== "undefined" ? localStorage.getItem(MOTION_KEY) === "lite" : false,
  );

  const rootRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const factsRef = useRef<HTMLDivElement>(null);
  const citesRef = useRef<HTMLDivElement>(null);
  const progRef = useRef<HTMLElement>(null);
  const pctRef = useRef<HTMLSpanElement>(null);
  const fcRef = useRef<HTMLSpanElement>(null);
  const ccRef = useRef<HTMLSpanElement>(null);
  const flowReadRef = useRef<HTMLDivElement>(null);
  const chatApi = useRef<{ replay: () => void } | null>(null);

  const loginForm = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const registerForm = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", full_name: "", role: "HR" },
  });
  const busy = loginForm.formState.isSubmitting || registerForm.formState.isSubmitting;

  useEffect(() => {
    const scope = rootRef.current;
    if (!scope) return;
    const cleanups: Array<() => void> = [];
    const reduced = localStorage.getItem(MOTION_KEY) === "lite";

    const ctx = gsap.context(() => {
      if (reduced) {
        scope.querySelectorAll(".rv").forEach((el) => gsap.set(el, { opacity: 1, y: 0 }));
        scope.querySelectorAll("[data-depth]").forEach((el) => gsap.set(el, { yPercent: 0 }));
        scope.querySelectorAll("#flowRow .fl").forEach((el, i) =>
          el.classList.toggle("on", i === 0),
        );
        if (flowReadRef.current) {
          flowReadRef.current.innerHTML =
            "Hồ sơ đi qua đủ bốn lớp. Mỗi lớp có người chịu trách nhiệm riêng và đều ghi vào nhật ký.";
        }
        const rail = scope.querySelector("#railFill");
        if (rail) gsap.set(rail, { scaleX: 1 });
      } else {
        /* Section reveals, staggered per group */
        scope.querySelectorAll("section, .hero").forEach((sec) => {
          const kids = Array.from(sec.querySelectorAll(".rv"));
          if (!kids.length) return;
          const hero = sec.classList.contains("hero");
          kids.forEach((k) => gsap.set(k, { opacity: 0, y: hero ? 26 : 16 }));
          gsap.to(kids, {
            opacity: 1,
            y: 0,
            duration: hero ? 0.9 : 0.62,
            ease: "power2.out",
            stagger: hero ? 0.1 : 0.07,
            scrollTrigger: { trigger: sec, start: "top 86%", once: true },
          });
        });

        /* 4-layer auto-cycle */
        const flowRow = scope.querySelector("#flowRow");
        if (flowRow) {
          const layers = Array.from(flowRow.querySelectorAll(".fl"));
          const setActive = (i: number) => {
            layers.forEach((el, n) => el.classList.toggle("on", n === i));
            if (flowReadRef.current) flowReadRef.current.innerHTML = FLOW_READS[i];
          };
          let flowTl: gsap.core.Timeline | null = null;
          const startFlow = () => {
            if (flowTl) return;
            setActive(0);
            const step = 2.2;
            flowTl = gsap.timeline({ repeat: -1, repeatDelay: 1.2 });
            layers.forEach((_, i) => {
              flowTl?.call(() => setActive(i));
              flowTl?.to({}, { duration: step });
            });
            flowTl.pause();
            const fio = new IntersectionObserver(([e]) => {
              if (!flowTl) return;
              if (e.isIntersecting) flowTl.play();
              else flowTl.pause();
            });
            const pin = scope.querySelector(".pinwrap");
            if (pin) fio.observe(pin);
            cleanups.push(() => fio.disconnect());
            flowTl.play();
          };
          ScrollTrigger.create({
            trigger: ".pinwrap",
            start: "top 75%",
            once: true,
            onEnter: startFlow,
          });
        }

        /* Impact cards auto-cycle */
        const impactCells = Array.from(scope.querySelectorAll(".impact .cell"));
        if (impactCells.length) {
          let impactTl: gsap.core.Timeline | null = null;
          const startImpact = () => {
            if (impactTl) return;
            const step = 2.2;
            impactTl = gsap.timeline({ repeat: -1, repeatDelay: 1.0 });
            impactCells.forEach((_, i) => {
              impactTl?.call(() => {
                impactCells.forEach((c, n) => c.classList.toggle("on", n === i));
              });
              impactTl?.to({}, { duration: step });
            });
            impactTl.pause();
            const iio = new IntersectionObserver(([e]) => {
              if (!impactTl) return;
              if (e.isIntersecting) impactTl.play();
              else impactTl.pause();
            });
            const impact = scope.querySelector(".impact");
            if (impact) iio.observe(impact);
            cleanups.push(() => iio.disconnect());
            impactTl.play();
          };
          ScrollTrigger.create({
            trigger: ".impact",
            start: "top 80%",
            once: true,
            onEnter: startImpact,
          });
        }

        /* Scroll progress rail */
        const rail = scope.querySelector("#railFill");
        if (rail) {
          gsap.to(rail, {
            scaleX: 1,
            ease: "none",
            scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 0.3 },
          });
        }

        /* Parallax on decorative layers only */
        scope.querySelectorAll("[data-depth]").forEach((el) => {
          const d = parseFloat((el as HTMLElement).dataset.depth ?? "0");
          const host = el.closest("section, header");
          if (!host) return;
          gsap.to(el, {
            yPercent: d,
            ease: "none",
            scrollTrigger: { trigger: host, start: "top bottom", end: "bottom top", scrub: 0.6 },
          });
        });

        /* Card hover */
        scope.querySelectorAll(".chain a").forEach((el) => {
          const xTo = gsap.quickTo(el, "x", { duration: 0.32, ease: "power2.out" });
          const enter = () => xTo(10);
          const leave = () => xTo(0);
          el.addEventListener("pointerenter", enter);
          el.addEventListener("pointerleave", leave);
          cleanups.push(() => {
            el.removeEventListener("pointerenter", enter);
            el.removeEventListener("pointerleave", leave);
          });
        });
        scope.querySelectorAll(".cell").forEach((el) => {
          const num = el.querySelector(".v");
          if (!num) return;
          const sTo = gsap.quickTo(num, "scale", { duration: 0.34, ease: "power2.out" });
          const enter = () => sTo(1.06);
          const leave = () => sTo(1);
          el.addEventListener("pointerenter", enter);
          el.addEventListener("pointerleave", leave);
          cleanups.push(() => {
            el.removeEventListener("pointerenter", enter);
            el.removeEventListener("pointerleave", leave);
          });
        });

        /* Magnetic focal CTA */
        const focal = scope.querySelector(".hero .btn.p");
        if (focal) {
          const mx = gsap.quickTo(focal, "x", { duration: 0.45, ease: "elastic.out(1,0.4)" });
          const my = gsap.quickTo(focal, "y", { duration: 0.45, ease: "elastic.out(1,0.4)" });
          const onMove = (e: Event) => {
            const ev = e as PointerEvent;
            const r = (focal as HTMLElement).getBoundingClientRect();
            mx((ev.clientX - (r.left + r.width / 2)) * 0.22);
            my((ev.clientY - (r.top + r.height / 2)) * 0.3);
          };
          const onOut = () => {
            mx(0);
            my(0);
          };
          focal.addEventListener("pointermove", onMove);
          focal.addEventListener("pointerleave", onOut);
          cleanups.push(() => {
            focal.removeEventListener("pointermove", onMove);
            focal.removeEventListener("pointerleave", onOut);
          });
        }
      }
    }, scope);

    /* Live chat loop (runs in both modes; static end state when lite) */
    const chat = chatRef.current;
    const factsEl = factsRef.current;
    const citesEl = citesRef.current;
    const prog = progRef.current;
    const pct = pctRef.current;
    let chatTl: gsap.core.Timeline | null = null;

    const setCount = (ref: React.RefObject<HTMLSpanElement | null>, v: string) => {
      if (ref.current) ref.current.textContent = v;
    };

    function bubble(role: string, text: string, time: string): HTMLElement | null {
      if (!chat) return null;
      const doc = chat.ownerDocument;
      const el = doc.createElement("div");
      el.className = `msg ${role}`;
      const head = doc.createElement("div");
      head.className = "mh";
      const who = doc.createElement("span");
      who.textContent = CHAT_ROLE_LABEL[role] ?? role;
      const when = doc.createElement("span");
      when.textContent = time;
      head.append(who, when);
      const body = doc.createElement("div");
      body.className = "mb";
      body.innerHTML = text;
      el.append(head, body);
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;
      return el;
    }

    function typingOn() {
      if (!chat) return;
      const t = chat.ownerDocument.createElement("div");
      t.className = "typing";
      t.innerHTML = "<i></i><i></i><i></i>";
      chat.appendChild(t);
    }
    function typingOff() {
      chat?.querySelectorAll(".typing").forEach((x) => x.remove());
    }

    function addFact(txt: string, warn?: boolean) {
      if (!factsEl) return null;
      const doc = factsEl.ownerDocument;
      const f = doc.createElement("div");
      f.className = warn ? "fact warn" : "fact";
      const mk = doc.createElement("span");
      mk.className = "mk";
      mk.textContent = "✓";
      const label = doc.createElement("span");
      label.textContent = txt;
      f.append(mk, label);
      factsEl.appendChild(f);
      setCount(fcRef, String(factsEl.children.length));
      return f;
    }

    function addCite(html: string, cls?: string) {
      if (!citesEl) return null;
      const doc = citesEl.ownerDocument;
      const c = doc.createElement("div");
      c.className = cls ? `cite ${cls}` : "cite";
      c.innerHTML = html;
      citesEl.appendChild(c);
      setCount(ccRef, String(citesEl.children.length));
      return c;
    }

    function resetChat() {
      if (chat) chat.innerHTML = "";
      if (factsEl) factsEl.innerHTML = "";
      if (citesEl) citesEl.innerHTML = "";
      if (prog) prog.style.width = "0%";
      if (pct) pct.textContent = "0%";
      setCount(fcRef, "0");
      setCount(ccRef, "0");
    }

    function buildChat() {
      if (chatTl) chatTl.kill();
      resetChat();
      const E = reduced ? 0.001 : 0.28;
      const H = reduced ? 0.01 : 0.4;
      const say = (role: string, text: string, time: string, hold?: number) => {
        if (!chatTl) return;
        chatTl.add(() => {
          const el = bubble(role, text, time);
          if (el) gsap.fromTo(el, { opacity: 0 }, { opacity: 1, duration: E, ease: "power2.out" });
        });
        chatTl.to({}, { duration: hold ?? H });
      };
      const showFact = (txt: string, warn?: boolean) => {
        if (!chatTl) return;
        chatTl.add(() => {
          const f = addFact(txt, warn);
          if (f) gsap.fromTo(f, { opacity: 0 }, { opacity: 1, duration: E * 0.7, ease: "power2.out" });
        });
        chatTl.to({}, { duration: H * 0.8 });
      };
      const showCite = (html: string, cls?: string) => {
        if (!chatTl) return;
        chatTl.add(() => {
          const c = addCite(html, cls);
          if (c) gsap.fromTo(c, { opacity: 0 }, { opacity: 1, duration: E * 0.7, ease: "power2.out" });
        });
        chatTl.to({}, { duration: H * 0.8 });
      };
      const pctTo = (v: number) => {
        if (!chatTl || !prog) return;
        chatTl.to(prog, { width: `${v}%`, duration: reduced ? 0.001 : 0.4, ease: "power2.out" }, "<");
        chatTl.add(() => {
          if (pct) pct.textContent = `${v}%`;
        });
      };

      chatTl = gsap.timeline({ repeat: -1, repeatDelay: 1.5 });
      chatTl.add(() => {
        resetChat();
        typingOn();
      }, 0);
      chatTl.to({}, { duration: H });
      chatTl.add(typingOff);
      say(
        "assistant",
        "Tôi thấy hồ sơ ghi nhận nhân viên vắng mặt. Bạn xác nhận ngày bắt đầu và ngày kết thúc là ngày nào?",
        "09:41",
      );
      say("user", "Từ 12/09 đến 15/09, không có lý do chính đáng.", "09:41", H * 0.6);
      chatTl.add(typingOn);
      pctTo(30);
      showFact("Thời gian: 12/09 – 15/09/2026");
      showFact("Lý do: không chính đáng");
      chatTl.add(typingOff);
      say("assistant", "Đã ghi nhận. Có tài liệu nào chứng minh đã thông báo trước với quản lý không?", "09:41");
      say("user", "Không có. Nhân viên khai chỉ gọi điện cho kế toán trưởng.", "09:42", H * 0.6);
      showFact("Thông báo trước: không có", true);
      pctTo(62);
      showCite("<b>Điều 21</b> · BLDS 2019");
      showCite("<b>Điều 40</b> · NQ 12/2024");
      showCite("<b>Điều 12</b> · NQ 12/2024", "warn");
      chatTl.add(typingOn);
      pctTo(88);
      chatTl.to({}, { duration: H });
      chatTl.add(typingOff);
      say(
        "assistant",
        "Mức xử lý ở Điều 12 cần HR xác nhận trước khi tôi dự thảo biên bản. Mức nào đúng với nội quy công ty?",
        "09:42",
      );
      pctTo(100);
      say(
        "system",
        "Đã đủ căn cứ. Hồ sơ #KL-2026-014 chờ pháp chế rà soát. AI không tự ban hành quyết định.",
        "09:42",
        H * 0.4,
      );
      return chatTl;
    }

    const chatTimeline = buildChat();
    if (reduced) {
      chatTimeline.progress(1);
      scope.querySelectorAll("#chat .msg, #facts .fact, #cites .cite").forEach((el) =>
        gsap.set(el, { opacity: 1 }),
      );
    } else {
      const demo = scope.querySelector("#demo");
      if (demo) {
        const io = new IntersectionObserver(([e]) => {
          if (!chatTl) return;
          if (e.isIntersecting) chatTl.play();
          else chatTl.pause();
        });
        io.observe(demo);
        cleanups.push(() => io.disconnect());
      }
    }
    chatApi.current = {
      replay: () => {
        buildChat()?.play(0);
      },
    };

    return () => {
      cleanups.forEach((fn) => fn());
      ctx.revert();
      resetChat();
      chatApi.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleMotion = () => {
    const next = lite ? "full" : "lite";
    localStorage.setItem(MOTION_KEY, next);
    setLite(next === "lite");
    window.location.reload();
  };

  const switchMode = (next: "login" | "register") => {
    setError(null);
    loginForm.clearErrors();
    registerForm.clearErrors();
    setMode(next);
  };

  return (
    <div ref={rootRef} className="landing-root">
      <div className="rail" aria-hidden="true">
        <i id="railFill" />
      </div>

      <nav className="nav">
        <div className="in wrap">
          <a className="logo" href="#top" style={{ textDecoration: "none", color: "inherit" }}>
            <span className="mark">
              HR
              <br />
              HELP
            </span>
            <span className="tx">
              <b>HR Help</b>
              <span className="sub">Trợ lý chính sách nhân sự</span>
            </span>
          </a>
          <div className="links">
            <a href="#demo">Xem hoạt động</a>
            <a href="#trace">Căn cứ</a>
            <a href="#control">Quyền kiểm soát</a>
            <a href="#impact">Tác động</a>
          </div>
          <div className="cta">
            <a className="btn s" href="#start" style={{ height: 38, padding: "0 16px", fontSize: 13.5 }}>
              Vào hệ thống
            </a>
            <button type="button" className="motiontoggle" aria-pressed={!lite} onClick={toggleMotion}>
              <span className="mt-ic" aria-hidden="true" />
              <span className="mt-tx">{lite ? "Hiệu ứng: Nhẹ" : "Hiệu ứng: Đầy đủ"}</span>
            </button>
          </div>
        </div>
      </nav>

      <header className="hero" id="top">
        <div className="gridlayer" data-depth="14" />
        <div className="glowblob one" data-depth="26" />
        <div className="glowblob two" data-depth="-18" />
        <div className="in wrap">
          <div>
            <div className="pill rv">
              <i className="dot" />
              AI đề xuất · Người quyết định
            </div>
            <h1 className="headline">
              Xử lý kỷ luật lao động
              <br />
              <em>nhanh hơn, chắc chắn hơn.</em>
            </h1>
            <p className="lead rv">
              HR Help đọc tình tiết, dẫn văn bản điều luật còn hiệu lực, đối chiếu chứng cứ và chuyển hồ
              sơ qua pháp chế, quản lý, người ký — trong một luồng có nhật ký đầy đủ.
            </p>
            <div className="acts rv">
              <a className="btn p" href="#demo">
                Xem hồ sơ chạy thật
              </a>
              <a className="btn s" href="#start">
                Tạo tài khoản thử
              </a>
            </div>
            <div className="proof rv">
              <div>
                <div className="v">Truy vết căn cứ</div>
                <div className="k">mọi kết luận đều trỏ về điều khoản cụ thể</div>
              </div>
              <div>
                <div className="v">4 lớp</div>
                <div className="k">nhân sự, AI, pháp chế và người ký</div>
              </div>
              <div>
                <div className="v">Người quyết định</div>
                <div className="k">AI gợi ý, người duyệt và ký</div>
              </div>
            </div>
          </div>

          <div className="demo rv" id="demo">
            <div className="hd">
              <div className="l">
                <span>Hồ sơ KL-2026-014</span>
              </div>
              <div className="live">
                <i />
                AGENT ĐANG XỬ LÝ
              </div>
            </div>
            <div className="screen">
              <div className="chathead">
                <div className="ava">
                  <span>§</span>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="t">Agent pháp chế</div>
                  <div className="s">Hỏi phần còn thiếu, gợi ý căn cứ và giữ hội thoại dễ tra lại.</div>
                </div>
                <div className="pills">
                  <span className="pill-ok">
                    <i />
                    Đang sẵn sàng
                  </span>
                  <span className="pill-ct">Có ngữ cảnh hồ sơ</span>
                </div>
              </div>
              <div className="split">
                <div>
                  <div className="chatbody" id="chat" ref={chatRef} />
                  <div className="suggest">
                    <span>Tóm tắt tình tiết</span>
                    <span>Cần bổ sung chứng cứ gì?</span>
                    <span>Kiểm tra rủi ro quy trình</span>
                  </div>
                </div>
                <div className="side">
                  <div className="meter">
                    <div className="lbl">
                      <span>Tiến độ</span>
                      <span id="pct" ref={pctRef}>
                        0%
                      </span>
                    </div>
                    <div className="bar">
                      <i id="prog" ref={progRef} />
                    </div>
                  </div>
                  <div>
                    <div className="meter" style={{ marginBottom: 6 }}>
                      <div className="lbl" style={{ margin: 0 }}>
                        <span>Tình tiết đã xác nhận</span>
                        <span id="fc" ref={fcRef}>
                          0
                        </span>
                      </div>
                    </div>
                    <div className="facts" id="facts" ref={factsRef} />
                  </div>
                  <div>
                    <div className="meter" style={{ marginBottom: 6 }}>
                      <div className="lbl" style={{ margin: 0 }}>
                        <span>Căn cứ</span>
                        <span id="cc" ref={ccRef}>
                          0
                        </span>
                      </div>
                    </div>
                    <div className="cites" id="cites" ref={citesRef} />
                  </div>
                </div>
              </div>
              <div className="composer">
                <div className="fake">Nhập câu trả lời của bạn…</div>
                <div className="send">Gửi</div>
              </div>
            </div>
            <div className="replay">
              <button type="button" onClick={() => chatApi.current?.replay()}>
                ↻ Chạy lại
              </button>
              <span className="hint">Minh hoạ bằng dữ liệu mẫu</span>
            </div>
          </div>
        </div>
      </header>

      <section className="band" id="trace">
        <div className="in wrap">
          <div className="sec-head rv">
            <div className="idx">01 / 05</div>
            <div className="kicker">Căn cứ truy vết</div>
            <h2>Mọi kết luận đều dẫn được về điều luật cụ thể.</h2>
            <p>
              Không có &quot;AI nói vậy&quot;. Từng mức xử lý đều trỏ về điều khoản cụ thể, kèm hiệu lực
              văn bản tại thời điểm xảy ra sự việc.
            </p>
          </div>
          <div className="trace">
            <div className="cite-big rv">
              <div className="tagline">Căn cứ chính</div>
              <h4>Điều 21 — Bộ luật Lao động 2019</h4>
              <div className="art">Hiệu lực từ 01/01/2021 · Áp dụng cho sự kiện ngày 12/09/2026</div>
              <blockquote>
                &quot;Xử lý hành vi trốn trốn làm việc hoặc không chấp hành nhiệm vụ công việc…&quot;
              </blockquote>
              <div className="foot">
                <span>Tổng hợp từ các bộ luật hiện hành</span>
                <span>
                  Độ tin cậy: <b style={{ color: "#332C22" }}>Đã kiểm chứng</b>
                </span>
              </div>
            </div>
            <div>
              <div className="chain">
                <a
                  className="rv"
                  href="#trace"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="n">21</span>
                  <span>
                    <span className="t">Điều 21 — Bộ luật Lao động 2019</span>
                    <span className="s">Xử lý trốn trốn làm việc</span>
                  </span>
                  <span className="tag ok">ÁP DỤNG</span>
                </a>
                <a
                  className="rv"
                  href="#trace"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="n">40</span>
                  <span>
                    <span className="t">Điều 40 — Nội quy lao động 12/2024</span>
                    <span className="s">Thời hạn báo trước khi nghỉ</span>
                  </span>
                  <span className="tag ok">ÁP DỤNG</span>
                </a>
                <a
                  className="rv"
                  href="#trace"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="n">12</span>
                  <span>
                    <span className="t">Điều 12 — Nội quy lao động 12/2024</span>
                    <span className="s">Mức xử lý vi phạm vắng mặt</span>
                  </span>
                  <span className="tag at">CẦN XÁC NHẬN</span>
                </a>
                <a
                  className="rv"
                  href="#trace"
                  onClick={(e) => e.preventDefault()}
                >
                  <span className="n">6</span>
                  <span>
                    <span className="t">Điều 6 — Nghị định 12/2022</span>
                    <span className="s">Xử phạt hành chính — tham chiếu rủi ro</span>
                  </span>
                  <span className="tag rf">THAM CHIẾU</span>
                </a>
              </div>
              <p className="rv" style={{ marginTop: 18, fontSize: 14, color: "var(--ink-3)" }}>
                Bấm vào từng căn cứ để mở toàn văn, điều khoản liên quan và văn bản sửa đổi.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="band dark pinwrap" id="control">
        <div className="deco" data-depth="-10" />
        <div className="in wrap">
          <div className="flow">
            <div className="sec-head rv">
              <div className="idx">02 / 05</div>
              <div className="kicker">Ranh giới trách nhiệm</div>
              <h2>
                Một hồ sơ đi qua bốn lớp.
                <br />
                Không lớp nào tự quyết.
              </h2>
              <p>Đây là điều kiện để đưa công cụ này vào quy trình kỷ luật thật.</p>
            </div>
            <div className="stage">
              <div className="row" id="flowRow">
                <div className="fl" data-i="0">
                  <div className="n">Lớp 01</div>
                  <h4>Thu thập tình tiết</h4>
                  <p>
                    HR mở hồ sơ, hội thoại làm rõ sự kiện, thời điểm, người liên quan. Mọi mục được khẳng
                    định trước khi chuyển bước.
                  </p>
                  <div className="who">NGƯỜI DÙNG · HR</div>
                </div>
                <div className="fl" data-i="1">
                  <div className="n">Lớp 02</div>
                  <h4>Phân tích và đối chiếu</h4>
                  <p>
                    Agent đọc tình tiết, truy vấn văn bản còn hiệu lực, so khớp điều khoản, đánh dấu chỗ
                    thiếu căn cứ.
                  </p>
                  <div className="who">AI · GỢI Ý</div>
                </div>
                <div className="fl" data-i="2">
                  <div className="n">Lớp 03</div>
                  <h4>Rà soát pháp chế</h4>
                  <p>
                    Pháp chế duyệt hoặc từ chối gói hồ sơ. Không được sửa tình tiết, mức xử lý hay trích
                    dẫn.
                  </p>
                  <div className="who">NGƯỜI DÙNG · PHÁP CHẾ</div>
                </div>
                <div className="fl" data-i="3">
                  <div className="n">Lớp 04</div>
                  <h4>Ban hành quyết định</h4>
                  <p>
                    Quản lý và người ký chịu trách nhiệm cuối cùng. Xuất biên bản kèm nhật ký đầy đủ.
                  </p>
                  <div className="who">NGƯỜI DÙNG · KÝ</div>
                </div>
              </div>
            </div>
            <div className="flowread" id="flowRead" ref={flowReadRef} />
          </div>
        </div>
      </section>

      <section className="band" id="impact">
        <div className="in wrap">
          <div className="sec-head rv">
            <div className="idx">03 / 05</div>
            <div className="kicker">Tác động vận hành</div>
            <h2>Thời gian nên dùng để chuyển giao, không phải để tìm căn cứ.</h2>
          </div>
          <div className="impact">
            <div className="cell rv">
              <div className="v">Đối chiếu trước khi duyệt</div>
              <p>
                Mọi điều khoản được trỏ về văn bản còn hiệu lực, kèm ngày áp dụng. Bấm vào từng căn cứ
                ở trên để mở toàn văn.
              </p>
            </div>
            <div className="cell rv">
              <div className="v">AI không tự ban hành</div>
              <p>
                Agent chỉ gợi ý và dự thảo. Duyệt, ký, đóng hồ sơ luôn là hành động của người có thẩm
                quyền.
              </p>
            </div>
            <div className="cell rv">
              <div className="v">Nhật ký từng bước</div>
              <p>Ai làm gì, lúc nào, dựa trên căn cứ nào — đều ghi lại để tra cứu khi cần đối chiếu.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="band final" id="start">
        <div className="in">
          <div>
            <h2>Chạy thử một hồ sơ thật của bạn.</h2>
            <p>Tạo tài khoản, mở một vụ việc và xem toàn bộ luồng trong 2 phút. Không cần cài gì.</p>
            <ul>
              <li>
                <span className="mk">✓</span>
                <span>Dữ liệu hồ sơ phân quyền theo vai trò HR, pháp chế, quản lý và người ký.</span>
              </li>
              <li>
                <span className="mk">✓</span>
                <span>Nhật ký thao tác cho từng bước duyệt, ai làm, lúc nào.</span>
              </li>
              <li>
                <span className="mk">✓</span>
                <span>Xuất biên bản, phiếu và quyết định ra DOCX hoặc Markdown.</span>
              </li>
            </ul>
          </div>
          <div className="form rv" id="auth">
            <div className="kicker2">Không gian hồ sơ</div>
            <h3>{mode === "login" ? "Đăng nhập hệ thống" : "Tạo tài khoản"}</h3>
            <p className="sub">
              {mode === "login" ? "Dùng tài khoản doanh nghiệp của bạn." : "Bắt đầu với vai trò nhân sự."}
            </p>
            {error ? (
              <p role="alert" style={{ marginTop: 14, fontSize: 13.5, color: "#8C2B2B" }}>
                {error}
              </p>
            ) : null}
            {mode === "login" ? (
              <form
                onSubmit={loginForm.handleSubmit(async (values) => {
                  setError(null);
                  try {
                    await login(values.email, values.password);
                  } catch (err) {
                    setError(errorMessage(err));
                  }
                })}
              >
                <div className="field">
                  <label htmlFor="email">Email</label>
                  <input id="email" type="email" autoComplete="email" {...loginForm.register("email")} />
                  {loginForm.formState.errors.email ? (
                    <p style={{ marginTop: 6, fontSize: 12.5, color: "#8C2B2B" }}>
                      {loginForm.formState.errors.email.message}
                    </p>
                  ) : null}
                </div>
                <div className="field">
                  <label htmlFor="password">Mật khẩu</label>
                  <input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    {...loginForm.register("password")}
                  />
                  {loginForm.formState.errors.password ? (
                    <p style={{ marginTop: 6, fontSize: 12.5, color: "#8C2B2B" }}>
                      {loginForm.formState.errors.password.message}
                    </p>
                  ) : null}
                </div>
                <button className="btn p" type="submit" disabled={busy}>
                  {busy ? "Đang xử lý…" : "Đăng nhập"}
                </button>
              </form>
            ) : (
              <form
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
                <div className="field">
                  <label htmlFor="reg-email">Email</label>
                  <input id="reg-email" type="email" autoComplete="email" {...registerForm.register("email")} />
                  {registerForm.formState.errors.email ? (
                    <p style={{ marginTop: 6, fontSize: 12.5, color: "#8C2B2B" }}>
                      {registerForm.formState.errors.email.message}
                    </p>
                  ) : null}
                </div>
                <div className="field">
                  <label htmlFor="full-name">Họ và tên</label>
                  <input id="full-name" autoComplete="name" {...registerForm.register("full_name")} />
                </div>
                <div className="field">
                  <label htmlFor="role">Vai trò</label>
                  <select id="role" {...registerForm.register("role")}>
                    {(Object.keys(ROLE_LABEL) as Array<keyof typeof ROLE_LABEL>).map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABEL[r]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="reg-password">Mật khẩu</label>
                  <input
                    id="reg-password"
                    type="password"
                    autoComplete="new-password"
                    {...registerForm.register("password")}
                  />
                  {registerForm.formState.errors.password ? (
                    <p style={{ marginTop: 6, fontSize: 12.5, color: "#8C2B2B" }}>
                      {registerForm.formState.errors.password.message}
                    </p>
                  ) : null}
                </div>
                <button className="btn p" type="submit" disabled={busy}>
                  {busy ? "Đang xử lý…" : "Tạo tài khoản"}
                </button>
              </form>
            )}
            <p className="swap">
              <span>{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}</span>{" "}
              <button type="button" onClick={() => switchMode(mode === "login" ? "register" : "login")}>
                {mode === "login" ? "Tạo tài khoản" : "Đăng nhập"}
              </button>
            </p>
          </div>
        </div>
      </section>

      <footer>
        <div className="in wrap">
          <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
            <div className="foot-seal">
              HR
              <br />
              HELP
            </div>
            <div>
              <b>HR Help</b> — Trợ lý chính sách nhân sự
              <br />
              <span style={{ fontSize: 12.5 }}>AI đề xuất. Người quyết định.</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
