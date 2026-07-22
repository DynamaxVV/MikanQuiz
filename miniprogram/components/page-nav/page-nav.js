Component({
  properties: { title: { type: String, value: "" } },
  data: { top: 20 },
  lifetimes: { attached() { this.setData({ top: wx.getSystemInfoSync().statusBarHeight || 20 }); } },
  methods: {
    back() { const pages = getCurrentPages(); if (pages.length > 1) wx.navigateBack(); else wx.reLaunch({ url: "/pages/index/index" }); },
    home() { wx.reLaunch({ url: "/pages/index/index" }); },
  },
});
