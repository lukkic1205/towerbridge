class VulcanGradesCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("vulcan-grades-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find((entityId) => {
      const stateObj = hass.states[entityId];
      return (
        entityId.startsWith("sensor.") &&
        Array.isArray(stateObj?.attributes?.grades)
      );
    });

    return {
      entity: entity || "",
      title: "Oceny",
      max_items: 10,
      show_header: true,
      show_category: true,
      show_weight: true,
      show_teacher: false,
      show_updated: true,
      compact: false,
    };
  }

  setConfig(config) {
    this.config = {
      entity: "",
      title: "Oceny",
      max_items: 10,
      show_header: true,
      show_teacher: false,
      show_weight: true,
      show_category: true,
      show_updated: true,
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

  getCardSize() {
    const count = Number(this.config?.max_items || 10);
    return Math.max(3, Math.ceil(count / 2));
  }

  getGridOptions() {
    return {
      columns: 12,
      rows: "auto",
      min_columns: 6,
      min_rows: 3,
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

  formatDate(value, withTime = false) {
    if (!value) return "";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return new Intl.DateTimeFormat("pl-PL", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      ...(withTime
        ? {
            hour: "2-digit",
            minute: "2-digit",
          }
        : {}),
    }).format(date);
  }

  gradeStyle(grade) {
    const rawValue = grade?.value;
    const value =
      rawValue === null || rawValue === undefined || rawValue === ""
        ? Number.NaN
        : Number(rawValue);

    const content = String(grade?.content ?? "").trim();

    if (!Number.isNaN(value)) {
      if (value >= 5) {
        return {
          color: "#4ade80",
          background: "rgba(74, 222, 128, 0.14)",
          border: "rgba(74, 222, 128, 0.28)",
        };
      }

      if (value >= 4) {
        return {
          color: "#8be9fd",
          background: "rgba(139, 233, 253, 0.13)",
          border: "rgba(139, 233, 253, 0.27)",
        };
      }

      if (value >= 3) {
        return {
          color: "#facc15",
          background: "rgba(250, 204, 21, 0.13)",
          border: "rgba(250, 204, 21, 0.27)",
        };
      }

      return {
        color: "#fb7185",
        background: "rgba(251, 113, 133, 0.13)",
        border: "rgba(251, 113, 133, 0.27)",
      };
    }

    if (content.includes("+")) {
      return {
        color: "#c4b5fd",
        background: "rgba(196, 181, 253, 0.13)",
        border: "rgba(196, 181, 253, 0.27)",
      };
    }

    return {
      color: "#94a3b8",
      background: "rgba(148, 163, 184, 0.12)",
      border: "rgba(148, 163, 184, 0.24)",
    };
  }

  render() {
    if (!this.shadowRoot || !this.config) return;

    const entityId = this.config.entity;
    const stateObj = this._hass?.states?.[entityId];

    if (!entityId) {
      this.shadowRoot.innerHTML = `
        ${this.cardStyles()}
        <ha-card>
          <div class="error">
            Wybierz encję ocen Vulcan w konfiguracji karty.
          </div>
        </ha-card>
      `;
      return;
    }

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        ${this.cardStyles()}
        <ha-card>
          <div class="error">
            Nie znaleziono encji:
            <strong>${this.escapeHtml(entityId)}</strong>
          </div>
        </ha-card>
      `;
      return;
    }

    const attrs = stateObj.attributes || {};
    let grades = Array.isArray(attrs.grades) ? [...attrs.grades] : [];

    if (this.config.subject) {
      const expected = String(this.config.subject).trim().toLowerCase();
      grades = grades.filter((grade) =>
        String(grade.subject || "")
          .trim()
          .toLowerCase()
          .includes(expected)
      );
    }

    grades.sort((a, b) => {
      const dateA = new Date(a.date_created || 0).getTime();
      const dateB = new Date(b.date_created || 0).getTime();
      return dateB - dateA;
    });

    const allMatchingCount = grades.length;
    const maxItems = Math.max(1, Number(this.config.max_items || 10));
    grades = grades.slice(0, maxItems);

    const studentName =
      attrs.first_name ||
      attrs.full_name ||
      stateObj.attributes.friendly_name ||
      "Uczeń";

    const title =
      this.config.title === false
        ? ""
        : this.config.title || `Oceny — ${studentName}`;

    const subtitleParts = [
      attrs.class ? `klasa ${attrs.class}` : "",
      attrs.school || attrs.unit || "",
    ].filter(Boolean);

    const compactClass = this.config.compact ? "compact" : "";

    const rows = grades
      .map((grade) => {
        const style = this.gradeStyle(grade);

        const description =
          grade.column_name ||
          grade.category ||
          grade.comment ||
          "Ocena bieżąca";

        const meta = [];

        if (this.config.show_category && grade.category) {
          meta.push(this.escapeHtml(grade.category));
        }

        if (
          this.config.show_weight &&
          grade.weight !== undefined &&
          grade.weight !== null
        ) {
          meta.push(`waga ${this.escapeHtml(grade.weight)}`);
        }

        if (this.config.show_teacher && grade.teacher) {
          meta.push(this.escapeHtml(grade.teacher));
        }

        return `
          <div class="grade-row">
            <div
              class="grade-badge"
              style="
                color:${style.color};
                background:${style.background};
                border-color:${style.border};
              "
            >
              ${this.escapeHtml(grade.content || "–")}
            </div>

            <div class="grade-main">
              <div class="subject">
                ${this.escapeHtml(grade.subject || "Bez przedmiotu")}
              </div>

              <div class="description">
                ${this.escapeHtml(description)}
              </div>

              ${
                meta.length
                  ? `<div class="meta">${meta.join(" · ")}</div>`
                  : ""
              }
            </div>

            <div class="date">
              ${this.escapeHtml(this.formatDate(grade.date_created))}
            </div>
          </div>
        `;
      })
      .join("");

    const emptyState = `
      <div class="empty">
        <ha-icon icon="mdi:star-off-outline"></ha-icon>
        <span>Brak ocen do wyświetlenia</span>
      </div>
    `;

    this.shadowRoot.innerHTML = `
      ${this.cardStyles()}

      <ha-card class="${compactClass}">
        <div class="content">
          ${
            this.config.show_header
              ? `
                <div class="header">
                  <div>
                    <div class="title">
                      ⭐ ${this.escapeHtml(title)}
                    </div>
                    ${
                      subtitleParts.length
                        ? `<div class="subtitle">${this.escapeHtml(
                            subtitleParts.join(" · ")
                          )}</div>`
                        : ""
                    }
                  </div>

                  <div class="counter">
                    ${grades.length} z ${allMatchingCount}
                  </div>
                </div>
              `
              : ""
          }

          <div class="grades">
            ${grades.length ? rows : emptyState}
          </div>

          ${
            this.config.show_updated && attrs.updated_at
              ? `
                <div class="updated">
                  Aktualizacja:
                  ${this.escapeHtml(this.formatDate(attrs.updated_at, true))}
                </div>
              `
              : ""
          }
        </div>
      </ha-card>
    `;
  }

  cardStyles() {
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
            radial-gradient(
              circle at 0% 0%,
              rgba(56, 189, 248, 0.17),
              transparent 38%
            ),
            radial-gradient(
              circle at 100% 0%,
              rgba(250, 204, 21, 0.10),
              transparent 34%
            ),
            linear-gradient(
              145deg,
              rgba(18, 27, 41, 0.97),
              rgba(7, 13, 22, 0.99)
            );
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
          align-items: center;
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
          margin-top: 4px;
          color: #94a3b8;
          font-size: 12px;
        }

        .counter {
          flex: 0 0 auto;
          padding: 7px 11px;
          border-radius: 12px;
          color: #8be9fd;
          font-size: 12px;
          font-weight: 700;
          background: rgba(56, 189, 248, 0.12);
          border: 1px solid rgba(56, 189, 248, 0.23);
        }

        .grades {
          display: flex;
          flex-direction: column;
          gap: 7px;
        }

        .grade-row {
          display: grid;
          grid-template-columns: 52px minmax(0, 1fr) auto;
          align-items: center;
          gap: 11px;
          padding: 10px 8px;
          border-radius: 15px;
          background: rgba(255, 255, 255, 0.025);
          border: 1px solid rgba(148, 163, 184, 0.10);
        }

        .grade-badge {
          display: flex;
          align-items: center;
          justify-content: center;
          box-sizing: border-box;
          width: 43px;
          min-width: 43px;
          height: 43px;
          border: 1px solid;
          border-radius: 13px;
          font-size: 22px;
          font-weight: 900;
        }

        .grade-main {
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

        .description {
          margin-top: 3px;
          color: #a8b3c3;
          font-size: 12px;
          line-height: 1.3;
          overflow-wrap: anywhere;
        }

        .meta {
          margin-top: 4px;
          color: #64748b;
          font-size: 10px;
          line-height: 1.25;
        }

        .date {
          align-self: start;
          padding-top: 2px;
          color: #64748b;
          font-size: 10px;
          white-space: nowrap;
        }

        .updated {
          margin-top: 10px;
          color: #64748b;
          font-size: 9px;
          text-align: right;
        }

        .empty {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          min-height: 90px;
          color: #94a3b8;
        }

        .error {
          padding: 18px;
          color: #fecaca;
          background: rgba(127, 29, 29, 0.28);
        }

        .compact .grade-row {
          grid-template-columns: 44px minmax(0, 1fr) auto;
          gap: 8px;
          padding: 7px 6px;
        }

        .compact .grade-badge {
          width: 36px;
          min-width: 36px;
          height: 36px;
          border-radius: 11px;
          font-size: 18px;
        }

        .compact .subject {
          font-size: 13px;
        }

        .compact .description {
          font-size: 11px;
        }
      </style>
    `;
  }
}


class VulcanGradesCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = {
      entity: "",
      title: "Oceny",
      max_items: 10,
      show_header: true,
      show_category: true,
      show_weight: true,
      show_teacher: false,
      show_updated: true,
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

  getGradeEntities() {
    if (!this._hass?.states) return [];

    return Object.entries(this._hass.states)
      .filter(([entityId, stateObj]) => {
        return (
          entityId.startsWith("sensor.") &&
          Array.isArray(stateObj?.attributes?.grades)
        );
      })
      .sort((a, b) => {
        const nameA =
          a[1].attributes?.friendly_name || a[0];
        const nameB =
          b[1].attributes?.friendly_name || b[0];

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
    const newConfig = {
      ...this._config,
      [key]: value,
    };

    if (key === "subject" && !value) {
      delete newConfig.subject;
    }

    this._config = newConfig;
    this.fireConfigChanged(newConfig);
    this.render();
  }

  render() {
    if (!this.shadowRoot || !this._config) return;

    const entities = this.getGradeEntities();

    const entityOptions = [
      `<option value="">— wybierz encję ocen —</option>`,
      ...entities.map(([entityId, stateObj]) => {
        const name =
          stateObj.attributes?.friendly_name || entityId;
        const selected =
          this._config.entity === entityId ? "selected" : "";

        return `
          <option
            value="${this.escapeHtml(entityId)}"
            ${selected}
          >
            ${this.escapeHtml(name)} — ${this.escapeHtml(entityId)}
          </option>
        `;
      }),
    ].join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          box-sizing: border-box;
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
          color: var(--primary-text-color);
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
        input[type="text"]:focus,
        input[type="number"]:focus {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
        }

        .switches {
          display: grid;
          gap: 4px;
          padding-top: 2px;
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

        .switch-label {
          color: var(--primary-text-color);
          font-size: 14px;
        }

        input[type="checkbox"] {
          width: 20px;
          height: 20px;
          accent-color: var(--primary-color);
          cursor: pointer;
        }

        .warning {
          padding: 12px;
          border-radius: 10px;
          color: var(--warning-color, #ff9800);
          background: color-mix(
            in srgb,
            var(--warning-color, #ff9800) 12%,
            transparent
          );
          font-size: 13px;
          line-height: 1.4;
        }
      </style>

      <div class="editor">
        ${
          entities.length === 0
            ? `
              <div class="warning">
                Nie znaleziono żadnej encji sensora z atrybutem
                <strong>grades</strong>. Sprawdź, czy integracja Vulcan
                utworzyła encję ocen.
              </div>
            `
            : ""
        }

        <div class="field">
          <label for="entity">Encja ocen</label>
          <select id="entity">
            ${entityOptions}
          </select>
          <div class="hint">
            Lista pokazuje wyłącznie sensory zawierające atrybut grades.
          </div>
        </div>

        <div class="field">
          <label for="title">Tytuł karty</label>
          <input
            id="title"
            type="text"
            value="${this.escapeHtml(this._config.title ?? "")}"
            placeholder="Oceny"
          />
        </div>

        <div class="field">
          <label for="max_items">Liczba wyświetlanych ocen</label>
          <input
            id="max_items"
            type="number"
            min="1"
            max="50"
            step="1"
            value="${this.escapeHtml(this._config.max_items ?? 10)}"
          />
        </div>

        <div class="field">
          <label for="subject">Filtr przedmiotu</label>
          <input
            id="subject"
            type="text"
            value="${this.escapeHtml(this._config.subject ?? "")}"
            placeholder="np. Matematyka — pozostaw puste dla wszystkich"
          />
        </div>

        <div class="switches">
          ${this.switchRow(
            "show_header",
            "Pokazuj nagłówek",
            this._config.show_header
          )}
          ${this.switchRow(
            "show_category",
            "Pokazuj kategorię",
            this._config.show_category
          )}
          ${this.switchRow(
            "show_weight",
            "Pokazuj wagę",
            this._config.show_weight
          )}
          ${this.switchRow(
            "show_teacher",
            "Pokazuj nauczyciela",
            this._config.show_teacher
          )}
          ${this.switchRow(
            "show_updated",
            "Pokazuj czas aktualizacji",
            this._config.show_updated
          )}
          ${this.switchRow(
            "compact",
            "Tryb kompaktowy",
            this._config.compact
          )}
        </div>
      </div>
    `;

    this.bindEvents();
  }

  switchRow(id, label, checked) {
    return `
      <label class="switch-row" for="${id}">
        <span class="switch-label">${this.escapeHtml(label)}</span>
        <input
          id="${id}"
          type="checkbox"
          ${checked ? "checked" : ""}
        />
      </label>
    `;
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

    root.getElementById("max_items")?.addEventListener("change", (event) => {
      const value = Math.min(
        50,
        Math.max(1, Number.parseInt(event.target.value, 10) || 10)
      );
      this.updateConfig("max_items", value);
    });

    root.getElementById("subject")?.addEventListener("change", (event) => {
      this.updateConfig("subject", event.target.value.trim());
    });

    [
      "show_header",
      "show_category",
      "show_weight",
      "show_teacher",
      "show_updated",
      "compact",
    ].forEach((key) => {
      root.getElementById(key)?.addEventListener("change", (event) => {
        this.updateConfig(key, event.target.checked);
      });
    });
  }
}


if (!customElements.get("vulcan-grades-card-editor")) {
  customElements.define(
    "vulcan-grades-card-editor",
    VulcanGradesCardEditor
  );
}

if (!customElements.get("vulcan-grades-card")) {
  customElements.define("vulcan-grades-card", VulcanGradesCard);
}

window.customCards = window.customCards || [];

if (
  !window.customCards.some(
    (card) => card.type === "vulcan-grades-card"
  )
) {
  window.customCards.push({
    type: "vulcan-grades-card",
    name: "Vulcan UONET+ — Oceny",
    description:
      "Karta ocen ucznia z integracji Vulcan UONET+",
    preview: true,
    documentationURL:
      "https://github.com/lukkic1205/towerbridge",
  });
}

console.info(
  "%c VULCAN-GRADES-CARD %c v1.0.4 załadowana",
  "color:#08111f;background:#8be9fd;font-weight:700;padding:3px 6px;border-radius:4px 0 0 4px;",
  "color:#8be9fd;background:#08111f;padding:3px 6px;border-radius:0 4px 4px 0;"
);
