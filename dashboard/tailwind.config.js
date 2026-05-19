/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy:   { DEFAULT: '#1A3A5C', light: '#2A5080', dark: '#102640' },
        gold:   { DEFAULT: '#A07830', light: '#C49A3C', dark: '#7A5C20' },
        sage:   { DEFAULT: '#1A6B3C', light: '#2A8B4E', dark: '#0E4A28' },
        coral:  { DEFAULT: '#C0392B', light: '#E04030', dark: '#922B21' },
        cream:  { DEFAULT: '#F8F9FA', dark: '#E9ECEF' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
