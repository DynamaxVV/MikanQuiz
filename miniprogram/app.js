const apiConfig = require("./config/api");

App({
  globalData: {
    apiBaseUrl: apiConfig.apiBaseUrl,
  },
});
