var fs = require("fs");
var vm = require("vm");
var code = fs.readFileSync("E:/AI24X/ai24x-website/ai24x01/web/config/locales.js", "utf8");
vm.runInThisContext(code);
var en = global.AI24X_LOCALES.en;
var html = fs.readFileSync("E:/AI24X/ai24x-website/ai24x01/web/console.html", "utf8");
var keys = [];
var re = /data-i18n(?:-html|-placeholder)?="([^"]+)"/g;
var m;
while ((m = re.exec(html))) keys.push(m[1]);
var miss = keys.filter(function (k) {
  return !en[k];
});
console.log("console keys", keys.length, "miss", miss);

var i18n = fs.readFileSync("E:/AI24X/ai24x-website/ai24x01/web/js/i18n.js", "utf8");
global.window = global;
global.localStorage = {
  _d: { ai24x_lang: "en" },
  getItem: function (k) {
    return this._d[k] || null;
  },
  setItem: function (k, v) {
    this._d[k] = String(v);
  },
};
global.document = {
  documentElement: { lang: "" },
  querySelectorAll: function () {
    return { forEach: function () {} };
  },
  getElementById: function () {
    return null;
  },
};
vm.runInThisContext(i18n);
global.AI24X_I18N.setLang("en");
[
  "page.console.title",
  "page.console.sub",
  "page.console.actions.logout",
  "auth.login.title",
  "page.refer.title",
].forEach(function (k) {
  console.log(k, "=>", global.AI24X_I18N.t(k));
});
