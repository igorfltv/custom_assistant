import React, { useEffect, useRef, useState, type ReactNode } from "react";
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
  Menu,
  LayoutDashboard,
  RotateCw,
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
export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const beforeNavigate = (event: Event) => {
      event.preventDefault();
    };
    const navigate = (event: MouseEvent) => {
      const link = (event.target as Element).closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !link ||
        link.target === "_blank" ||
        link.download ||
        link.href === location.href ||
        link.hash === "#main-content" ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.button !== 0
      )
        return;
      if (
        !window.confirm("Есть несохранённые изменения. Перейти без сохранения?")
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("forma:before-navigate", beforeNavigate);
    document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("forma:before-navigate", beforeNavigate);
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty]);
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
export function Spinner({ label = "Загружаем…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{label}</span>
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
  return (
    <div
      className={"banner " + tone}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
export function LoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="load-error">
      <Banner tone="error">{message}</Banner>
      <button className="button small" onClick={onRetry}>
        <RotateCw size={15} /> Попробовать снова
      </button>
    </div>
  );
}
export function Modal({
  title,
  onClose,
  children,
  dirty = false,
  busy = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  dirty?: boolean;
  busy?: boolean;
}) {
  useUnsavedChanges(dirty);
  const container = useRef<HTMLElement>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  const stayButton = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (confirmClose) stayButton.current?.focus();
    else if (returnFocus.current?.isConnected) returnFocus.current.focus();
  }, [confirmClose]);
  const closeRef = useRef(() => {});
  closeRef.current = () => {
    if (busy) return;
    if (confirmClose) {
      setConfirmClose(false);
      return;
    }
    if (!dirty) {
      onClose();
      return;
    }
    returnFocus.current = document.activeElement as HTMLElement | null;
    setConfirmClose(true);
  };
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () =>
      Array.from(
        container.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
        ) || [],
      ).filter((el) => el.getClientRects().length > 0);
    if (!container.current?.contains(document.activeElement)) {
      (
        container.current?.querySelector<HTMLElement>(
          "input:not([type=hidden]), textarea, select",
        ) ||
        focusable()[0] ||
        container.current
      )?.focus();
    }
    const f = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const nodes = focusable();
        const first = nodes[0],
          last = nodes.at(-1);
        if (!first) {
          e.preventDefault();
          container.current?.focus();
        } else if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === container.current)
        ) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", f);
    return () => {
      window.removeEventListener("keydown", f);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return (
    <div className="modal-scrim" onClick={() => closeRef.current()}>
      <section
        ref={container}
        tabIndex={-1}
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
            onClick={() => closeRef.current()}
            disabled={busy}
            aria-label="Закрыть"
          >
            <X size={20} />
          </button>
        </div>
        <div hidden={confirmClose}>{children}</div>
        {confirmClose && (
          <div className="discard-confirm">
            <h3>Сохранить изменения перед выходом?</h3>
            <p>
              Вернитесь к форме, чтобы сохранить данные, или закройте её без
              сохранения.
            </p>
            <div className="row">
              <button
                ref={stayButton}
                className="button primary"
                onClick={() => setConfirmClose(false)}
              >
                Вернуться к форме
              </button>
              <button className="button" onClick={onClose}>
                Закрыть без сохранения
              </button>
            </div>
          </div>
        )}
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
  error: "Ошибка обработки",
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
  focusMode = false,
  navigation,
  children,
}: {
  user: User;
  onLogout: () => void;
  active: string;
  adminMode?: boolean;
  focusMode?: boolean;
  navigation?: (onNavigate: () => void) => ReactNode;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 980px)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(max-width: 980px)");
    const update = () => setCompact(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
      onLogout();
    } catch (e) {
      setLogoutError((e as Error).message);
    }
  }
  const items = adminMode
    ? [
        ["/", "Обзор", LayoutDashboard],
        ["/models", "Модели и провайдеры", Settings2],
        ["/knowledge", "База знаний", BookOpen],
        ["/companies", "Компании", Files],
        ["/team", "Сотрудники", Users],
        ["/stats", "Статистика", ChartNoAxesCombined],
      ]
    : [
        ["/", "Декларации", Files],
        ["/knowledge", "База знаний", BookOpen],
      ];
  return (
    <div
      className={
        "app-shell" +
        (focusMode ? " focus-mode" : "") +
        (navigation ? " conversation-shell" : "")
      }
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        К содержимому
      </a>
      <div className="mobile-appbar">
        <a
          href={adminMode ? "/admin/" : "/workspace/"}
          className="mobile-brand"
        >
          форма<span className="orange">.</span>
        </a>
        <span>{adminMode ? "Управление" : "Рабочее пространство"}</span>
        <button
          className="icon-button"
          aria-label="Открыть меню"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(true)}
        >
          <Menu size={21} />
        </button>
      </div>
      <aside className="sidebar">
        <Brand />
        {navigation ? (
          !compact && navigation(() => {})
        ) : (
          <>
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
                  aria-current={active === url ? "page" : undefined}
                >
                  <Icon size={19} />
                  {title}
                  {active === url && <span className="active-dot" />}
                </a>
              ))}
            </nav>
          </>
        )}
        <div className="sidebar-bottom">
          {!navigation && (
            <div className="sidebar-note">
              <Sparkles size={19} />
              <strong>
                Каждое значение —<br />с источником
              </strong>
              <p>Документы, контекст и решения в одном месте.</p>
            </div>
          )}
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
            <button className="icon-button" onClick={logout} aria-label="Выйти">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="app-main">
        {!focusMode && (
          <header className="topbar">
            <span>
              Форма <span className="muted">/</span>{" "}
              {adminMode ? "Управление" : "Кабинет специалиста"}
            </span>
            <span className="prototype-tag">
              Прототип <span>0.1</span>
            </span>
          </header>
        )}
        <main className="content" id="main-content" tabIndex={-1}>
          {logoutError && <Banner tone="error">{logoutError}</Banner>}
          {children}
        </main>
        {!focusMode && (
          <footer className="app-footer">
            <span>Форма · Рабочее пространство декларанта</span>
            <span>Импорт и экспорт · Декларация на товары</span>
          </footer>
        )}
      </div>
      {menuOpen && (!navigation || compact) && (
        <Modal title="Навигация" onClose={() => setMenuOpen(false)}>
          {navigation ? (
            navigation(() => setMenuOpen(false))
          ) : (
            <>
              <nav className="mobile-menu">
                {items.map(([url, title, Icon]: any) => (
                  <a
                    key={url}
                    className={"nav-item " + (active === url ? "active" : "")}
                    href={"#" + url}
                    aria-current={active === url ? "page" : undefined}
                    onClick={() => setMenuOpen(false)}
                  >
                    <Icon size={19} />
                    {title}
                  </a>
                ))}
                {user.role === "admin" && (
                  <a
                    className="nav-item"
                    href={adminMode ? "/workspace/" : "/admin/"}
                  >
                    <ArrowUpRight size={19} />
                    {adminMode ? "Кабинет специалиста" : "Администрирование"}
                  </a>
                )}
              </nav>
            </>
          )}
          {navigation && user.role === "admin" && (
            <a className="nav-item" href="/admin/">
              <Settings2 size={18} /> Администрирование
            </a>
          )}
          <div className="mobile-account">
            <span>
              {user.name}
              <small>{user.email}</small>
            </span>
            <button className="button small" onClick={logout}>
              <LogOut size={16} /> Выйти
            </button>
          </div>
          {logoutError && <Banner tone="error">{logoutError}</Banner>}
        </Modal>
      )}
    </div>
  );
}

export {
  ContextFields,
  type ContextField,
  type ContextSchema,
} from "./ContextFields";
