import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync(new URL("./global.css", import.meta.url), "utf8");

describe("chat composer layout", () => {
  it("anchors the absolute composer to the chat page instead of the viewport", () => {
    expect(styles).toMatch(/\.chat-page\s*\{[^}]*position:\s*relative/s);
    expect(styles).toMatch(/\.composer-shell\s*\{[^}]*position:\s*absolute/s);
  });
});
