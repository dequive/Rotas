import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nav:    "var(--nav)",
        soft:   "var(--soft)",
        panel:  "var(--panel)",
        ink:    "var(--ink)",
        muted:  "var(--muted)",
        line:   "var(--line)",
        blue:   "var(--blue)",
        green:  "var(--green)",
        orange: "var(--orange)",
        red:    "var(--red)",
        cyan:   "var(--cyan)",
      },
    },
  },
  plugins: [],
}
export default config
