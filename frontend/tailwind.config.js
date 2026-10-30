/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Semantic color variables
        brand: {
          bg: 'var(--color-bg)',
          surface: 'var(--color-surface)',
          border: 'var(--color-border)',
          'text-primary': 'var(--color-text-primary)',
          'text-secondary': 'var(--color-text-secondary)',
          'text-muted': 'var(--color-text-muted)',
          primary: 'var(--color-primary)',
          'primary-text': 'var(--color-primary-text)',
          success: 'var(--color-success)',
          warning: 'var(--color-warning)',
          danger: 'var(--color-danger)',
          info: 'var(--color-info)',
        },
        // Policy colors
        policy: {
          static: '#64748B',
          loadAware: '#2563EB',
          ai: '#16A34A',
        },
        // Utilization Heat colors
        heat: {
          low: '#16A34A',
          med: '#EAB308',
          high: '#EA580C',
          crit: '#DC2626',
          failed: '#94A3B8',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans Gujarati', 'Noto Sans Devanagari', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '8px',
        md: '8px',
        lg: '12px',
      },
    },
  },
  plugins: [],
}
