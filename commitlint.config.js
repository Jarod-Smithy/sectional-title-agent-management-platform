// Conventional Commits config.
// Keeps the standard rules (incl. body-max-line-length: 100) for human commits,
// but exempts bot-generated commits (Dependabot) whose auto-generated bodies
// contain long changelog URLs that legitimately exceed the line-length limit.
module.exports = {
  extends: ["@commitlint/config-conventional"],
  ignores: [
    (message) => /(^|\n)Signed-off-by: dependabot\[bot\]/.test(message),
  ],
};
