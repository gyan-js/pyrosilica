/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: '#0D0B0A',
        surface: '#1A1614',
        border: '#2C2620',
        idle: '#332C24',
        primary: '#FF6A00',
        secondary: '#FFB238',
        alert: '#FF4470',
        text: '#F0E6DC',
        muted: '#8A7C6E',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}