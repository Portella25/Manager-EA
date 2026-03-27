/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Barlow', 'sans-serif'],
        condensed: ['Barlow Condensed', 'sans-serif'],
      },
      colors: {
        bg: {
          dark: 'var(--color-bg-dark)',
          card: 'var(--color-bg-card)',
        },
        semantic: {
          green: 'var(--color-semantic-green)',
          red: 'var(--color-semantic-red)',
          purple: 'var(--color-semantic-purple)',
          gold: 'var(--color-semantic-gold)',
          blue: 'var(--color-semantic-blue)',
        },
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
        }
      }
    },
  },
  plugins: [],
}
