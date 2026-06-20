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

function formatNytDate(key) {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekdays = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"];
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

function normalizeTodoMinutes(minutes) {
  const parsedMinutes = Number(minutes || 30);
  const safeMinutes = Number.isFinite(parsedMinutes) ? parsedMinutes : 30;

  return Math.min(480, Math.max(30, Math.ceil(safeMinutes / 30) * 30));
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
    .filter((todo) => todo.day >= yesterday || !todo.done)
    .map((todo) => (todo.day < yesterday ? { ...todo, day: today, carriedOver: true } : todo));
}

function loadStoredUserProfile() {
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

function isoDateDaysAgo(daysAgo) {
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() - daysAgo);
  return targetDate.toISOString().slice(0, 10);
}

function diaryHeadline(content) {
  const headline = content.trim().split("\n")[0] || "데모 다이어리";
  return headline.length <= 54 ? headline : `${headline.slice(0, 51)}...`;
}

function buildDemoMoodEntries() {
  const snippets = [
    "아침 루틴을 지키며 하루를 시작했다. 작은 습관이 컨디션을 떠받쳤다.",
    "집중 블록을 두 번 돌렸다. 방해 요소를 줄이니 진척이 보였다.",
    "회의가 길었지만 결론을 남겼다. 다음 액션이 분명해졌다.",
    "코드 리뷰에서 배운 점이 많았다. 피드백을 바로 반영하니 속도가 붙었다.",
    "작업량을 줄이고 우선순위에 집중했다. 마음이 한결 가벼워졌다.",
    "예상치 못한 이슈가 있었지만 차분히 처리했다. 회복 탄력을 느꼈다.",
    "일기 입력 기능 준비가 끝났다. 기분 점수와 시장 흐름을 함께 보는 아이디어가 데모 포인트가 됐다.",
  ];
  const scores = [6, 5, 7, 4, 6, 8, 7, 5, 6, 7, 5, 4, 6, 8, 7, 6, 5, 7, 6, 8, 5, 7, 6, 7, 4, 7, 6, 8, 7, 8];

  return scores.map((score, index) => {
    const daysAgo = scores.length - index - 1;
    const entryDate = isoDateDaysAgo(daysAgo);
    const content = snippets[index % snippets.length];

    return {
      entry_id: `demo-${entryDate}-${index}`,
      user_id: "demo-user",
      entry_date: entryDate,
      created_at: `${entryDate}T09:${String(index % 60).padStart(2, "0")}:00`,
      headline: diaryHeadline(content),
      content,
      mood_score: score,
      base_mood_score: score,
      kospi_change_rate: 0,
      adjusted_by_kospi: false,
      mood_sample_count: 1,
      message: "로그인 전 데모 다이어리 항목입니다.",
    };
  });
}

createApp({
  data() {
    const demoMoodEntries = buildDemoMoodEntries();
    const demoTodayDiary = demoMoodEntries[demoMoodEntries.length - 1];

    return {
      activeTab: "home",
      tabs: [
        { id: "home", label: "홈" },
        { id: "coach", label: "Copilot 코치" },
        { id: "diary", label: "다이어리" },
        { id: "news", label: "다이어리 뉴스" },
        { id: "availability", label: "가용 시간" },
        { id: "todos", label: "투두 보드" },
      ],
      chartRange: 7,
      chartRanges: [
        { days: 7, label: "7일" },
        { days: 30, label: "30일" },
      ],
      currentUser: null,
      authMeta: "",
      diaryText: localStorage.getItem("focusflow.diaryText") || demoTodayDiary.content,
      moodScore: Number(localStorage.getItem("focusflow.moodScore") || 5),
      diaryMeta: "데모 데이터",
      diaryError: false,
      savedDiary: demoTodayDiary,
      isSavingDiary: false,
      moodEntries: demoMoodEntries,
      kospiEntries: [],
      userProfile: loadStoredUserProfile(),
      todos: loadTodos(),
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
      coachRequest: localStorage.getItem("focusflow.coachRequest") || "오늘 남은 할 일을 기준으로 다음 행동, 집중 블록, 내일로 넘길 투두를 짧게 정리해줘.",
      coachAnswer: "",
      coachModel: "",
      coachMeta: "Ready",
      coachError: "",
      coachStats: null,
      isCoaching: false,
    };
  },
  computed: {
    dailyMoodEntries() {
      const groupedEntries = new Map();

      this.moodEntries.forEach((entry) => {
        const entries = groupedEntries.get(entry.entry_date) || [];
        entries.push(entry);
        groupedEntries.set(entry.entry_date, entries);
      });

      return [...groupedEntries.entries()]
        .map(([entryDate, entries]) => this.buildDailyMoodEntry(entryDate, entries))
        .sort((first, second) => first.entry_date.localeCompare(second.entry_date));
    },
    recentMoodEntries() {
      return this.dailyMoodEntries.slice(-this.chartRange);
    },
    moodPointRadius() {
      return this.recentMoodEntries.length <= 10 ? 5 : 0;
    },
    diaryNewsEntries() {
      return [...this.moodEntries]
        .sort((first, second) => {
          const firstTime = first.created_at || first.entry_date;
          const secondTime = second.created_at || second.entry_date;
          return secondTime.localeCompare(firstTime);
        })
        .slice(0, 10);
    },
    todayMoodEntry() {
      return this.savedDiary || this.recentMoodEntries[this.recentMoodEntries.length - 1] || null;
    },
    todayMoodScoreText() {
      return this.todayMoodEntry ? this.formatMoodValue(this.todayMoodEntry.mood_score) : "-";
    },
    moodAdjustmentText() {
      const entry = this.todayMoodEntry;
      const sampleCount = Number(entry?.mood_sample_count || 1);

      if (!entry || !entry.adjusted_by_kospi) {
        return sampleCount > 1 ? `오늘 ${sampleCount}번 입력한 기분 점수 평균입니다.` : "코스피 반영 전 점수입니다.";
      }

      const baseScore = Number(entry.base_mood_score);
      const finalScore = Number(entry.mood_score);
      const delta = Number((finalScore - baseScore).toFixed(2));
      const absoluteDelta = this.formatMoodValue(Math.abs(delta));
      const kospiRate = this.formatSignedPercent(entry.kospi_change_rate);

      if (sampleCount > 1) {
        return `오늘 ${sampleCount}번 입력한 기본 점수 평균 ${this.formatMoodValue(baseScore)}점에 코스피 ${kospiRate}를 반영한 최종 평균입니다.`;
      }

      if (delta < 0) {
        return `기본 ${this.formatMoodValue(baseScore)}점에서 코스피 ${kospiRate}로 ${absoluteDelta}점 깎여 현재 점수입니다.`;
      }

      if (delta > 0) {
        return `기본 ${this.formatMoodValue(baseScore)}점에서 코스피 ${kospiRate}로 ${absoluteDelta}점 더해져 현재 점수입니다.`;
      }

      return `기본 ${this.formatMoodValue(baseScore)}점에서 코스피 ${kospiRate}로 변동 없이 현재 점수입니다.`;
    },
    moodAdjustmentClass() {
      const entry = this.todayMoodEntry;

      if (!entry || !entry.adjusted_by_kospi) {
        return "flat";
      }

      const delta = Number(entry.mood_score) - Number(entry.base_mood_score);
      return delta === 0 ? "flat" : delta > 0 ? "up" : "down";
    },
    moodChartPoints() {
      const entries = this.recentMoodEntries;
      const width = 640;
      const height = 220;
      const paddingX = 52;
      const paddingY = 24;
      const usableWidth = width - paddingX * 2;
      const usableHeight = height - paddingY * 2;

      if (entries.length === 0) {
        return [];
      }

      const labelStep = Math.max(1, Math.ceil(entries.length / 7));

      return entries.map((entry, index) => {
        const x = entries.length === 1 ? width / 2 : paddingX + (usableWidth / (entries.length - 1)) * index;
        const y = paddingY + usableHeight - ((Number(entry.mood_score) - 1) / 9) * usableHeight;

        return {
          ...entry,
          x: Number(x.toFixed(2)),
          y: Number(y.toFixed(2)),
          showLabel: index % labelStep === 0 || index === entries.length - 1,
        };
      });
    },
    moodLinePath() {
      return this.moodChartPoints.map((point) => `${point.x},${point.y}`).join(" ");
    },
    moodAreaPath() {
      if (this.moodChartPoints.length === 0) {
        return "";
      }

      const baseline = 196;
      const first = this.moodChartPoints[0];
      const last = this.moodChartPoints[this.moodChartPoints.length - 1];
      const line = this.moodChartPoints.map((point) => `${point.x},${point.y}`).join(" ");
      return `${first.x},${baseline} ${line} ${last.x},${baseline}`;
    },
    recentKospiEntries() {
      return [...this.kospiEntries]
        .sort((first, second) => first.trading_date.localeCompare(second.trading_date))
        .slice(-this.chartRange);
    },
    kospiPointRadius() {
      return this.recentKospiEntries.length <= 10 ? 4.5 : 0;
    },
    kospiLatest() {
      return this.recentKospiEntries[this.recentKospiEntries.length - 1] || null;
    },
    kospiRange() {
      const values = this.recentKospiEntries.map((entry) => Number(entry.close));

      if (values.length === 0) {
        return { min: 0, max: 1 };
      }

      const min = Math.min(...values);
      const max = Math.max(...values);
      const buffer = Math.max((max - min) * 0.2, 10);

      return {
        min: Math.floor((min - buffer) / 10) * 10,
        max: Math.ceil((max + buffer) / 10) * 10,
      };
    },
    kospiAxisLevels() {
      const { min, max } = this.kospiRange;
      const step = (max - min) / 4;

      return Array.from({ length: 5 }, (_, index) => {
        const value = max - step * index;
        return {
          value,
          label: this.formatIndexValue(value),
          y: this.marketYForValue(value),
        };
      });
    },
    kospiChartPoints() {
      const entries = this.recentKospiEntries;
      const width = 640;
      const paddingX = 66;
      const usableWidth = width - paddingX * 2;

      if (entries.length === 0) {
        return [];
      }

      const labelStep = Math.max(1, Math.ceil(entries.length / 7));

      return entries.map((entry, index) => {
        const x = entries.length === 1 ? width / 2 : paddingX + (usableWidth / (entries.length - 1)) * index;

        return {
          ...entry,
          x: Number(x.toFixed(2)),
          y: this.marketYForValue(Number(entry.close)),
          showLabel: index % labelStep === 0 || index === entries.length - 1,
        };
      });
    },
    kospiLinePath() {
      return this.kospiChartPoints.map((point) => `${point.x},${point.y}`).join(" ");
    },
    kospiAreaPath() {
      if (this.kospiChartPoints.length === 0) {
        return "";
      }

      const baseline = 196;
      const first = this.kospiChartPoints[0];
      const last = this.kospiChartPoints[this.kospiChartPoints.length - 1];
      const line = this.kospiChartPoints.map((point) => `${point.x},${point.y}`).join(" ");
      return `${first.x},${baseline} ${line} ${last.x},${baseline}`;
    },
    kospiChangeClass() {
      if (!this.kospiLatest || this.kospiLatest.change === 0) {
        return "flat";
      }

      return this.kospiLatest.change > 0 ? "up" : "down";
    },
    profileSummary() {
      const name = this.userProfile.name.trim() || "이름 미입력";
      const kospiStatus = this.userProfile.invests_in_kospi ? "코스피 투자 중" : "코스피 투자 안 함";

      return `${name} · 가용 시간 ${this.formatMinutes(this.totalAvailableMinutes)} · ${kospiStatus}`;
    },
    totalAvailableMinutes() {
      return this.userProfile.availability_windows.reduce((total, window) => total + this.windowMinutes(window), 0);
    },
    effectiveAvailableMinutes() {
      return this.totalAvailableMinutes || 90;
    },
    availableTimePercent() {
      return Math.min(100, Math.round((this.totalAvailableMinutes / 1440) * 100));
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
    availableTimeRingStyle() {
      const segments = this.availabilitySegments;

      if (segments.length === 0) {
        return { background: "conic-gradient(from -90deg, rgba(77, 141, 255, 0.12) 0deg 360deg)" };
      }

      const gradientParts = [];
      let cursor = 0;

      segments.forEach((segment) => {
        if (segment.start > cursor) {
          gradientParts.push(`rgba(77, 141, 255, 0.12) ${cursor}deg ${segment.start}deg`);
        }

        gradientParts.push(`var(--teal) ${segment.start}deg ${segment.end}deg`);
        cursor = segment.end;
      });

      if (cursor < 360) {
        gradientParts.push(`rgba(77, 141, 255, 0.12) ${cursor}deg 360deg`);
      }

      return { background: `conic-gradient(from -90deg, ${gradientParts.join(", ")})` };
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
    openTodayTodos() {
      return this.todayTodos.filter((todo) => !todo.done);
    },
    completedTodayTodos() {
      return this.todayTodos.filter((todo) => todo.done);
    },
    coachMoodLabel() {
      const score = Number(this.todayMoodEntry?.mood_score || this.moodScore || 5);

      if (score <= 4) {
        return "low";
      }

      if (score >= 8) {
        return "high";
      }

      return "steady";
    },
    coachEnergyLevel() {
      const score = Number(this.todayMoodEntry?.mood_score || this.moodScore || 5);

      if (score <= 3) {
        return 2;
      }

      if (score >= 8) {
        return 5;
      }

      return 3;
    },
    coachContextSummary() {
      const openCount = this.openTodayTodos.length;
      const diaryStatus = this.savedDiary ? "일기 반영" : "일기 없음";

      return `${openCount}개 미완료 · ${this.formatMinutes(this.effectiveAvailableMinutes)} · ${diaryStatus}`;
    },
    tomorrowSuggestions() {
      const explicitTomorrowTodos = this.tomorrowTodos.filter((todo) => !todo.done);
      const sourceTodos = explicitTomorrowTodos.length ? explicitTomorrowTodos : this.openTodayTodos;
      const moodScore = Number(this.todayMoodEntry?.mood_score || this.moodScore || 5);
      const maxMinutes = moodScore <= 4 ? 30 : 60;

      return sourceTodos.slice(0, 4).map((todo, index) => ({
        id: `suggestion-${todo.id}`,
        title: explicitTomorrowTodos.length ? todo.title : `${todo.title} 이어가기`,
        duration_minutes: Math.min(normalizeTodoMinutes(todo.duration_minutes), maxMinutes),
        priority: index === 0 ? "high" : "medium",
        reason: explicitTomorrowTodos.length ? "내일 보드에 이미 예약됨" : "오늘 미완료 작업에서 Copilot 코치 컨텍스트로 전달됨",
      }));
    },
    visibleCopilotNote() {
      const name = this.userProfile.name.trim() || "사용자";
      const kospiNote = this.userProfile.invests_in_kospi
        ? "코스피 확인 시간은 집중 블록과 분리해두는 편이 좋습니다."
        : "투자 확인 시간은 계획에 포함하지 않았습니다.";

      return `${name}님의 가용 시간 ${this.formatMinutes(this.effectiveAvailableMinutes)}을 기준으로 생성했습니다. ${kospiNote}`;
    },
  },
  async mounted() {
    this.saveTodos();
    this.readAuthStatus();
    await this.fetchCurrentUser();

    if (this.currentUser) {
      await Promise.all([this.loadTodayDiary(), this.loadMoodEntries()]);
    }

    await this.loadKospiEntries();
    await this.checkCopilotSdk();
    await this.askCopilot();
  },
  methods: {
    setActiveTab(tabId) {
      this.activeTab = tabId;
    },
    setChartRange(days) {
      this.chartRange = days;
    },
    readAuthStatus() {
      const params = new URLSearchParams(window.location.search);
      const authStatus = params.get("auth");

      if (authStatus === "success") {
        this.authMeta = "깃허브 회원가입이 완료되었습니다";
      } else if (authStatus === "local") {
        this.authMeta = "로컬 깃허브 인증으로 로그인되었습니다";
      } else if (authStatus === "cancelled") {
        this.authMeta = "깃허브 회원가입이 취소되었습니다";
      }

      if (authStatus) {
        params.delete("auth");
        const query = params.toString();
        window.history.replaceState({}, "", query ? `/?${query}` : "/");
      }
    },
    async fetchCurrentUser() {
      try {
        const response = await fetch("/api/users/profile");

        if (!response.ok) {
          return;
        }

        this.currentUser = await response.json();
      } catch (error) {
        this.currentUser = null;
      }
    },
    buildLocalDiaryEntry(content, moodScore) {
      const entryDate = new Date().toISOString().slice(0, 10);
      const kospiRate = Number(this.kospiLatest?.change_rate || 0);
      const adjustedMoodScore = Number(Math.min(10, Math.max(1, moodScore + kospiRate)).toFixed(2));

      return {
        entry_id: `demo-local-${Date.now()}`,
        user_id: "demo-user",
        entry_date: entryDate,
        created_at: new Date().toISOString(),
        headline: diaryHeadline(content),
        content,
        mood_score: adjustedMoodScore,
        base_mood_score: moodScore,
        kospi_change_rate: kospiRate,
        adjusted_by_kospi: true,
        mood_sample_count: 1,
        message: "로그인 전 데모 다이어리로 저장했습니다.",
      };
    },
    buildDailyMoodEntry(entryDate, entries) {
      const sortedEntries = [...entries].sort((first, second) => {
        const firstTime = first.created_at || first.entry_date;
        const secondTime = second.created_at || second.entry_date;
        return firstTime.localeCompare(secondTime);
      });
      const latestEntry = sortedEntries[sortedEntries.length - 1];
      const adjustedEntries = sortedEntries.filter((entry) => entry.adjusted_by_kospi);
      const finalScores = sortedEntries.map((entry) => Number(entry.mood_score));
      const baseScores = sortedEntries.map((entry) => Number(entry.base_mood_score ?? entry.mood_score));

      return {
        ...latestEntry,
        entry_id: `daily-${entryDate}`,
        entry_date: entryDate,
        headline: `${entryDate} 평균 기분 점수`,
        mood_score: this.averageValues(finalScores),
        base_mood_score: this.averageValues(baseScores),
        kospi_change_rate: adjustedEntries.length ? adjustedEntries[adjustedEntries.length - 1].kospi_change_rate : null,
        adjusted_by_kospi: adjustedEntries.length > 0,
        mood_sample_count: sortedEntries.length,
      };
    },
    averageValues(values) {
      return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
    },
    formatDateLabel(entryDate) {
      return entryDate.slice(5).replace("-", "/");
    },
    formatNewsDate(value) {
      const source = value.includes("T") ? value.slice(0, 10) : value;
      return source.replaceAll("-", ".");
    },
    diaryPreview(content) {
      const preview = content.trim().replace(/\s+/g, " ");
      return preview.length <= 96 ? preview : `${preview.slice(0, 93)}...`;
    },
    formatIndexValue(value) {
      return Number(value).toLocaleString("ko-KR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    },
    formatMoodValue(value) {
      return Number(value).toLocaleString("ko-KR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
    },
    formatSignedValue(value) {
      const numericValue = Number(value);
      const prefix = numericValue > 0 ? "+" : "";
      return `${prefix}${this.formatIndexValue(numericValue)}`;
    },
    formatSignedPercent(value) {
      const numericValue = Number(value);
      const prefix = numericValue > 0 ? "+" : "";
      return `${prefix}${numericValue.toFixed(2)}%`;
    },
    marketYForValue(value) {
      const height = 220;
      const paddingY = 24;
      const usableHeight = height - paddingY * 2;
      const { min, max } = this.kospiRange;
      const ratio = max === min ? 0.5 : (Number(value) - min) / (max - min);
      const y = paddingY + usableHeight - ratio * usableHeight;
      return Number(y.toFixed(2));
    },
    async loadMoodEntries() {
      try {
        const response = await fetch("/api/diaries");

        if (!response.ok) {
          return;
        }

        this.moodEntries = await response.json();
      } catch (error) {
        return;
      }
    },
    async loadKospiEntries() {
      try {
        const response = await fetch("/api/markets/kospi");

        if (!response.ok) {
          return;
        }

        this.kospiEntries = await response.json();
      } catch (error) {
        return;
      }
    },
    async loadTodayDiary() {
      try {
        const response = await fetch("/api/diaries/today");

        if (!response.ok) {
          return;
        }

        const diary = await response.json();
        this.savedDiary = diary;
        this.diaryText = diary.content;
        this.diaryMeta = "불러옴";
        localStorage.setItem("focusflow.diaryText", this.diaryText);
      } catch (error) {
        this.savedDiary = null;
        this.diaryMeta = "준비됨";
      }
    },
    async deleteDiary(entry) {
      if (!entry.entry_id) {
        return;
      }

      if (!this.currentUser) {
        this.moodEntries = this.moodEntries.filter((diary) => diary.entry_id !== entry.entry_id);
        this.savedDiary = this.recentMoodEntries[this.recentMoodEntries.length - 1] || null;
        this.diaryMeta = "데모 삭제됨";
        return;
      }

      try {
        const response = await fetch(`/api/diaries/${encodeURIComponent(entry.entry_id)}`, {
          method: "DELETE",
        });

        if (!response.ok) {
          throw new Error("다이어리 삭제 실패");
        }

        this.moodEntries = this.moodEntries.filter((diary) => diary.entry_id !== entry.entry_id);

        if (this.savedDiary?.entry_date === entry.entry_date) {
          await this.loadTodayDiary();
        }
      } catch (error) {
        this.diaryMeta = "삭제 실패";
      }
    },
    async saveDiary() {
      const content = this.diaryText.trim();

      if (!content) {
        this.diaryError = true;
        this.diaryMeta = "먼저 작성하세요";
        return;
      }

      this.isSavingDiary = true;
      this.diaryError = false;
      this.diaryMeta = "저장 중";
      const submittedMoodScore = Number(this.moodScore);

      if (!this.currentUser) {
        const diary = this.buildLocalDiaryEntry(content, submittedMoodScore);
        this.moodEntries = [...this.moodEntries, diary];
        this.savedDiary = this.buildDailyMoodEntry(
          diary.entry_date,
          this.moodEntries.filter((entry) => entry.entry_date === diary.entry_date)
        );
        this.diaryText = diary.content;
        this.moodScore = submittedMoodScore;
        this.diaryMeta = "데모 저장됨";
        localStorage.setItem("focusflow.diaryText", this.diaryText);
        localStorage.setItem("focusflow.moodScore", String(this.moodScore));
        this.isSavingDiary = false;
        return;
      }

      try {
        const response = await fetch("/api/diaries/today", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content,
            mood_score: submittedMoodScore,
          }),
        });

        if (!response.ok) {
          throw new Error("다이어리 저장 실패");
        }

        const diary = await response.json();
        this.savedDiary = diary;
        this.diaryText = diary.content;
        this.moodScore = submittedMoodScore;
        this.diaryMeta = "저장됨";
        localStorage.setItem("focusflow.diaryText", this.diaryText);
        localStorage.setItem("focusflow.moodScore", String(this.moodScore));
        await this.loadMoodEntries();
      } catch (error) {
        this.diaryError = true;
        this.diaryMeta = "오류";
      } finally {
        this.isSavingDiary = false;
      }
    },
    saveUserProfile() {
      this.userProfile.available_minutes = this.totalAvailableMinutes;
      localStorage.setItem("focusflow.userProfile", JSON.stringify(this.userProfile));
      this.askCopilot();
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
      this.askCopilot();
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
      this.askCopilot();
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
    buildCoachPrompt() {
      const diary = this.savedDiary?.content || this.diaryText || "아직 저장된 일기가 없습니다.";
      const taskLines = this.todayTodos.length
        ? this.todayTodos.map((todo) => `- ${todo.done ? "완료" : "미완료"}: ${todo.title} (${this.formatMinutes(todo.duration_minutes)})`).join("\n")
        : "- 오늘 투두가 아직 없습니다.";
      const marketLine = this.kospiLatest
        ? `코스피 ${this.formatIndexValue(this.kospiLatest.close)}, 변동률 ${this.formatSignedPercent(this.kospiLatest.change_rate)}`
        : "코스피 데이터 없음";

      return [
        this.coachRequest.trim(),
        "",
        "응답 형식:",
        "1. 다음 행동 한 줄",
        "2. 오늘 집중 블록 2-4개",
        "3. 내일 투두 초안 2-4개",
        "4. 무리하지 않기 위한 짧은 조언",
        "",
        `사용자: ${this.userProfile.name.trim() || "익명"}`,
        `가용 시간: ${this.formatMinutes(this.effectiveAvailableMinutes)}`,
        `기분 점수: ${this.todayMoodScoreText}/10 (${this.coachMoodLabel})`,
        `시장 맥락: ${marketLine}`,
        `오늘 일기: ${diary.slice(0, 900)}`,
        "오늘 투두:",
        taskLines,
      ].join("\n");
    },
    async runCopilotCoach() {
      const prompt = this.buildCoachPrompt();

      this.isCoaching = true;
      this.coachMeta = "Calling SDK";
      this.coachError = "";
      localStorage.setItem("focusflow.coachRequest", this.coachRequest.trim());

      try {
        const response = await fetch("/api/productivity/coach", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request: prompt,
            user_profile: {
              name: this.userProfile.name,
              available_minutes: this.effectiveAvailableMinutes,
              usage_minutes: this.effectiveAvailableMinutes,
              availability_windows: this.userProfile.availability_windows.map(({ start, end }) => ({ start, end })),
              invests_in_kospi: this.userProfile.invests_in_kospi,
            },
            energy: this.coachEnergyLevel,
            mood: this.coachMoodLabel,
            focus_sessions: this.completedTodayTodos.length,
            tasks: this.todayTodos.map((todo, index) => ({
              title: todo.title,
              priority: todo.carriedOver || index === 0 ? "high" : "medium",
              done: todo.done,
            })),
          }),
        });

        if (!response.ok) {
          let detail = "Copilot 코치 요청에 실패했습니다.";
          try {
            const payload = await response.json();
            detail = payload.detail || detail;
          } catch (error) {
            detail = "Copilot 코치 응답을 읽을 수 없습니다.";
          }
          throw new Error(detail);
        }

        const payload = await response.json();
        this.coachAnswer = payload.answer;
        this.coachModel = payload.model;
        this.coachStats = {
          open_tasks: payload.open_tasks,
          completed_tasks: payload.completed_tasks,
        };
        this.coachMeta = "SDK Ready";
        await this.askCopilot();
      } catch (error) {
        this.coachError = error.message || "Copilot 코치 요청에 실패했습니다.";
        this.coachMeta = "SDK Offline";
      } finally {
        this.isCoaching = false;
      }
    },
    importTomorrowSuggestions() {
      const tomorrow = dayKey(1);
      let imported = false;

      this.tomorrowSuggestions.forEach((suggestion) => {
        const exists = this.todos.some((todo) => todo.day === tomorrow && todo.title === suggestion.title);
        if (exists) {
          return;
        }

        this.todos.push({
          id: crypto.randomUUID(),
          title: suggestion.title,
          duration_minutes: normalizeTodoMinutes(suggestion.duration_minutes),
          done: false,
          day: tomorrow,
          carriedOver: false,
        });
        imported = true;
      });

      if (imported) {
        this.boardOffset = 1;
        this.saveTodos();
        this.askCopilot();
      }
    },
    async askCopilot() {
      this.isPlanning = true;
      this.planMeta = "Working";
      this.planError = false;

      try {
        const response = await fetch("/api/productivity/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tasks: this.todayTodos
              .filter((todo) => !todo.done)
              .map((todo) => ({
                title: todo.title,
                duration_minutes: normalizeTodoMinutes(todo.duration_minutes),
                block_count: this.todoBlockCount(todo),
              })),
            energy: "medium",
            available_minutes: this.effectiveAvailableMinutes,
            user_profile: {
              name: this.userProfile.name,
              available_minutes: this.effectiveAvailableMinutes,
              usage_minutes: this.effectiveAvailableMinutes,
              availability_windows: this.userProfile.availability_windows.map(({ start, end }) => ({ start, end })),
              invests_in_kospi: this.userProfile.invests_in_kospi,
            },
          }),
        });

        if (!response.ok) {
          throw new Error("Plan unavailable");
        }

        this.plan = await response.json();
        this.planMeta = "Ready";
      } catch (error) {
        this.plan = null;
        this.planError = true;
        this.planMeta = "Offline";
      } finally {
        this.isPlanning = false;
      }
    },
  },
}).mount("#app");
