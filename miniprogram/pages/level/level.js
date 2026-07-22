const api = require("../../services/api");

const levels = [
  { key: "beginner", title: "新手级", subtitle: "从基础字形开始", icon: "新" },
  { key: "proficient", title: "熟练级", subtitle: "平衡观察与判断", icon: "熟" },
  { key: "challenge", title: "挑战级", subtitle: "挑战容易混淆的字形", icon: "挑" },
];

function buildLevels(settings) {
  return levels.map((level) => ({
    key: level.key,
    title: level.title,
    subtitle: level.subtitle,
    icon: level.icon,
    weights: settings.modes[level.key].map((value, index) => ({ star: index + 1, value })),
  }));
}

Page({
  data: { levels: [], loading: true, questionCount: 10 },

  onLoad() { this.loadLevels(); },

  async loadLevels() {
    try {
      const settings = await api.getQuizSettings();
      this.setData({ levels: buildLevels(settings), questionCount: settings.questionCount });
    } catch (error) { wx.showToast({ title: "难度设置加载失败", icon: "none" }); }
    finally { this.setData({ loading: false }); }
  },

  selectLevel(event) { wx.navigateTo({ url: `/pages/quiz/quiz?mode=${event.currentTarget.dataset.mode}` }); },
});
