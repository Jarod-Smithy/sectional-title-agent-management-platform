import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// Shared MSW server for the Vitest run (started in vitest.setup.ts).
export const server = setupServer(...handlers);
