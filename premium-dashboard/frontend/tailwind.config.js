/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'mp-black': '#080808',
        'mp-orange': '#FF6600',
        'glass': 'rgba(30, 41, 59, 0.45)',
      },
      backdropFilter: {
        'blur-md': 'blur(12px)',
      },
    },
  },
  plugins: [],
}
