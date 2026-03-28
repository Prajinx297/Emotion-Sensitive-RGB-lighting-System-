/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0f172a',
        glass: 'rgba(30, 41, 59, 0.7)',
        glassBorder: 'rgba(255, 255, 255, 0.1)',
      },
      boxShadow: {
        glass: '0 10px 15px -3px rgba(0,0,0,0.1)',
      }
    },
  },
  plugins: [],
};
