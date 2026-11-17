import { useId, type ReactNode } from "react";

export type ContextField = {
  key: string;
  label: string;
  type: string;
  group: string;
};
export type ContextSchema = {
  company: ContextField[];
  shipment: ContextField[];
  adjustments: ContextField[];
};
const groups: Record<string, string> = {
  consignee: "Получатель",
  declarant: "Декларант",
  financial_party: "Лицо, ответственное за финансовое урегулирование",
  representative: "Представитель",
  shipment: "Условия поставки",
  goods: "Параметры для всех товаров",
};

export function ContextFields({
  fields,
  values,
  onChange,
  renderHelp,
}: {
  fields: ContextField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  renderHelp?: (key: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className="context-form">
      {[...new Set(fields.map((f) => f.group))].map((group) => (
        <fieldset key={group}>
          <legend>{groups[group] || group}</legend>
          <div className="context-form-grid">
            {fields
              .filter((f) => f.group === group)
              .map((f) => {
                const help = renderHelp?.(f.key);
                const inputId = `${id}-${f.key}`;
                return (
                  <div key={f.key}>
                    <label htmlFor={inputId}>{f.label}</label>
                    <input
                      id={inputId}
                      name={f.key}
                      type={f.type}
                      value={values[f.key] || ""}
                      maxLength={2000}
                      aria-describedby={help ? `${inputId}-help` : undefined}
                      onInput={
                        f.type === "date"
                          ? (e) => onChange(f.key, e.currentTarget.value)
                          : undefined
                      }
                      onChange={(e) => onChange(f.key, e.target.value)}
                    />
                    {help && (
                      <div
                        id={`${inputId}-help`}
                        className="context-field-help"
                      >
                        {help}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
