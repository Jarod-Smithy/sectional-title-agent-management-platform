// Root ESLint flat config (ESLint 10).
//
// `npm run lint` runs `eslint .` from the repo root. Under ESLint 10 the
// configuration file is resolved relative to each linted file, so the
// frontend workspace is governed by its own `frontend/eslint.config.mjs`
// (Next.js shareable config). This root config covers the remaining
// repo-level JavaScript/TypeScript (e.g. tooling/config files and the
// standalone smoke test) so the monorepo lint passes end to end.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/coverage/**",
      "**/cdk.out/**",
      "**/playwright-report/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,cjs}"],
    languageOptions: {
      sourceType: "commonjs",
      globals: { ...globals.node },
    },
  },
  {
    files: ["**/*.{mjs,ts,tsx}"],
    languageOptions: {
      sourceType: "module",
      globals: { ...globals.node },
    },
  },
];
