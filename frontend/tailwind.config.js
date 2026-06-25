/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cdp: {
          bg: '#FFFFFF',
          card: '#F8FAFC',
          accent: '#2563EB',
          success: '#059669',
          warning: '#D97706',
          danger: '#DC2626',
          muted: '#94A3B8',
          text: '#0F172A',
          'text-muted': '#64748B',
          border: '#E2E8F0',
          hover: '#F1F5F9',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        xl: '12px',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 4px 12px 0 rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.08)',
        'elevated': '0 10px 25px -3px rgb(0 0 0 / 0.06), 0 4px 8px -4px rgb(0 0 0 / 0.04)',
      },
    },
  },
  plugins: [],
}
