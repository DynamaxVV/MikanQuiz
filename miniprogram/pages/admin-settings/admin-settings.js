const api = require("../../services/api");

const defaultSettings = {
  questionCount: 10,
  modes: {
    beginner: [65, 25, 10, 0, 0], proficient: [15, 25, 30, 20, 10],
    challenge: [0, 10, 20, 30, 40],
  },
  fontPresets: [],
};

function rows(settings) {
  return ["beginner", "proficient", "challenge"].map((key) => ({
    key, title: { beginner: "新手级", proficient: "熟练级", challenge: "挑战级" }[key],
    weights: settings.modes[key].map((value, index) => ({ value, index, mode: key, star: index + 1 })),
  }));
}

function groupSubmissions(submissions) {
  const groups = {};
  submissions.forEach((item) => {
    const name = item.displayName || item.display_name || item.userLabel || "未命名用户";
    if (!groups[name]) groups[name] = [];
    groups[name].push(item);
  });
  return Object.keys(groups).map((name) => ({
    name, items: groups[name], previewItems: groups[name].slice(0, 3),
    remainingCount: Math.max(0, groups[name].length - 3), expanded: false,
  }));
}

Page({
  data: {
    loading: true, savingStrategy: false, savingFonts: false, settings: defaultSettings,
    strategyRows: rows(defaultSettings), fontText: "", submissionGroups: [],
    submissionItems: [], submissionPage: 1, submissionsTotal: 0, loadingMore: false,
  },

  onLoad() {
    this.adminToken = wx.getStorageSync(api.ADMIN_TOKEN_KEY);
    this.load();
  },

  async load() {
    try {
      const data = await Promise.all([
        api.getAdminSettings(this.adminToken),
        api.listSubmissions(this.adminToken, { page: 1, pageSize: 50 }),
      ]);
      const settings = data[0];
      this.setData({
        settings, strategyRows: rows(settings), fontText: settings.fontPresets.join("\n"),
        submissionItems: data[1].items, submissionGroups: groupSubmissions(data[1].items),
        submissionPage: data[1].page, submissionsTotal: data[1].total,
      });
    } catch (error) { wx.showToast({ title: error.message || "加载失败", icon: "none" }); }
    finally { this.setData({ loading: false }); }
  },

  updateCount(event) {
    const settings = this.data.settings;
    settings.questionCount = Number(event.detail.value) || 0;
    this.setData({ settings });
  },

  updateWeight(event) {
    const settings = this.data.settings;
    const data = event.currentTarget.dataset;
    settings.modes[data.mode][data.index] = Number(event.detail.value) || 0;
    this.setData({ settings, strategyRows: rows(settings) });
  },

  updateFonts(event) { this.setData({ fontText: event.detail.value }); },

  async saveStrategy() {
    this.setData({ savingStrategy: true });
    try {
      await api.saveQuizStrategy(this.adminToken, this.data.settings);
      wx.showToast({ title: "出题策略已保存", icon: "success" });
    } catch (error) { wx.showToast({ title: error.message || "策略保存失败", icon: "none" }); }
    finally { this.setData({ savingStrategy: false }); }
  },

  async saveFonts() {
    const fontPresets = this.data.fontText.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
    this.setData({ savingFonts: true });
    try {
      await api.saveFontPresets(this.adminToken, fontPresets);
      this.setData({ "settings.fontPresets": fontPresets });
      wx.showToast({ title: "字体快捷项已保存", icon: "success" });
    } catch (error) { wx.showToast({ title: error.message || "字体快捷项保存失败", icon: "none" }); }
    finally { this.setData({ savingFonts: false }); }
  },

  async loadMoreSubmissions() {
    if (this.data.loadingMore || this.data.submissionItems.length >= this.data.submissionsTotal) return;
    this.setData({ loadingMore: true });
    try {
      const next = await api.listSubmissions(this.adminToken, { page: this.data.submissionPage + 1, pageSize: 50 });
      const submissionItems = this.data.submissionItems.concat(next.items);
      this.setData({
        submissionItems, submissionGroups: groupSubmissions(submissionItems),
        submissionPage: next.page, submissionsTotal: next.total,
      });
    } catch (error) { wx.showToast({ title: error.message || "加载提交记录失败", icon: "none" }); }
    finally { this.setData({ loadingMore: false }); }
  },

  toggleGroup(event) {
    const index = event.currentTarget.dataset.index;
    const groups = this.data.submissionGroups;
    groups[index].expanded = !groups[index].expanded;
    this.setData({ submissionGroups: groups });
  },
});
