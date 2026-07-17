class VulcanTimetableCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("vulcan-timetable-card-editor");
  }

  static getStubConfig(hass) {
    const entities = Object.keys(hass?.states || {}).filter((entityId) =>
      VulcanTimetableCard.isLessonEntity(entityId, hass.states[entityId])
    );

    const today =
      entities.find((id) => id.includes("lekcje_dzisiaj")) || entities[0] || "";

    return {
      entity: today,
      title: "Plan lekcji",
      archive_days: 60,
      show_header: true,
      show_teacher: true,
      show_room: true,
      show_status: true,
      compact: false,
    };
  }

  static isLessonEntity(entityId, stateObj) {
    if (!entityId?.startsWith("sensor.")) return false;

    const attrs = stateObj?.attributes || {};
    const idMatch =
      entityId.includes("vulcan_uonet") &&
      (entityId.includes("lekcje") || entityId.includes("plan_lekcji"));

    return idMatch || Array.isArray(attrs.lessons);
  }

  setConfig(config) {
    if (!config) throw new Error("Brak konfiguracji karty.");

    this.config = {
      entity: "",
      title: "Plan lekcji",
      archive_days: 60,
      show_header: true,
      show_teacher: true,
      show_room: true,
      show_status: true,
      compact: false,
      ...config,
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    this._historyCache = this._historyCache || new Map();
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
    this.loadArchiveIfNeeded();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return {
      columns: 12,
      rows: "auto",
      min_columns: 6,
      min_rows: 4,
    };
  }

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  normalizeText(value) {
    return String(value ?? "").trim();
  }

  formatDate(value) {
    if (!value) return "";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return new Intl.DateTimeFormat("pl-PL", {
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(date);
  }

  getLessons(attrs) {
    const candidates = [
      attrs?.lessons,
      attrs?.lesson_list,
      attrs?.timetable,
      attrs?.items,
    ];

    const lessons = candidates.find(Array.isArray);
    return Array.isArray(lessons) ? lessons : [];
  }

  getLessonValue(lesson, keys, fallback = "") {
    for (const key of keys) {
      const value = lesson?.[key];
      if (value !== undefined && value !== null && value !== "") {
        return value;
      }
    }
    return fallback;
  }

  normalizeLesson(lesson, index) {
    const number = this.getLessonValue(
      lesson,
      ["lesson_number", "number", "lesson_no", "position", "ordinal"],
      index + 1
    );

    const subject = this.getLessonValue(
      lesson,
      ["subject", "subject_name", "name", "lesson", "title"],
      "Lekcja"
    );

    const teacher = this.getLessonValue(
      lesson,
      ["teacher", "teacher_name", "employee", "lecturer"],
      ""
    );

    const room = this.getLessonValue(
      lesson,
      ["room", "room_name", "classroom"],
      ""
    );

    const start = this.getLessonValue(
      lesson,
      ["start", "start_time", "time_from", "from", "begin"],
      ""
    );

    const end = this.getLessonValue(
      lesson,
      ["end", "end_time", "time_to", "to", "finish"],
      ""
    );

    const status = this.getLessonValue(
      lesson,
      ["status", "change", "change_type", "event_type"],
      ""
    );

    const cancelled =
      Boolean(
        this.getLessonValue(
          lesson,
          ["cancelled", "is_cancelled", "canceled", "is_canceled"],
          false
        )
      ) ||
      /odwoł|cancel/i.test(String(status));

    const substitution =
      Boolean(
        this.getLessonValue(
          lesson,
          ["substitution", "is_substitution", "replacement"],
          false
        )
      ) ||
      /zastęp/i.test(String(status));

    return {
      number,
      subject,
      teacher,
      room,
      start,
      end,
      status,
      cancelled,
      substitution,
    };
  }

  async loadArchiveIfNeeded() {
    if (!this._hass || !this.config?.entity) return;

    const stateObj = this._hass.states?.[this.config.entity];
    if (!stateObj) return;

    const currentLessons = this.getLessons(stateObj.attributes || {});
    if (currentLessons.length) return;

    const days = Math.min(
      120,
      Math.max(1, Number.parseInt(this.config.archive_days, 10) || 60)
    );

    const cacheKey = `${this.config.entity}:${days}`;
    const cached = this._historyCache.get(cacheKey);

    if (cached?.status === "loading" || cached?.status === "ready") return;

    this._historyCache.set(cacheKey, { status: "loading" });
    this.render();

    try {
      const end = new Date();
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);

      const result = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: [this.config.entity],
        include_start_time_state: true,
        significant_changes_only: false,
        minimal_response: false,
        no_attributes: false,
      });

      const states = Array.isArray(result?.[0])
        ? result[0]
        : Array.isArray(result)
          ? result.flat()
          : [];

      let found = null;

      for (let index = states.length - 1; index >= 0; index -= 1) {
        const historicState = states[index];
        const attrs = historicState?.attributes || {};
        const lessons = this.getLessons(attrs);

        if (lessons.length) {
          found = {
            attrs,
            lessons,
            state: historicState,
          };
          break;
        }
      }

      this._historyCache.set(cacheKey, {
        status: "ready",
        found,
      });
    } catch (error) {
      console.error("Vulcan timetable: błąd historii", error);
      this._historyCache.set(cacheKey, {
        status: "error",
        error: String(error?.message || error),
      });
    }

    this.render();
  }

  render() {
    if (!this.shadowRoot || !this.config) return;

    const entityId = this.config.entity;
    const stateObj = this._hass?.states?.[entityId];

    if (!entityId) {
      this.shadowRoot.innerHTML = `
        ${this.styles()}
        <ha-card>
          <div class="message error">
            Wybierz encję lekcji Vulcan w konfiguracji karty.
          </div>
        </ha-card>
      `;
      return;
    }

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        ${this.styles()}
        <ha-card>
          <div class="message error">
            Nie znaleziono encji:
            <strong>${this.escapeHtml(entityId)}</strong>
          </div>
        </ha-card>
      `;
      return;
    }

    const liveAttrs = stateObj.attributes || {};
    let attrs = liveAttrs;
    let lessons = this.getLessons(liveAttrs);
    let archiveMode = false;
    let archiveStatus = null;

    const days = Math.min(
      120,
      Math.max(1, Number.parseInt(this.config.archive_days, 10) || 60)
    );
    const cacheKey = `${entityId}:${days}`;
    const history = this._historyCache?.get(cacheKey);

    if (!lessons.length && history) {
      archiveStatus = history.status;

      if (history.status === "ready" && history.found) {
        attrs = history.found.attrs || {};
        lessons = history.found.lessons || [];
        archiveMode = true;
      }
    }

    const student =
      attrs.full_name ||
      [attrs.first_name, attrs.last_name].filter(Boolean).join(" ") ||
      liveAttrs.full_name ||
      stateObj.attributes?.friendly_name ||
      "Uczeń";

    const date = attrs.date || "";
    const title =
      this.config.title === false
        ? ""
        : this.config.title || `Plan lekcji — ${student}`;

    const normalized = lessons.map((lesson, index) =>
      this.normalizeLesson(lesson, index)
    );

    const rows = normalized
      .map((lesson) => {
        const time =
          lesson.start || lesson.end
            ? `${this.escapeHtml(lesson.start || "—")}–${this.escapeHtml(
                lesson.end || "—"
              )}`
            : "";

        const meta = [];

        if (this.config.show_teacher && lesson.teacher) {
          meta.push(`👤 ${this.escapeHtml(lesson.teacher)}`);
        }

        if (this.config.show_room && lesson.room) {
          meta.push(`🚪 ${this.escapeHtml(lesson.room)}`);
        }

        let statusLabel = "";
        let statusClass = "";

        if (lesson.cancelled) {
          statusLabel = "Odwołana";
          statusClass = "cancelled";
        } else if (lesson.substitution) {
          statusLabel = "Zastępstwo";
          statusClass = "substitution";
        } else if (lesson.status) {
          statusLabel = this.escapeHtml(lesson.status);
          statusClass = "changed";
        }

        return `
          <div class="lesson-row ${lesson.cancelled ? "is-cancelled" : ""}">
            <div class="lesson-number">
              ${this.escapeHtml(lesson.number)}
            </div>

            <div class="lesson-main">
              <div class="subject">
                ${this.escapeHtml(lesson.subject)}
              </div>

              ${
                meta.length
                  ? `<div class="meta">${meta.join(" · ")}</div>`
                  : ""
              }

              ${
                this.config.show_status && statusLabel
                  ? `<div class="status ${statusClass}">${statusLabel}</div>`
                  : ""
              }
            </div>

            <div class="time">
              ${time}
            </div>
          </div>
        `;
      })
      .join("");

    let emptyContent = `
      <div class="empty">
        <ha-icon icon="mdi:calendar-blank-outline"></ha-icon>
        <span>Brak lekcji do wyświetlenia</span>
      </div>
    `;

    if (archiveStatus === "loading") {
      emptyContent = `
        <div class="empty">
          <ha-icon icon="mdi:history"></ha-icon>
          <span>Szukam ostatniego planu w historii…</span>
        </div>
      `;
    } else if (archiveStatus === "ready" && !history?.found) {
      emptyContent = `
        <div class="empty">
          <ha-icon icon="mdi:calendar-remove-outline"></ha-icon>
          <span>
            Brak zapisanych lekcji z ostatnich ${days} dni
          </span>
        </div>
      `;
    } else if (archiveStatus === "error") {
      emptyContent = `
        <div class="empty">
          <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
          <span>Nie udało się pobrać historii encji</span>
        </div>
      `;
    }

    const compactClass = this.config.compact ? "compact" : "";

    this.shadowRoot.innerHTML = `
      ${this.styles()}

      <ha-card class="${compactClass}">
        <div class="content">
          ${
            this.config.show_header
              ? `
                <div class="header">
                  <div>
                    <div class="title">
                      📚 ${this.escapeHtml(title)}
                    </div>

                    <div class="subtitle">
                      ${this.escapeHtml(student)}
                      ${attrs.class ? ` · klasa ${this.escapeHtml(attrs.class)}` : ""}
                      ${attrs.unit || attrs.school
                        ? ` · ${this.escapeHtml(attrs.unit || attrs.school)}`
                        : ""}
                    </div>
                  </div>

                  <div class="day-box">
                    ${
                      archiveMode
                        ? `<span class="archive-badge">ARCHIWUM</span>`
                        : ""
                    }
                    <span>${this.escapeHtml(this.formatDate(date))}</span>
                  </div>
                </div>
              `
              : ""
          }

          <div class="lessons">
            ${normalized.length ? rows : emptyContent}
          </div>

          ${
            archiveMode
              ? `
                <div class="archive-info">
                  Pokazano ostatni zapisany plan, ponieważ bieżąca encja
                  nie zawiera lekcji.
                </div>
              `
              : ""
          }

          ${
            attrs.updated_at
              ? `
                <div class="updated">
                  Aktualizacja:
                  ${this.escapeHtml(
                    new Intl.DateTimeFormat("pl-PL", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(attrs.updated_at))
                  )}
                </div>
              `
              : ""
          }
        </div>
      </ha-card>
    `;
  }

  styles() {
    return `
      <style>
        :host {
          display: block;
        }

        ha-card {
          overflow: hidden;
          border-radius: 22px;
          color: #f2f7ff;
          background:
            radial-gradient(circle at 0% 0%, rgba(56, 189, 248, 0.17), transparent 38%),
            radial-gradient(circle at 100% 0%, rgba(250, 204, 21, 0.10), transparent 34%),
            linear-gradient(145deg, rgba(18, 27, 41, 0.97), rgba(7, 13, 22, 0.99));
          border: 1px solid rgba(148, 163, 184, 0.20);
          box-shadow:
            0 10px 28px rgba(0, 0, 0, 0.34),
            inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }

        .content {
          padding: 14px;
        }

        .header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 14px;
        }

        .title {
          color: #f8fafc;
          font-size: 22px;
          font-weight: 800;
          line-height: 1.1;
        }

        .subtitle {
          margin-top: 5px;
          color: #94a3b8;
          font-size: 12px;
        }

        .day-box {
          display: grid;
          justify-items: end;
          gap: 4px;
          color: #8be9fd;
          font-size: 11px;
          font-weight: 700;
          text-align: right;
        }

        .archive-badge {
          padding: 3px 7px;
          border-radius: 8px;
          color: #facc15;
          background: rgba(250, 204, 21, 0.12);
          border: 1px solid rgba(250, 204, 21, 0.24);
          font-size: 9px;
          letter-spacing: 0.06em;
        }

        .lessons {
          display: flex;
          flex-direction: column;
          gap: 7px;
        }

        .lesson-row {
          display: grid;
          grid-template-columns: 42px minmax(0, 1fr) auto;
          align-items: center;
          gap: 11px;
          padding: 10px 9px;
          border-radius: 15px;
          background: rgba(255, 255, 255, 0.025);
          border: 1px solid rgba(148, 163, 184, 0.10);
        }

        .lesson-number {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 11px;
          color: #8be9fd;
          background: rgba(56, 189, 248, 0.12);
          border: 1px solid rgba(56, 189, 248, 0.23);
          font-size: 16px;
          font-weight: 900;
        }

        .lesson-main {
          min-width: 0;
        }

        .subject {
          overflow: hidden;
          color: #f1f5f9;
          font-size: 14px;
          font-weight: 750;
          line-height: 1.25;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .meta {
          margin-top: 4px;
          color: #94a3b8;
          font-size: 10px;
          line-height: 1.3;
          overflow-wrap: anywhere;
        }

        .time {
          color: #facc15;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
        }

        .status {
          display: inline-flex;
          margin-top: 5px;
          padding: 3px 7px;
          border-radius: 8px;
          font-size: 9px;
          font-weight: 700;
        }

        .status.cancelled {
          color: #fb7185;
          background: rgba(251, 113, 133, 0.13);
        }

        .status.substitution {
          color: #c4b5fd;
          background: rgba(196, 181, 253, 0.13);
        }

        .status.changed {
          color: #facc15;
          background: rgba(250, 204, 21, 0.13);
        }

        .is-cancelled {
          opacity: 0.70;
        }

        .is-cancelled .subject {
          text-decoration: line-through;
        }

        .empty {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 9px;
          min-height: 110px;
          color: #94a3b8;
          text-align: center;
        }

        .archive-info {
          margin-top: 10px;
          padding: 8px 10px;
          border-radius: 10px;
          color: #facc15;
          background: rgba(250, 204, 21, 0.08);
          border: 1px solid rgba(250, 204, 21, 0.16);
          font-size: 10px;
          line-height: 1.35;
        }

        .updated {
          margin-top: 10px;
          color: #64748b;
          font-size: 9px;
          text-align: right;
        }

        .message {
          padding: 18px;
        }

        .error {
          color: #fecaca;
          background: rgba(127, 29, 29, 0.28);
        }

        .compact .lesson-row {
          grid-template-columns: 36px minmax(0, 1fr) auto;
          gap: 8px;
          padding: 7px;
        }

        .compact .lesson-number {
          width: 31px;
          height: 31px;
          border-radius: 9px;
          font-size: 14px;
        }

        .compact .subject {
          font-size: 13px;
        }

        .compact .time {
          font-size: 11px;
        }
      </style>
    `;
  }
}


class VulcanTimetableCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = {
      entity: "",
      title: "Plan lekcji",
      archive_days: 60,
      show_header: true,
      show_teacher: true,
      show_room: true,
      show_status: true,
      compact: false,
      ...config,
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  getLessonEntities() {
    if (!this._hass?.states) return [];

    return Object.entries(this._hass.states)
      .filter(([entityId, stateObj]) =>
        VulcanTimetableCard.isLessonEntity(entityId, stateObj)
      )
      .sort((a, b) => {
        const nameA = a[1].attributes?.friendly_name || a[0];
        const nameB = b[1].attributes?.friendly_name || b[0];
        return String(nameA).localeCompare(String(nameB), "pl");
      });
  }

  fireConfigChanged(config) {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      })
    );
  }

  updateConfig(key, value) {
    this._config = {
      ...this._config,
      [key]: value,
    };

    this.fireConfigChanged(this._config);
    this.render();
  }

  switchRow(id, label, checked) {
    return `
      <label class="switch-row" for="${id}">
        <span>${this.escapeHtml(label)}</span>
        <input id="${id}" type="checkbox" ${checked ? "checked" : ""} />
      </label>
    `;
  }

  render() {
    if (!this.shadowRoot || !this._config) return;

    const entities = this.getLessonEntities();

    const entityOptions = [
      `<option value="">— wybierz encję lekcji —</option>`,
      ...entities.map(([entityId, stateObj]) => {
        const name = stateObj.attributes?.friendly_name || entityId;
        const selected = this._config.entity === entityId ? "selected" : "";

        return `
          <option value="${this.escapeHtml(entityId)}" ${selected}>
            ${this.escapeHtml(name)} — ${this.escapeHtml(entityId)}
          </option>
        `;
      }),
    ].join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          color: var(--primary-text-color);
        }

        * {
          box-sizing: border-box;
        }

        .editor {
          display: grid;
          gap: 16px;
          padding: 4px 0;
        }

        .field {
          display: grid;
          gap: 7px;
        }

        label {
          font-size: 14px;
          font-weight: 600;
        }

        .hint {
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.35;
        }

        select,
        input[type="text"],
        input[type="number"] {
          width: 100%;
          min-height: 46px;
          padding: 10px 12px;
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          outline: none;
          color: var(--primary-text-color);
          background: var(--card-background-color);
          font: inherit;
        }

        select:focus,
        input:focus {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
        }

        .switches {
          display: grid;
          gap: 3px;
        }

        .switch-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          min-height: 42px;
          padding: 5px 0;
          border-bottom: 1px solid var(--divider-color);
        }

        .switch-row:last-child {
          border-bottom: 0;
        }

        input[type="checkbox"] {
          width: 20px;
          height: 20px;
          accent-color: var(--primary-color);
        }

        .warning {
          padding: 12px;
          border-radius: 10px;
          color: var(--warning-color, #ff9800);
          background: rgba(255, 152, 0, 0.10);
          font-size: 13px;
          line-height: 1.4;
        }
      </style>

      <div class="editor">
        ${
          entities.length
            ? ""
            : `
              <div class="warning">
                Nie znaleziono encji Vulcan zawierającej atrybut
                <strong>lessons</strong>.
              </div>
            `
        }

        <div class="field">
          <label for="entity">Encja planu lekcji</label>
          <select id="entity">${entityOptions}</select>
          <div class="hint">
            Lista jest tworzona automatycznie — imię i nazwisko ucznia
            nie są wpisane w kodzie karty.
          </div>
        </div>

        <div class="field">
          <label for="title">Tytuł karty</label>
          <input
            id="title"
            type="text"
            value="${this.escapeHtml(this._config.title ?? "")}"
            placeholder="Plan lekcji"
          />
        </div>

        <div class="field">
          <label for="archive_days">Historia do przeszukania</label>
          <input
            id="archive_days"
            type="number"
            min="1"
            max="120"
            step="1"
            value="${this.escapeHtml(this._config.archive_days ?? 60)}"
          />
          <div class="hint">
            Gdy bieżąca lista jest pusta, karta szuka ostatniego planu
            w Recorderze Home Assistant.
          </div>
        </div>

        <div class="switches">
          ${this.switchRow("show_header", "Pokazuj nagłówek", this._config.show_header)}
          ${this.switchRow("show_teacher", "Pokazuj nauczyciela", this._config.show_teacher)}
          ${this.switchRow("show_room", "Pokazuj salę", this._config.show_room)}
          ${this.switchRow("show_status", "Pokazuj zmiany i odwołania", this._config.show_status)}
          ${this.switchRow("compact", "Tryb kompaktowy", this._config.compact)}
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    root.getElementById("entity")?.addEventListener("change", (event) => {
      this.updateConfig("entity", event.target.value);
    });

    root.getElementById("title")?.addEventListener("change", (event) => {
      this.updateConfig("title", event.target.value);
    });

    root.getElementById("archive_days")?.addEventListener("change", (event) => {
      const value = Math.min(
        120,
        Math.max(1, Number.parseInt(event.target.value, 10) || 60)
      );
      this.updateConfig("archive_days", value);
    });

    [
      "show_header",
      "show_teacher",
      "show_room",
      "show_status",
      "compact",
    ].forEach((key) => {
      root.getElementById(key)?.addEventListener("change", (event) => {
        this.updateConfig(key, event.target.checked);
      });
    });
  }
}


if (!customElements.get("vulcan-timetable-card-editor")) {
  customElements.define(
    "vulcan-timetable-card-editor",
    VulcanTimetableCardEditor
  );
}

if (!customElements.get("vulcan-timetable-card")) {
  customElements.define("vulcan-timetable-card", VulcanTimetableCard);
}

window.customCards = window.customCards || [];

if (
  !window.customCards.some(
    (card) => card.type === "vulcan-timetable-card"
  )
) {
  window.customCards.push({
    type: "vulcan-timetable-card",
    name: "Vulcan UONET+ — Plan lekcji",
    description:
      "Plan lekcji ucznia z automatycznym podglądem ostatniego planu z historii",
    preview: true,
  });
}

console.info(
  "%c VULCAN-TIMETABLE-CARD %c v1.0.0 załadowana",
  "color:#08111f;background:#8be9fd;font-weight:700;padding:3px 6px;border-radius:4px 0 0 4px;",
  "color:#8be9fd;background:#08111f;padding:3px 6px;border-radius:0 4px 4px 0;"
);

