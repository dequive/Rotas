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
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
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

        // ── ROTAS Design System v1.3.1 ────────────────────────
        rotas: {
          50: 'var(--rotas-50)',
          100: 'var(--rotas-100)',
          200: 'var(--rotas-200)',
          300: 'var(--rotas-300)',
          400: 'var(--rotas-400)',
          500: 'var(--rotas-500)',
          600: 'var(--rotas-600)',
          700: 'var(--rotas-700)',
          800: 'var(--rotas-800)',
          900: 'var(--rotas-900)',
          950: 'var(--rotas-950)',
        },
        'accent-action': {
          400: 'var(--accent-400)',
          500: 'var(--accent-500)',
          600: 'var(--accent-600)',
          soft: 'var(--accent-soft)',
        },
        focus: {
          DEFAULT: 'var(--focus-ring)',
          soft: 'var(--focus-ring-soft)',
        },
        'status-reception': {
          DEFAULT: 'var(--status-reception)',
          soft: 'var(--status-reception-soft)',
        },
        'status-diagnosis': {
          DEFAULT: 'var(--status-diagnosis)',
          soft: 'var(--status-diagnosis-soft)',
        },
        'status-awaiting': {
          DEFAULT: 'var(--status-awaiting)',
          soft: 'var(--status-awaiting-soft)',
        },
        'status-supplement': {
          DEFAULT: 'var(--status-supplement)',
          soft: 'var(--status-supplement-soft)',
        },
        'status-execution': {
          DEFAULT: 'var(--status-execution)',
          soft: 'var(--status-execution-soft)',
        },
        'status-quality': {
          DEFAULT: 'var(--status-quality)',
          soft: 'var(--status-quality-soft)',
        },
        'status-delivered': {
          DEFAULT: 'var(--status-delivered)',
          soft: 'var(--status-delivered-soft)',
        },
        'status-cancelled': {
          DEFAULT: 'var(--status-cancelled)',
          soft: 'var(--status-cancelled-soft)',
        },
        'status-draft': {
          DEFAULT: 'var(--status-draft)',
          soft: 'var(--status-draft-soft)',
        },

        // ── Compatibility aliases for incremental migration ───
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
          border: 'var(--success-border)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          bg: 'var(--warning-bg)',
          border: 'var(--warning-border)',
        },
        error: {
          DEFAULT: 'var(--error)',
          bg: 'var(--error-bg)',
          border: 'var(--error-border)',
        },
        info: {
          DEFAULT: 'var(--info)',
          bg: 'var(--info-bg)',
          border: 'var(--info-border)',
        },
        // ── Semantic border tokens ─────────────────────────────
        'blue-border': 'var(--blue-border)',
        // ── Track / fill ──────────────────────────────────────
        track: 'var(--track)',
        // ── Surface tokens ────────────────────────────────────
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'surface-elevated': 'var(--surface-elevated)',
        'border-strong': 'var(--border-strong)',
        'document-paper': 'var(--document-paper)',
        'document-ink': 'var(--document-ink)',
        'document-muted': 'var(--document-muted)',
        'document-header': 'var(--document-header)',
        'document-canvas': 'var(--document-canvas)',
        // ── Text tokens ───────────────────────────────────────
        'ink-2': 'var(--ink-2)',
        tertiary: 'var(--tertiary-color)',
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
        'r-full': 'var(--r-full)',
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
        s9: 'var(--s9)',
      },
      boxShadow: {
        'design-sm': 'var(--shadow-sm)',
        design: 'var(--shadow)',
        'design-md': 'var(--shadow-md)',
        'design-lg': 'var(--shadow-lg)',
        card: 'var(--shadow-card)',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
