import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

// Next 16 removed the `next lint` command and `eslint-config-next` now ships a
// native flat config. Consume the presets directly instead of via FlatCompat.
const eslintConfig = [
  ...coreWebVitals,
  ...typescript,
  {
    // eslint-config-next sets `react.version: "detect"`, which makes
    // eslint-plugin-react call the removed `context.getFilename()` under
    // ESLint 10. Pin the installed React major to skip version auto-detection.
    settings: { react: { version: "19" } },
  },
  {
    // `react-hooks/set-state-in-effect` is a new rule enabled by default in the
    // React-Compiler-aligned eslint-plugin-react-hooks v6 that ships with
    // eslint-config-next 16. It flags the existing (valid) "kick off an async
    // refresh on mount" pattern. Keep it visible as a warning rather than
    // refactoring working components as part of this dependency upgrade.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "coverage/**",
      "playwright-report/**",
      "out/**",
    ],
  },
];

export default eslintConfig;
