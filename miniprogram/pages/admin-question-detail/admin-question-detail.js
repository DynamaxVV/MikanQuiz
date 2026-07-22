const api = require("../../services/api");

function formatQuestion(item) {
  const stars = [];
  for (let index = 0; index < (item.difficulty || 1); index += 1) stars.push(index);
  return {
    _id: item.id, text: item.text, imageUrl: item.imageUrl || "", difficulty: item.difficulty || 1,
    stars, answer: item.answer,
    options: item.options.map((text, index) => ({ key: String.fromCharCode(65 + index), text })),
    explanation: item.explanation || "",
  };
}

Page({
  data: { loading: true, question: null },

  onLoad(options) {
    this.id = options.id;
    this.adminToken = wx.getStorageSync(api.ADMIN_TOKEN_KEY);
    this.loadQuestion();
  },

  async loadQuestion() {
    try {
      this.setData({ question: formatQuestion(await api.getAdminQuestion(this.adminToken, this.id)) });
    } catch (error) {
      wx.showToast({ title: error.message || "题目加载失败", icon: "none" });
    } finally { this.setData({ loading: false }); }
  },

  previewImage() {
    const url = this.data.question.imageUrl;
    if (url) wx.previewImage({ current: url, urls: [url] });
  },

  editQuestion() { wx.navigateTo({ url: `/pages/admin-question-form/admin-question-form?id=${this.id}` }); },
});
