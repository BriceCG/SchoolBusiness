/** @odoo-module **/

import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { browser } from "@web/core/browser/browser";

const STORAGE_KEY = "school_timetable_level";

export class TimetableCalendarModel extends CalendarModel {
    /**
     * Load the levels and choose the displayed one before the first load:
     * the level of the context, else the last one used, else the first one.
     */
    async load(params = {}) {
        if (!this.levels) {
            this.levels = await this.orm.searchRead("school.level", [], ["display_name"], {
                order: "sequence, name",
            });
            const context = params.context || this.meta.context || {};
            let id = context.default_level_id;
            if (!id && !context.timetable_all_levels) {
                try {
                    id = Number(browser.localStorage.getItem(STORAGE_KEY));
                } catch {
                    id = 0;
                }
            }
            if (!this.levels.some((level) => level.id === id)) {
                id = context.timetable_all_levels ? 0 : this.levels[0]?.id || 0;
            }
            this.levelId = id;
        }
        return super.load(params);
    }

    async setLevel(id) {
        this.levelId = id;
        try {
            browser.localStorage.setItem(STORAGE_KEY, id);
        } catch {
            // the choice is only a convenience
        }
        return this.load();
    }

    computeDomain(data) {
        const domain = super.computeDomain(data);
        if (this.levelId) {
            domain.push(["level_id", "=", this.levelId]);
        }
        return domain;
    }

    /** The selected level is the default of the new lessons. */
    makeContextDefaults(rawRecord) {
        const context = super.makeContextDefaults(rawRecord);
        if (this.levelId) {
            context.default_level_id = this.levelId;
        }
        return context;
    }
}

export class TimetableCalendarController extends CalendarController {
    onLevelChange(ev) {
        this.model.setLevel(parseInt(ev.target.value) || 0);
    }
}

export const timetableCalendarView = {
    ...calendarView,
    Controller: TimetableCalendarController,
    Model: TimetableCalendarModel,
    buttonTemplate: "school_business_backend.TimetableCalendarController.controlButtons",
};

registry.category("views").add("school_timetable_calendar", timetableCalendarView);
