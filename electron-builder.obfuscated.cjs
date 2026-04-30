const { build } = require("./package.json");

module.exports = {
  ...build,
  directories: {
    ...(build.directories || {}),
    app: "release/obfuscated-code",
    output: "dist-obfuscated",
  },
};
