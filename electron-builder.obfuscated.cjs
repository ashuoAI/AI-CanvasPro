const { build } = require("./package.json");

module.exports = {
  ...build,
  directories: {
    ...(build.directories || {}),
    app: "release/electron-obfuscated-app",
    output: "dist-obfuscated",
  },
};
