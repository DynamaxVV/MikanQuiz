const api = require("../../services/api");

const defaultSettings = {
  questionCount: 10,
  modes: {
    beginner: [90, 10, 0], proficient: [40, 40, 20],
    challenge: [10, 40, 50],
  },
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
    loading: true, savingStrategy: false, savingOptions: false, settings: defaultSettings,
    strategyRows: rows(defaultSettings), submissionGroups: [],
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
        api.listSubmissions(this.adminToken, { page: 1, pageSize: 50 }), api.getOptionGroups(this.adminToken),
      ]);
      const settings = data[0];
      this.setData({
        settings, strategyRows: rows(settings),
        submissionItems: data[1].items, submissionGroups: groupSubmissions(data[1].items),
        submissionPage: data[1].page, submissionsTotal: data[1].total, optionGroups: data[2],
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

  async saveStrategy() {
    this.setData({ savingStrategy: true });
    try {
      await api.saveQuizStrategy(this.adminToken, this.data.settings);
      wx.showToast({ title: "出题策略已保存", icon: "success" });
    } catch (error) { wx.showToast({ title: error.message || "策略保存失败", icon: "none" }); }
    finally { this.setData({ savingStrategy: false }); }
  },

  updateOptionName(event) {
    const { group, option } = event.currentTarget.dataset;
    this.setData({ [`optionGroups[${group}].options[${option}].name`]: event.detail.value });
  },
  addOption(event) {
    const index = event.currentTarget.dataset.group;
    const optionGroups = this.data.optionGroups;
    optionGroups[index].options.push({ id: "", name: "", minimumDifficulty: 1 });
    this.setData({ optionGroups });
  },
  updateOptionDifficulty(event) {
    const { group, option } = event.currentTarget.dataset;
    this.setData({ [`optionGroups[${group}].options[${option}].minimumDifficulty`]: Number(event.detail.value) + 1 });
  },
  async saveOptions() {
    this.setData({ savingOptions: true });
    try { await api.saveOptionGroups(this.adminToken, this.data.optionGroups); wx.showToast({ title: "字体分区已保存", icon: "success" }); }
    catch (error) { wx.showToast({ title: error.message || "字体分区保存失败", icon: "none" }); }
    finally { this.setData({ savingOptions: false }); }
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
