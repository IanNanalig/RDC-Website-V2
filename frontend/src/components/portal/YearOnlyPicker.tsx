import { useEffect, useId, useRef, useState } from "react";

const FIRST_YEAR = 1900;
const LAST_YEAR = 2200;
const YEARS_PER_PAGE = 12;

const pageStart = (year: number) =>
  FIRST_YEAR + Math.floor((year - FIRST_YEAR) / YEARS_PER_PAGE) * YEARS_PER_PAGE;

type YearOnlyPickerProps = {
  label: string;
  value: string;
  onChange: (year: string) => void;
  minYear?: number;
  maxYear?: number;
  required?: boolean;
  disabled?: boolean;
};

const YearOnlyPicker = ({
  label, value, onChange, minYear = FIRST_YEAR, maxYear = LAST_YEAR, required, disabled,
}: YearOnlyPickerProps) => {
  const id = useId();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [visibleStart, setVisibleStart] = useState(pageStart(new Date().getFullYear()));
  const [focusedYear, setFocusedYear] = useState(new Date().getFullYear());
  const [above, setAbove] = useState(false);
  const [maxHeight, setMaxHeight] = useState(280);
  const selectedYear = Number(value);
  const selectedValid = value !== "" && Number.isInteger(selectedYear) && selectedYear >= FIRST_YEAR && selectedYear <= LAST_YEAR;
  const lower = Math.max(FIRST_YEAR, minYear);
  const upper = Math.min(LAST_YEAR, maxYear);

  const close = (returnFocus = false) => {
    setOpen(false);
    if (returnFocus) window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const show = () => {
    if (disabled || lower > upper) return;
    const initial = Math.min(upper, Math.max(lower, selectedValid ? selectedYear : new Date().getFullYear()));
    setFocusedYear(initial);
    setVisibleStart(pageStart(initial));
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const updatePlacement = () => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const viewport = window.visualViewport;
      const viewportTop = viewport?.offsetTop ?? 0;
      const viewportBottom = viewportTop + (viewport?.height ?? window.innerHeight);
      const roomAbove = rect.top - viewportTop;
      const roomBelow = viewportBottom - rect.bottom;
      const placeAbove = roomBelow < 240 && roomAbove > roomBelow;
      setAbove(placeAbove);
      setMaxHeight(Math.max(80, Math.min(280, (placeAbove ? roomAbove : roomBelow) - 8)));
    };
    const onViewportResize = () => {
      const trigger = triggerRef.current;
      const viewport = window.visualViewport;
      if (trigger) {
        const rect = trigger.getBoundingClientRect();
        const top = viewport?.offsetTop ?? 0;
        const bottom = top + (viewport?.height ?? window.innerHeight);
        if (rect.top < top || rect.bottom > bottom) trigger.scrollIntoView({ block: "center" });
      }
      window.requestAnimationFrame(updatePlacement);
    };
    const onOutsideTap = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) close();
    };
    triggerRef.current?.scrollIntoView({ block: "center" });
    window.requestAnimationFrame(updatePlacement);
    document.addEventListener("pointerdown", onOutsideTap);
    window.addEventListener("resize", onViewportResize);
    window.visualViewport?.addEventListener("resize", onViewportResize);
    window.visualViewport?.addEventListener("scroll", updatePlacement);
    return () => {
      document.removeEventListener("pointerdown", onOutsideTap);
      window.removeEventListener("resize", onViewportResize);
      window.visualViewport?.removeEventListener("resize", onViewportResize);
      window.visualViewport?.removeEventListener("scroll", updatePlacement);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const target = popupRef.current?.querySelector<HTMLButtonElement>(`[data-year="${focusedYear}"]`);
    target?.focus();
  }, [open, focusedYear, visibleStart]);

  const moveFocus = (year: number) => {
    const next = Math.max(lower, Math.min(upper, year));
    setFocusedYear(next);
    setVisibleStart(pageStart(next));
  };

  const movePage = (direction: number) => {
    const nextStart = visibleStart + direction * YEARS_PER_PAGE;
    if (nextStart > upper || nextStart + YEARS_PER_PAGE - 1 < lower) return;
    setVisibleStart(nextStart);
    setFocusedYear(Math.max(lower, Math.min(upper, nextStart + (focusedYear - visibleStart))));
  };

  return (
    <div ref={wrapperRef} className="relative min-w-0">
      <label id={`${id}-label`} className="block text-sm text-slate-700">{label}{required ? " *" : ""}</label>
      <button
        ref={triggerRef}
        type="button"
        aria-labelledby={`${id}-label`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${id}-picker` : undefined}
        aria-required={required || undefined}
        disabled={disabled || lower > upper}
        onClick={() => open ? close() : show()}
        onKeyDown={(event) => {
          if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            event.preventDefault();
            show();
          }
        }}
        className="mt-1 flex min-h-10 w-full min-w-0 items-center justify-between rounded border border-slate-300 bg-white px-3 py-2 text-left text-slate-900 disabled:bg-slate-100 disabled:text-slate-400"
      >
        <span>{value || "Select year"}</span>
        <span aria-hidden="true" className="text-slate-500">▦</span>
      </button>
      {open && (
        <div
          ref={popupRef}
          id={`${id}-picker`}
          role="dialog"
          aria-label={`${label} year picker`}
          className={`absolute inset-x-0 z-40 min-w-0 overflow-y-auto rounded-lg border border-slate-300 bg-white p-2 shadow-xl ${above ? "bottom-full mb-1" : "top-full mt-1"}`}
          style={{ maxHeight }}
          onKeyDown={(event) => {
            const moves: Record<string, number> = {
              ArrowLeft: -1, ArrowRight: 1, ArrowUp: -4, ArrowDown: 4,
              PageUp: -YEARS_PER_PAGE, PageDown: YEARS_PER_PAGE,
            };
            if (event.key in moves) {
              event.preventDefault();
              moveFocus(focusedYear + moves[event.key]);
            } else if (event.key === "Home" || event.key === "End") {
              event.preventDefault();
              moveFocus(event.key === "Home" ? Math.max(lower, visibleStart) : Math.min(upper, visibleStart + YEARS_PER_PAGE - 1));
            } else if (event.key === "Escape") {
              event.preventDefault();
              close(true);
            } else if (event.key === "Tab") {
              close();
            }
          }}
        >
          <div className="mb-2 flex items-center justify-between gap-1">
            <button type="button" aria-label="Previous years" disabled={visibleStart - 1 < lower} onClick={() => movePage(-1)} className="min-h-10 min-w-10 rounded hover:bg-slate-100 disabled:opacity-40">‹</button>
            <span className="text-sm font-semibold text-slate-800">{visibleStart}–{Math.min(LAST_YEAR, visibleStart + YEARS_PER_PAGE - 1)}</span>
            <button type="button" aria-label="Next years" disabled={visibleStart + YEARS_PER_PAGE > upper} onClick={() => movePage(1)} className="min-h-10 min-w-10 rounded hover:bg-slate-100 disabled:opacity-40">›</button>
          </div>
          <div className="grid grid-cols-4 gap-1">
            {Array.from({ length: YEARS_PER_PAGE }, (_, index) => visibleStart + index).map((year) => (
              <button
                key={year}
                data-year={year}
                type="button"
                disabled={year < lower || year > upper}
                aria-pressed={selectedValid && year === selectedYear}
                tabIndex={year === focusedYear ? 0 : -1}
                onClick={() => { onChange(String(year)); close(true); }}
                className={`min-h-10 rounded text-sm disabled:cursor-not-allowed disabled:text-slate-300 ${year === selectedYear ? "bg-blue-600 text-white" : "text-slate-800 hover:bg-blue-50"}`}
              >
                {year}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default YearOnlyPicker;
