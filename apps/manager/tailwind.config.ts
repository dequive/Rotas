import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      colors: {
        // ── Legacy aliases (keep for unmigrated components) ──
        nav: 'var(--nav)',
        soft: 'var(--soft)',
        panel: 'var(--panel)',
        ink: 'var(--ink)',
        muted: 'var(--muted-color)',
        line: 'var(--line)',
        green: 'var(--green)',
        orange: 'var(--orange)',
        red: 'var(--red)',
        cyan: 'var(--cyan)',

        // ── DESIGN.md semantic tokens ─────────────────────────
        amber: {
          DEFAULT: 'var(--amber)',
          light: 'var(--amber-light)',
          dark: 'var(--amber-dark)',
        },
        blue: {
          DEFAULT: 'var(--blue)',
          light: 'var(--blue-light)',
          dark: 'var(--blue-dark)',
        },
        success: {
          DEFAULT: 'var(--success)',
          bg: 'var(--success-bg)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          bg: 'var(--warning-bg)',
        },
        error: {
          DEFAULT: 'var(--error)',
          bg: 'var(--error-bg)',
        },
        info: {
          DEFAULT: 'var(--info)',
          bg: 'var(--info-bg)',
        },
        // ── Surface tokens ────────────────────────────────────
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'border-strong': 'var(--border-strong)',
        // ── Text tokens ───────────────────────────────────────
        'ink-2': 'var(--ink-2)',
        placeholder: 'var(--placeholder)',
        // ── Sidebar tokens ────────────────────────────────────
        'sidebar-bg': 'var(--sidebar-bg)',
        'sidebar-hover': 'var(--sidebar-hover)',
        'sidebar-active': 'var(--sidebar-active)',
        'sidebar-text': 'var(--sidebar-text)',
        'sidebar-text-active': 'var(--sidebar-text-active)',
        'sidebar-section': 'var(--sidebar-section)',

        // ── shadcn/ui HSL tokens (required by shadcn components) ─
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: 'hsl(var(--destructive))',
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        'r-sm': 'var(--r-sm)',
        'r-md': 'var(--r-md)',
        'r-lg': 'var(--r-lg)',
        'r-xl': 'var(--r-xl)',
      },
      spacing: {
        s1: 'var(--s1)',
        s2: 'var(--s2)',
        s3: 'var(--s3)',
        s4: 'var(--s4)',
        s5: 'var(--s5)',
        s6: 'var(--s6)',
        s7: 'var(--s7)',
        s8: 'var(--s8)',
      },
      boxShadow: {
        'design-sm': 'var(--shadow-sm)',
        'design-md': 'var(--shadow-md)',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
