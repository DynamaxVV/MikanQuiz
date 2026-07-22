const api = require("../../services/api");

Page({
  data: { username: "", password: "", loading: false },

  onLoad() {
    this.redirectIfAuthorized();
  },

  async redirectIfAuthorized() {
    const adminToken = wx.getStorageSync("quiz-admin-token");
    if (!adminToken) return;
    try {
      await api.getAdminSession(adminToken);
      wx.redirectTo({ url: "/pages/admin/admin" });
    } catch (error) {
      wx.removeStorageSync("quiz-admin-token");
    }
  },

  updateUsername(event) { this.setData({ username: event.detail.value }); },
  updatePassword(event) { this.setData({ password: event.detail.value }); },

  async login() {
    const username = this.data.username.trim();
    const password = this.data.password;
    if (!username || !password) {
      wx.showToast({ title: "请输入账号和密码", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    try {
      const result = await api.login(username, password);
      if (!result.token) throw new Error("登录响应无效");
      wx.setStorageSync(api.ADMIN_TOKEN_KEY, result.token);
      this.setData({ password: "" });
      wx.redirectTo({ url: "/pages/admin/admin" });
    } catch (error) {
      this.setData({ password: "" });
      wx.showToast({ title: error.message || "登录失败", icon: "none" });
    } finally { this.setData({ loading: false }); }
  },
});
