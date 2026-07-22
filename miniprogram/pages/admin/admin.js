const api = require("../../services/api");

Page({
  data: { checked: false, authorized: false },

  onLoad() {
    this.adminToken = wx.getStorageSync("quiz-admin-token");
    this.checkAdmin();
  },

  async checkAdmin() {
    try {
      await api.getAdminSession(this.adminToken);
      this.setData({ authorized: true });
    } catch (error) {
      wx.removeStorageSync("quiz-admin-token");
    } finally {
      this.setData({ checked: true });
    }
  },

  goQuestions() { wx.navigateTo({ url: "/pages/admin-questions/admin-questions" }); },
  goAddQuestion() { wx.navigateTo({ url: "/pages/admin-question-form/admin-question-form" }); },
  goSettings() { wx.navigateTo({ url: "/pages/admin-settings/admin-settings" }); },
  async logout() {
    const token = this.adminToken;
    wx.removeStorageSync(api.ADMIN_TOKEN_KEY);
    try { await api.logout(token); } catch (error) { /* 本地令牌已清除。 */ }
    wx.reLaunch({ url: "/pages/index/index" });
  },
});
