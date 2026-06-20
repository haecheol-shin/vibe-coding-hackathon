const { createApp } = Vue;

const defaultUserProfile = {
  name: "",
  available_minutes: 0,
  availability_windows: [],
  invests_in_kospi: false,
};

function dayKey(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function todayKey() {
  return dayKey(0);
}

function formatDayLabel(key) {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];

  return `${month}월 ${day}일 (${weekdays[date.getDay()]})`;
}

function formatNytDate(key) {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekdays = [
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
  ];
  const months = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
  ];

  return `${weekdays[date.getDay()]}, ${months[month - 1]} ${day}, ${year}`;
}

function loadTodos() {
  const savedTodos = JSON.parse(localStorage.getItem("focusflow.todos") || "null") || [];
  const today = todayKey();
  const yesterday = dayKey(-1);

  return savedTodos
    .map((todo) => ({
      id: todo.id || crypto.randomUUID(),
      title: todo.title || "새 투두",
      duration_minutes: normalizeTodoMinutes(todo.duration_minutes),
      done: Boolean(todo.done),
      day: todo.day || today,
      carriedOver: Boolean(todo.carriedOver),
    }))
    // 어제·오늘·내일은 보드에 그대로 두고, 그보다 이전의 미완료만 오늘로 이어옵니다(완료된 과거는 정리).
    .filter((todo) => todo.day >= yesterday || !todo.done)
    .map((todo) => (todo.day < yesterday ? { ...todo, day: today, carriedOver: true } : todo));
}

function normalizeTodoMinutes(minutes) {
  const parsedMinutes = Number(minutes || 30);
  const safeMinutes = Number.isFinite(parsedMinutes) ? parsedMinutes : 30;

  return Math.min(480, Math.max(30, Math.ceil(safeMinutes / 30) * 30));
}

function loadUserProfile() {
  const savedProfile = JSON.parse(localStorage.getItem("focusflow.userProfile") || "null") || {};
  const savedAvailableMinutes = savedProfile.available_minutes ?? savedProfile.usage_minutes ?? 0;
  const savedWindows = Array.isArray(savedProfile.availability_windows) ? savedProfile.availability_windows : [];

  return {
    ...defaultUserProfile,
    ...savedProfile,
    available_minutes: Number(savedAvailableMinutes || 0),
    availability_windows: savedWindows.map((window) => ({
      id: window.id || crypto.randomUUID(),
      start: window.start || "09:00",
      end: window.end || "10:00",
    })),
    invests_in_kospi: Boolean(savedProfile.invests_in_kospi),
  };
}

function minutesFromTime(value) {
  const [hours, minutes] = value.split(":").map(Number);

  return hours * 60 + minutes;
}

function minutesToDegrees(minutes) {
  return (minutes / 1440) * 360;
}

function parseView() {
  const hash = window.location.hash.replace(/^#\/?/, "");

  return hash === "availability" ? "availability" : "todos";
}

createApp({
  data() {
    return {
      userProfile: loadUserProfile(),
      todos: loadTodos(),
      currentView: parseView(),
      newAvailabilityWindow: {
        start: "09:00",
        end: "10:00",
      },
      newTodoTitle: "",
      newTodoMinutes: 30,
      newTodoDay: "today",
      boardOffset: 0,
      sdkStatus: "Copilot SDK: checking",
      planMeta: "Ready",
      plan: null,
      planError: false,
      isPlanning: false,
    };
  },
  computed: {
    profileSummary() {
      const name = this.userProfile.name.trim() || "이름 미입력";
      const kospiStatus = this.userProfile.invests_in_kospi ? "코스피 투자 중" : "코스피 투자 안 함";

      return `${name} · 가용 시간 ${this.formatMinutes(this.totalAvailableMinutes)} · ${kospiStatus}`;
    },
    totalAvailableMinutes() {
      return this.userProfile.availability_windows.reduce((total, window) => total + this.windowMinutes(window), 0);
    },
    availableTimePercent() {
      return Math.min(100, Math.round((this.totalAvailableMinutes / 1440) * 100));
    },
    availableTimeRingStyle() {
      const segments = this.availabilitySegments;

      if (segments.length === 0) {
        return {
          background: "conic-gradient(from -90deg, rgba(31, 119, 109, 0.12) 0deg 360deg)",
        };
      }

      const gradientParts = [];
      let cursor = 0;

      segments.forEach((segment) => {
        if (segment.start > cursor) {
          gradientParts.push(`rgba(31, 119, 109, 0.12) ${cursor}deg ${segment.start}deg`);
        }

        gradientParts.push(`var(--teal) ${segment.start}deg ${segment.end}deg`);
        cursor = segment.end;
      });

      if (cursor < 360) {
        gradientParts.push(`rgba(31, 119, 109, 0.12) ${cursor}deg 360deg`);
      }

      return {
        background: `conic-gradient(from -90deg, ${gradientParts.join(", ")})`,
      };
    },
    availabilitySegments() {
      const segments = [];

      this.userProfile.availability_windows.forEach((window) => {
        const start = minutesFromTime(window.start);
        const end = minutesFromTime(window.end);
        const duration = this.windowMinutes(window);

        if (duration >= 1440) {
          segments.push({ start: 0, end: 360 });
        } else if (end > start) {
          segments.push({ start: minutesToDegrees(start), end: minutesToDegrees(end) });
        } else {
          segments.push({ start: minutesToDegrees(start), end: 360 });
          segments.push({ start: 0, end: minutesToDegrees(end) });
        }
      });

      return segments.sort((first, second) => first.start - second.start);
    },
    availableTimeSummary() {
      const count = this.userProfile.availability_windows.length;
      const windowText = count > 0 ? `${count}개 시간대` : "아직 시간대 없음";

      return `하루 24시간 기준 ${this.availableTimePercent}%를 확보했어요. ${windowText}, 총 ${this.formatMinutes(this.totalAvailableMinutes)}입니다.`;
    },
    timeOptions() {
      const options = [];

      for (let minutes = 0; minutes < 24 * 60; minutes += 30) {
        const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
        const mins = String(minutes % 60).padStart(2, "0");
        options.push(`${hours}:${mins}`);
      }

      return options;
    },
    newWindowMinutes() {
      return this.windowMinutes(this.newAvailabilityWindow);
    },
    yesterdayTodos() {
      return this.todosForDay(dayKey(-1));
    },
    todayTodos() {
      return this.todosForDay(todayKey());
    },
    tomorrowTodos() {
      return this.todosForDay(dayKey(1));
    },
    yesterdayLabel() {
      return formatDayLabel(dayKey(-1));
    },
    todayLabel() {
      return formatDayLabel(todayKey());
    },
    tomorrowLabel() {
      return formatDayLabel(dayKey(1));
    },
    yesterdayDate() {
      return formatNytDate(dayKey(-1));
    },
    todayDate() {
      return formatNytDate(todayKey());
    },
    tomorrowDate() {
      return formatNytDate(dayKey(1));
    },
    boardLabel() {
      if (this.boardOffset === -1) {
        return "어제";
      }

      return this.boardOffset === 1 ? "내일" : "오늘";
    },
    yesterdayUnfinished() {
      return this.yesterdayTodos.filter((todo) => !todo.done).length;
    },
    visibleCopilotNote() {
      const name = this.userProfile.name.trim() || "사용자";
      const kospiNote = this.userProfile.invests_in_kospi
        ? "코스피 확인 시간은 집중 블록과 분리해두는 편이 좋습니다."
        : "투자 확인 시간은 계획에 포함하지 않았습니다.";

      return `${name}님의 가용 시간 ${this.formatMinutes(this.totalAvailableMinutes)}을 기준으로 생성했습니다. ${kospiNote}`;
    },
  },
  mounted() {
    // loadTodos가 어제 항목을 오늘로 옮겼을 수 있으니 변경 사항을 저장합니다.
    this.saveTodos();
    if (!window.location.hash) {
      window.location.hash = "#/todos";
    }
    window.addEventListener("hashchange", this.syncView);
    this.checkCopilotSdk();
    this.askCopilot();
  },
  methods: {
    syncView() {
      this.currentView = parseView();
    },
    saveUserProfile() {
      this.userProfile.available_minutes = this.totalAvailableMinutes;
      localStorage.setItem("focusflow.userProfile", JSON.stringify(this.userProfile));
    },
    saveTodos() {
      localStorage.setItem("focusflow.todos", JSON.stringify(this.todos));
    },
    windowMinutes(window) {
      const start = minutesFromTime(window.start);
      const end = minutesFromTime(window.end);
      const duration = end > start ? end - start : end + 1440 - start;

      return Math.min(duration, 1440);
    },
    formatMinutes(minutes) {
      const hours = Math.floor(minutes / 60);
      const restMinutes = minutes % 60;

      return hours > 0 ? `${hours}시간 ${restMinutes}분` : `${restMinutes}분`;
    },
    addAvailabilityWindow() {
      this.userProfile.availability_windows.push({
        id: crypto.randomUUID(),
        start: this.newAvailabilityWindow.start,
        end: this.newAvailabilityWindow.end,
      });
      this.saveUserProfile();
    },
    removeAvailabilityWindow(windowId) {
      this.userProfile.availability_windows = this.userProfile.availability_windows.filter((window) => window.id !== windowId);
      this.saveUserProfile();
    },
    todoBlockCount(todo) {
      return Math.ceil(normalizeTodoMinutes(todo.duration_minutes) / 30);
    },
    todosForDay(day) {
      return this.todos
        .filter((todo) => todo.day === day)
        .sort((first, second) => Number(first.done) - Number(second.done));
    },
    blocksFor(list) {
      return list
        .filter((todo) => !todo.done)
        .reduce((total, todo) => total + this.todoBlockCount(todo), 0);
    },
    carryTodoToToday(todoId) {
      const todo = this.todos.find((item) => item.id === todoId);

      if (!todo) {
        return;
      }

      todo.day = todayKey();
      todo.carriedOver = true;
      this.boardOffset = 0;
      this.saveTodos();
      this.askCopilot();
    },
    carryAllToToday() {
      const today = todayKey();
      const yesterday = dayKey(-1);
      let moved = false;

      this.todos.forEach((todo) => {
        if (todo.day === yesterday && !todo.done) {
          todo.day = today;
          todo.carriedOver = true;
          moved = true;
        }
      });

      if (moved) {
        this.boardOffset = 0;
        this.saveTodos();
        this.askCopilot();
      }
    },
    prevDay() {
      if (this.boardOffset > -1) {
        this.boardOffset -= 1;
      }
    },
    nextDay() {
      if (this.boardOffset < 1) {
        this.boardOffset += 1;
      }
    },
    addTodo() {
      const title = this.newTodoTitle.trim();

      if (!title) {
        return;
      }

      this.todos.push({
        id: crypto.randomUUID(),
        title,
        duration_minutes: normalizeTodoMinutes(this.newTodoMinutes),
        done: false,
        day: this.newTodoDay === "tomorrow" ? dayKey(1) : todayKey(),
        carriedOver: false,
      });
      this.newTodoTitle = "";
      this.newTodoMinutes = 30;
      this.boardOffset = this.newTodoDay === "tomorrow" ? 1 : 0;
      this.saveTodos();
    },
    toggleTodo(todoId) {
      const todo = this.todos.find((item) => item.id === todoId);

      if (!todo) {
        return;
      }

      todo.done = !todo.done;
      todo.carriedOver = false;
      this.saveTodos();
      this.askCopilot();
    },
    removeTodo(todoId) {
      this.todos = this.todos.filter((todo) => todo.id !== todoId);
      this.saveTodos();
    },
    async checkCopilotSdk() {
      try {
        const response = await fetch("/copilotkit");

        if (!response.ok) {
          throw new Error("SDK unavailable");
        }

        const info = await response.json();
        const actionCount = Array.isArray(info.actions) ? info.actions.length : 0;
        this.sdkStatus = `Copilot SDK: ${actionCount} action`;
      } catch (error) {
        this.sdkStatus = "Copilot SDK: offline";
      }
    },
    async askCopilot() {
      this.isPlanning = true;
      this.planMeta = "Working";
      this.planError = false;

      const payload = {
        arguments: {
          tasks: this.todayTodos
            .filter((todo) => !todo.done)
            .map((todo) => ({
              title: todo.title,
              duration_minutes: normalizeTodoMinutes(todo.duration_minutes),
              block_count: this.todoBlockCount(todo),
            })),
          energy: "medium",
          available_minutes: 90,
          user_profile: {
            name: this.userProfile.name,
            available_minutes: this.totalAvailableMinutes,
            usage_minutes: this.totalAvailableMinutes,
            availability_windows: this.userProfile.availability_windows.map(({ start, end }) => ({ start, end })),
            invests_in_kospi: this.userProfile.invests_in_kospi,
          },
        },
      };

      try {
        const response = await fetch("/copilotkit/action/suggest_focus_plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error("Planning failed");
        }

        const data = await response.json();
        this.plan = data.result;
        this.planMeta = "Updated";
      } catch (error) {
        this.planError = true;
        this.planMeta = "Error";
      } finally {
        this.isPlanning = false;
      }
    },
  },
}).mount("#app");