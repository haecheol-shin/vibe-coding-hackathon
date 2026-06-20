const { createApp } = Vue;

const defaultTasks = [
  { id: crypto.randomUUID(), title: "Finish the product pitch", priority: "high" },
  { id: crypto.randomUUID(), title: "Review today's calendar", priority: "normal" },
  { id: crypto.randomUUID(), title: "Prepare deployment checklist", priority: "high" },
];

createApp({
  data() {
    return {
      tasks: JSON.parse(localStorage.getItem("focusflow.tasks") || "null") || defaultTasks,
      newTaskTitle: "",
      newTaskPriority: "normal",
      energy: "medium",
      availableMinutes: 90,
      sdkStatus: "Copilot SDK: checking",
      planMeta: "Ready",
      plan: null,
      planError: false,
      isPlanning: false,
    };
  },
  mounted() {
    this.checkCopilotSdk();
    this.askCopilot();
  },
  methods: {
    saveTasks() {
      localStorage.setItem("focusflow.tasks", JSON.stringify(this.tasks));
    },
    addTask() {
      const title = this.newTaskTitle.trim();

      if (!title) {
        return;
      }

      this.tasks.unshift({
        id: crypto.randomUUID(),
        title,
        priority: this.newTaskPriority,
      });
      this.newTaskTitle = "";
      this.saveTasks();
    },
    removeTask(taskId) {
      this.tasks = this.tasks.filter((task) => task.id !== taskId);
      this.saveTasks();
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
          tasks: this.tasks.map(({ title, priority }) => ({ title, priority })),
          energy: this.energy,
          available_minutes: Number(this.availableMinutes),
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