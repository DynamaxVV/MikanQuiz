const api = require("../../services/api");

Page({
  data: { displayName: "", editingName: false, draftName: "", isAdmin: false },
  onShow() {
    this.setData({ displayName: wx.getStorageSync("quiz-display-name") || "" });
    this.checkAdmin();
  },
  async checkAdmin() {
    const adminToken = wx.getStorageSync("quiz-admin-token");
    if (!adminToken) return this.setData({ isAdmin: false });
    try {
      await api.getAdminSession(adminToken);
      this.setData({ isAdmin: true });
    } catch (error) {
      wx.removeStorageSync("quiz-admin-token");
      this.setData({ isAdmin: false });
    }
  },
  openName() { this.setData({ editingName: true, draftName: this.data.displayName }); },
  updateName(event) { this.setData({ draftName: event.detail.value }); },
  saveName() {
    const displayName = this.data.draftName.trim().slice(0, 20);
    wx.setStorageSync("quiz-display-name", displayName);
    this.setData({ displayName, editingName: false });
  },
  closeName() { this.setData({ editingName: false }); },
  goLevel() { wx.navigateTo({ url: "/pages/level/level" }); },
  async goAdmin() {
    const adminToken = wx.getStorageSync("quiz-admin-token");
    if (!adminToken) return wx.navigateTo({ url: "/pages/admin-login/admin-login" });
    try {
      await api.getAdminSession(adminToken);
      wx.navigateTo({ url: "/pages/admin/admin" });
    } catch (error) {
      wx.removeStorageSync("quiz-admin-token");
      wx.navigateTo({ url: "/pages/admin-login/admin-login" });
    }
  },
});
