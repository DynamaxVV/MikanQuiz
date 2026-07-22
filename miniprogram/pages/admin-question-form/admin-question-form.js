const api = require("../../services/api");

const DEFAULT_TITLE = "请选择以下日文对应的汉字字体";
const emptyForm = () => ({ text: DEFAULT_TITLE, imageUrl: "", difficulty: 2, correctOptionId: "", explanation: "" });

function questionToForm(question) {
  return { text: question.text, imageUrl: question.imageUrl || "", difficulty: question.difficulty || 1, correctOptionId: question.correctOptionId, explanation: question.explanation || "" };
}

Page({
  data: { form: emptyForm(), saving: false, uploadingImage: false, optionGroups: [] },

  onLoad(options) {
    this.adminToken = wx.getStorageSync(api.ADMIN_TOKEN_KEY);
    this.questionId = options.id || "";
    if (this.questionId) wx.setNavigationBarTitle({ title: "编辑题目" });
    this.load();
  },

  async load() {
    try {
      const calls = [api.getOptionGroups(this.adminToken)];
      if (this.questionId) calls.push(api.getAdminQuestion(this.adminToken, this.questionId));
      const data = await Promise.all(calls);
      this.setData({ optionGroups: data[0], form: data[1] ? questionToForm(data[1]) : this.data.form });
    } catch (error) { wx.showToast({ title: error.message || "题目加载失败", icon: "none" }); }
  },

  updateField(event) {
    const update = {};
    update[`form.${event.currentTarget.dataset.field}`] = event.detail.value;
    this.setData(update);
  },
  selectAnswer(event) { this.setData({ "form.correctOptionId": String(event.currentTarget.dataset.id) }); },
  selectDifficulty(event) { this.setData({ "form.difficulty": Number(event.currentTarget.dataset.value) }); },

  async chooseImage() {
    try {
      const result = await wx.chooseMedia({ count: 1, mediaType: ["image"] });
      const filePath = result.tempFiles[0] && result.tempFiles[0].tempFilePath;
      if (!filePath) return;
      this.setData({ uploadingImage: true });
      const imageUrl = await api.uploadAdminImage(this.adminToken, filePath);
      if (!imageUrl) throw new Error("图片上传失败");
      this.setData({ "form.imageUrl": imageUrl });
    } catch (error) {
      if (error && error.errMsg && error.errMsg.includes("cancel")) return;
      wx.showToast({ title: error.message || "图片上传失败", icon: "none" });
    } finally { this.setData({ uploadingImage: false }); }
  },
  removeImage() { this.setData({ "form.imageUrl": "" }); },

  async saveQuestion() {
    const { form } = this.data;
    if (!form.text.trim() || !form.imageUrl || !form.correctOptionId || !form.explanation.trim()) {
      wx.showToast({ title: "请填写题目、上传题图、正确字体和解析", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    const question = { text: form.text.trim(), imageUrl: form.imageUrl.trim(), difficulty: form.difficulty, correctOptionId: form.correctOptionId, explanation: form.explanation.trim() };
    try {
      if (this.questionId) await api.updateAdminQuestion(this.adminToken, this.questionId, question);
      else await api.createAdminQuestion(this.adminToken, question);
      wx.showToast({ title: this.questionId ? "题目已更新" : "题目已加入题库", icon: "success" });
      setTimeout(() => wx.navigateBack(), 700);
    } catch (error) { wx.showToast({ title: error.message || "保存失败", icon: "none" }); }
    finally { this.setData({ saving: false }); }
  },
});
