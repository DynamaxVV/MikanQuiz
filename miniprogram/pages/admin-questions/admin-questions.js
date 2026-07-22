const api = require("../../services/api");

function formatQuestion(item) {
  const stars = [];
  for (let index = 0; index < (item.difficulty || 1); index += 1) stars.push(index);
  return { _id: item.id, text: item.text, difficulty: item.difficulty || 1, stars, imageUrl: item.imageUrl || "" };
}

Page({
  data: { loading: true, questions: [], page: 1, total: 0, loadingMore: false },
  onLoad() { this.adminToken = wx.getStorageSync("quiz-admin-token"); },
  onShow() { this.loadQuestions(); },
  async loadQuestions() {
    this.setData({ loading: true });
    try {
      const response = await api.listAdminQuestions(this.adminToken, { page: 1, pageSize: 100 });
      this.setData({ questions: response.items.map(formatQuestion), page: response.page, total: response.total });
    } catch (error) {
      wx.showToast({ title: "无法读取题库", icon: "none" });
    } finally { this.setData({ loading: false }); }
  },
  async loadMore() {
    if (this.data.loadingMore || this.data.questions.length >= this.data.total) return;
    this.setData({ loadingMore: true });
    try {
      const response = await api.listAdminQuestions(this.adminToken, { page: this.data.page + 1, pageSize: 100 });
      this.setData({
        questions: this.data.questions.concat(response.items.map(formatQuestion)),
        page: response.page, total: response.total,
      });
    } catch (error) { wx.showToast({ title: error.message || "加载题库失败", icon: "none" }); }
    finally { this.setData({ loadingMore: false }); }
  },
  goAdd() { wx.navigateTo({ url: "/pages/admin-question-form/admin-question-form" }); },
  goDetail(event) { wx.navigateTo({ url: `/pages/admin-question-detail/admin-question-detail?id=${event.currentTarget.dataset.id}` }); },
  async deleteQuestion(event) {
    const dialog = await wx.showModal({ title: "删除题目", content: "删除后无法恢复，确定继续吗？" });
    if (!dialog.confirm) return;
    try {
      await api.deleteAdminQuestion(this.adminToken, event.currentTarget.dataset.id);
      this.loadQuestions();
    } catch (error) { wx.showToast({ title: "删除失败", icon: "none" }); }
  },
});
