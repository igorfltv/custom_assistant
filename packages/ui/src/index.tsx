import React, { useEffect, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  Files,
  BookOpen,
  Settings2,
  Users,
  ChartNoAxesCombined,
  LogOut,
  X,
  LoaderCircle,
  Sparkles,
  ShieldCheck,
} from "lucide-react";

export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
};
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = "Не удалось выполнить запрос";
    try {
      const result = await response.json();
      message =
        typeof result.detail === "string"
          ? result.detail
          : "Проверьте введённые данные";
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
export function useHash() {
  const [hash, setHash] = useState(location.hash.slice(1) || "/");
  useEffect(() => {
    const listener = () => setHash(location.hash.slice(1) || "/");
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  return hash;
}
export function Brand({ light = false }: { light?: boolean }) {
  return (
    <a
      href="/"
      className={"brand " + (light ? "light" : "")}
      aria-label="Форма, главная"
    >
      <span className="brand-icon">
        <span />
        <span />
        <span />
      </span>
      форма<span className="brand-dot">.</span>
    </a>
  );
}
export function Spinner() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={24} />
      <span>Загружаем рабочее пространство</span>
    </div>
  );
}
export function Banner({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <div className={"banner " + tone}>{children}</div>;
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [onClose]);
  return (
    <div className="modal-scrim" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-head">
          <h2>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function Empty({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Files size={30} />
        <Sparkles size={14} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export const statusNames: Record<string, string> = {
  draft: "Черновик",
  queued: "В очереди",
  processing: "Анализируем",
  review: "На проверке",
  error: "Нужна помощь",
  completed: "Завершён",
  failed: "Ошибка",
  running: "В работе",
  uploaded: "Загружен",
  extracted: "Распознан",
  suggested: "Из документов",
  confirmed: "Подтверждено",
  conflict: "Противоречие",
  unverified: "Проверить источник",
};
export function Badge({ status, label }: { status: string; label?: string }) {
  return (
    <span className={"badge " + status}>
      <i />
      {label || statusNames[status] || status}
    </span>
  );
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
  }).format(new Date(value));
}
export function useAuth() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  return { user, setUser, loading };
}
export function Login({
  onLogin,
  adminMode = false,
}: {
  onLogin: (user: User) => void;
  adminMode?: boolean;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="auth-page">
      <div className="auth-top">
        <Brand />
        <a href="/">
          На главную <ArrowUpRight size={15} />
        </a>
      </div>
      <div className="auth-card">
        <span className="eyebrow">
          {adminMode ? "Управление системой" : "Рабочее пространство"}
        </span>
        <h1>
          С возвращением<span className="orange">.</span>
        </h1>
        <p>Войдите, чтобы продолжить работу с документами.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            const data = new FormData(e.currentTarget);
            try {
              onLogin(
                await api("/auth/login", {
                  method: "POST",
                  body: JSON.stringify(Object.fromEntries(data)),
                }),
              );
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              placeholder="name@company.ru"
            />
          </label>
          <label>
            Пароль
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="Ваш пароль"
            />
          </label>
          {error && <Banner tone="error">{error}</Banner>}
          <button className="button primary full" disabled={busy}>
            {busy ? <LoaderCircle size={18} className="spin" /> : "Войти"}
            <ArrowRight size={18} />
          </button>
        </form>
        <p className="small muted">
          Доступ сотрудникам предоставляет администратор компании.
        </p>
      </div>
      <p className="auth-foot">
        <ShieldCheck size={15} /> Документы доступны только сотрудникам компании
      </p>
    </div>
  );
}
export function Shell({
  user,
  onLogout,
  active,
  adminMode = false,
  children,
}: {
  user: User;
  onLogout: () => void;
  active: string;
  adminMode?: boolean;
  children: ReactNode;
}) {
  const items = adminMode
    ? [
        ["/models", "Модели и провайдеры", Settings2],
        ["/team", "Сотрудники", Users],
        ["/stats", "Статистика", ChartNoAxesCombined],
      ]
    : [
        ["/", "Декларации", Files],
        ["/knowledge", "База знаний", BookOpen],
      ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="org">
          <div className="org-avatar">К</div>
          <div>
            <strong>Компания</strong>
            <span>
              {adminMode ? "Администрирование" : "Рабочее пространство"}
            </span>
          </div>
          <span className="org-indicator" />
        </div>
        <p className="nav-caption">{adminMode ? "УПРАВЛЕНИЕ" : "РАБОТА"}</p>
        <nav>
          {items.map(([url, title, Icon]: any) => (
            <a
              key={url}
              className={"nav-item " + (active === url ? "active" : "")}
              href={"#" + url}
            >
              <Icon size={19} />
              {title}
              {active === url && <span className="active-dot" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Sparkles size={19} />
            <strong>
              Каждое значение —<br />с источником
            </strong>
            <p>Документы, контекст и решения в одном месте.</p>
          </div>
          {user.role === "admin" && (
            <a
              className="nav-item"
              href={adminMode ? "/workspace/" : "/admin/"}
            >
              <Settings2 size={18} />
              {adminMode ? "Кабинет специалиста" : "Администрирование"}
              <ArrowUpRight size={14} />
            </a>
          )}
          <div className="profile">
            <div className="avatar">{user.name.slice(0, 1)}</div>
            <div>
              <strong>{user.name}</strong>
              <span>
                {user.role === "admin" ? "Администратор" : "Специалист"}
              </span>
            </div>
            <button
              className="icon-button"
              onClick={async () => {
                await api("/auth/logout", { method: "POST" });
                onLogout();
              }}
              aria-label="Выйти"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <span>
            Форма <span className="muted">/</span>{" "}
            {adminMode ? "Управление" : "Кабинет специалиста"}
          </span>
          <span className="prototype-tag">
            Прототип <span>0.1</span>
          </span>
        </header>
        <main className="content">{children}</main>
        <footer className="app-footer">
          <span>Форма · Рабочее пространство декларанта</span>
          <span>Импорт в РФ · Декларация на товары</span>
        </footer>
      </div>
    </div>
  );
}
