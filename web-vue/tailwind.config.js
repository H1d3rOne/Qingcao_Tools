const colorVar = (name) => `rgb(var(${name}) / <alpha-value>)`

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: colorVar('--primary-color-rgb'),
          dark: colorVar('--primary-hover-rgb'),
          deep: colorVar('--primary-deep-rgb')
        },
        dark: {
          DEFAULT: colorVar('--app-bg-rgb'),
          lighter: colorVar('--app-surface-alt-rgb'),
          card: colorVar('--app-surface-rgb'),
          glass: colorVar('--app-surface-glass-rgb')
        },
        accent: {
          DEFAULT: colorVar('--app-accent-rgb'),
          soft: colorVar('--app-accent-soft-rgb'),
          alt: colorVar('--app-accent-alt-rgb'),
          glow: colorVar('--app-accent-glow-rgb')
        },
        gradient: {
          start: colorVar('--app-gradient-start-rgb'),
          mid: colorVar('--app-gradient-mid-rgb'),
          end: colorVar('--app-gradient-end-rgb')
        },
        white: colorVar('--utility-white-rgb'),
        gray: {
          300: colorVar('--utility-gray-300-rgb'),
          400: colorVar('--utility-gray-400-rgb'),
          500: colorVar('--utility-gray-500-rgb'),
          600: colorVar('--utility-gray-600-rgb'),
          700: colorVar('--utility-gray-700-rgb'),
          800: colorVar('--utility-gray-800-rgb')
        }
      },
      backdropBlur: {
        glass: '16px'
      },
      boxShadow: {
        glass: '0 8px 32px rgba(var(--app-shadow-rgb), 0.3), inset 0 1px 0 rgba(var(--utility-white-rgb), 0.04)',
        'glass-hover': '0 12px 40px rgba(var(--app-shadow-rgb), 0.4), inset 0 1px 0 rgba(var(--utility-white-rgb), 0.06)',
        'accent-glow': '0 4px 16px rgba(var(--app-accent-glow-rgb), 0.2)'
      }
    }
  },
  plugins: []
}
